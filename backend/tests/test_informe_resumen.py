"""Informes > Resumen: flujo neto, ingresos por fuente, presupuesto vs real y hallazgos.
Todas las cifras están calculadas a mano (hoy = jueves 15-oct-2026)."""
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'resumen.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import informe as inf  # noqa: E402
from app import informe_resumen as res  # noqa: E402
from app import limites  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

HOY = datetime(2026, 10, 15, 10, 0)


def _m(i, fecha, tipo, monto, cat, desc=""):
    return {"id": i, "fecha": fecha, "tipo": tipo, "monto": monto, "categoria": cat, "descripcion": desc or cat}


MOVS = [
    # Octubre (1 al 15): ingresos 1.200.000, gastos 200.000
    _m(1, datetime(2026, 10, 1), "income", 1_000_000, "Sueldo", "Sueldo Empresa"),
    _m(2, datetime(2026, 10, 5), "income", 200_000, "Ventas", "Venta Mercado Libre"),
    _m(3, datetime(2026, 10, 2), "expense", 100_000, "Comida", "Éxito"),
    _m(4, datetime(2026, 10, 9), "expense", 50_000, "Comida", "Éxito"),
    _m(5, datetime(2026, 10, 10), "expense", 50_000, "Transporte", "Uber"),
    # Septiembre: ingresos 900.000, gastos 500.000
    _m(6, datetime(2026, 9, 1), "income", 900_000, "Sueldo", "Sueldo Empresa"),
    _m(7, datetime(2026, 9, 3), "expense", 80_000, "Comida", "Éxito"),
    _m(8, datetime(2026, 9, 5), "expense", 20_000, "Transporte", "Uber"),
    _m(9, datetime(2026, 9, 20), "expense", 400_000, "Comida", "Éxito"),
    _m(10, datetime(2026, 9, 21), "transfer", 999_999, "Transferencia"),  # no cuenta nunca
]
PRES = [
    {"categoria": "Comida", "limite": 300_000, "periodo": "monthly", "alerta_pct": 80, "sobre_ajuste": 0, "activo": True},
    {"categoria": "Transporte", "limite": 40_000, "periodo": "monthly", "alerta_pct": 80, "sobre_ajuste": 0, "activo": True},
    {"categoria": "Ocio", "limite": 100_000, "periodo": "monthly", "alerta_pct": 80, "sobre_ajuste": 0, "activo": False},
]


# ── Flujo neto ──────────────────────────────────────────────────────────────────────────────
def test_agrupacion_automatica_segun_largo_del_rango():
    assert res.agrupacion_auto(inf.rango_periodo("este_mes", HOY)) == "dia"          # 15 días
    assert res.agrupacion_auto(inf.rango_periodo("3_meses", HOY)) == "semana"         # 1-ago a 15-oct: 76 días
    assert res.agrupacion_auto(inf.rango_periodo("anio", HOY)) == "mes"              # 288 días


def test_flujo_por_dia_con_huecos_y_acumulado():
    f = res.flujo_neto(MOVS, inf.rango_periodo("este_mes", HOY))
    assert f["agrupar"] == "dia" and len(f["puntos"]) == 15
    p = {x["clave"]: x for x in f["puntos"]}
    assert p["2026-10-01"]["neto"] == 1_000_000
    assert p["2026-10-02"]["neto"] == -100_000
    assert p["2026-10-03"]["con_datos"] is False and p["2026-10-03"]["neto"] is None   # hueco, no cero
    assert p["2026-10-05"]["neto"] == 200_000
    assert p["2026-10-15"]["acumulado"] == 1_000_000                                   # 1,2M de ingresos − 0,2M de gastos
    assert (f["positivos"], f["negativos"]) == (2, 3)
    assert f["mejor"] == "2026-10-01" and f["peor"] == "2026-10-02"
    # el acumulado final es exactamente ingresos − gastos del periodo
    assert f["puntos"][-1]["acumulado"] == 1_200_000 - 200_000


def test_flujo_por_semana_recorta_a_lunes_y_al_rango():
    f = res.flujo_neto(MOVS, inf.rango_periodo("este_mes", HOY), "semana")
    # 1-oct es jueves: 1-4, 5-11 y 12-15
    assert [(p["desde"], p["hasta"]) for p in f["puntos"]] == [
        ("2026-10-01", "2026-10-04"), ("2026-10-05", "2026-10-11"), ("2026-10-12", "2026-10-15")]
    assert [p["neto"] for p in f["puntos"]] == [900_000, 100_000, None]               # (1M−100k), (200k−50k−50k)
    assert f["puntos"][-1]["acumulado"] == 1_000_000


