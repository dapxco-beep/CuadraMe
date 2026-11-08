"""Procesar OTRA VEZ un extracto ya conciliado no debe duplicar lo que se había cruzado con un movimiento de otro canal.

Caso real (Nequi de una usuaria): el correo creó «Ingreso sin detalle $450.000»; al importar el extracto, esa línea se
CONCILIÓ con el movimiento del correo (que conserva su propia descripción). Al procesar el mismo extracto una segunda vez,
la línea ya no se reconocía (otra descripción, y el movimiento ya estaba conciliado) y se creaba de nuevo. Datos inventados."""
import os
import tempfile
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'reprocesar.db')}")

import pytest  # noqa: E402

from app import duplicados as dup  # noqa: E402
from app.conciliacion import auditar_movimientos, compute_fingerprint  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Cuenta, Movimiento  # noqa: E402
from app.routers.conciliacion import _cargar_ledger  # noqa: E402

Base.metadata.create_all(bind=engine)

LINEA = {"fecha": "2026-07-22", "monto": 450_000.0, "tipo": "income", "descripcion": "RECIBI POR BRE-B DE: Persona Uno"}


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _caso(db, con_huella=True):
    uid = f"rp-{uuid.uuid4().hex[:8]}"
    cu = Cuenta(usuario_id=uid, nombre="Nequi", tipo="ahorro", saldo=0, moneda="COP")
    db.add(cu)
    db.flush()
    # El movimiento que creó el correo: otra descripción, ya conciliado con el extracto la primera vez.
    mov = Movimiento(usuario_id=uid, cuenta_id=cu.id, fecha=datetime(2026, 7, 22, 12), descripcion="Ingreso sin detalle",
                     categoria="Otros", tipo="income", monto=450_000, fuente="email", notas="", conciliado_en=datetime(2026, 10, 28))
    db.add(mov)
    db.flush()
    if con_huella:
        fp = compute_fingerprint(datetime(2026, 7, 22), 450_000.0, cu.id, LINEA["descripcion"], "income")
        dup.registrar_canal(db, mov, dup.ORIGEN_EXTRACTO, dup.huella_extracto(fp, 1))
        db.flush()
    return uid, cu, mov


def test_la_segunda_pasada_reconoce_la_linea_ya_conciliada_y_no_la_duplica(db):
    uid, cu, mov = _caso(db)
    ledger = _cargar_ledger(db, uid, cu.id)
    r = auditar_movimientos([{**LINEA, "cuenta": cu.id}], ledger, cruzar_rapidos=True)
    item = r["review"][0]
    assert item["estado"] == "exacto" and item["match_id"] == mov.id
    assert r["faltantes"] == 0


def test_dos_lineas_identicas_siguen_siendo_dos_movimientos_distintos(db):
    uid, cu, mov = _caso(db)
    ledger = _cargar_ledger(db, uid, cu.id)
    dos = [{**LINEA, "cuenta": cu.id}, {**LINEA, "cuenta": cu.id}]
    estados = [i["estado"] for i in auditar_movimientos(dos, ledger, cruzar_rapidos=True)["review"]]
    assert estados.count("exacto") == 1  # una sola línea se cruza con el movimiento existente
    assert estados.count("exacto") + estados.count("faltante") + estados.count("aproximado") == 2


def test_sin_huella_previa_el_comportamiento_no_cambia(db):
    uid, cu, mov = _caso(db, con_huella=False)
    ledger = _cargar_ledger(db, uid, cu.id)
    assert len(ledger) == 1  # no se inventan filas
    r = auditar_movimientos([{**LINEA, "cuenta": cu.id}], ledger, cruzar_rapidos=True)
    assert r["review"][0]["estado"] != "exacto"


# ── el banco manda: el monto de una línea conciliada pasa a ser el del extracto ─────────────────────────
class _SinClasificador:
    def clasificar(self, _descripcion):
        return None


def _wallet(db, monto_anotado, saldo_inicial=1_000_000.0):
    uid = f"bm-{uuid.uuid4().hex[:8]}"
    cu = Cuenta(usuario_id=uid, nombre="Nu", tipo="ahorro", saldo=saldo_inicial - monto_anotado, moneda="COP")
    db.add(cu)
    db.flush()
    mov = Movimiento(usuario_id=uid, cuenta_id=cu.id, fecha=datetime(2026, 10, 18, 9, 30), descripcion="Compra en UBER RIDES",
                     categoria="Transporte", tipo="expense", monto=monto_anotado, fuente="wallet", notas="")
    db.add(mov)
    db.flush()
    return uid, cu, mov


def test_uber_anotado_11280_y_cobrado_10791_queda_en_lo_que_cobro_el_banco(db):
    from app.routers.conciliacion import _completar_con_extracto

    uid, cu, mov = _wallet(db, 11_280.0)
    item = {"fecha": "2026-10-18", "descripcion": "UBER RIDES", "monto": 10_791.0, "tipo": "expense"}
    _completar_con_extracto(db, mov, item, "h1", _SinClasificador(), uid, cuenta=cu, huella="ext:x#1")
    assert mov.monto == 10_791.0
    assert cu.saldo == pytest.approx(1_000_000.0 - 10_791.0)  # el saldo sigue al banco
    assert "$11.280" in mov.notas and "$10.791" in mov.notas  # lo anotado no se pierde
    assert item["monto_registrado"] == 11_280.0 and mov.conciliado_en is not None


def test_una_diferencia_de_redondeo_se_corrige_sin_ruido_en_las_notas(db):
    from app.routers.conciliacion import _completar_con_extracto

    uid, cu, mov = _wallet(db, 20_000.4)
    item = {"fecha": "2026-10-18", "descripcion": "TIENDA", "monto": 20_000.0, "tipo": "expense"}
    _completar_con_extracto(db, mov, item, "h1", _SinClasificador(), uid, cuenta=cu, huella="ext:y#1")
    assert mov.monto == 20_000.0 and cu.saldo == pytest.approx(1_000_000.0 - 20_000.0)
    assert "banco cobró" not in (mov.notas or "")


def test_si_el_monto_ya_coincide_no_cambia_nada(db):
    from app.routers.conciliacion import _completar_con_extracto

    uid, cu, mov = _wallet(db, 15_000.0)
    saldo = cu.saldo
    item = {"fecha": "2026-10-18", "descripcion": "TIENDA", "monto": 15_000.0, "tipo": "expense"}
    _completar_con_extracto(db, mov, item, "h1", _SinClasificador(), uid, cuenta=cu, huella="ext:z#1")
    assert mov.monto == 15_000.0 and cu.saldo == saldo and not mov.notas
