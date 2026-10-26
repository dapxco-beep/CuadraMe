"""
Uso Limitado de Google + minimización: lo que viene de Gmail NO sale hacia ninguna IA de terceros,
y el respaldo por correo va cifrado y sin contenido de correos ni credenciales.

Ninguna prueba hace llamadas de red: httpx.post se sustituye por un espía.
"""
import gzip
import io
import json
import os
import tempfile
import uuid
from datetime import timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'privacidad.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import backup as bk  # noqa: E402
from app import ia as ia_nueva  # noqa: E402
from app import insights  # noqa: E402
from app import asistente as ia_mod  # noqa: E402
from app import factura as factura_mod  # noqa: E402
from app import pdf_extract as pe  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ClavePdf, Consentimiento, CorreoGasto, Movimiento, Perfil  # noqa: E402
from app.routers import backup as backup_router  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)

TEXTO_EXTRACTO = (
    "Banco Cooperativo Ejemplo - Extracto\n"
    "Titular: Maria Fernanda Lopez Ruiz  CC 52.123.456 \n"
    "Correo: maria.lopez@ejemplo.com Celular 3101234567\n"
    "Cuenta de ahorros 1234567890123\n"
    "Clave del PDF: 52123456\n"
    "12 mar 2026 COMPRA EXITO CHAPINERO 150.000,00\n"
    "13 mar 2026 PAGO NOMINA 3.200.000,00\n"
    "14 mar 2026 RETIRO CAJERO 200.000,00\n"
)
# Formato que el regex no entiende (montos en palabras): obliga a considerar la IA.
TEXTO_NO_RECONOCIDO = (
    "Banco Cooperativo Ejemplo - Extracto de cuenta\n"
    "Saldo anterior y saldo final del periodo\n"
    "Fecha Valor Descripcion\n"
    "doce de marzo compra en exito por ciento cincuenta mil pesos\n"
    "Titular: Maria Fernanda Lopez Ruiz\n"
)
RESPUESTA_OK = {"choices": [{"message": {"content": json.dumps({"movimientos": [
    {"fecha": "2026-03-12", "descripcion": "COMPRA EXITO", "monto": 150000, "tipo": "expense", "referencia": ""}]})}}]}


class Respuesta:
    status_code = 200

    def __init__(self, cuerpo):
        self._c = cuerpo

    def json(self):
        return self._c

    def raise_for_status(self):
        return None


class EspiaHttp:
    """Sustituye httpx.post: registra cada llamada (URL y JSON) y responde con RESPUESTA_OK."""

    def __init__(self):
        self.llamadas: list[dict] = []

    def __call__(self, url, **kw):
        self.llamadas.append({"url": url, **kw})
        return Respuesta(RESPUESTA_OK)

    @property
    def texto_enviado(self) -> str:
        return json.dumps([l.get("json") for l in self.llamadas], ensure_ascii=False)


@pytest.fixture()
def espia(monkeypatch):
    e = EspiaHttp()
    for mod in (pe, ia_nueva, factura_mod):
        monkeypatch.setattr(mod.httpx, "post", e)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-prueba")
    monkeypatch.setattr(settings, "openrouter_model_privado", "")
    return e


# ───────────────────── 1) IA externa sobre datos de Gmail ─────────────────────

def test_gmail_nunca_llama_a_openrouter_por_defecto(espia):
    # Incluso con consentimiento «ia» vigente: sin modelo privado configurado, no hay llamada.
    r = pe.extraer_via_ia(TEXTO_EXTRACTO, "Ahorros", "generico", origen=pe.ORIGEN_GMAIL, consentimiento_ia=True)
    assert r == [] and espia.llamadas == []
    # Sin consentimiento tampoco, y un origen desconocido se trata como Gmail.
    assert pe.extraer_via_ia(TEXTO_EXTRACTO, "A", "generico", origen=pe.ORIGEN_GMAIL, consentimiento_ia=False) == []
    assert pe.extraer_via_ia(TEXTO_EXTRACTO, "A", "generico", origen="otro", consentimiento_ia=True) == []
    assert espia.llamadas == []


