"""Saldo inicial automático. Datos 100 % inventados.

Patrón: una cuenta de ahorros se creó con saldo 0 y solo tiene los movimientos importados de mayo en adelante, pero el
extracto de mayo dice que el banco abrió con 500.000. Sin ese saldo inicial, el saldo de la cuenta queda 500.000 por debajo.
"""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'saldo_ini_auto.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import saldo_inicial_auto as sia  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, HistorialExtracto, Movimiento  # noqa: E402

client = TestClient(app)
USUARIO = {"u": UsuarioActual(id="sia-0", email="s@test.com", nombre="Sia")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["u"]
    yield


def como(uid):
    USUARIO["u"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def _mov(cuenta, tipo, monto, fecha, desc="x"):
    r = client.post("/movimientos", json={"cuenta_id": cuenta, "tipo": tipo, "monto": monto, "descripcion": desc,
                                          "categoria": "Otros", "fecha": fecha, "confirmar_nuevo": True})
    assert r.status_code in (200, 201), r.text


def _hist(uid, cuenta, *, ini, fin, inicio, corte, origen="extracto"):
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta, banco_detectado="prueba", estado="pendiente_revision",
                              review_json="[]", saldo_inicial_extracto=ini, saldo_final_extracto=fin,
                              periodo_inicio=inicio, fecha_corte=corte, saldos_origen=origen)
        db.add(h)
        db.commit()
        return h.id
    finally:
        db.close()


def _saldo(cuenta):
    return next(c for c in client.get("/cuentas").json() if c["id"] == cuenta)["saldo"]


def _escenario(uid, tipo="ahorro", origen="extracto", saldo=0):
    como(uid)
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "tipo": tipo, "saldo": saldo}).json()["id"]
    _mov(cuenta, "income", 300_000, "2026-05-05T10:00:00", "Pago")
    _mov(cuenta, "expense", 100_000, "2026-05-10T10:00:00", "Compra")
    _hist(uid, cuenta, ini=500_000, fin=700_000, inicio="2026-05-01", corte="2026-05-31", origen=origen)
    return cuenta


def _registrar():
    r = client.post("/conciliacion/cuadre/saldo-inicial-auto")
    assert r.status_code == 200, r.text
    return r.json()["registrados"]


def test_registra_solo_y_el_saldo_queda_bien():
    cuenta = _escenario("sia-1")
    assert _saldo(cuenta) == 200_000  # sin saldo inicial: 500.000 por debajo del banco
    reg = _registrar()
    assert len(reg) == 1 and reg[0]["monto"] == 500_000 and reg[0]["fecha"] == "2026-04-30"
    assert "Registré con cuánto empezó tu cuenta" in reg[0]["texto"] and "$500.000" in reg[0]["texto"]
    assert _saldo(cuenta) == 700_000  # saldo inicial + movimientos = lo que dice el extracto
    db = SessionLocal()
    try:
        m = db.get(Movimiento, reg[0]["movimiento_id"])
        assert m.fuente == "ajuste_saldo" and m.notas.endswith("automático")
    finally:
        db.close()


def test_no_cuenta_como_ingreso_ni_gasto_y_el_mes_cuadra():
    cuenta = _escenario("sia-2")
    _registrar()
    r = client.get(f"/conciliacion/cuadre/encadenado?cuenta_id={cuenta}").json()
    assert r["cuadra"] is True and r["meses"][0]["estado"] == "cuadra"
    ig = client.get("/informes/ingresos-gastos?desde=2026-04-01&hasta=2026-05-31")
    if ig.status_code == 200:  # el saldo inicial no suma 500.000 de ingreso
        assert ig.json().get("ingresos") == 300_000


def test_idempotente_nunca_duplica():
    cuenta = _escenario("sia-3")
    assert len(_registrar()) == 1
    assert _registrar() == [] and _registrar() == []
    assert _saldo(cuenta) == 700_000
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta, Movimiento.fuente == "ajuste_saldo").count() == 1
    finally:
        db.close()


def test_deshacer_y_no_se_vuelve_a_crear():
    cuenta = _escenario("sia-4")
    mov_id = _registrar()[0]["movimiento_id"]
    r = client.post("/conciliacion/cuadre/deshacer", json={"movimiento_id": mov_id, "confirmar": True})
    assert r.status_code == 200
    assert _saldo(cuenta) == 200_000
    assert _registrar() == []  # la persona lo deshizo: se respeta
    assert _saldo(cuenta) == 200_000


def test_tarjeta_no_recibe_saldo_inicial_automatico():
    cuenta = _escenario("sia-5", tipo="credito")
    assert _registrar() == []
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta, Movimiento.fuente == "ajuste_saldo").count() == 0
    finally:
        db.close()


def test_con_movimientos_anteriores_al_extracto_no_hace_nada():
    como("sia-6")
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "tipo": "ahorro", "saldo": 0}).json()["id"]
    _mov(cuenta, "income", 80_000, "2026-04-15T10:00:00", "Anterior")
    _mov(cuenta, "income", 300_000, "2026-05-05T10:00:00", "Pago")
    _hist("sia-6", cuenta, ini=500_000, fin=800_000, inicio="2026-05-01", corte="2026-05-31")
    assert _registrar() == []


def test_saldo_fijado_a_mano_en_la_cuenta_se_respeta():
    cuenta = _escenario("sia-7", saldo=120_000)  # la persona creó la cuenta con un saldo propio
    assert _registrar() == []
    assert _saldo(cuenta) == 320_000


def test_extracto_sin_saldo_inicial_o_de_origen_tabla_no_cuenta():
    cuenta = _escenario("sia-8", origen="tabla")
    assert _registrar() == []
    como("sia-8b")
    c2 = client.post("/cuentas", json={"nombre": "Otro", "tipo": "ahorro", "saldo": 0}).json()["id"]
    _hist("sia-8b", c2, ini=None, fin=700_000, inicio="2026-05-01", corte="2026-05-31")
    assert _registrar() == []
    assert cuenta


def test_modo_hoy_no_inventa_el_pasado():
    cuenta = _escenario("sia-9")
    r = client.put("/perfil/punto-de-partida", json={"modo": "hoy", "fecha": "2026-06-01"})
    assert r.status_code in (200, 201), r.text
    assert _registrar() == []
    assert _saldo(cuenta) == 200_000


def test_al_importar_el_primer_extracto_tambien_se_registra():
    cuenta = _escenario("sia-10")
    db = SessionLocal()
    try:
        c = db.get(Cuenta, cuenta)
        r = sia.registrar(db, c)
        assert r and r["monto"] == 500_000
        assert sia.registrar(db, c) is None
    finally:
        db.close()


def test_aislado_por_usuario():
    cuenta = _escenario("sia-11")
    como("sia-12")
    assert _registrar() == []  # otro usuario no toca cuentas ajenas
    como("sia-11")
    assert _saldo(cuenta) == 200_000
    assert len(_registrar()) == 1
