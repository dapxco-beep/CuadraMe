"""
Cálculos de tarjetas de crédito reales (cuentas de tipo "credito").

Convención de saldo: igual que en cualquier cuenta, un gasto RESTA. Una tarjeta
con saldo -800.000 significa que se han usado 800.000 del cupo. Un saldo >= 0
significa cupo usado = 0 (si pagaste de más queda a favor, no se considera
cupo extra).

Funciones puras: reciben `hoy` para poder probarlas con fechas fijas.
"""
import calendar
from datetime import date, datetime, timedelta

from app.contabilidad import FUENTE_AJUSTE, FUENTE_IMPORTADO_SIN_SALDO, FUENTE_TRANSFERENCIA
from app.utiles import ahora_co

UMBRAL_ALERTA = 30  # % de utilización a partir del cual conviene vigilar
UMBRAL_CRITICO = 80  # % que ya afecta el score crediticio y deja poco margen
PCT_PAGO_MINIMO = 0.05  # estimación: 5% del saldo usado + intereses (cada banco difiere)
DIAS_AVISO_PAGO = 3  # cuántos días antes del pago se avisa por push


def _fecha_en_mes(anio: int, mes: int, dia: int) -> date:
    """Clampa el día al último día real del mes (31 en febrero -> 28/29)."""
    return date(anio, mes, min(dia, calendar.monthrange(anio, mes)[1]))


def proxima_fecha(dia: int, hoy: date) -> date:
    """Próxima ocurrencia (hoy incluido) de un 'día del mes'."""
    f = _fecha_en_mes(hoy.year, hoy.month, dia)
    if f >= hoy:
        return f
    anio, mes = (hoy.year + 1, 1) if hoy.month == 12 else (hoy.year, hoy.month + 1)
    return _fecha_en_mes(anio, mes, dia)


def _g(m, campo, defecto=None):
    """Lee un campo de un objeto ORM o de un dict."""
    if isinstance(m, dict):
        return m.get(campo, defecto)
    return getattr(m, campo, defecto)


def ultimo_corte(dia_corte: int, hoy: date) -> date:
    """Último día de corte ya ocurrido (hoy incluido: el banco cierra al final del día)."""
    f = _fecha_en_mes(hoy.year, hoy.month, dia_corte)
    if f <= hoy:
        return f
    anio, mes = (hoy.year - 1, 12) if hoy.month == 1 else (hoy.year, hoy.month - 1)
    return _fecha_en_mes(anio, mes, dia_corte)


def limite_pago_del_corte(corte: date, dia_pago: int) -> date:
    """Fecha límite de pago del extracto que cierra en `corte`: la primera fecha
    con ese día de pago que cae DESPUÉS del corte (corte 15 / pago 30 -> mismo mes;
    corte 25 / pago 10 -> mes siguiente; en meses cortos el día se ajusta al último)."""
    f = _fecha_en_mes(corte.year, corte.month, dia_pago)
    if f > corte:
        return f
    anio, mes = (corte.year + 1, 1) if corte.month == 12 else (corte.year, corte.month + 1)
    return _fecha_en_mes(anio, mes, dia_pago)


def inicio_despues_corte(dia_corte: int | None, hoy: datetime | date | None = None) -> datetime | None:
    """Desde cuándo hay que traer los movimientos de la tarjeta (el día siguiente al
    último corte, 00:00), o None si no se conoce el día de corte."""
    if not dia_corte:
        return None
    hoy_d = (hoy or ahora_co())
    hoy_d = hoy_d.date() if isinstance(hoy_d, datetime) else hoy_d
    c = ultimo_corte(dia_corte, hoy_d)
    return datetime(c.year, c.month, c.day) + timedelta(days=1)


