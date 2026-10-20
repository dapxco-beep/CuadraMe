"""Fechas de los extractos: que cada extracto caiga en el MES correcto y que las fechas dudosas se vean.

Problema que resuelve: el código genérico de procesar extractos tomaba como «corte» la última fecha que veía en el
texto. En la tarjeta Nu eso es la FECHA LÍMITE DE PAGO (días después del corte), y el extracto caía en el mes
equivocado en «Tus cuentas, mes a mes», en el cierre de mes y en el cuadre. El lector de tarjeta Nu
(`extractos_tarjeta_nu.leer_resumen`) sí lee bien el resumen: periodo facturado, corte y límite de pago.

Reglas (sin columnas nuevas; todo cabe en `fecha_corte`, `periodo_inicio` y `lectura_json`):
  · Tarjeta con resumen leído: `periodo_inicio` = inicio del periodo facturado, `fecha_corte` = corte (JAMÁS el
    límite de pago) y `lectura_json["periodo_fin"]` = fin del periodo. Esa fecha es «leída del PDF».
  · El «mes» de un extracto de TARJETA, para las vistas por mes, es el mes de la FECHA DE CORTE (corte 15-oct =
    octubre 2026). Los extractos de ahorros siguen por mes calendario, sin cambios.
  · Respaldo: si no hay resumen leído ni PDF, el corte se estima con la fecha del correo (Nu manda el extracto el
    día del corte). Queda marcado en `lectura_json["fechas_estimadas"]` y NUNCA pisa una fecha leída del PDF.
  · Duplicado de subida (misma cuenta, mismo periodo y mismos saldos): el segundo se marca en
    `lectura_json["duplicado_de"]` y las vistas lo ocultan. No se toca ningún movimiento ni saldo.
Todo es idempotente y reversible (el autoarreglo guarda `fecha_corte`, `periodo_inicio` y `lectura_json` antes/después)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.cuadre_extracto import TOLERANCIA, a_fecha
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto
from app.utiles import ahora_co

CLAVE_ESTIMADAS = "fechas_estimadas"
CLAVE_FIN = "periodo_fin"
CLAVE_DUPLICADO = "duplicado_de"
DIAS_PERIODO_MAX = 45  # un periodo de extracto más largo que esto es raro


# ── lectura_json (JSON libre: se conserva todo lo que ya traía) ───────────────────────────────────
def _lectura(h: HistorialExtracto) -> dict:
    return dict(h.lectura or {})


def _guardar_lectura(h: HistorialExtracto, d: dict) -> None:
    h.lectura_json = json.dumps(d, default=str, ensure_ascii=False)


def _resumen(h: HistorialExtracto) -> dict | None:
    r = (h.lectura or {}).get("resumen_tarjeta")
    return r if isinstance(r, dict) else None


def es_estimada(h: HistorialExtracto) -> bool:
    return bool((h.lectura or {}).get(CLAVE_ESTIMADAS))


def duplicado_de(h: HistorialExtracto) -> str | None:
    return (h.lectura or {}).get(CLAVE_DUPLICADO) or None


def es_duplicado(h: HistorialExtracto) -> bool:
    return duplicado_de(h) is not None


# ── 1) Fechas que dice el resumen de la tarjeta ───────────────────────────────────────────────────
def fechas_del_resumen(resumen: dict | None) -> dict | None:
    """{periodo_inicio, fecha_corte, periodo_fin} (ISO) de un `resumen_tarjeta`, o None si no trae corte válido.
    El corte es el corte; el límite de pago NO se usa nunca como fecha del extracto."""
    if not isinstance(resumen, dict):
        return None
    corte = a_fecha(resumen.get("corte"))
    if corte is None:
        return None
    per = resumen.get("periodo") or {}
    ini, fin = a_fecha(per.get("inicio")), a_fecha(per.get("fin"))
    if ini is not None and ini > corte:
        ini = None  # incoherente: mejor sin inicio que un inicio inventado
    return {"periodo_inicio": ini.isoformat() if ini else None, "fecha_corte": corte.isoformat(),
            "periodo_fin": fin.isoformat() if fin else None}


def aplicar_resumen(h: HistorialExtracto, resumen: dict | None) -> bool:
    """Fija las fechas del extracto con las del resumen leído del PDF. Sin commit. True si cambió algo.
    No toca extractos con saldos escritos a mano ni importa nada."""
    f = fechas_del_resumen(resumen)
    if f is None or h.saldos_origen == "manual":
        return False
    cambio = False
    if h.fecha_corte != f["fecha_corte"]:
        h.fecha_corte, cambio = f["fecha_corte"], True
    if f["periodo_inicio"] and h.periodo_inicio != f["periodo_inicio"]:
        h.periodo_inicio, cambio = f["periodo_inicio"], True
    lect = _lectura(h)
    if lect.get(CLAVE_ESTIMADAS) or (f["periodo_fin"] and lect.get(CLAVE_FIN) != f["periodo_fin"]):
        lect.pop(CLAVE_ESTIMADAS, None)
        if f["periodo_fin"]:
            lect[CLAVE_FIN] = f["periodo_fin"]
        _guardar_lectura(h, lect)
        cambio = True
    return cambio


# ── 2) Respaldo: el corte según la fecha del correo (marcado como estimado) ──────────────────────
def corte_estimado_por_correo(recibido_en: datetime | None) -> date | None:
    """Nu manda el extracto el día del corte: esa fecha (hora de Colombia) es el mejor respaldo."""
    if recibido_en is None:
        return None
    return (recibido_en - timedelta(hours=5)).date()


def aplicar_estimada(h: HistorialExtracto, recibido_en: datetime | None) -> bool:
    """Solo si el extracto NO tiene fecha de corte: la estima con la fecha del correo y lo marca. Sin commit.
    Jamás pisa una fecha leída del PDF (ni una escrita a mano)."""
    if h.fecha_corte or h.saldos_origen == "manual":
        return False
    d = corte_estimado_por_correo(recibido_en)
    if d is None:
        return False
    h.fecha_corte = d.isoformat()
    lect = _lectura(h)
    lect[CLAVE_ESTIMADAS] = True
    _guardar_lectura(h, lect)
    return True


# ── 3) El mes de un extracto ─────────────────────────────────────────────────────────────────────
def mes_de_corte(h: HistorialExtracto) -> str | None:
    """'AAAA-MM' del mes de la FECHA DE CORTE, o None si no hay."""
    d = a_fecha(h.fecha_corte)
    return f"{d.year:04d}-{d.month:02d}" if d else None


def es_de_tarjeta_h(h: HistorialExtracto, cuenta: Cuenta | None) -> bool:
    return (cuenta is not None and (cuenta.tipo or "").lower() == "credito") or _resumen(h) is not None


def mes_de_extracto(h: HistorialExtracto, cuenta: Cuenta | None) -> str | None:
    """Mes del extracto para las vistas por mes SOLO si es de tarjeta y tiene corte: el mes del corte. Si no, None
    (la vista usa su regla de siempre: mes calendario)."""
    return mes_de_corte(h) if es_de_tarjeta_h(h, cuenta) else None


def detalle_tarjeta(h: HistorialExtracto) -> dict | None:
    """Para mostrar «Corte 15 oct · Pago hasta 4 nov»: {corte, limite_pago, periodo_fin, estimado} (ISO). Solo tarjetas
    con resumen leído, o con corte estimado (entonces sin límite de pago). None si no hay nada que mostrar."""
    r = _resumen(h)
    if r is not None:
        f = fechas_del_resumen(r) or {}
        corte = f.get("fecha_corte") or h.fecha_corte
        if not corte:
            return None
        return {"corte": corte, "limite_pago": (a_fecha(r.get("limite_pago")).isoformat() if a_fecha(r.get("limite_pago")) else None),
                "periodo_fin": f.get("periodo_fin"), "estimado": False}
    if es_estimada(h) and h.fecha_corte:
        return {"corte": h.fecha_corte, "limite_pago": None, "periodo_fin": None, "estimado": True}
    return None


# ── 4) Rellenar lo ya guardado (sin Gmail) ───────────────────────────────────────────────────────
def _correo(db: Session, h: HistorialExtracto) -> ExtractoCorreo | None:
    return (db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == h.usuario_id, ExtractoCorreo.historial_id == h.id)
            .order_by(ExtractoCorreo.recibido_en.desc()).first())


def _fechas_de_lineas(h: HistorialExtracto) -> tuple[date, date] | None:
    """(primera, última) fecha de las líneas leídas del extracto (las que no son «sobrante»), si las hay."""
    try:
        review = json.loads(h.review_json or "[]")
    except ValueError:
        return None
    fechas = [d for d in (a_fecha(i.get("fecha")) for i in review if isinstance(i, dict) and i.get("estado") != "sobrante") if d]
    return (min(fechas), max(fechas)) if fechas else None


def aplicar_desde_lineas(h: HistorialExtracto) -> bool:
    """Respaldo para extractos SIN resumen (ahorros u otros bancos): rellena SOLO lo que falta con las fechas de las
    líneas leídas y lo marca como estimado. Nunca pisa una fecha que ya está. Sin commit."""
    if h.saldos_origen == "manual" or (h.fecha_corte and h.periodo_inicio):
        return False
    rango = _fechas_de_lineas(h)
    if rango is None:
        return False
    cambio = False
    if not h.periodo_inicio:
        h.periodo_inicio, cambio = rango[0].isoformat(), True
    if not h.fecha_corte:
        h.fecha_corte, cambio = rango[1].isoformat(), True
    if cambio:
        lect = _lectura(h)
        lect[CLAVE_ESTIMADAS] = True
        _guardar_lectura(h, lect)
    return cambio


def completar_fechas(db: Session, usuario_id: str, excluir: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Repara las fechas de los extractos del usuario con lo que YA se guardó (sin descargar nada). Sin commit.
      · tarjeta con `resumen_tarjeta`: las fechas pasan a ser las del resumen (corrige corte vacío o equivocado);
      · tarjeta sin resumen y sin corte: se estima con la fecha del correo (marcado como estimado);
      · cualquier extracto conciliado al que le falte corte o inicio: se completa con las líneas leídas (estimado).
    Una fecha leída del PDF nunca se pisa con una estimada. Devuelve los ids de historial que cambiaron."""
    cuentas = {c.id: c for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).all()}
    cambiados = []
    for h in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == usuario_id,
                                                HistorialExtracto.estado != "error").all():
        if h.id in excluir or es_duplicado(h):
            continue
        hecho = False
        tarjeta = es_de_tarjeta_h(h, cuentas.get(h.cuenta_id))
        if tarjeta:
            if _resumen(h) is not None:
                hecho = aplicar_resumen(h, _resumen(h))
            else:
                fila = _correo(db, h)
                hecho = aplicar_estimada(h, fila.recibido_en if fila is not None else None)
        # En una tarjeta basta el corte (el inicio lo deduce el cuadre); en otras cuentas se completa también el inicio.
        if not hecho and h.estado == "conciliado" and not (tarjeta and h.fecha_corte):
            hecho = aplicar_desde_lineas(h)
        if hecho:
            cambiados.append(h.id)
    return cambiados


