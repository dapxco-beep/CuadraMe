"""Líneas del extracto con DOS montos («Pago $697.534,97 -$474.542,00»): el lector no adivina.

Datos inventados. Antes la línea salía como un gasto de -$222.993 «Sin categoría» y se importaba sin avisar.
Ahora: se marca `lectura_dudosa` (con los montos que aparecen escritos), no se importa sin que la persona elija
el monto, y un «Pago ...» de un extracto de TARJETA se sugiere como traslado (pago de la tarjeta).
"""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'dudosa.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import conciliacion as c  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.contabilidad import MARCA_TRASLADO_PROPIO  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import HistorialExtracto, Movimiento  # noqa: E402

client = TestClient(app)
USUARIO = UsuarioActual(id="dud-1", email="d@test.com", nombre="Dud")


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO
    yield
    app.dependency_overrides.pop(get_current_user, None)


TARJETA = """Extracto de tu tarjeta de crédito Nu
Período 01 - 31 OCT 2026
Pago mínimo $98.000
05 oct Pago $697.534,97 -$474.542,00 -$150.000,00
06 oct Tienda de prueba -$45.000,00
"""
AHORROS = """Extracto de tu cuenta de ahorros Nu
Período 01 - 31 OCT 2026
05 oct Pago Servicio de prueba -$80.000,00
"""


def _por_desc(movs, inicio):
    return next(m for m in movs if m["descripcion"].startswith(inicio))


def test_linea_con_dos_montos_se_marca_dudosa_y_ofrece_los_dos():
    movs, _ = c._parse_nu(TARJETA, "2026")
    pago = _por_desc(movs, "Pago")
    assert pago["lectura_dudosa"] is True
    assert pago["montos_alternativos"] == [697534.97, 474542.0]
    # lo que el lector entendió se conserva, pero no se da por bueno
    assert pago["monto"] == 150000.0


def test_linea_normal_no_se_marca():
    movs, _ = c._parse_nu(TARJETA, "2026")
    tienda = _por_desc(movs, "Tienda")
    assert "lectura_dudosa" not in tienda and "pista" not in tienda


def test_pago_en_extracto_de_tarjeta_se_sugiere_como_traslado():
    movs, _ = c._parse_nu(TARJETA, "2026")
    pago = _por_desc(movs, "Pago")
    assert pago["pista"] == MARCA_TRASLADO_PROPIO and pago["pago_tarjeta"] is True


def test_pago_en_extracto_de_ahorros_sigue_siendo_un_gasto_normal():
    movs, _ = c._parse_nu(AHORROS, "2026")
    pago = _por_desc(movs, "Pago")
    assert "pista" not in pago and "lectura_dudosa" not in pago


def test_montos_en_texto_sin_repetir():
    assert c.montos_en_texto("Pago $1.000,00 -$1.000,00 y $2.500") == [1000.0, 2500.0]
    assert c.montos_en_texto("Compra sin signo de pesos 12.000") == []


def _historial_con_dudosa():
    db = SessionLocal()
    try:
        cuenta = client.post("/cuentas", json={"nombre": "Nu Colombia", "tipo": "ahorro", "saldo": 1_000_000}).json()["id"]
        review = [
            {"fecha": "2026-10-05", "descripcion": "Pago $697.534,97 -$474.542,00", "monto": 222993.0, "tipo": "expense",
             "referencia": "", "fingerprint": "fp-dudosa", "estado": "faltante", "categoria_sugerida": "Pago de tarjeta",
             "lectura_dudosa": True, "montos_alternativos": [697534.97, 474542.0], "pago_tarjeta": True},
            {"fecha": "2026-10-06", "descripcion": "Tienda de prueba", "monto": 45000.0, "tipo": "expense",
             "referencia": "", "fingerprint": "fp-normal", "estado": "faltante", "categoria_sugerida": "Otros"},
        ]
        h = HistorialExtracto(usuario_id=USUARIO.id, cuenta_id=cuenta, banco_detectado="nu", estado="pendiente_revision",
                              review_json=json.dumps(review), total_movimientos=2, faltantes=2)
        db.add(h)
        db.commit()
        return cuenta, h.id
    finally:
        db.close()


def test_la_revision_devuelve_las_marcas():
    _, hid = _historial_con_dudosa()
    r = client.get(f"/conciliacion/historial/{hid}").json()
    d = next(i for i in r["review"] if i["fingerprint"] == "fp-dudosa")
    assert d["lectura_dudosa"] is True and d["montos_alternativos"] == [697534.97, 474542.0] and d["pago_tarjeta"] is True


def test_sin_elegir_monto_la_dudosa_no_se_importa_aunque_venga_marcada():
    cuenta, hid = _historial_con_dudosa()
    out = client.post(f"/conciliacion/historial/{hid}/importar", json={"fingerprints": ["fp-dudosa", "fp-normal"]}).json()
    assert out["importados"] == 1 and out["dudosas_omitidas"] == 1
    db = SessionLocal()
    try:
        descs = [m.descripcion for m in db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta)]
    finally:
        db.close()
    assert descs == ["Tienda de prueba"]


def test_con_el_monto_elegido_se_importa_con_ese_monto_y_deja_de_ser_dudosa():
    cuenta, hid = _historial_con_dudosa()
    out = client.post(f"/conciliacion/historial/{hid}/importar", json={
        "fingerprints": ["fp-dudosa"], "montos": {"fp-dudosa": 474542.0}}).json()
    assert out["importados"] == 1 and out["dudosas_omitidas"] == 0
    db = SessionLocal()
    try:
        m = db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta).one()
        h = db.query(HistorialExtracto).filter(HistorialExtracto.id == hid).one()
        review = json.loads(h.review_json)
    finally:
        db.close()
    assert m.monto == 474542.0 and m.tipo == "expense"
    d = next(i for i in review if i["fingerprint"] == "fp-dudosa")
    assert d["estado"] == "importado" and d["lectura_dudosa"] is False and d["monto_leido"] == 222993.0
