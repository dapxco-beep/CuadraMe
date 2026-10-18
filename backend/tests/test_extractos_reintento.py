"""Motivo de error guardado al leer un extracto de Gmail y «Intentar de nuevo» (reproceso). Gmail simulado."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'reintento.db')}")

import pytest  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import ExtractoCorreo  # noqa: E402
from tests.test_extractos_gmail import (  # noqa: E402
    CLAVE,
    TEXTO_EXTRACTO,
    GmailFalso,
    _entorno,  # noqa: F401  (clave Fernet de prueba, autouse)
    adjunto,
    client,
    conectar_usuario,
    hacer_pdf,
    mensaje,
)

pytest.importorskip("reportlab.pdfgen.canvas")

BANCOLOMBIA = "Bancolombia <extractos@bancolombia.com.co>"


def _fila(uid):
    db = SessionLocal()
    try:
        f = db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == uid, ExtractoCorreo.archivo != "").first()
        return f.id, f.estado, f.motivo_error, f.periodo
    finally:
        db.close()


def test_motivo_de_clave_y_reintento_con_la_clave_buena(monkeypatch):
    gmail = GmailFalso(
        [mensaje("r1", BANCOLOMBIA, "Extracto", partes=[adjunto("Extracto_092026.pdf", "A1")])],
        {"A1": hacer_pdf(TEXTO_EXTRACTO, CLAVE)},
    )
    conectar_usuario("reint-clave", gmail, monkeypatch)
    client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 0})
    client.post("/correos/sincronizar")
    eid, estado, motivo, _ = _fila("reint-clave")
    assert (estado, motivo) == ("falta_clave", "clave_faltante")

    client.put("/correos/clave-pdf", json={"clave": "0000"})  # equivocada
    client.post("/correos/sincronizar", params={"completa": True})
    assert _fila("reint-clave")[2] == "clave_incorrecta"
    todos = client.get("/sincronizacion/extractos").json()["items"]
    assert todos[0]["estado_vista"] == "necesita_clave" and todos[0]["acciones"] == ["poner_clave", "probar_clave"]

    r = client.post(f"/correos/extractos/{eid}/reintentar").json()
    assert r["ok"] is False and r["estado"] == "falta_clave" and "clave" in r["mensaje"]

    client.put("/correos/clave-pdf", json={"clave": CLAVE})
    r = client.post(f"/correos/extractos/{eid}/reintentar").json()
    assert r["ok"] is True and r["estado"] == "nuevo" and r["motivo_error"] is None
    _, estado, motivo, periodo = _fila("reint-clave")
    assert (estado, motivo) == ("nuevo", None) and periodo  # el reproceso también rellena el periodo
    item = client.get("/sincronizacion/extractos").json()["items"][0]
    assert item["estado_vista"] == "sin_procesar" and item["mes"] == "2026-09"


def test_archivo_vacio_dice_el_motivo_y_se_puede_reintentar(monkeypatch):
    gmail = GmailFalso(
        [mensaje("r2", BANCOLOMBIA, "Extracto", partes=[adjunto("Extracto_092026.pdf", "A1")])],
        {"A1": b""},
    )
    conectar_usuario("reint-vacio", gmail, monkeypatch)
    client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 0})
    client.post("/correos/sincronizar")
    eid, estado, motivo, _ = _fila("reint-vacio")
    assert (estado, motivo) == ("error", "archivo_vacio")
    item = client.get("/sincronizacion/extractos").json()["items"][0]
    assert item["estado_vista"] == "no_se_pudo_leer"
    assert item["resultado"].startswith("No pudimos leer este extracto: el archivo llegó vacío o dañado")
    assert item["acciones"][0] == "intentar_de_nuevo"
    r = client.post(f"/correos/extractos/{eid}/reintentar").json()
    assert r["ok"] is False and r["motivo_error"] == "archivo_vacio" and "vacío" in r["mensaje"]
    # Gmail se cae: motivo temporal, y el extracto sigue ahí para reintentar.
    gmail.adjuntos["A1"] = hacer_pdf(TEXTO_EXTRACTO)
    r = client.post(f"/correos/extractos/{eid}/reintentar").json()
    assert r["ok"] is True and _fila("reint-vacio")[2] is None


def test_procesar_un_archivo_roto_guarda_el_motivo_en_el_historial(monkeypatch):
    import base64

    gmail = GmailFalso([], {})
    conectar_usuario("reint-hist", gmail, monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Nu Colombia", "saldo": 0}).json()["id"]
    r = client.post("/conciliacion/procesar", json={"pdf_base64": base64.b64encode(b"no soy un pdf").decode(),
                                                   "cuenta_id": cuenta})
    assert r.json()["ok"] is False and r.json()["motivo_error"] == "archivo_vacio"
    escaneado = hacer_pdf([])  # PDF válido sin texto: una imagen escaneada se ve igual
    r = client.post("/conciliacion/procesar", json={"pdf_base64": base64.b64encode(escaneado).decode(),
                                                   "cuenta_id": cuenta})
    assert r.json()["motivo_error"] == "pdf_escaneado"
    cifrado = hacer_pdf(TEXTO_EXTRACTO, CLAVE)
    r = client.post("/conciliacion/procesar", json={"pdf_base64": base64.b64encode(cifrado).decode(),
                                                   "cuenta_id": cuenta})
    assert r.json()["motivo_error"] == "clave_faltante" and r.json()["requiere_clave"] is True
    r = client.post("/conciliacion/procesar", json={"pdf_base64": base64.b64encode(cifrado).decode(),
                                                   "cuenta_id": cuenta, "password": "0000"})
    assert r.json()["motivo_error"] == "clave_incorrecta"
    # Los intentos fallidos salen en la lista agrupados por lo que les pasa: los que esperan la clave van en UNA
    # fila («x2 intentos», con un solo botón «Poner la clave») y los demás en otra.
    items = client.get("/sincronizacion/extractos").json()["items"]
    err = [i for i in items if i["estado_vista"] == "no_se_pudo_leer"]
    assert sorted(i["copias"] for i in err) == [2, 2] and {i["copias_texto"] for i in err} == {"x2 intentos"}
    clave = next(i for i in err if "poner_clave" in i["acciones"])
    assert clave["titulo"] == "2 extractos de Nu Colombia esperan la clave del PDF"
    otros = next(i for i in err if "poner_clave" not in i["acciones"])
    assert otros["motivo_error"] in ("archivo_vacio", "pdf_escaneado")