# ── 5) Duplicados de subida ──────────────────────────────────────────────────────────────────────
def _igual(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) < TOLERANCIA


def _mismo_extracto(a: HistorialExtracto, b: HistorialExtracto) -> bool:
    return (a.cuenta_id == b.cuenta_id and bool(a.fecha_corte) and a.fecha_corte == b.fecha_corte
            and (a.periodo_inicio or None) == (b.periodo_inicio or None)
            and _igual(a.saldo_final_extracto, b.saldo_final_extracto)
            and (a.saldo_inicial_extracto is None and b.saldo_inicial_extracto is None
                 or _igual(a.saldo_inicial_extracto, b.saldo_inicial_extracto)))


def _conciliados(db: Session, usuario_id: str) -> list[HistorialExtracto]:
    return (db.query(HistorialExtracto)
            .filter(HistorialExtracto.usuario_id == usuario_id, HistorialExtracto.estado == "conciliado")
            .order_by(HistorialExtracto.creado_en, HistorialExtracto.id).all())


def duplicados_de_subida(db: Session, usuario_id: str) -> list[tuple[HistorialExtracto, HistorialExtracto]]:
    """[(el que se queda, el duplicado)]: conciliados de la MISMA cuenta con el mismo periodo y los mismos saldos.
    Se queda el que más movimientos importó; a igualdad, el más viejo."""
    vivos = [h for h in _conciliados(db, usuario_id) if not es_duplicado(h)]
    pares, ocultos = [], set()
    for i, a in enumerate(vivos):
        if a.id in ocultos:
            continue
        for b in vivos[i + 1:]:
            if b.id in ocultos or not _mismo_extracto(a, b):
                continue
            queda, sobra = (a, b) if (a.importados or 0) >= (b.importados or 0) else (b, a)
            pares.append((queda, sobra))
            ocultos.add(sobra.id)
    return pares


