"""«Releer este extracto»: volver a leer un extracto YA procesado con el lector de hoy.

Problema: cuando el lector mejora (resumen de la factura anterior, «Cobro por cuota» limpio, saldos de Nu...)
los extractos viejos conservan la lectura vieja en `historial_extractos.review_json`. El PDF no se guarda, así
que se vuelve a TRAER de Gmail (como releer_saldos / extractos_error) usando el correo registrado.

Cómo se reconcilia con lo guardado, sin duplicar ni deshacer trabajo:
  · se CONSERVAN tal cual las líneas ya resueltas: importado, exacto, aproximado, completado, borrado_antes
    y los «sobrantes». Siguen vinculadas por movimiento_id / huella.
  · cada línea que el lector de hoy ve se compara con las conservadas por HUELLA (`huella_de_linea` reconoce
    también la huella vieja de una línea cuya lectura cambió): si ya estaba resuelta, no se agrega otra vez.
  · las que NO estaban resueltas (faltante / anterior) se REEMPLAZAN por la lectura nueva. Las que no
    cambiaron se dejan como estaban (así releer dos veces da el mismo resultado).
  · se recalculan los contadores y el estado (pendiente_revision si quedan faltantes, conciliado si no).
  · los saldos se actualizan solo si no eran manuales.
  · todo en una sola transacción: si Gmail o la descarga fallan no se escribe nada.

Versión del lector SIN columna nueva: la marca `releer_extracto:<id>` (tabla marcas_cron) guarda la
VERSION_LECTOR con la que se releyó cada historial. Al abrir «Traer movimientos» se releen UNA vez, con esta
versión, los `pendiente_revision` con correo (máx. 3 por apertura); los `conciliado` no se tocan solos.
Al mejorar el lector, sube VERSION_LECTOR. (Costo aceptado: un extracto nuevo también se relee una vez; es
idempotente y no cuesta nada visible.)"""
from __future__ import annotations

import json
import logging
from collections import Counter

from sqlalchemy.orm import Session

from app import cuadre_extracto
from app import estado_traer
from app import punto_partida
from app.conciliacion import parse_bank_date, parse_texto_con_regex, fijar_nombre_titular, huella_de_linea
from app.crons import liberar_marca, reclamar_marca
from app.extractos_gmail import abrir_pdf, claves_candidatas, descargar_adjunto, listar_adjuntos_pdf
from app.models import ExtractoCorreo, HistorialExtracto, Cuenta

logger = logging.getLogger(__name__)

VERSION_LECTOR = "2026-10-v1-resumen-factura"  # súbela cuando el lector de extractos mejore y valga la pena releer
PREFIJO = "releer_extracto:"
MAXIMO_AUTOMATICO = 3  # PDFs por apertura de «Traer movimientos»

# Estados que la persona (o la app) ya resolvió: se conservan tal cual.
REEMPLAZABLES = ("faltante", "anterior")

MSG_MANUAL = "Este extracto lo subiste a mano; súbelo de nuevo para leerlo otra vez."
MSG_FALLA = "No pudimos releerlo ahora. Prueba de nuevo en un rato; no cambié nada."


class ReleerError(Exception):
    """Falla amable: `estado` es el código HTTP sugerido y `mensaje` ya viene listo para mostrar."""

    def __init__(self, estado: int, mensaje: str):
        super().__init__(mensaje)
        self.estado, self.mensaje = estado, mensaje


def correo_de(db: Session, h: HistorialExtracto) -> ExtractoCorreo | None:
    """El correo del que vino el historial (None = subido a mano)."""
    return (db.query(ExtractoCorreo)
            .filter(ExtractoCorreo.usuario_id == h.usuario_id, ExtractoCorreo.historial_id == h.id,
                    ExtractoCorreo.archivo != "", ExtractoCorreo.gmail_msg_id.isnot(None))
            .order_by(ExtractoCorreo.recibido_en.desc()).first())


