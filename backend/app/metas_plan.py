"""Plan de una meta de ahorro, en lenguaje llano y SIN base de datos (puro, para probarlo con números exactos).

Responde tres preguntas que la persona se hace frente a una meta:
  1. «Si aparto $X al mes, ¿cuándo llego?»  -> opciones cómodo / recomendado / acelerado.
  2. «¿Cuánto necesito al mes para llegar a tiempo?»  -> `aporte_necesario_mes`.
  3. «¿Voy bien?»  -> adelantado / al día / atrasado frente a una línea recta entre el inicio y la fecha.

El sobrante que alimenta las opciones es ingresos - gastos REALES de los últimos 3 meses completos
(sin traslados entre cuentas propias, pagos de tarjeta ni ajustes: ver app/contabilidad.py).
Orientación educativa; no promete rendimientos (no se asume ninguna tasa)."""
import calendar
import math
from datetime import datetime

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]
# Qué parte del sobrante mensual propone cada opción.
OPCIONES = (("comodo", "Cómodo", 0.30), ("recomendado", "Recomendado", 0.50), ("acelerado", "Acelerado", 0.70))
MESES_HISTORIAL = 3
TOLERANCIA_RITMO = 0.03  # ±3 % del objetivo se considera «al día»
TOPE_MESES = 600


def pesos(n: float) -> str:
    return "$" + f"{round(n):,.0f}".replace(",", ".")


def mes_anio(fecha: datetime) -> str:
    return f"{MESES[fecha.month - 1]} de {fecha.year}"


def sumar_meses(fecha: datetime, n: int) -> datetime:
    """Mismo día n meses después (si el mes destino es más corto, el último día de ese mes)."""
    total = fecha.year * 12 + (fecha.month - 1) + n
    anio, mes = divmod(total, 12)
    mes += 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return fecha.replace(year=anio, month=mes, day=dia)


def _meses_hasta(hoy: datetime, fecha: datetime) -> int:
    """Cuotas mensuales que quedan hasta la fecha (días / 30,4375 hacia arriba, mínimo 1; 0 si ya pasó)."""
    dias = (fecha.date() - hoy.date()).days
    if dias <= 0:
        return 0
    return max(1, math.ceil(dias / 30.4375))


