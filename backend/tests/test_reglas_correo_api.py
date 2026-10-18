"""«Enséñale a leer este correo» de punta a punta con Gmail simulado: ver el texto, marcar monto y nombre (ICETEX de Nu),
crear la regla, traer de vuelta los correos parecidos que se habían descartado, leer uno nuevo con la regla, borrar.
El lector estándar se simula roto. Todo sintético."""
import base64
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'reglas_correo.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.autocat import ClasificadorUsuario  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.derechos_titular import borrar_todo  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CorreoGasto, ReglaCorreo  # noqa: E402
from app.routers import correos as rcor  # noqa: E402
from app.routers import reglas_correo as rrc  # noqa: E402
from tests.test_extractos_gmail import GmailFalso, mensaje  # noqa: E402

client = TestClient(app)
U1 = UsuarioActual(id="regla-u1", email="u1-regla@test.com", nombre="Uno")
U2 = UsuarioActual(id="regla-u2", email="u2-regla@test.com", nombre="Dos")
REM = "Nu <nu@nu.com.co>"
ASUNTO = "Pagaste con tu Cuenta de ahorros Nu"
CUERPO1 = ("Hola, Daniel Alfonso: Acá está el detalle de tu pago. Pagaste en: ICETEX. La cantidad de: $1.000.000,00. "
           "Más el impuesto del 4xmil de: $0,00. Si no fuiste tú, contáctanos vía chat")
CUERPO2 = CUERPO1.replace("ICETEX", "Colegio San José").replace("$1.000.000,00", "$350.000,00")


def _msg(id_, cuerpo):
    data = base64.urlsafe_b64encode(cuerpo.encode()).decode()
    return mensaje(id_, REM, ASUNTO, snippet="Hola, Daniel Alfonso: Acá está el detalle de tu pago.",
                   partes=[{"mimeType": "text/plain", "body": {"data": data}}])


@pytest.fixture
def entorno(monkeypatch):
    gmail = GmailFalso([_msg("nu1", CUERPO1), _msg("nu2", CUERPO2)], {})
    monkeypatch.setattr(rrc, "_gmail_del_usuario", lambda db, uid, modo="extracto": gmail)
    # El lector estándar "falla": ni monto ni comercio (así la regla es lo único que sabe leer este correo).
    monkeypatch.setattr(rcor, "extraer_monto", lambda *a, **k: 0.0)
    monkeypatch.setattr(rcor, "extraer_comercio", lambda *a, **k: "Gasto sin detalle")
    app.dependency_overrides[get_current_user] = lambda: U1
    yield gmail
    app.dependency_overrides.pop(get_current_user, None)
    db = SessionLocal()
    try:
        for u in (U1, U2):
            borrar_todo(db, u.id, u.email)
    finally:
        db.close()


def _sembrar_descartado():
    db = SessionLocal()
    try:
        db.add(CorreoGasto(usuario_id=U1.id, gmail_msg_id="viejo1", remitente=REM, asunto=ASUNTO, snippet="x",
                           monto=80_000, comercio="Gasto sin detalle", estado="ignorado"))
        db.commit()
    finally:
        db.close()


def test_ensenar_ver_texto_crear_regla_y_traer_parecidos(entorno):
    _sembrar_descartado()
    v = client.post("/reglas-correo/vista", json={"gmail_msg_id": "nu1"})
    assert v.status_code == 200, v.text
    vista = v.json()
    assert "La cantidad de: $1.000.000,00" in vista["texto"] and vista["monto_actual"] == 0
    assert vista["comercio_actual"] == "Gasto sin detalle"

    r = client.post("/reglas-correo", json={"gmail_msg_id": "nu1", "monto_texto": "$1.000.000,00",
                                            "comercio_texto": "ICETEX", "tipo": "expense"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["similares"] == 1 and cuerpo["regla"]["marca_monto"] and cuerpo["regla"]["marca_comercio"]
    assert cuerpo["regla"]["corrige"] is False
    # La regla no trae el cuerpo del correo: solo dominio y esqueleto.
    assert cuerpo["regla"]["remitente_dominio"] == "nu.com.co"
    assert cuerpo["regla"]["esqueleto_asunto"] == "pagaste con tu cuenta de ahorros nu"

    a = client.post(f"/reglas-correo/{cuerpo['regla']['id']}/aplicar-anteriores")
    assert a.status_code == 200 and a.json()["recuperados"] == 1
    db = SessionLocal()
    try:
        assert db.query(CorreoGasto).filter(CorreoGasto.gmail_msg_id == "viejo1").one().estado == "pendiente"
    finally:
        db.close()

    lista = client.get("/reglas-correo").json()
    assert len(lista) == 1 and lista[0]["id"] == cuerpo["regla"]["id"]


def test_un_correo_nuevo_parecido_se_lee_solo_con_la_regla(entorno):
    assert client.post("/reglas-correo", json={"gmail_msg_id": "nu1", "monto_texto": "$1.000.000,00",
                                               "comercio_texto": "ICETEX", "tipo": "expense"}).status_code == 200
    db = SessionLocal()
    try:
        modelo = ClasificadorUsuario(db, U1.id)
        candidato = rcor._procesar_transaccion(entorno, db, U1.id, "nu2", modelo, None, set())
        db.commit()
        c = db.query(CorreoGasto).filter(CorreoGasto.usuario_id == U1.id, CorreoGasto.gmail_msg_id == "nu2").one()
        assert candidato and c.estado == "pendiente"
        assert c.monto == 350_000 and c.comercio == "Colegio San José" and c.tipo_sugerido == "expense"
        assert db.query(ReglaCorreo).filter(ReglaCorreo.usuario_id == U1.id).one().usos == 1
    finally:
        db.close()


def test_sin_regla_el_lector_roto_lo_deja_de_lado(entorno):
    db = SessionLocal()
    try:
        modelo = ClasificadorUsuario(db, U1.id)
        assert rcor._procesar_transaccion(entorno, db, U1.id, "nu2", modelo, None, set()) is False
    finally:
        db.close()


def test_las_reglas_de_una_persona_no_leen_los_correos_de_otra(entorno):
    assert client.post("/reglas-correo", json={"gmail_msg_id": "nu1", "monto_texto": "$1.000.000,00",
                                               "comercio_texto": "ICETEX", "tipo": "expense"}).status_code == 200
    app.dependency_overrides[get_current_user] = lambda: U2
    assert client.get("/reglas-correo").json() == []
    db = SessionLocal()
    try:
        modelo = ClasificadorUsuario(db, U2.id)
        assert rcor._procesar_transaccion(entorno, db, U2.id, "nu2", modelo, None, set()) is False
    finally:
        db.close()


def test_marca_invalida_y_borrado(entorno):
    r = client.post("/reglas-correo", json={"gmail_msg_id": "nu1", "monto_texto": "$9.999.999", "tipo": "expense"})
    assert r.status_code == 400 and "monto" in r.json()["detail"].lower()
    assert client.post("/reglas-correo", json={"gmail_msg_id": "nu1", "tipo": "expense"}).status_code == 400
    assert client.post("/reglas-correo", json={"tipo": "expense"}).status_code == 400
    ok = client.post("/reglas-correo", json={"gmail_msg_id": "nu1", "monto_texto": "$1.000.000,00", "tipo": "income"}).json()
    assert client.delete(f"/reglas-correo/{ok['regla']['id']}").status_code == 200
    assert client.get("/reglas-correo").json() == []
    assert client.delete(f"/reglas-correo/{ok['regla']['id']}").status_code == 404
