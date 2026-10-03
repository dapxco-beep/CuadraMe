"""
Puntaje de salud financiera (0-100).

Todo lo de este módulo es PURO (sin base de datos ni red): recibe números ya
convertidos a COP y devuelve el puntaje. Así se puede probar con casos exactos
y el endpoint solo se encarga de juntar los datos.

Cada componente da 0-100 y pesa distinto. Si a un componente le faltan datos
(ej. no hay presupuestos creados) se EXCLUYE y los pesos se re-normalizan: no
se castiga a alguien por algo que aún no configuró.
"""

# Pesos (suman 100). El colchón y el ahorro son lo que más protege a una persona.
PESOS = {
    "emergencia": 30,
    "ahorro": 25,
    "deuda": 20,
    "presupuesto": 15,
    "constancia": 10,
}

NOMBRES = {
    "emergencia": "Fondo de emergencia",
    "ahorro": "Tasa de ahorro",
    "deuda": "Deuda vs. ingreso",
    "presupuesto": "Cumplimiento de presupuesto",
    "constancia": "Constancia de registro",
}

META_MESES_EMERGENCIA = 6      # 6 meses de gasto = puntaje completo
META_TASA_AHORRO = 0.20        # ahorrar 20% del ingreso = puntaje completo
TOPE_DEUDA_INGRESO = 0.40      # cuotas >= 40% del ingreso = puntaje 0
DIAS_META_CONSTANCIA = 20      # registrar en 20 de los últimos 30 días = completo


def _acotar(valor: float) -> float:
    return max(0.0, min(100.0, valor))


def puntaje_emergencia(saldo_liquido: float, gasto_mensual: float) -> tuple[float | None, float | None]:
    """Devuelve (puntaje, meses_cubiertos). Sin gastos conocidos no hay base de comparación."""
    if gasto_mensual <= 0:
        return None, None
    meses = max(0.0, saldo_liquido) / gasto_mensual
    return _acotar(meses / META_MESES_EMERGENCIA * 100), meses


def puntaje_ahorro(ingresos: float, gastos: float) -> tuple[float | None, float | None]:
    if ingresos <= 0:
        return (0.0, None) if gastos > 0 else (None, None)
    tasa = (ingresos - gastos) / ingresos
    return _acotar(tasa / META_TASA_AHORRO * 100), tasa


def puntaje_deuda(cuotas_mensuales: float, ingresos: float) -> tuple[float | None, float | None]:
    if cuotas_mensuales <= 0:
        return 100.0, 0.0  # sin deudas activas es lo mejor posible
    if ingresos <= 0:
        return 0.0, None
    ratio = cuotas_mensuales / ingresos
    return _acotar((1 - ratio / TOPE_DEUDA_INGRESO) * 100), ratio


def puntaje_presupuesto(presupuestos: list[tuple[float, float]]) -> tuple[float | None, float | None]:
    """presupuestos = [(limite_efectivo, gastado)]. Fracción de presupuestos respetados."""
    validos = [(lim, gas) for lim, gas in presupuestos if lim > 0]
    if not validos:
        return None, None
    cumplidos = sum(1 for lim, gas in validos if gas <= lim)
    frac = cumplidos / len(validos)
    return frac * 100, frac


def puntaje_constancia(dias_con_registro: int) -> tuple[float, int]:
    return _acotar(dias_con_registro / DIAS_META_CONSTANCIA * 100), dias_con_registro


def _pesos(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def _consejo(clave: str, detalle: float | None, saldo: float, gasto: float) -> str:
    if clave == "emergencia":
        faltan = max(0.0, META_MESES_EMERGENCIA * gasto - saldo)
        return (
            f"Tu colchón cubre {detalle:.1f} meses de gasto. Para llegar a {META_MESES_EMERGENCIA} "
            f"te faltan unos ${_pesos(faltan)}: crea una meta de ahorro con aporte automático."
        )
    if clave == "ahorro":
        if detalle is None or detalle <= 0:
            return "Estás gastando todo lo que ganas. Revisa tus 3 categorías más grandes y recorta una."
        return (
            f"Ahorras el {detalle * 100:.0f}% de tus ingresos; la meta es {META_TASA_AHORRO * 100:.0f}%. "
            "Aparta ese dinero el día que cobras."
        )
    if clave == "deuda":
        if detalle is None:
            return "Tienes cuotas de deuda pero ningún ingreso registrado en 30 días. Registra tus ingresos."
        return f"Tus cuotas de deuda son el {detalle * 100:.0f}% de tu ingreso. Abona extra a la de mayor tasa para bajarlas."
    if clave == "presupuesto":
        return "Estás pasado en algún presupuesto este mes. Muévele plata desde otro sobre o ajusta el límite."
    return "Registra tus gastos a diario (aunque sean pocos): con 20 días al mes tendrás datos confiables."


def calcular_salud_financiera(
    *,
    saldo_liquido: float,
    gasto_mensual_promedio: float,
    ingresos_30d: float,
    gastos_30d: float,
    cuotas_deuda_mensual: float,
    presupuestos: list[tuple[float, float]],
    dias_con_registro_30d: int,
) -> dict:
    """Devuelve {score, nivel, componentes:[...], consejos:[...]}.
    Cada componente: {clave, nombre, puntaje, peso, detalle, disponible}."""
    p_em, meses = puntaje_emergencia(saldo_liquido, gasto_mensual_promedio)
    p_ah, tasa = puntaje_ahorro(ingresos_30d, gastos_30d)
    p_de, ratio = puntaje_deuda(cuotas_deuda_mensual, ingresos_30d)
    p_pr, frac = puntaje_presupuesto(presupuestos)
    p_co, dias = puntaje_constancia(dias_con_registro_30d)

    crudos = {
        "emergencia": (p_em, meses),
        "ahorro": (p_ah, tasa),
        "deuda": (p_de, ratio),
        "presupuesto": (p_pr, frac),
        "constancia": (p_co, dias),
    }

    peso_total = sum(PESOS[k] for k, (p, _) in crudos.items() if p is not None)
    componentes = []
    score = 0.0
    for clave, (puntaje, detalle) in crudos.items():
        disponible = puntaje is not None
        # peso efectivo re-normalizado a 100 entre los componentes con datos
        peso_efectivo = round(PESOS[clave] / peso_total * 100, 1) if disponible and peso_total else 0
        if disponible and peso_total:
            score += puntaje * PESOS[clave] / peso_total
        componentes.append({
            "clave": clave,
            "nombre": NOMBRES[clave],
            "puntaje": round(puntaje) if disponible else None,
            "peso": peso_efectivo,
            "detalle": detalle,
            "disponible": disponible,
        })

    score_final = int(round(_acotar(score)))

    # Consejos: los dos componentes con más puntos por ganar (brecha * peso).
    candidatos = sorted(
        (c for c in componentes if c["disponible"] and c["puntaje"] < 100),
        key=lambda c: (100 - c["puntaje"]) * c["peso"],
        reverse=True,
    )
    consejos = [_consejo(c["clave"], c["detalle"], saldo_liquido, gasto_mensual_promedio) for c in candidatos[:2]]
    if not consejos:
        consejos = ["¡Excelente! Mantén tus hábitos y considera invertir el excedente."]

    if score_final >= 80:
        nivel = "Excelente"
    elif score_final >= 60:
        nivel = "Buena"
    elif score_final >= 40:
        nivel = "Regular"
    else:
        nivel = "Por mejorar"

    return {"score": score_final, "nivel": nivel, "componentes": componentes, "consejos": consejos}
