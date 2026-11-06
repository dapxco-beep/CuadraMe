"""Clave API guardada como hash SHA-256 (acceso) y cifrada (para que su dueño pueda volver a verla),
las claves antiguas en claro siguen sirviendo y se migran al primer uso."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'apikeyhash.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import claves_api  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Perfil  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="h-0", email="h@test.com", nombre="H")}
RUTA = "/movimientos/cuentas-rapido"


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    from cryptography.fernet import Fernet

    from app.config import settings

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def como(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def _fila(uid):
    db = SessionLocal()
    try:
        return db.execute(
            text("SELECT api_key, api_key_hash, api_key_prefijo FROM perfiles WHERE usuario_id = :u"), {"u": uid}
        ).one()
    finally:
        db.close()


def test_clave_nueva_se_guarda_como_hash_y_cifrada_y_se_puede_volver_a_ver():
    como("h-1")
    r = client.get("/perfil/api-key").json()
    clave = r["api_key"]
    assert clave.startswith("cdm_") and r["nueva"] is True
    api_key, h, prefijo = _fila("h-1")
    assert api_key is None and h == claves_api.hash_clave(clave) and clave not in str(tuple(_fila("h-1")))
    assert prefijo == clave[:8] + "…"
    # La base solo tiene la clave cifrada, nunca en claro...
    db = SessionLocal()
    try:
        enc = db.execute(text("SELECT api_key_enc FROM perfiles WHERE usuario_id = 'h-1'")).scalar()
    finally:
        db.close()
    assert enc and clave not in enc
    # ...y su dueño puede volver a verla las veces que quiera, sin generar otra.
    r2 = client.get("/perfil/api-key").json()
    assert r2["api_key"] == clave and r2["nueva"] is False and r2["visible"] is True
    # Y sigue funcionando para el Atajo, que se autentica con el hash.
    assert client.get(RUTA, headers={"X-Api-Key": clave}).status_code == 200
    assert client.get(RUTA, headers={"X-Api-Key": clave + "x"}).status_code == 401


def test_clave_de_antes_del_cifrado_se_vuelve_visible_cuando_el_atajo_la_usa():
    como("h-9")
    clave = client.get("/perfil/api-key").json()["api_key"]
    db = SessionLocal()
    try:  # simula una clave creada antes de esta función: solo hash
        db.execute(text("UPDATE perfiles SET api_key_enc = NULL WHERE usuario_id = 'h-9'"))
        db.commit()
    finally:
        db.close()
    r = client.get("/perfil/api-key").json()
    assert r["api_key"] is None and "Genera una nueva" in r["mensaje"] and r["prefijo"]
    # El Atajo la presenta completa una vez: desde ahí su dueño puede verla, sin regenerar.
    assert client.get(RUTA, headers={"X-Api-Key": clave}).status_code == 200
    assert client.get("/perfil/api-key").json()["api_key"] == clave


def test_cifrado_ilegible_no_tumba_nada():
    como("h-10")
    clave = client.get("/perfil/api-key").json()["api_key"]
    db = SessionLocal()
    try:
        db.execute(text("UPDATE perfiles SET api_key_enc = 'basura' WHERE usuario_id = 'h-10'"))
        db.commit()
    finally:
        db.close()
    r = client.get("/perfil/api-key").json()
    assert r["api_key"] is None and r["tiene_clave"] is True
    assert client.get(RUTA, headers={"X-Api-Key": clave}).status_code == 200


def test_regenerar_invalida_la_anterior_y_muestra_la_nueva():
    como("h-2")
    vieja = client.get("/perfil/api-key").json()["api_key"]
    nueva = client.post("/perfil/api-key/regenerar").json()["api_key"]
    assert nueva != vieja
    assert client.get(RUTA, headers={"X-Api-Key": vieja}).status_code == 401
    assert client.get(RUTA, headers={"X-Api-Key": nueva}).status_code == 200


def test_clave_antigua_en_claro_funciona_y_se_migra_al_primer_uso():
    db = SessionLocal()
    db.add(Perfil(usuario_id="h-3", plan="free", api_key="clave-vieja-en-claro"))
    db.commit()
    db.close()
    como("h-3")
    # Antes de usarla todavía se puede consultar completa.
    assert client.get("/perfil/api-key").json()["api_key"] == "clave-vieja-en-claro"
    assert client.get(RUTA, headers={"X-Api-Key": "clave-vieja-en-claro"}).status_code == 200
    api_key, h, _ = _fila("h-3")
    assert api_key is None and h == claves_api.hash_clave("clave-vieja-en-claro")
    # Sigue sirviendo ya como hash.
    assert client.get(RUTA, headers={"X-Api-Key": "clave-vieja-en-claro"}).status_code == 200


def test_sin_columna_hash_todo_sigue_en_claro(monkeypatch):
    monkeypatch.setattr(claves_api, "hay_columna_hash", lambda db: False)
    como("h-4")
    clave = client.get("/perfil/api-key").json()["api_key"]
    api_key, _, _ = _fila("h-4")
    assert api_key == clave  # modo antiguo, sin romperse
    assert client.get(RUTA, headers={"X-Api-Key": clave}).status_code == 200
