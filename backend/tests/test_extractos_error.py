"""Extractos en error (datos sintéticos): motivo siempre guardado, reintento automático de los errores de clave
que vinieron de un correo (el procesado REEMPLAZA a la fila de error) y «Quitar de la lista» solo para errores."""
import base64
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'ext_error.db')}")

import pytest  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import ExtractoCorreo, HistorialExtracto  # noqa: E402
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


def _error(uid, cuenta_id, motivo="clave_faltante"):
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta_id, banco_detectado="bancolombia", estado="error",
                              motivo_error=motivo)
        db.add(h)
        db.commit()
        return h.id
    finally:
        db.close()


def _historiales(uid):
    db = SessionLocal()
    try:
        return [(h.id, h.estado, h.motivo_error) for h in
                db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == uid).all()]
    finally:
        db.close()


def _con_correo_con_clave(uid, monkeypatch):
    gmail = GmailFalso(
        [mensaje("e1", BANCOLOMBIA, "Extracto", partes=[adjunto("Extracto_092026.pdf", "A1")])],
        {"A1": hacer_pdf(TEXTO_EXTRACTO, CLAVE)},
    )
    conectar_usuario(uid, gmail, monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 0}).json()["id"]
    client.post("/correos/sincronizar")  # sin clave guardada: el extracto queda en «falta_clave»
    return cuenta


def _lector_con_lineas(monkeypatch):
    """El PDF de prueba no trae tabla de movimientos: el lector devuelve dos líneas sintéticas."""
    from app.routers import conciliacion as mod

    lineas = [{"fecha": "2026-09-18", "descripcion": "COMPRA TIENDA UNO", "monto": 5000.0, "tipo": "expense", "referencia": ""},
              {"fecha": "2026-09-19", "descripcion": "COMPRA TIENDA DOS", "monto": 7000.0, "tipo": "expense", "referencia": ""}]
    monkeypatch.setattr(mod, "parse_texto_con_regex", lambda t: ([dict(i) for i in lineas], 0))


def test_al_guardar_la_clave_el_error_con_correo_se_reemplaza_por_el_extracto_procesado(monkeypatch):
    cuenta = _con_correo_con_clave("err-reemplazo", monkeypatch)
    _lector_con_lineas(monkeypatch)
    manual = _error("err-reemplazo", cuenta)  # un error de clave, sin vínculo directo al correo (antiguo)
    assert [h[1] for h in _historiales("err-reemplazo")] == ["error"]
    lista = client.get("/sincronizacion/extractos").json()["items"]
    fila_error = next(i for i in lista if manual in i.get("historiales_error", []))
    assert "reintentar" in fila_error["acciones"] and "quitar_de_la_lista" in fila_error["acciones"]

    r = client.put("/correos/clave-pdf", json={"clave": CLAVE}).json()
    assert r["ok"] is True and r["extractos_leidos"] == 1

    hs = _historiales("err-reemplazo")
    assert len(hs) == 1 and hs[0][0] != manual and hs[0][1] == "pendiente_revision"  # el error ya no está; no se duplicó
    db = SessionLocal()
    try:
        e = db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == "err-reemplazo").first()
        assert e.estado == "procesado" and e.historial_id == hs[0][0]
    finally:
        db.close()
    # Repetirlo no crea nada más (idempotente).
    client.put("/correos/clave-pdf", json={"clave": CLAVE})
    client.post("/conciliacion/reintentar-errores")
    assert len(_historiales("err-reemplazo")) == 1


def test_clave_incorrecta_deja_el_error_y_actualiza_el_motivo(monkeypatch):
    cuenta = _con_correo_con_clave("err-mala", monkeypatch)
    hid = _error("err-mala", cuenta)
    client.put("/correos/clave-pdf", json={"clave": "0000"})
    hs = _historiales("err-mala")
    assert hs == [(hid, "error", "clave_incorrecta")]


def test_error_subido_a_mano_no_se_reintenta_pero_se_quita(monkeypatch):
    conectar_usuario("err-mano", GmailFalso([], {}), monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Nu Colombia", "saldo": 0}).json()["id"]
    cifrado = hacer_pdf(TEXTO_EXTRACTO, CLAVE)
    r = client.post("/conciliacion/procesar", json={"pdf_base64": base64.b64encode(cifrado).decode(), "cuenta_id": cuenta})
    assert r.json()["motivo_error"] == "clave_faltante"
    item = next(i for i in client.get("/sincronizacion/extractos").json()["items"] if i["estado_vista"] == "no_se_pudo_leer")
    assert "reintentar" not in item["acciones"] and "quitar_de_la_lista" in item["acciones"]
    hid = item["historiales_error"][0]
    r = client.post(f"/conciliacion/historial/{hid}/reintentar").json()
    assert r["ok"] is False and "a mano" in r["mensaje"]

    assert client.delete(f"/conciliacion/historial/{hid}/error").json() == {"ok": True}
    assert _historiales("err-mano") == []


def test_quitar_de_la_lista_nunca_borra_un_extracto_con_revision(monkeypatch):
    conectar_usuario("err-solo", GmailFalso([], {}), monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Nu Colombia", "saldo": 0}).json()["id"]
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id="err-solo", cuenta_id=cuenta, banco_detectado="nu", estado="conciliado")
        db.add(h)
        db.commit()
        hid = h.id
    finally:
        db.close()
    assert client.delete(f"/conciliacion/historial/{hid}/error").status_code == 409
    assert client.post(f"/conciliacion/historial/{hid}/reintentar").status_code == 409
    assert [h[1] for h in _historiales("err-solo")] == ["conciliado"]
    assert client.delete("/conciliacion/historial/no-existe/error").status_code == 404


def test_errores_antiguos_sin_motivo_reciben_uno_legible(monkeypatch):
    conectar_usuario("err-vacio", GmailFalso([], {}), monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Nu Colombia", "saldo": 0}).json()["id"]
    hid = _error("err-vacio", cuenta, motivo=None)
    client.post("/conciliacion/reintentar-errores")
    assert _historiales("err-vacio") == [(hid, "error", "pdf_ilegible")]
    item = next(i for i in client.get("/sincronizacion/extractos").json()["items"] if i["estado_vista"] == "no_se_pudo_leer")
    assert item["resultado"].startswith("No pudimos leer este extracto: no pudimos leer el PDF")


def test_extracto_sin_lineas_de_un_banco_conocido_dice_sin_movimientos(monkeypatch):
    from app.routers import conciliacion as mod

    conectar_usuario("err-sinmov", GmailFalso([], {}), monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Nu Colombia", "saldo": 0}).json()["id"]
    monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: "Extracto Nu resumen del periodo sin tabla de movimientos")
    monkeypatch.setattr(mod, "detectar_banco", lambda t: "nu")
    monkeypatch.setattr(mod, "parse_texto_con_regex", lambda t: ([], 0))
    monkeypatch.setattr(mod, "senales_extracto", lambda t: 5)
    monkeypatch.setattr(mod, "_decodificar_pdf", lambda b: b"%PDF-1.4")
    monkeypatch.setattr(mod, "extraer_via_ia", lambda *a, **k: [])
    r = client.post("/conciliacion/procesar", json={"pdf_base64": "x", "cuenta_id": cuenta}).json()
    assert r["ok"] is False and r["motivo_error"] == "sin_movimientos"
    assert _historiales("err-sinmov")[0][2] == "sin_movimientos"
