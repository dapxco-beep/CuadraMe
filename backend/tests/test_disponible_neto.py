"""GET /cuentas/resumen: «Tienes disponible» = ahorros y efectivo menos lo que se debe en tarjetas; las inversiones
(CDT, fondos) van aparte y no cuentan como plata para gastar. Números inventados."""
import os
import tempfile
import uuid

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'disponible_neto.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta  # noqa: E402

client = TestClient(app)


@pytest.fixture
def usuario():
    u = UsuarioActual(id=f"dn-{uuid.uuid4().hex[:8]}", email="dn@test.com", nombre="Dn")
    app.dependency_overrides[get_current_user] = lambda: u
    yield u
    app.dependency_overrides.pop(get_current_user, None)


def _cuentas(u, filas):
    db = SessionLocal()
    for nombre, tipo, saldo in filas:
        db.add(Cuenta(usuario_id=u.id, nombre=nombre, tipo=tipo, saldo=saldo, moneda="COP"))
    db.commit()
    db.close()


def test_el_disponible_no_cuenta_inversiones_y_resta_la_tarjeta(usuario):
    _cuentas(usuario, [("Banco", "ahorro", 4_000_000), ("Efectivo", "efectivo", 500_000),
                       ("CDT", "inversion", 5_000_000), ("Visa", "credito", -800_000)])
    r = client.get("/cuentas/resumen").json()
    assert r["liquido_cop"] == 4_500_000
    assert r["inversiones_cop"] == 5_000_000
    assert r["deudas_tarjeta_cop"] == 800_000
    assert r["disponible_neto_cop"] == 3_700_000  # 4.500.000 - 800.000
    assert r["disponible_cop"] == 9_500_000       # campo histórico: todo lo que no es tarjeta (no cambia)
    assert r["total_cop"] == 8_700_000            # saldo total = lo que cuadra con Cuentas y Patrimonio


def test_sin_inversiones_ni_tarjetas_el_neto_es_el_liquido(usuario):
    _cuentas(usuario, [("Banco", "ahorro", 1_000_000)])
    r = client.get("/cuentas/resumen").json()
    assert r["disponible_neto_cop"] == r["liquido_cop"] == 1_000_000
    assert r["inversiones_cop"] == 0
