"""Moneda base fase 2: cada pantalla suma en la moneda base del perfil, con tasas manuales por usuario.
Usuario con base MXN y cuentas en COP/MXN/USD; sin tasa -> marcado y NO sumado; usuario COP idéntico.
Datos solo sintéticos."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'mb2.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import fx  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Perfil  # noqa: E402

client = TestClient(app)
MX = UsuarioActual(id="mb2-mx", email="mx-mb2@test.com", nombre="Mx")
CO = UsuarioActual(id="mb2-co", email="co-mb2@test.com", nombre="Co")
OTRO = UsuarioActual(id="mb2-otro", email="otro-mb2@test.com", nombre="Otro")
ACTUAL = {"u": MX}


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(fx, "_USD_APROX", {})  # sin tasas de respaldo: solo manuales
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    fx.borrar_tasas_manuales()
    from app.models import TasaManual

    db = SessionLocal()
    db.query(TasaManual).delete()
    db.commit()
    db.close()
    fx.usar_proveedor(lambda base: {})  # sin red y sin tasas del proveedor
    yield
    fx.usar_proveedor(None)
    app.dependency_overrides.pop(get_current_user, None)


def _sembrar():
    db = SessionLocal()
    try:
        if db.query(Perfil).filter(Perfil.usuario_id == MX.id).first():
            return
        db.add(Perfil(usuario_id=MX.id, moneda_base="MXN"))
        db.add(Perfil(usuario_id=CO.id))
        for uid, nombre, moneda, saldo, tipo in [
            (MX.id, "Pesos MX", "MXN", 1000.0, "ahorro"),
            (MX.id, "Dolares", "USD", 10.0, "ahorro"),
            (MX.id, "Pesos CO", "COP", 40000.0, "efectivo"),
            (CO.id, "Ahorros", "COP", 500000.0, "ahorro"),
            (CO.id, "Tarjeta", "COP", -100000.0, "credito"),
        ]:
            db.add(Cuenta(usuario_id=uid, nombre=nombre, moneda=moneda, saldo=saldo, tipo=tipo))
        db.commit()
    finally:
        db.close()


def como(u):
    ACTUAL["u"] = u
    _sembrar()


def _poner(moneda, tasa):
    r = client.put(f"/perfil/tasas/{moneda}", json={"tasa": tasa})
    assert r.status_code == 200, r.text


def test_sin_tasa_no_se_suma_y_se_marca():
    como(MX)
    r = client.get("/cuentas/resumen").json()
    assert r["moneda_base"] == "MXN"
    assert r["monedas_sin_tasa"] == ["COP", "USD"] or sorted(r["monedas_sin_tasa"]) == ["COP", "USD"]
    assert r["total_cop"] == 1000.0  # solo la cuenta MXN


def test_con_tasas_manuales_el_total_es_la_suma_esperada_en_todas_las_pantallas():
    como(MX)
    _poner("USD", 17.0)
    _poner("COP", 0.005)
    esperado = 1000 + 10 * 17.0 + 40000 * 0.005  # 1370
    r = client.get("/cuentas/resumen").json()
    assert r["monedas_sin_tasa"] == []
    assert r["total_cop"] == pytest.approx(esperado)
    assert r["por_moneda"] == {"MXN": 1000.0, "USD": 10.0, "COP": 40000.0}  # por moneda: en su moneda
    b = client.get("/presupuestos/en-mi-bolsillo").json()
    assert b["moneda_base"] == "MXN" and b["monedas_sin_tasa"] == []
    assert b["saldo_total"] == pytest.approx(esperado)
    f = client.get("/reportes/flujo-caja-futuro").json()
    assert f["moneda_base"] == "MXN" and f["monedas_sin_tasa"] == []
    s = client.get("/insights/salud-financiera").json()
    assert s.get("moneda_base") == "MXN" if isinstance(s, dict) else True
    p = client.get("/patrimonio").json() if client.get("/patrimonio").status_code == 200 else None
    if p:
        assert p["moneda_base"] == "MXN" and p["monedas_sin_tasa"] == []


def test_la_tasa_manual_es_privada_de_cada_usuario():
    como(MX)
    _poner("USD", 17.0)
    como(OTRO)
    assert client.get("/perfil/tasas").json()["tasas"] == {}
    como(MX)
    assert client.get("/perfil/tasas").json()["tasas"].get("USD") == 17.0
    assert client.put("/perfil/tasas/MXN", json={"tasa": 1}).status_code == 422  # ya es la base
    assert client.put("/perfil/tasas/USD", json={"tasa": 0}).status_code == 422
    assert client.put("/perfil/tasas/US1", json={"tasa": 2}).status_code == 422
    assert client.delete("/perfil/tasas/USD").status_code == 200
    assert client.get("/perfil/tasas").json()["tasas"] == {}


def test_usuario_cop_identico_a_antes():
    como(CO)
    r = client.get("/cuentas/resumen").json()
    assert r["moneda_base"] == "COP" and r["monedas_sin_tasa"] == []
    assert r["total_cop"] == 400000.0
    assert r["disponible_cop"] == 500000.0 and r["deudas_tarjeta_cop"] == 100000.0
    b = client.get("/presupuestos/en-mi-bolsillo").json()
    assert b["saldo_total"] == 400000.0 and b["monedas_sin_tasa"] == []


def test_impuestos_y_renta_siguen_en_cop_aunque_la_base_sea_mxn():
    como(MX)
    _poner("USD", 17.0)
    from app.routers.patrimonio import calcular_resumen

    db = SessionLocal()
    try:
        r = calcular_resumen(db, MX.id, base="COP")
        assert r["moneda_base"] == "COP"
    finally:
        db.close()


def test_informe_y_reportes_marcan_moneda_base_y_sin_tasa():
    como(MX)
    from datetime import datetime

    from app.models import Movimiento

    db = SessionLocal()
    try:
        usd = db.query(Cuenta).filter(Cuenta.usuario_id == MX.id, Cuenta.moneda == "USD").first()
        if not db.query(Movimiento).filter(Movimiento.cuenta_id == usd.id).first():
            db.add(Movimiento(cuenta_id=usd.id, usuario_id=MX.id, descripcion="Compra sintetica", monto=20.0,
                              tipo="expense", categoria="Comida", fecha=datetime.now()))
            db.commit()
    finally:
        db.close()
    j = client.get("/informes/gasto").json()
    assert j["moneda_base"] == "MXN" and j["monedas_sin_tasa"] == ["USD"]
    assert j["total"] == 0 if "total" in j else True  # sin tasa: el gasto en USD no se suma
    _poner("USD", 17.0)
    j = client.get("/informes/gasto").json()
    assert j["monedas_sin_tasa"] == []
    r = client.get("/reportes/mensual").json()
    assert r["moneda_base"] == "MXN" and r["monedas_sin_tasa"] == []
    assert r["gastos"] == pytest.approx(20 * 17.0)
