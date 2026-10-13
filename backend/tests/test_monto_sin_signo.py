"""Montos en correos de bancos: Nequi/Bre-B escribe «Recibiste 30.000 de ...» SIN «$». Antes: 30.000 se leía
como 0 (el correo se perdía), 45.500 como 500 y 1.250.000 como 250.000 (entraban con un monto falso).
También: un año («de 2026») no es un monto, el cuerpo del correo se lee solo cuando el fragmento no basta,
y los correos de bancos descartados por esa falla se recuperan una sola vez. Datos sintéticos."""
import base64
import os
import tempfile
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'monto.db')}")

import pytest  # noqa: E402

from app import reevaluar_ignorados  # noqa: E402
from app.crons import MarcaCron  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402,F401  (al importarla se crean las tablas de prueba)
from app.gmail_extract import detectar_tipo, extraer_comercio, extraer_monto, texto_cuerpo  # noqa: E402
from app.models import CorreoGasto, SyncGmail  # noqa: E402


# ── Lectura del monto ────────────────────────────────────────────────
@pytest.mark.parametrize("texto,esperado", [
    ("¡Recibiste plata por Bre-B! Recibiste 30.000 de LUIS PEREZ el 8 de octubre de 2026 a las 4:30 pm", 30000),
    ("Enviaste de manera exitosa 45.500 a la llave 3001234567 de MARIA GOMEZ el 3 de julio de 2026", 45500),
    ("Recibiste 1.250.000 de LUIS PEREZ el 8 de octubre de 2026", 1250000),
    ("Enviaste de manera exitosa 8.000 a la llave @luis de LUIS el 1 de enero de 2026", 8000),
    ("Recibiste $ 72.300 de ANA", 72300),
    ("Compra por $45.000 en JUAN VALDEZ", 45000),
    ("Compra por 1.250.000,50 COP en Tienda", 1250000.5),
    ("Compra de 250 USD en Amazon", 250),
    ("Retiro en cajero por 300.000", 300000),
])
def test_monto_se_lee_completo(texto, esperado):
    assert extraer_monto(texto) == esperado


@pytest.mark.parametrize("texto", [
    "Recibimos el pago que hiciste de tu Tarjeta de crédito Nu el 10 de octubre de 2026",
    "Tu cita es el 15.10.2026 a las 9.30",
    "Promoción válida hasta 2026",
])
def test_un_ano_o_una_hora_no_es_un_monto(texto):
    assert extraer_monto(texto) == 0


def test_tipo_y_concepto_de_bre_b():
    recibido = "¡Recibiste plata por Bre-B! Recibiste 30.000 de LUIS PEREZ el 8 de octubre"
    enviado = "¡Enviaste plata por Bre-B! Enviaste de manera exitosa 45.500 a la llave 3001234567 de MARIA GOMEZ el 3 de julio"
    assert detectar_tipo(recibido) == "income" and detectar_tipo(enviado) == "expense"
    assert extraer_comercio("notificaciones@nequi.com.co", "¡Recibiste plata por Bre-B!", recibido).startswith("Recibido de")
    assert "Maria Gomez" in extraer_comercio("notificaciones@nequi.com.co", "¡Enviaste plata por Bre-B!", enviado)


# ── Cuerpo del correo (solo para leer el monto; no se guarda) ─────────────
def _b64(texto: str) -> str:
    return base64.urlsafe_b64encode(texto.encode()).decode().rstrip("=")


def test_texto_cuerpo_prefiere_texto_plano_y_limpia_html():
    msg = {"payload": {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/html", "body": {"data": _b64("<html><style>x{}</style><p>Valor: <b>$ 90.000</b></p></html>")}},
        {"mimeType": "text/plain", "body": {"data": _b64("Recibimos tu pago por 90.000   pesos")}},
    ]}}
    assert texto_cuerpo(msg) == "Recibimos tu pago por 90.000 pesos"
    solo_html = {"payload": {"mimeType": "text/html", "body": {"data": _b64("<p>Valor <b>$ 90.000</b></p><script>alert(1)</script>")}}}
    assert texto_cuerpo(solo_html) == "Valor $ 90.000"
    assert texto_cuerpo({"payload": {}}) == ""
    assert len(texto_cuerpo({"payload": {"mimeType": "text/plain", "body": {"data": _b64("a" * 20000)}}})) == 6000


# ── Recuperar los correos de bancos que se descartaron sin monto ──────────
UID = "reeval-u1"


def _correo(uid, remitente, asunto, snippet, estado="ignorado", monto=0):
    return CorreoGasto(
        id=str(uuid.uuid4()), usuario_id=uid, gmail_msg_id=str(uuid.uuid4()), remitente=remitente, asunto=asunto,
        snippet=snippet, monto=monto, estado=estado, recibido_en=datetime.utcnow(),
    )


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        for m in (CorreoGasto, MarcaCron, SyncGmail):
            s.query(m).delete()
        s.commit()
        yield s
    finally:
        s.close()


