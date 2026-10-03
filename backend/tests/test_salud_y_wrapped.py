"""Pruebas de las funciones puras de salud financiera y del resumen Wrapped."""
from datetime import date, datetime

from app.salud_financiera import calcular_salud_financiera, puntaje_ahorro, puntaje_deuda, puntaje_emergencia
from app.wrapped import calcular_wrapped, mejor_racha


def _salud(**kw):
    base = dict(
        saldo_liquido=0, gasto_mensual_promedio=1_000_000, ingresos_30d=0, gastos_30d=0,
        cuotas_deuda_mensual=0, presupuestos=[], dias_con_registro_30d=0,
    )
    base.update(kw)
    return calcular_salud_financiera(**base)


def test_emergencia_seis_meses_es_puntaje_completo():
    assert puntaje_emergencia(6_000_000, 1_000_000)[0] == 100
    assert puntaje_emergencia(3_000_000, 1_000_000) == (50.0, 3.0)
    assert puntaje_emergencia(-5, 1_000_000)[0] == 0
    assert puntaje_emergencia(1, 0) == (None, None)  # sin gastos no hay base


def test_ahorro_y_deuda():
    assert puntaje_ahorro(1_000_000, 800_000)[0] == 100   # 20%
    assert puntaje_ahorro(1_000_000, 1_200_000)[0] == 0   # gasta de más
    assert puntaje_ahorro(0, 0) == (None, None)
    assert puntaje_deuda(0, 1_000_000)[0] == 100
    assert puntaje_deuda(400_000, 1_000_000)[0] == 0      # 40% del ingreso
    assert puntaje_deuda(200_000, 1_000_000)[0] == 50
    assert puntaje_deuda(100, 0)[0] == 0


def test_persona_ideal_saca_100():
    r = _salud(saldo_liquido=7_000_000, ingresos_30d=3_000_000, gastos_30d=1_000_000,
               presupuestos=[(500_000, 400_000)], dias_con_registro_30d=25)
    assert r["score"] == 100
    assert r["nivel"] == "Excelente"
    assert len(r["consejos"]) == 1  # mensaje de felicitación


def test_componentes_sin_datos_se_excluyen_y_pesos_se_renormalizan():
    r = _salud(saldo_liquido=1_000_000, ingresos_30d=2_000_000, gastos_30d=1_600_000, dias_con_registro_30d=10)
    comp = {c["clave"]: c for c in r["componentes"]}
    assert comp["presupuesto"]["disponible"] is False and comp["presupuesto"]["puntaje"] is None
    assert round(sum(c["peso"] for c in r["componentes"]), 0) == 100
    assert 0 <= r["score"] <= 100


def test_score_siempre_en_rango_y_consejos_apuntan_a_lo_mas_debil():
    r = _salud(saldo_liquido=100_000, ingresos_30d=1_000_000, gastos_30d=1_500_000,
               cuotas_deuda_mensual=500_000, presupuestos=[(100, 500)], dias_con_registro_30d=1)
    assert 0 <= r["score"] < 40
    assert r["nivel"] == "Por mejorar"
    assert 1 <= len(r["consejos"]) <= 2
    assert all(isinstance(c, str) and c for c in r["consejos"])


def test_nunca_divide_por_cero_con_todo_en_cero():
    r = _salud(gasto_mensual_promedio=0)
    assert 0 <= r["score"] <= 100


def test_mejor_racha():
    d = lambda n: date(2026, 9, n)  # noqa: E731
    assert mejor_racha([]) == 0
    assert mejor_racha([d(1), d(1), d(2), d(3), d(10), d(11)]) == 3
    assert mejor_racha([d(5), d(7)]) == 1


def test_wrapped_calcula_todo_y_compara_con_mes_anterior():
    mes = [
        {"tipo": "income", "monto": 3_000_000, "categoria": "Ingresos", "fecha": datetime(2026, 9, 1)},
        {"tipo": "expense", "monto": 600_000, "categoria": "Mercado", "fecha": datetime(2026, 9, 2)},
        {"tipo": "expense", "monto": 200_000, "categoria": "Transporte", "fecha": datetime(2026, 9, 3)},
        {"tipo": "expense", "monto": 200_000, "categoria": "Mercado", "fecha": datetime(2026, 9, 9)},
    ]
    ant = [{"tipo": "expense", "monto": 500_000, "categoria": "Mercado", "fecha": datetime(2026, 8, 5)}]
    w = calcular_wrapped("2026-09", mes, ant)
    assert w["gasto_total"] == 1_000_000
    assert w["ahorro"] == 2_000_000
    assert w["categoria_top"] == {"categoria": "Mercado", "monto": 800_000}
    assert w["mejor_racha"] == 3
    assert w["variacion_gasto_pct"] == 100.0


def test_wrapped_mes_vacio_no_revienta():
    w = calcular_wrapped("2026-09", [], [])
    assert w["categoria_top"] is None and w["variacion_gasto_pct"] is None
    assert w["gasto_total"] == 0 and w["mejor_racha"] == 0
