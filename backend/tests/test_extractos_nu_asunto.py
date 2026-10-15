"""Correos de Nu (cuenta y tarjeta): descubrimiento, datos del cuerpo y búsqueda manual por asunto.
Todo sintético (nombres, montos y claves inventados)."""
import base64
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'nuasunto.db')}")

import pytest  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402

from app import extractos_gmail as eg  # noqa: E402
from app.config import settings  # noqa: E402
from tests.test_extractos_gmail import CLAVE, GmailFalso, adjunto, client, conectar_usuario, hacer_pdf, mensaje  # noqa: E402,F401

CUERPO_TARJETA = (
    "Así viviste un NUevo mes con tu Tarjeta Nu. Pago mínimo $372.195,67 · Período facturado 15 agosto - 14 septiembre · "
    "Fecha de corte 14 septiembre · Fecha límite de pago 5 octubre. Para abrirlo solo debes escribir el número de tu "
    "documento de identidad en el archivo adjunto."
)


@pytest.fixture(autouse=True)
def _clave_cifrado(monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())


def _con_cuerpo(msg: dict, texto: str) -> dict:
    data = base64.urlsafe_b64encode(texto.encode()).decode()
    msg["payload"]["parts"].insert(0, {"mimeType": "text/plain", "filename": "", "body": {"data": data}})
    return msg


def _gmail_nu():
    cuenta = mensaje("c1", "Nu <nu@nu.com.co>", "El extracto de tu Cuenta Nu ya está aquí",
                     snippet="Hola, Persona. Encontrarás tu extracto de septiembre del 2026 adjunto.",
                     partes=[adjunto("Nu_2026-10-04.pdf", "A1")])
    tarjeta = mensaje("t1", "Nu <nu@nu.com.co>", "Llegó el extracto de tu tarjeta de crédito Nu",
                      snippet="Así viviste un NUevo mes con tu Tarjeta Nu",
                      partes=[adjunto("Nu_tarjeta_2026-10-05.pdf", "A2")])
    _con_cuerpo(tarjeta, CUERPO_TARJETA)
    return GmailFalso([cuenta, tarjeta], {
        "A1": hacer_pdf(["Nu Colombia", "Periodo 01 - 30 SEP 2026"], CLAVE),
        "A2": hacer_pdf(["Nu Colombia Tarjeta de credito", "Fecha de corte 14/09/2026"], CLAVE),
    })


def test_ambos_correos_de_nu_se_listan_sin_cuenta_de_tarjeta_y_con_pdf_cifrado(monkeypatch):
    gmail = _gmail_nu()
    conectar_usuario("u-nu-asunto", gmail, monkeypatch)
    client.post("/cuentas", json={"nombre": "Nu Colombia", "saldo": 0})  # solo la cuenta; no hay tarjeta Nu
    r = client.post("/correos/sincronizar").json()
    assert r["extractos_nuevos"] == 2
    filas = {e["archivo"]: e for e in client.get("/correos/extractos").json()}
    assert set(filas) == {"Nu_2026-10-04.pdf", "Nu_tarjeta_2026-10-05.pdf"}
    assert all(e["estado"] == "falta_clave" and e["banco"] == "Nu Colombia" for e in filas.values())
    tarjeta = filas["Nu_tarjeta_2026-10-05.pdf"]
    assert tarjeta["datos_cuerpo"] == {
        "pago_minimo": 372195.67, "periodo_facturado": "15 agosto - 14 septiembre",
        "fecha_corte": "14 septiembre", "fecha_limite": "5 octubre",
    }
    assert filas["Nu_2026-10-04.pdf"]["datos_cuerpo"] is None
    # Con la clave guardada (la cédula) ambos se abren solos en la siguiente lectura.
    client.put("/correos/clave-pdf", json={"clave": CLAVE})
    client.post("/correos/sincronizar")
    estados = {e["archivo"]: e["estado"] for e in client.get("/correos/extractos").json()}
    assert set(estados.values()) == {"nuevo"}


def test_datos_del_cuerpo_no_inventan():
    assert eg.datos_cuerpo_tarjeta("Hola, tu tarjeta ya tiene extracto.") is None
    assert eg.datos_cuerpo_tarjeta("Fecha de corte 14 septiembre") is None  # no habla de tarjeta
    d = eg.datos_cuerpo_tarjeta("Tu Tarjeta Nu. Fecha de corte 14 de septiembre de 2026")
    assert d == {"fecha_corte": "14 de septiembre de 2026"}


def test_asunto_se_escapa_y_no_deja_operadores_libres():
    frase = eg.asunto_para_gmail('x" OR from:(otro@x.com) -in:trash {a b} \\')
    assert '"' not in frase and "(" not in frase and "{" not in frase and "\\" not in frase
    q = eg.construir_query_asunto(frase)
    assert q.count('"') == 2 and q.endswith('"')
    assert eg.asunto_para_gmail("ab") is None
    assert len(eg.asunto_para_gmail("a" * 500)) <= 80


def test_busqueda_manual_por_asunto_lista_y_procesa(monkeypatch):
    gmail = _gmail_nu()
    conectar_usuario("u-nu-buscar", gmail, monkeypatch)
    client.post("/cuentas", json={"nombre": "Nu Colombia", "saldo": 0})
    client.put("/correos/clave-pdf", json={"clave": CLAVE})
    assert client.post("/correos/extractos/buscar-asunto", json={"asunto": "ab"}).status_code == 400
    r = client.post("/correos/extractos/buscar-asunto", json={"asunto": 'Llegó el extracto de tu tarjeta de crédito Nu"'})
    assert r.status_code == 200
    q = gmail.consultas[-1]
    assert 'subject:"Llegó el extracto de tu tarjeta de crédito Nu"' in q and "newer_than:365d" in q and "has:attachment" in q
    hallados = {x["gmail_msg_id"]: x for x in r.json()}
    assert "t1" in hallados and hallados["t1"]["ya_en_lista"] is False and hallados["t1"]["remitente"].startswith("Nu")
    assert client.get("/correos/extractos").json() == []  # buscar no guarda nada
    p = client.post("/correos/extractos/buscar-asunto/procesar", json={"ids": ["t1"]})
    assert p.json() == {"ok": True, "extractos_nuevos": 1}
    filas = client.get("/correos/extractos").json()
    assert [f["archivo"] for f in filas] == ["Nu_tarjeta_2026-10-05.pdf"] and filas[0]["estado"] == "nuevo"
    # Repetir no duplica; un id raro se rechaza.
    client.post("/correos/extractos/buscar-asunto/procesar", json={"ids": ["t1"]})
    assert len(client.get("/correos/extractos").json()) == 1
    assert client.post("/correos/extractos/buscar-asunto/procesar", json={"ids": ["../x"]}).status_code == 400
