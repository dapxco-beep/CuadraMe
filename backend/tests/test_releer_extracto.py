"""«Releer este extracto»: reconciliar la lectura guardada con el lector de hoy. Gmail y lector simulados,
datos 100 % inventados."""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'releer_extracto.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import limites  # noqa: E402
from app import releer_extracto as rx  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.conciliacion import compute_fingerprint  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, Perfil  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)


class _Exec:
    def __init__(self, v): self.v = v
    def execute(self): return self.v


class GmailFalso:
    def __init__(self, falla=False):
        self.llamadas, self.falla = 0, falla

    def users(self): return self
    def messages(self): return self

    def get(self, **kw):
        self.llamadas += 1
        if self.falla:
            raise RuntimeError("sin red")
        return _Exec({"id": kw["id"]})


# Lectura NUEVA: la fila de resumen ya es un pago de 474.542, y hay una línea que antes no se leía.
LECTURA_NUEVA = [
    {"fecha": "2026-10-02", "descripcion": "Compra en tienda uno", "monto": 30000.0, "tipo": "expense"},
    {"fecha": "2026-10-05", "descripcion": "Pago de la factura anterior", "monto": 474542.0, "tipo": "income",
     "pago_tarjeta": True, "pago_detalle": {"capital": 474542.0, "intereses": 0.0, "cargos": 0.0, "aplicado": [474542.0]}},
    {"fecha": "2026-10-09", "descripcion": "Compra en tienda dos", "monto": 15000.0, "tipo": "expense"},
]


@pytest.fixture(autouse=True)
def _simulado(monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.setattr(rx, "listar_adjuntos_pdf", lambda msg: [{"archivo": "nu.pdf", "attachment_id": "a1"}])
    monkeypatch.setattr(rx, "descargar_adjunto", lambda g, m, a: b"%PDF-falso")
    monkeypatch.setattr(rx, "abrir_pdf", lambda pdf, claves: ("ok", "texto", None))
    monkeypatch.setattr(rx, "_leer_lineas", lambda texto: [dict(m) for m in LECTURA_NUEVA])
    yield
    app.dependency_overrides.clear()


def _montar(uid, monkeypatch, gmail=None, con_correo=True, estado="pendiente_revision", saldos_manual=False):
    gmail = gmail or GmailFalso()
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.com", nombre="Persona Prueba")
    monkeypatch.setattr(router_correos, "cliente_gmail", lambda _t: gmail)
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", gmail_conectado=True, gmail_refresh_token_enc="t", gmail_email="x@g.com"))
        c = Cuenta(usuario_id=uid, nombre="Nu tarjeta", tipo="credito", saldo=0)
        db.add(c)
        db.flush()
        review = [
            # resuelta: se conserva
            {"fecha": "2026-10-02", "descripcion": "Compra en tienda uno", "monto": 30000.0, "tipo": "expense",
             "fingerprint": compute_fingerprint("2026-10-02", 30000.0, c.id, "Compra en tienda uno", "expense"),
             "estado": "importado", "movimiento_id": "mov-1"},
            # lectura vieja equivocada: un gasto que NO existe
            {"fecha": "2026-10-05", "descripcion": "Pago $697.534,97 -$474.542,00", "monto": 222992.97, "tipo": "expense",
             "fingerprint": "huella-vieja-mala", "estado": "faltante", "categoria_sugerida": "Otros"},
        ]
        h = HistorialExtracto(usuario_id=uid, cuenta_id=c.id, banco_detectado="nu", estado=estado,
                              total_movimientos=2, importados=1, faltantes=1, review_json=json.dumps(review))
        if saldos_manual:
            h.saldo_final_extracto, h.fecha_corte, h.saldos_origen = 123.0, "2026-10-15", "manual"
        db.add(h)
        db.flush()
        if con_correo:
            db.add(ExtractoCorreo(usuario_id=uid, gmail_msg_id=f"m-{uid}", archivo="nu.pdf", estado="procesado", historial_id=h.id))
        db.commit()
        return h.id, c.id
    finally:
        db.close()


def _estado(hid):
    db = SessionLocal()
    try:
        h = db.get(HistorialExtracto, hid)
        return h.estado, h.faltantes, h.importados, h.total_movimientos, h.saldos_origen, h.saldo_final_extracto, json.loads(h.review_json)
    finally:
        db.close()


def test_reemplaza_faltante_mal_leida_conserva_importada_y_agrega_nueva(monkeypatch):
    hid, _ = _montar("rx-1", monkeypatch)
    r = client.post(f"/conciliacion/historial/{hid}/releer")
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["cambiadas"], j["agregadas"], j["quitadas"], j["conservadas"]) == (1, 1, 0, 1)
    assert j["mensaje"].startswith("Cambié 1 línea, agregué 1, conservé 1")
    estado, faltantes, importados, total, _, _, review = _estado(hid)
    descs = {i["descripcion"]: i for i in review}
    assert "Pago $697.534,97 -$474.542,00" not in descs
    assert descs["Compra en tienda uno"]["estado"] == "importado" and descs["Compra en tienda uno"]["movimiento_id"] == "mov-1"
    assert descs["Pago de la factura anterior"]["estado"] == "faltante" and descs["Pago de la factura anterior"]["pago_detalle"]
    assert descs["Compra en tienda dos"]["estado"] == "faltante"
    assert (estado, faltantes, importados, total) == ("pendiente_revision", 2, 1, 3)


