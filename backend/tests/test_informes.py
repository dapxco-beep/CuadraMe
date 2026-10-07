"""Informe de gasto, meses con datos, gasto diario y preguntas del asistente.
Casos numéricos calculados a mano."""
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'informes.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import asistente as ia  # noqa: E402
from app import asistente_consultas as cons  # noqa: E402
from app import informe as inf  # noqa: E402
from app import limites  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

HOY = datetime(2026, 10, 15, 10, 0)


def _m(i, fecha, tipo, monto, cat, desc=""):
    return {"id": i, "fecha": fecha, "tipo": tipo, "monto": monto, "categoria": cat, "descripcion": desc or cat}


MOVS = [
    _m(1, datetime(2026, 10, 2), "expense", 100_000, "Comida", "Éxito"),
    _m(2, datetime(2026, 10, 9), "expense", 50_000, "Comida", "exito "),
    _m(3, datetime(2026, 10, 10), "expense", 50_000, "Transporte", "Uber"),
    _m(4, datetime(2026, 10, 1), "income", 1_000_000, "Sueldo"),
    _m(5, datetime(2026, 9, 3), "expense", 80_000, "Comida", "Éxito"),
    _m(6, datetime(2026, 9, 5), "expense", 20_000, "Transporte", "Uber"),
    _m(7, datetime(2026, 9, 20), "expense", 400_000, "Comida", "Éxito"),
    _m(8, datetime(2026, 9, 21), "transfer", 999_999, "Transferencia"),
]


def test_rangos_de_periodo():
    r = inf.rango_periodo("este_mes", HOY)
    assert r["desde"] == datetime(2026, 10, 1) and r["hasta"] == datetime(2026, 10, 16)
    r = inf.rango_periodo("mes_pasado", HOY)
    assert r["desde"] == datetime(2026, 9, 1) and r["hasta"] == datetime(2026, 10, 1)
    assert inf.rango_periodo("3_meses", HOY)["desde"] == datetime(2026, 8, 1)
    assert inf.rango_periodo("anio", HOY)["desde"] == datetime(2026, 1, 1)
    r = inf.rango_periodo("rango", HOY, "2026-09-10", "2026-09-12")
    assert r["hasta"] == datetime(2026, 9, 13)           # hasta es inclusivo para el usuario
    with pytest.raises(inf.PeriodoInvalido):
        inf.rango_periodo("rango", HOY, "2026-09-12", "2026-09-10")
    with pytest.raises(inf.PeriodoInvalido):
        inf.rango_periodo("mes", HOY, mes="2026-13")


def test_periodo_anterior_mismo_tramo():
    r = inf.rango_periodo("este_mes", HOY)
    a = inf.periodo_anterior(r)
    assert a["desde"] == datetime(2026, 9, 1) and a["hasta"] == datetime(2026, 9, 16)   # 15 días, no septiembre completo
    r3 = inf.rango_periodo("rango", HOY, "2026-10-10", "2026-10-14")                  # 5 días
    a3 = inf.periodo_anterior(r3)
    assert a3["desde"] == datetime(2026, 10, 5) and a3["hasta"] == datetime(2026, 10, 10)


def test_informe_gasto_categorias_pct_y_comparacion():
    r = inf.rango_periodo("este_mes", HOY)
    i = inf.informe_gasto(MOVS, r)
    assert i["total"] == 200_000 and i["ingresos"] == 1_000_000 and i["ahorro"] == 800_000
    comida, transp = i["categorias"]
    assert comida["categoria"] == "Comida" and comida["monto"] == 150_000 and comida["pct"] == 75.0
    assert transp["monto"] == 50_000 and transp["pct"] == 25.0
    # 1-15 sep: Comida 80k + Transporte 20k = 100k (los 400k del 20 quedan fuera)
    assert i["total_anterior"] == 100_000 and i["variacion_pct"] == 100.0
    assert comida["anterior"] == 80_000 and comida["variacion_pct"] == 87.5
    assert transp["variacion_pct"] == 150.0
    # "Éxito" y "exito " son el mismo comercio
    assert i["comercios"][0] == {"nombre": "Éxito", "monto": 150_000, "num": 2}


def test_informe_ignora_transferencias_y_sin_base_no_inventa_variacion():
    r = inf.rango_periodo("mes", HOY, mes="2026-09")
    i = inf.informe_gasto(MOVS, r)
    assert i["total"] == 500_000                      # los 999.999 de la transferencia no cuentan
    assert i["variacion_pct"] is None                 # agosto sin gastos: no hay base honesta


