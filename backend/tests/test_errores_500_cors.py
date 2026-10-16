"""Un error inesperado debe responder 500 CON cabeceras CORS (si no, el navegador lo muestra como «sin conexión»)."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'e500.db')}")

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402


@app.get("/_prueba_error_500")
def _explota():
    raise RuntimeError("columna inexistente de prueba")


def test_error_inesperado_sale_como_500_con_cors():
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/_prueba_error_500", headers={"Origin": settings.pwa_url})
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == settings.pwa_url
    assert "detail" in r.json()
