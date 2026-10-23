"""Registro por movimiento: GET /autoarreglo/movimientos/{id}/historia cuenta en español lo que el autoarreglo le hizo a UN
movimiento, con fecha y lote, y está aislado por usuario (el de otra persona responde 404). Datos 100 % inventados."""
import json
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'historia.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import autoarreglo as aa  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento  # noqa: E402
from app.models_autoarreglo import ArregloAuto  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)


@pytest.fixture(autouse=True)
def _limpio():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def como(uid):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.com", nombre="Persona Prueba")


def _arreglo(db, uid, lote, tipo, mid, antes, despues, creado, revertido=None):
    db.add(ArregloAuto(usuario_id=uid, lote_id=lote, tipo=tipo, entidad_id=mid, antes=json.dumps(antes) if antes else None,
                       despues=json.dumps(despues) if despues else None, creado_en=creado, revertido_en=revertido))


def _mundo(uid):
    db = SessionLocal()
    try:
        a = Cuenta(usuario_id=uid, nombre="Banco Ejemplo A Ahorros", tipo="ahorro", saldo=0)
        b = Cuenta(usuario_id=uid, nombre="Banco Ejemplo A Tarjeta", tipo="credito", saldo=0)
        db.add_all([a, b])
        db.flush()
        m = Movimiento(usuario_id=uid, cuenta_id=b.id, descripcion="Tienda Uno", tipo="expense", monto=20_000.0, fecha=datetime(2026, 8, 5),
                       fuente="conciliacion_extracto")
        db.add(m)
        db.flush()
        _arreglo(db, uid, "lote-1", "mover_cuenta", m.id, {"cuenta_id": a.id}, {"cuenta_id": b.id}, datetime(2026, 10, 21, 9))
        _arreglo(db, uid, "lote-2", "corregir_tipo", m.id, {"tipo": "income"}, {"tipo": "expense"}, datetime(2026, 10, 22, 9))
        _arreglo(db, uid, "lote-3", "corregir_monto", m.id, {"monto": 40_000.0}, {"monto": 60_000.0}, datetime(2026, 10, 22, 10),
                 revertido=datetime(2026, 10, 24, 8))
        _arreglo(db, uid, "lote-3", "saldo", b.id, {"saldo": 1}, {"saldo": 2}, datetime(2026, 10, 22, 10))  # no es del movimiento
        # un movimiento borrado por repetido: ya no existe, pero su historia sí
        _arreglo(db, uid, "lote-4", "quitar_repetido", "mov-borrado", {"descripcion": "Pago repetido", "monto": 5.0}, None, datetime(2026, 10, 23, 9))
        db.commit()
        return m.id
    finally:
        db.close()


def test_la_linea_de_tiempo_viene_en_orden_con_fecha_y_lote():
    mid = _mundo("h-1")
    como("h-1")
    r = client.get(f"/autoarreglo/movimientos/{mid}/historia")
    assert r.status_code == 200, r.text
    h = r.json()["historia"]
    assert r.json()["existe"] is True
    assert [x["lote_id"] for x in h] == ["lote-1", "lote-2", "lote-3", "lote-3"]
    assert h[0]["texto"] == "El 21 de octubre pasé este movimiento de «Banco Ejemplo A Ahorros» a «Banco Ejemplo A Tarjeta», que es donde está en tu extracto."
    assert h[1]["texto"].startswith("El 22 de octubre cambié este movimiento de ingreso a gasto")
    assert "de $40.000 a $60.000" in h[2]["texto"] and h[2]["deshecho"] is True
    assert h[3]["tipo"] == "deshacer" and h[3]["texto"].startswith("El 24 de octubre deshiciste")
    assert all(x["fecha"] and x["lote_id"] for x in h)


def test_un_movimiento_quitado_conserva_su_historia():
    _mundo("h-2")
    como("h-2")
    r = client.get("/autoarreglo/movimientos/mov-borrado/historia")
    assert r.status_code == 200
    assert r.json()["existe"] is False
    assert r.json()["historia"][0]["texto"] == "El 23 de octubre quité este movimiento porque era repetido de otro."


def test_otro_usuario_recibe_404_y_no_se_filtra_nada():
    mid = _mundo("h-3")
    _mundo("h-4")  # otra persona con su propia historia
    como("h-4")
    assert client.get(f"/autoarreglo/movimientos/{mid}/historia").status_code == 404  # el movimiento es de h-3
    como("h-3")
    assert client.get(f"/autoarreglo/movimientos/{mid}/historia").status_code == 200
    como("h-3")  # el movimiento borrado de h-3 es de h-3 aunque h-4 tenga otro con el mismo id
    assert len(client.get("/autoarreglo/movimientos/mov-borrado/historia").json()["historia"]) == 1
    como("h-5")
    assert client.get("/autoarreglo/movimientos/mov-borrado/historia").status_code == 404


def test_movimiento_propio_sin_arreglos_da_historia_vacia_y_sin_login_no_entra():
    db = SessionLocal()
    try:
        c = Cuenta(usuario_id="h-6", nombre="Banco Ejemplo B", tipo="ahorro", saldo=0)
        db.add(c)
        db.flush()
        m = Movimiento(usuario_id="h-6", cuenta_id=c.id, descripcion="Compra", tipo="expense", monto=1_000.0, fecha=datetime(2026, 8, 1))
        db.add(m)
        db.commit()
        mid = m.id
    finally:
        db.close()
    como("h-6")
    r = client.get(f"/autoarreglo/movimientos/{mid}/historia")
    assert r.status_code == 200 and r.json()["historia"] == []
    app.dependency_overrides.clear()
    assert client.get(f"/autoarreglo/movimientos/{mid}/historia").status_code in (401, 403)
    assert aa.historia_de_movimiento  # contrato público
