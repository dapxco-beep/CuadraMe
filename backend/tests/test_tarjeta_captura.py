"""Captura de una tarjeta de crédito nueva y compras por el atajo (registro rápido)."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'capt.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _usuario():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-capt", email="c@t.com", nombre="C")
    yield


def test_tarjeta_nueva_con_deuda_guardada_en_negativo_deja_cupo_usado():
    # Lo que hace la PWA: el cliente escribe 1.200.000 (lo que debe) y se envía -1200000.
    r = client.post("/cuentas", json={
        "nombre": "Nu Crédito", "tipo": "credito", "saldo": -1_200_000, "cupo_total": 5_000_000,
        "dia_corte": 15, "dia_pago": 30, "tasa_ea": 28.5,
    })
    assert r.status_code == 200, r.text
    t = r.json()["tarjeta"]
    assert t["cupo_usado"] == 1_200_000
    assert t["cupo_disponible"] == 3_800_000
    assert t["utilizacion_pct"] == 24.0


def test_el_error_de_fondo_saldo_positivo_se_lee_como_a_favor():
    """Documenta por qué el formulario NO manda el número tal cual en una tarjeta."""
    r = client.post("/cuentas", json={"nombre": "Mal", "tipo": "credito", "saldo": 1_200_000, "cupo_total": 5_000_000})
    assert r.json()["tarjeta"]["cupo_usado"] == 0


def test_compra_con_la_tarjeta_por_alias_resta_y_sube_la_utilizacion():
    r = client.post("/cuentas", json={
        "nombre": "Visa Alias", "tipo": "credito", "saldo": -1_200_000, "cupo_total": 5_000_000,
        "alias_tarjeta": "Visa 9876",
    })
    assert r.status_code == 200, r.text
    key = client.get("/perfil/api-key").json()["api_key"]
    r = client.post("/movimientos/rapido", headers={"X-Api-Key": key}, json={
        "comercio": "Exito", "monto": "300.000,00", "tarjeta": "Visa ••9876", "moneda": "COP",
        "fecha": ahora_co().isoformat(),
    })
    assert r.status_code == 200, r.text
    tarjeta = next(c for c in client.get("/cuentas").json() if c["nombre"] == "Visa Alias")
    assert tarjeta["saldo"] == -1_500_000
    assert tarjeta["tarjeta"]["cupo_usado"] == 1_500_000
    assert tarjeta["tarjeta"]["utilizacion_pct"] == 30.0
