"""Modelo de estados ÚNICO de «Traer movimientos»: qué pasó con cada extracto y qué falta por hacer.

Antes cada pantalla contaba por su lado: «cruzados» era exactos + aproximados (sin los completados),
el historial guardaba contadores que se quedaban viejos al importar y la pantalla mostraba solo los
`importados`. Resultado: un extracto con todo ya registrado decía «0 movimientos» y parecía que no
había pasado nada. Aquí hay UNA sola cuenta, hecha desde la revisión guardada (review_json), que es
lo que de verdad pasó con cada línea:

    leidas = ya_estaban + nuevas_agregadas + por_revisar + descartadas + anteriores

  ya_estaban        exactos + aproximados + completados (la línea coincide con algo que ya tenías)
  nuevas_agregadas  líneas que se agregaron como movimiento nuevo
  por_revisar       líneas «faltantes» que aún no se agregaron ni se descartaron
  descartadas       líneas que coinciden con algo que borraste antes (no resucitan)
  anteriores        líneas anteriores a tu fecha de inicio (no se ofrecen)
  duplicadas_detectadas  líneas que otro canal (correo, atajo, a mano) ya había registrado y se
                    juntaron con ese movimiento en vez de crear otro

Estado de un extracto: al_dia | por_revisar | necesita_clave | no_se_pudo_leer |
anterior_al_inicio | sin_movimientos_reales.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

AL_DIA = "al_dia"
POR_REVISAR = "por_revisar"
NECESITA_CLAVE = "necesita_clave"
NO_SE_PUDO_LEER = "no_se_pudo_leer"
ANTERIOR_AL_INICIO = "anterior_al_inicio"
SIN_MOVIMIENTOS_REALES = "sin_movimientos_reales"
ESTADOS = (AL_DIA, POR_REVISAR, NECESITA_CLAVE, NO_SE_PUDO_LEER, ANTERIOR_AL_INICIO, SIN_MOVIMIENTOS_REALES)

# Los que piden acción de la persona (van arriba, en «Por hacer»).
PIDEN_ACCION = (POR_REVISAR, NECESITA_CLAVE, NO_SE_PUDO_LEER)

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
          "octubre", "noviembre", "diciembre"]


def nombre_mes(clave: str | None) -> str:
    """'2026-04' -> 'Abril' (sin año si es del año en curso lo decide quien llama)."""
    try:
        a, m = int(clave[:4]), int(clave[5:7])
        return _MESES[m - 1].capitalize()
    except (TypeError, ValueError, IndexError):
        return ""


def _n(cantidad: int, uno: str, varios: str) -> str:
    return f"{cantidad} {uno if cantidad == 1 else varios}"


# ── Conteo (puro) ─────────────────────────────────────────────────────────────────────────
def contar_review(review: list[dict]) -> dict:
    """Cuenta qué pasó con cada línea leída de un extracto. Pura: solo mira los estados."""
    c = {"leidas": 0, "ya_estaban": 0, "nuevas_agregadas": 0, "por_revisar": 0, "descartadas": 0,
         "anteriores": 0, "duplicadas_detectadas": 0, "dudosas": 0}
    for i in review or []:
        est = i.get("estado")
        if est == "sobrante":
            continue  # es un movimiento tuyo que NO aparece en el extracto: no es una línea leída
        c["leidas"] += 1
        if est in ("exacto", "aproximado", "completado"):
            c["ya_estaban"] += 1
            if est == "aproximado":
                c["dudosas"] += 1
            if i.get("duplicado_evitado"):
                c["duplicadas_detectadas"] += 1
        elif est == "importado":
            c["nuevas_agregadas"] += 1
        elif est == "faltante":
            c["por_revisar"] += 1
        elif est == "borrado_antes":
            c["descartadas"] += 1
            if i.get("duplicado_evitado"):
                c["duplicadas_detectadas"] += 1
        elif est == "anterior":
            c["anteriores"] += 1
        else:  # estado raro: no se pierde, se pide mirar
            c["por_revisar"] += 1
    return c


def conteo_de_historial(h) -> dict:
    """Conteo de un historial. Con revisión guardada manda la revisión; los historiales de Excel/CSV
    (sin revisión) se leen de sus contadores: exactos = ya estaban, importados = agregados."""
    try:
        review = json.loads(h.review_json or "[]")
    except ValueError:
        review = []
    if review:
        return contar_review(review)
    total = int(h.total_movimientos or 0)
    ya = int(h.exactos or 0) + int(h.aproximados or 0)
    nuevas = int(h.importados or 0)
    por_revisar = int(h.faltantes or 0) if h.estado == "pendiente_revision" else 0
    return {"leidas": total, "ya_estaban": ya, "nuevas_agregadas": nuevas, "por_revisar": por_revisar,
            "descartadas": 0, "anteriores": max(0, total - ya - nuevas - por_revisar),
            "duplicadas_detectadas": int(h.exactos or 0), "dudosas": 0}


def estado_de_conteo(conteo: dict, historial_estado: str | None = None) -> str:
    if historial_estado == "error":
        return NO_SE_PUDO_LEER
    if conteo["leidas"] == 0:
        return SIN_MOVIMIENTOS_REALES
    if conteo["por_revisar"] > 0:
        return POR_REVISAR
    if conteo["leidas"] and conteo["leidas"] == conteo["anteriores"]:
        return ANTERIOR_AL_INICIO
    return AL_DIA


def frase(estado: str, conteo: dict, *, mes: str | None, cuenta: str, banco: str = "") -> str:
    """Una línea humana por extracto. Siempre dice qué pasó, aunque no se haya agregado nada."""
    mes_txt = nombre_mes(mes) or "Extracto"
    quien = cuenta or banco or "tu cuenta"
    cab = f"{mes_txt} · {quien}: "
    if estado == NECESITA_CLAVE:
        return cab + "falta la clave del PDF para poder leerlo"
    if estado == NO_SE_PUDO_LEER:
        return cab + "no pudimos leer el archivo. Prueba subirlo de nuevo o agrega los movimientos a mano"
    if estado == ANTERIOR_AL_INICIO:
        return cab + "es anterior a tu fecha de inicio, no se trae"
    if estado == SIN_MOVIMIENTOS_REALES:
        return cab + "no trae movimientos de plata (solo saldos o líneas en cero)"
    leidas, ya, nuevas, falta = conteo["leidas"], conteo["ya_estaban"], conteo["nuevas_agregadas"], conteo["por_revisar"]
    if estado == POR_REVISAR:
        if leidas == 0 and falta == 0:
            return cab + "nuevo, listo para revisar"
        return cab + f"{_n(leidas, 'movimiento leído', 'movimientos leídos')}, {ya} ya estaban y {_n(falta, 'falta registrar', 'faltan por registrar')}"
    if nuevas == 0:
        base = f"{_n(leidas, 'movimiento leído', 'movimientos leídos')}, "
        base += f"{ya} ya estaban registrados, 0 nuevos" if ya != 1 else "1 ya estaba registrado, 0 nuevos"
        return cab + base
    texto = f"{_n(nuevas, 'nuevo agregado', 'nuevos agregados')}, {ya} ya estaban" if ya != 1 else f"{_n(nuevas, 'nuevo agregado', 'nuevos agregados')}, 1 ya estaba"
    return cab + texto


# ── Base de datos ─────────────────────────────────────────────────────────────────────────
def _mes_de_historial(h) -> str | None:
    from app.conciliacion import parse_bank_date

    try:
        review = json.loads(h.review_json or "[]")
    except ValueError:
        review = []
    fechas = [d for d in (parse_bank_date(i.get("fecha")) for i in review if i.get("estado") != "sobrante") if d]
    if fechas:
        u = max(fechas)
        return f"{u.year:04d}-{u.month:02d}"
    return None


def sincronizar_contadores(h, review: list[dict]) -> None:
    """Deja los contadores del historial iguales a la revisión (antes se quedaban viejos al importar
    y por eso un extracto ya resuelto seguía diciendo «faltan N»). Sin commit."""
    if not review:
        return
    c = contar_review(review)
    h.exactos = sum(1 for i in review if i.get("estado") == "exacto")
    h.aproximados = sum(1 for i in review if i.get("estado") == "aproximado")
    h.faltantes = c["por_revisar"]
    h.importados = c["nuevas_agregadas"]
    if c["por_revisar"] == 0 and h.estado == "pendiente_revision":
        h.estado = "conciliado"
    elif c["por_revisar"] > 0 and h.estado == "conciliado":
        h.estado = "pendiente_revision"


def reconciliar_pendientes(db: Session, usuario_id: str, limite: int = 12) -> int:
    """Carrera entre canales: entre procesar un extracto y revisarlo, la app, el atajo o el correo
    pudieron registrar alguna de sus líneas «faltantes». Aquí esas líneas se JUNTAN con lo que ya
    existe (nunca se duplican) y el extracto pasa a «al día» solo, sin que la persona haga nada.
    También sale de «por revisar» lo que quedó anterior al punto de partida. Idempotente; hace commit
    solo si algo cambió. Devuelve cuántas líneas se resolvieron."""
    from app import duplicados as dup
    from app import punto_partida
    from app.autocat import ClasificadorUsuario
    from app.conciliacion import parse_bank_date
    from app.models import Cuenta, HistorialExtracto
    from app.routers.conciliacion import _absorbidas_por_otro_canal, _completar_con_extracto, _huella_linea

    hist = (db.query(HistorialExtracto)
            .filter(HistorialExtracto.usuario_id == usuario_id, HistorialExtracto.estado == "pendiente_revision")
            .order_by(HistorialExtracto.creado_en.desc()).limit(limite).all())
    if not hist:
        return 0
    inicio = punto_partida.fecha_inicio(db, usuario_id)
    modelo = None
    resueltas = 0
    for h in hist:
        try:
            review = json.loads(h.review_json or "[]")
        except ValueError:
            continue
        faltantes = [i for i in review if i.get("estado") == "faltante"]
        cambio = False
        for it in list(faltantes):
            if inicio and punto_partida.es_anterior(parse_bank_date(it.get("fecha")), inicio):
                it["estado"] = "anterior"
                faltantes.remove(it)
                cambio = True
        cuenta = db.query(Cuenta).filter(Cuenta.id == h.cuenta_id, Cuenta.usuario_id == usuario_id).first() if faltantes else None
        if cuenta is not None:
            absorbidas = _absorbidas_por_otro_canal(db, usuario_id, cuenta, faltantes)
            for it in faltantes:
                if id(it) not in absorbidas:
                    continue
                existente = absorbidas[id(it)]
                if existente is None:
                    it["estado"] = "borrado_antes"
                else:
                    if modelo is None:
                        modelo = ClasificadorUsuario(db, usuario_id)
                    _completar_con_extracto(db, existente, it, h.id, modelo, usuario_id, cuenta=cuenta,
                                            huella=_huella_linea(db, usuario_id, it))
                    it["estado"] = "completado"
                it["duplicado_evitado"] = True
                resueltas += 1
                cambio = True
        if cambio:
            h.review_json = json.dumps(review, default=str)
        sincronizar_contadores(h, review)
    db.commit()
    return resueltas


def _item(*, clave, extracto_id, historial_id, cuenta_id, cuenta, banco, periodo, mes, estado, conteo, origenes,
          copias=1, motivo="", clave_estado=None, reciente=None) -> dict:
    return {
        "id": clave,
        "extracto_id": extracto_id,
        "historial_id": historial_id,
        "cuenta_id": cuenta_id,
        "cuenta": cuenta,
        "banco": banco,
        "periodo": periodo,
        "mes": mes,
        "estado": estado,
        "pide_accion": estado in PIDEN_ACCION,
        "origenes": sorted(origenes),
        "copias": copias,  # cuántos correos/archivos eran este mismo extracto (se muestra uno solo)
        "motivo": motivo,
        "clave_estado": clave_estado,
        **conteo,
        "frase": frase(estado, conteo, mes=mes, cuenta=cuenta, banco=banco),
        "_reciente": reciente,
    }


_VACIO = {"leidas": 0, "ya_estaban": 0, "nuevas_agregadas": 0, "por_revisar": 0, "descartadas": 0,
          "anteriores": 0, "duplicadas_detectadas": 0, "dudosas": 0}


def lista_extractos(db: Session, usuario_id: str, inicio_pp=None) -> list[dict]:
    """Un renglón por EXTRACTO REAL (cuenta + mes), venga de un correo, de un archivo subido a mano o
    de los dos: el mismo PDF en dos correos, o subido a mano y también por Gmail, es UN extracto.
    Ordenado: primero lo que pide acción, luego lo más reciente."""
    from app import punto_partida
    from app.extractos_conciliados import ESTADO_YA_CONCILIADO, mes_del_extracto
    from app.extractos_gmail import banco_por_remitente
    from app.models import Cuenta, ExtractoCorreo, HistorialExtracto

    cuentas = {c.id: c for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).all()}
    historiales = {h.id: h for h in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == usuario_id).all()}
    correos = db.query(ExtractoCorreo).filter(
        ExtractoCorreo.usuario_id == usuario_id,
        ExtractoCorreo.estado.in_(("nuevo", "falta_clave", "procesado", "error", ESTADO_YA_CONCILIADO))).all()

    crudos: list[dict] = []
    usados = set()
    for e in correos:
        h = historiales.get(e.historial_id) if e.historial_id else None
        if h is not None:
            usados.add(h.id)
        mes = mes_del_extracto(e.periodo, e.recibido_en)
        cuenta_id = (h.cuenta_id if h is not None else e.cuenta_sugerida_id) or None
        cuenta = cuentas.get(cuenta_id)
        banco = e.banco or banco_por_remitente(e.remitente) or ""
        anterior = e.estado in ("nuevo", "falta_clave", "error") and punto_partida.extracto_es_anterior(
            e.periodo, e.recibido_en, inicio_pp)
        if e.estado == "falta_clave":
            estado, conteo = NECESITA_CLAVE, dict(_VACIO)
        elif e.estado == "error":
            estado, conteo = NO_SE_PUDO_LEER, dict(_VACIO)
        elif anterior:
            estado, conteo = ANTERIOR_AL_INICIO, dict(_VACIO)
        elif h is not None:
            conteo = conteo_de_historial(h)
            estado = estado_de_conteo(conteo, h.estado)
        elif e.estado in (ESTADO_YA_CONCILIADO, "procesado"):
            # Ya resuelto sin revisión guardada que contar (periodo conciliado por otro lado).
            conteo, estado = dict(_VACIO), AL_DIA
        else:  # nuevo, o «procesado» cuya revisión se borró: hay que volver a revisarlo
            conteo, estado = dict(_VACIO), POR_REVISAR
        crudos.append(dict(
            clave=f"c:{e.id}", extracto_id=e.id, historial_id=h.id if h is not None else None, cuenta_id=cuenta_id,
            cuenta=cuenta.nombre if cuenta else "", banco=banco, periodo=e.periodo or "", mes=mes, estado=estado,
            conteo=conteo, origen="correo", clave_estado=getattr(e, "clave_resultado", None),
            reciente=e.recibido_en or e.creado_en, sin_revisar=(e.estado == "nuevo"),
            sin_cuenta=cuenta_id is None, historial=h,
        ))
    # Subidas a mano (sin extracto de correo detrás).
    for h in historiales.values():
        if h.id in usados or h.estado not in ("conciliado", "pendiente_revision", "error"):
            continue
        cuenta = cuentas.get(h.cuenta_id)
        if cuenta is None:
            continue
        conteo = conteo_de_historial(h)
        estado = estado_de_conteo(conteo, h.estado)
        crudos.append(dict(
            clave=f"h:{h.id}", extracto_id=None, historial_id=h.id, cuenta_id=h.cuenta_id, cuenta=cuenta.nombre,
            banco=(h.banco_detectado or "").replace("archivo: ", ""), periodo="", mes=_mes_de_historial(h),
            estado=estado, conteo=conteo, origen="archivo", clave_estado=None, reciente=h.creado_en,
            sin_revisar=False, sin_cuenta=False, historial=h,
        ))

    # Un renglón por (cuenta, mes). Los de error solo cuentan si no hay un intento bueno después.
    grupos: dict[tuple, list[dict]] = {}
    sueltos: list[dict] = []
    for c in crudos:
        if c["cuenta_id"] and c["mes"]:
            grupos.setdefault((c["cuenta_id"], c["mes"]), []).append(c)
        else:
            sueltos.append(c)

    def prioridad(c):
        # Cuál representa al grupo: el que ya tiene una revisión real; entre ellos, el más reciente.
        con_revision = c["historial"] is not None and c["estado"] != NO_SE_PUDO_LEER
        return (con_revision, c["estado"] == POR_REVISAR, c["estado"] != NECESITA_CLAVE, c["reciente"] or datetime.min)

    salida = []
    for lista in list(grupos.values()) + [[s] for s in sueltos]:
        mejor = max(lista, key=prioridad)
        copias = len(lista)
        origenes = {c["origen"] for c in lista}
        estado = mejor["estado"]
        # Si el grupo ya tiene una revisión buena, las copias sin abrir NO son pendientes: es el mismo extracto.
        if mejor["historial"] is None and len(lista) > 1:
            estados = [c["estado"] for c in lista]
            # Una copia ya resuelta del mismo extracto manda sobre las que nadie ha abierto.
            estado = AL_DIA if AL_DIA in estados else max(estados, key=lambda s: (s in PIDEN_ACCION, s))
        salida.append(_item(
            clave=mejor["clave"], extracto_id=mejor["extracto_id"], historial_id=mejor["historial_id"],
            cuenta_id=mejor["cuenta_id"], cuenta=mejor["cuenta"], banco=mejor["banco"], periodo=mejor["periodo"],
            mes=mejor["mes"], estado=estado, conteo=mejor["conteo"], origenes=origenes, copias=copias,
            motivo="elige_cuenta" if mejor["sin_cuenta"] and estado == POR_REVISAR else "",
            clave_estado=mejor["clave_estado"], reciente=mejor["reciente"]))
    salida.sort(key=lambda i: (not i["pide_accion"], -(i["_reciente"].timestamp() if i["_reciente"] else 0)))
    for i in salida:
        i.pop("_reciente", None)
    return salida


def resumen_por_celda(extractos: list[dict]) -> dict[tuple[str, str], dict]:
    """{(cuenta_id, mes): totales} para el detalle de cada celda de la cobertura."""
    celdas: dict[tuple[str, str], dict] = {}
    for x in extractos:
        if not x["cuenta_id"] or not x["mes"]:
            continue
        c = celdas.setdefault((x["cuenta_id"], x["mes"]), {
            "leidas": 0, "ya_estaban": 0, "nuevas_agregadas": 0, "por_revisar": 0, "estados": []})
        for k in ("leidas", "ya_estaban", "nuevas_agregadas", "por_revisar"):
            c[k] += x[k]
        c["estados"].append(x["estado"])
    return celdas
