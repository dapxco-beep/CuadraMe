"""La clave VAPID del servidor se usa como OBJETO (pywebpush no lee el texto de un PEM). Sin esto ningún aviso salía.

Estas pruebas firman DE VERDAD con una clave real generada aquí: no simulan la clave, que es justo lo que ocultó el error."""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'pushvapid.db')}")

import pytest  # noqa: E402
from py_vapid import Vapid01  # noqa: E402

from app import push  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import PushSubscription  # noqa: E402


@pytest.fixture
def clave(monkeypatch):
    v = Vapid01()
    v.generate_keys()
    pem = v.private_pem().decode()
    # Así llega a Railway: el PEM en UNA línea con «\n» escritos como texto
    monkeypatch.setattr(settings, "vapid_private_key_pem", pem.strip().replace("\n", "\\n"))
    return v


def test_la_clave_de_railway_se_lee_y_firma(clave):
    v = push._vapid()
    assert isinstance(v, Vapid01)
    firmado = v.sign({"sub": "mailto:prueba@ejemplo.com", "aud": "https://web.push.apple.com"})
    assert firmado["Authorization"].startswith(("vapid", "WebPush"))
    assert v.public_key.public_numbers() == clave.public_key.public_numbers()


def test_pasarle_el_texto_del_pem_a_pywebpush_falla_y_el_objeto_no(clave):
    """Documenta el bug original: con el TEXTO del PEM pywebpush revienta; con el objeto firma bien."""
    from pywebpush import WebPusher

    pem_texto = push._private_key_pem()
    with pytest.raises(Exception):
        Vapid01.from_string(pem_texto)  # lo que pywebpush hacía con un texto
    assert WebPusher is not None and push._vapid() is not None


def test_enviar_push_entrega_un_objeto_de_clave_a_webpush(clave, monkeypatch):
    recibido = {}

    def falso_webpush(subscription_info, data, vapid_private_key, vapid_claims):
        recibido["clave"] = vapid_private_key
        recibido["datos"] = json.loads(data)

    monkeypatch.setattr(push, "webpush", falso_webpush)
    db = SessionLocal()
    try:
        db.add(PushSubscription(usuario_id="pv-1", endpoint="https://web.push.apple.com/abc", p256dh="x", auth="y"))
        db.commit()
        assert push.enviar_push(db, "pv-1", "CuadraMe", "Hola", "/perfil") == 1
    finally:
        db.close()
    assert isinstance(recibido["clave"], Vapid01)  # NO un texto
    assert recibido["datos"]["url"] == "/#/perfil"


def test_una_clave_ilegible_no_tumba_el_envio_y_queda_en_el_registro(monkeypatch, caplog):
    monkeypatch.setattr(settings, "vapid_private_key_pem", "esto-no-es-una-clave")
    db = SessionLocal()
    try:
        db.add(PushSubscription(usuario_id="pv-2", endpoint="https://web.push.apple.com/zzz", p256dh="x", auth="y"))
        db.commit()
        with caplog.at_level("ERROR", logger="app.push"):
            assert push.enviar_push(db, "pv-2", "CuadraMe", "Hola") == 0
    finally:
        db.close()
    assert "clave VAPID" in caplog.text
