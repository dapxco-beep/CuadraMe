"""Extractos en estado «error»: reintentar los que se pueden y limpiar los que no.

Un historial `estado='error'` nace cuando de un PDF no salió ningún movimiento (ver
routers/conciliacion._procesar_extracto). Antes quedaba para siempre: sin forma de reintentar ni de
quitarlo. Aquí vive lo que lo resuelve:

  · `completar_motivos`   los errores antiguos sin `motivo_error` reciben uno legible (nunca vacío).
  · `correo_de_error`     el correo (ExtractoCorreo) del que vino, si lo hay. Los subidos a mano NO tienen:
                          no se pueden reintentar (el PDF no se guarda), solo quitar y volver a subir.
  · `reintentar_historial` re-trae el adjunto de Gmail (como releer_saldos), lo abre con la clave guardada y,
                          si ahora se lee, REEMPLAZA la fila de error por el extracto procesado: el error se
                          borra (no queda un historial de más) y los movimientos solo se crean al importar,
                          que ya es idempotente.
  · `reintentar_errores_clave` lo anterior para los errores de clave, en lote pequeño (al guardar la clave
                          o al abrir «Traer movimientos»).

Nunca lanza hacia fuera: un fallo de Gmail deja el error como estaba."""
from __future__ import annotations

import base64
import logging

from sqlalchemy.orm import Session

from app.compartidos import reclamar_estado
from app.models import ExtractoCorreo, HistorialExtracto

logger = logging.getLogger(__name__)

MOTIVOS_CLAVE = ("clave_faltante", "clave_incorrecta")
MOTIVO_POR_DEFECTO = "pdf_ilegible"  # error antiguo sin motivo guardado: lo único seguro es «no pudimos leerlo»
MAXIMO_POR_LLAMADA = 3  # PDFs por llamada: cada uno descarga y lee un adjunto


def _norm(t: str | None) -> str:
    return " ".join((t or "").lower().replace("archivo:", "").split())


def completar_motivos(db: Session, usuario_id: str) -> int:
    """Da un `motivo_error` a los errores que no lo tienen: el del correo vinculado si lo hay, si no el
    genérico «pdf_ilegible». Hace commit solo si cambió algo. Devuelve cuántos completó."""
    vacios = db.query(HistorialExtracto).filter(
        HistorialExtracto.usuario_id == usuario_id, HistorialExtracto.estado == "error",
        (HistorialExtracto.motivo_error.is_(None)) | (HistorialExtracto.motivo_error == "")).all()
    if not vacios:
        return 0
    por_historial = {e.historial_id: e for e in db.query(ExtractoCorreo).filter(
        ExtractoCorreo.usuario_id == usuario_id, ExtractoCorreo.historial_id.in_([h.id for h in vacios])).all()}
    for h in vacios:
        e = por_historial.get(h.id)
        h.motivo_error = (e.motivo_error if e is not None and e.motivo_error else None) or MOTIVO_POR_DEFECTO
    db.commit()
    return len(vacios)


def correo_de_error(db: Session, h: HistorialExtracto, *, correos: list | None = None):
    """El ExtractoCorreo del que vino este error, o None (subido a mano).
    1) vínculo directo (`historial_id`); 2) errores de CLAVE antiguos sin vínculo: un correo que sigue
    pidiendo clave para la MISMA cuenta (si hay varios, el del mismo banco; si no, el más reciente)."""
    if correos is None:
        correos = db.query(ExtractoCorreo).filter(
            ExtractoCorreo.usuario_id == h.usuario_id, ExtractoCorreo.archivo != "").all()
    directo = next((e for e in correos if e.historial_id == h.id and e.archivo and e.gmail_msg_id), None)
    if directo is not None:
        return directo
    if h.motivo_error not in MOTIVOS_CLAVE:
        return None
    candidatos = [e for e in correos if e.archivo and e.gmail_msg_id and e.historial_id is None
                  and e.estado == "falta_clave" and e.cuenta_sugerida_id == h.cuenta_id]
    if not candidatos:
        return None
    mismo_banco = [e for e in candidatos if _norm(e.banco) and _norm(e.banco) == _norm(h.banco_detectado)]
    elegidos = mismo_banco or candidatos
    return max(elegidos, key=lambda e: e.recibido_en or e.creado_en)


def reintentable(db: Session, h: HistorialExtracto, correos: list | None = None) -> bool:
    return h.estado == "error" and correo_de_error(db, h, correos=correos) is not None


