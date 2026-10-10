"""Compresión gzip y permiso CORS recordado (rendimiento en datos móviles)."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'compresion.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
U = UsuarioActual(id="comp-usuario", email="comp@test.com", nombre="Comp")


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: U
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_respuesta_grande_sale_comprimida_y_conserva_las_cabeceras_de_seguridad():
    # La lista de categorías por defecto pasa de 1 KB.
    r = client.get("/categorias", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"
    assert r.headers["cache-control"] == "no-store"  # la política de seguridad sigue intacta
    assert r.headers["x-content-type-options"] == "nosniff"
    assert isinstance(r.json(), list)  # y descomprime bien


def test_sin_accept_encoding_no_se_comprime():
    r = client.get("/categorias", headers={"Accept-Encoding": "identity"})
    assert r.status_code == 200
    assert "content-encoding" not in r.headers


def test_respuesta_pequena_no_se_comprime():
    r = client.get("/health", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert "content-encoding" not in r.headers


def test_preflight_cors_se_recuerda_por_horas():
    r = client.options(
        "/cuentas",
        headers={
            "Origin": settings.pwa_url,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert r.status_code == 200
    assert int(r.headers["access-control-max-age"]) >= 3600
