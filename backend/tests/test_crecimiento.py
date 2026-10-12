"""Monitor de capacidad y crecimiento: umbrales, idempotencia, tolerancia a fallos, panel solo-admin.
Todo con datos sintéticos; el envío por Resend y Sentry se reemplazan por capturas."""
import asyncio
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'crecimiento.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import crecimiento, monitor  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.crons import MarcaCron  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.limites_diarios import LIMITES_DIARIOS, UsoDiario  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento, Perfil  # noqa: E402
from app.seguridad import SeguridadMiddleware  # noqa: E402

client = TestClient(app)
CRON = {"X-Cron-Secret": "secreto-de-prueba"}
ADMIN = UsuarioActual(id="crec-admin", email="Dueno@CuadraMe.test", nombre="Dueño")
NORMAL = UsuarioActual(id="crec-normal", email="cliente@test.com", nombre="Cliente")
LUNES = datetime(2026, 10, 5, 8, 0)  # lunes
MIERCOLES = datetime(2026, 10, 7, 8, 0)


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    db = SessionLocal()
    db.query(MarcaCron).filter(MarcaCron.usuario_id == crecimiento.SISTEMA).delete()
    db.commit()
    db.close()
    monkeypatch.setattr(settings, "admin_email", "dueno@cuadrame.test")
    monkeypatch.setattr(settings, "resend_api_key", "re_clave_de_prueba")
    monkeypatch.setattr(settings, "gmail_tope_usuarios", 100)
    monkeypatch.setattr(settings, "supabase_db_limite_mb", 500)
    monitor.reiniciar()
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def correos(monkeypatch):
    enviados = []
    monkeypatch.setattr(crecimiento, "_enviar", lambda destino, asunto, texto: enviados.append((destino, asunto, texto)))
    return enviados


@pytest.fixture
def sentry(monkeypatch):
    mensajes = []
    monkeypatch.setattr(crecimiento.sentry_sdk, "capture_message", lambda msg, level=None: mensajes.append((msg, level)))
    return mensajes


def medicion(**cambios) -> dict:
    """Mediciones sintéticas (todo en cero salvo lo que se pida)."""
    m = {
        "generado_en": "2026-10-07T08:00:00", "usuarios_total": 10, "activos_7d": 5, "activos_30d": 8,
        "nuevos_7d": 2, "nuevos_30d": 6, "gmail": 0, "base_mb": 10.0, "base_limite_mb": 500,
        "movimientos": 1000, "correos_procesados": 50, "extractos_procesados": 5, "ia_mes": 0,
        "resend_dia": 0, "resend_mes": 0, "errores_5xx_24h": 0, "usuarios_en_tope_7d": 0, "tendencia": [],
        "dia": "2026-10-07", "mes": "2026-10", "semana": "2026-W41",
    }
    m.update(cambios)
    return m


@pytest.fixture
def fijar(monkeypatch):
    def _fijar(**cambios):
        monkeypatch.setattr(crecimiento, "recopilar", lambda db, ahora=None: medicion(**cambios))
        # El resumen semanal solo sale los lunes: se fija un miércoles para que la prueba no dependa del día real.
        monkeypatch.setattr(crecimiento, "ahora_co", lambda: MIERCOLES)
    return _fijar


def correr(fijar, **cambios):
    fijar(**cambios)
    r = client.post("/metricas/cron/avisos-crecimiento", headers=CRON)
    assert r.status_code == 200, r.text
    return r.json()


# ── Umbrales e idempotencia ───────────────────────────────────────────────────────
def test_sin_secreto_401():
    assert client.post("/metricas/cron/avisos-crecimiento").status_code == 401


def test_todo_normal_no_avisa(fijar, correos):
    r = correr(fijar)
    assert r["avisos"] == [] and r["enviado"] is False and correos == []


def test_gmail_avisa_una_sola_vez_por_umbral(fijar, correos):
    r = correr(fijar, gmail=64)
    assert [a["umbral"] for a in r["avisos"]] == [60] and r["enviado"] is True
    assert len(correos) == 1 and correos[0][0] == "dueno@cuadrame.test"
    assert correos[0][1] == "CuadraMe: llegaste al 60 % de usuarios con Gmail conectado"
    assert "QUÉ HACER" in correos[0][2] and "verificación" in correos[0][2]
    # misma situación otra vez: nada nuevo
    assert correr(fijar, gmail=66)["avisos"] == [] and len(correos) == 1
    # sube a 85: solo el 80 (el 60 ya se avisó)
    assert [a["umbral"] for a in correr(fijar, gmail=85)["avisos"]] == [80]
    # salta a 100: solo se avisa el más alto, no el 90 también
    assert [a["umbral"] for a in correr(fijar, gmail=100)["avisos"]] == [100]
    assert len(correos) == 3


def test_base_80_por_ciento_asunto_y_accion(fijar, correos):
    r = correr(fijar, base_mb=410.0)
    assert [a["id"] for a in r["avisos"]] == [("base")] and r["avisos"][0]["umbral"] == 80
    assert correos[0][1] == "CuadraMe: llegaste al 80 % de la base de datos"
    assert "Supabase Pro" in correos[0][2]


