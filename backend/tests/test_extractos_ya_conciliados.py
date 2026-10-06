"""
No rebuscar lo ya conciliado: un extracto cuyo banco+cuenta+periodo ya quedó
conciliado no se descarga, no se muestra como pendiente y no cuenta en las
tareas. Gmail simulado: ninguna prueba llama a Google.
"""
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'ya_conc.db')}")

import pytest  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.extractos_conciliados import mes_del_extracto, periodo_en_asunto  # noqa: E402
from app.models import ExtractoCorreo, Movimiento  # noqa: E402
from tests.test_extractos_gmail import (  # noqa: E402
    CLAVE,
    TEXTO_EXTRACTO,
    GmailFalso,
    adjunto,
    client,
    conectar_usuario,
    hacer_pdf,
    mensaje,
)

pytest.importorskip("reportlab.pdfgen.canvas")

BANCOLOMBIA = "Bancolombia <extractos@bancolombia.com.co>"


class GmailContador(GmailFalso):
    """Cuenta cuántos adjuntos se descargan (lo caro de cada sincronización)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.descargas = 0

    def get(self, userId, id=None, messageId=None, format=None):  # noqa: N803
        if messageId:
            self.descargas += 1
        return super().get(userId, id=id, messageId=messageId, format=format)


def _conciliar_mes(uid: str, cuenta_id: str, fecha=datetime(2026, 9, 10)):
    """Deja septiembre conciliado como lo hace una subida manual: un movimiento con conciliado_en."""
    db = SessionLocal()
    try:
        db.add(Movimiento(
            usuario_id=uid, cuenta_id=cuenta_id, fecha=fecha, descripcion="Compra D1", categoria="Comida",
            tipo="expense", monto=1000, fuente="manual", cat_confirmada=True, conciliado_en=fecha,
        ))
        db.commit()
    finally:
        db.close()


def _tarea(id_):
    return next((t for t in client.get("/sincronizacion/estado").json()["tareas"] if t["id"] == id_), None)


def test_mismo_extracto_dos_veces_no_se_descarga_dos_veces(monkeypatch):
    gmail = GmailContador(
        [mensaje("e1", BANCOLOMBIA, "Tu extracto de septiembre", partes=[adjunto("Extracto_092026.pdf", "A1")])],
        {"A1": hacer_pdf(TEXTO_EXTRACTO)},
    )
    conectar_usuario("yc-dos-veces", gmail, monkeypatch)
    client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 0})

    r1 = client.post("/correos/sincronizar").json()
    assert r1["extractos_nuevos"] == 1 and gmail.descargas == 1
    r2 = client.post("/correos/sincronizar", params={"completa": True}).json()
    assert r2["extractos_nuevos"] == 0
    assert gmail.descargas == 1  # ya registrado: ni se descarga ni se analiza otra vez
    assert len(client.get("/correos/extractos").json()) == 1


def test_periodo_conciliado_por_subida_manual_se_guarda_sin_descargar(monkeypatch):
    gmail = GmailContador(
        [mensaje("e1", BANCOLOMBIA, "Tu extracto de septiembre", partes=[adjunto("Extracto_092026.pdf", "A1")])],
        {"A1": hacer_pdf(TEXTO_EXTRACTO)},
    )
    conectar_usuario("yc-previo", gmail, monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 0}).json()
    _conciliar_mes("yc-previo", cuenta["id"])

    r = client.post("/correos/sincronizar").json()
    assert r["ok"] and r["extractos_nuevos"] == 0
    assert gmail.descargas == 0  # el asunto ya decía septiembre: no hizo falta abrir el PDF

    filas = client.get("/correos/extractos").json()
    assert [(f["estado"], f["banco"], f["periodo"], f["cruzados"]) for f in filas] == [
        ("ya_conciliado", "Bancolombia", "septiembre 2026", 1)
    ]
    assert _tarea("extractos_por_conciliar") is None
    # Y no vuelve a leerse en la siguiente sincronización.
    client.post("/correos/sincronizar", params={"completa": True})
    assert gmail.descargas == 0 and len(client.get("/correos/extractos").json()) == 1


def test_extracto_pendiente_pasa_a_ya_conciliado_cuando_el_periodo_se_concilia_despues(monkeypatch):
    gmail = GmailContador(
        [mensaje("e1", BANCOLOMBIA, "Extracto", partes=[adjunto("Extracto_092026.pdf", "A1")])],
        {"A1": hacer_pdf(TEXTO_EXTRACTO)},
    )
    conectar_usuario("yc-despues", gmail, monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 0}).json()
    client.post("/correos/sincronizar")
    assert client.get("/correos/extractos").json()[0]["estado"] == "nuevo"
    assert _tarea("extractos_por_conciliar")["cantidad"] == 1

    _conciliar_mes("yc-despues", cuenta["id"])  # el usuario subió el archivo a mano

    assert _tarea("extractos_por_conciliar") is None
    assert client.get("/correos/extractos").json()[0]["estado"] == "ya_conciliado"
    assert client.get("/correos/extractos?estado=nuevo").json() == []


def test_conciliado_de_otra_cuenta_o_mes_no_oculta_el_extracto(monkeypatch):
    gmail = GmailContador(
        [mensaje("e1", BANCOLOMBIA, "Tu extracto de septiembre", partes=[adjunto("Extracto_092026.pdf", "A1")])],
        {"A1": hacer_pdf(TEXTO_EXTRACTO)},
    )
    conectar_usuario("yc-otro", gmail, monkeypatch)
    client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 0})
    otra = client.post("/cuentas", json={"nombre": "Nequi", "saldo": 0}).json()
    _conciliar_mes("yc-otro", otra["id"])  # septiembre conciliado, pero en Nequi
    r = client.post("/correos/sincronizar").json()
    assert r["extractos_nuevos"] == 1 and gmail.descargas == 1
    assert client.get("/correos/extractos").json()[0]["estado"] == "nuevo"


def test_falta_clave_se_reintenta_solo_con_clave_nueva(monkeypatch):
    gmail = GmailContador(
        [mensaje("e1", BANCOLOMBIA, "Extracto", partes=[adjunto("Extracto_092026.pdf", "A1")])],
        {"A1": hacer_pdf(TEXTO_EXTRACTO, CLAVE)},
    )
    conectar_usuario("yc-clave", gmail, monkeypatch)
    client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 0})

    client.post("/correos/sincronizar")
    assert client.get("/correos/extractos").json()[0]["estado"] == "falta_clave"
    assert gmail.descargas == 1

    client.post("/correos/sincronizar", params={"completa": True})
    assert gmail.descargas == 1  # sin clave nueva no se vuelve a bajar

    client.put("/correos/clave-pdf", json={"clave": "0000"})  # clave equivocada
    client.post("/correos/sincronizar", params={"completa": True})
    assert gmail.descargas == 2
    assert client.get("/correos/extractos").json()[0]["estado"] == "falta_clave"
    client.post("/correos/sincronizar", params={"completa": True})
    assert gmail.descargas == 2  # esa misma clave ya falló: no insiste

    client.put("/correos/clave-pdf", json={"clave": CLAVE})  # clave nueva y buena
    client.post("/correos/sincronizar", params={"completa": True})
    assert gmail.descargas == 3
    assert client.get("/correos/extractos").json()[0]["estado"] == "nuevo"


def test_falta_clave_reintentada_de_un_periodo_conciliado_queda_ya_conciliado(monkeypatch):
    gmail = GmailContador(
        [mensaje("e1", BANCOLOMBIA, "Extracto", partes=[adjunto("Extracto_092026.pdf", "A1")])],
        {"A1": hacer_pdf(TEXTO_EXTRACTO, CLAVE)},
    )
    conectar_usuario("yc-clave-conc", gmail, monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 0}).json()
    client.post("/correos/sincronizar")
    _conciliar_mes("yc-clave-conc", cuenta["id"])
    client.put("/correos/clave-pdf", json={"clave": CLAVE})
    client.post("/correos/sincronizar", params={"completa": True})
    assert client.get("/correos/extractos").json()[0]["estado"] == "ya_conciliado"
    assert _tarea("falta_clave") is None


def test_contadores_de_sincronizacion_no_incluyen_conciliados_ni_descartados(monkeypatch):
    conectar_usuario("yc-contadores", GmailContador([], {}), monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Nu", "saldo": 0}).json()
    db = SessionLocal()
    try:
        for n, estado in enumerate(["nuevo", "ya_conciliado", "ya_conciliado", "descartado", "procesado"]):
            db.add(ExtractoCorreo(
                usuario_id="yc-contadores", gmail_msg_id=f"m{n}", archivo=f"e{n}.pdf", remitente="x@nu.com.co",
                banco="Nu Colombia", periodo=f"agosto 2026" if n else "septiembre 2026", estado=estado,
                cuenta_sugerida_id=cuenta["id"], recibido_en=datetime(2026, 10, 2),
            ))
        db.commit()
    finally:
        db.close()
    assert _tarea("extractos_por_conciliar")["cantidad"] == 1
    por_estado = {f["estado"] for f in client.get("/correos/extractos").json()}
    assert "descartado" not in por_estado and "ya_conciliado" in por_estado


def test_periodo_en_asunto_y_mes():
    hoy = datetime(2026, 10, 5)
    assert periodo_en_asunto("Tu extracto de septiembre", hoy) == "septiembre 2026"
    assert periodo_en_asunto("Extracto de diciembre", hoy) == "diciembre 2025"  # aún no llegaba diciembre
    assert periodo_en_asunto("Extracto marzo de 2025", hoy) == "marzo 2025"
    assert periodo_en_asunto("Tu extracto está listo", hoy) == ""
    assert mes_del_extracto(periodo_en_asunto("Extracto de agosto", hoy), None) == "2026-08"


@pytest.fixture(autouse=True)
def _entorno(monkeypatch):
    from cryptography.fernet import Fernet

    from app.config import settings

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    yield