def test_gmail_solo_con_consentimiento_y_modelo_privado(espia, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_model_privado", "proveedor/modelo-de-pago")
    # Con modelo privado pero SIN consentimiento: nada.
    assert pe.extraer_via_ia(TEXTO_EXTRACTO, "A", "generico", origen=pe.ORIGEN_GMAIL, consentimiento_ia=False) == []
    assert espia.llamadas == []
    r = pe.extraer_via_ia(TEXTO_EXTRACTO, "A", "generico", origen=pe.ORIGEN_GMAIL, consentimiento_ia=True,
                          nombre_titular="Maria Fernanda Lopez Ruiz")
    assert len(r) >= 1 and espia.llamadas
    cuerpo = espia.llamadas[0]["json"]
    assert cuerpo["model"] == "proveedor/modelo-de-pago"
    assert cuerpo["provider"] == {"data_collection": "deny"}  # el proveedor no guarda ni entrena


def test_manual_sin_consentimiento_no_llama(espia):
    assert pe.extraer_via_ia(TEXTO_EXTRACTO, "A", "generico", origen=pe.ORIGEN_MANUAL, consentimiento_ia=False) == []
    assert espia.llamadas == []


def test_manual_con_consentimiento_usa_texto_enmascarado(espia):
    r = pe.extraer_via_ia(TEXTO_EXTRACTO, "Ahorros", "generico", origen=pe.ORIGEN_MANUAL,
                          consentimiento_ia=True, nombre_titular="Maria Fernanda Lopez Ruiz")
    assert r and espia.llamadas
    assert espia.llamadas[0]["json"]["model"] == pe.OPENROUTER_MODEL
    enviado = espia.texto_enviado
    for secreto in ("52.123.456", "52123456", "maria.lopez@ejemplo.com", "3101234567",
                    "1234567890123", "Maria", "Lopez", "Clave del PDF"):
        assert secreto not in enviado, secreto
    # Lo útil sí viaja: fechas, descripciones y montos.
    assert "COMPRA EXITO" in enviado and "150.000,00" in enviado and "12 mar 2026" in enviado


def test_enmascarar_conserva_montos_y_fechas():
    t = pe.enmascarar_texto("2026-03-12 COMPRA 1.234.567,89 ref 123456 saldo 150000\nPIN: 1234\ntarjeta 4111 1111 1111 1111")
    assert "1.234.567,89" in t and "2026-03-12" in t and "150000" in t and "123456" in t
    assert "PIN" not in t and "4111" not in t


def _ambiente_gmail(monkeypatch):
    """Usuario con Gmail y un extracto de un banco que el regex no reconoce, llegado por Gmail."""
    from tests.test_extractos_gmail import GmailFalso, _gmail_de_prueba, conectar_usuario  # noqa: F401
    from app.routers import correos as router_correos
    from cryptography.fernet import Fernet

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    uid = f"priv-{uuid.uuid4().hex[:8]}"
    gmail = _gmail_de_prueba()
    conectar_usuario(uid, gmail, monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Cooperativa", "saldo": 0}).json()
    client.post("/correos/sincronizar")
    ext = next(e for e in client.get("/correos/extractos").json() if e["archivo"] == "estado_de_cuenta.pdf")
    return uid, cuenta, ext, router_correos


def test_flujo_gmail_completo_no_llama_a_openrouter(espia, monkeypatch):
    pytest.importorskip("reportlab")
    uid, cuenta, ext, _ = _ambiente_gmail(monkeypatch)
    from app.routers import conciliacion as conc

    monkeypatch.setattr(conc, "pdf_a_texto", lambda *a, **k: TEXTO_NO_RECONOCIDO)
    monkeypatch.setattr(settings, "exigir_consentimientos", True)
    db = SessionLocal()
    try:
        for fin in ("tratamiento_basico", "lectura_correo", "ia"):  # incluso con «ia» aceptada
            db.add(Consentimiento(usuario_id=uid, version="1.1", finalidad=fin, aceptado=True,
                                  creado_en_utc=ahora_co(), creado_en_co=ahora_co()))
        db.commit()
    finally:
        db.close()

    visto = {}
    original = conc.extraer_via_ia

    def con_registro(*a, **k):
        visto["origen"] = k.get("origen")
        return original(*a, **k)

    monkeypatch.setattr(conc, "extraer_via_ia", con_registro)
    r = client.post(f"/correos/extractos/{ext['id']}/conciliar", json={"cuenta_id": cuenta["id"]}).json()
    assert visto.get("origen") == pe.ORIGEN_GMAIL  # el flujo llegó a la extracción y declaró su origen
    assert espia.llamadas == []                    # y no salió ni una llamada HTTP
    assert r["ok"] is False                        # queda para revisión manual, sin inventar filas


def test_subida_manual_con_consentimiento_si_usa_ia_y_sin_el_no(espia, monkeypatch):
    uid = f"priv-{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.co", nombre="Maria Fernanda Lopez Ruiz")
    from app.routers import conciliacion as conc

    cuenta = client.post("/cuentas", json={"nombre": "Cooperativa", "saldo": 0}).json()
    monkeypatch.setattr(conc, "pdf_a_texto", lambda *a, **k: TEXTO_NO_RECONOCIDO)
    monkeypatch.setattr(settings, "exigir_consentimientos", True)

    client.post("/conciliacion/procesar", json={"cuenta_id": cuenta["id"], "pdf_base64": "x"})
    assert espia.llamadas == []                    # sin consentimiento «ia»: nada sale

    db = SessionLocal()
    try:
        db.add(Consentimiento(usuario_id=uid, version="1.1", finalidad="ia", aceptado=True,
                              creado_en_utc=ahora_co(), creado_en_co=ahora_co()))
        db.commit()
    finally:
        db.close()
    client.post("/conciliacion/procesar", json={"cuenta_id": cuenta["id"], "pdf_base64": "x"})
    assert len(espia.llamadas) >= 1
    assert "Maria" not in espia.texto_enviado and "Lopez" not in espia.texto_enviado


def test_asistente_no_recibe_cuerpos_ni_descripciones_de_gmail(espia, monkeypatch):
    uid = f"priv-{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.co", nombre="Pers")
    monkeypatch.setattr(settings, "exigir_consentimientos", False)
    cuenta = client.post("/cuentas", json={"nombre": "Ahorros", "saldo": 100000}).json()
    asunto, snippet, comercio = "ASUNTO-SECRETO-GMAIL", "SNIPPET-SECRETO-GMAIL", "COMERCIO-DE-CORREO"
    db = SessionLocal()
    try:
        db.add(CorreoGasto(usuario_id=uid, gmail_msg_id="m-1", remitente="banco@x.co", asunto=asunto,
                           snippet=snippet, monto=45000, comercio=comercio))
        db.add(Movimiento(usuario_id=uid, cuenta_id=cuenta["id"], descripcion=comercio, categoria="Otros",
                          tipo="expense", monto=45000, fecha=ahora_co() - timedelta(hours=1), fuente="email"))
        db.add(Movimiento(usuario_id=uid, cuenta_id=cuenta["id"], descripcion="TIENDA-MANUAL", categoria="Otros",
                          tipo="expense", monto=1000, fecha=ahora_co() - timedelta(hours=1), fuente="manual"))
        db.commit()
    finally:
        db.close()

    client.post("/asistente/mensaje", json={"texto": "cuéntame algo curioso sobre mis finanzas de forma general"})
    client.post("/insights/preguntar", json={"pregunta": "cuéntame algo curioso sobre mis finanzas de forma general"})
    enviado = espia.texto_enviado
    assert espia.llamadas, "la prueba debe ejercitar la IA"
    for prohibido in (asunto, snippet, comercio, "banco@x.co"):
        assert prohibido not in enviado, prohibido
    assert "TIENDA-MANUAL" in enviado  # lo que el usuario registró él mismo sigue disponible