def marcar_duplicados(db: Session, usuario_id: str, excluir: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Marca los duplicados de subida (solo `lectura_json`; movimientos y saldos intactos). Sin commit. Ids marcados."""
    marcados = []
    for queda, sobra in duplicados_de_subida(db, usuario_id):
        if sobra.id in excluir:
            continue
        lect = _lectura(sobra)
        lect[CLAVE_DUPLICADO] = queda.id
        _guardar_lectura(sobra, lect)
        marcados.append(sobra.id)
    return marcados


# ── 6) Hallazgos de fechas dudosas ───────────────────────────────────────────────────────────────
def _periodo(h: HistorialExtracto) -> tuple[date, date] | None:
    corte, ini = a_fecha(h.fecha_corte), a_fecha(h.periodo_inicio)
    return (ini, corte) if corte and ini and ini <= corte else None


def revisar_fechas(db: Session, usuario_id: str, hoy: date | None = None) -> dict:
    """Qué extractos conciliados tienen fechas dudosas, por causa. Solo lectura. Cada lista son ids de historial.
      sin_fechas   (a) conciliado sin fecha de corte o sin inicio de periodo            -> se repara solo
      duplicados   (d) misma cuenta, mismo periodo y mismos saldos que otro               -> se marca solo
      futuras      (b) corte posterior a mañana, o corte anterior al inicio del periodo   -> decide la persona
      traslapados  (c) el periodo se cruza con el de otro extracto de la misma cuenta     -> decide la persona"""
    hoy = hoy or ahora_co().date()
    out: dict[str, list[str]] = {"sin_fechas": [], "duplicados": [], "futuras": [], "traslapados": []}
    todos = _conciliados(db, usuario_id)
    cuentas = {c.id: c for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).all()}
    vivos = [h for h in todos if not es_duplicado(h)]
    for queda, sobra in duplicados_de_subida(db, usuario_id):
        out["duplicados"].append(sobra.id)
    dups = set(out["duplicados"])
    for h in vivos:
        if h.id in dups:
            continue
        corte, ini = a_fecha(h.fecha_corte), a_fecha(h.periodo_inicio)
        if corte is None or (ini is None and not es_de_tarjeta_h(h, cuentas.get(h.cuenta_id))):
            out["sin_fechas"].append(h.id)  # (en una tarjeta basta el corte)
            continue
        if corte > hoy + timedelta(days=1) or (ini is not None and ini > corte):
            out["futuras"].append(h.id)
    por_cuenta: dict[str, list[HistorialExtracto]] = {}
    for h in vivos:
        if h.id not in dups and _periodo(h) and h.id not in out["futuras"]:
            por_cuenta.setdefault(h.cuenta_id, []).append(h)
    for lista in por_cuenta.values():
        lista.sort(key=lambda x: _periodo(x))
        for a, b in zip(lista, lista[1:]):
            (_, fa), (ib, _) = _periodo(a), _periodo(b)
            if ib <= fa:  # el siguiente empieza antes de que termine el anterior
                for x in (a, b):
                    if x.id not in out["traslapados"]:
                        out["traslapados"].append(x.id)
    return out


def reparar(db: Session, usuario_id: str, excluir: set[str] | frozenset[str] = frozenset()) -> dict:
    """Repara lo que se puede arreglar solo: (a) fechas faltantes o equivocadas de tarjetas y (d) duplicados de subida.
    Sin commit. Devuelve {fechas: [ids], duplicados: [ids]}."""
    return {"fechas": completar_fechas(db, usuario_id, excluir), "duplicados": marcar_duplicados(db, usuario_id, excluir)}
