"""GET /reportes/mensual lee solo el periodo (+ margen) en vez de todo el historial. El resultado debe ser IDÉNTICO al
de leer todo, también cuando un traslado entre cuentas propias cruza el borde del mes (por eso el margen)."""
import os
import tempfile
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'mensual_acotado.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento  # noqa: E402
from app.routers import reportes  # noqa: E402

client = TestClient(app)


@pytest.fixture
def usuario():
    u = UsuarioActual(id=f"ma-{uuid.uuid4().hex[:8]}", email="ma@test.com", nombre="Ma")
    app.dependency_overrides[get_current_user] = lambda: u
    db = SessionLocal()
    a = Cuenta(usuario_id=u.id, nombre="Banco A", tipo="ahorro", saldo=0, moneda="COP")
    b = Cuenta(usuario_id=u.id, nombre="Banco B", tipo="ahorro", saldo=0, moneda="COP")
    db.add_all([a, b])
    db.flush()

    def mv(cuenta, tipo, monto, desc, dia, cat="Otros", mes=10):
        db.add(Movimiento(usuario_id=u.id, cuenta_id=cuenta.id, fecha=datetime(2026, mes, dia, 12), descripcion=desc,
                          categoria=cat, tipo=tipo, monto=monto, fuente="manual", notas=""))

    mv(a, "income", 3_000_000, "Nomina", 1, "Ingresos", 9)
    mv(a, "expense", 120_000, "Mercado", 15, "Mercado", 9)
    mv(a, "income", 3_000_000, "Nomina", 1, "Ingresos")
    mv(a, "expense", 200_000, "Mercado", 12, "Mercado")
    mv(a, "expense", 45_000, "Taxi", 30, "Transporte")
    # Traslado propio que cruza el borde de octubre a noviembre (sale el 31/oct, entra el 2/nov)
    mv(a, "expense", 500_000, "Enviaste a Banco B", 31)
    mv(b, "income", 500_000, "Recibiste de Banco A", 2, "Otros", 11)
    # Otro dentro del mes y otro que cruza el borde de septiembre a octubre
    mv(a, "expense", 300_000, "Enviaste a Banco B", 10)
    mv(b, "income", 300_000, "Recibiste de Banco A", 10)
    mv(b, "expense", 80_000, "Enviaste a Banco A", 30, "Otros", 9)
    mv(a, "income", 80_000, "Recibiste de Banco B", 2)
    mv(a, "expense", 60_000, "Cine", 3, "Ocio", 11)
    db.commit()
    db.close()
    yield u
    app.dependency_overrides.pop(get_current_user, None)


CONSULTAS = ["", "?mes=2026-09", "?mes=2026-10", "?mes=2026-11", "?mes=2026-12", "?mes=2025-01",
             "?desde=2026-10-01&hasta=2026-10-31", "?desde=2026-09-15&hasta=2026-11-05", "?mes=basura", "?desde=2026-10-01"]


@pytest.mark.parametrize("q", CONSULTAS)
def test_resultado_identico_a_leer_todo_el_historial(usuario, monkeypatch, q):
    acotado = client.get(f"/reportes/mensual{q}")
    monkeypatch.setattr(reportes, "_limites_del_periodo", lambda *a, **k: None)  # comportamiento anterior: leer todo
    completo = client.get(f"/reportes/mensual{q}")
    assert acotado.status_code == completo.status_code
    assert acotado.json() == completo.json()


def test_los_traslados_del_borde_no_cuentan_como_gasto(usuario):
    oct_ = client.get("/reportes/mensual?mes=2026-10").json()
    assert oct_["gastos"] == 200_000 + 45_000  # ni el traslado del 31/oct ni el del 10/oct
    assert oct_["ingresos"] == 3_000_000  # ni el que entra el 2/oct ni el del 10/oct
