"""Un extracto subido dos veces no deja «Falta registrar» para siempre en la revisión vieja. Datos inventados."""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'repetido.db')}")

from datetime import datetime  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app import estado_traer  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.conciliacion import compute_fingerprint  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import HistorialExtracto, Movimiento  # noqa: E402

client = TestClient(app)
UID = "rep-1"
app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=UID, email="r@test.com", nombre="Rep")

DESC = "Pago de tu tarjeta (factura anterior)"


def _linea(cuenta, estado="faltante"):
    fp = compute_fingerprint(datetime(2026, 10, 5), 474_542, cuenta, DESC, "income")
    return {"fecha": "2026-10-05", "descripcion": DESC, "monto": 474_542, "tipo": "income", "fingerprint": fp, "estado": estado}


def _historial(cuenta, review):
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id=UID, cuenta_id=cuenta, banco_detectado="nu", estado="pendiente_revision",
                              review_json=json.dumps(review))
        db.add(h)
        db.commit()
        return h.id
    finally:
        db.close()


def _estados(hid):
    db = SessionLocal()
    try:
        h = db.query(HistorialExtracto).filter(HistorialExtracto.id == hid).first()
        return [i["estado"] for i in json.loads(h.review_json)], h.estado
    finally:
        db.close()


def _resolver():
    db = SessionLocal()
    try:
        return estado_traer.reconciliar_pendientes(db, UID)
    finally:
        db.close()


def _cuenta_con_pago(nombre):
    c = client.post("/cuentas", json={"nombre": nombre, "tipo": "credito", "saldo": 0}).json()["id"]
    r = client.post("/movimientos", json={"cuenta_id": c, "tipo": "income", "monto": 474_542, "descripcion": DESC,
                                          "categoria": "Pago de tarjeta", "fecha": "2026-10-05T00:00:00", "confirmar_nuevo": True})
    assert r.status_code in (200, 201), r.text
    # Ya importado desde otro archivo del mismo periodo: conciliado, así que no cuenta como «hecho a mano».
    db = SessionLocal()
    try:
        m = db.query(Movimiento).filter(Movimiento.id == r.json()["id"]).first()
        m.conciliado_en = datetime(2026, 10, 10)
        m.fuente = "conciliacion_extracto"
        db.commit()
    finally:
        db.close()
    return c


def test_la_linea_ya_registrada_en_la_cuenta_deja_de_decir_falta_registrar():
    cuenta = _cuenta_con_pago("Tarjeta A")
    hid = _historial(cuenta, [_linea(cuenta)])
    assert _resolver() == 1
    assert _estados(hid) == (["exacto"], "conciliado")
    assert _resolver() == 0  # idempotente


def test_dos_lineas_iguales_con_un_solo_movimiento_dejan_una_por_registrar():
    cuenta = _cuenta_con_pago("Tarjeta B")
    hid = _historial(cuenta, [_linea(cuenta), _linea(cuenta)])
    _resolver()
    estados, estado_historial = _estados(hid)
    assert sorted(estados) == ["exacto", "faltante"] and estado_historial == "pendiente_revision"


def test_si_no_esta_registrada_sigue_faltando():
    cuenta = client.post("/cuentas", json={"nombre": "Tarjeta C", "tipo": "credito", "saldo": 0}).json()["id"]
    hid = _historial(cuenta, [_linea(cuenta)])
    assert _resolver() == 0
    assert _estados(hid) == (["faltante"], "pendiente_revision")
