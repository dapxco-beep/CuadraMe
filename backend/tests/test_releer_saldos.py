"""Releer saldos de extractos ya procesados sin saldos (lector viejo). Datos 100 % inventados.
El PDF no se conserva: se vuelve a traer de Gmail (aquí un Gmail falso) y solo se completan los saldos."""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'releer.db')}")

import pytest  # noqa: E402

from app import releer_saldos as rs  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402,F401  (registra todos los modelos)
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento  # noqa: E402

Base.metadata.create_all(bind=engine)

TEXTO_NU = """Extracto de tu cuenta Nu
Del 1 de septiembre de 2026 al 30 de septiembre de 2026
Tu dinero al inicio del mes $500.000,00
Tu dinero a final del mes $700.000,00
"""
REVIEW = [{"fecha": "2026-09-05", "descripcion": "Pago", "monto": 200000, "tipo": "income", "estado": "exacto", "fingerprint": "f"}]


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


@pytest.fixture(autouse=True)
def _pdf(monkeypatch):
    monkeypatch.setattr(rs, "listar_adjuntos_pdf", lambda msg: [{"archivo": "nu.pdf", "attachment_id": "a1"}])
    monkeypatch.setattr(rs, "descargar_adjunto", lambda g, m, a: b"%PDF-falso")
    monkeypatch.setattr(rs, "abrir_pdf", lambda pdf, claves: ("ok", TEXTO_NU, None))


def _escenario(uid, saldos_manual=False):
    db = SessionLocal()
    try:
        c = Cuenta(usuario_id=uid, nombre="Nu", tipo="ahorro", saldo=700000)
        db.add(c)
        db.flush()
        h = HistorialExtracto(usuario_id=uid, cuenta_id=c.id, banco_detectado="nu", estado="conciliado",
                              review_json=json.dumps(REVIEW))
        if saldos_manual:
            h.saldo_final_extracto, h.fecha_corte, h.saldos_origen = 123.0, "2026-09-30", "manual"
        db.add(h)
        db.flush()
        db.add(ExtractoCorreo(usuario_id=uid, gmail_msg_id=f"m-{uid}", archivo="nu.pdf", estado="procesado", historial_id=h.id))
        db.commit()
        return h.id
    finally:
        db.close()


def _correr(uid, gmail):
    db = SessionLocal()
    try:
        return rs.releer(db, uid, gmail)
    finally:
        db.close()


def _h(hid):
    db = SessionLocal()
    try:
        h = db.get(HistorialExtracto, hid)
        return (h.saldo_inicial_extracto, h.saldo_final_extracto, h.saldos_origen, h.estado, h.fecha_corte)
    finally:
        db.close()


def test_completa_saldos_sin_duplicar_y_una_sola_vez():
    hid = _escenario("rs-1")
    db = SessionLocal()
    antes = db.query(Movimiento).count()
    db.close()
    g = GmailFalso()
    r = _correr("rs-1", g)
    assert r["leidos"] == 1
    ini, fin, origen, estado, corte = _h(hid)
    assert (ini, fin, origen, estado) == (500000.0, 700000.0, "extracto", "conciliado") and corte is not None
    db = SessionLocal()
    assert db.query(Movimiento).count() == antes
    db.close()
    # segunda corrida: ya tiene saldos, no vuelve a Gmail
    r2 = _correr("rs-1", g)
    assert r2["leidos"] == 0 and g.llamadas == 1


def test_si_el_pdf_no_trae_saldo_se_intenta_una_vez_y_queda_para_escribirlo(monkeypatch):
    monkeypatch.setattr(rs, "abrir_pdf", lambda pdf, claves: ("ok", "Extracto sin resumen", None))
    hid = _escenario("rs-2")
    g = GmailFalso()
    assert _correr("rs-2", g)["sin_saldo"] == 1
    assert _correr("rs-2", g)["sin_saldo"] == 0 and g.llamadas == 1
    assert _h(hid)[1] is None
    db = SessionLocal()
    try:
        assert rs.pendientes_por_historial(db, "rs-2") == set()
    finally:
        db.close()


def test_si_gmail_falla_se_reintenta_despues():
    hid = _escenario("rs-3")
    assert _correr("rs-3", GmailFalso(falla=True))["fallidos"] == 1
    assert _h(hid)[1] is None
    assert _correr("rs-3", GmailFalso())["leidos"] == 1
    assert _h(hid)[1] == 700000.0


def test_no_pisa_saldos_manuales_y_esta_aislado_por_usuario():
    manual = _escenario("rs-4", saldos_manual=True)
    ajeno = _escenario("rs-5")
    g = GmailFalso()
    assert _correr("rs-4", g)["leidos"] == 0 and g.llamadas == 0
    assert _h(manual)[1] == 123.0
    assert _h(ajeno)[1] is None  # el otro usuario no se tocó
