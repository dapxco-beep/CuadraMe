"""Neutralidad de los traslados entre cuentas PROPIAS en los informes, sin perder el saldo.

Escenario (números a mano), mes en curso:
  Nequi: importa 'Enviaste a <titular>' -500.000 y 'Enviaste a Pepito' -15.000
  Nu:    importa 'Recibiste de <titular>' +500.000 y 'Nómina' +2.000.000
  Saldos: Nequi = 1.000.000 - 500.000 - 15.000 = 485.000 | Nu = 0 + 500.000 + 2.000.000 = 2.500.000
  Informes: ingresos reales 2.000.000 (nómina) | gastos reales 15.000 (a un tercero)
"""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'trasneu.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.contabilidad import MARCA_TRASLADO_PROPIO, tipos_efectivos  # noqa: E402
from app.main import app  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)


def _m(id, tipo, monto, desc, cuenta, dias=0, notas="", base=datetime(2026, 10, 5, 12)):
    return {"id": id, "tipo": tipo, "monto": monto, "descripcion": desc, "cuenta_id": cuenta, "categoria": "Otros",
            "fecha": base + timedelta(days=dias), "fuente": "importacion_archivo", "notas": notas}


TIPOS = {"N": "ahorro", "U": "ahorro"}


def test_egreso_nequi_e_ingreso_nu_del_mismo_dia_son_neutrales():
    te = tipos_efectivos([_m("e", "expense", 500_000, "Enviaste a Ana Lopez", "N"),
                          _m("i", "income", 500_000, "Recibiste de Ana Lopez", "U")], TIPOS)
    assert te == {"e": "transfer", "i": "transfer"}


def test_transferencia_a_un_tercero_es_gasto_real():
    te = tipos_efectivos([_m("e", "expense", 15_000, "Para PEPITO PEREZ", "N")], TIPOS)
    assert te == {"e": "expense"}
    # con un ingreso del mismo monto pero sin ninguna pista de traslado, tampoco se empareja
    te = tipos_efectivos([_m("e", "expense", 15_000, "COMPRA TIENDA", "N"),
                          _m("i", "income", 15_000, "Venta de libro", "U")], TIPOS)
    assert te == {"e": "expense", "i": "income"}


def test_dos_pares_identicos_el_mismo_dia_se_emparejan_1_a_1():
    movs = [_m("e1", "expense", 20_000, "Enviaste a Ana", "N"), _m("e2", "expense", 20_000, "Enviaste a Ana", "N"),
            _m("i1", "income", 20_000, "Recibiste de Ana", "U"), _m("i2", "income", 20_000, "Recibiste de Ana", "U")]
    te = tipos_efectivos(movs, TIPOS)
    assert set(te.values()) == {"transfer"}
    # un tercer egreso idéntico sin ingreso sobrante sigue siendo gasto
    te = tipos_efectivos(movs + [_m("e3", "expense", 20_000, "Enviaste a Ana", "N")], TIPOS)
    assert sorted(te.values()) == ["expense", "transfer", "transfer", "transfer", "transfer"]


def test_moneda_distinta_no_se_empareja():
    tipos = {"N": "ahorro", "U": "ahorro"}
    from app.contabilidad import TiposCuenta
    t = TiposCuenta(tipos)
    t.monedas = {"N": "COP", "U": "USD"}
    te = tipos_efectivos([_m("e", "expense", 500, "Enviaste a Ana", "N"), _m("i", "income", 500, "Recibiste de Ana", "U")], t)
    assert te == {"e": "expense", "i": "income"}
    t.monedas = {"N": "COP", "U": "COP"}
    te = tipos_efectivos([_m("e", "expense", 500, "Enviaste a Ana", "N"), _m("i", "income", 500, "Recibiste de Ana", "U")], t)
    assert set(te.values()) == {"transfer"}


def test_la_marca_del_lector_basta_como_pista_y_el_mejor_candidato_gana():
    movs = [_m("e", "expense", 100_000, "Movimiento", "N", notas=MARCA_TRASLADO_PROPIO),
            _m("lejos", "income", 100_000, "Movimiento", "U", dias=1.5),
            _m("cerca", "income", 100_000, "Movimiento", "U", dias=0.1, notas=MARCA_TRASLADO_PROPIO)]
    te = tipos_efectivos(movs, TIPOS)
    assert te["cerca"] == te["e"] == "transfer" and te["lejos"] == "income"