def test_varios_avisos_van_en_un_solo_correo(fijar, correos):
    r = correr(fijar, gmail=82, base_mb=470.0)
    assert len(r["avisos"]) == 2 and len(correos) == 1
    assert "2 avisos" in correos[0][1]


def test_resend_diario_se_rearma_al_dia_siguiente(fijar, correos):
    correr(fijar, resend_dia=85)
    assert correr(fijar, resend_dia=85)["avisos"] == []
    assert [a["umbral"] for a in correr(fijar, resend_dia=85, dia="2026-10-08")["avisos"]] == [80]


def test_senal_de_errores_5xx(fijar, correos, monkeypatch):
    monkeypatch.setattr(settings, "errores_5xx_aviso", 20)
    assert correr(fijar, errores_5xx_24h=5)["avisos"] == []
    r = correr(fijar, errores_5xx_24h=30)
    assert r["avisos"][0]["id"] == "errores_5xx"
    assert correr(fijar, errores_5xx_24h=31)["avisos"] == []


# ── Tolerancia a fallos ───────────────────────────────────────────────────────────
def test_si_el_envio_falla_se_libera_y_se_reintenta(fijar, monkeypatch):
    def _roto(*a, **k):
        raise RuntimeError("Resend caído")

    monkeypatch.setattr(crecimiento, "_enviar", _roto)
    r = correr(fijar, gmail=85)
    assert r["ok"] is False and r["enviado"] is False and r["fallidos"] >= 1
    enviados = []
    monkeypatch.setattr(crecimiento, "_enviar", lambda d, a, t: enviados.append(a))
    r2 = correr(fijar, gmail=85)
    assert r2["enviado"] is True and len(enviados) == 1


def test_sin_admin_email_solo_log_y_no_se_cae(fijar, correos, monkeypatch, caplog):
    monkeypatch.setattr(settings, "admin_email", "")
    r = correr(fijar, gmail=85)
    assert r["enviado"] is False and correos == [] and len(r["avisos"]) == 1
    assert any("ADMIN_EMAIL" in rec.message for rec in caplog.records)


def test_una_medicion_que_falla_no_tumba_el_monitor(monkeypatch):
    def _roto(db):
        raise RuntimeError("sin permiso")

    monkeypatch.setattr(crecimiento, "tamano_base_bytes", _roto)
    db = SessionLocal()
    try:
        m = crecimiento.recopilar(db, MIERCOLES)
    finally:
        db.close()
    assert m["base_mb"] is None and m["usuarios_total"] is not None
    cap = {c["id"]: c for c in crecimiento.capacidades(m)}
    assert cap["base"]["pct"] is None and cap["base"]["nivel"] == "sin_dato"


def test_tamano_base_usa_pg_database_size_solo_en_postgres():
    class Dialecto:
        name = "postgresql"

    class Resultado:
        def scalar(self):
            return 250 * 1_048_576

    class FalsaDB:
        class bind:  # noqa: N801
            dialect = Dialecto

        consultas = []

        def execute(self, q):
            self.consultas.append(str(q))
            return Resultado()

    db = FalsaDB()
    assert crecimiento.tamano_base_bytes(db) == 250 * 1_048_576
    assert "pg_database_size" in db.consultas[0]
    db2 = SessionLocal()
    try:
        assert crecimiento.tamano_base_bytes(db2) is None  # SQLite
    finally:
        db2.close()


# ── Resumen semanal y Sentry ──────────────────────────────────────────────────────
def test_resumen_semanal_solo_lunes_y_una_vez(fijar, correos, monkeypatch):
    fijar()
    db = SessionLocal()
    try:
        assert crecimiento.procesar_avisos(db, MIERCOLES)["resumen_semanal"] == "no_toca"
        assert crecimiento.procesar_avisos(db, LUNES)["resumen_semanal"] == "enviado"
        assert crecimiento.procesar_avisos(db, LUNES)["resumen_semanal"] == "ya_enviado"
    finally:
        db.close()
    asuntos = [c[1] for c in correos]
    assert asuntos == ["CuadraMe: resumen semanal de crecimiento"]
    assert "Nuevos esta semana: 2" in correos[0][2] and "Base de datos" in correos[0][2]


def test_sentry_recibe_mensajes_sin_datos_personales(fijar, correos, sentry):
    correr(fijar, gmail=85, base_mb=300.0)
    assert sentry, "debía registrar en Sentry"
    for msg, nivel in sentry:
        assert nivel in ("info", "warning")
        assert "@" not in msg and "dueno" not in msg.lower()
    assert ("Capacidad: gmail alcanzó el 80 % del límite", "warning") in sentry
    assert ("Capacidad: base alcanzó el 60 % del límite", "info") in sentry