def movimientos_tras_corte(db, cuenta, hoy: datetime | None = None) -> list:
    """Movimientos de la tarjeta posteriores a su último corte (lista vacía si no
    tiene día de corte). Es lo único que necesita estado_extracto."""
    from app.models import Movimiento  # import local: evita ciclos al cargar el módulo

    desde = inicio_despues_corte(cuenta.dia_corte, hoy)
    if desde is None:
        return []
    return db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta.id, Movimiento.fecha >= desde).all()


def extractos_guardados(db, cuenta_ids: list[str]) -> dict[str, dict]:
    """{cuenta_id: extracto real aplicado por el cliente} (solo las tarjetas que tengan uno)."""
    from app.models_cuotas import ExtractoTarjeta  # import local: evita ciclos al cargar el módulo

    if not cuenta_ids:
        return {}
    filas = db.query(ExtractoTarjeta).filter(ExtractoTarjeta.cuenta_id.in_(cuenta_ids)).all()
    return {
        f.cuenta_id: {
            "pago_total": f.pago_total, "pago_minimo": f.pago_minimo, "cupo_disponible": f.cupo_disponible,
            "fecha_limite_pago": f.fecha_limite_pago, "fecha_corte": f.fecha_corte,
        }
        for f in filas
    }


def sin_historial_al_corte(db, cuenta, hoy: datetime | None = None) -> bool:
    """True si la tarjeta no tiene ningún movimiento real (ni ajuste) hasta su último corte:
    todo lo que se sabe de su deuda es el saldo que el cliente declaró al crearla. En ese caso
    ese saldo NO es un extracto del banco y no se puede decir que el plazo 'ya pasó'."""
    from app.models import Movimiento  # import local: evita ciclos al cargar el módulo

    desde = inicio_despues_corte(cuenta.dia_corte, hoy)
    if desde is None:
        return False
    previo = (
        db.query(Movimiento.id)
        .filter(Movimiento.cuenta_id == cuenta.id, Movimiento.fecha < desde, Movimiento.fuente != FUENTE_AJUSTE)
        .first()
    )
    return previo is None


def delta_saldo_movimiento(m) -> float:
    """Cuánto movió el saldo de la tarjeta este movimiento (compra < 0, abono > 0).
    Misma regla que el módulo de movimientos: los importados 'sin saldo' y los
    'transfer' sueltos de un extracto no tocaron el saldo; las transferencias
    internas sí (':in' suma, ':out' resta)."""
    tipo, monto, fuente = _g(m, "tipo"), float(_g(m, "monto", 0) or 0), _g(m, "fuente")
    if fuente == FUENTE_IMPORTADO_SIN_SALDO:
        return 0.0
    if tipo == "income":
        return monto
    if tipo == "expense":
        return -monto
    if tipo == "transfer" and fuente == FUENTE_TRANSFERENCIA:
        notas = _g(m, "notas") or ""
        return monto if notas.endswith(":in") else -monto if notas.endswith(":out") else 0.0
    return 0.0


