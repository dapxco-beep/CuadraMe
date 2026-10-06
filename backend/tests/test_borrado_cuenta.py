"""Borrado de cuenta (Ley 1581): no debe quedar ninguna fila del usuario, ni huérfanas."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'borrado.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta  # noqa: E402
from app.models_gastos import ContactoGasto, GastoCompartido, GrupoGasto, MiembroGrupoGasto, ParteGasto  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": None}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _sembrar(db, uid):
    db.add(Cuenta(usuario_id=uid, nombre="Banco", saldo=10, moneda="COP"))
    contacto = ContactoGasto(usuario_id=uid, nombre="Amigo")
    grupo = GrupoGasto(usuario_id=uid, nombre="Viaje")
    db.add_all([contacto, grupo])
    db.flush()
    db.add(MiembroGrupoGasto(grupo_id=grupo.id, contacto_id=contacto.id))
    gasto = GastoCompartido(usuario_id=uid, grupo_id=grupo.id, descripcion="Cena", total=100, pagador_id="yo")
    db.add(gasto)
    db.flush()
    db.add_all([ParteGasto(gasto_id=gasto.id, participante_id="yo", monto=50),
                ParteGasto(gasto_id=gasto.id, participante_id=contacto.id, monto=50)])
    db.commit()


def _filas_de(db, uid):
    """Recorrido genérico: filas con usuario_id == uid + hijas sin usuario_id."""
    encontradas = {}
    for tabla in Base.metadata.sorted_tables:
        if "usuario_id" in tabla.c:
            n = db.execute(tabla.select().where(tabla.c.usuario_id == uid)).fetchall()
            if n:
                encontradas[tabla.name] = len(n)
    return encontradas


def test_borrar_cuenta_no_deja_filas_ni_huerfanas(monkeypatch):
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    USUARIO["actual"] = UsuarioActual(id="bor-1", email="b1@test.com", nombre="B")
    db = SessionLocal()
    try:
        _sembrar(db, "bor-1")
        _sembrar(db, "bor-otro")  # otro usuario: no debe tocarse
        assert _filas_de(db, "bor-1")

        r = client.post("/perfil/eliminar-cuenta", json={"confirmacion": "ELIMINAR"})
        assert r.status_code == 200 and r.json()["ok"] is True

        db.expire_all()
        assert _filas_de(db, "bor-1") == {}
        # Hijas sin usuario_id: solo deben quedar las del otro usuario (1 miembro, 2 partes).
        assert db.query(MiembroGrupoGasto).count() == 1
        assert db.query(ParteGasto).count() == 2
        assert _filas_de(db, "bor-otro")["grupos_gasto"] == 1
    finally:
        db.close()


def test_si_falla_auth_responde_ok_con_aviso_y_datos_borrados(monkeypatch):
    import httpx

    monkeypatch.setattr(settings, "supabase_service_role_key", "clave")

    def _falla(*a, **k):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(httpx, "delete", _falla)
    USUARIO["actual"] = UsuarioActual(id="bor-2", email="b2@test.com", nombre="B")
    db = SessionLocal()
    try:
        _sembrar(db, "bor-2")
        r = client.post("/perfil/eliminar-cuenta", json={"confirmacion": "ELIMINAR"}).json()
        assert r["ok"] is True and r["auth_eliminado"] is False
        assert "soporte" in r["aviso"]
        db.expire_all()
        assert _filas_de(db, "bor-2") == {}
    finally:
        db.close()
