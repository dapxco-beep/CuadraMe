"""
Detección robusta de traslados entre cuentas propias y comparación ingresos vs gastos.

- Los casos de backend/tests/fixtures/contabilidad_casos.json son los MISMOS que prueba la PWA
  (pwa/src/test/contabilidad_paridad.test.js): así el espejo lib/contabilidad.js no se desvía.
- Ingresos vs gastos: con traslados presentes el total NO cambia.
- Decisión de la persona (con memoria por huella) respetada por los informes.
"""
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'trasrob.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import contabilidad as c  # noqa: E402
from app import informe as inf  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento  # noqa: E402

CASOS = json.loads((Path(__file__).parent / "fixtures" / "contabilidad_casos.json").read_text(encoding="utf-8"))["casos"]


def _tc(caso) -> c.TiposCuenta:
    tc = c.TiposCuenta()
    tc.monedas = {k: v["moneda"] for k, v in caso["cuentas"].items()}
    for k, v in caso["cuentas"].items():
        tc[k] = v["tipo"]
    tc.reglas = caso.get("reglas", {})
    tc.nombres = caso.get("nombres", [])
    return tc


def _movs(caso):
    return [{**m, "fecha": datetime.fromisoformat(m["fecha"])} for m in caso["movs"]]


@pytest.mark.parametrize("caso", CASOS, ids=[x["nombre"] for x in CASOS])
def test_casos_compartidos_con_la_pwa(caso):
    assert c.tipos_efectivos(_movs(caso), _tc(caso)) == caso["esperado"]


def test_la_neutralidad_no_depende_del_tipo_guardado_ni_de_la_categoria_plural():
    """Diagnóstico de producción: 0 movimientos 'transfer' y la categoría «Transferencias» (plural)
    con gastos reales: nada de eso debe volverlos neutrales."""
    movs = [
        {"id": "a", "tipo": "expense", "monto": 30000, "descripcion": "Pago a Pedro", "cuenta_id": "N",
         "categoria": "Transferencias", "fecha": datetime(2026, 10, 5), "fuente": "x", "notas": ""},
    ]
    assert c.tipos_efectivos(movs, {"N": "ahorro"}) == {"a": "expense"}


def test_razon_del_par_y_su_pareja():
    caso = CASOS[0]
    cl = c.clasificar(_movs(caso), _tc(caso))
    assert cl["e"] == {"tipo": "transfer", "razon": "par", "par": "i"}
    assert cl["i"]["par"] == "e"


def test_comision_es_configurable():
    caso = next(x for x in CASOS if x["nombre"].startswith("Traslado con comision"))
    tc = _tc(caso)
    assert c.clasificar(_movs(caso), tc)["e"]["razon"] == "par_comision"
    tc.tolerancia_comision = 1000  # con menos tolerancia ya no es par (cada pata queda como posible traslado)
    assert c.clasificar(_movs(caso), tc)["e"]["razon"] == "posible"


def test_huella_estable_sin_numeros_ni_verbos():
    assert c.huella_traslado("Enviaste a Ana Lopez 123456") == "ana lopez"
    assert c.huella_traslado("Recibiste de ANA  LÓPEZ") == "ana lopez"
    assert c.huella_traslado("Para 1234") == ""


def test_nombre_parcial_y_sin_tildes():
    assert c.menciones_propias("ENVIASTE A DANIEL PARRADO", ["Daniel Alfonso Parrado Cárdenas"]) == 2
    assert c.menciones_propias("Enviaste a Daniel Gomez", ["Daniel Alfonso Parrado Cárdenas"]) == 1
    assert c.menciones_propias("Pago Exito", ["Daniel"]) == 0


def test_sugerencias_par_sin_pista_y_decision_no_se_vuelve_a_sugerir():
    movs = [
        {"id": "e", "tipo": "expense", "monto": 200000, "descripcion": "Pago XYZ", "cuenta_id": "N", "categoria": "Otros",
         "fecha": datetime(2026, 10, 5, 10), "fuente": "x", "notas": ""},
        {"id": "i", "tipo": "income", "monto": 200000, "descripcion": "Abono ABC", "cuenta_id": "U", "categoria": "Otros",
         "fecha": datetime(2026, 10, 6, 10), "fuente": "x", "notas": ""},
    ]
    tc = c.TiposCuenta({"N": "ahorro", "U": "ahorro"})
    sug = c.sugerir_traslados(movs, tc)
    assert [s["tipo"] for s in sug] == ["par"] and sug[0]["ids"] == ["e", "i"]
    assert c.tipos_efectivos(movs, tc) == {"e": "expense", "i": "income"}  # nada se aplica solo
    movs[0]["notas"] = c.notas_con_decision("", "real")
    assert c.sugerir_traslados(movs, tc) == []