def estado_extracto(saldo: float, movimientos, dia_corte: int | None, dia_pago: int | None, hoy: date,
                    guardado: dict | None = None, saldo_declarado: bool = False) -> dict:
    """Lo que hay que pagar para NO pagar intereses: la deuda al último corte.

    deuda al corte = deuda de hoy menos lo que se movió DESPUÉS del corte
    (compras la suben, abonos la bajan). `movimientos` son los de la cuenta con
    fecha posterior al corte (los anteriores no hacen falta: ya están en el saldo).
    Lo pagado desde el corte se descuenta del total del extracto, y las compras
    posteriores van al próximo extracto. Función pura (recibe `hoy`).

    `guardado` = lo que el cliente aplicó de su extracto real ({pago_total, pago_minimo,
    fecha_limite_pago}). Si su fecha límite es la de este ciclo, el total del banco
    (que incluye intereses y cargos que no vemos) manda sobre el que calculamos.

    `saldo_declarado` = la tarjeta no tiene historial hasta el corte: su deuda es solo el saldo que
    el cliente declaró al crearla, no un extracto. Se marca y NUNCA se da por vencida (a menos que
    el total venga de un extracto real del banco).
    """
    vacio = {
        "total_extracto": None, "pagado_desde_corte": None, "falta_para_evitar_intereses": None,
        "compras_despues_corte": None, "fecha_limite_pago": None, "fecha_ultimo_corte": None,
        "dias_para_limite": None, "pagado_pct": None, "vencido": False, "total_del_banco": False,
        "pago_minimo_extracto": None, "pago_total_extracto": None, "saldo_declarado": False,
    }
    if not dia_corte:
        return vacio
    corte = ultimo_corte(dia_corte, hoy)
    despues = [
        m for m in movimientos
        if (_g(m, "fecha").date() if isinstance(_g(m, "fecha"), datetime) else _g(m, "fecha")) > corte
    ]
    movido = sum(delta_saldo_movimiento(m) for m in despues)  # incluye ajustes: reconstruye el saldo
    reales = [m for m in despues if _g(m, "fuente") != FUENTE_AJUSTE]
    deltas = [delta_saldo_movimiento(m) for m in reales]
    compras = round(sum(-d for d in deltas if d < 0), 2)
    pagado = round(sum(d for d in deltas if d > 0), 2)

    saldo_al_corte = (saldo or 0) - movido
    total = round(max(0.0, -saldo_al_corte), 2)
    limite = limite_pago_del_corte(corte, dia_pago) if dia_pago else None

    # Extracto real aplicado por el cliente: vale mientras su fecha límite no haya pasado.
    vigente = bool(guardado and guardado.get("fecha_limite_pago") and guardado["fecha_limite_pago"] >= hoy.isoformat())
    del_banco = bool(
        vigente and guardado.get("pago_total") is not None and limite is not None
        and guardado["fecha_limite_pago"] == limite.isoformat()
    )
    if del_banco:
        total = round(float(guardado["pago_total"]), 2)
    falta = round(max(0.0, total - pagado), 2)
    declarado = bool(saldo_declarado and not del_banco)
    return {
        "saldo_declarado": declarado,
        "total_del_banco": del_banco,
        "pago_minimo_extracto": guardado.get("pago_minimo") if vigente else None,
        "pago_total_extracto": guardado.get("pago_total") if vigente else None,
        "total_extracto": total,
        "pagado_desde_corte": min(pagado, total) if total else 0.0,
        "falta_para_evitar_intereses": falta,
        "compras_despues_corte": compras,
        "fecha_limite_pago": limite.isoformat() if limite else None,
        "fecha_ultimo_corte": corte.isoformat(),
        "dias_para_limite": (limite - hoy).days if limite else None,
        "pagado_pct": round(min(pagado, total) / total * 100, 1) if total else None,
        "vencido": bool(limite and hoy > limite and falta > 0 and not declarado),
    }


def nivel_utilizacion(pct: float | None) -> str:
    if pct is None:
        return "sin_cupo"
    if pct > UMBRAL_CRITICO:
        return "critico"
    if pct > UMBRAL_ALERTA:
        return "alerta"
    return "ok"