# ── Mediciones reales (SQLite sintético) ──────────────────────────────────────────
def test_recopilar_cuenta_usuarios_activos_gmail_y_topes():
    db = SessionLocal()
    ahora = datetime(2026, 10, 7, 12, 0)
    try:
        antes = crecimiento.recopilar(db, ahora)
        db.add_all([
            Perfil(usuario_id="crec-u1", creado_en=ahora - timedelta(days=2), gmail_conectado=True),
            Perfil(usuario_id="crec-u2", creado_en=ahora - timedelta(days=20)),
            Perfil(usuario_id="crec-u3", creado_en=None),  # antiguo: sin fecha de alta
        ])
        db.add(Cuenta(id="crec-c1", usuario_id="crec-u1", nombre="Caja"))
        db.add(Movimiento(usuario_id="crec-u1", cuenta_id="crec-c1", fecha=ahora - timedelta(days=1),
                          descripcion="x", tipo="expense", monto=1))
        accion, (tope, _n) = next(iter(LIMITES_DIARIOS.items()))
        db.add(UsoDiario(usuario_id="crec-u2", accion=accion, dia="2026-10-06", cantidad=tope))
        db.commit()
        # El ORM aplica el default al insertar None: se deja en NULL a mano, como un perfil antiguo.
        db.query(Perfil).filter(Perfil.usuario_id == "crec-u3").update({Perfil.creado_en: None})
        db.commit()
        despues = crecimiento.recopilar(db, ahora)
        assert despues["usuarios_total"] == antes["usuarios_total"] + 3
        assert despues["nuevos_7d"] == antes["nuevos_7d"] + 1
        assert despues["nuevos_30d"] == antes["nuevos_30d"] + 2
        assert despues["gmail"] == antes["gmail"] + 1
        assert despues["activos_7d"] >= antes["activos_7d"] + 2  # u1 por movimiento, u2 por uso diario
        assert despues["usuarios_en_tope_7d"] == antes["usuarios_en_tope_7d"] + 1
        assert despues["movimientos"] == antes["movimientos"] + 1
        assert len(despues["tendencia"]) == 30
        totales = [p["total"] for p in despues["tendencia"]]
        assert totales == sorted(totales) and totales[-1] <= despues["usuarios_total"]  # acumulado creciente
    finally:
        db.query(Movimiento).filter(Movimiento.usuario_id == "crec-u1").delete()
        db.query(Cuenta).filter(Cuenta.id == "crec-c1").delete()
        db.query(UsoDiario).filter(UsoDiario.usuario_id == "crec-u2").delete()
        db.query(Perfil).filter(Perfil.usuario_id.in_(["crec-u1", "crec-u2", "crec-u3"])).delete()
        db.commit()
        db.close()


def test_contador_de_correos_enviados_alimenta_resend():
    antes_db = SessionLocal()
    try:
        antes = crecimiento.recopilar(antes_db)
    finally:
        antes_db.close()
    crecimiento.registrar_correo_enviado()
    crecimiento.registrar_correo_enviado()
    db = SessionLocal()
    try:
        despues = crecimiento.recopilar(db)
        assert despues["resend_dia"] == antes["resend_dia"] + 2
        assert despues["resend_mes"] == antes["resend_mes"] + 2
    finally:
        db.query(UsoDiario).filter(UsoDiario.usuario_id == crecimiento.SISTEMA).delete()
        db.commit()
        db.close()


def test_middleware_cuenta_5xx_y_excepciones():
    async def app_500(scope, receive, send):
        await send({"type": "http.response.start", "status": 503, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def app_explota(scope, receive, send):
        raise RuntimeError("boom")

    async def app_ok(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def llamar(aplicacion):
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(_m):
            pass

        await SeguridadMiddleware(aplicacion)({"type": "http", "method": "GET", "path": "/x", "headers": []}, receive, send)

    asyncio.run(llamar(app_ok))
    assert monitor.contar_5xx() == 0
    asyncio.run(llamar(app_500))
    assert monitor.contar_5xx() == 1
    with pytest.raises(RuntimeError):
        asyncio.run(llamar(app_explota))
    assert monitor.contar_5xx() == 2


# ── Panel solo para el administrador ──────────────────────────────────────────────
def como(u):
    app.dependency_overrides[get_current_user] = lambda: u


def test_panel_admin_ve_todo():
    como(ADMIN)  # el correo se compara sin importar mayúsculas
    r = client.get("/metricas/panel")
    assert r.status_code == 200, r.text
    p = r.json()
    ids = {c["id"] for c in p["capacidades"]}
    assert {"gmail", "base", "resend_dia", "resend_mes", "ia_mes"} <= ids
    assert len(p["tendencia"]) == 30 and "usuarios_total" in p["usuarios"]
    assert {s["id"] for s in p["senales"]} == {"errores_5xx", "topes_diarios"}
    assert all("accion" in c and "significa" in c for c in p["capacidades"])


def test_panel_usuario_normal_recibe_404():
    como(NORMAL)
    assert client.get("/metricas/panel").status_code == 404


def test_panel_sin_admin_email_configurado_404(monkeypatch):
    monkeypatch.setattr(settings, "admin_email", "")
    como(ADMIN)
    assert client.get("/metricas/panel").status_code == 404
    como(UsuarioActual(id="x", email="", nombre=""))
    assert client.get("/metricas/panel").status_code == 404


def test_panel_sin_sesion_401():
    assert client.get("/metricas/panel").status_code == 401
