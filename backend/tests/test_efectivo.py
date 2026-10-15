"""Efectivo: retiro de cajero = traslado hacia la cuenta Efectivo (no gasto); depósito = inverso."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'efectivo.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.derechos_titular import borrar_todo  # noqa: E402
from app.efectivo import sugerencia_efectivo  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
U = UsuarioActual(id="efectivo-u", email="efectivo@test.com", nombre="Ana")


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: U
    yield
    app.dependency_overrides.pop(get_current_user, None)
    db = SessionLocal()
    try:
        borrar_todo(db, U.id, U.email)
    finally:
        db.close()


def test_reconoce_retiros_y_depositos():
    assert sugerencia_efectivo("expense", "Retiro cajero Bancolombia") == "retiro"
    assert sugerencia_efectivo("expense", "RETIRO CORRESPONSAL") == "retiro"
    assert sugerencia_efectivo("income", "Consignación en efectivo") == "deposito"
    assert sugerencia_efectivo("expense", "Comisión retiro cajero ajeno") is None  # cobro: sigue siendo gasto
    assert sugerencia_efectivo("income", "Retiro cajero") is None  # dirección contraria
    assert sugerencia_efectivo("expense", "Compra Éxito") is None


def _mov(cuenta, tipo, desc, monto):
    r = client.post("/movimientos", json={"cuenta_id": cuenta, "tipo": tipo, "descripcion": desc,
                                           "monto": monto, "categoria": "Otros"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _saldos():
    return {c["tipo"]: c["saldo"] for c in client.get("/cuentas").json()}


def test_retiro_pasa_a_efectivo_sin_ser_gasto_y_pide_crear_cuenta():
    banco = client.post("/cuentas", json={"nombre": "Banco", "saldo": 1_000_000}).json()["id"]
    mid = _mov(banco, "expense", "Retiro cajero", 200_000)
    assert _saldos()["ahorro"] == 800_000
    # sin cuenta Efectivo: pide confirmar la creación
    assert client.post(f"/movimientos/{mid}/pasar-a-efectivo").status_code == 409
    r = client.post(f"/movimientos/{mid}/pasar-a-efectivo?crear_cuenta=true")
    assert r.status_code == 200 and r.json()["sentido"] == "retiro"
    s = _saldos()
    assert s["ahorro"] == 800_000 and s["efectivo"] == 200_000  # el total no cambia
    movs = client.get("/movimientos").json()
    assert {m["tipo"] for m in movs} == {"transfer"}  # ya no hay gasto
    # no se puede repetir
    assert client.post(f"/movimientos/{mid}/pasar-a-efectivo").status_code == 400


def test_deposito_es_traslado_inverso():
    banco = client.post("/cuentas", json={"nombre": "Banco", "saldo": 0}).json()["id"]
    client.post("/cuentas", json={"nombre": "Efectivo", "tipo": "efectivo", "saldo": 500_000})
    mid = _mov(banco, "income", "Consignación en efectivo", 300_000)
    assert client.post(f"/movimientos/{mid}/pasar-a-efectivo").status_code == 200
    s = _saldos()
    assert s["ahorro"] == 300_000 and s["efectivo"] == 200_000
    resumen = client.get("/cuentas/resumen").json()
    assert resumen["total_cop"] == 500_000 and resumen["disponible_cop"] == 500_000


def test_compra_normal_no_se_puede_pasar_a_efectivo():
    banco = client.post("/cuentas", json={"nombre": "Banco", "saldo": 100_000}).json()["id"]
    mid = _mov(banco, "expense", "Compra Éxito", 10_000)
    assert client.post(f"/movimientos/{mid}/pasar-a-efectivo?crear_cuenta=true").status_code == 400
