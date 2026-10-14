"""Cálculos puros de Inversiones con casos sintéticos verificados a mano."""
from datetime import datetime, timedelta

import pytest

from app import inversiones_calc as ic

D0 = datetime(2025, 1, 1)


def tx(tipo, dias, **kw):
    return {"tipo": tipo, "fecha": D0 + timedelta(days=dias), **kw}


def test_promedio_ponderado_y_venta_parcial():
    txs = [tx("compra", 0, cantidad=10, precio=100, comision=10),   # costo 1010
           tx("compra", 10, cantidad=10, precio=120),               # costo 1200 -> 2210 / 20 = 110,5
           tx("venta", 20, cantidad=5, precio=130, comision=5)]     # recibe 645; costo 552,5
    r = ic.resumen_transacciones(txs)
    assert r["cantidad"] == 15
    assert r["costo_promedio"] == pytest.approx(110.5)
    assert r["costo_total"] == pytest.approx(2210 - 552.5)
    assert r["realizada"] == pytest.approx(645 - 552.5)
    assert r["comisiones"] == 15


def test_venta_total_reinicia_y_no_vende_de_mas():
    r = ic.resumen_transacciones([tx("compra", 0, cantidad=2, precio=50), tx("venta", 1, cantidad=5, precio=60)])
    assert r["cantidad"] == 0 and r["costo_total"] == 0
    assert r["realizada"] == pytest.approx(2 * 60 - 100)  # solo vendió 2


def test_dividendos_y_rentabilidad_total():
    txs = [tx("compra", 0, cantidad=10, precio=100), tx("dividendo", 30, monto=50)]
    r = ic.resumen_transacciones(txs)
    assert r["dividendos"] == 50
    v = ic.valor_y_ganancia(r["cantidad"], 110, r["costo_total"])
    assert v["valor"] == 1100 and v["no_realizada"] == 100 and v["no_realizada_pct"] == pytest.approx(10)
    t = ic.rentabilidad_total(v["valor"], r["costo_total"], r["realizada"], r["dividendos"], r["aportado"])
    assert t["total"] == 150 and t["total_pct"] == pytest.approx(15)


def test_ticker_sin_precio_no_inventa_valor():
    v = ic.valor_y_ganancia(10, None, 1000)
    assert v == {"valor": None, "no_realizada": None, "no_realizada_pct": None}


def test_tir_un_anio_y_casos_borde():
    hoy = D0 + timedelta(days=365)
    f = ic.flujos_tir([tx("compra", 0, cantidad=10, precio=100)])
    assert ic.tir(f, 1100, hoy) == pytest.approx(10.0, abs=0.05)
    assert ic.tir([], 1000, hoy) is None                       # sin flujos
    assert ic.tir(f, 1100, D0 + timedelta(days=10)) is None    # muy poca historia
    assert ic.tir(f, 0, hoy) is None                           # todos negativos: sin solución
    f2 = ic.flujos_tir([tx("compra", 0, cantidad=10, precio=100), tx("aporte", 180, monto=500)])
    assert ic.tir(f2, 1700, hoy) is not None


def test_dietz_periodo():
    # 1000 al inicio, aporte de 100 a mitad, termina en 1200: (1200-1000-100)/(1000+50)
    r = ic.rentabilidad_periodo(1000, 1200, [(0.5, 100)])
    assert r == pytest.approx(100 / 1050 * 100)
    assert ic.rentabilidad_periodo(0, 0, []) is None


def test_moneda():
    fx = ic.FXManual({"USD": 4000})
    assert ic.convertir(10, "USD", "COP", fx) == 40000
    assert ic.convertir(10, "COP", "COP", fx) == 10
    assert ic.convertir(10, "EUR", "COP", fx) is None          # sin tasa: no se suma como COP
    assert ic.convertir(10, "EUR", "COP", fx, tipo_cambio=4500) == 45000


def test_agrupar_y_concentracion():
    filas = [{"nombre": "A", "tipo": "accion", "valor_cop": 600}, {"nombre": "B", "tipo": "etf", "valor_cop": 400},
             {"nombre": "C", "tipo": "etf", "valor_cop": None}]
    assert ic.mayor_concentracion(filas) == {"nombre": "A", "pct": 60.0, "valor": 600}
    d = ic.agrupar(filas, "tipo")
    assert [x["clase"] for x in d] == ["accion", "etf"]
    assert ic.mayor_concentracion([]) is None


def test_bienes():
    hoy = datetime(2026, 1, 1)
    assert ic.valor_vehiculo_estimado(100, hoy - timedelta(days=365), hoy, 10) == pytest.approx(90)
    e = ic.extras_bien("inmueble", 300, 200, hoy - timedelta(days=200), 1, hoy)
    assert e["variacion_tipo"] == "valorizacion" and e["variacion_pct"] == pytest.approx(50)
    assert e["sugerir_actualizar"] is True and e["arriendo_anual_pct"] == pytest.approx(4.0)
    assert ic.hace_cuanto(hoy - timedelta(days=3), hoy) == "hace 3 días"
