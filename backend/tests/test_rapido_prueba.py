"""POST /movimientos/rapido-prueba: probar la conexión con la sesión, sin leer la clave guardada."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'rapidoprueba.db')}")

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_rapido_prueba_crea_movimiento_por_confirmar_con_la_sesion():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="rp-1", email="r@t.co", nombre="R")
    try:
        client.post("/cuentas", json={"nombre": "Efectivo", "saldo": 10000})
        body = {"comercio": "Pago de prueba CuadraMe", "monto": "1.000", "tarjeta": "Prueba CuadraMe",
                "moneda": "COP", "fuente": "wallet"}
        r = client.post("/movimientos/rapido-prueba", json=body)
        assert r.status_code == 200, r.text
        ids = [m["id"] for m in client.get("/movimientos/por-confirmar").json()]
        assert r.json()["id"] in ids
    finally:
        app.dependency_overrides.pop(get_current_user, None)