def test_flujo_por_mes_y_traslados_no_suman():
    r = inf.rango_periodo("rango", HOY, "2026-09-01", "2026-10-15")
    f = res.flujo_neto(MOVS, r, "mes")
    assert [p["clave"] for p in f["puntos"]] == ["2026-09-01", "2026-10-01"]
    assert [p["neto"] for p in f["puntos"]] == [900_000 - 500_000, 1_200_000 - 200_000]
    assert sum(p["ingresos"] for p in f["puntos"]) == 2_100_000                        # el traslado de 999.999 no entra


def test_flujo_sin_datos_no_inventa():
    f = res.flujo_neto([], inf.rango_periodo("este_mes", HOY))
    assert f["hay_datos"] is False and all(p["neto"] is None for p in f["puntos"])
    assert f["mejor"] is None and f["peor"] is None


def test_flujo_muy_largo_se_agrupa_mas_grueso():
    r = inf.rango_periodo("rango", HOY, "2021-10-16", "2026-10-15")                    # 5 años
    f = res.flujo_neto(MOVS, r, "dia")
    assert f["agrupar"] == "mes" and len(f["puntos"]) <= res.MAX_PUNTOS


def test_meses_de_la_serie_minimo_6_maximo_24():
    assert res.meses_de_la_serie(inf.rango_periodo("este_mes", HOY)) == 6
    assert res.meses_de_la_serie(inf.rango_periodo("anio", HOY)) == 10                 # ene–oct
    assert res.meses_de_la_serie(inf.rango_periodo("rango", HOY, "2022-01-01", "2026-10-15")) == 24


# ── Ingresos por fuente ─────────────────────────────────────────────────────────────────────
def test_ingresos_por_fuente_con_comparacion():
    r = inf.rango_periodo("este_mes", HOY)
    out = res.ingresos_por_fuente(MOVS, r, inf.periodo_anterior(r))
    assert out["total"] == 1_200_000 and out["otras"] is None
    f0, f1 = out["fuentes"]
    assert (f0["nombre"], f0["monto"], f0["pct"]) == ("Sueldo Empresa", 1_000_000, 83.3)
    assert f0["anterior"] == 900_000 and f0["variacion_pct"] == 11.1                   # +11,1 %
    assert (f1["nombre"], f1["monto"], f1["pct"], f1["variacion_pct"]) == ("Venta Mercado Libre", 200_000, 16.7, None)
    assert round(sum(f["pct"] for f in out["fuentes"]), 1) == 100.0


def test_fuentes_sobrantes_van_a_otras_y_la_suma_cuadra():
    movs = [_m(i, datetime(2026, 10, 1 + i), "income", 10_000 * (i + 1), "Otros", f"Fuente {i}") for i in range(8)]
    r = inf.rango_periodo("este_mes", HOY)
    out = res.ingresos_por_fuente(movs, r, inf.periodo_anterior(r), maximo=6)
    assert len(out["fuentes"]) == 6 and out["otras"]["cantidad"] == 2
    assert sum(f["monto"] for f in out["fuentes"]) + out["otras"]["monto"] == out["total"] == 360_000
    assert res.ingresos_por_fuente([], r, inf.periodo_anterior(r))["hay_datos"] is False


# ── Presupuesto vs real ─────────────────────────────────────────────────────────────────────
def test_presupuesto_vs_real_mes_completo():
    r = inf.rango_periodo("mes_pasado", HOY)                                           # septiembre completo
    out = res.presupuesto_vs_real(MOVS, PRES, r, HOY)
    assert out["meses_equivalentes"] == 1.0
    comida, transp = out["categorias"]
    assert (comida["categoria"], comida["presupuesto"], comida["gastado"], comida["disponible"]) == ("Comida", 300_000, 480_000, -180_000)
    assert comida["pct"] == 160.0 and comida["estado"] == "excedido"
    assert (transp["gastado"], transp["pct"], transp["estado"]) == (20_000, 50.0, "dentro")
    assert out["presupuesto_total"] == 340_000 and out["gastado_total"] == 500_000 and out["pct_total"] == 147.1
    assert all(c["categoria"] != "Ocio" for c in out["categorias"])                    # presupuesto inactivo no cuenta


def test_presupuesto_se_reparte_por_dias_en_rango_parcial():
    r = inf.rango_periodo("este_mes", HOY)                                             # 15 de 31 días
    out = res.presupuesto_vs_real(MOVS, PRES, r, HOY)
    assert out["meses_equivalentes"] == pytest.approx(15 / 31, abs=0.01)
    comida = next(c for c in out["categorias"] if c["categoria"] == "Comida")
    assert comida["presupuesto"] == round(300_000 * 15 / 31) == 145_161 and comida["gastado"] == 150_000
    assert comida["estado"] == "excedido"