def test_idempotente(monkeypatch):
    hid, _ = _montar("rx-2", monkeypatch)
    assert client.post(f"/conciliacion/historial/{hid}/releer").status_code == 200
    antes = _estado(hid)
    limites._eventos.pop(f"releer-extracto:{hid}", None)  # saltar el límite de 1 por minuto
    j = client.post(f"/conciliacion/historial/{hid}/releer").json()
    assert (j["cambiadas"], j["agregadas"], j["quitadas"]) == (0, 0, 0) and "no cambié nada" in j["mensaje"]
    assert _estado(hid) == antes


def test_sin_faltantes_pasa_a_conciliado(monkeypatch):
    monkeypatch.setattr(rx, "_leer_lineas", lambda texto: [dict(LECTURA_NUEVA[0])])
    hid, _ = _montar("rx-3", monkeypatch)
    j = client.post(f"/conciliacion/historial/{hid}/releer").json()
    assert (j["cambiadas"], j["agregadas"], j["quitadas"]) == (0, 0, 1)
    estado, faltantes, *_ = _estado(hid)
    assert (estado, faltantes) == ("conciliado", 0)


def test_subido_a_mano_da_409(monkeypatch):
    hid, _ = _montar("rx-4", monkeypatch, con_correo=False)
    r = client.post(f"/conciliacion/historial/{hid}/releer")
    assert r.status_code == 409 and "súbelo de nuevo" in r.json()["detail"]


def test_falla_de_gmail_no_escribe(monkeypatch):
    gmail = GmailFalso(falla=True)
    hid, _ = _montar("rx-5", monkeypatch, gmail=gmail)
    antes = _estado(hid)
    r = client.post(f"/conciliacion/historial/{hid}/releer")
    assert r.status_code == 502 and "no cambié nada" in r.json()["detail"]
    assert _estado(hid) == antes


def test_pdf_sin_movimientos_no_escribe(monkeypatch):
    monkeypatch.setattr(rx, "_leer_lineas", lambda texto: [])
    hid, _ = _montar("rx-6", monkeypatch)
    antes = _estado(hid)
    assert client.post(f"/conciliacion/historial/{hid}/releer").status_code == 409
    assert _estado(hid) == antes


