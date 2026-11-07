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
