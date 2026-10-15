"""Leer de nuevo los saldos de extractos que ya se procesaron con un lector que no los reconocía.

Problema: un extracto (p. ej. Nu: «Tu dinero al inicio del mes») que se procesó antes de que el lector
supiera esas etiquetas quedó en `historial_extractos` sin saldos, y nunca se volvía a leer: la app
terminaba pidiendo escribirlos a mano.

El PDF NO se conserva (solo metadatos en `extractos_correo`), así que aquí se vuelve a TRAER de Gmail
usando el correo y el adjunto que ya están registrados (gmail_msg_id + archivo + historial_id). Solo se
completan los saldos del historial existente: no se crean movimientos, no se cambia el estado de la
conciliación ni se vuelve a importar nada, y por eso repetirlo no duplica.

Una sola vez por historial y versión del lector (marca `releer_saldos:<historial>` = VERSION). Si Gmail o
la descarga fallan, la marca se libera y se reintenta en la próxima sincronización. Nunca lanza."""
import json
import logging

from sqlalchemy.orm import Session

from app import cuadre_extracto
from app.crons import MarcaCron, liberar_marca, reclamar_marca
from app.extractos_gmail import abrir_pdf, claves_candidatas, descargar_adjunto, listar_adjuntos_pdf
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto

logger = logging.getLogger(__name__)

VERSION = "v1-nu-tu-dinero"  # súbela cuando el lector de saldos mejore y valga la pena releer
PREFIJO = "releer_saldos:"
MAXIMO_POR_CORRIDA = 6  # PDFs por llamada: se reparte en varias sincronizaciones para no pasar el timeout


def _sin_saldos(h: HistorialExtracto) -> bool:
    return h.saldo_final_extracto is None and h.saldo_inicial_extracto is None and h.saldos_origen != "manual"


def candidatos(db: Session, usuario_id: str) -> list[tuple[HistorialExtracto, ExtractoCorreo]]:
    """Historiales sin saldos que vinieron de un correo y aún no se intentaron con esta versión del lector."""
    filas = (
        db.query(ExtractoCorreo)
        .filter(ExtractoCorreo.usuario_id == usuario_id, ExtractoCorreo.historial_id.isnot(None))
        .order_by(ExtractoCorreo.recibido_en.desc())
        .all()
    )
    if not filas:
        return []
    hist = {h.id: h for h in db.query(HistorialExtracto).filter(
        HistorialExtracto.usuario_id == usuario_id,
        HistorialExtracto.id.in_([f.historial_id for f in filas])).all()}
    hechas = {m.clave for m in db.query(MarcaCron).filter(
        MarcaCron.usuario_id == usuario_id, MarcaCron.valor == VERSION, MarcaCron.clave.like(PREFIJO + "%")).all()}
    out, vistos = [], set()
    for f in filas:
        h = hist.get(f.historial_id)
        if h is None or h.id in vistos or h.estado == "error" or not _sin_saldos(h) or (PREFIJO + h.id) in hechas:
            continue
        vistos.add(h.id)
        out.append((h, f))
    return out


def pendientes_por_historial(db: Session, usuario_id: str) -> set[str]:
    return {h.id for h, _ in candidatos(db, usuario_id)}


def _movimientos(h: HistorialExtracto) -> list[dict]:
    try:
        review = json.loads(h.review_json or "[]")
    except ValueError:
        return []
    return [i for i in review if isinstance(i, dict) and i.get("estado") != "sobrante"]


def releer(db: Session, usuario_id: str, gmail, clave_pdf: str | None = None, maximo: int = MAXIMO_POR_CORRIDA) -> dict:
    """Relee saldos de hasta `maximo` historiales. Devuelve {leidos, sin_saldo, fallidos, pendientes}."""
    from app.routers.conciliacion import _saldos_del_extracto  # mismo lector que al procesar un extracto

    res = {"leidos": 0, "sin_saldo": 0, "fallidos": 0, "pendientes": 0}
    try:
        cola = candidatos(db, usuario_id)
        res["pendientes"] = max(0, len(cola) - maximo)
        for h, fila in cola[:maximo]:
            clave = PREFIJO + h.id
            if not reclamar_marca(db, usuario_id, clave, VERSION):
                continue  # otra corrida ya lo tomó
            try:
                cuenta = db.query(Cuenta).filter(Cuenta.id == h.cuenta_id).first()
                msg = gmail.users().messages().get(userId="me", id=fila.gmail_msg_id, format="full").execute()
                pdfs = listar_adjuntos_pdf(msg)
                adj = next((a for a in pdfs if a["archivo"] == fila.archivo), None) or (pdfs[0] if len(pdfs) == 1 else None)
                if adj is None:
                    res["sin_saldo"] += 1  # el adjunto ya no está: no se reintenta
                    continue
                pdf = descargar_adjunto(gmail, fila.gmail_msg_id, adj["attachment_id"])
                estado, texto, _ = abrir_pdf(pdf, claves_candidatas(clave_pdf))
                if estado != "ok" or cuenta is None:
                    res["sin_saldo"] += 1
                    continue
                saldos = _saldos_del_extracto(cuenta, texto, _movimientos(h))
                if saldos and (saldos.get("saldo_final") is not None or saldos.get("saldo_inicial") is not None):
                    if _sin_saldos(h):  # nunca pisar saldos que llegaron mientras tanto (p. ej. a mano)
                        cuadre_extracto.guardar_saldos(h, saldos)
                        db.commit()
                        res["leidos"] += 1
                else:
                    res["sin_saldo"] += 1
            except Exception:  # noqa: BLE001 - falla de Gmail o del PDF: se reintenta en la próxima
                db.rollback()
                liberar_marca(db, usuario_id, clave)
                res["fallidos"] += 1
                logger.warning("Releer saldos: no se pudo leer un extracto (usuario %s)", usuario_id[:8])
        return res
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Releer saldos falló (se ignora)")
        return res
