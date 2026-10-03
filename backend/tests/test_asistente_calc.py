"""Cálculos del asistente. Los números esperados se verificaron a mano (ver comentarios)."""
from datetime import datetime

import pytest

from app import asistente_calc as c

HOY = datetime(2026, 10, 3, 12, 0)

# Escenario base:
#   disponible_real = 5.000.000 - 500.000 - 300.000 - 200.000 = 4.000.000
#   colchón         = 0,5 * 3.000.000 gasto mensual            = 1.500.000
#   usable          = 4.000.000 - 1.500.000                    = 2.500.000
#   capacidad       = 4.000.000 ingreso - 3.000.000 gasto      = 1.000.000
CTX = {
    "saldo_liquido": 5_000_000, "recurrentes_pendientes": 500_000, "cuotas_pendientes": 300_000,
    "aportes_metas": 200_000, "ingreso_mensual": 4_000_000, "gasto_mensual": 3_000_000,
}


def test_disponible_y_capacidad():
    assert c.disponible_real(CTX) == 4_000_000
    assert c.capacidad_ahorro(CTX) == 1_000_000
    assert c.capacidad_ahorro({"ingreso_mensual": 1, "gasto_mensual": 5}) == 0  # nunca negativa


def test_compra_ajustada_con_alternativas():
    r = c.simular_compra(4_000_000, CTX)
    assert r["veredicto"] == "ajustado"          # 4M <= disponible 4M pero > usable 2,5M
    assert r["disponible_real"] == 4_000_000
    assert r["colchon_sugerido"] == 1_500_000
    assert r["quedaria_disponible"] == 0
    assert r["meses_ahorrando"] == 2             # (4M - 2,5M) / 1M = 1,5 -> 2
    cuota12 = next(q for q in r["cuotas"] if q["plazo_meses"] == 12)
    assert cuota12["cuota_sin_interes"] == 333_333   # 4M / 12
    # 4M * 0,02 / (1 - 1,02^-12) = 4M * 0,0945596 = 378.238
    assert cuota12["cuota_con_interes"] == pytest.approx(378_238, abs=2)
    assert cuota12["intereses_totales"] == pytest.approx(378_238 * 12 - 4_000_000, abs=30)
    assert cuota12["cabe_en_tu_capacidad"] is True   # 378k <= 1M
    assert cuota12["pct_de_tu_capacidad"] == 38      # 378.238 / 1M = 37,8 %
    assert r["cuotas"][0]["plazo_meses"] == 3 and r["cuotas"][0]["cabe_en_tu_capacidad"] is False  # 1.37M > 1M


def test_compra_si_y_no():
    si = c.simular_compra(2_000_000, CTX)
    assert si["veredicto"] == "si" and si["meses_ahorrando"] == 0 and si["quedaria_disponible"] == 2_000_000
    no = c.simular_compra(5_000_000, CTX)
    assert no["veredicto"] == "no_aun"
    assert no["meses_ahorrando"] == 3            # (5M - 2,5M) / 1M = 2,5 -> 3
    assert no["quedaria_disponible"] == -1_000_000


def test_compra_sin_capacidad_de_ahorro():
    ctx = {**CTX, "ingreso_mensual": 3_000_000}   # ingreso = gasto -> capacidad 0
    r = c.simular_compra(6_000_000, ctx)
    assert r["meses_ahorrando"] is None
    assert all(q["cabe_en_tu_capacidad"] is False and q["pct_de_tu_capacidad"] is None for q in r["cuotas"])


def test_compra_invalida():
    with pytest.raises(ValueError):
        c.simular_compra(0, CTX)


def test_cuota_con_interes():
    assert c.cuota_con_interes(1_200_000, 12, 0) == 100_000
    # Un pago a 1 mes: capital + 2 % = 1.020.000
    assert c.cuota_con_interes(1_000_000, 1, 0.02) == pytest.approx(1_020_000)


def test_meses_entre():
    assert c.meses_entre(HOY, datetime(2027, 12, 31)) == 14   # oct-2026 -> dic-2027
    assert c.meses_entre(HOY, datetime(2026, 10, 30)) == 1    # mínimo 1


