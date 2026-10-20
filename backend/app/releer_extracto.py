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
versión, los `pendiente_revision` con correo y, en modo «solo agregar lo que faltaba», los `conciliado` de
TARJETA que ya están en una cuenta de crédito (máx. 3 por apertura en total). Los conciliados de otro tipo no se
tocan solos. Ver docs/RELECTURA_DE_TARJETAS.md. Al mejorar el lector, sube VERSION_LECTOR. (Costo aceptado: un extracto nuevo también se relee una vez; es
idempotente y no cuesta nada visible.)"""
from __future__ import annotations

import json
import logging
from collections import Counter

from sqlalchemy.orm import Session

from app import cuadre_extracto
from app import rendimientos_extracto
from app import saldo_inicial_auto
from app import estado_traer
from app import punto_partida
from app.extractos_tarjeta_nu import datos_de_lectura, es_extracto_tarjeta_nu, leer_extracto_tarjeta_nu
from app.conciliacion import parse_bank_date, parse_texto_con_regex, fijar_nombre_titular, huella_de_linea
from app.crons import liberar_marca, reclamar_marca
from app.extractos_gmail import abrir_pdf, claves_candidatas, descargar_adjunto, listar_adjuntos_pdf
from app import corregir_pago, corregir_tipo, fechas_extracto
from app import duplicados as dup
from app.cuentas_banco import CREDITO, producto_de_texto
from app.models import ExtractoCorreo, HistorialExtracto, Cuenta

logger = logging.getLogger(__name__)

VERSION_LECTOR = "2026-10-v7-fechas-de-tarjeta"  # súbela cuando el lector de extractos mejore y valga la pena releer
PREFIJO = "releer_extracto:"
MAXIMO_AUTOMATICO = 3  # PDFs por apertura de «Traer movimientos»

# Estados que la persona (o la app) ya resolvió: se conservan tal cual.
REEMPLAZABLES = ("faltante", "anterior", "corregir_monto", "corregir_tipo")

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


def es_de_tarjeta(h: HistorialExtracto, cuenta, fila: ExtractoCorreo | None) -> bool:
    """¿Es el extracto de una TARJETA de crédito? Por la cuenta, por la lectura de tarjeta guardada o porque el
    asunto/archivo del correo hablan de tarjeta de crédito (los extractos viejos no traen `lectura_json`)."""
    if cuenta is not None and (getattr(cuenta, "tipo", "") or "").lower() == "credito":
        return True
    if (h.lectura or {}).get("resumen_tarjeta") is not None:
        return True
    texto = f"{getattr(fila, 'asunto', '') or ''} {getattr(fila, 'archivo', '') or ''}"
    return producto_de_texto(texto) == CREDITO


def _leer_lineas(texto: str) -> list[dict]:
    """Líneas del extracto con el lector de hoy (solo lectores de banco; nunca IA externa al releer)."""
    lineas, _descartadas = parse_texto_con_regex(texto) if texto else ([], 0)
    return [m for m in lineas if abs(m.get("monto") or 0) >= 1]


def _clave(items: list[dict]) -> Counter:
    return Counter(i.get("fingerprint") for i in items)


ESTADOS_CON_MOVIMIENTO = ("importado", "exacto", "aproximado", "completado")


def _huerfana_igual(item: dict, huerfanas: list[dict]) -> dict | None:
    """Una línea conservada que no tiene pareja por huella pero ES esta (mismo día, tipo, monto y comercio parecido):
    la leyó el lector anterior con otro texto. Sirve para no volver a ofrecerla como «por importar»."""
    f = parse_bank_date(item.get("fecha"))
    for h in huerfanas:
        g = parse_bank_date(h.get("fecha"))
        if not f or not g or f.date() != g.date() or h.get("tipo") != item.get("tipo"):
            continue
        if abs(abs(float(h.get("monto") or 0)) - abs(float(item.get("monto") or 0))) > 0.5:
            continue
        sim = dup.similitud_comercio(h.get("descripcion"), item.get("descripcion"))
        if sim is None or sim >= 0.75:
            return h
    return None


def reconciliar(review_viejo: list[dict], nuevas: list[dict], *, descartados: dict | None = None,
                inicio=None, solo_agregar: bool = False) -> tuple[list[dict], dict]:
    """Función pura (sin base de datos): devuelve (review nuevo, {cambiadas, agregadas, quitadas, conservadas}).
    `nuevas` = líneas leídas hoy, ya con `cuenta` puesta. Las líneas nuevas salen sin sugerencia de categoría
    (la pone quien llama). Con `solo_agregar` nunca se quita ni se cambia nada de lo que ya había: solo se
    suman líneas. Una línea nueva que equivale 1:1 a una conservada sin pareja por huella (el lector anterior la
    leyó con otro texto, o el extracto cambió de cuenta y la huella lleva el id de la cuenta) NO se ofrece de
    nuevo: la conservada anota la huella nueva en `huellas_alt` y así la próxima relectura también la reconoce."""
    conservadas = [i for i in review_viejo if i.get("estado") not in REEMPLAZABLES]
    pool_viejo = [i for i in review_viejo if i.get("estado") in REEMPLAZABLES]

    libres = Counter(i.get("fingerprint") for i in conservadas if i.get("estado") != "sobrante")
    huellas_libro = set(libres)
    # Lo que el usuario borró antes y ya está representado por una línea conservada no se cuenta dos veces.
    por_fp = Counter(dict((descartados or {}).get("fingerprints") or {}))
    for i in conservadas:
        if i.get("estado") == "borrado_antes" and por_fp.get(i.get("fingerprint"), 0) > 0:
            por_fp[i["fingerprint"]] -= 1

    alias: dict[str, list[str]] = {}  # huella alterna -> huellas de las conservadas que la reconocen
    for i in conservadas:
        for a in i.get("huellas_alt") or []:
            alias.setdefault(a, []).append(i.get("fingerprint"))

    resto = []  # lo que hoy se lee y NO estaba resuelto
    for mov in nuevas:
        fp = huella_de_linea(mov, huellas_libro)
        if libres.get(fp, 0) > 0:
            libres[fp] -= 1  # ya estaba resuelta: se conserva la que hay (una sola vez por línea)
            continue
        if alias.get(fp):
            dueno = alias[fp].pop(0)
            if libres.get(dueno, 0) > 0:
                libres[dueno] -= 1  # la reconoce por una huella alterna anotada antes
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

    if solo_agregar:
        mantenidas, quitadas = mantenidas + quitadas, []

    # Conservadas que ninguna línea de hoy reclamó por huella (el lector anterior las leyó distinto).
    huerfanas, restantes = [], Counter(libres)
    for i in conservadas:
        if i.get("estado") in ESTADOS_CON_MOVIMIENTO and restantes.get(i.get("fingerprint"), 0) > 0:
            restantes[i["fingerprint"]] -= 1
            huerfanas.append(i)
    reconocidas, nuevas_reales = 0, []
    for item in agregadas:
        igual = _huerfana_igual(item, huerfanas) if item["estado"] == "faltante" else None
        if igual is None:
            nuevas_reales.append(item)
            continue
        huerfanas = [h for h in huerfanas if h is not igual]
        igual.setdefault("huellas_alt", []).append(item["fingerprint"])
        reconocidas += 1
    agregadas = nuevas_reales
    por_importar = sum(1 for i in agregadas if i["estado"] == "faltante")

    cambiadas = min(len(quitadas), len(agregadas))
    res = {
        "por_importar": por_importar, "reconocidas": reconocidas,
        "cambiadas": cambiadas,
        "agregadas": len(agregadas) - cambiadas,
        "quitadas": len(quitadas) - cambiadas,
        "conservadas": len([i for i in conservadas if i.get("estado") != "sobrante"]) + len(mantenidas),
    }
    if not quitadas and not agregadas:
        return (list(review_viejo) if reconocidas else review_viejo), res

    ids_quitadas = {id(q) for q in quitadas}
    final = [i for i in review_viejo if id(i) not in ids_quitadas] + agregadas
    lineas = sorted((i for i in final if i.get("estado") != "sobrante"),
                    key=lambda i: parse_bank_date(i.get("fecha")) or parse_bank_date("2999-01-01"))
    return lineas + [i for i in final if i.get("estado") == "sobrante"], res


def frase_resultado(res: dict) -> str:
    def n(c, uno, varios):
        return f"{c} {uno if c == 1 else varios}"
    corr = res.get("correcciones") or 0
    if not (res["cambiadas"] or res["agregadas"] or res["quitadas"]):
        if corr:
            return f"Encontré {n(corr, 'corrección', 'correcciones')} en lo que ya importaste. Revísala antes de importar."
        return "Ya estaba bien leído: no cambié nada."
    partes = [f"Cambié {n(res['cambiadas'], 'línea', 'líneas')}", f"agregué {res['agregadas']}"]
    if res["quitadas"]:
        partes.append(f"quité {res['quitadas']}")
    partes.append(f"conservé {res['conservadas']}")
    return ", ".join(partes)


def releer_historial(db: Session, usuario, h: HistorialExtracto, gmail=None, solo_agregar: bool = False) -> dict:
    """Relee UN historial. Lanza ReleerError (sin escribir nada) si no se puede. Devuelve el resultado.

    `solo_agregar` (extractos ya conciliados): jamás modifica ni quita lo que había; si la lectura de tarjeta
    no suma lo que dice el extracto, no se agrega nada (solo se guarda la lectura para poder avisarlo)."""
    from app.autocat import ClasificadorUsuario
    from app.contabilidad import CATEGORIA_PAGO_TARJETA
    from app.routers import correos as rc
    from app.routers.conciliacion import (
        _confirmar_pagos_de_tarjeta, _descartados, _enriquecer_dudosas, _saldos_del_extracto,
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
        # Extracto de cuenta con «Rendimiento total»: esa plata suma al saldo pero no es una línea; se agrega UNA línea.
        nuevas, lectura_rend = rendimientos_extracto.con_rendimiento(nuevas, texto, cuenta)
        for m in nuevas:
            m["cuenta"] = cuenta.id

        lectura_hoy = datos_de_lectura(leer_extracto_tarjeta_nu(texto)) if es_extracto_tarjeta_nu(texto) else None
        no_cuadra = bool(solo_agregar and lectura_hoy is not None and not lectura_hoy["lectura_completa"])
        nuevo_review, res = reconciliar(
            review, [] if no_cuadra else nuevas, descartados=_descartados(db, usuario.id, cuenta.id, nuevas),
            inicio=punto_partida.fecha_inicio(db, usuario.id), solo_agregar=solo_agregar)
        if no_cuadra:  # nada se agrega si lo leído no cuadra con el extracto; la lectura queda para avisarlo
            nuevo_review, res = review, {**res, "cambiadas": 0, "agregadas": 0, "quitadas": 0, "por_importar": 0}

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
                if item.get("categoria_fija"):
                    item["categoria_sugerida"] = item["categoria_fija"]
                    item["razon_categoria"], item["confianza_categoria"] = rendimientos_extracto.razon_de(item), 1.0
                if item.get("pago_tarjeta") and (item["categoria_sugerida"] == "Otros" or item.get("pago_detalle")):
                    item["categoria_sugerida"] = CATEGORIA_PAGO_TARJETA
                    item["razon_categoria"] = "parece el pago de tu tarjeta desde otra cuenta tuya"
                    item["confianza_categoria"] = 0.6
            _confirmar_pagos_de_tarjeta(db, usuario.id, cuenta, h.banco_detectado or "", pendientes)
            _enriquecer_dudosas(db, usuario.id, pendientes)

        # Un pago que el lector viejo leyó con otro monto y ya está importado: se CORRIGE ese movimiento (no se duplica).
        corregidas = 0 if no_cuadra else (corregir_pago.marcar(db, usuario.id, cuenta.id, nuevo_review)
                                          + corregir_tipo.marcar(db, usuario.id, cuenta.id, nuevo_review))
        if corregidas:  # lo que se vuelve corrección ya no es una compra por importar
            res["por_importar"] = sum(1 for i in nuevo_review if id(i) not in viejos and i.get("estado") == "faltante")
        res["correcciones"] = sum(1 for i in nuevo_review if i.get("estado") in corregir_pago.ESTADOS_CORRECCION)
        if corregidas:
            nuevo_review = list(nuevo_review)  # copia: así se guarda aunque la reconciliación no cambiara nada

        if nuevo_review is not review:
            h.review_json = json.dumps(nuevo_review, default=str)
            h.total_movimientos = len([i for i in nuevo_review if i.get("estado") != "sobrante"])
            estado_traer.sincronizar_contadores(h, nuevo_review)
        if lectura_hoy is not None:  # el resumen y las comprobaciones se actualizan con el lector de hoy
            h.lectura_json = json.dumps(lectura_hoy, default=str)
        elif lectura_rend is not None:  # cuenta con rendimientos: «Leí N líneas, incluidos tus rendimientos...»
            h.lectura_json = json.dumps(lectura_rend, default=str)
        if h.saldos_origen != "manual" and not (solo_agregar and h.saldo_final_extracto is not None):
            saldos = _saldos_del_extracto(cuenta, texto, nuevas)
            if saldos and (saldos.get("saldo_final") is not None or saldos.get("saldo_inicial") is not None):
                cuadre_extracto.guardar_saldos(h, saldos)
        if lectura_hoy is not None:  # las fechas del extracto salen del resumen del PDF (corte, no límite de pago)
            fechas_extracto.aplicar_resumen(h, lectura_hoy.get("resumen_tarjeta"))
        db.commit()
        try:  # releer puede traer un saldo inicial distinto: el ajuste inicial se recalcula
            saldo_inicial_auto.refrescar_de_usuario(db, usuario.id, [h.cuenta_id])
        except Exception:  # noqa: BLE001 - no estorba a la relectura
            db.rollback()
    except ReleerError:
        db.rollback()
        raise
    except Exception as e:  # noqa: BLE001 - Gmail, descarga o PDF: no se escribe nada
        db.rollback()
        logger.warning("Releer extracto falló (usuario %s): %s", usuario.id[:8], type(e).__name__)
        raise ReleerError(502, MSG_FALLA) from e

    reclamar_marca(db, usuario.id, PREFIJO + h.id, VERSION_LECTOR)  # ya está al día con este lector
    res = {**res, "estado": h.estado, "historial_id": h.id, "mensaje": frase_resultado(res),
           "mensaje_lectura": h.mensaje_lectura, "lectura_completa": h.lectura_completa,
           "lineas_leidas": (h.lectura or {}).get("lineas_leidas", len(nuevas)), "no_cuadra": no_cuadra}
    return res


def _conciliados_de_tarjeta(db: Session, usuario) -> list[HistorialExtracto]:
    """Conciliados de TARJETA con correo que ya están en una cuenta de crédito (los que están en otra cuenta los
    arregla «Arreglar mis extractos de la tarjeta», que primero los mueve: releerlos allí traería líneas a la
    cuenta equivocada)."""
    hist = (db.query(HistorialExtracto)
            .filter(HistorialExtracto.usuario_id == usuario.id, HistorialExtracto.estado == "conciliado")
            .order_by(HistorialExtracto.creado_en.desc()).all())
    if not hist:
        return []
    cuentas = {c.id: c for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all()}
    salida = []
    for h in hist:
        cuenta = cuentas.get(h.cuenta_id)
        if cuenta is None or (cuenta.tipo or "").lower() != "credito":
            continue
        fila = correo_de(db, h)
        if fila is not None and es_de_tarjeta(h, cuenta, fila):
            salida.append(h)
    return salida


def releer_pendientes(db: Session, usuario, maximo: int = MAXIMO_AUTOMATICO) -> dict:
    """Al abrir «Traer movimientos»: relee UNA vez (por versión del lector) los `pendiente_revision` con correo y,
    después, los `conciliado` de TARJETA ya en su cuenta de crédito en modo «solo agregar lo que faltaba»
    (jamás toca lo importado; si hay líneas nuevas el extracto vuelve a «por revisar»). Máximo `maximo` en total.
    Nunca lanza; si falla, libera la marca para reintentar."""
    out = {"releidos": 0, "cambiados": 0, "pendientes": 0}
    try:
        try:  # fechas de tarjeta que ya se pueden arreglar con lo guardado (sin Gmail)
            if fechas_extracto.completar_fechas(db, usuario.id):
                db.commit()
        except Exception:  # noqa: BLE001 - un extra: no estorba a la relectura
            db.rollback()
        hist = (db.query(HistorialExtracto)
                .filter(HistorialExtracto.usuario_id == usuario.id, HistorialExtracto.estado == "pendiente_revision")
                .order_by(HistorialExtracto.creado_en.desc()).all())
        tarjetas = _conciliados_de_tarjeta(db, usuario)
        from app import registrar_ajustes_extracto  # también los de ahorro que probablemente traen rendimientos o 4x1000 sin registrar
        tarjetas += [h for h, _est, _c in registrar_ajustes_extracto.candidatos_a_completar(db, usuario)]
        if not hist and not tarjetas:
            return out
        from app.crons import MarcaCron
        hechas = {m.clave for m in db.query(MarcaCron).filter(
            MarcaCron.usuario_id == usuario.id, MarcaCron.valor == VERSION_LECTOR,
            MarcaCron.clave.like(PREFIJO + "%")).all()}
        con_correo = {c.historial_id for c in db.query(ExtractoCorreo.historial_id).filter(
            ExtractoCorreo.usuario_id == usuario.id, ExtractoCorreo.historial_id.in_([h.id for h in hist]),
            ExtractoCorreo.archivo != "").all()} if hist else set()
        cola = [(h, False) for h in hist if h.id in con_correo and (PREFIJO + h.id) not in hechas]
        cola += [(h, True) for h in tarjetas if (PREFIJO + h.id) not in hechas]
        out["pendientes"] = max(0, len(cola) - maximo)
        for h, solo_agregar in cola[:maximo]:
            clave = PREFIJO + h.id
            if not reclamar_marca(db, usuario.id, clave, VERSION_LECTOR):
                continue
            try:
                r = releer_historial(db, usuario, h, solo_agregar=solo_agregar)
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