def test_recupera_solo_notificaciones_de_bancos_sin_monto(db):
    db.add_all([
        _correo(UID, "Nequi <notificaciones@nequi.com.co>", "¡Recibiste plata por Bre-B!", "Recibiste 30.000 de LUIS"),
        _correo(UID, "Nu <nu@nu.com.co>", "¡Ya entró tu pago!", "Recibimos el pago que hiciste de tu Tarjeta de crédito Nu"),
        _correo(UID, "Nu <nu@nu.com.co>", "JULIANA, novedades Nu en septiembre", "Mira lo nuevo de Nu este mes"),  # publicidad
        _correo(UID, "Tienda <notificaciones@homecentermail.com.co>", "Tu Pedido Fue Entregado", "Compra entregada"),  # no es banco
        _correo(UID, "Nequi <hola@nequi.com.co>", "Información sobre tus datos personales", "pago 5.000", monto=5000),  # ya tenía monto
        _correo(UID, "Nequi <notificaciones@nequi.com.co>", "¡Recibiste plata por Bre-B!", "Recibiste 9.000 de ANA",
                estado="aprobado", monto=9000),  # ya procesado: no se toca
    ])
    db.add(SyncGmail(usuario_id=UID, en_curso=False, ultima_sync=datetime.utcnow()))
    db.commit()

    assert reevaluar_ignorados.preparar(db, UID) == 2
    restantes = {c.asunto for c in db.query(CorreoGasto).filter(CorreoGasto.usuario_id == UID).all()}
    assert "¡Ya entró tu pago!" not in restantes
    assert "JULIANA, novedades Nu en septiembre" in restantes and "Tu Pedido Fue Entregado" in restantes
    assert db.query(CorreoGasto).filter(CorreoGasto.usuario_id == UID, CorreoGasto.estado == "aprobado").count() == 1
    assert db.get(SyncGmail, UID).ultima_sync is None  # la próxima sincronización usa la ventana larga


def test_corre_una_sola_vez_y_solo_para_su_usuario(db):
    db.add_all([
        _correo(UID, "Nequi <notificaciones@nequi.com.co>", "¡Recibiste plata por Bre-B!", "Recibiste 30.000 de LUIS"),
        _correo("otro-usuario", "Nequi <notificaciones@nequi.com.co>", "¡Enviaste plata por Bre-B!", "Enviaste 8.000 a ANA"),
    ])
    db.commit()
    assert reevaluar_ignorados.preparar(db, UID) == 1
    # Un correo nuevo descartado después NO se vuelve a borrar: la marca ya está reclamada.
    db.add(_correo(UID, "Nequi <notificaciones@nequi.com.co>", "¡Recibiste plata por Bre-B!", "Recibiste 11.000 de PEPE"))
    db.commit()
    assert reevaluar_ignorados.preparar(db, UID) == 0
    assert db.query(CorreoGasto).filter(CorreoGasto.usuario_id == UID).count() == 1
    assert db.query(CorreoGasto).filter(CorreoGasto.usuario_id == "otro-usuario").count() == 1  # intacto


# ── Avisos que NO son transacciones (regresión: llegaron a «Por revisar» con montos absurdos) ──────────
@pytest.mark.parametrize("asunto", [
    "El extracto de tu Cuenta Nu ya está aquí",
    "Llegó el extracto de tu tarjeta de crédito Nu",
    "Agregaste tu tarjeta Nu a Apple Pay",
    "Faltan fondos para pagar en Didi",
    "Estamos creando tu tarjeta de crédito",
    "JULIANA, novedades Nu en septiembre",
])
def test_los_avisos_no_son_transacciones(asunto):
    from app.extractos_gmail import es_aviso_no_transaccion, es_notificacion_transaccion
    assert es_aviso_no_transaccion(asunto, "") is True
    assert es_notificacion_transaccion(asunto, "pago movimientos compra") is False


@pytest.mark.parametrize("asunto", [
    "¡Recibiste plata por Bre-B!", "¡Enviaste plata por Bre-B!", "¡Ya entró tu pago!",
    "Pagaste en TECNIPAGOS S A con Cuenta Nu", "Compra aprobada",
])
def test_las_transacciones_siguen_siendo_transacciones(asunto):
    from app.extractos_gmail import es_aviso_no_transaccion
    assert es_aviso_no_transaccion(asunto, "") is False


def test_el_cuerpo_se_lee_en_modo_estricto_y_no_toma_numeros_de_cuenta():
    cuerpo = "Hola. Tu extracto ya está disponible. NIT 901658107-1 cuenta 12345678901 línea 3001234567 año 2026."
    assert extraer_monto(cuerpo, estricto=True) == 0
    assert extraer_monto("Recibimos tu pago. Valor: $ 90.000 el 10 de octubre", estricto=True) == 90000
    assert extraer_monto("Recibiste 30.000 de ANA", estricto=True) == 30000


def test_vuelve_a_ignorado_lo_que_entro_como_aviso(db):
    db.add_all([
        _correo(UID, "Nu <nu@nu.com.co>", "El extracto de tu Cuenta Nu ya está aquí", "Revisa", estado="pendiente", monto=901658107),
        _correo(UID, "Nu <nu@nu.com.co>", "Faltan fondos para pagar en Didi", "No se pudo", estado="pendiente", monto=8900),
        _correo(UID, "Nequi <notificaciones@nequi.com.co>", "¡Recibiste plata por Bre-B!", "Recibiste 30.000 de LUIS", estado="pendiente", monto=30000),
    ])
    db.commit()
    reevaluar_ignorados.preparar(db, UID)
    estados = {c.asunto: c.estado for c in db.query(CorreoGasto).filter(CorreoGasto.usuario_id == UID).all()}
    assert estados["El extracto de tu Cuenta Nu ya está aquí"] == "ignorado"
    assert estados["Faltan fondos para pagar en Didi"] == "ignorado"
    assert estados["¡Recibiste plata por Bre-B!"] == "pendiente"  # una transacción real no se toca
