"""El flujo genérico (lector -> clasificación -> importar -> cuadre) no asume que el banco es Nu. Usa tests/fixtures_bancos.py
(extractos inventados de «Banco Ejemplo A» y «Banco Ejemplo B», y uno de «Banco Ejemplo C» que ningún lector conoce).
No se crea ningún lector nuevo: se prueba lo que hoy hace el lector genérico y el camino de «sin lector»."""
import base64
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'bancos_genericos.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import autoarreglo as aa  # noqa: E402
from app import cierre_extractos  # noqa: E402
from app import cuadre_extracto as cx  # noqa: E402
from app import limites  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.conciliacion import detectar_banco, parse_texto_con_regex  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, HistorialExtracto, Movimiento, Perfil  # noqa: E402
from app.routers import conciliacion as mod  # noqa: E402
from tests.fixtures_bancos import (  # noqa: E402
    EJEMPLO_A, EJEMPLO_A_ESPERADO, EJEMPLO_B, EJEMPLO_B_ESPERADO, EJEMPLO_C_ILEGIBLE,
)

Base.metadata.create_all(bind=engine)
client = TestClient(app)
PDF_FALSO = base64.b64encode(b"%PDF-1.4 inventado").decode()  # parece un PDF; el texto lo pone el monkeypatch de pdf_a_texto


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    app.dependency_overrides.clear()
    limites._eventos.clear()
    llamadas_ia = []
    monkeypatch.setattr(mod, "extraer_via_ia", lambda *a, **k: llamadas_ia.append(1) or [])
    yield llamadas_ia
    app.dependency_overrides.clear()


def _persona(uid, nombre_cuenta):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.com", nombre="Persona Prueba")
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free"))
        c = Cuenta(usuario_id=uid, nombre=nombre_cuenta, tipo="ahorro", saldo=0)
        db.add(c)
        db.commit()
        return c.id
    finally:
        db.close()


def _procesar(cuenta_id, texto, monkeypatch):
    monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: texto)
    return client.post("/conciliacion/procesar", json={"cuenta_id": cuenta_id, "pdf_base64": PDF_FALSO})


def _importar_todo(r):
    fps = [i["fingerprint"] for i in r.json()["review"] if i["estado"] == "faltante"]
    ok = client.post(f"/conciliacion/historial/{r.json()['historial_id']}/importar", json={"fingerprints": fps})
    assert ok.status_code == 200, ok.text


def _correr(uid):
    db = SessionLocal()
    try:
        return aa.correr(db, uid)
    finally:
        db.close()


def test_el_lector_generico_lee_el_banco_a_y_sus_saldos_sin_asumir_nu():
    assert detectar_banco(EJEMPLO_A) == "generico" and detectar_banco(EJEMPLO_B) == "generico"  # ni Nu ni Nequi
    movs, _ = parse_texto_con_regex(EJEMPLO_A)
    assert [(m["fecha"], m["tipo"], m["monto"]) for m in movs] == EJEMPLO_A_ESPERADO["movimientos"]
    saldos = cx.leer_saldos_extracto(EJEMPLO_A)
    assert saldos["saldo_inicial"] == EJEMPLO_A_ESPERADO["saldo_inicial"] and saldos["saldo_final"] == EJEMPLO_A_ESPERADO["saldo_final"]
    neto = sum(m["monto"] * (1 if m["tipo"] == "income" else -1) for m in movs)
    assert saldos["saldo_inicial"] + neto == saldos["saldo_final"]  # lo leído explica el cambio de saldo


def test_ahorros_generico_con_saldo_inicial_y_final_cuadra(monkeypatch):
    uid = "bg-1"
    cuenta = _persona(uid, "Banco Ejemplo A Ahorros")
    r = _procesar(cuenta, EJEMPLO_A, monkeypatch)
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    _importar_todo(r)
    resp = _correr(uid)
    cuadre = next(c for c in resp["cuadre"] if c["cuenta_id"] == cuenta)
    assert cuadre["estado"] == "cuadra", cuadre
    db = SessionLocal()
    try:
        assert round(db.get(Cuenta, cuenta).saldo, 2) == EJEMPLO_A_ESPERADO["saldo_final"]
    finally:
        db.close()
    assert resp["coherencia"] == [] and resp["aprendizaje"] is None  # nada incoherente, nada que aprender


