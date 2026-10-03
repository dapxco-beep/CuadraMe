"""Cálculo puro de gastos compartidos: nunca se pierde ni se crea dinero."""
import pytest

from app.division import (
    DivisionInvalida, calcular_saldos, dividir, saldos_con, simplificar_deudas,
)


def _p(*ids, valores=None):
    return [{"id": i, "valor": (valores[k] if valores else 0)} for k, i in enumerate(ids)]


def test_iguales_reparte_el_resto_sin_perder_pesos():
    r = dividir(100000, "iguales", _p("yo", "a", "b"))
    assert sum(r.values()) == 100000
    assert sorted(r.values()) == [33333, 33333, 33334]


def test_iguales_con_centavos():
    r = dividir(10, "iguales", _p("yo", "a", "b"), decimales=2)
    assert round(sum(r.values()), 2) == 10.0
    assert sorted(r.values()) == [3.33, 3.33, 3.34]


def test_partes():
    r = dividir(90000, "partes", _p("yo", "a", valores=[2, 1]))
    assert r == {"yo": 60000, "a": 30000}


def test_partes_con_residuo_suma_exacta():
    r = dividir(100, "partes", _p("a", "b", "c", valores=[1, 1, 1]))
    assert sum(r.values()) == 100


def test_porcentajes_y_validacion():
    r = dividir(200000, "porcentajes", _p("yo", "a", valores=[25, 75]))
    assert r == {"yo": 50000, "a": 150000}
    with pytest.raises(DivisionInvalida, match="100"):
        dividir(200000, "porcentajes", _p("yo", "a", valores=[25, 70]))


def test_porcentajes_decimales_no_pierden_dinero():
    r = dividir(1000, "porcentajes", _p("a", "b", "c", valores=[33.33, 33.33, 33.34]))
    assert sum(r.values()) == 1000


def test_montos_exactos_deben_sumar_el_total():
    assert dividir(100, "montos", _p("yo", "a", valores=[40, 60])) == {"yo": 40, "a": 60}
    with pytest.raises(DivisionInvalida, match="no suman"):
        dividir(100, "montos", _p("yo", "a", valores=[40, 50]))


def test_entradas_invalidas():
    with pytest.raises(DivisionInvalida):
        dividir(100, "iguales", [])
    with pytest.raises(DivisionInvalida):
        dividir(0, "iguales", _p("yo"))
    with pytest.raises(DivisionInvalida):
        dividir(100, "iguales", _p("yo", "yo"))
    with pytest.raises(DivisionInvalida):
        dividir(100, "partes", _p("yo", "a", valores=[0, 0]))
    with pytest.raises(DivisionInvalida):
        dividir(100, "inventado", _p("yo"))
    with pytest.raises(DivisionInvalida):
        dividir(100, "partes", _p("yo", "a", valores=[-1, 2]))


def test_el_participante_con_cero_partes_queda_en_cero():
    r = dividir(100, "partes", _p("yo", "a", valores=[0, 1]))
    assert r == {"yo": 0, "a": 100}


def test_saldos_yo_pague_y_me_pagan():
    g = [{"pagador": "yo", "partes": {"yo": 40000, "ana": 30000, "beto": 30000}}]
    assert saldos_con("yo", g, []) == {"ana": 30000, "beto": 30000}
    liq = [{"de": "ana", "a": "yo", "monto": 30000}]
    assert saldos_con("yo", g, liq) == {"beto": 30000}


def test_saldos_otro_pago_yo_debo():
    g = [{"pagador": "ana", "partes": {"yo": 20000, "ana": 20000}}]
    assert saldos_con("yo", g, []) == {"ana": -20000}
    assert saldos_con("yo", g, [{"de": "yo", "a": "ana", "monto": 5000}]) == {"ana": -15000}


def test_saldos_netos_suman_cero_y_se_simplifica():
    # Ana pagó 90 (3 iguales: yo, ana, beto); yo pagué 60 (yo y beto).
    g = [
        {"pagador": "ana", "partes": {"yo": 30, "ana": 30, "beto": 30}},
        {"pagador": "yo", "partes": {"yo": 30, "beto": 30}},
    ]
    neto = calcular_saldos(g, [])
    assert sum(neto.values()) == 0
    assert neto == {"ana": 60, "yo": 0, "beto": -60}
    pagos = simplificar_deudas(neto)
    assert pagos == [{"de": "beto", "a": "ana", "monto": 60}]  # yo ya no pinto nada


def test_simplificar_reduce_pagos_y_cuadra():
    neto = {"a": 70, "b": 30, "c": -50, "d": -40, "e": -10}
    pagos = simplificar_deudas(neto)
    assert len(pagos) <= len(neto) - 1
    recibido = {k: 0 for k in neto}
    for p in pagos:
        recibido[p["a"]] += p["monto"]
        recibido[p["de"]] -= p["monto"]
    assert recibido == neto
    with pytest.raises(DivisionInvalida):
        simplificar_deudas({"a": 10, "b": -5})