def test_meses_con_datos_y_ultimo():
    ms = inf.meses_con_datos(MOVS)
    assert [m["mes"] for m in ms] == ["2026-09", "2026-10"]
    assert ms[0]["gastos"] == 500_000 and ms[1]["ingresos"] == 1_000_000 and ms[1]["ahorro"] == 800_000
    assert inf.ultimo_mes_con_datos(MOVS) == "2026-10"
    assert inf.ultimo_mes_con_datos(MOVS, antes_de=HOY) == "2026-09"


def test_gasto_diario_con_ceros():
    r = inf.rango_periodo("rango", HOY, "2026-10-09", "2026-10-11")
    assert inf.gasto_diario(MOVS, r) == [
        {"dia": "2026-10-09", "gasto": 50_000, "ingreso": 0},
        {"dia": "2026-10-10", "gasto": 50_000, "ingreso": 0},
        {"dia": "2026-10-11", "gasto": 0, "ingreso": 0},
    ]


# ── asistente: detección y respuestas ──────────────────────────────

def test_parsear_periodo_texto():
    assert cons.parsear_periodo("en que gaste mas en julio", HOY)["desde"] == datetime(2026, 7, 1)
    assert cons.parsear_periodo("gastos de diciembre", HOY)["desde"] == datetime(2025, 12, 1)   # diciembre aún no llega
    assert cons.parsear_periodo("en julio de 2025", HOY)["desde"] == datetime(2025, 7, 1)
    assert cons.parsear_periodo("el mes pasado", HOY)["periodo"] == "mes_pasado"
    assert cons.parsear_periodo("ultimos 3 meses", HOY)["desde"] == datetime(2026, 8, 1)
    assert cons.parsear_periodo("hola", HOY) is None


def test_detectar_intenciones_de_consulta():
    c = ia.detectar_intencion("¿Cuánto gasté en comida el mes pasado?", HOY)
    assert c["intencion"] == "consulta" and c["tipo"] == "gasto_en" and c["objeto"] == "comida"
    assert c["periodo"]["periodo"] == "mes_pasado"
    c = ia.detectar_intencion("¿Gasté más que el mes pasado?", HOY)
    assert c["tipo"] == "comparar" and c["periodo"] is None          # este mes vs el pasado
    assert ia.detectar_intencion("¿Voy bien con mi presupuesto?", HOY)["tipo"] == "presupuesto"
    r = ia.detectar_intencion("¿En qué gasté más en julio?", HOY)
    assert r["intencion"] == "rapida" and r["id"] == "gasto_mes" and r["periodo"]["desde"] == datetime(2026, 7, 1)


def _datos(movs=MOVS, presupuestos=()):
    return {"hoy": HOY, "movs": movs, "presupuestos": list(presupuestos)}


def test_respuesta_gasto_top_con_cifras_y_periodo():
    t = cons.responder_consulta({"tipo": "gasto_top", "periodo": None}, _datos())["texto"]
    assert "octubre de 2026" in t and "$200.000" in t and "Comida $150.000 (75 %)" in t
    assert "+100 %" in t and "los mismos días" in t


def test_respuesta_sin_datos_ofrece_ultimo_mes():
    r = inf.rango_periodo("mes", HOY, mes="2026-08")
    out = cons.responder_consulta({"tipo": "gasto_top", "periodo": r}, _datos())
    assert out["sin_datos"] and "agosto de 2026" in out["texto"]
    assert "último mes con gastos es octubre de 2026" in out["texto"] and "$200.000" in out["texto"]


def test_respuesta_gasto_en_categoria_y_comercio():
    t = cons.responder_consulta({"tipo": "gasto_en", "periodo": None, "objeto": "comida"}, _datos())["texto"]
    assert "$150.000 en Comida" in t and "75 %" in t and "(sept" not in t
    # Septiembre 1-15: comida 80k -> 150k es +87,5 %
    assert "+87,5 %" in t
    t = cons.responder_consulta({"tipo": "gasto_en", "periodo": None, "objeto": "uber"}, _datos())["texto"]
    assert "$50.000 en uber" in t
    t = cons.responder_consulta({"tipo": "gasto_en", "periodo": None, "objeto": "zapatos"}, _datos())["texto"]
    assert "No encontré gastos" in t and "Comida" in t


def test_respuesta_comparar_y_presupuesto():
    t = cons.responder_consulta({"tipo": "comparar", "periodo": None}, _datos())["texto"]
    assert "$200.000" in t and "$100.000" in t and "$100.000 más (+100 %)" in t
    assert "Lo que más subió: Comida (+$70.000)" in t
    pres = [{"categoria": "Comida", "limite": 120_000}, {"categoria": "Transporte", "limite": 500_000}]
    t = cons.responder_consulta({"tipo": "presupuesto"}, _datos(presupuestos=pres))["texto"]
    assert "ya te pasaste" in t and "Comida $150.000 de $120.000 (125 %)" in t
    assert "no tienes presupuestos" in cons.responder_consulta({"tipo": "presupuesto"}, _datos())["texto"].lower()


