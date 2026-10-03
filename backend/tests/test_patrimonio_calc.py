"""Cálculos puros de patrimonio. Cada caso tiene el resultado hecho a mano en el comentario."""
from datetime import datetime, timedelta

import pytest

from app import patrimonio_calc as c

T0 = datetime(2025, 1, 1)


def test_cdt_un_anio_es_capital_por_uno_mas_ea():
    # 10.000.000 al 12 % E.A. por 365 días = 10.000.000 * 1,12 = 11.200.000
    assert c.valor_cdt(10_000_000, 12, T0, T0 + timedelta(days=365)) == pytest.approx(11_200_000)


def test_cdt_dos_anios_compone():
    # 1,12^2 = 1,2544 -> 12.544.000
    assert c.valor_cdt(10_000_000, 12, T0, T0 + timedelta(days=730)) == pytest.approx(12_544_000)


def test_cdt_antes_del_inicio_vale_el_capital():
    assert c.valor_cdt(5_000_000, 10, T0, T0 - timedelta(days=10)) == 5_000_000


def test_cdt_despues_del_vencimiento_se_congela():
    venc = T0 + timedelta(days=365)
    en_venc = c.valor_cdt(1_000_000, 12, T0, venc, venc)
    assert c.valor_cdt(1_000_000, 12, T0, venc + timedelta(days=400), venc) == pytest.approx(en_venc)
    assert en_venc == pytest.approx(1_120_000)


def test_rentabilidad_posicion():
    # 120 unidades a costo 50 = 6.000; precio 62,5 -> 7.500; ganancia 1.500 = 25 %
    valor = c.valor_posicion(120, 62.5)
    r = c.rentabilidad(valor, 120 * 50)
    assert valor == 7500
    assert r["ganancia"] == 1500
    assert r["rentabilidad_pct"] == pytest.approx(25.0)


def test_rentabilidad_sin_costo_no_divide_por_cero():
    assert c.rentabilidad(100, 0)["rentabilidad_pct"] is None


def test_rentabilidad_negativa():
    # 800 sobre 1.000 = -20 %
    assert c.rentabilidad(800, 1000)["rentabilidad_pct"] == pytest.approx(-20.0)


def test_xirr_un_anio_diez_por_ciento():
    # -1000 hoy, +1100 a 365 días -> 10 %
    assert c.xirr([(T0, -1000), (T0 + timedelta(days=365), 1100)]) == pytest.approx(0.10, abs=1e-6)


def test_xirr_dos_anios():
    # -1000 -> 1210 en 730 días: 1,1^2 = 1,21 -> 10 % anual
    assert c.xirr([(T0, -1000), (T0 + timedelta(days=730), 1210)]) == pytest.approx(0.10, abs=1e-6)


def test_xirr_varios_flujos():
    # -1000 (t0), -1000 (365), +2310 (730): a 10 % -> -1000 - 909,09 + 1909,09 = 0
    flujos = [(T0, -1000), (T0 + timedelta(days=365), -1000), (T0 + timedelta(days=730), 2310)]
    assert c.xirr(flujos) == pytest.approx(0.10, abs=1e-6)


def test_xirr_perdida_es_negativa():
    # -1000 -> 900 en un año = -10 %
    assert c.xirr([(T0, -1000), (T0 + timedelta(days=365), 900)]) == pytest.approx(-0.10, abs=1e-6)


def test_xirr_sin_solucion():
    assert c.xirr([(T0, -1000)]) is None
    assert c.xirr([(T0, 100), (T0 + timedelta(days=30), 200)]) is None  # mismo signo
    assert c.xirr([(T0, -100), (T0, 200)]) is None  # ventana de cero días


def test_distribucion_porcentajes_y_orden():
    d = c.distribucion({"cdt": 300, "fondo": 600, "cripto": 100, "negativa": -50, "cero": 0})
    assert [f["clase"] for f in d] == ["fondo", "cdt", "cripto"]
    assert [round(f["pct"], 6) for f in d] == [60.0, 30.0, 10.0]
    assert sum(f["pct"] for f in d) == pytest.approx(100.0)


def test_distribucion_vacia():
    assert c.distribucion({}) == []
    assert c.distribucion({"a": 0}) == []


def test_patrimonio_neto():
    assert c.patrimonio_neto(100, 50, 30) == 120
    assert c.patrimonio_neto(0, 10, 25) == -15