def _leer_lineas(texto: str) -> list[dict]:
    """Líneas del extracto con el lector de hoy (solo lectores de banco; nunca IA externa al releer)."""
    lineas, _descartadas = parse_texto_con_regex(texto) if texto else ([], 0)
    return [m for m in lineas if abs(m.get("monto") or 0) >= 1]


def _clave(items: list[dict]) -> Counter:
    return Counter(i.get("fingerprint") for i in items)


def reconciliar(review_viejo: list[dict], nuevas: list[dict], *, descartados: dict | None = None,
                inicio=None) -> tuple[list[dict], dict]:
    """Función pura (sin base de datos): devuelve (review nuevo, {cambiadas, agregadas, quitadas, conservadas}).
    `nuevas` = líneas leídas hoy, ya con `cuenta` puesta. Las líneas nuevas salen sin sugerencia de categoría
    (la pone quien llama)."""
    conservadas = [i for i in review_viejo if i.get("estado") not in REEMPLAZABLES]
    pool_viejo = [i for i in review_viejo if i.get("estado") in REEMPLAZABLES]

    libres = Counter(i.get("fingerprint") for i in conservadas if i.get("estado") != "sobrante")
    huellas_libro = set(libres)
    # Lo que el usuario borró antes y ya está representado por una línea conservada no se cuenta dos veces.
    por_fp = Counter(dict((descartados or {}).get("fingerprints") or {}))
    for i in conservadas:
        if i.get("estado") == "borrado_antes" and por_fp.get(i.get("fingerprint"), 0) > 0:
            por_fp[i["fingerprint"]] -= 1

    resto = []  # lo que hoy se lee y NO estaba resuelto
    for mov in nuevas:
        fp = huella_de_linea(mov, huellas_libro)
        if libres.get(fp, 0) > 0:
            libres[fp] -= 1  # ya estaba resuelta: se conserva la que hay (una sola vez por línea)
            continue
        item = {**mov, "fingerprint": fp, "estado": "faltante"}
        if por_fp.get(fp, 0) > 0:
            por_fp[fp] -= 1
            item["estado"] = "borrado_antes"
        elif inicio and punto_partida.es_anterior(parse_bank_date(item["fecha"]), inicio):
            item["estado"] = "anterior"
        resto.append(item)

    # Las que no cambiaron (misma huella) se quedan como estaban; el resto se reemplaza.
    pendientes_viejos = Counter(i.get("fingerprint") for i in pool_viejo)
    iguales, agregadas = Counter(), []
    for item in resto:
        fp = item["fingerprint"]
        if pendientes_viejos.get(fp, 0) > iguales[fp]:
            iguales[fp] += 1
        else:
            agregadas.append(item)
    mantenidas, quitadas = [], []
    gastados = Counter()
    for v in pool_viejo:
        fp = v.get("fingerprint")
        if gastados[fp] < iguales[fp]:
            gastados[fp] += 1
            mantenidas.append(v)
        else:
            quitadas.append(v)

    cambiadas = min(len(quitadas), len(agregadas))
    res = {
        "cambiadas": cambiadas,
        "agregadas": len(agregadas) - cambiadas,
        "quitadas": len(quitadas) - cambiadas,
        "conservadas": len([i for i in conservadas if i.get("estado") != "sobrante"]) + len(mantenidas),
    }
    if not quitadas and not agregadas:
        return review_viejo, res

    ids_quitadas = {id(q) for q in quitadas}
    final = [i for i in review_viejo if id(i) not in ids_quitadas] + agregadas
    lineas = sorted((i for i in final if i.get("estado") != "sobrante"),
                    key=lambda i: parse_bank_date(i.get("fecha")) or parse_bank_date("2999-01-01"))
    return lineas + [i for i in final if i.get("estado") == "sobrante"], res


