"""La tarjeta de crédito es DEUDA, no «saldo».

Decisión del dueño: el saldo de una cuenta de crédito es siempre ≤ 0 y vale «− lo que debes». Una compra o cargo es un
`expense` (baja el saldo = sube la deuda); un pago es un `income` de traslado propio (sube el saldo = baja la deuda) y
JAMÁS cuenta como ingreso (regla única de contabilidad.py: no se toca aquí).

Qué hay en este módulo (puro salvo lecturas y lo que dice cada función):
  1) ANCLAS por extracto (`anclar_cuenta`): de `lectura_json.resumen_tarjeta` de Nu sale lo que se DEBÍA al corte.
        saldo_final_extracto   = − usado            (usado = cupo − disponible = deuda total al corte; origen «extracto»)
        sin «usado» leído      = − (deuda a pagar + deuda restante + cuota de manejo + cargos por conversión + intereses),
                                 marcado «estimado» (relación observada en extractos sin abonos grandes)
        saldo_inicial_extracto = saldo final del extracto anterior (la cadena cuadra exacto); el del PRIMER extracto se
                                 deriva con sus líneas (final − neto de las líneas) y solo si la lectura está completa.
  2) CUADRE por extracto (`detalle_cuadre`): «Debía al inicio · Compras y cargos · Intereses · Pagos · Debo al corte
        (calculado) · Según tu extracto ✓/✕ por $D». Las compras en cuotas valen su VALOR COMPLETO el día de la compra.
  3) DEUDA INICIAL (`objetivo_deuda_inicial`): con cuánto empezó la tarjeta, derivado del extracto más antiguo.
        A = (− usado del extracto más antiguo) − Σ movimientos de la cuenta con fecha ≤ su corte (sin el propio ajuste).
     Se aplica con la misma maquinaria de `saldo_inicial_auto.recalcular` (movimiento neutro, recalculable, deshacible).
  4) VISTA EN VIVO (`vista`): deuda actual = deuda al último corte + compras y cargos desde el corte − pagos desde el
     corte; cupo disponible = cupo del último extracto − esa deuda.

Los números de los textos y de los tests son inventados; nada se manda a ningún sitio.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app import cuadre_extracto as cx
from app import fechas_extracto as fe
from app.contabilidad import FUENTE_AJUSTE, delta_saldo
from app.models import Cuenta, HistorialExtracto

TOL = cx.TOLERANCIA
ORIGEN_EXTRACTO = "extracto"
ORIGEN_ESTIMADO = "estimado"
DESC_INTERESES = "Intereses de tu tarjeta"
DESC_DEUDA_INICIAL = "Deuda inicial"
ESTADOS_QUE_FALTAN = ("faltante", "dudoso")
ESTADOS_LINEA_SUMA = ("importado", "exacto", "aproximado", "completado", "faltante", "dudoso", "borrado_antes", "anterior")


def pesos(v: float) -> str:
    return cx.pesos(v)


# ── 1) Lo que se debía al corte, leído del resumen ──────────────────────────────────────────────────────
def _num(v) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def usado_de_resumen(r: dict | None) -> tuple[float | None, str | None]:
    """(deuda total al corte, origen). `usado` leído -> «extracto». Si no, la relación (2) -> «estimado». Si tampoco -> (None, None)."""
    if not isinstance(r, dict):
        return None, None
    usado = _num(r.get("usado"))
    if usado is not None and usado >= 0:
        return round(usado, 2), ORIGEN_EXTRACTO
    a_pagar, restante = _num(r.get("deuda_a_pagar")), _num(r.get("deuda_restante"))
    if a_pagar is None or restante is None:
        return None, None
    extra = sum(_num(r.get(k)) or 0.0 for k in ("cuota_manejo", "cargos_conversion", "intereses"))
    return round(a_pagar + restante + extra, 2), ORIGEN_ESTIMADO


def _resumen(h: HistorialExtracto) -> dict | None:
    r = (h.lectura or {}).get("resumen_tarjeta")
    return r if isinstance(r, dict) else None


def _review(h: HistorialExtracto) -> list[dict]:
    try:
        r = json.loads(h.review_json or "[]")
    except ValueError:
        return []
    return r if isinstance(r, list) else []


def _neto_de_lineas(h: HistorialExtracto) -> float | None:
    """Σ (pagos − compras y cargos) de las líneas del extracto; None si alguna línea no se puede dar por buena."""
    neto = 0.0
    for i in _review(h):
        if i.get("estado") == "sobrante":
            continue
        if i.get("estado") not in ESTADOS_LINEA_SUMA or i.get("tipo") not in ("income", "expense"):
            return None
        neto += float(i.get("monto") or 0) * (1 if i.get("tipo") == "income" else -1)
    return round(neto, 2)


def extractos_de_tarjeta(db: Session, cuenta_id: str) -> list[HistorialExtracto]:
    """Extractos de la cuenta con resumen de tarjeta y corte, por corte (uno por fecha de corte: el más reciente; sin errores
    ni repetidos de subida)."""
    por_corte: dict[date, HistorialExtracto] = {}
    for h in (db.query(HistorialExtracto).filter(HistorialExtracto.cuenta_id == cuenta_id)
              .order_by(HistorialExtracto.creado_en).all()):
        if h.estado == "error" or fe.es_duplicado(h) or _resumen(h) is None:
            continue
        corte = cx.a_fecha(h.fecha_corte) or cx.a_fecha(_resumen(h).get("corte"))
        if corte:
            por_corte[corte] = h
    return [por_corte[k] for k in sorted(por_corte)]


def _poner(h: HistorialExtracto, campo: str, valor) -> bool:
    actual = getattr(h, campo)
    if (actual is None and valor is None) or (actual is not None and valor is not None and abs(float(actual) - float(valor)) < 0.005) \
            or (isinstance(valor, str) and actual == valor):
        return False
    setattr(h, campo, valor)
    return True


def anclar_cuenta(db: Session, cuenta: Cuenta) -> list[str]:
    """Pone en cada extracto de la tarjeta su deuda al corte (negativa) y su deuda inicial (la del extracto anterior).
    Respeta lo escrito a mano (`saldos_origen == 'manual'`). Idempotente. Sin commit. Devuelve los ids cambiados."""
    if (cuenta.tipo or "") != "credito":
        return []
    cambiados: list[str] = []
    anterior: HistorialExtracto | None = None
    for h in extractos_de_tarjeta(db, cuenta.id):
        if h.saldos_origen == "manual":
            anterior = h
            continue
        usado, origen = usado_de_resumen(_resumen(h))
        cambio = False
        if usado is not None:
            cambio |= _poner(h, "saldo_final_extracto", -usado)
            cambio |= _poner(h, "saldos_origen", origen)
        if anterior is not None:
            ini = anterior.saldo_final_extracto
        elif usado is not None and h.lectura_completa is True and not any(
                i.get("estado") in ESTADOS_QUE_FALTAN for i in _review(h)):
            neto = _neto_de_lineas(h)
            ini = None if neto is None else round(-usado - neto, 2)
        else:
            ini = None
        if usado is not None or ini is not None:
            cambio |= _poner(h, "saldo_inicial_extracto", ini)
        if cambio:
            cambiados.append(h.id)
        anterior = h
    return cambiados


# ── 2) Cuadre por extracto ───────────────────────────────────────────────────────────────────────────────
def _es_interes(f: dict) -> bool:
    return (f.get("descripcion") or "").startswith(DESC_INTERESES) or (f.get("categoria") or "").lower() == "intereses"


def composicion(filas: list[dict], ini: date, fin: date, es_apertura) -> dict:
    """Compras y cargos / intereses / pagos de la tarjeta dentro del periodo [ini, fin] (valores positivos)."""
    a, b = datetime.combine(ini, time.min), datetime.combine(fin, time.max)
    compras = intereses = pagos = 0.0
    for f in filas:
        if f["fecha"] is None or not (a <= f["fecha"] <= b) or es_apertura(f):
            continue
        d = delta_saldo(f)
        if d < 0:
            if _es_interes(f):
                intereses += -d
            else:
                compras += -d
        elif d > 0:
            pagos += d
    return {"compras": round(compras, 2), "intereses": round(intereses, 2), "pagos": round(pagos, 2)}


def detalle_cuadre(fila: dict, filas: list[dict], es_apertura) -> dict:
    """El renglón de la tarjeta para un mes del cuadre encadenado (`fila` = el dict del mes). Todo en deuda POSITIVA."""
    ini, fin = cx.a_fecha(fila.get("periodo_inicio")), cx.a_fecha(fila.get("fecha_corte"))
    comp = composicion(filas, ini, fin, es_apertura)
    debia = round(-fila["app_inicial"], 2)
    calculado = round(-fila["app_final"], 2)
    segun = round(-fila["banco_final"], 2)
    dif = round(calculado - segun, 2)  # >0: tu app dice que debes MÁS que el extracto
    cuadra = abs(dif) < TOL
    out = {"debia_inicio": debia, "compras_cargos": comp["compras"], "intereses": comp["intereses"], "pagos": comp["pagos"],
           "debo_calculado": calculado, "segun_extracto": segun, "diferencia": dif, "cuadra": cuadra}
    out["texto"] = (f"Debía al inicio {pesos(debia)} · Compras y cargos {pesos(comp['compras'])} · Intereses {pesos(comp['intereses'])} · "
                    f"Pagos {pesos(comp['pagos'])} · Debo al corte {pesos(calculado)} (calculado) · Según tu extracto "
                    f"{pesos(segun)} " + ("✓" if cuadra else f"✕ por {pesos(dif)}"))
    return out


def causas_orientativas(h: HistorialExtracto | None, fila: dict, filas: list[dict]) -> list[dict]:
    """Por qué no cuadra una tarjeta (solo orienta; nada se cambia solo): líneas sin importar, lectura incompleta y un pago o
    una compra con el tipo cambiado."""
    dif = fila["tarjeta"]["diferencia"]
    out: list[dict] = []
    if h is not None:
        pend = [i for i in _review(h) if i.get("estado") in ESTADOS_QUE_FALTAN]
        if pend:
            out.append({"codigo": "lineas_sin_importar", "probable": True, "efecto": 0.0, "texto": (
                f"Hay {len(pend)} {'línea' if len(pend) == 1 else 'líneas'} del extracto sin importar. Impórtalas y vuelve a mirar.")})
        if h.lectura_completa is False:
            out.append({"codigo": "lectura_incompleta", "probable": True, "efecto": 0.0, "texto": (
                "No leí completo este extracto: lo que leí no suma lo que dice el resumen. Mándame el extracto para aprender su formato.")})
    ini, fin = cx.a_fecha(fila.get("periodo_inicio")), cx.a_fecha(fila.get("fecha_corte"))
    a, b = datetime.combine(ini, time.min), datetime.combine(fin, time.max)
    for f in filas:
        if f["fecha"] is None or not (a <= f["fecha"] <= b) or f.get("fuente") == FUENTE_AJUSTE:
            continue
        monto = float(f.get("monto") or 0)
        # un pago guardado como compra (o una compra como pago) mueve la deuda el DOBLE de su monto
        if abs(2 * monto - abs(dif)) < TOL:
            if f["tipo"] == "expense" and ((f.get("categoria") or "").lower() == "pago de tarjeta" or (f.get("descripcion") or "").lower().startswith(("pago", "abono"))) \
                    and dif > 0:
                out.append({"codigo": "pago_como_compra", "probable": True, "efecto": 0.0, "movimiento_id": f["id"], "texto": (
                    f"«{(f.get('descripcion') or '')[:40]}» de {pesos(monto)} está como compra y parece un pago. Corrige su tipo.")})
                break
            if f["tipo"] == "income" and dif < 0:
                out.append({"codigo": "compra_como_pago", "probable": True, "efecto": 0.0, "movimiento_id": f["id"], "texto": (
                    f"«{(f.get('descripcion') or '')[:40]}» de {pesos(monto)} está como pago y parece una compra. Corrige su tipo.")})
                break
    return out


# ── 3) Deuda inicial ─────────────────────────────────────────────────────────────────────────────────────
def mes_de(h: HistorialExtracto) -> str:
    corte = cx.a_fecha(h.fecha_corte)
    return cx._MESES_LARGO[corte.month - 1] if corte else "tu primer extracto"


def texto_faltan_lineas(h: HistorialExtracto) -> str:
    return f"Aún no puedo calcular con cuánto empezó tu tarjeta: faltan líneas del extracto de {mes_de(h)}."


def objetivo_deuda_inicial(db: Session, cuenta: Cuenta, filas: list[dict], es_automatico) -> dict:
    """Qué deuda inicial corresponde a la tarjeta. {estado: 'sin_extracto'|'incompleto'|'ok', h, inicio, monto, fecha, texto}.
    Solo cuenta el extracto MÁS ANTIGUO, con `usado` leído y TODAS sus líneas leídas y verificadas; si no, no se inventa."""
    ext = extractos_de_tarjeta(db, cuenta.id)
    if not ext:
        return {"estado": "sin_extracto"}
    h = ext[0]
    corte = cx.a_fecha(h.fecha_corte)
    usado, origen = usado_de_resumen(_resumen(h))
    inicio = cx.a_fecha(h.periodo_inicio) or (corte.replace(day=1) if corte else None)
    if corte is None or inicio is None:
        return {"estado": "sin_extracto"}
    if (usado is None or origen != ORIGEN_EXTRACTO or h.lectura_completa is not True
            or any(i.get("estado") in ESTADOS_QUE_FALTAN for i in _review(h))):
        return {"estado": "incompleto", "h": h, "inicio": inicio, "texto": texto_faltan_lineas(h)}
    propias = [f for f in filas if not es_automatico(f)]
    limite = datetime.combine(corte, time.max)
    m = sum(delta_saldo(f) for f in propias if f["fecha"] is None or f["fecha"] <= limite)
    fechas = [f["fecha"].date() for f in propias if f["fecha"] is not None]
    ancla = min(inicio, min(fechas)) if fechas else inicio
    return {"estado": "ok", "h": h, "inicio": inicio, "monto": round(-usado - m, 2), "fecha": ancla - timedelta(days=1)}


# ── 4) Vista en vivo ──────────────────────────────────────────────────────────────────────────────────────
def vista(db: Session, cuenta: Cuenta, hoy: date | None = None) -> dict | None:
    """«Debes $X · Cupo · Disponible · Corte · Pago hasta · Pago mínimo» de UNA tarjeta, en vivo con los movimientos de la app.
    None si la cuenta no es tarjeta. Sin extractos leídos, `deuda` sale del saldo de la cuenta y no hay cupo."""
    if (cuenta.tipo or "") != "credito":
        return None
    _, _, filas = cx._serie(db, cuenta.id)
    saldo_vivo = round(sum(delta_saldo(f) for f in filas), 2)
    ext = [h for h in extractos_de_tarjeta(db, cuenta.id) if h.saldo_final_extracto is not None]
    out = {"cuenta_id": cuenta.id, "tarjeta": True, "deuda": max(0.0, round(-(cuenta.saldo or 0.0), 2)), "cupo": None,
           "disponible": None, "uso_pct": None, "corte": None, "limite_pago": None, "pago_minimo": None,
           "deuda_al_corte": None, "desde_corte": None, "con_extracto": False, "a_favor": (cuenta.saldo or 0.0) > TOL}
    if not ext:
        return out
    h = ext[-1]
    r = _resumen(h) or {}
    corte = cx.a_fecha(h.fecha_corte)
    base = -float(h.saldo_final_extracto)
    desde = datetime.combine(corte, time.max)
    compras = pagos = 0.0
    for f in filas:
        if f["fecha"] is None or f["fecha"] <= desde:
            continue
        d = delta_saldo(f)
        if d < 0:
            compras += -d
        else:
            pagos += d
    deuda = round(base + compras - pagos, 2)
    cupo = _num(r.get("cupo"))
    det = fe.detalle_tarjeta(h) or {}
    out.update(con_extracto=True, deuda=max(0.0, deuda), a_favor=deuda < -TOL, deuda_al_corte=round(base, 2),
               desde_corte={"compras_cargos": round(compras, 2), "pagos": round(pagos, 2)},
               corte=det.get("corte") or (corte.isoformat() if corte else None), limite_pago=det.get("limite_pago"),
               pago_minimo=_num(r.get("pago_minimo")), historial_id=h.id)
    if cupo is not None and cupo > 0:
        disp = round(cupo - max(0.0, deuda), 2)
        out.update(cupo=cupo, disponible=max(0.0, disp), uso_pct=min(100.0, round(max(0.0, deuda) / cupo * 100, 1)))
    return out