def calc_tarjeta(cuenta, hoy: datetime | None = None, movimientos=None, guardado: dict | None = None,
                 saldo_declarado: bool = False) -> dict:
    """Devuelve cupo usado/disponible, % de utilización, próximas fechas de
    corte y pago (hora Colombia), pago mínimo e interés estimados. Si se pasan
    los `movimientos` posteriores al último corte (ver inicio_despues_corte),
    también el extracto: total, pagado, falta para evitar intereses, etc."""
    hoy_d = (hoy or ahora_co()).date()
    usado = max(0.0, -(cuenta.saldo or 0))
    cupo = cuenta.cupo_total if cuenta.cupo_total and cuenta.cupo_total > 0 else None

    disponible = max(0.0, cupo - usado) if cupo else None
    pct = round(usado / cupo * 100, 1) if cupo else None

    corte = proxima_fecha(cuenta.dia_corte, hoy_d) if cuenta.dia_corte else None
    pago = proxima_fecha(cuenta.dia_pago, hoy_d) if cuenta.dia_pago else None

    # Interés de un mes si NO se paga el total: la tasa efectiva anual se
    # convierte a mensual equivalente (1+ea)^(1/12)-1, no ea/12.
    interes = None
    if cuenta.tasa_ea is not None:
        tasa_mensual = (1 + cuenta.tasa_ea / 100) ** (1 / 12) - 1
        interes = round(usado * tasa_mensual)
    minimo = min(usado, usado * PCT_PAGO_MINIMO + (interes or 0))

    if movimientos is not None:
        extracto = estado_extracto(cuenta.saldo, movimientos, cuenta.dia_corte, cuenta.dia_pago, hoy_d, guardado, saldo_declarado)
    else:
        extracto = estado_extracto(0, [], None, None, hoy_d)  # todo en None

    return {
        **extracto,
        "cupo_usado": round(usado),
        "cupo_disponible": round(disponible) if disponible is not None else None,
        "utilizacion_pct": pct,
        "nivel_utilizacion": nivel_utilizacion(pct),
        "proximo_corte": corte.isoformat() if corte else None,
        "proximo_pago": pago.isoformat() if pago else None,
        "dias_para_corte": (corte - hoy_d).days if corte else None,
        "dias_para_pago": (pago - hoy_d).days if pago else None,
        "pago_minimo_estimado": round(minimo),
        # El del extracto real (si el cliente lo aplicó y sigue vigente) manda sobre la estimación.
        "pago_minimo": extracto["pago_minimo_extracto"] if extracto["pago_minimo_extracto"] is not None else round(minimo),
        "pago_minimo_del_extracto": extracto["pago_minimo_extracto"] is not None,
        "interes_estimado": interes,
    }


def tarjetas_por_avisar(cuentas, hoy: datetime | None = None, movs_por_cuenta: dict | None = None,
                        guardados: dict | None = None):
    """Filtra las tarjetas a las que hoy toca avisar 'paga antes del X':
    el pago es en <= DIAS_AVISO_PAGO días y ese pago aún no se avisó
    (ultima_alerta_pago guarda la fecha ya notificada, así el cron diario no
    repite el mismo aviso). Devuelve [(cuenta, info)].

    Con `movs_por_cuenta` ({cuenta.id: movimientos posteriores al corte}) y día de
    corte, el monto es lo que FALTA para no pagar intereses (total del extracto
    menos lo ya pagado) y no se avisa si ya está pagado. Sin esos datos usa la
    deuda actual (comportamiento anterior). La info trae monto_aviso,
    fecha_aviso y dias_aviso para armar el mensaje."""
    por_avisar = []
    for c in cuentas:
        if c.tipo != "credito" or not c.dia_pago:
            continue
        usar_extracto = movs_por_cuenta is not None and bool(c.dia_corte)
        movs = (movs_por_cuenta.get(getattr(c, "id", None)) or []) if usar_extracto else None
        info = calc_tarjeta(c, hoy, movs, (guardados or {}).get(getattr(c, "id", None)))
        if info["falta_para_evitar_intereses"] is not None:
            monto, fecha, dias = info["falta_para_evitar_intereses"], info["fecha_limite_pago"], info["dias_para_limite"]
            if monto <= 0 or dias < 0:
                continue  # ya pagado, o el plazo ya pasó (no es un "paga antes de")
        else:
            monto, fecha, dias = info["cupo_usado"], info["proximo_pago"], info["dias_para_pago"]
            if monto <= 0:
                continue
        if dias > DIAS_AVISO_PAGO:
            continue
        if c.ultima_alerta_pago == fecha:
            continue
        info = {**info, "monto_aviso": monto, "fecha_aviso": fecha, "dias_aviso": dias}
        por_avisar.append((c, info))
    return por_avisar
