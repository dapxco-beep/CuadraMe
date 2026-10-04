"""
Detección de extractos y notificaciones en Gmail, con correos y PDFs
simulados: ninguna prueba llama a Google.
"""
import base64
import io
import logging
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'extractos.db')}")

import pytest  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import extractos_gmail as eg  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ClavePdf, Perfil  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402
from app.schemas import ProcesarExtractoResponse  # noqa: E402

reportlab_canvas = pytest.importorskip("reportlab.pdfgen.canvas")

client = TestClient(app)
CLAVE = "1020304050"


# ── Utilidades de prueba ────────────────────────────────────────────

def hacer_pdf(lineas: list[str], clave: str | None = None) -> bytes:
    buf = io.BytesIO()
    c = reportlab_canvas.Canvas(buf, encrypt=clave) if clave else reportlab_canvas.Canvas(buf)
    y = 800
    for linea in lineas:
        c.drawString(50, y, linea)
        y -= 18
    c.save()
    return buf.getvalue()


TEXTO_EXTRACTO = [
    "BANCOLOMBIA - Extracto de cuenta de ahorros",
    "Cuenta terminada en 4321",
    "Periodo: 01/09/2026 al 30/09/2026",
]


def adjunto(nombre: str, adj_id: str) -> dict:
    return {"filename": nombre, "mimeType": "application/pdf", "body": {"attachmentId": adj_id, "size": 2000}}


def mensaje(id_, remitente, asunto, snippet="", partes=None, labels=None) -> dict:
    return {
        "id": id_,
        "snippet": snippet,
        "internalDate": "1790000000000",
        "labelIds": labels or [],
        "payload": {
            "headers": [{"name": "From", "value": remitente}, {"name": "Subject", "value": asunto}],
            "parts": partes or [],
        },
    }


class _Llamada:
    def __init__(self, valor):
        self.valor = valor

    def execute(self):
        return self.valor


class GmailFalso:
    """Imita la parte de la API de Gmail que usa el backend."""

    def __init__(self, mensajes: list[dict], adjuntos: dict[str, bytes], etiquetas=None):
        self.mensajes = {m["id"]: m for m in mensajes}
        self.adjuntos = adjuntos
        self.etiquetas = etiquetas or []
        self.consultas: list[str] = []

    def users(self):
        return self

    def labels(self):
        return self

    def messages(self):
        return self

    def attachments(self):
        return self

    def list(self, userId, q=None, labelIds=None, maxResults=25, pageToken=None):  # noqa: N803
        if q is None and labelIds is None:
            return _Llamada({"labels": self.etiquetas})
        if labelIds:
            ids = [i for i, m in self.mensajes.items() if labelIds[0] in m["labelIds"]]
        else:
            self.consultas.append(q)
            if "-has:attachment" in q:
                ids = [i for i, m in self.mensajes.items() if not m["payload"]["parts"] and not m["labelIds"]]
            else:
                ids = [i for i, m in self.mensajes.items() if m["payload"]["parts"]]
        # Paginación como Gmail: pageToken = posición de la siguiente página.
        ini = int(pageToken or 0)
        pagina = ids[ini:ini + maxResults]
        resp = {"messages": [{"id": i} for i in pagina], "resultSizeEstimate": len(ids)}
        if ini + maxResults < len(ids):
            resp["nextPageToken"] = str(ini + maxResults)
        return _Llamada(resp)

    def get(self, userId, id=None, messageId=None, format=None):  # noqa: N803
        if messageId:  # attachments().get
            datos = base64.urlsafe_b64encode(self.adjuntos[id]).decode()
            return _Llamada({"data": datos})
        return _Llamada(self.mensajes[id])


@pytest.fixture(autouse=True)
def _entorno(monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    yield


def conectar_usuario(usuario_id: str, gmail: GmailFalso, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id=usuario_id, email=f"{usuario_id}@test.com", nombre="Persona Prueba"
    )
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=usuario_id, plan="free", gmail_conectado=True,
                      gmail_refresh_token_enc="token-falso", gmail_email="x@gmail.com"))
        db.commit()
    finally:
        db.close()
    monkeypatch.setattr(router_correos, "cliente_gmail", lambda _token: gmail)


# ── Funciones puras ─────────────────────────────────────────────────

def test_query_de_extractos_usa_palabras_y_dominios_sin_etiqueta():
    q = eg.construir_query_extractos()
    assert "has:attachment" in q and "filename:pdf" in q
    assert '"estado de cuenta"' in q and "extracto" in q
    assert "bancolombia.com.co" in q and "nequi.com.co" in q
    assert "label:" not in q


def test_banco_por_remitente_acepta_subdominios_y_rechaza_parecidos():
    assert eg.banco_por_remitente('"Nequi" <no-responder@alertas.nequi.com.co>') == "Nequi"
    assert eg.banco_por_remitente("extractos@davivienda.com") == "Davivienda"
    assert eg.banco_por_remitente("x@fake-bancolombia.com.co.evil.com") is None
    assert eg.banco_por_remitente("promo@tienda.com") is None


