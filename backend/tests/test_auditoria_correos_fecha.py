"""Regresión: aprobar un correo guarda la fecha en hora Colombia, no en UTC."""
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'correosfecha.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CorreoGasto, Movimiento  # noqa: E402
from app.utiles import utc_a_co  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="cor-f", email="c@test.com", nombre="C")
    yield


def test_utc_a_co_cruza_de_dia():
    assert utc_a_co(datetime(2026, 2, 1, 1, 0)) == datetime(2026, 1, 31, 20, 0)
    assert utc_a_co(None) is None


def test_aprobar_correo_guarda_hora_colombia():
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "saldo": 100_000}).json()["id"]
    db = SessionLocal()
    c = CorreoGasto(usuario_id="cor-f", gmail_msg_id="m1", monto=10_000, comercio="Tienda",
                    tipo_sugerido="expense", recibido_en=datetime(2026, 2, 1, 1, 0))
    db.add(c)
    db.commit()
    cid = c.id
    db.close()
    r = client.post(f"/correos/{cid}/aprobar", json={"cuenta_id": cuenta})
    assert r.status_code == 200, r.text
    db = SessionLocal()
    mov = db.query(Movimiento).filter(Movimiento.usuario_id == "cor-f").one()
    assert mov.fecha == datetime(2026, 1, 31, 20, 0)
    db.close()
