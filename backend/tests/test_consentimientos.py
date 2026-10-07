"""Autorización de tratamiento de datos (Ley 1581): registro auditable, bloqueos y error de Gmail."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'consent.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Consentimiento  # noqa: E402
from app.routers.consentimientos import VERSION_TEXTOS  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="co-0", email="c@test.com", nombre="C")}


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    monkeypatch.setattr(settings, "exigir_consentimientos", True)   # aquí SÍ se exige
    yield


def como(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def dar(*items, version=VERSION_TEXTOS):
    return client.post("/consentimientos", json={"version": version, "items": [{"finalidad": f, "aceptado": a} for f, a in items]})


def test_usuario_nuevo_debe_autorizar():
    como("co-nuevo")
    r = client.get("/consentimientos").json()
    assert r["requiere_autorizacion"] is True and r["version_vigente"] == VERSION_TEXTOS
    assert all(not f["aceptado"] for f in r["finalidades"].values())   # nada premarcado
    assert r["finalidades"]["tratamiento_basico"]["obligatoria"] is True
    assert r["finalidades"]["ia"]["obligatoria"] is False


def test_aceptar_basico_y_opcionales_por_separado():
    como("co-acepta")
    r = dar(("tratamiento_basico", True), ("ia", True), ("lectura_correo", False), ("notificaciones", False)).json()
    assert r["requiere_autorizacion"] is False
    f = r["finalidades"]
    assert f["tratamiento_basico"]["aceptado"] and f["ia"]["aceptado"]
    assert not f["lectura_correo"]["aceptado"] and not f["notificaciones"]["aceptado"]
    assert f["ia"]["fecha_utc"] and f["ia"]["fecha_co"] and f["ia"]["version"] == VERSION_TEXTOS


def test_revocar_agrega_fila_y_no_borra_historico():
    como("co-revoca")
    dar(("tratamiento_basico", True), ("ia", True))
    dar(("ia", False))
    dar(("ia", True))
    with SessionLocal() as db:
        filas = db.query(Consentimiento).filter_by(usuario_id="co-revoca", finalidad="ia").order_by(Consentimiento.creado_en_utc).all()
        assert [f.aceptado for f in filas] == [True, False, True]       # 3 registros, ninguno editado
        assert all(f.creado_en_co and f.creado_en_utc for f in filas)
        # La hora Colombia va 5 horas atrás de UTC
        d = (filas[0].creado_en_utc - filas[0].creado_en_co).total_seconds()
        assert 4.9 * 3600 < d < 5.1 * 3600
    h = client.get("/consentimientos/historial").json()
    assert len([x for x in h if x["finalidad"] == "ia"]) == 3
    assert "ip" not in h[0]
    assert client.get("/consentimientos").json()["finalidades"]["ia"]["aceptado"] is True


def test_nueva_version_de_textos_vuelve_a_pedir_autorizacion():
    como("co-version")
    with SessionLocal() as db:   # alguien que aceptó una versión anterior
        from app.utiles import ahora_co
        from datetime import datetime
        db.add(Consentimiento(usuario_id="co-version", version="1.0", finalidad="tratamiento_basico", aceptado=True,
                              creado_en_utc=datetime.utcnow(), creado_en_co=ahora_co()))
        db.commit()
    assert client.get("/consentimientos").json()["requiere_autorizacion"] is True
    dar(("tratamiento_basico", True))
    assert client.get("/consentimientos").json()["requiere_autorizacion"] is False


def test_validaciones():
    como("co-valida")
    assert dar(("inventada", True)).status_code == 400
    assert dar(("ia", True), ("ia", False)).status_code == 400
    assert dar(("ia", True), version="0.1").status_code == 400
    assert client.post("/consentimientos", json={"version": VERSION_TEXTOS, "items": []}).status_code == 400


def test_consentimientos_son_privados_por_usuario():
    como("co-priv-a")
    dar(("tratamiento_basico", True), ("ia", True))
    como("co-priv-b")
    assert client.get("/consentimientos").json()["finalidades"]["ia"]["aceptado"] is False
    assert client.get("/consentimientos/historial").json() == []


def test_gmail_se_bloquea_sin_consentimiento_especifico(monkeypatch):
    como("co-gmail")
    monkeypatch.setattr("app.routers.correos.url_autorizacion", lambda state: "https://accounts.google.com/x")
    monkeypatch.setattr("app.routers.correos.crear_state", lambda uid: "state-de-prueba")
    r = client.get("/correos/gmail/conectar")
    assert r.status_code == 403
    assert r.json()["detail"]["codigo"] == "consentimiento_requerido" and r.json()["detail"]["finalidad"] == "lectura_correo"
    assert client.get("/correos/gmail/estado").json()["consentimiento"] is False
    dar(("tratamiento_basico", True), ("lectura_correo", True))
    assert client.get("/correos/gmail/conectar").status_code == 200
    assert client.get("/correos/gmail/estado").json()["consentimiento"] is True
    dar(("lectura_correo", False))        # revocar vuelve a bloquear
    assert client.get("/correos/gmail/conectar").status_code == 403


def test_ia_se_bloquea_sin_consentimiento(monkeypatch):
    como("co-ia")
    r = client.post("/asistente/mensaje", json={"texto": "¿En qué gasté más este mes?"})
    assert r.status_code == 403 and r.json()["detail"]["finalidad"] == "ia"
    r = client.post("/facturas/escanear", json={"imagen_base64": "AAAA", "mime": "image/jpeg"})
    assert r.status_code == 403 and r.json()["detail"]["finalidad"] == "ia"
    dar(("tratamiento_basico", True), ("ia", True))
    assert client.post("/asistente/mensaje", json={"texto": "¿En qué gasté más este mes?"}).status_code == 200


def test_callback_access_denied_redirige_a_la_app_con_mensaje():
    r = client.get("/correos/oauth/callback?error=access_denied", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == f"{settings.pwa_url}/#/correos?gmail=sin_acceso"
    r = client.get("/correos/oauth/callback?error=otra_cosa", follow_redirects=False)
    assert r.headers["location"].endswith("/#/correos?gmail=error")


def test_callback_sin_code_ni_error_es_400():
    assert client.get("/correos/oauth/callback", follow_redirects=False).status_code == 400


def test_estado_gmail_expone_modo_pruebas_y_soporte(monkeypatch):
    como("co-soporte")
    monkeypatch.setattr(settings, "soporte_email", "ayuda@cuadrame.test")
    e = client.get("/correos/gmail/estado").json()
    assert e["modo_pruebas"] is True and e["soporte_email"] == "ayuda@cuadrame.test"


def test_eliminar_cuenta_borra_tambien_los_consentimientos():
    como("co-borra")
    dar(("tratamiento_basico", True))
    assert client.post("/perfil/eliminar-cuenta", json={"confirmacion": "ELIMINAR"}).status_code == 200
    with SessionLocal() as db:
        assert db.query(Consentimiento).filter_by(usuario_id="co-borra").count() == 0