def test_listar_adjuntos_pdf_recorre_partes_anidadas():
    msg = mensaje("m", "a@b.co", "x", partes=[
        {"mimeType": "multipart/alternative", "parts": [adjunto("Extracto_sep.PDF", "A1")]},
        {"filename": "foto.png", "mimeType": "image/png", "body": {"attachmentId": "A2", "size": 5}},
    ])
    assert [a["archivo"] for a in eg.listar_adjuntos_pdf(msg)] == ["Extracto_sep.PDF"]


def test_abrir_pdf_sin_clave_con_clave_y_clave_incorrecta():
    claro = hacer_pdf(TEXTO_EXTRACTO)
    cifrado = hacer_pdf(TEXTO_EXTRACTO, CLAVE)

    estado, texto, _ = eg.abrir_pdf(claro, eg.claves_candidatas(None))
    assert estado == "ok" and "Extracto" in texto

    estado, texto, _ = eg.abrir_pdf(cifrado, eg.claves_candidatas(None))
    assert estado == "falta_clave" and texto == ""

    estado, _, _ = eg.abrir_pdf(cifrado, eg.claves_candidatas("0000"))
    assert estado == "falta_clave"

    estado, texto, usada = eg.abrir_pdf(cifrado, eg.claves_candidatas(f"0000, {CLAVE}"))
    assert estado == "ok" and usada == CLAVE and "4321" in texto

    assert eg.abrir_pdf(b"no soy un pdf", [""])[0] == "error"


def test_periodo_ultimos4_y_sugerencia_de_cuenta():
    texto = "\n".join(TEXTO_EXTRACTO)
    assert eg.detectar_periodo(texto) == "01/09/2026 a 30/09/2026"
    assert eg.detectar_periodo("", "Extracto septiembre 2026.pdf") == "septiembre 2026"
    assert eg.detectar_ultimos4(texto) == "4321"

    class C:
        def __init__(self, id, nombre):
            self.id, self.nombre = id, nombre

    cuentas = [C("a", "Efectivo"), C("b", "Bancolombia Ahorros"), C("c", "Nequi")]
    assert eg.sugerir_cuenta("Bancolombia", "", cuentas) == "b"
    assert eg.sugerir_cuenta("Davivienda", "", cuentas) is None
    ambiguas = [C("b", "Bancolombia Ahorros"), C("d", "Bancolombia Crédito")]
    assert eg.sugerir_cuenta("Bancolombia", "", ambiguas) is None
    assert eg.sugerir_cuenta("Bancolombia", "4321", [C("b", "Bancolombia *4321"), C("d", "Bancolombia Crédito")]) == "b"


# ── Flujo completo por la API ───────────────────────────────────────

def _gmail_de_prueba():
    mensajes = [
        # Notificación de transacción de un banco, sin etiqueta.
        mensaje("n1", "Bancolombia <alertas@alertas.bancolombia.com.co>", "Compra aprobada",
                "Compra por $45.000 en EXITO con tu tarjeta"),
        # Publicidad del mismo banco: se ignora, no llega a pendientes.
        mensaje("n2", "Bancolombia <promo@bancolombia.com.co>", "Gana premios", "Participa y gana"),
        # Extracto cifrado de un banco.
        mensaje("e1", "Bancolombia <extractos@bancolombia.com.co>", "Tu extracto de septiembre",
                partes=[adjunto("Extracto_092026.pdf", "ADJ1")]),
        # Extracto sin cifrar de un remitente no listado (se detecta por la palabra).
        mensaje("e2", "info@cooperativa.org", "Estado de cuenta octubre",
                partes=[adjunto("estado_de_cuenta.pdf", "ADJ2")]),
        # PDF que no es un extracto: se ignora.
        mensaje("e3", "Davivienda <no-reply@davivienda.com>", "Certificado laboral",
                partes=[adjunto("certificado.pdf", "ADJ3")]),
    ]
    adjuntos = {
        "ADJ1": hacer_pdf(TEXTO_EXTRACTO, CLAVE),
        "ADJ2": hacer_pdf(["Cooperativa - Estado de cuenta", "Periodo: 01/10/2026 al 31/10/2026"]),
        "ADJ3": hacer_pdf(["Certificado"]),
    }
    return GmailFalso(mensajes, adjuntos)