def test_resumen_semanal_sin_consentimiento_no_llama_a_la_ia(espia, monkeypatch):
    uid = f"priv-{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.co", nombre="Pers")
    monkeypatch.setattr(settings, "exigir_consentimientos", True)
    r = client.get("/insights/resumen-semanal")
    assert r.status_code == 200 and espia.llamadas == []


# ───────────────────── 2) Respaldo cifrado y sin sensibles ─────────────────────

def test_cifrado_ida_y_vuelta_y_frase_incorrecta():
    datos = gzip.compress(b'{"tablas": {"cuentas": [{"saldo": 123.45}]}}')
    blob = bk.cifrar_respaldo(datos, "una frase larga y unica")
    assert blob.startswith(bk.MAGIC) and b"saldo" not in blob and datos not in blob
    assert bk.descifrar_respaldo(blob, "una frase larga y unica") == datos
    assert bk.cifrar_respaldo(datos, "una frase larga y unica") != blob  # sal y nonce aleatorios
    with pytest.raises(ValueError):
        bk.descifrar_respaldo(blob, "otra frase")
    with pytest.raises(ValueError):
        bk.descifrar_respaldo(blob[:-1] + bytes([blob[-1] ^ 1]), "una frase larga y unica")  # alterado
    with pytest.raises(ValueError):
        bk.cifrar_respaldo(datos, "")


def test_script_de_restauracion_descifra_lo_que_envia_el_servidor():
    import importlib.util
    ruta = os.path.join(os.path.dirname(__file__), "..", "tools", "descifrar_respaldo.py")
    spec = importlib.util.spec_from_file_location("descifrar_respaldo", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    original = b'{"tablas": {"cuentas": []}}'
    blob = bk.cifrar_respaldo(gzip.compress(original), "frase de prueba")
    assert mod.descifrar(blob, "frase de prueba") == original
    with pytest.raises(ValueError):
        mod.descifrar(blob, "mala")


def _sembrar_sensibles(uid):
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", gmail_conectado=True, gmail_refresh_token_enc="TOKEN-SECRETO-GMAIL",
                      gmail_email="gmail-personal@gmail.com", api_key=f"cdm_CLAVE-ATAJO-SECRETA-{uid}"))
        db.add(CorreoGasto(usuario_id=uid, gmail_msg_id=f"g-{uid}", remitente="REMITENTE-SECRETO@banco.co",
                           asunto="ASUNTO-SECRETO", snippet="SNIPPET-SECRETO", monto=10))
        db.add(ClavePdf(usuario_id=uid, clave_enc="CLAVE-PDF-SECRETA"))
        db.commit()
    finally:
        db.close()