def reintentar_historial(db: Session, usuario, h: HistorialExtracto, gmail=None) -> dict:
    """Reintenta UN error. Devuelve {ok, reemplazado, historial_id, mensaje}. `ok` = ahora se lee."""
    from app.extractos_gmail import abrir_pdf, claves_candidatas, descargar_adjunto, listar_adjuntos_pdf
    from app.extractos_vista import clasificar_motivo, frase_error
    from app.routers import correos as rc
    from app.routers.conciliacion import procesar_extracto_de_gmail
    from app.schemas import ProcesarExtractoRequest

    res = {"ok": False, "reemplazado": False, "historial_id": None, "mensaje": ""}
    fila = correo_de_error(db, h)
    if fila is None:
        res["mensaje"] = "Este extracto se subió a mano: súbelo de nuevo o quítalo de la lista."
        return res
    perfil = rc._get_or_create_perfil(db, usuario.id)
    if not perfil.gmail_conectado or not perfil.gmail_refresh_token_enc:
        res["mensaje"] = "Gmail no está conectado."
        return res
    if perfil.gmail_leer_extractos is False:
        res["mensaje"] = "Tienes apagada la lectura de «Extractos»."
        return res
    # Candado: dos reintentos a la vez (doble toque, guardar la clave + abrir la pantalla) no procesan dos veces.
    if not reclamar_estado(db, HistorialExtracto, h.id, "error", "reintentando"):
        db.rollback()
        res["mensaje"] = "Ya lo estamos reintentando."
        return res
    db.commit()
    cuenta_id, fila_id = h.cuenta_id, fila.id
    motivo_nuevo, reemplazo = None, None
    errores_antes = {x.id for x in db.query(HistorialExtracto.id).filter(
        HistorialExtracto.usuario_id == usuario.id, HistorialExtracto.estado.in_(("error", "reintentando"))).all()}
    try:
        gmail = gmail or rc.cliente_gmail(perfil.gmail_refresh_token_enc)
        msg = gmail.users().messages().get(userId="me", id=fila.gmail_msg_id, format="full").execute()
        adj = next((a for a in listar_adjuntos_pdf(msg) if a["archivo"] == fila.archivo), None)
        if adj is None:
            res["mensaje"] = "El archivo ya no está en tu correo."
        else:
            pdf = descargar_adjunto(gmail, fila.gmail_msg_id, adj["attachment_id"])
            clave = rc._clave_pdf(db, usuario.id)
            estado, _texto, clave_usada = abrir_pdf(pdf, claves_candidatas(clave))
            if estado == "falta_clave":
                motivo_nuevo = clasificar_motivo(pide_clave=True, clave_dada=bool(clave))
                res["mensaje"] = frase_error(motivo_nuevo)
            elif estado != "ok":
                motivo_nuevo = clasificar_motivo(pdf_vacio=not pdf)
                res["mensaje"] = frase_error(motivo_nuevo)
            else:
                cuenta_destino = fila.cuenta_sugerida_id or cuenta_id
                reemplazo = procesar_extracto_de_gmail(
                    ProcesarExtractoRequest(pdf_base64=base64.b64encode(pdf).decode(), cuenta_id=cuenta_destino,
                                            password=clave_usada or ""), db, usuario)
    except Exception as e:  # noqa: BLE001 - Gmail/IA/lectura: el error se queda como estaba
        db.rollback()
        logger.warning("Reintento de extracto en error falló (usuario %s): %s", usuario.id[:8], type(e).__name__)
        res["mensaje"] = "No pudimos intentarlo ahora. Prueba de nuevo en un rato."
    # Estado final (filas frescas: procesar_extracto pudo haber hecho commit).
    db.expire_all()
    h2 = db.query(HistorialExtracto).filter(HistorialExtracto.id == h.id).first()
    if h2 is None:
        return res
    if reemplazo is not None and reemplazo.ok and reemplazo.historial_id:
        # Se lee: el extracto procesado reemplaza a la fila de error (sin dejar las dos).
        f2 = db.query(ExtractoCorreo).filter(ExtractoCorreo.id == fila_id).first()
        if f2 is not None:
            f2.estado, f2.historial_id, f2.motivo_error, f2.clave_resultado = "procesado", reemplazo.historial_id, None, "ok"
        db.delete(h2)
        db.commit()
        res.update(ok=True, reemplazado=True, historial_id=reemplazo.historial_id, mensaje="Listo: ya lo podemos revisar.")
        return res
    if reemplazo is not None:  # abrió pero siguen sin salir movimientos
        motivo_nuevo = reemplazo.motivo_error or "sin_movimientos"
        res["mensaje"] = frase_error(motivo_nuevo)
        # procesar_extracto dejó OTRO historial de error (el de este intento): sobra, nos quedamos con el de siempre.
        for extra in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == usuario.id,
                                                        HistorialExtracto.estado == "error").all():
            if extra.id not in errores_antes:
                db.delete(extra)
    h2.estado = "error"
    if motivo_nuevo:
        h2.motivo_error = motivo_nuevo
    elif not h2.motivo_error:
        h2.motivo_error = MOTIVO_POR_DEFECTO
    db.commit()
    return res


def reintentar_errores_clave(db: Session, usuario, maximo: int = MAXIMO_POR_LLAMADA) -> dict:
    """Reintenta los errores por clave que tienen correo. Pensado para correr al guardar la clave del PDF y al
    abrir «Traer movimientos». Devuelve {reintentados, leidos, pendientes}. Nunca lanza."""
    out = {"reintentados": 0, "leidos": 0, "pendientes": 0}
    try:
        completar_motivos(db, usuario.id)
        errores = db.query(HistorialExtracto).filter(
            HistorialExtracto.usuario_id == usuario.id, HistorialExtracto.estado == "error",
            HistorialExtracto.motivo_error.in_(MOTIVOS_CLAVE)).order_by(HistorialExtracto.creado_en).all()
        from app.routers import correos as rc
        if not errores or not rc._clave_pdf(db, usuario.id):
            return out
        correos = db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == usuario.id,
                                                  ExtractoCorreo.archivo != "").all()
        usados: set[str] = set()
        cola = []
        for h in errores:
            e = correo_de_error(db, h, correos=[c for c in correos if c.id not in usados])
            if e is not None:
                usados.add(e.id)  # un correo reemplaza UN error (no varios del mismo)
                cola.append(h)
        out["pendientes"] = max(0, len(cola) - maximo)
        for h in cola[:maximo]:
            r = reintentar_historial(db, usuario, h)
            out["reintentados"] += 1
            out["leidos"] += 1 if r["ok"] else 0
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Reintentar errores de clave falló (se ignora)")
    return out
