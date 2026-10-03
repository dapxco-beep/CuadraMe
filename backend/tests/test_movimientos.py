"""
Pruebas del flujo de movimientos y saldos con una base SQLite temporal.
Se salta la autenticación real de Supabase sobreescribiendo la dependencia
get_current_user, que es la forma estándar de probar endpoints en FastAPI.

Ejecutar desde backend/:  venv/Scripts/python.exe -m pytest tests -q
"""
import os
import tempfile

# Debe fijarse ANTES de importar la app: el engine se crea al importar.
_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _usuario_de_esta_suite():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id="user-1", email="a@test.com", nombre="Ana Pérez"
    )
    yield


def _cuenta(nombre, saldo=1000, moneda="COP"):
    r = client.post("/cuentas", json={"nombre": nombre, "saldo": saldo, "moneda": moneda})
    assert r.status_code == 200, r.text
    return r.json()


def _saldo(cuenta_id):
    return next(c["saldo"] for c in client.get("/cuentas").json() if c["id"] == cuenta_id)


@pytest.fixture()
def cuenta():
    return _cuenta("Cuenta test")


def test_tipo_invalido_se_rechaza(cuenta):
    r = client.post("/movimientos", json={
        "cuenta_id": cuenta["id"], "descripcion": "x", "monto": 10, "tipo": "regalo",
    })
    assert r.status_code == 422


def test_gasto_y_borrado_ajustan_saldo(cuenta):
    r = client.post("/movimientos", json={
        "cuenta_id": cuenta["id"], "descripcion": "Almuerzo", "monto": 300, "tipo": "expense",
    })
    assert r.status_code == 200
    assert _saldo(cuenta["id"]) == 700
    assert client.delete(f"/movimientos/{r.json()['id']}").status_code == 200
    assert _saldo(cuenta["id"]) == 1000


def test_editar_corrige_saldo_y_cambia_de_cuenta(cuenta):
    otra = _cuenta("Otra", saldo=500)
    mov = client.post("/movimientos", json={
        "cuenta_id": cuenta["id"], "descripcion": "Taxi", "monto": 100, "tipo": "expense",
    }).json()
    assert _saldo(cuenta["id"]) == 900

    r = client.put(f"/movimientos/{mov['id']}", json={"monto": 250, "cuenta_id": otra["id"]})
    assert r.status_code == 200
    assert _saldo(cuenta["id"]) == 1000  # se devolvió lo del movimiento viejo
    assert _saldo(otra["id"]) == 250  # 500 - 250

    r = client.put(f"/movimientos/{mov['id']}", json={"tipo": "income"})
    assert r.status_code == 200
    assert _saldo(otra["id"]) == 750  # 500 + 250


def test_transferencia_mueve_saldo_y_se_borra_completa(cuenta):
    destino = _cuenta("Destino", saldo=0)
    r = client.post("/movimientos/transferencia", json={
        "cuenta_origen_id": cuenta["id"], "cuenta_destino_id": destino["id"], "monto": 400,
    })
    assert r.status_code == 200, r.text
    assert _saldo(cuenta["id"]) == 600
    assert _saldo(destino["id"]) == 400

    movs = [m for m in client.get("/movimientos?limit=500").json() if m["fuente"] == "transferencia_interna"]
    assert len(movs) >= 2
    # Borrar una pata revierte las dos.
    una = next(m for m in movs if m["cuenta_id"] == destino["id"])
    assert client.delete(f"/movimientos/{una['id']}").status_code == 200
    assert _saldo(cuenta["id"]) == 1000
    assert _saldo(destino["id"]) == 0


def test_transferencia_a_la_misma_cuenta_falla(cuenta):
    r = client.post("/movimientos/transferencia", json={
        "cuenta_origen_id": cuenta["id"], "cuenta_destino_id": cuenta["id"], "monto": 1,
    })
    assert r.status_code == 400


def test_transferencia_entre_monedas_distintas_falla(cuenta):
    usd = _cuenta("Dólares", saldo=0, moneda="USD")
    r = client.post("/movimientos/transferencia", json={
        "cuenta_origen_id": cuenta["id"], "cuenta_destino_id": usd["id"], "monto": 1,
    })
    assert r.status_code == 400


def test_fechas_invalidas_dan_400_y_limit_tiene_tope(cuenta):
    assert client.get("/movimientos?desde=ayer").status_code == 400
    assert client.get("/movimientos?limit=100000").status_code == 422


def test_busqueda_trata_porcentaje_como_texto(cuenta):
    client.post("/movimientos", json={
        "cuenta_id": cuenta["id"], "descripcion": "Descuento 50% hoy", "monto": 1, "tipo": "expense",
    })
    r = client.get("/movimientos?q=50%25")
    assert r.status_code == 200
    assert any("50%" in m["descripcion"] for m in r.json())


def test_nombre_propio_depende_del_usuario():
    from app.conciliacion import es_transferencia_propia, fijar_nombre_titular

    fijar_nombre_titular("Ana Pérez")
    assert es_transferencia_propia("Enviaste a Ana Perez")
    fijar_nombre_titular("Luis Gómez")
    assert not es_transferencia_propia("Enviaste a Ana Perez")
