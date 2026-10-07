"""Ajuste de saldo: el saldo cambia, pero el ajuste NO es gasto ni ingreso en ningún reporte.

Escenario (números a mano): sueldo +2.000.000 y compra -100.000 => saldo 1.900.000.
El usuario ve 1.700.000 en su banco y ajusta: se crea un 'Ajuste de saldo' de -200.000 que
NO debe aparecer como gasto (gastos reales siguen en 100.000) ni como ingreso.
"""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'ajuste.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.contabilidad import FUENTE_AJUSTE, tipos_efectivos  # noqa: E402
from app.main import app  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="aj-0", email="a@test.com", nombre="Aj")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def como(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def _base(uid):
    como(uid)
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "tipo": "ahorro", "saldo": 0}).json()["id"]
    client.post("/movimientos", json={"cuenta_id": cuenta, "tipo": "income", "monto": 2_000_000,
                                      "descripcion": "Nómina", "categoria": "Ingresos"})
    client.post("/movimientos", json={"cuenta_id": cuenta, "tipo": "expense", "monto": 100_000,
                                      "descripcion": "Restaurante", "categoria": "Comida"})
    return cuenta


def _saldo(cuenta):
    return {c["id"]: c["saldo"] for c in client.get("/cuentas").json()}[cuenta]


def test_ajuste_a_la_baja_cambia_saldo_y_crea_movimiento():
    cuenta = _base("aj-baja")
    r = client.post(f"/cuentas/{cuenta}/ajustar-saldo", json={"saldo_real": 1_700_000}).json()
    assert r["ajustado"] and r["diferencia"] == -200_000 and r["saldo"] == 1_700_000
    assert _saldo(cuenta) == 1_700_000
    mov = client.get(f"/movimientos/{r['movimiento_id']}").json()
    assert mov["fuente"] == FUENTE_AJUSTE and mov["categoria"] == "Ajuste de saldo"
    assert mov["tipo"] == "expense" and mov["monto"] == 200_000


def test_ajuste_al_alza_y_sin_cambio():
    cuenta = _base("aj-alza")
    r = client.post(f"/cuentas/{cuenta}/ajustar-saldo", json={"saldo_real": 2_000_000}).json()
    assert r["diferencia"] == 100_000 and _saldo(cuenta) == 2_000_000
    r = client.post(f"/cuentas/{cuenta}/ajustar-saldo", json={"saldo_real": 2_000_000}).json()
    assert r["ajustado"] is False and r["movimiento_id"] is None  # sin diferencia no se ensucia el historial


def test_ajuste_no_cuenta_en_reportes_ni_tendencias_ni_insights():
    cuenta = _base("aj-reportes")
    client.post(f"/cuentas/{cuenta}/ajustar-saldo", json={"saldo_real": 1_700_000})      # -200.000
    client.post(f"/cuentas/{cuenta}/ajustar-saldo", json={"saldo_real": 5_000_000})      # +3.300.000
    r = client.get("/reportes/mensual").json()
    assert r["gastos"] == 100_000 and r["ingresos"] == 2_000_000 and r["ahorro"] == 1_900_000
    assert {c["categoria"] for c in r["top_categorias"]} == {"Comida"}
    t = client.get("/reportes/tendencias?meses=1").json()["meses"][-1]
    assert t["gastos"] == 100_000 and t["ingresos"] == 2_000_000
    s = client.get("/insights/resumen-semanal").json()
    assert s["gastos"] == 100_000 and s["ingresos"] == 2_000_000
    assert _saldo(cuenta) == 5_000_000   # el saldo sí refleja los ajustes


def test_ajuste_no_gasta_presupuestos_aunque_se_llame_como_la_categoria():
    cuenta = _base("aj-pres")
    client.post("/presupuestos", json={"categoria": "Ajuste de saldo", "limite": 50_000})
    client.post("/presupuestos", json={"categoria": "Comida", "limite": 500_000})
    client.post(f"/cuentas/{cuenta}/ajustar-saldo", json={"saldo_real": 1_000_000})   # -900.000
    por_cat = {c["categoria"]: c["gastado"] for c in client.get("/presupuestos/disponible-hoy").json()["categorias"]}
    assert por_cat["Ajuste de saldo"] == 0
    assert por_cat["Comida"] == 100_000


