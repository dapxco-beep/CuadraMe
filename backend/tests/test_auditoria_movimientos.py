"""Regresiones de la auditoría: transferencias antiguas y fecha por defecto en hora Colombia."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'audmov.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.contabilidad import FUENTE_TRANSFERENCIA  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Movimiento  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="aud-m", email="a@test.com", nombre="A")
    yield


def _saldo(cuenta_id):
    return [c for c in client.get("/cuentas").json() if c["id"] == cuenta_id][0]["saldo"]


def _pata_antigua(saldo_actual, tipo, monto):
    """Cuenta con `saldo_actual` y una pata de transferencia SIN notas 'TRF:' (formato antiguo)."""
    cuenta = client.post("/cuentas", json={"nombre": f"C{tipo}{saldo_actual}", "saldo": saldo_actual}).json()["id"]
    db = SessionLocal()
    m = Movimiento(usuario_id="aud-m", cuenta_id=cuenta, descripcion="Traslado", categoria="Transferencia",
                   tipo=tipo, monto=monto, fuente=FUENTE_TRANSFERENCIA, notas="")
    db.add(m)
    db.commit()
    mid = m.id
    db.close()
    return cuenta, mid


def test_borrar_transferencia_antigua_salida_devuelve_el_dinero():
    # saldo 70.000 tras sacar 30.000 -> borrar la pata de salida devuelve a 100.000
    cuenta, mid = _pata_antigua(70_000, "expense", 30_000)
    assert client.delete(f"/movimientos/{mid}").status_code == 200
    assert _saldo(cuenta) == 100_000


def test_borrar_transferencia_antigua_entrada_resta_el_dinero():
    # saldo 130.000 tras recibir 30.000 -> borrar la pata de entrada baja a 100.000 (antes sumaba mal)
    cuenta, mid = _pata_antigua(130_000, "income", 30_000)
    assert client.delete(f"/movimientos/{mid}").status_code == 200
    assert _saldo(cuenta) == 100_000


def test_borrar_transferencia_antigua_ambigua_se_bloquea():
    cuenta, mid = _pata_antigua(50_000, "transfer", 30_000)
    r = client.delete(f"/movimientos/{mid}")
    assert r.status_code == 400 and "antigua" in r.json()["detail"]
    assert _saldo(cuenta) == 50_000
    db = SessionLocal()
    assert db.query(Movimiento).filter(Movimiento.id == mid).count() == 1
    db.close()