def test_presupuesto_varios_meses_y_periodos_no_mensuales():
    r = inf.rango_periodo("rango", HOY, "2026-08-01", "2026-09-30")                    # dos meses completos
    assert res._fraccion_de_meses(r) == pytest.approx(2.0)
    quincenal = [{"categoria": "Comida", "limite": 100_000, "periodo": "biweekly", "alerta_pct": 80, "sobre_ajuste": 0, "activo": True}]
    assert res.presupuesto_vs_real(MOVS, quincenal, inf.rango_periodo("mes_pasado", HOY), HOY)["categorias"][0]["presupuesto"] == 200_000


def test_estado_cerca_y_gasto_sin_presupuesto_y_sobre_ajuste():
    pres = [{"categoria": "Comida", "limite": 190_000, "periodo": "monthly", "alerta_pct": 75, "sobre_ajuste": 10_000, "activo": True}]
    r = inf.rango_periodo("mes", HOY, mes="2026-10")
    out = res.presupuesto_vs_real(MOVS, pres, r, HOY)                                  # octubre sí incluye el mes en curso
    c = out["categorias"][0]
    assert c["presupuesto"] == round(190_000 * 15 / 31) + 10_000 == 101_935
    assert out["gasto_sin_presupuesto"] == 50_000                                      # Transporte no tiene presupuesto
    out = res.presupuesto_vs_real(MOVS, pres, inf.rango_periodo("mes_pasado", HOY), HOY)
    assert out["categorias"][0]["presupuesto"] == 190_000                              # septiembre: sin sobre_ajuste


def test_sin_presupuestos():
    out = res.presupuesto_vs_real(MOVS, [], inf.rango_periodo("este_mes", HOY), HOY)
    assert out["hay_presupuestos"] is False and out["categorias"] == [] and out["pct_total"] is None


# ── Hallazgos ───────────────────────────────────────────────────────────────────────────────
def _hallazgos(rango, pres=PRES, max_n=5):
    ant = inf.periodo_anterior(rango)
    base = inf.ingresos_gastos(MOVS, rango, ant, 6)
    informe = inf.informe_gasto(MOVS, rango, ant)
    return res.hallazgos(base, informe, res.presupuesto_vs_real(MOVS, pres, rango, HOY), rango["etiqueta"], max_n)


def test_hallazgos_son_verificables_y_ordenados():
    h = {x["id"]: x for x in _hallazgos(inf.rango_periodo("este_mes", HOY), max_n=20)}
    assert h["flujo"]["tono"] == "bueno" and h["flujo"]["datos"] == {"ingresos": 1_200_000, "gastos": 200_000, "neto": 1_000_000}
    assert "$1.200.000" in h["flujo"]["texto"] and "$1.000.000" in h["flujo"]["texto"]
    # tasa de ahorro: oct 83,3 % contra 1–15 de sep (ing 900k, gasto 80k+20k = 100k → 88,9 %)
    assert h["tasa"]["datos"]["puntos"] == pytest.approx(83.3 - 88.9, abs=0.05) and h["tasa"]["tono"] == "atento"
    assert h["peso_categoria"]["datos"]["categoria"] == "Comida"                       # 150k de 200k = 75 %
    lista = _hallazgos(inf.rango_periodo("este_mes", HOY))
    assert [x["prioridad"] for x in lista] == sorted(x["prioridad"] for x in lista) and len(lista) <= 5
    assert all(x["enlace"].startswith("/") and x["titulo"] and x["texto"] for x in lista)


def test_hallazgo_presupuesto_excedido_en_septiembre():
    h = {x["id"] for x in _hallazgos(inf.rango_periodo("mes_pasado", HOY))}
    assert "presupuesto_excedido" in h


def test_sin_movimientos_no_hay_hallazgos_ni_texto_vacio():
    r = inf.rango_periodo("rango", HOY, "2025-01-01", "2025-01-31")
    base = inf.ingresos_gastos([], r, inf.periodo_anterior(r), 6)
    assert res.hallazgos(base, inf.informe_gasto([], r), res.presupuesto_vs_real([], [], r, HOY), r["etiqueta"]) == []


def test_frases_con_la_etiqueta_del_periodo_se_leen_bien():
    assert res.en_periodo("octubre de 2026") == "en octubre de 2026"
    assert res.en_periodo("del 1 de junio al 25 de noviembre de 2026") == "en el periodo del 1 de junio al 25 de noviembre de 2026"
    assert res.en_periodo("los últimos 3 meses") == "durante los últimos 3 meses"
    assert res.en_periodo("el año 2026") == "durante el año 2026"