def test_ajuste_no_cuenta_en_exportar_ni_wrapped():
    cuenta = _base("aj-exp")
    client.post(f"/cuentas/{cuenta}/ajustar-saldo", json={"saldo_real": 1_000_000})
    csv = client.get("/exportar/movimientos.csv").text
    linea = [l for l in csv.splitlines() if "Ajuste de saldo" in l][0]
    assert "No cuenta" in linea
    w = client.get(f"/reportes/wrapped?mes={ahora_co().strftime('%Y-%m')}").json()
    assert w["gasto_total"] == 100_000


def test_regla_pura_el_ajuste_es_transfer_aun_sin_categoria():
    movs = [
        {"id": "a", "tipo": "income", "monto": 5, "descripcion": "x", "cuenta_id": "A", "categoria": "Otros", "fuente": FUENTE_AJUSTE},
        {"id": "b", "tipo": "expense", "monto": 5, "descripcion": "x", "cuenta_id": "A", "categoria": "Otros", "fuente": FUENTE_AJUSTE},
        {"id": "c", "tipo": "expense", "monto": 5, "descripcion": "x", "cuenta_id": "A", "categoria": "Ajuste de saldo", "fuente": "manual"},
    ]
    assert set(tipos_efectivos(movs, {"A": "ahorro"}).values()) == {"transfer"}


def test_tarjeta_ajuste_con_signo_de_deuda():
    como("aj-tc")
    tc = client.post("/cuentas", json={"nombre": "Visa", "tipo": "credito", "saldo": -800_000, "cupo_total": 3_000_000}).json()
    assert tc["tarjeta"]["cupo_usado"] == 800_000 and tc["tarjeta"]["cupo_disponible"] == 2_200_000
    r = client.post(f"/cuentas/{tc['id']}/ajustar-saldo", json={"saldo_real": -1_000_000}).json()   # ahora debo 1.000.000
    assert r["diferencia"] == -200_000
    det = client.get(f"/cuentas/{tc['id']}/detalle").json()
    assert det["cuenta"]["tarjeta"]["cupo_usado"] == 1_000_000 and det["gastos_mes"] == 0


def test_ajustar_cuenta_ajena_es_404_y_viewer_no_puede():
    cuenta = _base("aj-dueno")
    como("aj-intruso")
    assert client.post(f"/cuentas/{cuenta}/ajustar-saldo", json={"saldo_real": 1}).status_code == 404
    assert client.get(f"/cuentas/{cuenta}/detalle").status_code == 404


def test_detalle_y_resumen():
    cuenta = _base("aj-detalle")
    tc = client.post("/cuentas", json={"nombre": "Visa", "tipo": "credito", "saldo": -300_000, "cupo_total": 1_000_000}).json()["id"]
    d = client.get(f"/cuentas/{cuenta}/detalle").json()
    assert d["saldo_actual"] == 1_900_000 and d["ingresos_mes"] == 2_000_000 and d["gastos_mes"] == 100_000
    assert len(d["movimientos"]) == 2 and d["ultimo_movimiento"]
    r = client.get("/cuentas/resumen").json()
    assert r["total_cop"] == 1_600_000                       # 1.900.000 - 300.000
    assert r["disponible_cop"] == 1_900_000 and r["deudas_tarjeta_cop"] == 300_000
    assert r["por_tipo"] == {"ahorro": 1_900_000, "credito": -300_000}
    assert r["por_moneda"] == {"COP": 1_600_000} and r["hay_movimientos"] is True
    assert cuenta in r["ultimo_por_cuenta"] and tc not in r["ultimo_por_cuenta"]   # la tarjeta aún no tiene movimientos


def test_resumen_usuario_nuevo_sin_movimientos():
    como("aj-vacio")
    client.post("/cuentas", json={"nombre": "Nequi", "tipo": "ahorro", "saldo": 50_000})
    r = client.get("/cuentas/resumen").json()
    assert r["total_cop"] == 50_000 and r["hay_movimientos"] is False and r["ultimo_movimiento"] is None
