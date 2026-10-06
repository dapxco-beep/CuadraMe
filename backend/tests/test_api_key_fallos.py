"""Tope de intentos fallidos de API key por IP (30 cada 10 minutos)."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'apikey.db')}")

from types import SimpleNamespace  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app import limites  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Perfil  # noqa: E402

client = TestClient(app)
RUTA = "/movimientos/cuentas-rapido"


def _con_ip(ip, clave="mala"):
    return {"X-Api-Key": clave, "X-Forwarded-For": f"{ip}, 10.0.0.1"}


def test_ip_cliente_usa_primer_valor_de_forwarded_y_respaldo_al_socket():
    req = SimpleNamespace(headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"}, client=SimpleNamespace(host="9.9.9.9"))
    assert limites.ip_cliente(req) == "1.2.3.4"
    req = SimpleNamespace(headers={}, client=SimpleNamespace(host="9.9.9.9"))
    assert limites.ip_cliente(req) == "9.9.9.9"
    assert limites.ip_cliente(SimpleNamespace(headers={}, client=None)) == "desconocida"


def test_30_fallos_bloquean_la_ip_con_429_legible_y_otras_ips_siguen():
    for _ in range(limites.FALLOS_API_KEY_MAX):
        assert client.get(RUTA, headers=_con_ip("7.7.7.7")).status_code == 401
    r = client.get(RUTA, headers=_con_ip("7.7.7.7"))
    assert r.status_code == 429
    assert r.json()["mensaje"].startswith("No se registró")  # formato legible de los atajos
    assert "Retry-After" in r.headers
    # Otra IP no se ve afectada.
    assert client.get(RUTA, headers=_con_ip("8.8.8.8")).status_code == 401


def test_la_ventana_expira(monkeypatch):
    for _ in range(limites.FALLOS_API_KEY_MAX):
        limites.registrar_fallo_api_key("6.6.6.6")
    real = limites.time.monotonic
    monkeypatch.setattr(limites.time, "monotonic", lambda: real() + 601)
    limites.bloquear_si_demasiados_fallos("6.6.6.6")  # no lanza


def test_los_aciertos_no_gastan_cupo():
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id="ak-1", plan="free", api_key="clave-buena-123"))
        db.commit()
    finally:
        db.close()
    for _ in range(limites.FALLOS_API_KEY_MAX + 5):
        assert client.get(RUTA, headers=_con_ip("5.5.5.5", "clave-buena-123")).status_code != 429