def test_banco_b_con_celdas_vacias_se_lee_bien_y_cuadra(monkeypatch):
    """Columnas Débito/Crédito con la celda de una vacía: la consignación es ingreso y el retiro, gasto (se decide por la
    aritmética del saldo del banco o por la columna bajo la que cae el valor, nunca por el orden del texto)."""
    uid = "bg-2"
    cuenta = _persona(uid, "Banco Ejemplo B Ahorros")
    movs, _ = parse_texto_con_regex(EJEMPLO_B)
    assert [(m["fecha"], m["tipo"], m["monto"]) for m in movs] == EJEMPLO_B_ESPERADO["movimientos"]
    saldos = cx.leer_saldos_extracto(EJEMPLO_B)
    neto = sum(m["monto"] * (1 if m["tipo"] == "income" else -1) for m in movs)
    assert saldos["saldo_inicial"] + neto == saldos["saldo_final"]
    r = _procesar(cuenta, EJEMPLO_B, monkeypatch)
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    _importar_todo(r)
    resp = _correr(uid)
    db = SessionLocal()
    try:
        assert round(db.get(Cuenta, cuenta).saldo, 2) == saldos["saldo_final"]
    finally:
        db.close()
    assert next(c for c in resp["cuadre"] if c["cuenta_id"] == cuenta)["estado"] == "cuadra"


def test_columnas_debito_credito_sin_columna_de_saldo_se_leen_por_la_posicion():
    texto = """Banco Ejemplo D
Fecha        Descripcion                      Debito        Credito       Saldo
04-09-2026   Consignacion Empresa Ficticia                  750.000,00    750.000,00
09-09-2026   Compra Libreria Ficticia         60.000,00                   690.000,00
"""
    movs, _ = parse_texto_con_regex(texto)
    assert [(m["tipo"], m["monto"]) for m in movs] == [("income", 750_000.0), ("expense", 60_000.0)]


def test_banco_desconocido_no_se_toca_y_queda_aprendiendo(monkeypatch, _ambiente):
    uid = "bg-3"
    cuenta = _persona(uid, "Banco Ejemplo C Ahorros")
    r = _procesar(cuenta, EJEMPLO_C_ILEGIBLE, monkeypatch)
    assert r.status_code == 200 and r.json()["ok"] is False
    assert r.json()["motivo_error"] == "formato_no_reconocido"
    resp = _correr(uid)
    # estado claro y NO accionable
    ap = resp["aprendizaje"]
    assert ap["estado_aprendizaje"] == "aprendiendo" and ap["cantidad"] == 1
    assert ap["texto_aprendizaje"] == "Estamos aprendiendo el formato de tu banco; no tienes que hacer nada."
    assert not any(d["tipo"] in ("dudosas", "tarjeta_sin_verificar", "clave_pdf") for d in resp["decisiones"])  # no se le pide nada
    # y no se tocó nada: ni movimientos, ni saldo, ni el extracto
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta).count() == 0
        assert db.get(Cuenta, cuenta).saldo == 0
        h = db.query(HistorialExtracto).filter_by(usuario_id=uid).one()
        assert h.estado == "error" and h.motivo_error == "formato_no_reconocido" and h.review_json in (None, "[]")
    finally:
        db.close()
    assert resp["cambios"] == 0 and resp["resumen"] is None
    # y el cuadre no inventa nada para una cuenta sin extractos leídos
    assert [c for c in cierre_extractos.cuadre_por_cuenta(SessionLocal(), uid) if c["cuenta_id"] == cuenta] == []
