"""El cierre de app (Atajo de cierre) no deja el mismo pago dos veces: se une solo con lo seguro y, ante la duda
(dos pagos reales idénticos), no une. Cubre: cierre que llega después de otro canal, sobrante tras un extracto,
«Buscar duplicados» entre cierre y Wallet, 24 h corridas y la cuenta hermana del mismo banco. Datos inventados."""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'cierre1.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import duplicados as dup  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Movimiento  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="u-0", email="u@test.com", nombre="U")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def _usuario(uid, cuentas):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)
    ids = {n: client.post("/cuentas", json={"nombre": n, "saldo": s}).json()["id"] for n, s in cuentas}
    return client.get("/perfil/api-key").json()["api_key"], ids


def _manual(cuenta_id, monto, desc, tipo="income", hora="12:00:00"):
    hoy = ahora_co().strftime("%Y-%m-%d")
    r = client.post("/movimientos", json={"cuenta_id": cuenta_id, "tipo": tipo, "monto": monto, "descripcion": desc,
                                          "categoria": "Otros", "fecha": f"{hoy}T{hora}", "confirmar_nuevo": True})
    assert r.status_code == 200, r.text
    return r.json()


def _cierre(key, monto="1.060.000", tipo="ingreso", cuenta="Nequi", **extra):
    r = client.post("/movimientos/rapido", headers={"X-Api-Key": key},
                    json={"tipo": tipo, "monto": monto, "cuenta": cuenta, "fuente": "cierre_app", **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _n(cuenta_id):
    return len([m for m in client.get("/movimientos").json() if m["cuenta_id"] == cuenta_id])


# ── 1. el cierre llega DESPUÉS de otro canal ──
def test_cierre_se_absorbe_en_el_manual_del_mismo_dia():
    key, ids = _usuario("cu-1", [("Nequi", 0)])
    mano = _manual(ids["Nequi"], 1_060_000, "Juliana")
    out = _cierre(key)
    assert out["duplicado"] is True and out["id"] == mano["id"] and out["ya_estaba_por"] == "manual"
    assert _n(ids["Nequi"]) == 1
    nota = {m["id"]: m for m in client.get("/movimientos").json()}[mano["id"]]["notas"]
    assert "Se unió con un aviso del atajo de cierre" in nota  # queda constancia de la unión
    assert client.get("/cuentas").json()[0]["saldo"] == 1_060_000  # un solo ingreso


def test_cierre_con_dos_manuales_iguales_no_se_une():
    key, ids = _usuario("cu-2", [("Nequi", 0)])
    _manual(ids["Nequi"], 20_000, "Cafe", "expense", "09:00:00")
    _manual(ids["Nequi"], 20_000, "Almuerzo", "expense", "13:00:00")
    out = _cierre(key, "20.000", "gasto")
    assert out["duplicado"] is False
    assert _n(ids["Nequi"]) == 3


def test_dos_pagos_reales_identicos_por_cierre_no_se_unen():
    key, ids = _usuario("cu-3", [("Nequi", 0)])
    _manual(ids["Nequi"], 20_000, "Cafe", "expense", "09:00:00")
    a = _cierre(key, "20.000", "gasto")  # se absorbe en el manual
    assert a["duplicado"] is True
    # el segundo pago igual del día llega por el mismo atajo: el atajo ya habló de este monto hoy, es otro pago
    b = _cierre(key, "20.000", "gasto", fecha=(ahora_co() - timedelta(minutes=5)).isoformat())
    assert b["duplicado"] is False
    assert _n(ids["Nequi"]) == 2


def test_cierre_no_se_une_con_otro_dia_ni_otro_monto():
    key, ids = _usuario("cu-4", [("Nequi", 0)])
    viejo = (ahora_co() - timedelta(days=2)).strftime("%Y-%m-%d")
    client.post("/movimientos", json={"cuenta_id": ids["Nequi"], "tipo": "income", "monto": 1_060_000, "descripcion": "Juliana",
                                      "categoria": "Otros", "fecha": f"{viejo}T12:00:00", "confirmar_nuevo": True})
    _manual(ids["Nequi"], 1_000_000, "Otro")
    assert _cierre(key)["duplicado"] is False
    assert _n(ids["Nequi"]) == 3


# ── 2. sobrante de cierre tras un extracto ──
def _procesar(monkeypatch, cuenta_id, items):
    from app.routers import conciliacion as mod
    monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: "texto del extracto")
    monkeypatch.setattr(mod, "detectar_banco", lambda t: "nequi")
    monkeypatch.setattr(mod, "parse_texto_con_regex", lambda t: (items, 0))
    return client.post("/conciliacion/procesar", json={"cuenta_id": cuenta_id, "pdf_base64": "x"})


def _dos_cierres_y_extracto(monkeypatch, uid):
    key, ids = _usuario(uid, [("Nequi", 100_000)])
    hoy = ahora_co().strftime("%Y-%m-%d")
    h = {"X-Api-Key": key}
    a = client.post("/movimientos/rapido", headers=h, json={"tipo": "ingreso", "monto": "60.000", "descripcion": "De JOSE", "cuenta": "Nequi", "fuente": "cierre_app"}).json()
    items = [{"fecha": hoy, "descripcion": "De JOSE", "monto": 60_000, "tipo": "income", "referencia": ""}]
    _procesar(monkeypatch, ids["Nequi"], items)  # el extracto respalda el primero
    b = client.post("/movimientos/rapido", headers=h, json={
        "tipo": "ingreso", "monto": "60.000", "cuenta": "Nequi", "fuente": "cierre_app",
        "fecha": (ahora_co() - timedelta(minutes=20)).isoformat()}).json()
    return ids, items, a, b


def test_cierre_sobrante_tras_el_extracto_se_une_solo_y_se_deshace(monkeypatch):
    ids, items, a, b = _dos_cierres_y_extracto(monkeypatch, "cu-5")
    assert b["id"] != a["id"]  # el primero ya estaba respaldado por el banco: el segundo no se adivina al llegar
    out = _procesar(monkeypatch, ids["Nequi"], items).json()
    unidos = [i for i in out["review"] if i["estado"] == "sobrante_resuelto" and i.get("resuelto") == "unido"]
    assert [i["match_id"] for i in unidos] == [b["id"]]
    assert b["id"] not in [m["id"] for m in client.get("/movimientos").json()]
    r = client.post(f"/conciliacion/historial/{out['historial_id']}/sobrantes/{b['id']}", json={"accion": "restaurar", "motivo": "no_va"})
    assert r.status_code == 200, r.text
    assert b["id"] in [m["id"] for m in client.get("/movimientos").json()]


def test_dos_pagos_reales_con_dos_lineas_en_el_extracto_no_se_unen(monkeypatch):
    key, ids = _usuario("cu-6", [("Nequi", 100_000)])
    hoy = ahora_co().strftime("%Y-%m-%d")
    for minutos in (50, 10):
        client.post("/movimientos/rapido", headers={"X-Api-Key": key}, json={
            "tipo": "gasto", "monto": "20.000", "cuenta": "Nequi", "fuente": "cierre_app",
            "fecha": (ahora_co() - timedelta(minutes=minutos)).isoformat()})
    items = [{"fecha": hoy, "descripcion": f"Compra {k}", "monto": 20_000, "tipo": "expense", "referencia": ""} for k in "AB"]
    out = _procesar(monkeypatch, ids["Nequi"], items).json()
    assert not [i for i in out["review"] if i["estado"] in ("sobrante", "sobrante_resuelto")]
    assert _n(ids["Nequi"]) == 2


def test_cierre_confirmado_por_la_persona_no_se_une_solo(monkeypatch):
    ids, items, a, b = _dos_cierres_y_extracto(monkeypatch, "cu-7")
    r = client.post("/movimientos/confirmar-categorias", json={"movimiento_ids": [b["id"]]})
    assert r.status_code == 200 and r.json()["confirmados"] == 1, r.text
    out = _procesar(monkeypatch, ids["Nequi"], items).json()
    assert not [i for i in out["review"] if i["estado"] == "sobrante_resuelto"]
    assert b["id"] in [m["id"] for m in client.get("/movimientos").json()]


# ── 3. «Buscar duplicados»: cierre_app con Wallet ──
def _db_mov(db, uid, cuenta_id, fuente, monto, minutos):
    m = Movimiento(usuario_id=uid, cuenta_id=cuenta_id, tipo="expense", monto=monto,
                   descripcion="Exito" if fuente == "wallet" else "Movimiento en Nequi",
                   categoria="Otros", fuente=fuente, cat_origen=fuente, cat_confirmada=False,
                   fecha=ahora_co().replace(microsecond=0) - timedelta(minutes=minutos))
    db.add(m)
    db.commit()
    return m


def test_buscar_duplicados_empareja_cierre_con_wallet_pero_no_dos_cierres():
    _, ids = _usuario("cu-8", [("Nequi", 0)])
    db = SessionLocal()
    try:
        w = _db_mov(db, "cu-8", ids["Nequi"], "wallet", 30_000, 120)
        c = _db_mov(db, "cu-8", ids["Nequi"], "cierre_app", 30_000, 100)
        grupos = dup.grupos_posibles_duplicados(db, "cu-8")
        assert len(grupos) == 1 and {m["id"] for m in grupos[0]["movimientos"]} == {w.id, c.id}
    finally:
        db.close()
    _, ids = _usuario("cu-9", [("Nequi", 0)])
    db = SessionLocal()
    try:
        _db_mov(db, "cu-9", ids["Nequi"], "cierre_app", 30_000, 120)
        _db_mov(db, "cu-9", ids["Nequi"], "cierre_app", 30_000, 100)
        assert dup.grupos_posibles_duplicados(db, "cu-9") == []  # dos cierres iguales: dos pagos, no se sugiere
        _db_mov(db, "cu-9", ids["Nequi"], "wallet", 30_000, 90)
        assert len(dup.grupos_posibles_duplicados(db, "cu-9")) == 1  # un solo par; el otro cierre queda suelto
    finally:
        db.close()


# ── 4. ventana de horas ──
def _cand(origen, fecha, con_hora, texto="EXITO"):
    return dup.Cand(id=origen, origen=origen, tipo="expense", monto=10_000, fecha=fecha, cuentas=frozenset({"c"}),
                    texto=texto, con_hora=con_hora)


def test_ventana_24h_exactas_con_mismo_comercio_se_une_pero_otro_comercio_no():
    a = datetime(2026, 11, 1, 10, 0)
    atajo = _cand("atajo", a, True)
    assert dup.puntaje(_cand("correo", a + timedelta(hours=24), True), atajo) is not None
    assert dup.puntaje(_cand("correo", a + timedelta(hours=24), True, "RAPPI"), atajo) is None
    assert dup.puntaje(_cand("correo", a + timedelta(hours=10), True), atajo) is None  # otra compra
    # correo solo con fecha (sin hora real): el límite de horas no aplica
    assert dup.puntaje(_cand("correo", datetime(2026, 11, 2, 0, 0), False), atajo) is not None


# ── 5. cuenta hermana ──
def test_creo_a_mano_algo_igual_a_lo_de_la_cuenta_hermana_avisa_y_con_otro_banco_no():
    USUARIO["actual"] = UsuarioActual(id="cu-10", email="a@t.com", nombre="a")
    h1 = client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 0}).json()["id"]
    h2 = client.post("/cuentas", json={"nombre": "Bancolombia Nomina", "saldo": 0}).json()["id"]
    otro = client.post("/cuentas", json={"nombre": "Davivienda", "saldo": 0}).json()["id"]
    db = SessionLocal()
    try:
        mov = {"id": _db_mov(db, "cu-10", h1, "wallet", 50_000, 5).id}  # llegó por Wallet a la cuenta hermana
    finally:
        db.close()
    base = {"tipo": "expense", "monto": 50_000, "descripcion": "Mercado", "categoria": "Otros", "fecha": ahora_co().isoformat()}
    r = client.post("/movimientos", json={**base, "cuenta_id": h2})
    assert r.status_code == 409 and r.json()["detail"]["movimiento_id"] == mov["id"] and r.json()["detail"]["cuenta_id"] == h1
    assert client.post("/movimientos", json={**base, "cuenta_id": h2, "confirmar_nuevo": True}).status_code == 200
    assert client.post("/movimientos", json={**base, "cuenta_id": otro}).status_code == 200


