"""Roles en una cuenta compartida: el lector solo lee; el editor mueve movimientos pero no
administra la cuenta (no la edita, no la borra, no invita, no ve ni quita accesos) y no puede
atar la cuenta del dueño a metas, recurrentes o deudas propias."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'roles.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.derechos_titular import borrar_todo  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
DUENO = UsuarioActual(id="rol-dueno", email="dueno-rol@test.com", nombre="Dueño")
VIEWER = UsuarioActual(id="rol-viewer", email="viewer-rol@test.com", nombre="Lector")
EDITOR = UsuarioActual(id="rol-editor", email="editor-rol@test.com", nombre="Editor")
ACTUAL = {"u": DUENO}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(scope="module", autouse=True)
def _limpiar():
    yield
    db = SessionLocal()
    try:
        for u in (DUENO, VIEWER, EDITOR):
            borrar_todo(db, u.id, u.email)
    finally:
        db.close()


def como(u):
    ACTUAL["u"] = u


@pytest.fixture()
def compartida():
    como(DUENO)
    cta = client.post("/cuentas", json={"nombre": "Compartida", "saldo": 100}).json()["id"]
    mov = client.post("/movimientos", json={"cuenta_id": cta, "descripcion": "m", "monto": 5, "tipo": "expense"}).json()["id"]
    for u, rol in ((VIEWER, "viewer"), (EDITOR, "editor")):
        como(DUENO)
        inv = client.post(f"/cuentas/{cta}/invitar", json={"email": u.email, "rol": rol}).json()["id"]
        como(u)
        assert client.post(f"/cuentas/invitaciones/{inv}/aceptar").status_code == 200
    return cta, mov


def _denegado(r):
    assert 400 <= r.status_code < 500, f"{r.request.method} {r.request.url.path} -> {r.status_code}"


def test_el_lector_puede_leer_pero_no_escribir(compartida):
    cta, mov = compartida
    como(VIEWER)
    assert client.get(f"/movimientos/{mov}").status_code == 200
    _denegado(client.put(f"/movimientos/{mov}", json={"monto": 1}))
    _denegado(client.delete(f"/movimientos/{mov}"))
    _denegado(client.post("/movimientos", json={"cuenta_id": cta, "descripcion": "x", "monto": 1, "tipo": "expense"}))
    _denegado(client.post("/movimientos/eliminar-masivo", json={"movimiento_ids": [mov]}))
    _denegado(client.post(f"/cuentas/{cta}/ajustar-saldo", json={"saldo_real": 1}))
    _denegado(client.post("/importar/confirmar", json={"cuenta_id": cta, "filas": [
        {"fecha": "2026-01-01", "descripcion": "x", "monto": 5, "tipo": "expense"}]}))
    como(DUENO)
    assert client.get(f"/movimientos/{mov}").json()["monto"] == 5  # nada cambió


def test_el_editor_no_administra_la_cuenta_del_dueno(compartida):
    cta, mov = compartida
    como(EDITOR)
    _denegado(client.post(f"/cuentas/{cta}/invitar", json={"email": "z@test.com", "rol": "editor"}))
    _denegado(client.put(f"/cuentas/{cta}", json={"nombre": "mía"}))
    _denegado(client.delete(f"/cuentas/{cta}"))
    _denegado(client.get(f"/cuentas/{cta}/invitaciones"))
    _denegado(client.get(f"/cuentas/{cta}/compartida-con"))
    _denegado(client.delete(f"/cuentas/{cta}/compartir/{VIEWER.id}"))
    como(DUENO)
    nombres = [c["nombre"] for c in client.get("/cuentas").json()]
    assert "Compartida" in nombres  # sigue siendo suya y con su nombre


def test_el_editor_no_ata_la_cuenta_ajena_a_registros_propios(compartida):
    cta, _ = compartida
    como(EDITOR)
    _denegado(client.post("/recurrentes", json={"nombre": "r", "monto": 5, "cuenta_id": cta}))
    _denegado(client.post("/deudas", json={"nombre": "d", "saldo_inicial": 5, "cuenta_pago_id": cta}))
    _denegado(client.post("/metas", json={"nombre": "m", "monto_objetivo": 10, "cuenta_origen_id": cta,
                                         "aporte_automatico": 5}))