def test_plan_ahorro_viable_y_no_viable():
    p = c.plan_ahorro(12_000_000, 0, datetime(2027, 12, 31), 1_000_000, HOY)
    assert p["meses"] == 14 and p["aporte_mensual"] == 857_143   # 12M / 14 = 857.142,86 -> 857.143
    assert p["viable"] is True and p["pct_de_tu_capacidad"] == 86
    q = c.plan_ahorro(12_000_000, 0, datetime(2027, 12, 31), 500_000, HOY)
    assert q["viable"] is False and q["meses_con_tu_capacidad"] == 24   # 12M / 500k
    ya = c.plan_ahorro(1_000_000, 1_500_000, datetime(2027, 1, 31), 0, HOY)
    assert ya["faltante"] == 0 and ya["viable"] is True


def test_plan_deudas_sin_interes():
    # 1.200.000 al 0 %, cuota 100.000: sin extra tarda 12 meses.
    deudas = [{"id": "a", "nombre": "Préstamo", "saldo": 1_200_000, "tasa_mensual": 0, "cuota": 100_000}]
    p = c.plan_deudas(deudas, 6, capacidad=150_000)
    assert p["meses_sin_extra"] == 12
    assert p["extra_mensual"] == 100_000          # 6 meses * 200.000 = 1.200.000
    assert p["pago_total_mensual"] == 200_000 and p["meses_logrados"] == 6
    assert p["viable"] is True
    sin_cap = c.plan_deudas(deudas, 6, capacidad=50_000)
    assert sin_cap["viable"] is False
    igual = c.plan_deudas(deudas, 12, capacidad=0)
    assert igual["extra_mensual"] == 0 and igual["viable"] is True


def test_plan_deudas_con_interes_termina_a_tiempo():
    deudas = [
        {"id": "t", "nombre": "Tarjeta", "saldo": 2_000_000, "tasa_mensual": 2.0, "cuota": 100_000},
        {"id": "p", "nombre": "Préstamo", "saldo": 1_000_000, "tasa_mensual": 1.0, "cuota": 80_000},
    ]
    p = c.plan_deudas(deudas, 12, capacidad=10_000_000)
    assert p["meses_logrados"] <= 12
    assert p["extra_mensual"] > 0 and p["extra_mensual"] % 1000 == 0
    # Es el mínimo: 1.000 menos ya NO alcanza el plazo
    from app.estrategia_deudas import simular
    menos = simular(deudas, p["extra_mensual"] - 1000, "avalancha")
    assert menos["meses"] is None or menos["meses"] > 12
    assert p["orden"][0]["nombre"] == "Préstamo" or p["orden"][0]["nombre"] == "Tarjeta"


def test_plan_deudas_vacio():
    assert c.plan_deudas([], 12, 0)["sin_deudas"] is True


def _mov(dia, cat, monto, mes=10, anio=2026, tipo="expense", desc=""):
    return {"fecha": datetime(anio, mes, dia), "categoria": cat, "monto": monto, "tipo": tipo, "descripcion": desc}


def test_gasto_por_categoria():
    movs = [_mov(1, "Comida", 30_000), _mov(2, "Comida", 20_000), _mov(3, "Transporte", 50_000),
            _mov(4, "Sueldo", 3_000_000, tipo="income"), _mov(5, "Comida", 99_000, mes=9)]
    r = c.gasto_por_categoria(movs, 2026, 10)
    assert [f["categoria"] for f in r] == ["Comida", "Transporte"]
    assert r[0]["monto"] == 50_000 and r[0]["pct"] == 50 and r[1]["pct"] == 50   # 50k de 100k


def test_gastos_atipicos():
    previos = [_mov(d, "Comida", m, mes=9) for d, m in ((1, 20_000), (2, 25_000), (3, 30_000))]   # mediana 25.000
    actuales = [_mov(5, "Comida", 120_000, desc="Cena"), _mov(6, "Comida", 60_000), _mov(7, "Comida", 10_000)]
    r = c.gastos_atipicos(previos + actuales, 2026, 10)
    assert len(r) == 1 and r[0]["monto"] == 120_000 and r[0]["veces"] == 4.8   # 120k / 25k
    # sin historial suficiente no se marca nada
    assert c.gastos_atipicos(actuales, 2026, 10) == []


def test_suscripciones_anuales():
    r = c.suscripciones_anuales([
        {"nombre": "Netflix", "monto": 40_000, "tipo": "expense"},
        {"nombre": "Gimnasio", "monto": 30_000, "tipo": "expense"},
        {"nombre": "Sueldo", "monto": 5_000_000, "tipo": "income"},
        {"nombre": "Viejo", "monto": 10_000, "tipo": "expense", "activo": False},
    ])
    assert r["total_mensual"] == 70_000 and r["total_anual"] == 840_000
    assert r["items"][0]["nombre"] == "Netflix" and r["items"][0]["anual"] == 480_000