def test_extracto_da_pista_de_la_cuenta_hermana_sin_unir_solo(monkeypatch):
    USUARIO["actual"] = UsuarioActual(id="cu-11", email="b@t.com", nombre="b")
    h1 = client.post("/cuentas", json={"nombre": "Nequi Principal", "saldo": 0}).json()["id"]
    h2 = client.post("/cuentas", json={"nombre": "Nequi Bolsillo", "saldo": 0}).json()["id"]
    mov = _manual(h1, 70_000, "Pago luz", "expense")
    hoy = ahora_co().strftime("%Y-%m-%d")
    items = [{"fecha": hoy, "descripcion": "PAGO LUZ", "monto": 70_000, "tipo": "expense", "referencia": ""}]
    out = _procesar(monkeypatch, h2, items).json()
    it = out["review"][0]
    assert it["estado"] == "faltante"  # no se une sola
    assert it["pista_hermana"]["movimiento_id"] == mov["id"] and it["pista_hermana"]["accion"]["etiqueta"] == "Pasarlo a esta cuenta"
    assert "otra cuenta" in it["pista_hermana"]["mensaje"]
    # dos iguales en la hermana: ambiguo, no se adivina
    _manual(h1, 70_000, "Pago luz 2", "expense", "15:00:00")
    out = _procesar(monkeypatch, h2, items).json()
    assert out["review"][0].get("pista_hermana") is None


def test_manual_igual_en_la_hermana_a_mano_no_estorba():
    """Lo que la persona anotó a mano en cada cuenta es deliberado: solo se avisa de lo que llegó por otro canal."""
    USUARIO["actual"] = UsuarioActual(id="cu-12", email="c@t.com", nombre="c")
    h1 = client.post("/cuentas", json={"nombre": "Nu Ahorros", "saldo": 0}).json()["id"]
    h2 = client.post("/cuentas", json={"nombre": "Nu Tarjeta", "saldo": 0}).json()["id"]
    _manual(h1, 30_000, "Cine", "expense")
    base = {"tipo": "expense", "monto": 30_000, "descripcion": "Cine", "categoria": "Otros", "fecha": ahora_co().isoformat()}
    assert client.post("/movimientos", json={**base, "cuenta_id": h2}).status_code == 200
