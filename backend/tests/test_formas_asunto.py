"""Contador anónimo y opt-in de «formas de asunto» que fallan: sin consentimiento no cuenta nada; con él cuenta solo
el esqueleto (sin dígitos ni nombres) y el dominio, sin usuario; la lista interna exige el secreto de los crons."""
import base64
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'formas.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import formas_asunto as fa  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.autocat import ClasificadorUsuario  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal  # noqa: E402
from app.derechos_titular import borrar_todo  # noqa: E402
from app.main import app  # noqa: E402
from app.models import FormaAsuntoFallida  # noqa: E402
from app.routers import consentimientos as consent  # noqa: E402
from app.routers import correos as rcor  # noqa: E402
from tests.test_extractos_gmail import GmailFalso, mensaje  # noqa: E402

client = TestClient(app)
UA = UsuarioActual(id="forma-a", email="a-forma@test.com", nombre="A")
UB = UsuarioActual(id="forma-b", email="b-forma@test.com", nombre="B")
REM = "Nu <nu@nu.com.co>"
ASUNTO = "Pagaste en Colegio San José con Cuenta Nu 4455"


@pytest.fixture(autouse=True)
def _limpio():
    db = SessionLocal()
    db.query(FormaAsuntoFallida).delete()
    db.commit()
    db.close()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    db = SessionLocal()
    try:
        db.query(FormaAsuntoFallida).delete()
        for u in (UA, UB):
            borrar_todo(db, u.id, u.email)
    finally:
        db.close()


def _aceptar(usuario, si=True):
    app.dependency_overrides[get_current_user] = lambda: usuario
    r = client.post("/consentimientos", json={"version": consent.VERSION_TEXTOS, "items": [{"finalidad": "estadisticas_anonimas", "aceptado": si}]})
    assert r.status_code == 200, r.text
    return r.json()


def _filas():
    db = SessionLocal()
    try:
        return [(f.esqueleto, f.dominio, f.conteo) for f in db.query(FormaAsuntoFallida).all()]
    finally:
        db.close()


def test_la_finalidad_es_opcional_y_viene_apagada(monkeypatch):
    assert consent.FINALIDADES["estadisticas_anonimas"]["obligatoria"] is False
    app.dependency_overrides[get_current_user] = lambda: UA
    f = client.get("/consentimientos").json()["finalidades"]["estadisticas_anonimas"]
    assert f["aceptado"] is False


def test_sin_consentimiento_no_cuenta_nada():
    app.dependency_overrides[get_current_user] = lambda: UA
    db = SessionLocal()
    try:
        assert fa.registrar_forma(db, UA.id, REM, ASUNTO) is False
        db.commit()
    finally:
        db.close()
    assert _filas() == []


def test_con_consentimiento_cuenta_solo_la_forma_sin_datos_personales():
    _aceptar(UA)
    db = SessionLocal()
    try:
        assert fa.registrar_forma(db, UA.id, REM, ASUNTO)
        assert fa.registrar_forma(db, UA.id, REM, "Pagaste en Otro Lugar con Cuenta Nu 99")
        db.commit()
    finally:
        db.close()
    filas = _filas()
    assert len(filas) == 1 and filas[0][1] == "nu.com.co" and filas[0][2] == 2
    esq = filas[0][0]
    assert esq == "pagaste en * con cuenta nu *"
    assert not any(ch.isdigit() for ch in esq)
    for nombre in ("colegio", "san", "jose", "otro", "lugar"):
        assert nombre not in esq.split()


def test_la_tabla_no_tiene_usuario_ni_remitente_completo():
    cols = {c.name for c in Base.metadata.tables["formas_asunto_fallidas"].c}
    assert cols == {"id", "esqueleto", "dominio", "conteo", "primera_vez", "ultima_vez"}


def test_revocar_deja_de_contar():
    _aceptar(UA)
    _aceptar(UA, si=False)
    db = SessionLocal()
    try:
        assert fa.registrar_forma(db, UA.id, REM, ASUNTO) is False
    finally:
        db.close()


def test_correo_de_banco_que_no_se_lee_alimenta_el_contador_solo_si_acepto():
    cuerpo = "Hola. Movimiento realizado sin cifra legible."
    msg = mensaje("fx1", REM, "Pagaste con tu Cuenta de ahorros Nu", snippet=cuerpo,
                  partes=[{"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(cuerpo.encode()).decode()}}])
    gmail = GmailFalso([msg], {})
    for usuario, acepta in ((UB, False), (UA, True)):
        if acepta:
            _aceptar(usuario)
        db = SessionLocal()
        try:
            modelo = ClasificadorUsuario(db, usuario.id)
            assert rcor._procesar_transaccion(gmail, db, usuario.id, "fx1", modelo, None, set()) is False
            db.commit()
        finally:
            db.close()
        if not acepta:
            assert _filas() == []
    filas = _filas()
    assert len(filas) == 1 and filas[0][0] == "pagaste con tu cuenta de ahorros nu" and filas[0][2] == 1


def test_lista_interna_exige_el_secreto_de_los_crons():
    db = SessionLocal()
    try:
        db.add(FormaAsuntoFallida(esqueleto="pagaste en * con cuenta nu", dominio="nu.com.co", conteo=5))
        db.add(FormaAsuntoFallida(esqueleto="recibiste dinero de *", dominio="nu.com.co", conteo=9))
        db.commit()
    finally:
        db.close()
    url = "/formas-asunto/cron/mas-frecuentes"
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"X-Cron-Secret": "equivocado"}).status_code == 401
    r = client.get(url, headers={"X-Cron-Secret": settings.cron_secret})
    assert r.status_code == 200
    datos = r.json()
    assert [d["conteo"] for d in datos] == [9, 5]
    assert set(datos[0]) == {"esqueleto", "dominio", "conteo", "ultima_vez"}
