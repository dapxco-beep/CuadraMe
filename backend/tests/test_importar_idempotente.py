"""Importar sin duplicar (datos sintéticos): dos peticiones iguales sobre el mismo historial / correo /
archivo (reintento de la cola offline de la PWA, doble toque) crean UN solo juego de movimientos."""
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'imp_idem.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CorreoGasto, HistorialExtracto, Movimiento  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _auth():
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _como(uid):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def _movs(uid):
    db = SessionLocal()
    try:
        return db.query(Movimiento).filter(Movimiento.usuario_id == uid).count()
    finally:
        db.close()


def _historial_con_faltantes(uid):
    _como(uid)
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "saldo": 1000}).json()
    review = [
        {"fecha": "2026-09-18", "descripcion": f"COMPRA {i}", "monto": 100.0 * (i + 1), "tipo": "expense",
         "fingerprint": f"fp-{uid}-{i}", "estado": "faltante"} for i in range(3)
    ]
    import json
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta["id"], banco_detectado="nu", total_movimientos=3,
                              faltantes=3, estado="pendiente_revision", review_json=json.dumps(review))
        db.add(h)
        db.commit()
        return cuenta, h.id, [i["fingerprint"] for i in review]
    finally:
        db.close()


def _saldo(cuenta_id):
    return next(c["saldo"] for c in client.get("/cuentas").json() if c["id"] == cuenta_id)


def test_importar_dos_veces_seguidas_no_duplica():
    cuenta, hid, fps = _historial_con_faltantes("idem-seq")
    a = client.post(f"/conciliacion/historial/{hid}/importar", json={"fingerprints": fps}).json()
    b = client.post(f"/conciliacion/historial/{hid}/importar", json={"fingerprints": fps}).json()
    assert a["importados"] == 3 and not a.get("ya_importado")
    assert b["importados"] == 0 and b["ya_importado"] is True
    assert _movs("idem-seq") == 3
    assert _saldo(cuenta["id"]) == 1000 - 600  # el saldo se movió UNA vez


def test_importar_en_paralelo_crea_un_solo_juego_de_movimientos():
    cuenta, hid, fps = _historial_con_faltantes("idem-par")

    def _llamar(_):
        return client.post(f"/conciliacion/historial/{hid}/importar", json={"fingerprints": fps}).json()

    with ThreadPoolExecutor(max_workers=4) as pool:
        resultados = list(pool.map(_llamar, range(4)))
    assert sorted(r["importados"] for r in resultados) == [0, 0, 0, 3]
    assert _movs("idem-par") == 3
    assert _saldo(cuenta["id"]) == 400
    db = SessionLocal()
    try:
        assert db.query(HistorialExtracto).filter(HistorialExtracto.id == hid).first().estado == "conciliado"
    finally:
        db.close()


def test_importar_parcial_deja_el_historial_pendiente_y_no_queda_importando():
    cuenta, hid, fps = _historial_con_faltantes("idem-parc")
    r = client.post(f"/conciliacion/historial/{hid}/importar", json={"fingerprints": fps[:1]}).json()
    assert r["importados"] == 1
    db = SessionLocal()
    try:
        assert db.query(HistorialExtracto).filter(HistorialExtracto.id == hid).first().estado == "pendiente_revision"
    finally:
        db.close()
    # Lo que falta se puede importar después (el candado no lo dejó bloqueado).
    r2 = client.post(f"/conciliacion/historial/{hid}/importar", json={"fingerprints": fps}).json()
    assert r2["importados"] == 2 and _movs("idem-parc") == 3


def test_confirmar_archivo_en_paralelo_no_duplica():
    _como("idem-conf")
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "saldo": 0}).json()
    cuerpo = {"cuenta_id": cuenta["id"], "nombre_archivo": "mov.csv", "ajustar_saldo": True, "filas": [
        {"fecha": "2026-09-01", "descripcion": "TIENDA UNO", "monto": 5000, "tipo": "expense"},
        {"fecha": "2026-09-02", "descripcion": "TIENDA DOS", "monto": 7000, "tipo": "expense"},
    ]}

    def _llamar(_):
        return client.post("/importar/confirmar", json=cuerpo).json()

    with ThreadPoolExecutor(max_workers=3) as pool:
        resultados = list(pool.map(_llamar, range(3)))
    assert all("importados" in r for r in resultados), resultados
    assert sorted(r["importados"] for r in resultados) == [0, 0, 2]
    assert _movs("idem-conf") == 2
    assert _saldo(cuenta["id"]) == -12000


def _correo_pendiente(uid, cuenta_id):
    db = SessionLocal()
    try:
        c = CorreoGasto(usuario_id=uid, gmail_msg_id=f"m-{uid}", remitente="Banco <a@banco.co>", asunto="Compra",
                        monto=500.0, comercio="Tienda", categoria_sugerida="Otros", tipo_sugerido="expense",
                        estado="pendiente", recibido_en=ahora_co())
        db.add(c)
        db.commit()
        return c.id
    finally:
        db.close()


def test_aprobar_correo_dos_veces_y_en_paralelo_crea_un_movimiento():
    _como("idem-mail")
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "saldo": 0}).json()
    cid = _correo_pendiente("idem-mail", cuenta["id"])

    def _llamar(_):
        return client.post(f"/correos/{cid}/aprobar", json={"cuenta_id": cuenta["id"]}).status_code

    with ThreadPoolExecutor(max_workers=3) as pool:
        codigos = list(pool.map(_llamar, range(3)))
    assert codigos == [200, 200, 200]
    assert client.post(f"/correos/{cid}/aprobar", json={"cuenta_id": cuenta["id"]}).status_code == 200  # secuencial
    assert _movs("idem-mail") == 1
    assert _saldo(cuenta["id"]) == -500
