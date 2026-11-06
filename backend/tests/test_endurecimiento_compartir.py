"""Endurecimiento de lo compartido: montos absurdos (Infinity, billones) se rechazan con 422, un LECTOR de una
cuenta compartida no puede poner un movimiento ajeno a la vista de un parche, y un enlace se reclama una sola vez."""
import os
import tempfile
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'endurecimiento.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.limites import _eventos  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, CuentaCompartida, Movimiento  # noqa: E402

client = TestClient(app)


@pytest.fixture
def gente():
    s = uuid.uuid4().hex[:8]
    _eventos.clear()
    yield {n: UsuarioActual(id=f"{n}-{s}", email=f"{n}-{s}@test.com", nombre=n.capitalize()) for n in ("ana", "beto")}
    app.dependency_overrides.pop(get_current_user, None)


def como(u):
    app.dependency_overrides[get_current_user] = lambda: u


def _hogar(gente):
    como(gente["ana"])
    return client.post("/hogares", json={"nombre": "Casa"}).json()["id"]


@pytest.mark.parametrize("total", ["Infinity", "NaN", "1e15"])
def test_gasto_de_parche_rechaza_montos_absurdos(gente, total):
    hid = _hogar(gente)
    miembro = client.get(f"/hogares/{hid}").json()["miembros"][0]["id"]
    cuerpo = '{"descripcion":"x","total":%s,"participantes":[{"id":"%s"}]}' % (total, miembro)
    r = client.post(f"/hogares/{hid}/gastos", content=cuerpo, headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def _movimiento_de_ana_con_beto(gente, rol):
    db = SessionLocal()
    cu = Cuenta(usuario_id=gente["ana"].id, nombre="Cuenta Ana", tipo="ahorro", saldo=0, moneda="COP")
    db.add(cu)
    db.flush()
    mov = Movimiento(usuario_id=gente["ana"].id, cuenta_id=cu.id, fecha=datetime.utcnow(), descripcion="Mercado",
                     categoria="Mercado", tipo="expense", monto=50_000, fuente="manual", notas="")
    db.add(mov)
    db.add(CuentaCompartida(cuenta_id=cu.id, usuario_id=gente["beto"].id, rol=rol))
    db.commit()
    mid = mov.id
    db.close()
    return mid


def _compartir_como_beto(gente, mid):
    como(gente["beto"])
    hid = client.post("/hogares", json={"nombre": "Beto y yo"}).json()["id"]
    miembro = client.get(f"/hogares/{hid}").json()["miembros"][0]["id"]
    return client.post(f"/hogares/{hid}/gastos", json={
        "descripcion": "Mercado", "total": 50_000, "participantes": [{"id": miembro}], "movimiento_id": mid})


def test_lector_no_puede_compartir_un_movimiento_de_la_cuenta_ajena(gente):
    mid = _movimiento_de_ana_con_beto(gente, "viewer")
    assert _compartir_como_beto(gente, mid).status_code == 404


def test_editor_si_puede_compartir_un_movimiento_de_la_cuenta_ajena(gente):
    mid = _movimiento_de_ana_con_beto(gente, "editor")
    assert _compartir_como_beto(gente, mid).status_code == 200


def test_el_enlace_de_invitacion_se_reclama_una_sola_vez(gente):
    hid = _hogar(gente)
    token = client.post(f"/hogares/{hid}/invitar", json={}).json()["token"]
    como(gente["beto"])
    assert client.post(f"/hogares/invitaciones/{token}/aceptar", json={}).status_code == 200
    assert client.post(f"/hogares/invitaciones/{token}/aceptar", json={}).status_code in (400, 404)
