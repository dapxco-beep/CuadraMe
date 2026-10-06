"""Regresión: los promedios de plan-meta usan la regla contable central."""
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'planreg.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="plan-regla", email="r@test.com", nombre="R")
    yield


def test_promedios_historicos_ignoran_pago_de_tarjeta():
    """Un pago de tarjeta de $1.000.000 no infla el gasto promedio mensual."""
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "saldo": 5_000_000}).json()["id"]
    hoy = ahora_co()
    y, m = (hoy.year - 1, 12) if hoy.month == 1 else (hoy.year, hoy.month - 1)
    fecha = datetime(y, m, 10, 12).isoformat()
    for desc, monto, tipo, cat in (("Nómina", 3_000_000, "income", "Ingresos"),
                                   ("Mercado", 500_000, "expense", "Comida"),
                                   ("Pago tarjeta Visa", 1_000_000, "expense", "Otros")):
        client.post("/movimientos", json={"cuenta_id": cuenta, "descripcion": desc, "monto": monto,
                                          "tipo": tipo, "categoria": cat, "fecha": fecha})
    h = client.post("/planificacion/plan-meta", json={"objetivo": 1_000_000}).json()["historico"]
    assert h["gasto"] == pytest.approx(500_000)      # sin los 1.000.000 del pago
    assert h["ingreso"] == pytest.approx(3_000_000)
    assert h["ahorro"] == pytest.approx(2_500_000)