def test_notas_con_decision():
    assert c.notas_con_decision("hola", "traslado") == "hola · es_traslado_propio"
    n = c.notas_con_decision("posible_traslado_propio · es_traslado_propio", "real")
    assert n == "no_es_traslado"
    assert c.notas_con_decision(n, "traslado") == "es_traslado_propio"


# ── Ingresos vs gastos con traslados presentes ───────────────────────────────────────────────────
def _e(id, tipo, monto, fecha, razon="normal"):
    return {"id": id, "tipo": tipo, "monto": monto, "fecha": fecha, "categoria": "Otros", "descripcion": id, "razon": razon}


def test_ingresos_gastos_puro_balance_tasa_y_comparacion():
    hoy = datetime(2026, 10, 15, 12)
    rango = inf.rango_periodo("este_mes", hoy)
    movs = [
        _e("i1", "income", 3_000_000, datetime(2026, 10, 2)), _e("g1", "expense", 1_000_000, datetime(2026, 10, 3)),
        _e("t1", "transfer", 500_000, datetime(2026, 10, 4), "par"),  # traslado: no cuenta
        _e("i0", "income", 2_000_000, datetime(2026, 9, 2)), _e("g0", "expense", 2_500_000, datetime(2026, 9, 3)),
    ]
    r = inf.ingresos_gastos(movs, rango, meses=3)
    assert (r["ingresos"], r["gastos"], r["balance"], r["tasa_ahorro"]) == (3_000_000, 1_000_000, 2_000_000, 66.7)
    assert r["anterior"]["balance"] == -500_000 and r["anterior"]["tasa_ahorro"] == -25.0
    assert r["variacion"]["ingresos_pct"] == 50.0 and r["variacion"]["balance_pct"] == 500.0
    assert [m["mes"] for m in r["meses"]] == ["2026-08", "2026-09", "2026-10"]
    assert r["meses"][2]["balance"] == 2_000_000


def test_sin_ingresos_no_hay_tasa_de_ahorro():
    rango = inf.rango_periodo("este_mes", datetime(2026, 10, 15))
    r = inf.ingresos_gastos([_e("g", "expense", 100, datetime(2026, 10, 3))], rango)
    assert r["tasa_ahorro"] is None and r["balance"] == -100 and r["hay_datos"]
    assert inf.ingresos_gastos([], rango)["hay_datos"] is False


def test_no_se_cuenta_agrupa_por_motivo():
    rango = inf.rango_periodo("este_mes", datetime(2026, 10, 15))
    movs = [_e("a", "transfer", 10, datetime(2026, 10, 3), "par"), _e("b", "transfer", 20, datetime(2026, 10, 4), "pago_tarjeta"),
            _e("c", "transfer", 5, datetime(2026, 10, 5), "ajuste"), _e("d", "expense", 9, datetime(2026, 10, 5))]
    r = inf.no_se_cuenta(movs, rango)
    assert r["cantidad"] == 3
    assert {g["nombre"] for g in r["grupos"]} == {"Traslado entre tus cuentas", "Pago de tarjeta", "Ajuste de saldo"}


# ── Endpoints ─────────────────────────────────────────────────────────────────────────────────────
client = TestClient(app)
U = UsuarioActual(id="tr-rob-u", email="tr@test.com", nombre="Daniel Alfonso Parrado Cardenas")
OTRO = UsuarioActual(id="tr-rob-otro", email="otro@test.com", nombre="Otra Persona")
ACTUAL = {"u": U}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    ACTUAL["u"] = U
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def escenario():
    """Dos cuentas del usuario con un traslado Nequi->Nu (con pistas), un sueldo y un gasto real."""
    from app.utiles import ahora_co

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    ahora = ahora_co().replace(hour=12, minute=0, second=0, microsecond=0)
    base = ahora.replace(day=2) if ahora.day >= 2 else ahora
    cu_n = Cuenta(usuario_id=U.id, nombre="Nequi demo", tipo="ahorro", saldo=0, moneda="COP")
    cu_u = Cuenta(usuario_id=U.id, nombre="Nu demo", tipo="ahorro", saldo=0, moneda="COP")
    db.add_all([cu_n, cu_u])
    db.flush()

    def mv(cuenta, tipo, monto, desc, dias=0, cat="Otros"):
        from datetime import timedelta
        m = Movimiento(usuario_id=U.id, cuenta_id=cuenta.id, fecha=base + timedelta(days=dias), descripcion=desc,
                       categoria=cat, tipo=tipo, monto=monto, fuente="importacion_archivo", notas="")
        db.add(m)
        return m

    out = {
        "traslado_sale": mv(cu_n, "expense", 400_000, "Enviaste a Ana Demo"),
        "traslado_entra": mv(cu_u, "income", 400_000, "Recibiste de Ana Demo"),
        "sueldo": mv(cu_u, "income", 2_000_000, "Nomina Empresa Demo", 1),
        "gasto": mv(cu_n, "expense", 150_000, "Supermercado Demo", 1, "Mercado"),
        "sin_pareja_a": mv(cu_n, "expense", 90_000, "Pago Taller Demo", 1),
        "sin_pareja_b": mv(cu_u, "income", 90_000, "Abono Cliente Demo", 1),
    }
    db.commit()
    ids = {k: v.id for k, v in out.items()}
    ids["cuenta_n"], ids["cuenta_u"] = cu_n.id, cu_u.id
    db.close()
    yield ids
    from app.derechos_titular import borrar_todo
    db = SessionLocal()
    try:
        borrar_todo(db, U.id, U.email)
    finally:
        db.close()