def test_mas_de_dos_dias_no_se_empareja():
    te = tipos_efectivos([_m("e", "expense", 500_000, "Enviaste a Ana", "N"),
                          _m("i", "income", 500_000, "Recibiste de Ana", "U", dias=3)], TIPOS)
    assert set(te.values()) == {"expense", "income"}


def test_rendimiento_con_miles_de_movimientos():
    import time
    movs = []
    for k in range(3000):
        movs.append(_m(f"e{k}", "expense", 1000 + k, f"Enviaste a Ana {k}", "N", dias=k % 30))
        movs.append(_m(f"i{k}", "income", 1000 + k, f"Recibiste de Ana {k}", "U", dias=k % 30))
    t0 = time.perf_counter()
    te = tipos_efectivos(movs, TIPOS)
    assert time.perf_counter() - t0 < 3
    assert set(te.values()) == {"transfer"}


# ── API: los informes ven lo mismo y los saldos se mueven ───────────

@pytest.fixture()
def escenario(request):
    uid = f"user-neu-{request.node.name}"[:60]
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email="n@test.com", nombre="N")
    hoy = ahora_co().strftime("%Y-%m-%d")
    nequi = client.post("/cuentas", json={"nombre": "Nequi", "tipo": "ahorro", "saldo": 1_000_000}).json()["id"]
    nu = client.post("/cuentas", json={"nombre": "Nu", "tipo": "ahorro", "saldo": 0}).json()["id"]
    f = lambda d, m, t: {"fecha": hoy, "descripcion": d, "monto": m, "tipo": t, "categoria": "Otros"}  # noqa: E731
    r1 = client.post("/importar/confirmar", json={"cuenta_id": nequi, "nombre_archivo": "n.csv", "filas": [
        f("Enviaste a Ana Lopez", 500_000, "expense"), f("Enviaste a Pepito Perez", 15_000, "expense")]}).json()
    r2 = client.post("/importar/confirmar", json={"cuenta_id": nu, "nombre_archivo": "u.csv", "filas": [
        f("Recibiste de Ana Lopez", 500_000, "income"), f("Nómina", 2_000_000, "income")]}).json()
    assert r1["importados"] == 2 and r2["importados"] == 2
    return nequi, nu


def test_saldos_se_mueven_por_ambas_patas(escenario):
    nequi, nu = escenario
    s = {c["id"]: c["saldo"] for c in client.get("/cuentas").json()}
    assert s[nequi] == 485_000 and s[nu] == 2_500_000


def test_reportes_exportar_y_resumen_ven_el_traslado_como_neutral(escenario):
    r = client.get("/reportes/mensual").json()
    assert r["ingresos"] == 2_000_000 and r["gastos"] == 15_000
    mes = ahora_co().strftime("%Y-%m")
    w = client.get(f"/reportes/wrapped?mes={mes}").json()
    assert w["gasto_total"] == 15_000 and w["ingresos"] == 2_000_000
    s = client.get("/insights/resumen-semanal").json()
    assert s["gastos"] == 15_000 and s["ingresos"] == 2_000_000
    csv = client.get("/exportar/movimientos.csv").text
    assert "No cuenta" in [l for l in csv.splitlines() if "Enviaste a Ana Lopez" in l][0]
    assert [l for l in csv.splitlines() if "Enviaste a Pepito" in l][0].rstrip().endswith("Gasto")


def test_es_un_gasto_real_del_usuario_impide_el_emparejamiento():
    from app.contabilidad import MARCA_NO_TRASLADO
    te = tipos_efectivos([_m("e", "expense", 500_000, "Enviaste a Ana Lopez", "N", notas=MARCA_NO_TRASLADO),
                          _m("i", "income", 500_000, "Recibiste de Ana Lopez", "U")], TIPOS)
    assert te == {"e": "expense", "i": "income"}