def test_exportacion_no_contiene_correos_tokens_claves_ni_push():
    uid = f"bk-{uuid.uuid4().hex[:8]}"
    _sembrar_sensibles(uid)
    from app.models import PushSubscription
    db = SessionLocal()
    try:
        db.add(PushSubscription(usuario_id=uid, endpoint="https://push.ejemplo/ENDPOINT-SECRETO", p256dh="P256-SECRETO", auth="AUTH-SECRETO"))
        db.commit()
    finally:
        db.close()

    contenido = gzip.decompress(bk.exportar_base_de_datos()).decode("utf-8")
    for secreto in ("TOKEN-SECRETO-GMAIL", "gmail-personal@gmail.com", "CLAVE-ATAJO-SECRETA", "REMITENTE-SECRETO",
                    "ASUNTO-SECRETO", "SNIPPET-SECRETO", "CLAVE-PDF-SECRETA", "ENDPOINT-SECRETO", "P256-SECRETO", "AUTH-SECRETO"):
        assert secreto not in contenido, secreto
    tablas = json.loads(contenido)["tablas"]
    assert not (bk.TABLAS_NO_RESPALDADAS & set(tablas))
    assert uid in {f["usuario_id"] for f in tablas["perfiles"]}  # el resto del perfil sí se respalda
    for filas in tablas.values():
        for fila in filas:
            for col in fila:
                assert bk.columna_respaldable(col), col


def test_ninguna_tabla_nueva_con_texto_de_correo_se_cuela():
    """Red de seguridad: toda columna del esquema con nombre de texto/credencial de correo queda fuera."""
    sospechosas = ("asunto", "snippet", "remitente", "token", "api_key", "secret", "password", "clave_enc", "p256dh")
    for nombre_tabla, tabla in Base.metadata.tables.items():
        if nombre_tabla in bk.TABLAS_NO_RESPALDADAS:
            continue
        for col in tabla.columns:
            if any(s in col.name.lower() for s in sospechosas):
                assert not bk.columna_respaldable(col.name), f"{nombre_tabla}.{col.name} se respaldaría"


def test_cron_sin_frase_no_envia_y_avisa(monkeypatch, caplog):
    llamadas = []
    monkeypatch.setattr(settings, "resend_api_key", "re_prueba")
    monkeypatch.setattr(settings, "backup_passphrase", "")
    monkeypatch.setattr(bk.httpx, "post", lambda *a, **k: llamadas.append(1))
    eventos = []
    from app import avisos
    monkeypatch.setattr(avisos, "registrar_evento", lambda tipo, *a, **k: eventos.append(tipo))
    monkeypatch.setattr(backup_router, "ahora_co", lambda: ahora_co() + timedelta(days=4000))
    caplog.set_level("WARNING")
    r = client.post("/backup/cron/enviar", headers={"X-Cron-Secret": "secreto-de-prueba"})
    assert r.status_code == 503 and "BACKUP_PASSPHRASE" in r.json()["detail"]
    assert llamadas == []
    assert "respaldo_sin_cifrar" in eventos
    assert "BACKUP_PASSPHRASE" in caplog.text


def test_cron_con_frase_envia_adjunto_cifrado(monkeypatch):
    enviados = []
    monkeypatch.setattr(settings, "resend_api_key", "re_prueba")
    monkeypatch.setattr(settings, "backup_passphrase", "frase-de-prueba-larga")
    monkeypatch.setattr(bk.httpx, "post", lambda url, **k: enviados.append(k["json"]) or Respuesta({}))
    monkeypatch.setattr(backup_router, "ahora_co", lambda: ahora_co() + timedelta(days=5000))
    uid = f"bk-{uuid.uuid4().hex[:8]}"
    _sembrar_sensibles(uid)
    r = client.post("/backup/cron/enviar", headers={"X-Cron-Secret": "secreto-de-prueba"})
    assert r.status_code == 200 and r.json()["enviado"] is True and r.json()["cifrado"] is True
    adj = enviados[0]["attachments"][0]
    assert adj["filename"].endswith(".cmbk")
    import base64
    blob = base64.b64decode(adj["content"])
    assert blob.startswith(bk.MAGIC) and b"perfiles" not in blob
    crudo = gzip.decompress(bk.descifrar_respaldo(blob, "frase-de-prueba-larga")).decode()
    assert "TOKEN-SECRETO-GMAIL" not in crudo and "ASUNTO-SECRETO" not in crudo
