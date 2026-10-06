"""Edición masiva de movimientos: mover a otra cuenta y eliminar varios con saldos correctos,
y conteo de movimientos del mismo comercio. Solo del dueño."""
import os
import tempfile

_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _como(uid):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.com", nombre=uid)


@pytest.fixture(autouse=True)
def _usuario():
    _como("masivo-1")
    yield


def _cuenta(nombre, saldo=1000, moneda="COP"):
    r = client.post("/cuentas", json={"nombre": nombre, "saldo": saldo, "moneda": moneda})
    assert r.status_code == 200, r.text
    return r.json()


def _saldo(cid):
    return next(c["saldo"] for c in client.get("/cuentas").json() if c["id"] == cid)


def _mov(cid, desc, monto, tipo="expense"):
    r = client.post("/movimientos", json={"cuenta_id": cid, "descripcion": desc, "monto": monto, "tipo": tipo})
    assert r.status_code == 200, r.text
    return r.json()


def test_mover_masivo_ajusta_saldos_de_ambas_cuentas():
    a, b = _cuenta("A", 1000), _cuenta("B", 500)
    m1, m2, m3 = _mov(a["id"], "Cafe", 100), _mov(a["id"], "Sueldo", 300, "income"), _mov(a["id"], "Taxi", 50)
    assert _saldo(a["id"]) == 1150
    r = client.post("/movimientos/mover-masivo", json={"movimiento_ids": [m1["id"], m2["id"]], "cuenta_id": b["id"]})
    assert r.status_code == 200 and r.json()["actualizados"] == 2
    # A: arranca 1000, -100 +300 -50 = 1150; al irse m1 (+100) y m2 (-300) queda 950
    assert _saldo(a["id"]) == 950
    # B: 500 + (-100) + 300 = 700
    assert _saldo(b["id"]) == 700
    assert client.get(f"/movimientos/{m3['id']}").json()["cuenta_id"] == a["id"]


def test_mover_masivo_omite_otra_moneda_y_misma_cuenta():
    a, usd = _cuenta("A2", 1000), _cuenta("USD", 10, "USD")
    m = _mov(a["id"], "Cafe", 100)
    r = client.post("/movimientos/mover-masivo", json={"movimiento_ids": [m["id"]], "cuenta_id": usd["id"]})
    assert r.json()["actualizados"] == 0 and r.json()["omitidos"] == 1
    r = client.post("/movimientos/mover-masivo", json={"movimiento_ids": [m["id"]], "cuenta_id": a["id"]})
    assert r.json()["actualizados"] == 0
    assert _saldo(a["id"]) == 900 and _saldo(usd["id"]) == 10


def test_eliminar_masivo_revierte_saldos():
    a = _cuenta("A3", 1000)
    m1, m2 = _mov(a["id"], "Cafe", 100), _mov(a["id"], "Premio", 400, "income")
    assert _saldo(a["id"]) == 1300
    r = client.post("/movimientos/eliminar-masivo", json={"movimiento_ids": [m1["id"], m2["id"]]})
    assert r.status_code == 200 and r.json()["actualizados"] == 2
    assert _saldo(a["id"]) == 1000
    assert client.get(f"/movimientos/{m1['id']}").status_code == 404


def test_eliminar_masivo_omite_transferencias():
    a, b = _cuenta("A4", 1000), _cuenta("B4", 0)
    assert client.post("/movimientos/transferencia", json={
        "cuenta_origen_id": a["id"], "cuenta_destino_id": b["id"], "monto": 200}).status_code == 200
    trf = next(m for m in client.get("/movimientos?limit=50").json() if m["cuenta_id"] == a["id"])
    r = client.post("/movimientos/eliminar-masivo", json={"movimiento_ids": [trf["id"]]})
    assert r.json()["actualizados"] == 0 and r.json()["omitidos"] == 1
    assert _saldo(a["id"]) == 800 and _saldo(b["id"]) == 200


def test_masivo_no_toca_movimientos_de_otro_usuario():
    a = _cuenta("Mia", 1000)
    m = _mov(a["id"], "Cafe", 100)
    _como("masivo-2")
    mia_otro = _cuenta("Suya", 50)
    r = client.post("/movimientos/eliminar-masivo", json={"movimiento_ids": [m["id"]]})
    assert r.json()["actualizados"] == 0
    r = client.post("/movimientos/mover-masivo", json={"movimiento_ids": [m["id"]], "cuenta_id": mia_otro["id"]})
    assert r.json()["actualizados"] == 0
    r = client.post("/movimientos/mover-masivo", json={"movimiento_ids": [m["id"]], "cuenta_id": a["id"]})
    assert r.status_code == 404  # la cuenta de destino no es suya
    _como("masivo-1")
    assert _saldo(a["id"]) == 900
    assert client.get(f"/movimientos/{m['id']}").status_code == 200


def test_conteo_similares_cuenta_el_mismo_comercio():
    a = _cuenta("A5", 0)
    base = _mov(a["id"], "Compra PANADERIA LA 80 0105", 10)
    _mov(a["id"], "PANADERIA LA 80 BOGOTA", 10)
    _mov(a["id"], "Pago panaderia la 80", 10)
    _mov(a["id"], "Otro comercio distinto", 10)
    r = client.get("/movimientos/similares/conteo", params={"descripcion": base["descripcion"], "excluir_id": base["id"]})
    assert r.status_code == 200
    assert r.json()["huella"] == "panaderia"
    assert r.json()["conteo"] == 2