def frase_resultado(res: dict) -> str:
    def n(c, uno, varios):
        return f"{c} {uno if c == 1 else varios}"
    if not (res["cambiadas"] or res["agregadas"] or res["quitadas"]):
        return "Ya estaba bien leído: no cambié nada."
    partes = [f"Cambié {n(res['cambiadas'], 'línea', 'líneas')}", f"agregué {res['agregadas']}"]
    if res["quitadas"]:
        partes.append(f"quité {res['quitadas']}")
    partes.append(f"conservé {res['conservadas']}")
    return ", ".join(partes)


def releer_historial(db: Session, usuario, h: HistorialExtracto, gmail=None) -> dict:
    """Relee UN historial. Lanza ReleerError (sin escribir nada) si no se puede. Devuelve el resultado."""
    from app.autocat import ClasificadorUsuario
    from app.contabilidad import CATEGORIA_PAGO_TARJETA
    from app.routers import correos as rc
    from app.routers.conciliacion import (
        _confirmar_pagos_de_factura, _descartados, _enriquecer_dudosas, _saldos_del_extracto,
    )

    if h.estado == "error":
        raise ReleerError(409, "Este extracto no se pudo leer; usa «Intentar de nuevo».")
    fila = correo_de(db, h)
    if fila is None:
        raise ReleerError(409, MSG_MANUAL)
    perfil = rc._get_or_create_perfil(db, usuario.id)
    if not perfil.gmail_conectado or not perfil.gmail_refresh_token_enc:
        raise ReleerError(409, "Gmail no está conectado.")
    cuenta = db.query(Cuenta).filter(Cuenta.id == h.cuenta_id, Cuenta.usuario_id == usuario.id).first()
    if cuenta is None:
        raise ReleerError(404, "No encontramos la cuenta de este extracto.")
    try:
        review = json.loads(h.review_json or "[]")
    except ValueError:
        review = []
    if not isinstance(review, list):
        review = []

    try:
        gmail = gmail or rc.cliente_gmail(perfil.gmail_refresh_token_enc)
        msg = gmail.users().messages().get(userId="me", id=fila.gmail_msg_id, format="full").execute()
        pdfs = listar_adjuntos_pdf(msg)
        adj = next((a for a in pdfs if a["archivo"] == fila.archivo), None) or (pdfs[0] if len(pdfs) == 1 else None)
        if adj is None:
            raise ReleerError(409, "El archivo ya no está en tu correo.")
        pdf = descargar_adjunto(gmail, fila.gmail_msg_id, adj["attachment_id"])
        estado, texto, _ = abrir_pdf(pdf, claves_candidatas(rc._clave_pdf(db, usuario.id)))
        if estado != "ok":
            raise ReleerError(409, "No pudimos abrir el PDF (¿cambió la clave?). No cambié nada.")
        fijar_nombre_titular(usuario.nombre)
        nuevas = _leer_lineas(texto)
        if not nuevas:
            raise ReleerError(409, "No pude leer movimientos en este PDF. No cambié nada.")
        for m in nuevas:
            m["cuenta"] = cuenta.id

        nuevo_review, res = reconciliar(
            review, nuevas, descartados=_descartados(db, usuario.id, cuenta.id, nuevas),
            inicio=punto_partida.fecha_inicio(db, usuario.id))

        # Las líneas nuevas llevan la misma ayuda que al procesar: categoría sugerida, pago de tarjeta, resumen.
        viejos = {id(i) for i in review}
        pendientes = [i for i in nuevo_review if id(i) not in viejos and i.get("estado") == "faltante"]
        if pendientes:
            modelo = ClasificadorUsuario(db, usuario.id)
            for item in pendientes:
                clasif = modelo.clasificar(item["descripcion"])
                item["categoria_sugerida"] = clasif["categoria"] if clasif else "Otros"
                item["razon_categoria"] = clasif.get("razon") if clasif else None
                item["confianza_categoria"] = clasif.get("confianza") if clasif else None
                if item.get("pago_tarjeta") and (item["categoria_sugerida"] == "Otros" or item.get("resumen_factura")):
                    item["categoria_sugerida"] = CATEGORIA_PAGO_TARJETA
                    item["razon_categoria"] = "parece el pago de tu tarjeta desde otra cuenta tuya"
                    item["confianza_categoria"] = 0.6
            _confirmar_pagos_de_factura(db, usuario.id, cuenta, h.banco_detectado or "", pendientes)
            _enriquecer_dudosas(db, usuario.id, pendientes)

        if nuevo_review is not review:
            h.review_json = json.dumps(nuevo_review, default=str)
            h.total_movimientos = len([i for i in nuevo_review if i.get("estado") != "sobrante"])
            estado_traer.sincronizar_contadores(h, nuevo_review)
        if h.saldos_origen != "manual":
            saldos = _saldos_del_extracto(cuenta, texto, nuevas)
            if saldos and (saldos.get("saldo_final") is not None or saldos.get("saldo_inicial") is not None):
                cuadre_extracto.guardar_saldos(h, saldos)
        db.commit()
    except ReleerError:
        db.rollback()
        raise
    except Exception as e:  # noqa: BLE001 - Gmail, descarga o PDF: no se escribe nada
        db.rollback()
        logger.warning("Releer extracto falló (usuario %s): %s", usuario.id[:8], type(e).__name__)
        raise ReleerError(502, MSG_FALLA) from e

    reclamar_marca(db, usuario.id, PREFIJO + h.id, VERSION_LECTOR)  # ya está al día con este lector
    res = {**res, "estado": h.estado, "historial_id": h.id, "mensaje": frase_resultado(res)}
    return res


