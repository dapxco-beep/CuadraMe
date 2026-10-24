"""El atajo de cierre solo pregunta una vez por ventana de horas (no en cada cierre de app)."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'cierre.db')}")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Perfil  # noqa: E402

client = TestClient(app)
RUTA = "/movimientos/cierre-pregunta"


def _usuario(uid, clave):
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", api_key=clave))
        db.commit()
    finally:
        db.close()


def test_pregunta_la_primera_vez_y_calla_los_cierres_siguientes():
    _usuario("cierrepq-1", "clave-cierrepq-1")
    h = {"X-Api-Key": "clave-cierrepq-1"}
    assert client.get(RUTA, headers=h).json() == {"preguntar": "si"}
    for _ in range(5):  # saltar de un banco a otro mirando saldos
        assert client.get(RUTA, headers=h).json() == {"preguntar": "no"}


def test_cada_persona_tiene_su_propia_ventana():
    _usuario("cierrepq-2", "clave-cierrepq-2")
    _usuario("cierrepq-3", "clave-cierrepq-3")
    assert client.get(RUTA, headers={"X-Api-Key": "clave-cierrepq-2"}).json()["preguntar"] == "si"
    assert client.get(RUTA, headers={"X-Api-Key": "clave-cierrepq-3"}).json()["preguntar"] == "si"


def test_sin_clave_valida_no_responde():
    assert client.get(RUTA, headers={"X-Api-Key": "mala"}).status_code == 401
