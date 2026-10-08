"""Defensas generales: cabeceras, tamaños, NaN/Infinity, pagos, Gmail, PDFs y Sentry."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'seguridad.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import seguridad  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Perfil  # noqa: E402
from app.routers import correos as correos_mod  # noqa: E402
from app.routers.pagos import _url_de_retorno_valida  # noqa: E402

client = TestClient(app)
U = UsuarioActual(id="seg-usuario", email="seg@test.com", nombre="Seg")


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: U
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ── Cabeceras ──────────────────────────────────────────────────────────────────────

def test_toda_respuesta_lleva_cabeceras_de_seguridad():
    for r in (client.get("/health"), client.get("/cuentas"), client.get("/ruta-que-no-existe")):
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert "max-age" in r.headers["strict-transport-security"]
        assert r.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_cors_no_abre_a_cualquier_origen():
    r = client.get("/health", headers={"Origin": "https://sitio-malo.example"})
    assert "access-control-allow-origin" not in r.headers
    ok = client.get("/health", headers={"Origin": settings.pwa_url})
    assert ok.headers["access-control-allow-origin"] == settings.pwa_url
    # el parecido por prefijo tampoco pasa
    r = client.get("/health", headers={"Origin": settings.pwa_url + ".malo.com"})
    assert "access-control-allow-origin" not in r.headers


# ── Tamaño y números ──────────────────────────────────────────────────────────────

def test_cuerpo_grande_en_ruta_normal_da_413():
    r = client.post("/cuentas", content=b'{"nombre":"' + b"a" * (seguridad.LIMITE_NORMAL + 10) + b'"}',
                    headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_ruta_de_archivos_admite_mas_pero_tiene_tope():
    assert seguridad.limite_de("/conciliacion/procesar") > seguridad.limite_de("/cuentas")
    grande = b'{"pdf_base64":"' + b"A" * (seguridad.LIMITE_GRANDE + 10) + b'"}'
    r = client.post("/conciliacion/procesar", content=grande, headers={"content-type": "application/json"})
    assert r.status_code == 413


@pytest.mark.parametrize("cuerpo", [
    b'{"nombre":"x","saldo":NaN}', b'{"nombre":"x","saldo":Infinity}', b'{"nombre":"x","saldo":-Infinity}',
])
def test_json_con_nan_o_infinity_se_rechaza(cuerpo):
    r = client.post("/cuentas", content=cuerpo, headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_texto_normal_con_la_palabra_nan_no_se_confunde():
    r = client.post("/cuentas", json={"nombre": "Nancy NaN Infinity", "saldo": 5})
    assert r.status_code == 200
    assert seguridad.json_es_finito(b'{"a": 1}') and seguridad.json_es_finito(b"{roto NaN")


def test_cuerpo_normal_llega_intacto_al_endpoint():
    r = client.post("/cuentas", json={"nombre": "Normal", "saldo": 123.5})
    assert r.status_code == 200 and r.json()["saldo"] == 123.5


# ── Pagos ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,valida", [
    ("https://cuadrame.dapx.shop/#/perfil", True),
    ("https://cuadrame.dapx.shop", True),
    ("http://localhost:5173/#/perfil", True),
    ("https://cuadrame.dapx.shop.malo.com/", False),
    ("https://malo.com/https://cuadrame.dapx.shop", False),
    ("https://cuadrame.dapx.shop@malo.com/", False),
    ("https://usuario:clave@cuadrame.dapx.shop/", False),
    ("http://cuadrame.dapx.shop/", False),
    ("http://localhost.malo.com/", False),
    ("javascript:alert(1)", False),
    ("", False),
])
def test_url_de_retorno_de_stripe(url, valida):
    assert _url_de_retorno_valida(url) is valida


def test_checkout_rechaza_url_parecida():
    r = client.post("/pagos/checkout", params={"success_url": "https://cuadrame.dapx.shop.malo.com/",
                                               "cancel_url": "http://localhost:5173/"})
    assert r.status_code == 400


def test_webhook_sin_secreto_configurado_no_acepta_firmas_forjadas(monkeypatch):
    import hashlib
    import hmac
    import time

    monkeypatch.setattr(settings, "stripe_webhook_secret", "")
    cuerpo = b'{"id":"evt_1","object":"event","type":"checkout.session.completed","data":{"object":{"client_reference_id":"seg-usuario"}}}'
    t = str(int(time.time()))
    firma = hmac.new(b"", f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()  # firma con clave vacía
    r = client.post("/pagos/webhook", content=cuerpo, headers={"stripe-signature": f"t={t},v1={firma}"})
    assert r.status_code == 503
    db = SessionLocal()
    try:
        p = db.query(Perfil).filter(Perfil.usuario_id == "seg-usuario").first()
        assert p is None or p.plan != "pro"
    finally:
        db.close()


def test_webhook_con_firma_invalida_da_400(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_prueba")
    r = client.post("/pagos/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=00"})
    assert r.status_code == 400


# ── Gmail ─────────────────────────────────────────────────────────────────────────

def test_desconectar_gmail_revoca_el_token_en_google(monkeypatch):
    from app.gmail_oauth import cifrar

    from cryptography.fernet import Fernet

    if not settings.fernet_key:
        monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=U.id, plan="free", gmail_conectado=True, gmail_refresh_token_enc=cifrar("rt-seg"),
                      gmail_email="x@gmail.com"))
        db.commit()
    finally:
        db.close()
    vistos = []
    monkeypatch.setattr(correos_mod, "revocar_token", lambda enc: vistos.append(enc) or True)
    assert client.post("/correos/gmail/desconectar").status_code == 200
    assert len(vistos) == 1
    db = SessionLocal()
    try:
        p = db.query(Perfil).filter(Perfil.usuario_id == U.id).first()
        assert p.gmail_refresh_token_enc is None and p.gmail_conectado is False
    finally:
        db.close()


def test_callback_de_gmail_con_codigo_rechazado_vuelve_a_la_app_sin_500(monkeypatch):
    from app.gmail_oauth import crear_state
    from cryptography.fernet import Fernet

    if not settings.fernet_key:
        monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())

    def _falla(code):
        raise RuntimeError("invalid_grant")

    monkeypatch.setattr(correos_mod, "intercambiar_code", _falla)
    r = client.get("/correos/oauth/callback", params={"code": "x", "state": crear_state(U.id)}, follow_redirects=False)
    assert r.status_code in (302, 307) and "gmail=error" in r.headers["location"]


def test_callback_de_gmail_rechaza_state_falso():
    r = client.get("/correos/oauth/callback", params={"code": "x", "state": "inventado"})
    assert r.status_code == 400


def test_etiqueta_de_gmail_tiene_tope_de_largo():
    assert client.post("/correos/gmail/etiqueta", params={"etiqueta": "a" * 81}).status_code == 422


# ── PDFs ──────────────────────────────────────────────────────────────────────────

def test_pdf_con_base64_roto_o_que_no_es_pdf_no_da_500():
    for malo in ("###", "AAAA", "JVBERi0"):  # el último: "%PDF-" truncado, base64 inválido
        r = client.post("/cuentas", json={"nombre": "Para PDF", "saldo": 0})
        cuenta = r.json()["id"]
        r = client.post("/conciliacion/procesar", json={"pdf_base64": malo, "cuenta_id": cuenta})
        assert r.status_code < 500, malo


def test_solo_se_leen_las_primeras_paginas(monkeypatch):
    from app import pdf_extract

    class Pagina:
        def __init__(self, i):
            self.i = i

        def extract_text(self):
            return f"p{self.i}"

    class FalsoPdf:
        pages = [Pagina(i) for i in range(500)]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(pdf_extract.pdfplumber, "open", lambda *a, **k: FalsoPdf())
    import base64

    texto = pdf_extract.pdf_a_texto(base64.b64encode(b"%PDF-1.4 falso").decode())
    assert len(texto.split("\n")) == pdf_extract.MAX_PAGINAS_EXTRACTO


# ── Sentry ────────────────────────────────────────────────────────────────────────

def test_sentry_no_recibe_cuerpos_ni_claves():
    evento = {"request": {"data": {"pdf": "x"}, "cookies": {"a": "b"}, "query_string": "code=secreto",
                          "headers": {"Authorization": "Bearer abc", "X-Api-Key": "cdm_1", "X-Cron-Secret": "s",
                                      "User-Agent": "ok"}}}
    limpio = seguridad.limpiar_evento_sentry(evento, None)
    r = limpio["request"]
    assert "data" not in r and "cookies" not in r and "query_string" not in r
    assert r["headers"]["Authorization"] == "[filtrado]" and r["headers"]["X-Api-Key"] == "[filtrado]"
    assert r["headers"]["X-Cron-Secret"] == "[filtrado]" and r["headers"]["User-Agent"] == "ok"


# ── Sesión (JWT) y tope general por usuario ──────────────────────────────────────────

def _token(clave_privada, **extra):
    import time

    import jwt

    carga = {"sub": "jwt-usuario", "email": "jwt@test.com", "aud": "authenticated", "exp": int(time.time()) + 600, **extra}
    carga = {k: v for k, v in carga.items() if v is not None}
    return jwt.encode(carga, clave_privada, algorithm="RS256")


@pytest.fixture()
def con_jwt_real(monkeypatch):
    """Usa la verificación REAL de get_current_user con un par de claves de prueba (sin red)."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    from app import auth
    from app.limites import _eventos

    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class _Clave:
        key = privada.public_key()

    class _Jwks:
        def get_signing_key_from_jwt(self, token):
            return _Clave()

    monkeypatch.setattr(auth, "_jwks_client", _Jwks())
    app.dependency_overrides.pop(get_current_user, None)
    for k in ("api:jwt-usuario", "api:jwt-otro"):
        _eventos.pop(k, None)
    yield privada
    for k in ("api:jwt-usuario", "api:jwt-otro"):
        _eventos.pop(k, None)


