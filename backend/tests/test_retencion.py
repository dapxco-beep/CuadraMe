"""Retención de datos de Gmail (minimización): apagada por defecto, ignorados vacíos, procesados con
huella, eventos, idempotencia, cron con secreto y simulación solo-admin. Datos sintéticos."""
import os
import tempfile
import uuid
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'retencion.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import retencion  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.duplicados import huella_correo  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CorreoGasto, ExtractoCorreo  # noqa: E402
from app.models_avisos import EventoActividad  # noqa: E402

client = TestClient(app)
CABECERA = {"X-Cron-Secret": "secreto-de-prueba"}
URL = "/correos/cron/purgar-retencion"
UID = "ret-u1"
VIEJO = datetime.utcnow() - timedelta(days=400)
RECIENTE = datetime.utcnow() - timedelta(days=2)


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "cron_secret", "secreto-de-prueba")
    for n in ("retencion_correos_ignorados_dias", "retencion_correos_procesados_dias", "retencion_eventos_dias"):
        monkeypatch.setattr(settings, n, 0)
    db = SessionLocal()
    try:
        for m in (CorreoGasto, ExtractoCorreo, EventoActividad):
            db.query(m).delete()
        db.commit()
    finally:
        db.close()
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _correo(estado, creado, msg=None, **kw):
    return CorreoGasto(
        usuario_id=UID, gmail_msg_id=msg or uuid.uuid4().hex, remitente="alertas@banco.co",
        asunto="Compra aprobada", snippet="Compra por $45.000 en EXITO", comercio="EXITO", monto=45000,
        estado=estado, creado_en=creado, recibido_en=creado, **kw)


def _sembrar():
    db = SessionLocal()
    try:
        db.add_all([
            _correo("ignorado", VIEJO, "m-ign-viejo"), _correo("ignorado", RECIENTE, "m-ign-nuevo"),
            _correo("descartado", VIEJO, "m-des-viejo"),
            _correo("aprobado", VIEJO, "m-apr-viejo", movimiento_id="mov-1"),
            _correo("ya_registrado", VIEJO, "m-yr-viejo", movimiento_id="mov-2"),
            _correo("aprobado", RECIENTE, "m-apr-nuevo", movimiento_id="mov-3"),
            _correo("pendiente", VIEJO, "m-pen-viejo"),
            ExtractoCorreo(usuario_id=UID, gmail_msg_id="e-ign", archivo="", remitente="a@b.co", asunto="Hola",
                           estado="ignorado", creado_en=VIEJO),
            ExtractoCorreo(usuario_id=UID, gmail_msg_id="e-proc", archivo="ext.pdf", remitente="a@b.co",
                           asunto="Extracto", banco="Bancolombia", periodo="2025-01", estado="ya_conciliado",
                           historial_id="h1", creado_en=VIEJO),
            ExtractoCorreo(usuario_id=UID, gmail_msg_id="e-nuevo", archivo="x.pdf", remitente="a@b.co",
                           asunto="Extracto", estado="nuevo", creado_en=VIEJO),
            EventoActividad(tipo="limite", clave_unica="limite:x:1", resumen="r", creado_en=VIEJO),
            EventoActividad(tipo="limite", clave_unica="limite:x:2", resumen="r", creado_en=RECIENTE),
            EventoActividad(tipo="nuevo_registro", clave_unica="nuevo_registro:u", resumen="r", creado_en=VIEJO),
        ])
        db.commit()
    finally:
        db.close()


def _c(msg):
    db = SessionLocal()
    try:
        return db.query(CorreoGasto).filter(CorreoGasto.gmail_msg_id == msg).one()
    finally:
        db.close()


def test_con_plazos_en_cero_no_se_borra_nada():
    _sembrar()
    r = client.post(URL, headers=CABECERA)
    assert r.status_code == 200
    assert r.json()["procesados"] == 0 and r.json()["completo"] is True
    db = SessionLocal()
    try:
        assert db.query(CorreoGasto).filter(CorreoGasto.asunto != "").count() == 7
        assert db.query(EventoActividad).count() == 3
        assert db.query(ExtractoCorreo).filter(ExtractoCorreo.asunto != "").count() == 3
    finally:
        db.close()


def test_ignorados_se_vacian_y_conservan_la_marca_anti_relectura(monkeypatch):
    _sembrar()
    monkeypatch.setattr(settings, "retencion_correos_ignorados_dias", 30)
    r = client.post(URL, headers=CABECERA).json()
    assert r["correos_ignorados"] == 2 and r["extractos_ignorados"] == 1 and r["correos_procesados"] == 0
    viejo = _c("m-ign-viejo")  # la fila sigue (no se vuelve a leer ni resucita) pero sin contenido
    assert (viejo.asunto, viejo.snippet, viejo.remitente, viejo.comercio) == ("", "", "", "")
    assert viejo.estado == "ignorado" and viejo.gmail_msg_id == "m-ign-viejo"
    assert _c("m-des-viejo").estado == "descartado" and _c("m-des-viejo").asunto == ""
    assert _c("m-ign-nuevo").asunto != ""      # dentro del plazo
    assert _c("m-apr-viejo").asunto != ""      # procesados: su plazo sigue apagado
    assert _c("m-pen-viejo").asunto != ""      # pendientes nunca se tocan


