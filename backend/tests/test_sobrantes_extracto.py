"""Un movimiento TUYO que el extracto no trae («sobrante») se puede dejar o borrar, y la decisión queda guardada
en la revisión del extracto (antes solo se listaba y no había forma de arreglarlo). Datos inventados."""
import json
import os
import tempfile
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'sobrantes.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, HistorialExtracto, Movimiento  # noqa: E402

client = TestClient(app)


@pytest.fixture
def caso():
    u = UsuarioActual(id=f"sb-{uuid.uuid4().hex[:8]}", email="sb@test.com", nombre="Sb")
    otro = UsuarioActual(id=f"sb-{uuid.uuid4().hex[:8]}", email="sb2@test.com", nombre="Sb2")
    app.dependency_overrides[get_current_user] = lambda: u
    db = SessionLocal()
    cu = Cuenta(usuario_id=u.id, nombre="Banco", tipo="ahorro", saldo=0, moneda="COP")
    db.add(cu)
    db.flush()
    movs = []
    for desc, monto in [("Dollarcity Floresta", 18000), ("Estacion Terpel", 39979), ("Novaventa", 5300)]:
        m = Movimiento(usuario_id=u.id, cuenta_id=cu.id, fecha=datetime(2026, 10, 18, 12), descripcion=desc,
                       categoria="Otros", tipo="expense", monto=monto, fuente="atajo", notas="")
        db.add(m)
        movs.append(m)
    db.flush()
    review = [{"fecha": "2026-10-18", "descripcion": m.descripcion, "monto": m.monto, "tipo": "expense", "referencia": "",
               "fingerprint": f"sobrante-{m.id}", "estado": "sobrante", "match_id": m.id} for m in movs]
    h = HistorialExtracto(usuario_id=u.id, cuenta_id=cu.id, banco_detectado="Banco", review_json=json.dumps(review))
    db.add(h)
    db.commit()
    ids = [m.id for m in movs]
    hid = h.id
    db.close()
    yield {"u": u, "otro": otro, "hid": hid, "ids": ids}
    app.dependency_overrides.pop(get_current_user, None)


def _revision(hid):
    db = SessionLocal()
    try:
        return json.loads(db.get(HistorialExtracto, hid).review_json)
    finally:
        db.close()


def _existe(mid):
    db = SessionLocal()
    try:
        return db.get(Movimiento, mid) is not None
    finally:
        db.close()


def test_dejar_conserva_el_movimiento_y_deja_de_avisar(caso):
    r = client.post(f"/conciliacion/historial/{caso['hid']}/sobrantes/{caso['ids'][0]}", json={"accion": "dejar"})
    assert r.status_code == 200 and r.json() == {"ok": True, "resuelto": "dejado", "restantes": 2}
    assert _existe(caso["ids"][0])
    est = {i["match_id"]: i["estado"] for i in _revision(caso["hid"])}
    assert est[caso["ids"][0]] == "sobrante_resuelto" and est[caso["ids"][1]] == "sobrante"


def test_borrar_elimina_el_movimiento_y_queda_resuelto(caso):
    r = client.post(f"/conciliacion/historial/{caso['hid']}/sobrantes/{caso['ids'][1]}", json={"accion": "borrar", "motivo": "no_va"})
    assert r.status_code == 200 and r.json()["resuelto"] == "borrado" and r.json()["restantes"] == 2
    assert not _existe(caso["ids"][1]) and _existe(caso["ids"][0])


def test_es_idempotente_y_borrar_dos_veces_no_falla(caso):
    url = f"/conciliacion/historial/{caso['hid']}/sobrantes/{caso['ids'][2]}"
    assert client.post(url, json={"accion": "borrar"}).status_code == 200
    assert client.post(url, json={"accion": "borrar"}).status_code == 200


def test_valida_la_accion_el_motivo_y_que_el_movimiento_sea_un_sobrante(caso):
    base = f"/conciliacion/historial/{caso['hid']}/sobrantes/"
    assert client.post(base + caso["ids"][0], json={"accion": "explotar"}).status_code == 422
    assert client.post(base + caso["ids"][0], json={"accion": "borrar", "motivo": "x"}).status_code == 422
    assert client.post(base + "no-existe", json={"accion": "dejar"}).status_code == 404


def test_otra_persona_no_puede_tocar_mi_extracto(caso):
    app.dependency_overrides[get_current_user] = lambda: caso["otro"]
    r = client.post(f"/conciliacion/historial/{caso['hid']}/sobrantes/{caso['ids'][0]}", json={"accion": "borrar"})
    assert r.status_code == 404
    assert _existe(caso["ids"][0])