# ── API ────────────────────────────────────────────────────────────

client = TestClient(app)


@pytest.fixture(autouse=True)
def _usuario():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="inf-1", email="i@test.com", nombre="I")
    limites._eventos.clear()
    yield


def _sembrar():
    if client.get("/cuentas").json():
        return
    c = client.post("/cuentas", json={"nombre": "Ahorros", "saldo": 0, "tipo": "ahorro"}).json()
    hoy = ahora_co()
    a, m = inf.sumar_meses(hoy.year, hoy.month, -2)            # hace dos meses: fuera del mes actual
    f = datetime(a, m, 10, 12).isoformat()
    for desc, monto, tipo, cat in [("Éxito", 100_000, "expense", "Comida"), ("Uber", 40_000, "expense", "Transporte"),
                                   ("Pago tarjeta Visa", 900_000, "expense", "Otros"), ("Sueldo", 2_000_000, "income", "Sueldo")]:
        client.post("/movimientos", json={"cuenta_id": c["id"], "descripcion": desc, "monto": monto, "tipo": tipo,
                                          "categoria": cat, "fecha": f})


def _clave_dos_meses():
    hoy = ahora_co()
    return "%d-%02d" % inf.sumar_meses(hoy.year, hoy.month, -2)


def test_api_informe_gasto_sin_pago_de_tarjeta():
    _sembrar()
    r = client.get("/informes/gasto", params={"periodo": "mes", "mes": _clave_dos_meses()}).json()
    assert r["total"] == 140_000 and r["ingresos"] == 2_000_000          # el pago de tarjeta (900k) no es gasto
    assert [c["categoria"] for c in r["categorias"]] == ["Comida", "Transporte"]
    assert round(r["categorias"][0]["pct"], 1) == 71.4                   # 100k / 140k


def test_api_vacio_ofrece_ultimo_mes_y_movimientos_de_categoria():
    _sembrar()
    r = client.get("/informes/gasto", params={"periodo": "este_mes"}).json()
    assert r["hay_datos"] is False and r["ultimo_mes_con_datos"] == _clave_dos_meses()
    m = client.get("/informes/gasto/movimientos", params={"categoria": "Comida", "periodo": "mes", "mes": _clave_dos_meses()}).json()
    assert m["total"] == 100_000 and m["cantidad"] == 1 and m["movimientos"][0]["descripcion"] == "Éxito"
    assert client.get("/informes/gasto", params={"periodo": "rango", "desde": "2026-02-01"}).status_code == 422


def test_api_meses_y_diario():
    _sembrar()
    r = client.get("/informes/meses").json()
    assert r["ultimo_con_datos"] == _clave_dos_meses()
    assert r["meses"][-1]["gastos"] == 140_000 and r["meses"][-1]["ahorro"] == 1_860_000
    d = client.get("/informes/diario").json()
    assert len(d["dias"]) == 35
    d = client.get("/informes/diario", params={"desde": "2026-01-01", "hasta": "2026-01-03"}).json()
    assert [x["dia"] for x in d["dias"]] == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_api_preguntar_resuelve_con_calculo_y_sin_datos():
    _sembrar()
    r = client.post("/insights/preguntar", json={"pregunta": "¿En qué gasté más?"}).json()
    assert "No pude responder" not in r["respuesta"]
    assert "$140.000" in r["respuesta"]            # ofrece el último mes con datos
    nombre = inf.nombre_mes(_clave_dos_meses()).split(" de ")[0]
    r = client.post("/insights/preguntar", json={"pregunta": f"¿Cuánto gasté en comida en {nombre}?"}).json()
    assert "$100.000 en Comida" in r["respuesta"]
    r = client.post("/insights/preguntar", json={"pregunta": "blablabla"}).json()
    assert r["sugerencias"] and "No entendí" in r["respuesta"]


def test_api_resumen_semanal_rango_personalizado():
    _sembrar()
    c = _clave_dos_meses()
    r = client.get("/insights/resumen-semanal", params={"desde": f"{c}-01", "hasta": f"{c}-28"}).json()
    assert r["gastos"] == 140_000 and r["ingresos"] == 2_000_000 and r["desde"] == f"{c}-01"
    assert client.get("/insights/resumen-semanal").json()["etiqueta"] == "los últimos 7 días"
