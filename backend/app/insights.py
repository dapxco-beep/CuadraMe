"""
Insights financieros: detección de anomalías (regla estadística, sin IA) y
generación de resumen/respuestas en lenguaje natural sobre las finanzas del
usuario (vía OpenRouter, mismo modelo gratuito usado en pdf_extract.py).
"""
import json
from collections import defaultdict


from app.utiles import ahora_co
from app import ia



def detectar_anomalias(movimientos: list[dict]) -> list[dict]:
    """Compara el gasto del mes actual contra el promedio de los 3 meses
    anteriores, por categoría. Marca las que se disparan >40%."""
    hoy = ahora_co()
    mes_actual = hoy.strftime("%Y-%m")

    por_mes_categoria: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for m in movimientos:
        if m["tipo"] != "expense":
            continue
        clave_mes = m["fecha"].strftime("%Y-%m")
        por_mes_categoria[clave_mes][m["categoria"]] += m["monto"]

    meses_anteriores = sorted(k for k in por_mes_categoria if k < mes_actual)[-3:]
    if not meses_anteriores or mes_actual not in por_mes_categoria:
        return []

    anomalias = []
    gasto_actual = por_mes_categoria[mes_actual]
    for categoria, monto_actual in gasto_actual.items():
        historicos = [por_mes_categoria[m].get(categoria, 0) for m in meses_anteriores]
        promedio = sum(historicos) / len(historicos) if historicos else 0
        if promedio < 10000:  # ignora categorías con gasto histórico insignificante
            continue
        variacion = (monto_actual - promedio) / promedio
        if variacion > 0.4:
            anomalias.append({
                "categoria": categoria,
                "monto_actual": round(monto_actual),
                "promedio_historico": round(promedio),
                "variacion_pct": round(variacion * 100),
            })

    anomalias.sort(key=lambda a: a["variacion_pct"], reverse=True)
    return anomalias


def _resumen_contexto(resumen: dict) -> str:
    return json.dumps(resumen, ensure_ascii=False, default=str)


def generar_resumen_semanal(resumen: dict) -> str:
    """resumen: dict con ingresos/gastos de la semana, top categorías, anomalías, etc."""
    if not ia.hay_ia():
        return _resumen_fallback(resumen)

    prompt = (
        "Eres el asistente financiero de CuadraMe. Con estos datos de la semana del "
        "usuario, escribe un resumen breve (máx 4 líneas), cálido pero directo, en "
        "español de Colombia. Menciona lo más relevante: si gastó más o menos que "
        "antes, la categoría que más pesó, y UN consejo concreto y accionable. "
        "No uses saludos ni cierres genéricos, ve directo al contenido.\n\n"
        f"Datos: {_resumen_contexto(resumen)}"
    )

    try:
        return ia.completar([{"role": "user", "content": prompt}], temperatura=0.6, max_tokens=400)
    except Exception:
        return _resumen_fallback(resumen)


def _resumen_fallback(resumen: dict) -> str:
    gastos = resumen.get("gastos", 0)
    ingresos = resumen.get("ingresos", 0)
    top = resumen.get("top_categorias", [])
    top_txt = f" La mayor parte fue en {top[0]['categoria']}." if top else ""
    periodo = resumen.get("periodo") or "los últimos 7 días"
    return f"En {periodo} ingresaron ${ingresos:,.0f} y gastaste ${gastos:,.0f}.{top_txt}"


def responder_pregunta(pregunta: str, contexto: dict) -> str | None:
    """Chat de finanzas: responde preguntas sobre los datos del usuario, usando
    SOLO el contexto que se le pasa (no accede a la base de datos directamente,
    así que no puede inventar cifras que no estén en el contexto)."""
    if not ia.hay_ia():
        return None

    prompt = (
        "Eres el asistente financiero de CuadraMe. Responde la pregunta del usuario "
        "usando ÚNICAMENTE los datos del contexto JSON de abajo — si la respuesta no "
        "está ahí, dilo claramente en vez de inventar cifras. Responde en español de "
        "Colombia, breve y directo (máx 3 líneas), con cifras en pesos colombianos.\n\n"
        f"Contexto: {_resumen_contexto(contexto)}\n\n"
        f"Pregunta: {pregunta}"
    )

    try:
        return ia.completar([{"role": "user", "content": prompt}], temperatura=0.3, max_tokens=400)
    except Exception:
        return None