def test_procesados_conservan_huella_fecha_y_monto(monkeypatch):
    _sembrar()
    monkeypatch.setattr(settings, "retencion_correos_procesados_dias", 365)
    r = client.post(URL, headers=CABECERA).json()
    assert r["correos_procesados"] == 2 and r["extractos_procesados"] == 1 and r["correos_ignorados"] == 0
    c = _c("m-apr-viejo")
    assert (c.asunto, c.snippet, c.remitente, c.comercio) == ("", "", "", "")
    assert c.estado == "aprobado" and c.movimiento_id == "mov-1" and c.monto == 45000 and c.recibido_en is not None
    assert huella_correo(c.gmail_msg_id)  # la huella sale del id del mensaje, que se conserva
    assert _c("m-yr-viejo").estado == "ya_registrado"
    assert _c("m-apr-nuevo").asunto != ""
    db = SessionLocal()
    try:
        e = db.query(ExtractoCorreo).filter(ExtractoCorreo.gmail_msg_id == "e-proc").one()
        assert e.estado == "ya_conciliado" and e.periodo == "2025-01" and e.historial_id == "h1"
        assert e.archivo == "ext.pdf" and e.asunto == "" and e.remitente == ""
        assert db.query(ExtractoCorreo).filter(ExtractoCorreo.gmail_msg_id == "e-nuevo").one().asunto != ""
    finally:
        db.close()


def test_eventos_se_borran_salvo_la_marca_de_registro(monkeypatch):
    _sembrar()
    monkeypatch.setattr(settings, "retencion_eventos_dias", 365)
    r = client.post(URL, headers=CABECERA).json()
    assert r["eventos"] == 1
    db = SessionLocal()
    try:
        claves = {e.clave_unica for e in db.query(EventoActividad).all()}
        assert claves == {"limite:x:2", "nuevo_registro:u"}
    finally:
        db.close()


def test_idempotente_y_por_lotes(monkeypatch):
    _sembrar()
    monkeypatch.setattr(settings, "retencion_correos_ignorados_dias", 30)
    monkeypatch.setattr(settings, "retencion_correos_procesados_dias", 365)
    monkeypatch.setattr(settings, "retencion_eventos_dias", 365)
    db = SessionLocal()
    try:
        a = retencion.purgar(db, lote=1)  # lotes de 1 fila
        b = retencion.purgar(db)
    finally:
        db.close()
    assert a["correos_ignorados"] == 2 and a["correos_procesados"] == 2 and a["eventos"] == 1 and a["completo"]
    assert all(b[k] == 0 for k in retencion._CLAVES)


def test_tope_de_tiempo_deja_trabajo_para_la_proxima(monkeypatch):
    _sembrar()
    monkeypatch.setattr(settings, "retencion_correos_ignorados_dias", 30)
    t = iter(range(0, 1000, 100))
    monkeypatch.setattr(retencion, "_reloj", lambda: next(t))
    db = SessionLocal()
    try:
        r = retencion.purgar(db, presupuesto=150, lote=1)
    finally:
        db.close()
    assert r["completo"] is False


def test_un_fallo_no_detiene_las_demas_categorias(monkeypatch):
    _sembrar()
    monkeypatch.setattr(settings, "retencion_correos_ignorados_dias", 30)
    monkeypatch.setattr(settings, "retencion_eventos_dias", 365)
    original = retencion._poner_vacio

    def roto(modelo):
        if modelo is CorreoGasto:
            raise RuntimeError("falla simulada")
        return original(modelo)

    monkeypatch.setattr(retencion, "_poner_vacio", roto)
    db = SessionLocal()
    try:
        r = retencion.purgar(db)
    finally:
        db.close()
    assert r["fallidos"] == 1 and r["eventos"] == 1 and r["extractos_ignorados"] == 1


def test_cron_exige_secreto():
    assert client.post(URL).status_code == 401
    assert client.post(URL, headers={"X-Cron-Secret": "malo"}).status_code == 401


def test_simulacion_solo_admin(monkeypatch):
    _sembrar()
    monkeypatch.setattr(settings, "admin_email", "dueno@cuadrame.test")
    monkeypatch.setattr(settings, "retencion_correos_ignorados_dias", 30)
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="x", email="otro@test.com", nombre="O")
    assert client.get("/avisos/retencion").status_code == 404
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="a", email="Dueno@CuadraMe.test", nombre="D")
    r = client.get("/avisos/retencion")
    assert r.status_code == 200
    j = r.json()
    assert j["configuracion"]["correos_ignorados_dias"] == 30 and j["configuracion"]["eventos_dias"] == 0
    assert j["alcanzaria"]["correos_ignorados"] == 2 and j["alcanzaria"]["eventos"] == 0
    # simular no cambia nada
    assert _c("m-ign-viejo").asunto != ""
    assert "Compra" not in r.text  # nunca devuelve contenido
