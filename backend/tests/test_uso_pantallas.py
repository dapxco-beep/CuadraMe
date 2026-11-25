"""Uso de pantallas (opt-in, anónimo): sin consentimiento no cuenta nada; con él cuenta solo la ruta de la app."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'uso.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import formas_asunto as fa  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.derechos_titular import borrar_todo  # noqa: E402
from app.main import app  # noqa: E402
from app.models import FormaAsuntoFallida  # noqa: E402
from app.routers import consentimientos as consent  # noqa: E402

client = TestClient(app)
U = UsuarioActual(id="uso-a", email="a-uso@test.com", nombre="A")


@pytest.fixture(autouse=True)
def _limpio():
    db = SessionLocal()
    db.query(FormaAsuntoFallida).delete()
    db.commit()
    db.close()
    app.dependency_overrides[get_current_user] = lambda: U
    yield
    app.dependency_overrides.pop(get_current_user, None)
    db = SessionLocal()
    try:
        db.query(FormaAsuntoFallida).delete()
        borrar_todo(db, U.id, U.email)
    finally:
        db.close()


def _aceptar(si=True):
    r = client.post("/consentimientos", json={"version": consent.VERSION_TEXTOS, "items": [{"finalidad": "estadisticas_anonimas", "aceptado": si}]})
    assert r.status_code == 200, r.text


def _filas():
    db = SessionLocal()
    try:
        return [(f.esqueleto, f.dominio, f.conteo) for f in db.query(FormaAsuntoFallida).all()]
    finally:
        db.close()


def test_sin_consentimiento_no_cuenta_nada():
    r = client.post("/formas-asunto/pantalla", json={"ruta": "/presupuesto"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert _filas() == []


def test_con_consentimiento_cuenta_solo_la_ruta():
    _aceptar()
    for ruta in ("/presupuesto?tab=fijos", "/presupuesto?tab=fijos", "/movimientos/:id"):
        assert client.post("/formas-asunto/pantalla", json={"ruta": ruta}).status_code == 200
    filas = sorted(_filas())
    assert filas == [("pantalla /movimientos/:id", "pantalla", 1), ("pantalla /presupuesto?tab=fijos", "pantalla", 2)]


def test_rutas_raras_se_ignoran():
    _aceptar()
    for ruta in ("", "presupuesto", "/Presupuesto", "/a b", "/x?y=1", "/" + "a" * 100, "/cuentas/juan@correo.com"):
        client.post("/formas-asunto/pantalla", json={"ruta": ruta})
    assert _filas() == []


def test_revocar_deja_de_contar():
    _aceptar()
    client.post("/formas-asunto/pantalla", json={"ruta": "/informes"})
    _aceptar(False)
    client.post("/formas-asunto/pantalla", json={"ruta": "/informes"})
    assert _filas()[0][2] == 1


def test_la_lista_interna_exige_el_secreto_y_no_mezcla_con_las_formas_de_asunto():
    _aceptar()
    client.post("/formas-asunto/pantalla", json={"ruta": "/informes"})
    assert client.get("/formas-asunto/cron/pantallas").status_code == 401
    db = SessionLocal()
    try:
        assert fa.pantallas_mas_usadas(db) == [{"ruta": "/informes", "aperturas": 1, "ultima_vez": fa.pantallas_mas_usadas(db)[0]["ultima_vez"]}]
        assert fa.mas_frecuentes(db) == []  # las pantallas no se mezclan con las formas de asunto
    finally:
        db.close()
