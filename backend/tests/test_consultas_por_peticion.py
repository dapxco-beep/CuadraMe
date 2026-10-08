"""Protección contra consultas N+1: el número de sentencias SQL de un endpoint NO debe crecer
con la cantidad de presupuestos, cuentas o meses (hallado con tools/prueba_carga.py)."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'consultas.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
USUARIO = UsuarioActual(id="consultas-1", email="q@test.com", nombre="Q")


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: USUARIO
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _contar(ruta: str) -> int:
    client.get(ruta)  # calentamiento: la primera vez algunos endpoints crean datos base
    n = {"sql": 0}

    def _cuenta(*a, **k):
        n["sql"] += 1

    event.listen(engine, "before_cursor_execute", _cuenta)
    try:
        r = client.get(ruta)
    finally:
        event.remove(engine, "before_cursor_execute", _cuenta)
    assert r.status_code == 200, r.text
    return n["sql"]


def _sembrar(n_presupuestos: int):
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "saldo": 1_000_000}).json()
    for i in range(n_presupuestos):
        assert client.post("/presupuestos", json={"categoria": f"Cat{i}", "limite": 100_000}).status_code == 200
    for i in range(12):
        client.post("/movimientos", json={"cuenta_id": cuenta["id"], "descripcion": f"gasto {i}", "monto": 1000,
                                          "tipo": "expense", "categoria": f"Cat{i % max(n_presupuestos, 1)}"})


def test_disponible_hoy_no_hace_una_consulta_por_presupuesto():
    _sembrar(2)
    con_2 = _contar("/presupuestos/disponible-hoy")
    for i in range(2, 22):
        client.post("/presupuestos", json={"categoria": f"Cat{i}", "limite": 100_000})
    con_22 = _contar("/presupuestos/disponible-hoy")
    assert con_22 == con_2, f"{con_2} consultas con 2 presupuestos y {con_22} con 22: hay un N+1"
    assert con_22 <= 10


def test_la_cuadricula_de_sincronizacion_usa_una_consulta_para_todos_los_meses():
    seis = _contar("/sincronizacion/estado?meses=6")
    veinticuatro = _contar("/sincronizacion/estado?meses=24")
    assert seis == veinticuatro, f"{seis} consultas para 6 meses y {veinticuatro} para 24: una por mes"


def test_otros_endpoints_de_lectura_tienen_tope_de_consultas():
    for ruta, tope in (("/cuentas", 6), ("/movimientos", 6), ("/presupuestos", 4), ("/reportes/mensual", 10),
                       ("/insights/alertas-proactivas", 10), ("/cuentas/resumen", 8)):
        assert _contar(ruta) <= tope, ruta