def test_endpoint_ingresos_gastos_ignora_el_traslado(escenario):
    r = client.get("/reportes/ingresos-gastos?periodo=este_mes").json()
    # sueldo 2.000.000 + abono 90.000 son ingresos reales; el traslado de 400.000 no cuenta
    assert r["ingresos"] == 2_090_000
    assert r["gastos"] == 150_000 + 90_000
    assert r["balance"] == r["ingresos"] - r["gastos"]
    assert len(r["meses"]) == 6 and r["meses"][-1]["ingresos"] == r["ingresos"]
    # el detalle por categoría existente sigue igual y tampoco incluye el traslado
    g = client.get("/informes/gasto?periodo=este_mes").json()
    assert g["total"] == r["gastos"]


def test_endpoint_no_se_cuenta_lista_el_traslado(escenario):
    r = client.get("/informes/no-se-cuenta?periodo=este_mes").json()
    assert r["cantidad"] == 2
    assert {m["id"] for m in r["movimientos"]} == {escenario["traslado_sale"], escenario["traslado_entra"]}
    assert r["grupos"][0]["nombre"] == "Traslado entre tus cuentas"


def test_rango_invalido_da_422(escenario):
    assert client.get("/reportes/ingresos-gastos?periodo=rango&desde=2026-10-10&hasta=2026-10-01").status_code == 422


def test_sugerencias_y_decision_con_memoria_se_respeta_en_los_informes(escenario):
    sug = client.get("/traslados/sugerencias").json()["sugerencias"]
    par = next(s for s in sug if s["tipo"] == "par")
    assert set(par["ids"]) == {escenario["sin_pareja_a"], escenario["sin_pareja_b"]}
    antes = client.get("/reportes/ingresos-gastos?periodo=este_mes").json()
    # la persona dice «es un traslado»: ya no suma ni resta, y se recuerda
    r = client.post("/traslados/decidir", json={"ids": par["ids"], "decision": "traslado", "recordar": True})
    assert r.status_code == 200 and r.json()["aplicados"] == 2
    despues = client.get("/reportes/ingresos-gastos?periodo=este_mes").json()
    assert despues["ingresos"] == antes["ingresos"] - 90_000
    assert despues["gastos"] == antes["gastos"] - 90_000
    assert despues["balance"] == antes["balance"]
    # ya no se sugiere otra vez
    assert not [s for s in client.get("/traslados/sugerencias").json()["sugerencias"] if s["tipo"] == "par"]
    assert len(client.get("/traslados/reglas").json()) >= 1
    # «No es un traslado» sobre el traslado detectado lo vuelve ingreso y gasto reales
    ids = [escenario["traslado_sale"], escenario["traslado_entra"]]
    assert client.post("/traslados/decidir", json={"ids": ids, "decision": "real"}).status_code == 200
    real = client.get("/reportes/ingresos-gastos?periodo=este_mes").json()
    assert real["ingresos"] == despues["ingresos"] + 400_000 and real["gastos"] == despues["gastos"] + 400_000


def test_la_regla_recordada_vale_para_un_movimiento_nuevo(escenario):
    from app.utiles import ahora_co
    ids = [escenario["sin_pareja_a"], escenario["sin_pareja_b"]]
    client.post("/traslados/decidir", json={"ids": ids, "decision": "traslado", "recordar": True})
    db = SessionLocal()
    try:
        m = Movimiento(usuario_id=U.id, cuenta_id=escenario["cuenta_n"], fecha=ahora_co(), descripcion="Pago Taller Demo 998877",
                       categoria="Otros", tipo="expense", monto=33_333, fuente="importacion_archivo", notas="")
        db.add(m)
        db.commit()
        nuevo = m.id
    finally:
        db.close()
    fila = next(x for x in client.get("/informes/no-se-cuenta?periodo=este_mes").json()["movimientos"] if x["id"] == nuevo)
    assert fila["razon"] == "regla"


def test_decidir_valida_entrada_y_dueno(escenario):
    assert client.post("/traslados/decidir", json={"ids": [escenario["gasto"]], "decision": "otra"}).status_code == 422
    ACTUAL["u"] = OTRO
    r = client.post("/traslados/decidir", json={"ids": [escenario["gasto"]], "decision": "traslado"})
    assert r.status_code == 404
    assert client.get("/traslados/sugerencias").json()["sugerencias"] == []