def test_sincronizar_detecta_sin_etiqueta_no_duplica_y_usa_la_clave(monkeypatch, caplog):
    gmail = _gmail_de_prueba()
    conectar_usuario("u-extractos", gmail, monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 1000}).json()

    caplog.set_level(logging.DEBUG)
    r = client.post("/correos/sincronizar").json()
    assert r["ok"] is True
    assert r["nuevos"] == 1            # solo la compra; la publicidad queda ignorada
    assert r["extractos_nuevos"] == 2  # e1 y e2; el certificado no

    # Notificación: queda pendiente de revisión y NO se creó ningún movimiento.
    pendientes = client.get("/correos/pendientes").json()
    assert [p["monto"] for p in pendientes] == [45000.0]
    assert client.get("/movimientos").json() in ([], {"items": [], "total": 0}) or not any(
        m.get("fuente") == "email" for m in _items(client.get("/movimientos").json())
    )

    extractos = {e["archivo"]: e for e in client.get("/correos/extractos").json()}
    assert set(extractos) == {"Extracto_092026.pdf", "estado_de_cuenta.pdf"}
    cifrado = extractos["Extracto_092026.pdf"]
    assert cifrado["estado"] == "falta_clave"
    assert cifrado["banco"] == "Bancolombia"
    assert cifrado["cuenta_sugerida_id"] == cuenta["id"]
    assert extractos["estado_de_cuenta.pdf"]["estado"] == "nuevo"
    assert extractos["estado_de_cuenta.pdf"]["periodo"] == "01/10/2026 a 31/10/2026"

    # Segunda sincronización: nada nuevo, nada duplicado.
    r2 = client.post("/correos/sincronizar").json()
    assert r2["nuevos"] == 0 and r2["extractos_nuevos"] == 0
    assert len(client.get("/correos/pendientes").json()) == 1
    assert len(client.get("/correos/extractos").json()) == 2

    # Guardar la clave: se cifra, no se devuelve y no aparece en logs.
    g = client.put("/correos/clave-pdf", json={"clave": CLAVE})
    assert g.json() == {"ok": True, "configurada": True}
    assert CLAVE not in g.text
    assert client.get("/correos/clave-pdf").json() == {"configurada": True}
    db = SessionLocal()
    try:
        fila = db.query(ClavePdf).filter(ClavePdf.usuario_id == "u-extractos").first()
        assert fila.clave_enc != CLAVE and router_correos.descifrar(fila.clave_enc) == CLAVE
    finally:
        db.close()

    # Con la clave, la siguiente sincronización destraba el extracto.
    client.post("/correos/sincronizar")
    cifrado = next(e for e in client.get("/correos/extractos").json() if e["archivo"] == "Extracto_092026.pdf")
    assert cifrado["estado"] == "nuevo"
    assert cifrado["periodo"] == "01/09/2026 a 30/09/2026"

    assert CLAVE not in caplog.text

    # Conciliar: pasa por la conciliación existente con el PDF y la clave correctos.
    llamadas = {}

    def falso_procesar(data, db, usuario):
        llamadas["pdf"] = base64.b64decode(data.pdf_base64)
        llamadas["password"] = data.password
        llamadas["cuenta"] = data.cuenta_id
        return ProcesarExtractoResponse(ok=True, historial_id="h-1", banco_detectado="bancolombia")

    monkeypatch.setattr(router_correos, "procesar_extracto", falso_procesar)
    c = client.post(f"/correos/extractos/{cifrado['id']}/conciliar", json={"cuenta_id": cuenta["id"]}).json()
    assert c["ok"] is True and c["historial_id"] == "h-1"
    assert llamadas["pdf"] == gmail.adjuntos["ADJ1"]
    assert llamadas["password"] == CLAVE and llamadas["cuenta"] == cuenta["id"]
    procesado = next(e for e in client.get("/correos/extractos").json() if e["id"] == cifrado["id"])
    assert procesado["estado"] == "procesado" and procesado["historial_id"] == "h-1"


def _items(resp):
    return resp["items"] if isinstance(resp, dict) and "items" in resp else resp


def test_conciliar_sin_clave_deja_falta_clave_y_no_llama_a_la_conciliacion(monkeypatch):
    gmail = _gmail_de_prueba()
    conectar_usuario("u-sin-clave", gmail, monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Ahorros", "saldo": 0}).json()
    client.post("/correos/sincronizar")
    cifrado = next(e for e in client.get("/correos/extractos").json() if e["estado"] == "falta_clave")

    def no_debe_llamarse(*a, **k):
        raise AssertionError("no se debe conciliar un PDF que no se pudo abrir")

    monkeypatch.setattr(router_correos, "procesar_extracto", no_debe_llamarse)
    r = client.post(f"/correos/extractos/{cifrado['id']}/conciliar", json={"cuenta_id": cuenta["id"]}).json()
    assert r["ok"] is False and "clave" in r["error"].lower()


def test_errores_de_gmail_no_filtran_detalles(monkeypatch):
    class Roto(GmailFalso):
        def list(self, *a, **k):
            raise RuntimeError("secreto-interno token=abc123")

    conectar_usuario("u-roto", Roto([], {}), monkeypatch)
    r = client.post("/correos/sincronizar").json()
    assert r["ok"] is False
    assert "abc123" not in str(r) and "RuntimeError" not in str(r)


def test_extractos_y_clave_son_por_usuario(monkeypatch):
    conectar_usuario("u-privado-a", _gmail_de_prueba(), monkeypatch)
    client.post("/correos/sincronizar")
    client.put("/correos/clave-pdf", json={"clave": CLAVE})
    assert len(client.get("/correos/extractos").json()) == 2

    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-privado-b", email="b@t.com", nombre="B")
    assert client.get("/correos/extractos").json() == []
    assert client.get("/correos/clave-pdf").json() == {"configurada": False}

    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-privado-a", email="a@t.com", nombre="A")
    assert client.delete("/correos/clave-pdf").json() == {"ok": True, "configurada": False}
    assert client.get("/correos/clave-pdf").json() == {"configurada": False}
