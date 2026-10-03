"""Crons protegidos, alerta de presupuesto única por mes, URLs de push y state de OAuth."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'test2.db')}")

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, cron_autorizado, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento, Presupuesto, PushSubscription  # noqa: E402
from app.push import _url_hash  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
CABECERA = {"X-Cron-Secret": "secreto-de-prueba"}


def test_cron_rechaza_secreto_incorrecto_o_ausente():
    assert client.post("/push/cron/revisar-presupuestos").status_code == 401
    assert client.post("/push/cron/revisar-presupuestos", headers={"X-Cron-Secret": "otro"}).status_code == 401
    assert client.post("/backup/cron/enviar", headers={"X-Cron-Secret": "otro"}).status_code == 401
    assert cron_autorizado("secreto-de-prueba")
    assert not cron_autorizado("")


def test_url_de_push_usa_hash_router():
    assert _url_hash("/presupuesto") == "/#/presupuesto"
    assert _url_hash("/") == "/#/"
    assert _url_hash("/#/metas") == "/#/metas"
    assert _url_hash("metas") == "/#/metas"


def test_alerta_de_presupuesto_solo_una_vez_al_mes():
    db = SessionLocal()
    try:
        cuenta = Cuenta(usuario_id="u-cron", nombre="Banco", saldo=1000, moneda="COP")
        db.add(cuenta)
        db.flush()
        db.add(PushSubscription(usuario_id="u-cron", endpoint="https://push.test/1", p256dh="x", auth="y"))
        db.add(Presupuesto(usuario_id="u-cron", categoria="Comida", limite=100, alerta_pct=80))
        db.add(Movimiento(
            usuario_id="u-cron", cuenta_id=cuenta.id, descripcion="Almuerzo", categoria="Comida",
            tipo="expense", monto=95, fecha=ahora_co(),
        ))
        db.commit()
    finally:
        db.close()

    primera = client.post("/push/cron/revisar-presupuestos", headers=CABECERA).json()
    segunda = client.post("/push/cron/revisar-presupuestos", headers=CABECERA).json()
    assert primera["notificados"] == 1
    assert segunda["notificados"] == 0  # antes se repetía todos los días


def test_state_de_oauth_es_valido_y_a_prueba_de_manipulacion():
    from cryptography.fernet import Fernet

    from app.config import settings

    settings.fernet_key = Fernet.generate_key().decode()
    from app.gmail_oauth import crear_state, leer_state

    state = crear_state("usuario-123")
    assert leer_state(state) == "usuario-123"
    assert leer_state(state + "x") is None
    assert leer_state("basura") is None
    assert leer_state(state, max_segundos=-1) is None  # expirado
