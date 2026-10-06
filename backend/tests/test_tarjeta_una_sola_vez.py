"""La deuda de una tarjeta de crédito cuenta UNA sola vez en patrimonio (ya está restada
en la cuenta de la tarjeta; si además se registró como Deuda 'tarjeta' no se suma otra vez)."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'unavez.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.patrimonio_calc import deudas_duplicadas_de_tarjetas  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _usuario():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-unavez", email="u@t.com", nombre="U")
    yield


def d(id, tipo, nombre, entidad=""):
    return {"id": id, "tipo": tipo, "nombre": nombre, "entidad": entidad}


def test_deteccion_por_palabra_distintiva_e_ignora_genericas():
    tarjetas = [{"nombre": "Bancolombia Crédito"}, {"nombre": "Nu Colombia Crédito"}]
    assert deudas_duplicadas_de_tarjetas([d("1", "tarjeta", "Visa Bancolombia")], tarjetas) == ["1"]
    assert deudas_duplicadas_de_tarjetas([d("2", "tarjeta", "Tarjeta Nu")], tarjetas) == ["2"]
    assert deudas_duplicadas_de_tarjetas([d("3", "tarjeta", "Tarjeta de crédito Visa", "Davivienda")], tarjetas) == []  # otro banco
    assert deudas_duplicadas_de_tarjetas([d("4", "tarjeta", "Tarjeta de crédito Visa")], tarjetas) == []  # solo genéricas
    # un préstamo del mismo banco NO es la tarjeta
    assert deudas_duplicadas_de_tarjetas([d("5", "credito", "Libranza Bancolombia", "Bancolombia")], tarjetas) == []
    assert deudas_duplicadas_de_tarjetas([d("6", "tarjeta", "Visa Bancolombia")], []) == []  # sin tarjeta con deuda


def test_patrimonio_no_suma_dos_veces_la_deuda_de_la_tarjeta():
    client.post("/cuentas", json={"nombre": "Ahorros Bancolombia", "saldo": 300_000})
    client.post("/cuentas", json={"nombre": "Bancolombia Crédito", "tipo": "credito", "saldo": -1_000_000, "cupo_total": 3_000_000})
    # La misma tarjeta registrada además como deuda + un préstamo de verdad
    assert client.post("/deudas", json={"nombre": "Visa Bancolombia", "tipo": "tarjeta", "saldo_inicial": 1_000_000}).status_code == 200
    assert client.post("/deudas", json={"nombre": "Moto", "tipo": "credito", "saldo_inicial": 500_000}).status_code == 200

    p = client.get("/patrimonio").json()
    assert p["total_cuentas"] == -700_000  # 300.000 - 1.000.000 (la tarjeta ya resta aquí)
    assert p["total_deudas"] == 500_000  # solo la moto
    assert p["deudas_tarjeta"] == 1_000_000
    assert [x["nombre"] for x in p["pasivos"]] == ["Moto"]
    assert [x["nombre"] for x in p["pasivos_duplicados"]] == ["Visa Bancolombia"]
    assert p["patrimonio_neto"] == -1_200_000  # -700.000 - 500.000 (y NO -2.200.000)


def test_sin_duplicados_nada_cambia():
    otro = UsuarioActual(id="u-unavez-2", email="u2@t.com", nombre="U2")
    app.dependency_overrides[get_current_user] = lambda: otro
    client.post("/cuentas", json={"nombre": "Nu Crédito", "tipo": "credito", "saldo": -200_000})
    client.post("/deudas", json={"nombre": "Tarjeta Falabella", "tipo": "tarjeta", "saldo_inicial": 400_000})
    p = client.get("/patrimonio").json()
    assert p["total_deudas"] == 400_000 and p["pasivos_duplicados"] == [] and p["patrimonio_neto"] == -600_000
