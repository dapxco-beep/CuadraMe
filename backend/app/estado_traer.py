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

from app import extractos_error
from app import extractos_vista as ev

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
         "anteriores": 0, "duplicadas_detectadas": 0, "dudosas": 0, "lectura_dudosa": 0}
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
            if i.get("lectura_dudosa"):
                c["lectura_dudosa"] += 1  # trae varios montos: no se importa hasta que la persona elige
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
            "duplicadas_detectadas": int(h.exactos or 0), "dudosas": 0, "lectura_dudosa": 0}


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
          copias=1, motivo="", clave_estado=None, reciente=None, extra=None) -> dict:
    d = {
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
    d.update(extra or {})
    return d


_VACIO = {"leidas": 0, "ya_estaban": 0, "nuevas_agregadas": 0, "por_revisar": 0, "descartadas": 0,
          "anteriores": 0, "duplicadas_detectadas": 0, "dudosas": 0, "lectura_dudosa": 0}


def _banco_de(e) -> str:
    from app.extractos_gmail import banco_por_remitente

    return e.banco or banco_por_remitente(e.remitente) or ""


def mes_de_correo(e, h=None) -> dict:
    """Mes deducido de un extracto de Gmail (ver app/extractos_vista.py: periodo, asunto, archivo, líneas,
    recepción). `h` = su historial, si ya se leyó. Lo usan la lista y la cobertura: así dicen el mismo mes."""
    return ev.deducir_periodo(
        periodo=e.periodo or "", asunto=e.asunto or "", archivo=e.archivo or "", recibido_en=e.recibido_en,
        mes_lineas=_mes_de_historial(h) if h is not None else None, banco=_banco_de(e), remitente=e.remitente or "")


def persistir_periodos(db: Session, usuario_id: str) -> int:
    """Guarda en ExtractoCorreo.periodo el mes deducido con fuentes seguras (asunto, nombre del archivo, líneas
    leídas) cuando el extracto no traía periodo. Así todo el sistema (cobertura, conciliados, punto de partida)
    ve el mismo mes. La fecha de recepción NO se guarda (es solo una suposición). Idempotente."""
    from app.models import ExtractoCorreo, HistorialExtracto

    filas = db.query(ExtractoCorreo).filter(
        ExtractoCorreo.usuario_id == usuario_id,
        ExtractoCorreo.estado.in_(("nuevo", "falta_clave", "procesado", "error", "ya_conciliado")),
        (ExtractoCorreo.periodo.is_(None)) | (ExtractoCorreo.periodo == "")).all()
    if not filas:
        return 0
    hist = {h.id: h for h in db.query(HistorialExtracto).filter(
        HistorialExtracto.usuario_id == usuario_id,
        HistorialExtracto.id.in_([f.historial_id for f in filas if f.historial_id] or [""])).all()}
    n = 0
    for e in filas:
        ded = mes_de_correo(e, hist.get(e.historial_id))
        if ded["mes"] and ded["fuente"] in ev.FUENTES_SEGURAS:
            e.periodo = ev.periodo_texto(ded["mes"])
            n += 1
    if n:
        db.commit()
    return n


def _norm(t: str) -> str:
    return " ".join((t or "").lower().split())


def lista_extractos(db: Session, usuario_id: str, inicio_pp=None) -> list[dict]:
    """Un renglón por EXTRACTO REAL (cuenta + mes), venga de un correo, de un archivo subido a mano o
    de los dos: el mismo PDF en dos correos, o subido a mano y también por Gmail, es UN extracto.
    Ordenado: primero lo que pide acción, luego lo más reciente. Cada renglón trae además lo que la lista
    «Todos los extractos» necesita: tipo, título, mes (con su fuente), estado de la lista, frase de resultado,
    motivo si no se pudo leer y acciones."""
    from app import punto_partida
    from app.reasignar_extracto import sugerir_cuenta_credito
    from app.extractos_conciliados import ESTADO_YA_CONCILIADO
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
        ded = mes_de_correo(e, h)
        mes = ded["mes"]
        cuenta_id = (h.cuenta_id if h is not None else e.cuenta_sugerida_id) or None
        cuenta = cuentas.get(cuenta_id)
        banco = _banco_de(e)
        periodo_ef = e.periodo or (ev.periodo_texto(mes) if mes and ded["fuente"] in ev.FUENTES_SEGURAS else "")
        anterior = e.estado in ("nuevo", "falta_clave", "error") and punto_partida.extracto_es_anterior(
            periodo_ef, e.recibido_en, inicio_pp)
        motivo_err = e.motivo_error or (h.motivo_error if h is not None else None)
        if e.estado == "falta_clave":
            estado, conteo = NECESITA_CLAVE, dict(_VACIO)
        elif e.estado == "error":
            estado, conteo = NO_SE_PUDO_LEER, dict(_VACIO)
        elif anterior:
            estado, conteo = ANTERIOR_AL_INICIO, dict(_VACIO)
        elif h is not None:
            conteo = conteo_de_historial(h)
            estado = estado_de_conteo(conteo, h.estado)
        elif e.estado == "nuevo" and e.motivo_error:
            # Se intentó leer y no se pudo (el estado «nuevo» sigue para poder reintentar).
            estado, conteo = NO_SE_PUDO_LEER, dict(_VACIO)
        elif e.estado in (ESTADO_YA_CONCILIADO, "procesado"):
            # Ya resuelto sin revisión guardada que contar (periodo conciliado por otro lado).
            conteo, estado = dict(_VACIO), AL_DIA
        else:  # nuevo, o «procesado» cuya revisión se borró: hay que volver a revisarlo
            conteo, estado = dict(_VACIO), POR_REVISAR
        corte = (h.fecha_corte if h is not None and h.fecha_corte else "") or ev.corte_del_periodo(e.periodo or "")
        crudos.append(dict(
            clave=f"c:{e.id}", extracto_id=e.id, historial_id=h.id if h is not None else None, cuenta_id=cuenta_id,
            cuenta=cuenta.nombre if cuenta else "", banco=banco, periodo=e.periodo or "", mes=mes, estado=estado,
            conteo=conteo, origen="correo", clave_estado=getattr(e, "clave_resultado", None),
            reciente=e.recibido_en or e.creado_en, sin_revisar=(e.estado == "nuevo"),
            sin_cuenta=cuenta_id is None, historial=h, mes_fuente=ded["fuente"], mes_deducido=ded["deducido"],
            tipo=ev.tipo_de_extracto(cuenta.tipo if cuenta else None, e.asunto or "", e.archivo or ""),
            # Lo que DICE el correo (tarjeta o cuenta): si no coincide con la cuenta a la que quedó, el título
            # dice la verdad del correo, no la de la cuenta equivocada.
            tipo_texto=ev.tipo_de_extracto(None, e.asunto or "", e.archivo or ""),
            corte=corte, motivo_error=motivo_err, asunto=e.asunto or "", archivo=e.archivo or "",
            recibido_en=e.recibido_en or e.creado_en,
            sugerencia_cuenta=sugerir_cuenta_credito(h, cuenta, list(cuentas.values()), f"{e.asunto or ''} {e.archivo or ''}"),
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
        mes_h = _mes_de_historial(h)
        crudos.append(dict(
            clave=f"h:{h.id}", extracto_id=None, historial_id=h.id, cuenta_id=h.cuenta_id, cuenta=cuenta.nombre,
            banco=(h.banco_detectado or "").replace("archivo: ", ""), periodo="", mes=mes_h,
            estado=estado, conteo=conteo, origen="archivo", clave_estado=None, reciente=h.creado_en,
            sin_revisar=False, sin_cuenta=False, historial=h, mes_fuente=ev.FUENTE_LINEAS if mes_h else None,
            mes_deducido=not mes_h, tipo=ev.tipo_de_extracto(cuenta.tipo), tipo_texto="", corte=h.fecha_corte or "",
            motivo_error=h.motivo_error, asunto="", archivo="", recibido_en=h.creado_en,
            historial_error=(h.estado == "error"),
            reintentable=(h.estado == "error" and extractos_error.reintentable(db, h, correos)),
            sugerencia_cuenta=sugerir_cuenta_credito(h, cuenta, list(cuentas.values()), h.banco_detectado or ""),
        ))

    # Un renglón por (cuenta, mes). Los de error solo cuentan si no hay un intento bueno después.
    def clave_grupo(c):
        if c["mes"] and c["cuenta_id"]:
            # El correo dice claramente que es de OTRO producto que la cuenta a la que quedó (la tarjeta Nu
            # asignada a la cuenta Nu): es otro extracto del mismo mes, no una copia.
            texto = ev.tipo_de_extracto(None, c.get("asunto", ""), c.get("archivo", "")) if c["origen"] == "correo" else ""
            ajeno = texto if texto and c["tipo"] and texto != c["tipo"] else ""
            return ("c", c["cuenta_id"], c["mes"], ajeno)
        if c["mes"] and c["banco"]:
            return ("b", _norm(c["banco"]), c["tipo"], c["mes"])
        if c["estado"] == NO_SE_PUDO_LEER and c["origen"] == "archivo" and c["cuenta_id"]:
            # Varios intentos fallidos sin mes: se juntan por cuenta y por familia de motivo: los que esperan la
            # clave («10 extractos de Nu esperan la clave») y los demás («5 no se pudieron leer»).
            return ("e", c["cuenta_id"], c["motivo_error"] in extractos_error.MOTIVOS_CLAVE)
        return None

    grupos: dict[tuple, list[dict]] = {}
    sueltos: list[dict] = []
    for c in crudos:
        k = clave_grupo(c)
        if k:
            grupos.setdefault(k, []).append(c)
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
        motivo = "elige_cuenta" if mejor["sin_cuenta"] and estado == POR_REVISAR else ""
        vista = ev.estado_de_vista(estado, mejor["historial_id"] is not None)
        motivo_err = None
        if estado == NO_SE_PUDO_LEER:
            motivo_err = mejor["motivo_error"] or next((c["motivo_error"] for c in lista if c["motivo_error"]), None)
        if copias > 1:
            copias_texto = f"x{copias} intentos" if origenes == {"archivo"} else (
                f"x{copias} correos" if origenes == {"correo"} else f"x{copias} copias")
        else:
            copias_texto = ""
        nombre_banco = ev.banco_para_titulo(mejor["banco"], mejor["cuenta"])
        tipo_titulo = mejor["tipo_texto"] if mejor["tipo_texto"] and mejor["tipo"] and mejor["tipo_texto"] != mejor["tipo"] else mejor["tipo"]
        motivo_codigo = (motivo_err or extractos_error.MOTIVO_POR_DEFECTO) if estado == NO_SE_PUDO_LEER else None
        if motivo_codigo:
            distintos = {c["motivo_error"] or extractos_error.MOTIVO_POR_DEFECTO for c in lista if c["estado"] == NO_SE_PUDO_LEER}
            if len(distintos) > 1:  # intentos con motivos distintos: si todos piden clave, es la clave; si no, «no se pudieron leer»
                motivo_codigo = "clave_faltante" if distintos <= set(extractos_error.MOTIVOS_CLAVE) else extractos_error.MOTIVO_POR_DEFECTO
        if estado == NO_SE_PUDO_LEER and not mejor["mes"]:
            # Sin mes no hay «Mes por confirmar»: la fila dice cuántos hay, de qué banco y qué les pasa.
            titulo = ev.titulo_grupo_error(motivo_codigo, copias, nombre_banco)
        else:
            titulo = ev.titulo_extracto(banco=nombre_banco, tipo=tipo_titulo, mes=mejor["mes"], corte=mejor["corte"])
        ejemplos = [{"nombre": c["archivo"] or c["asunto"] or "Subido a mano", "fecha": c["recibido_en"].isoformat() if c["recibido_en"] else None}
                    for c in sorted(lista, key=lambda c: c["recibido_en"] or datetime.min, reverse=True)[:3]]
        extra = {
            "tipo": mejor["tipo"], "mes_fuente": mejor["mes_fuente"], "mes_deducido": bool(mejor["mes_deducido"]),
            "mes_por_confirmar": not mejor["mes"], "mes_etiqueta": ev.etiqueta_mes(mejor["mes"]),
            "titulo": titulo,
            # De dónde salió y a qué cuenta quedó (nada sin nombre ni origen).
            "banco_nombre": nombre_banco, "cuenta_asignada": mejor["cuenta"], "tipo_titulo": tipo_titulo,
            "origen_texto": ev.origen_texto(mejor["origen"], asunto=mejor["asunto"], archivo=mejor["archivo"],
                                            fecha_iso=mejor["recibido_en"].isoformat() if mejor["recibido_en"] else None),
            "ejemplos": ejemplos, "motivo_codigo": motivo_codigo,
            "motivo_corto": ev.motivo_corto(motivo_codigo) if motivo_codigo else None,
            "banco_sin_identificar": (mejor["banco"] or "").lower() in ev.BANCOS_SIN_NOMBRE,
            "estado_vista": vista, "estado_etiqueta": ev.ETIQUETA_ESTADO[vista],
            "estado_corto": ev.estado_corto(vista, mejor["conteo"], clave_estado=mejor["clave_estado"]),
            "resultado": ev.frase_resultado(vista, mejor["conteo"], clave_estado=mejor["clave_estado"],
                                            motivo=motivo_err, copias=copias),
            "motivo_error": motivo_err,
            # Todas las filas de error de este renglón (varios intentos del mismo mes): «Quitar de la lista» las limpia.
            "historiales_error": [c["historial_id"] for c in lista if c.get("historial_error") and c["historial_id"]],
            "copias_texto": copias_texto, "asunto": mejor["asunto"], "archivo": mejor["archivo"],
            "recibido_en": mejor["recibido_en"].isoformat() if mejor["recibido_en"] else None,
            "puede_fijar_mes": mejor["extracto_id"] is not None,
            "puede_cambiar_cuenta": bool(mejor["historial_id"] and mejor["cuenta_id"] and mejor["historial"] is not None
                                         and mejor["historial"].estado in ("conciliado", "pendiente_revision")),
            "sugerencia_cuenta": mejor.get("sugerencia_cuenta"),
            "acciones": _acciones(vista, mejor),
        }
        salida.append(_item(
            clave=mejor["clave"], extracto_id=mejor["extracto_id"], historial_id=mejor["historial_id"],
            cuenta_id=mejor["cuenta_id"], cuenta=mejor["cuenta"], banco=mejor["banco"], periodo=mejor["periodo"],
            mes=mejor["mes"], estado=estado, conteo=mejor["conteo"], origenes=origenes, copias=copias,
            motivo=motivo, clave_estado=mejor["clave_estado"], reciente=mejor["reciente"], extra=extra))
    salida.sort(key=lambda i: (not i["pide_accion"], -(i["_reciente"].timestamp() if i["_reciente"] else 0)))
    for i in salida:
        i.pop("_reciente", None)
    return salida


def _acciones(vista: str, c: dict) -> list[str]:
    """Qué botones lleva la fila (la pantalla los pinta; aquí se decide y se prueba)."""
    if vista in (ev.SIN_PROCESAR, ev.POR_REVISAR):
        # «Releer»: solo si ya hay una lectura guardada que viene de un correo (los subidos a mano no se pueden releer).
        return ["revisar"] + (["releer"] if vista == ev.POR_REVISAR and c["extracto_id"] and c["historial_id"] else [])
    if vista == ev.NECESITA_CLAVE:
        return ["poner_clave", "probar_clave"]
    if vista == ev.NO_SE_PUDO_LEER:
        # Un error por clave se arregla con la clave: un solo botón «Poner la clave» para todo el grupo.
        clave = c.get("motivo_error") in extractos_error.MOTIVOS_CLAVE
        poner = ["poner_clave"] if clave else []
        banco = [] if clave else ["mi_banco_no_esta"]
        if c["extracto_id"]:
            return poner + ["intentar_de_nuevo"] + banco
        if c.get("historial_error"):
            # Subido a mano o sin correo: «Reintentar» solo si hay un correo del que volver a traer el PDF.
            return poner + (["reintentar"] if c.get("reintentable") else ["subir_de_nuevo"]) + ["quitar_de_la_lista"] + banco
        return poner + ["subir_de_nuevo"] + banco
    if vista == ev.REVISADO:
        return (["ver"] + (["revisar_de_nuevo"] if c["extracto_id"] and c["cuenta_id"] else [])
                + (["releer"] if c["extracto_id"] and c["historial_id"] else []))
    return []


def resumen_por_celda(extractos: list[dict]) -> dict[tuple[str, str], dict]:
    """{(cuenta_id, mes): totales} para el detalle de cada celda de la cobertura."""
    celdas: dict[tuple[str, str], dict] = {}
    for x in extractos:
        if not x["cuenta_id"] or not x["mes"]:
            continue
        c = celdas.setdefault((x["cuenta_id"], x["mes"]), {
            "leidas": 0, "ya_estaban": 0, "nuevas_agregadas": 0, "por_revisar": 0, "lectura_dudosa": 0, "estados": [], "lista": []})
        for k in ("leidas", "ya_estaban", "nuevas_agregadas", "por_revisar", "lectura_dudosa"):
            c[k] += x.get(k, 0)
        c["estados"].append(x["estado"])
        # Lo mismo que dice la lista (título, estado): la cobertura y «Todos los extractos» no se contradicen.
        c["lista"].append({"id": x["id"], "titulo": x["titulo"], "estado_vista": x["estado_vista"],
                           "estado_etiqueta": x["estado_etiqueta"], "motivo_corto": x.get("motivo_corto"),
                           "historial_id": x.get("historial_id"), "extracto_id": x.get("extracto_id"),
                           "acciones": x.get("acciones") or []})
    return celdas


def _orden_mes(mes: str | None) -> int:
    """Más reciente primero; sin mes al final."""
    if not mes:
        return 10 ** 9
    return -(int(mes[:4]) * 12 + int(mes[5:7]))


def vista_completa(db: Session, usuario_id: str, inicio_pp=None, lista: list[dict] | None = None) -> dict:
    """Todo lo que necesita «Todos los extractos»: filas (del más reciente al más antiguo), contadores por
    estado y los correos de extracto que no traían PDF. Aislado por usuario (todo sale de `usuario_id`)."""
    from app.models import ExtractoCorreo

    items = lista if lista is not None else lista_extractos(db, usuario_id, inicio_pp)
    items = sorted(items, key=lambda i: (_orden_mes(i["mes"]), ev.ESTADOS_VISTA.index(i["estado_vista"]), i["titulo"]))
    cont = {k: 0 for k in ev.ESTADOS_VISTA}
    for i in items:
        cont[i["estado_vista"]] += 1
    ign = (db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == usuario_id, ExtractoCorreo.estado == "ignorado")
           .order_by(ExtractoCorreo.creado_en.desc()).limit(100).all())
    sin_adjunto = [{
        "id": e.id, "asunto": e.asunto or "", "banco": _banco_de(e),
        "recibido_en": (e.recibido_en or e.creado_en).isoformat() if (e.recibido_en or e.creado_en) else None,
        "razon": ev.RAZON_SIN_ADJUNTO,
    } for e in ign]
    return {
        "items": items,
        "contadores": cont,
        "total": len(items),
        "resumen": ev.frase_contadores(cont),
        "sin_adjunto": sin_adjunto,
        "razon_sin_adjunto": ev.RAZON_SIN_ADJUNTO,
    }


def origen_de_historial(db: Session, usuario_id: str, h) -> dict:
    """De dónde salió un extracto ya procesado y a qué cuenta quedó, para el encabezado de su revisión
    («Tarjeta Nu · corte 15 oct 2026» / «Correo «…» · archivo X» / «En la cuenta Nu Colombia»). Nada sin origen."""
    from app.models import Cuenta, ExtractoCorreo

    e = (db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == usuario_id, ExtractoCorreo.historial_id == h.id)
         .order_by(ExtractoCorreo.recibido_en.desc()).first())
    cuenta = db.query(Cuenta).filter(Cuenta.id == h.cuenta_id, Cuenta.usuario_id == usuario_id).first()
    mes = mes_de_correo(e, h)["mes"] if e is not None else _mes_de_historial(h)
    tipo = ev.tipo_de_extracto(cuenta.tipo if cuenta else None)
    tipo_texto = ev.tipo_de_extracto(None, e.asunto or "", e.archivo or "") if e is not None else ""
    tipo_titulo = tipo_texto if tipo_texto and tipo and tipo_texto != tipo else tipo
    banco = ev.banco_para_titulo((_banco_de(e) if e is not None else (h.banco_detectado or "").replace("archivo: ", "")), cuenta.nombre if cuenta else "")
    corte = h.fecha_corte or (ev.corte_del_periodo(e.periodo or "") if e is not None else "")
    fecha = (e.recibido_en or e.creado_en) if e is not None else h.creado_en
    return {
        "titulo": ev.titulo_extracto(banco=banco, tipo=tipo_titulo, mes=mes, corte=corte or ""),
        "origen_texto": ev.origen_texto("correo" if e is not None else "archivo", asunto=(e.asunto if e is not None else ""),
                                        archivo=(e.archivo if e is not None else ""), fecha_iso=fecha.isoformat() if fecha else None),
        "asunto": e.asunto if e is not None else "", "archivo": e.archivo if e is not None else "",
        "cuenta_id": h.cuenta_id, "cuenta_nombre": cuenta.nombre if cuenta else "", "mes_etiqueta": ev.etiqueta_mes(mes),
    }
