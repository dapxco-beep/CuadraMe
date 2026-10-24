"""Avisos nuevos del Inicio: cuenta en negativo y gasto fuera de lo normal. Datos inventados."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'recsg.db')}")

from datetime import timedelta  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
USUARIO = {"u": UsuarioActual(id="rsg-0", email="r@test.com", nombre="R")}


@pytest.fixture(autouse=True)
def _usuario():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["u"]
    yield


def como(uid):
    USUARIO["u"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def _cuenta(nombre, tipo="ahorro", saldo=0):
    return client.post("/cuentas", json={"nombre": nombre, "tipo": tipo, "saldo": saldo}).json()["id"]


def _gasto(cuenta, monto, dias_atras, desc="Compra"):
    fecha = (ahora_co() - timedelta(days=dias_atras)).strftime("%Y-%m-%dT12:00:00")
    r = client.post("/movimientos", json={"cuenta_id": cuenta, "tipo": "expense", "monto": monto, "descripcion": desc,
                                          "categoria": "Otros", "fecha": fecha, "confirmar_nuevo": True})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _tipos():
    return {r["tipo"]: r for r in client.get("/recordatorios").json()}


def test_cuenta_en_negativo_avisa_pero_una_tarjeta_endeudada_no():
    como("rsg-1")
    _cuenta("Nequi", "ahorro", -980_119)
    _cuenta("Nu Crédito", "credito", -500_000)
    _cuenta("Efectivo", "efectivo", 300_000)
    lista = [r for r in client.get("/recordatorios").json() if r["tipo"] == "saldo_negativo"]
    assert len(lista) == 1 and "Nequi" in lista[0]["titulo"] and "980.119" in lista[0]["texto"]


def test_gasto_grande_se_avisa_sobre_tu_gasto_tipico():
    como("rsg-2")
    c = _cuenta("Nu", "ahorro", 10_000_000)
    for i in range(10):
        _gasto(c, 20_000 + i * 1000, 10 + i * 5)  # gasto típico ~25.000, todo anterior a los últimos 3 días
    grande = _gasto(c, 2_785_231, 1, "Macbook")
    pequeno = _gasto(c, 90_000, 1, "Mercado")
    r = _tipos()
    assert r["gasto_grande"]["clave"] == f"gasto_grande:{grande}"
    assert r["gasto_grande"]["ruta"] == f"/movimientos/{grande}"
    assert pequeno not in str(r["gasto_grande"])


def test_sin_historia_suficiente_no_adivina():
    como("rsg-3")
    c = _cuenta("Nu", "ahorro", 10_000_000)
    for i in range(3):
        _gasto(c, 20_000, 20 + i)
    _gasto(c, 2_000_000, 1, "Algo grande")
    assert "gasto_grande" not in _tipos()


def test_un_gasto_grande_normal_para_ti_no_avisa():
    como("rsg-4")
    c = _cuenta("Nu", "ahorro", 90_000_000)
    for i in range(10):
        _gasto(c, 1_500_000, 10 + i * 5, "Arriendo o similar")  # lo típico ya es grande
    _gasto(c, 1_600_000, 1)
    assert "gasto_grande" not in _tipos()
