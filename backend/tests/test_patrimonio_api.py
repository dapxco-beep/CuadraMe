"""Endpoints de /patrimonio con base SQLite temporal. La conversión de moneda se
simula (1 USD = 4.000 COP, 1 EUR = 5.000 COP) para no salir a la red."""
import os
import tempfile
from datetime import timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'patrimonio.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import patrimonio as mod  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="pat-1", email="p@test.com", nombre="P")}
TASAS = {"COP": 1, "USD": 4000, "EUR": 5000}


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    from app import fx
    monkeypatch.setattr(fx, "tasa", lambda o, b: (TASAS[o] / TASAS[b], None, "prueba"))
    yield


def como(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def iso(dt):
    return dt.isoformat()


def test_usuario_nuevo_resumen_vacio():
    como("pat-vacio")
    r = client.get("/patrimonio")
    assert r.status_code == 200
    j = r.json()
    assert j["patrimonio_neto"] == 0 and j["activos"] == [] and j["historial"] == []


def test_validaciones():
    como("pat-val")
    assert client.post("/patrimonio/activos", json={"clase": "bono", "nombre": "x"}).status_code == 422
    assert client.post("/patrimonio/activos", json={"clase": "cdt", "nombre": "x"}).status_code == 422
    assert client.post("/patrimonio/activos", json={"clase": "accion", "nombre": "x", "moneda": "JPY"}).status_code == 422
    assert client.post("/patrimonio/activos", json={"clase": "inmueble", "nombre": "Casa"}).status_code == 422
    hoy = ahora_co()
    malo = {"clase": "cdt", "nombre": "x", "capital": 1000, "tasa_ea": 10,
            "fecha_inicio": iso(hoy), "fecha_vencimiento": iso(hoy - timedelta(days=1))}
    assert client.post("/patrimonio/activos", json=malo).status_code == 422


def test_patrimonio_neto_completo_con_monedas():
    como("pat-full")
    hoy = ahora_co()
    client.post("/cuentas", json={"nombre": "Banco", "saldo": 1_000_000})
    client.post("/cuentas", json={"nombre": "Wise", "saldo": 100, "moneda": "USD"})  # 400.000 COP
    client.post("/deudas", json={"nombre": "Tarjeta", "saldo_inicial": 300_000})
    # CDT iniciado hace 365 días al 12 % -> hoy 1.120.000
    cdt = client.post("/patrimonio/activos", json={
        "clase": "cdt", "nombre": "CDT Bancolombia", "capital": 1_000_000, "tasa_ea": 12,
        "fecha_inicio": iso(hoy - timedelta(days=365)),
        "fecha_vencimiento": iso(hoy + timedelta(days=365))}).json()
    assert cdt["valor"] == pytest.approx(1_120_000, rel=1e-3)
    assert cdt["valor_vencimiento"] == pytest.approx(1_000_000 * 1.12 ** 2, rel=1e-3)
    assert cdt["xirr_pct"] == pytest.approx(12.0, abs=0.05)
    # 10 unidades de ETF en USD: costo 100, precio 110 -> 1.100 USD = 4.400.000 COP
    etf = client.post("/patrimonio/activos", json={
        "clase": "etf", "nombre": "VOO", "moneda": "USD", "unidades": 10,
        "costo_promedio": 100, "precio_actual": 110}).json()
    assert etf["valor"] == 1100 and etf["ganancia"] == 100
    assert etf["rentabilidad_pct"] == pytest.approx(10.0)
    assert etf["xirr_pct"] is None  # sin flujos
    client.post("/patrimonio/activos", json={"clase": "inmueble", "nombre": "Apto",
                                             "precio_actual": 200_000_000, "costo_adquisicion": 150_000_000})

    r = client.get("/patrimonio").json()
    activos = 1_120_000 + 4_400_000 + 200_000_000
    assert r["total_cuentas"] == pytest.approx(1_400_000)
    assert r["total_deudas"] == 300_000
    assert r["total_activos"] == pytest.approx(activos, rel=1e-3)
    assert r["patrimonio_neto"] == pytest.approx(activos + 1_400_000 - 300_000, rel=1e-3)
    assert sum(f["pct"] for f in r["distribucion"]) == pytest.approx(100.0)
    assert r["distribucion"][0]["clase"] == "inmueble"
    assert len(r["historial"]) == 1  # snapshot perezoso del mes en curso
    assert r["historial"][0]["patrimonio_neto"] == pytest.approx(r["patrimonio_neto"])
    assert len(client.get("/patrimonio").json()["historial"]) == 1  # no duplica


def test_xirr_con_flujos_y_valor_historico():
    como("pat-xirr")
    hoy = ahora_co()
    a = client.post("/patrimonio/activos", json={
        "clase": "fondo", "nombre": "Fondo X", "unidades": 100, "costo_promedio": 10,
        "precio_actual": 10}).json()
    # aporte de 1.000 hace 365 días; hoy vale 100 u * 11 = 1.100 -> 10 % E.A.
    client.post(f"/patrimonio/activos/{a['id']}/flujos", json={"monto": -1000, "fecha": iso(hoy - timedelta(days=365))})
    ed = client.post(f"/patrimonio/activos/{a['id']}/valor", json={"valor": 11}).json()
    assert ed["valor"] == 1100
    assert ed["xirr_pct"] == pytest.approx(10.0, abs=0.05)
    assert len(client.get(f"/patrimonio/activos/{a['id']}/valores").json()) == 2  # inicial + nuevo
    assert client.post(f"/patrimonio/activos/{a['id']}/flujos", json={"monto": 0}).status_code == 422


def test_editar_y_borrar_activo_y_aislamiento():
    como("pat-dueno")
    a = client.post("/patrimonio/activos", json={"clase": "vehiculo", "nombre": "Carro",
                                                  "precio_actual": 50_000_000}).json()
    como("pat-intruso")
    assert client.put(f"/patrimonio/activos/{a['id']}", json={"clase": "vehiculo", "nombre": "Mío",
                                                              "precio_actual": 1}).status_code == 404
    assert client.delete(f"/patrimonio/activos/{a['id']}").status_code == 404
    assert client.get("/patrimonio").json()["activos"] == []
    como("pat-dueno")
    e = client.put(f"/patrimonio/activos/{a['id']}", json={"clase": "vehiculo", "nombre": "Carro",
                                                            "precio_actual": 45_000_000}).json()
    assert e["valor"] == 45_000_000
    assert client.delete(f"/patrimonio/activos/{a['id']}").json() == {"ok": True}
    assert client.get("/patrimonio/activos").json() == []


def test_cron_snapshot_requiere_secreto_y_guarda():
    como("pat-cron")
    client.post("/cuentas", json={"nombre": "Banco", "saldo": 500})
    assert client.post("/patrimonio/cron/snapshot-mensual").status_code == 401
    r = client.post("/patrimonio/cron/snapshot-mensual", headers={"X-Cron-Secret": "secreto-de-prueba"})
    assert r.status_code == 200 and r.json()["guardados"] >= 1
    h = client.get("/patrimonio/historial").json()
    assert h and h[-1]["patrimonio_neto"] == 500
    r2 = client.post("/patrimonio/cron/actualizar-precios", headers={"X-Cron-Secret": "secreto-de-prueba"})
    assert r2.json()["actualizados"] == 0
