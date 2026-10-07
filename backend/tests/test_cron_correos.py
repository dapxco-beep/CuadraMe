"""Cron de sincronización periódica de Gmail (POST /correos/cron/sincronizar), con Gmail simulado:
aislamiento por usuario, consentimiento, presupuesto de tiempo, idempotencia y un solo push."""
import os
import tempfile
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'cron_correos.db')}")

import pytest  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402
from google.auth.exceptions import RefreshError  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import CorreoGasto, Consentimiento, Perfil  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402
from tests.test_extractos_gmail import GmailFalso, client, mensaje  # noqa: E402

CABECERA = {"X-Cron-Secret": "secreto-de-prueba"}
URL = "/correos/cron/sincronizar"


def _compra(id_, monto="45.000"):
    return mensaje(id_, "Bancolombia <alertas@alertas.bancolombia.com.co>", "Compra aprobada",
                   f"Compra por ${monto} en EXITO con tu tarjeta")


@pytest.fixture()
def entorno(monkeypatch):
    """Solo los usuarios de la prueba tienen Gmail conectado; push y Gmail simulados."""
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    db = SessionLocal()
    try:
        db.query(Perfil).update({Perfil.gmail_conectado: False})
        db.commit()
    finally:
        db.close()
    gmails: dict = {}
    llamadas: list = []
    avisos: list = []

    def cliente(token):
        llamadas.append(token)
        g = gmails[token]
        if isinstance(g, Exception):
            raise g
        return g

    monkeypatch.setattr(router_correos, "cliente_gmail", cliente)
    monkeypatch.setattr(router_correos, "enviar_push", lambda db, uid, titulo, cuerpo, url="/": avisos.append((uid, cuerpo)) or 1)
    return {"gmails": gmails, "llamadas": llamadas, "avisos": avisos}


def _usuario(env, gmail, consentimiento=True):
    uid = f"cron-{uuid.uuid4().hex[:8]}"
    token = f"tok-{uid}"
    env["gmails"][token] = gmail
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", gmail_conectado=True, gmail_refresh_token_enc=token, gmail_email="x@gmail.com"))
        if consentimiento:
            ahora = datetime.utcnow()
            db.add(Consentimiento(usuario_id=uid, version="1.1", finalidad="lectura_correo", aceptado=True,
                                  creado_en_utc=ahora, creado_en_co=ahora))
        db.commit()
    finally:
        db.close()
    return uid, token


def _pendientes(uid):
    db = SessionLocal()
    try:
        return db.query(CorreoGasto).filter(CorreoGasto.usuario_id == uid, CorreoGasto.estado == "pendiente").count()
    finally:
        db.close()


def test_exige_secreto():
    assert client.post(URL).status_code == 401
    assert client.post(URL, headers={"X-Cron-Secret": "otro"}).status_code == 401


def test_dos_usuarios_uno_falla_el_otro_se_sincroniza_y_recibe_un_push(entorno):
    uid_ok, _ = _usuario(entorno, GmailFalso([_compra("m1"), _compra("m2", "12.000")], {}))
    uid_mal, _ = _usuario(entorno, RuntimeError("Gmail caído"))
    r = client.post(URL, headers=CABECERA).json()
    assert r["ok"] is True and r["procesados"] == 1 and r["fallidos"] == 1 and r["nuevos"] == 2
    assert _pendientes(uid_ok) == 2 and _pendientes(uid_mal) == 0
    assert entorno["avisos"] == [(uid_ok, "Encontré 2 movimientos nuevos en tu correo")]


def test_sin_consentimiento_se_omite_sin_llamar_a_gmail(entorno):
    _uid, token = _usuario(entorno, GmailFalso([_compra("m1")], {}), consentimiento=False)
    r = client.post(URL, headers=CABECERA).json()
    assert r["sin_consentimiento"] == 1 and r["nuevos"] == 0 and r["fallidos"] == 0
    assert token not in entorno["llamadas"] and entorno["avisos"] == []


def test_revocar_el_consentimiento_tambien_lo_omite(entorno):
    uid, token = _usuario(entorno, GmailFalso([_compra("m1")], {}))
    db = SessionLocal()
    try:
        ahora = datetime.utcnow()
        db.add(Consentimiento(usuario_id=uid, version="1.1", finalidad="lectura_correo", aceptado=False,
                              creado_en_utc=ahora, creado_en_co=ahora))
        db.commit()
    finally:
        db.close()
    assert client.post(URL, headers=CABECERA).json()["sin_consentimiento"] == 1
    assert token not in entorno["llamadas"]


def test_idempotente_la_segunda_ejecucion_no_duplica_ni_avisa(entorno):
    uid, _ = _usuario(entorno, GmailFalso([_compra("m1")], {}))
    r1 = client.post(URL, headers=CABECERA).json()
    r2 = client.post(URL, headers=CABECERA).json()
    assert r1["nuevos"] == 1 and r2["nuevos"] == 0 and r2["fallidos"] == 0
    assert _pendientes(uid) == 1
    assert len(entorno["avisos"]) == 1  # sin nuevos no hay push


def test_sin_nada_nuevo_no_hay_push(entorno):
    _usuario(entorno, GmailFalso([], {}))
    r = client.post(URL, headers=CABECERA).json()
    assert r["nuevos"] == 0 and r["avisados"] == 0 and entorno["avisos"] == []


def test_presupuesto_de_tiempo_corta_y_la_siguiente_ejecucion_continua(entorno, monkeypatch):
    usuarios = [_usuario(entorno, GmailFalso([_compra(f"t{i}")], {}))[0] for i in range(3)]
    reloj = {"t": 0.0}

    def avanzar():
        reloj["t"] += 20.0  # cada consulta del reloj "pasan" 20 s
        return reloj["t"]

    monkeypatch.setattr(router_correos, "_reloj", avanzar)
    r1 = client.post(URL, headers=CABECERA).json()
    # El reloj marca 20 (inicio), 40, 60, 80: transcurridos 20 y 40 s caben dos usuarios; con 60 s corta.
    assert r1["procesados"] == 2 and r1["pendientes_por_tiempo"] == 1
    hechos = sum(1 for u in usuarios if _pendientes(u))
    assert hechos == r1["procesados"] and hechos < 3

    monkeypatch.setattr(router_correos, "_reloj", lambda: 0.0)  # ahora sí hay tiempo
    r2 = client.post(URL, headers=CABECERA).json()
    assert r2["pendientes_por_tiempo"] == 0
    assert all(_pendientes(u) == 1 for u in usuarios)  # nadie duplicado ni perdido
    assert r1["nuevos"] + r2["nuevos"] == 3


def test_acceso_revocado_desconecta_y_no_detiene_a_los_demas(entorno):
    uid_rev, _ = _usuario(entorno, RefreshError("invalid_grant"))
    uid_ok, _ = _usuario(entorno, GmailFalso([_compra("m1")], {}))
    r = client.post(URL, headers=CABECERA).json()
    assert r["desconectados"] == 1 and r["fallidos"] == 0 and r["nuevos"] == 1
    db = SessionLocal()
    try:
        perfil = db.query(Perfil).filter(Perfil.usuario_id == uid_rev).first()
        assert perfil.gmail_conectado is False and perfil.gmail_refresh_token_enc is None
    finally:
        db.close()
    assert _pendientes(uid_ok) == 1