def test_saldos_manuales_no_se_pisan(monkeypatch):
    monkeypatch.setattr("app.routers.conciliacion._saldos_del_extracto",
                        lambda c, t, m: {"saldo_final": 999.0, "saldo_inicial": 1.0, "fecha_corte": "2026-10-15"})
    hid, _ = _montar("rx-7", monkeypatch, saldos_manual=True)
    client.post(f"/conciliacion/historial/{hid}/releer")
    assert _estado(hid)[4:6] == ("manual", 123.0)
    hid2, _ = _montar("rx-8", monkeypatch)
    client.post(f"/conciliacion/historial/{hid2}/releer")
    assert _estado(hid2)[5] == 999.0


def test_limite_de_una_vez_por_minuto(monkeypatch):
    hid, _ = _montar("rx-9", monkeypatch)
    assert client.post(f"/conciliacion/historial/{hid}/releer").status_code == 200
    assert client.post(f"/conciliacion/historial/{hid}/releer").status_code == 429


def test_automatico_relee_una_vez_por_version_y_no_toca_conciliados(monkeypatch):
    gmail = GmailFalso()
    _montar("rx-10", monkeypatch, gmail=gmail)
    j = client.post("/conciliacion/releer-pendientes").json()
    assert j["releidos"] == 1 and j["cambiados"] == 1
    llamadas = gmail.llamadas
    j = client.post("/conciliacion/releer-pendientes").json()
    assert j["releidos"] == 0 and gmail.llamadas == llamadas  # una sola vez por versión del lector
    monkeypatch.setattr(rx, "VERSION_LECTOR", "otra-version")  # el lector mejoró: vuelve a leer
    assert client.post("/conciliacion/releer-pendientes").json()["releidos"] == 1

    # Un conciliado que NO es de tarjeta (cuenta de ahorros, sin pistas de tarjeta) no se toca solo.
    gmail2 = GmailFalso()
    hid2, cid2 = _montar("rx-11", monkeypatch, gmail=gmail2, estado="conciliado")
    db = SessionLocal()
    db.get(Cuenta, cid2).tipo = "ahorro"
    db.commit()
    db.close()
    assert client.post("/conciliacion/releer-pendientes").json()["releidos"] == 0 and gmail2.llamadas == 0


def test_automatico_conciliado_de_tarjeta_solo_agrega(monkeypatch):
    """Un conciliado de TARJETA (ya en su cuenta de crédito) se relee una vez por versión en modo «solo agregar»:
    lo importado queda intacto, la línea nueva entra como faltante y el extracto vuelve a «por revisar»."""
    gmail = GmailFalso()
    hid, _ = _montar("rx-13", monkeypatch, gmail=gmail, estado="conciliado")
    db = SessionLocal()
    h = db.get(HistorialExtracto, hid)
    r = json.loads(h.review_json)
    r[1]["estado"] = "exacto"  # la línea mal leída ya estaba resuelta: nada que reemplazar ni quitar
    h.review_json = json.dumps(r)
    db.commit()
    db.close()
    antes = _estado(hid)[6]
    j = client.post("/conciliacion/releer-pendientes").json()
    assert j["releidos"] == 1 and j["cambiados"] == 1
    estado, faltantes, _, _, _, _, review = _estado(hid)
    assert estado == "pendiente_revision" and faltantes == 2
    assert review[:2] == antes[:2]  # lo que había, intacto
    assert {i["descripcion"] for i in review if i["estado"] == "faltante"} == {"Pago de la factura anterior", "Compra en tienda dos"}
    assert client.post("/conciliacion/releer-pendientes").json()["releidos"] == 0  # una sola vez por versión


def test_automatico_con_gmail_caido_reintenta_despues(monkeypatch):
    gmail = GmailFalso(falla=True)
    hid, _ = _montar("rx-12", monkeypatch, gmail=gmail)
    antes = _estado(hid)
    assert client.post("/conciliacion/releer-pendientes").json()["releidos"] == 0
    assert _estado(hid) == antes
    gmail.falla = False
    assert client.post("/conciliacion/releer-pendientes").json()["releidos"] == 1
