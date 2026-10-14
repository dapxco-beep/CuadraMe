"""Endpoints de /inversiones con SQLite temporal, sin red: proveedores simulados."""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'inv.db')}")
os.environ.setdefault("CRON_SECRET", "secreto-de-prueba")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import inversiones_calc as ic  # noqa: E402
from app import precios_ticker as pt  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import inversiones as mod  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="inv-1", email="i@test.com", nombre="I")}


class FalsoProveedor(pt.ProveedorCotizacion):
    nombre = "twelvedata"
    llamadas = 0
    precios = {"ECOPETROL": 2000.0}

    def disponible(self):
        return True

    def cotizar(self, ticker, mercado, tipo):
        FalsoProveedor.llamadas += 1
        p = self.precios.get(ticker)
        return {"precio": p, "moneda": "COP", "fecha": datetime.utcnow(), "anterior": 1900.0} if p else None


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    monkeypatch.setattr(mod, "fx_proveedor", ic.FXManual({"USD": 4000}))
    monkeypatch.setitem(pt.PROVEEDORES_COTIZACION, "twelvedata", FalsoProveedor())
    monkeypatch.setattr(settings, "cron_secret", "secreto-de-prueba", raising=False)
    FalsoProveedor.llamadas = 0
    yield


def como(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def test_vacio_y_validaciones():
    como("inv-vacio")
    j = client.get("/inversiones").json()
    assert j["tiene"] is False and j["posiciones"] == []
    assert client.post("/inversiones/brokers", json={"nombre": " "}).status_code == 422
    assert client.post("/inversiones/posiciones", json={"nombre": "X", "tipo": "bono"}).status_code == 422


def test_posicion_sin_broker_con_precio_por_ticker_y_espejo_en_patrimonio():
    como("inv-a")
    p = client.post("/inversiones/posiciones", json={
        "nombre": "Ecopetrol", "ticker": "ecopetrol", "mercado": "CL", "cantidad": 10, "costo_promedio": 1500}).json()
    assert p["precio"] is None and p["precio_estado"] == "sin_datos" and p["valor"] is None
    r = client.post("/inversiones/precios/actualizar").json()
    assert r["resumen"] == {"ok": 1}
    d = client.get(f"/inversiones/posiciones/{p['id']}").json()
    assert d["precio"] == 2000 and d["valor"] == 20000 and d["no_realizada"] == 5000
    assert d["hoy_cop"] == pytest.approx(1000)
    # Caché: una segunda actualización inmediata no vuelve a pedir
    llamadas = FalsoProveedor.llamadas
    assert client.post("/inversiones/precios/actualizar").json()["resumen"] == {"cache": 1}
    assert FalsoProveedor.llamadas == llamadas
    # Sin doble conteo: aparece UNA vez en Patrimonio, con el mismo valor
    pat = client.get("/patrimonio").json()
    espejos = [a for a in pat["activos"] if a["ticker"] == "ECOPETROL"]
    assert len(espejos) == 1 and espejos[0]["valor"] == 20000
    assert pat["total_activos"] == 20000


def test_ticker_inexistente_y_precio_manual():
    como("inv-b")
    p = client.post("/inversiones/posiciones", json={"nombre": "Rara", "ticker": "ZZZZ", "cantidad": 2,
                                                     "costo_promedio": 10}).json()
    client.post("/inversiones/precios/actualizar")
    d = client.get(f"/inversiones/posiciones/{p['id']}").json()
    assert d["precio"] is None and "Sin datos" in d["precio_mensaje"]
    m = client.post(f"/inversiones/posiciones/{p['id']}/precio-manual", json={"precio": 15}).json()
    assert m["valor"] == 30 and m["precio_estado"] == "manual"


def test_transacciones_aporte_enlazado_neutral_y_dividendo_ingreso():
    como("inv-c")
    cta = client.post("/cuentas", json={"nombre": "Banco", "saldo": 1_000_000}).json()
    b = client.post("/inversiones/brokers", json={"nombre": "Trii", "tipo": "acciones"}).json()
    p = client.post("/inversiones/posiciones", json={"nombre": "VOO", "ticker": "VOO", "mercado": "US",
                                                     "tipo": "etf", "moneda": "USD", "broker_id": b["id"]}).json()
    r = client.post(f"/inversiones/posiciones/{p['id']}/transacciones", json={
        "tipo": "compra", "cantidad": 1, "precio": 100, "cuenta_id": cta["id"], "monto_cuenta": 400_000})
    assert r.status_code == 200 and r.json()["cantidad"] == 1
    movs = client.get("/movimientos").json()
    movs = movs if isinstance(movs, list) else movs.get("items", movs.get("movimientos", []))
    inv = [m for m in movs if "Inversiones" in m["descripcion"]]
    assert inv and inv[0]["tipo"] == "transfer" and inv[0]["categoria"] == "Transferencia"
    client.post(f"/inversiones/posiciones/{p['id']}/transacciones", json={
        "tipo": "dividendo", "monto": 5, "cuenta_id": cta["id"], "monto_cuenta": 20_000})
    saldo = [c for c in client.get("/cuentas").json() if c["id"] == cta["id"]][0]["saldo"]
    assert saldo == 1_000_000 - 400_000 + 20_000
    movs = client.get("/movimientos").json()
    movs = movs if isinstance(movs, list) else movs.get("items", movs.get("movimientos", []))
    div = [m for m in movs if m["categoria"] == "Rendimientos"]
    assert div and div[0]["tipo"] == "income"
    # vender de más se rechaza
    assert client.post(f"/inversiones/posiciones/{p['id']}/transacciones",
                       json={"tipo": "venta", "cantidad": 5, "precio": 100}).status_code == 422
    # borrar la compra deshace el movimiento y el saldo
    d = client.get(f"/inversiones/posiciones/{p['id']}").json()
    compra = [t for t in d["transacciones"] if t["tipo"] == "compra"][0]
    assert client.delete(f"/inversiones/transacciones/{compra['id']}").status_code == 200
    saldo = [c for c in client.get("/cuentas").json() if c["id"] == cta["id"]][0]["saldo"]
    assert saldo == 1_000_000 + 20_000


def test_moneda_en_resumen():
    como("inv-d")
    client.post("/inversiones/posiciones", json={"nombre": "AAPL", "ticker": "AAPL", "mercado": "US",
                                                 "moneda": "USD", "cantidad": 2, "costo_promedio": 100,
                                                 "precio_manual": 110})
    j = client.get("/inversiones").json()
    assert j["valor_total"] == 2 * 110 * 4000
    assert j["no_realizada"] == 2 * 10 * 4000


def test_importar_csv_vista_previa_y_aplicar():
    como("inv-e")
    texto = "ticker,cantidad,costo\nAAPL,3,150.5\n,1,2\nMSFT,x,3\n"
    v = client.post("/inversiones/importar", json={"csv": texto, "moneda": "USD"}).json()
    assert v["validas"] == 1 and v["creadas"] == 0 and sum(1 for f in v["filas"] if f["error"]) == 2
    assert client.get("/inversiones").json()["posiciones"] == []
    a = client.post("/inversiones/importar", json={"csv": texto, "moneda": "USD", "aplicar": True}).json()
    assert a["creadas"] == 1
    assert len(client.get("/inversiones").json()["posiciones"]) == 1
    assert client.post("/inversiones/importar", json={"csv": "a,b\n1,2"}).status_code == 422


def test_topes_de_peticiones(monkeypatch):
    como("inv-f")
    monkeypatch.setenv("INVERSIONES_TOPE_USUARIO_DIA", "1")
    for t in ("TOPEAAA", "TOPEBBB"):
        client.post("/inversiones/posiciones", json={"nombre": t, "ticker": t, "mercado": "CL"})
    r = client.post("/inversiones/precios/actualizar").json()
    assert r["resumen"].get("tope_usuario") == 1 and "máximo" in r["mensaje"]


def test_cron_requiere_secreto_e_idempotente():
    como("inv-g")
    client.post("/inversiones/posiciones", json={"nombre": "Eco", "ticker": "ECOPETROL", "mercado": "CL"})
    assert client.post("/inversiones/cron/actualizar-precios").status_code == 401
    h = {"X-Cron-Secret": "secreto-de-prueba"}
    assert client.post("/inversiones/cron/actualizar-precios", headers=h).status_code == 200
    n = FalsoProveedor.llamadas
    client.post("/inversiones/cron/actualizar-precios", headers=h)
    assert FalsoProveedor.llamadas == n  # caché: no repite la petición


def test_aislamiento():
    como("inv-h1")
    p = client.post("/inversiones/posiciones", json={"nombre": "Mía", "cantidad": 1, "costo_promedio": 5}).json()
    como("inv-h2")
    assert client.get(f"/inversiones/posiciones/{p['id']}").status_code == 404
    assert client.delete(f"/inversiones/posiciones/{p['id']}").status_code == 404
    assert client.get("/inversiones").json()["posiciones"] == []