def _redondear(monto: float) -> int:
    """Hacia abajo a un múltiplo «redondo» (5.000 si es poco, 10.000 si es más): se ve como una cifra que alguien apartaría."""
    paso = 5_000 if monto < 200_000 else 10_000
    return int(monto // paso) * paso


def opciones_de_aporte(sobrante: float | None) -> list[dict]:
    """[{id, nombre, monto}] según el sobrante mensual. Vacío si no sobra nada. Sin montos repetidos."""
    if not sobrante or sobrante <= 0:
        return []
    out, vistos = [], set()
    for id_, nombre, parte in OPCIONES:
        monto = _redondear(sobrante * parte)
        if monto <= 0 or monto in vistos:
            continue
        vistos.add(monto)
        out.append({"id": id_, "nombre": nombre, "monto": monto})
    return out


def _meses_para_llegar(faltante: float, aporte: float) -> int | None:
    if faltante <= 0:
        return 0
    if aporte <= 0:
        return None
    n = math.ceil(faltante / aporte)
    return n if n <= TOPE_MESES else None


def _estado_ritmo(meta: dict, hoy: datetime) -> tuple[str, float | None]:
    """('lograda'|'sin_fecha'|'vencida'|'adelantado'|'al_dia'|'atrasado', diferencia en pesos)."""
    objetivo, actual = meta["monto_objetivo"], meta["monto_actual"]
    if objetivo > 0 and actual >= objetivo:
        return "lograda", 0.0
    fin, ini = meta.get("fecha_objetivo"), meta.get("fecha_inicio")
    if not fin:
        return "sin_fecha", None
    if fin <= hoy:
        return "vencida", actual - objetivo
    ini = ini or hoy
    total = (fin - ini).total_seconds()
    if total <= 0:
        return "sin_fecha", None
    transcurrido = min(max((hoy - ini).total_seconds(), 0), total)
    esperado = objetivo * transcurrido / total
    diferencia = actual - esperado
    if abs(diferencia) <= objetivo * TOLERANCIA_RITMO:
        return "al_dia", diferencia
    return ("adelantado" if diferencia > 0 else "atrasado"), diferencia


def plan_de_meta(meta: dict, sobrante: float | None, hoy: datetime) -> dict:
    """`meta`: {monto_objetivo, monto_actual, fecha_inicio?, fecha_objetivo?}. Devuelve el plan completo."""
    objetivo = float(meta.get("monto_objetivo") or 0)
    actual = float(meta.get("monto_actual") or 0)
    faltante = max(0.0, objetivo - actual)
    fin = meta.get("fecha_objetivo")
    estado, diferencia = _estado_ritmo({**meta, "monto_objetivo": objetivo, "monto_actual": actual}, hoy)

    necesario = None
    if fin and faltante > 0:
        meses = _meses_hasta(hoy, fin)
        if meses > 0:
            necesario = math.ceil(faltante / meses)

    opciones = []
    for o in opciones_de_aporte(sobrante):
        n = _meses_para_llegar(faltante, o["monto"])
        llegada = sumar_meses(hoy, n) if n is not None else None
        a_tiempo = bool(fin and llegada is not None and llegada.date() <= fin.date())
        opciones.append({
            **o, "meses": n, "llegas": mes_anio(llegada) if llegada else None,
            "llegada": llegada.date().isoformat() if llegada else None,
            "a_tiempo": a_tiempo if fin else None,
            "texto": (f"Si apartas {pesos(o['monto'])} al mes llegas en {mes_anio(llegada)}"
                      if llegada else f"Con {pesos(o['monto'])} al mes tardarías demasiado"),
        })

    # La que se propone de entrada: la más cómoda que llega a tiempo; si ninguna, la «recomendada».
    sugerida = None
    if opciones:
        a_tiempo = [o for o in opciones if o["a_tiempo"]]
        sugerida = (a_tiempo[0] if a_tiempo else next((o for o in opciones if o["id"] == "recomendado"), opciones[0]))["id"]

    texto_necesario = None
    if estado == "lograda":
        texto_resumen = "¡Ya llegaste a tu meta!"
    elif necesario is not None:
        texto_necesario = f"Para llegar a tiempo necesitas {pesos(necesario)} al mes"
        texto_resumen = texto_necesario
    elif estado == "vencida":
        texto_resumen = "La fecha que pusiste ya pasó. Elige una nueva para recalcular."
    else:
        texto_resumen = "Ponle una fecha a tu meta y te digo cuánto apartar al mes."

    if estado != "lograda" and sobrante is None:
        aviso_sobrante = "Aún no tenemos un mes completo de movimientos para calcular cuánto te sobra."
    elif estado != "lograda" and not opciones:
        aviso_sobrante = "En los últimos meses no te ha sobrado plata: gastaste lo mismo o más de lo que entró."
    else:
        aviso_sobrante = None

    frase_ritmo = {
        "lograda": "Meta cumplida.",
        "adelantado": f"Vas adelantado: llevas {pesos(abs(diferencia or 0))} más de lo previsto para hoy.",
        "al_dia": "Vas al día con tu plan.",
        "atrasado": f"Vas atrasado: te faltan {pesos(abs(diferencia or 0))} para ir al día.",
        "vencida": "La fecha ya pasó.",
        "sin_fecha": None,
    }[estado]

    return {
        "faltante": faltante,
        "estado_ritmo": estado,
        "diferencia_ritmo": round(diferencia) if diferencia is not None else None,
        "frase_ritmo": frase_ritmo,
        "aporte_necesario_mes": necesario,
        "texto_necesario": texto_necesario,
        "texto_resumen": texto_resumen,
        "opciones": opciones,
        "opcion_sugerida": sugerida,
        "aviso_sobrante": aviso_sobrante,
    }


def sobrante_promedio(db, usuario_id: str, hoy: datetime) -> dict:
    """{sobrante, ingreso, gasto, meses_con_datos}: promedio de los últimos 3 meses COMPLETOS.
    `sobrante` es None si no hay ningún mes con movimientos (no se inventa una cifra)."""
    from app.informe_datos import cargar_movs_efectivos

    anio, mes = hoy.year, hoy.month
    fin = datetime(anio, mes, 1)
    for _ in range(MESES_HISTORIAL):
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    inicio = datetime(anio, mes, 1)
    ingresos = gastos = 0.0
    meses = set()
    for m in cargar_movs_efectivos(db, usuario_id, inicio, fin):
        if not (inicio <= m["fecha"] < fin) or m["tipo"] not in ("income", "expense"):
            continue
        meses.add(m["fecha"].strftime("%Y-%m"))
        if m["tipo"] == "income":
            ingresos += m["monto"]
        else:
            gastos += m["monto"]
    if not meses:
        return {"sobrante": None, "ingreso": 0.0, "gasto": 0.0, "meses_con_datos": 0}
    n = len(meses)
    return {"sobrante": (ingresos - gastos) / n, "ingreso": ingresos / n, "gasto": gastos / n, "meses_con_datos": n}
