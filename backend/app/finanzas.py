"""
Cálculos de metas de ahorro, recurrentes y deudas.
Migrado de Features.js: progreso/ETA de metas, estado de recurrentes
(pagado/próximo/vencido), amortización simple de deudas.
"""
import math
from datetime import datetime


def calc_progreso_meta(meta) -> dict:
    hoy = datetime.utcnow()
    objetivo = meta.monto_objetivo or 0
    actual = meta.monto_actual or 0
    progreso = min(100, (actual / objetivo) * 100) if objetivo > 0 else 0
    faltante = max(0, objetivo - actual)

    inicio = meta.fecha_inicio or hoy
    dias_transcurridos = max(1, (hoy - inicio).total_seconds() / 86400)
    ritmo = actual / dias_transcurridos  # COP/día
    eta_meses = math.ceil(faltante / (ritmo * 30)) if ritmo > 0 else None

    dias_restantes = None
    aporte_necesario_mes = None
    if meta.fecha_objetivo:
        dias_restantes = math.ceil((meta.fecha_objetivo - hoy).total_seconds() / 86400)
        if dias_restantes > 0:
            aporte_necesario_mes = math.ceil(faltante / (dias_restantes / 30))

    return {
        "progreso_pct": round(progreso, 1),
        "faltante": faltante,
        "dias_restantes": dias_restantes,
        "eta_meses": eta_meses,
        "aporte_necesario_mes": aporte_necesario_mes,
        "completada": progreso >= 100,
    }


def calc_estado_recurrente(rec) -> dict:
    hoy = datetime.utcnow()
    dia_mes = rec.dia_del_mes or 1
    alerta_dias = rec.alerta_dias_antes or 2
    fecha_esperada = hoy.replace(day=min(dia_mes, 28))

    ya_este_mes = (
        rec.ultima_vez is not None
        and rec.ultima_vez.year == hoy.year
        and rec.ultima_vez.month == hoy.month
    )

    dias_para_vencer = math.ceil((fecha_esperada - hoy).total_seconds() / 86400)

    if ya_este_mes:
        estado = "pagado"
    elif dias_para_vencer < 0:
        estado = "vencido"
    elif dias_para_vencer <= alerta_dias:
        estado = "proximo"
    else:
        estado = "pendiente"

    return {
        "estado": estado,
        "dias_para_vencer": dias_para_vencer,
        "ya_este_mes": ya_este_mes,
    }


def calc_deuda(deuda) -> dict:
    hoy = datetime.utcnow()
    saldo = deuda.saldo_actual or 0
    cuota = deuda.cuota_mensual or 0
    tasa_mensual = deuda.tasa_mensual or 0

    interes_este_mes = saldo * (tasa_mensual / 100)
    abono_capital = max(0, cuota - interes_este_mes)

    cuotas_faltantes = None
    if cuota > interes_este_mes and saldo > 0 and tasa_mensual > 0:
        try:
            cuotas_faltantes = math.ceil(
                math.log(cuota / (cuota - saldo * (tasa_mensual / 100)))
                / math.log(1 + tasa_mensual / 100)
            )
            if cuotas_faltantes < 0 or not math.isfinite(cuotas_faltantes):
                cuotas_faltantes = None
        except (ValueError, ZeroDivisionError):
            cuotas_faltantes = None

    dia_pago = deuda.dia_pago or 1
    fecha_pago = hoy.replace(day=min(dia_pago, 28))
    if fecha_pago < hoy:
        mes_siguiente = fecha_pago.month + 1
        anio = fecha_pago.year + (1 if mes_siguiente > 12 else 0)
        mes_siguiente = mes_siguiente if mes_siguiente <= 12 else 1
        fecha_pago = fecha_pago.replace(year=anio, month=mes_siguiente)
    dias_para_pago = math.ceil((fecha_pago - hoy).total_seconds() / 86400)

    dias_para_corte = None
    if deuda.dia_corte:
        fecha_corte = hoy.replace(day=min(deuda.dia_corte, 28))
        if fecha_corte < hoy:
            mes_siguiente = fecha_corte.month + 1
            anio = fecha_corte.year + (1 if mes_siguiente > 12 else 0)
            mes_siguiente = mes_siguiente if mes_siguiente <= 12 else 1
            fecha_corte = fecha_corte.replace(year=anio, month=mes_siguiente)
        dias_para_corte = math.ceil((fecha_corte - hoy).total_seconds() / 86400)

    if dias_para_pago <= 3:
        urgencia = "critico"
    elif dias_para_pago <= 7:
        urgencia = "proximo"
    else:
        urgencia = "normal"

    tasa_ea = round((math.pow(1 + tasa_mensual / 100, 12) - 1) * 100, 2)

    return {
        "tasa_ea": tasa_ea,
        "interes_este_mes": round(interes_este_mes),
        "abono_capital": round(abono_capital),
        "cuotas_faltantes": cuotas_faltantes,
        "dias_para_pago": dias_para_pago,
        "dias_para_corte": dias_para_corte,
        "urgencia": urgencia,
    }