def test_token_valido_entra_y_token_sin_vencimiento_no(con_jwt_real):
    ok = client.get("/cuentas", headers={"Authorization": f"Bearer {_token(con_jwt_real)}"})
    assert ok.status_code == 200
    sin_exp = client.get("/cuentas", headers={"Authorization": f"Bearer {_token(con_jwt_real, exp=None)}"})
    assert sin_exp.status_code == 401
    vencido = client.get("/cuentas", headers={"Authorization": f"Bearer {_token(con_jwt_real, exp=1)}"})
    assert vencido.status_code == 401
    otra_audiencia = client.get("/cuentas", headers={"Authorization": f"Bearer {_token(con_jwt_real, aud='otra')}"})
    assert otra_audiencia.status_code == 401
    assert client.get("/cuentas", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_tope_general_por_usuario_da_429_con_retry_after(con_jwt_real):
    from app.auth import LIMITE_GENERAL_POR_MINUTO

    h = {"Authorization": f"Bearer {_token(con_jwt_real)}"}
    for _ in range(LIMITE_GENERAL_POR_MINUTO):
        assert client.get("/metas", headers=h).status_code == 200
    r = client.get("/metas", headers=h)
    assert r.status_code == 429 and "Retry-After" in r.headers
    # otro usuario no se ve afectado
    h2 = {"Authorization": f"Bearer {_token(con_jwt_real, sub='jwt-otro')}"}
    assert client.get("/metas", headers=h2).status_code == 200
