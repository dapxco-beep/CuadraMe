"""Clave API guardada como hash SHA-256: se muestra completa solo al crear/regenerar,
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
def _ambiente():
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


def test_clave_nueva_se_muestra_una_vez_y_se_guarda_como_hash():
    como("h-1")
    r = client.get("/perfil/api-key").json()
    clave = r["api_key"]
    assert clave.startswith("cdm_") and r["nueva"] is True
    api_key, h, prefijo = _fila("h-1")
    assert api_key is None and h == claves_api.hash_clave(clave) and clave not in str(tuple(_fila("h-1")))
    assert prefijo == clave[:8] + "…"
    # La segunda vez ya no se puede ver completa.
    r2 = client.get("/perfil/api-key").json()
    assert r2["api_key"] is None and r2["tiene_clave"] is True and r2["prefijo"] == prefijo
    # Y sigue funcionando para el Atajo.
    assert client.get(RUTA, headers={"X-Api-Key": clave}).status_code == 200
    assert client.get(RUTA, headers={"X-Api-Key": clave + "x"}).status_code == 401


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