def releer_pendientes(db: Session, usuario, maximo: int = MAXIMO_AUTOMATICO) -> dict:
    """Al abrir «Traer movimientos»: relee UNA vez (por versión del lector) los `pendiente_revision` con correo.
    Los `conciliado` no se tocan solos. Nunca lanza; si falla, libera la marca para reintentar."""
    out = {"releidos": 0, "cambiados": 0, "pendientes": 0}
    try:
        hist = (db.query(HistorialExtracto)
                .filter(HistorialExtracto.usuario_id == usuario.id, HistorialExtracto.estado == "pendiente_revision")
                .order_by(HistorialExtracto.creado_en.desc()).all())
        if not hist:
            return out
        from app.crons import MarcaCron
        hechas = {m.clave for m in db.query(MarcaCron).filter(
            MarcaCron.usuario_id == usuario.id, MarcaCron.valor == VERSION_LECTOR,
            MarcaCron.clave.like(PREFIJO + "%")).all()}
        con_correo = {c.historial_id for c in db.query(ExtractoCorreo.historial_id).filter(
            ExtractoCorreo.usuario_id == usuario.id, ExtractoCorreo.historial_id.in_([h.id for h in hist]),
            ExtractoCorreo.archivo != "").all()}
        cola = [h for h in hist if h.id in con_correo and (PREFIJO + h.id) not in hechas]
        out["pendientes"] = max(0, len(cola) - maximo)
        for h in cola[:maximo]:
            clave = PREFIJO + h.id
            if not reclamar_marca(db, usuario.id, clave, VERSION_LECTOR):
                continue
            try:
                r = releer_historial(db, usuario, h)
                out["releidos"] += 1
                out["cambiados"] += 1 if (r["cambiadas"] or r["agregadas"] or r["quitadas"]) else 0
            except ReleerError as e:
                if e.estado in (502, 404) or "Gmail" in e.mensaje:
                    liberar_marca(db, usuario.id, clave)  # falla pasajera: se reintenta en la próxima apertura
            except Exception:  # noqa: BLE001
                db.rollback()
                liberar_marca(db, usuario.id, clave)
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Releer extractos pendientes falló (se ignora)")
    return out