# ── Tasa de ahorro ──────────────────────────────────────────────────────────────────────────
def test_resumen_tasa_pondera_por_ingresos_y_omite_meses_sin_ingresos():
    meses = [
        {"mes": "2026-07", "etiqueta_larga": "julio de 2026", "ingresos": 1_000_000, "balance": 500_000, "tasa_ahorro": 50.0},
        {"mes": "2026-08", "etiqueta_larga": "agosto de 2026", "ingresos": 3_000_000, "balance": 300_000, "tasa_ahorro": 10.0},
        {"mes": "2026-09", "etiqueta_larga": "septiembre de 2026", "ingresos": 0, "balance": -100_000, "tasa_ahorro": None},
    ]
    r = res.resumen_tasa(meses)
    assert r["promedio"] == 20.0                       # (500k + 300k) / (1M + 3M), no el promedio simple (30 %)
    assert r["mejor"]["mes"] == "2026-07" and r["peor"]["mes"] == "2026-08" and r["meses_con_tasa"] == 2
    assert res.resumen_tasa([m for m in meses if m["tasa_ahorro"] is None]) == {"promedio": None, "mejor": None, "peor": None, "meses_con_tasa": 0}


# ── API de punta a punta ────────────────────────────────────────────────────────────────────
client = TestClient(app)


@pytest.fixture(autouse=True)
def _usuario():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="res-1", email="r@test.com", nombre="R")
    limites._eventos.clear()
    yield


def _sembrar():
    if client.get("/cuentas").json():
        return
    c = client.post("/cuentas", json={"nombre": "Ahorros", "saldo": 0, "tipo": "ahorro"}).json()
    hoy = ahora_co()
    a, m = inf.sumar_meses(hoy.year, hoy.month, -2)
    f = datetime(a, m, 10, 12).isoformat()
    for desc, monto, tipo, cat in [("Éxito", 100_000, "expense", "Comida"), ("Uber", 40_000, "expense", "Transporte"),
                                   ("Pago tarjeta Visa", 900_000, "expense", "Otros"),
                                   ("Sueldo Empresa", 2_000_000, "income", "Sueldo")]:
        client.post("/movimientos", json={"cuenta_id": c["id"], "descripcion": desc, "monto": monto, "tipo": tipo,
                                          "categoria": cat, "fecha": f})
    client.post("/presupuestos", json={"categoria": "Comida", "limite": 80_000, "periodo": "monthly", "alerta_pct": 80})


def _clave():
    hoy = ahora_co()
    return "%d-%02d" % inf.sumar_meses(hoy.year, hoy.month, -2)


def test_api_resumen_una_sola_lectura():
    _sembrar()
    r = client.get("/informes/resumen", params={"periodo": "mes", "mes": _clave()}).json()
    assert (r["ingresos"], r["gastos"], r["balance"], r["tasa_ahorro"]) == (2_000_000, 140_000, 1_860_000, 93.0)   # el pago de tarjeta no es gasto
    assert r["flujo"]["agrupar"] in ("dia", "semana", "mes") and r["flujo"]["puntos"][-1]["acumulado"] == 1_860_000
    assert r["fuentes"]["fuentes"][0]["nombre"] == "Sueldo Empresa" and r["fuentes"]["fuentes"][0]["pct"] == 100.0
    assert r["presupuesto"]["categorias"][0]["estado"] == "excedido"                                              # 100k de 80k
    assert len(r["meses"]) == 6 and r["meses"][-1]["mes"] == "%d-%02d" % tuple(int(x) for x in _clave().split("-"))
    assert "flujo" in {h["id"] for h in r["hallazgos"]}
    assert r["tasa_serie"]["meses_con_tasa"] == 1 and r["tasa_serie"]["promedio"] == 93.0


def test_api_resumen_periodo_vacio_y_rango_invalido():
    _sembrar()
    r = client.get("/informes/resumen", params={"periodo": "este_mes"}).json()
    assert r["flujo"]["hay_datos"] is False and r["fuentes"]["hay_datos"] is False and r["hallazgos"] == []
    assert client.get("/informes/resumen", params={"periodo": "rango", "desde": "2026-10-10", "hasta": "2026-10-01"}).status_code == 422
    assert client.get("/informes/resumen", params={"agrupar": "hora"}).status_code == 422


def test_api_movimientos_de_una_fuente_de_ingreso():
    _sembrar()
    m = client.get("/informes/gasto/movimientos", params={"tipo": "ingreso", "fuente": "sueldo empresa", "periodo": "mes", "mes": _clave()}).json()
    assert m["total"] == 2_000_000 and m["cantidad"] == 1
    assert client.get("/informes/gasto/movimientos", params={"tipo": "ingreso", "periodo": "mes", "mes": _clave()}).status_code == 422
    gasto = client.get("/informes/gasto/movimientos", params={"categoria": "Comida", "periodo": "mes", "mes": _clave()}).json()
    assert gasto["total"] == 100_000                                                   # sin «tipo»: sigue siendo gasto
