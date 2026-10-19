"""Corregir un pago de tarjeta importado con la lectura vieja (app/corregir_pago.py). Datos 100 % inventados:
pago A = $600.000, aplicado $400.000 + $200.000; el lector viejo lo importó por $400.000."""
import json
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'corregir_pago.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import corregir_pago as cp  # noqa: E402
from app import duplicados as dup  # noqa: E402
from app import limites  # noqa: E402
from app import releer_extracto as rx  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.conciliacion import compute_fingerprint  # noqa: E402
from app.contabilidad import CATEGORIA_PAGO_TARJETA, MARCA_TRASLADO_PROPIO, delta_saldo  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, HuellaOrigen, Movimiento, Perfil  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)

DESC_VIEJA = "Pago de tu tarjeta (factura anterior)"
DESC_NUEVA = "Pago de tu tarjeta"
A, B, C = 600000.0, 400000.0, 200000.0
REGLA = {"descripcion": DESC_VIEJA, "tipo": "income", "montos": [B, C]}
FECHA = "2026-10-05"


def _linea_pago(cuenta_id, **extra):
    d = {"fecha": FECHA, "descripcion": DESC_NUEVA, "monto": A, "tipo": "income", "linea_tipo": "pago",
         "pago_tarjeta": True, "pista": MARCA_TRASLADO_PROPIO, "corrige_lectura": dict(REGLA),
         "pago_detalle": {"capital": A, "intereses": 0.0, "cargos": 0.0, "aplicado": [B, C]}, "cuenta": cuenta_id}
    d.update(extra)
    return d


class _Exec:
    def __init__(self, v): self.v = v
    def execute(self): return self.v


class GmailFalso:
    def users(self): return self
    def messages(self): return self
    def get(self, **kw): return _Exec({"id": kw["id"]})


@pytest.fixture(autouse=True)
def _simulado(monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.setattr(rx, "listar_adjuntos_pdf", lambda msg: [{"archivo": "nu.pdf", "attachment_id": "a1"}])
    monkeypatch.setattr(rx, "descargar_adjunto", lambda g, m, a: b"%PDF-falso")
    monkeypatch.setattr(rx, "abrir_pdf", lambda pdf, claves: ("ok", "texto", None))
    monkeypatch.setattr(router_correos, "cliente_gmail", lambda _t: GmailFalso())
    yield
    app.dependency_overrides.clear()


def _como(uid):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.com", nombre="Persona Prueba")


def _escena(uid, *, viejo=True, nuevo_ya=False, marca=True, desc_viejo=DESC_VIEJA, monto_viejo=B):
    """Tarjeta con deuda, un pago viejo por B (si `viejo`), y un extracto con la línea nueva por A."""
    _como(uid)
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", gmail_conectado=True, gmail_refresh_token_enc="t", gmail_email="x@g.com"))
        cuenta = Cuenta(usuario_id=uid, nombre="Nu tarjeta", tipo="credito", saldo=-1000000.0)
        db.add(cuenta)
        db.flush()
        review, ids = [], {}
        if viejo:
            m = Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion=desc_viejo, categoria=CATEGORIA_PAGO_TARJETA,
                           tipo="income", monto=monto_viejo, fecha=datetime(2026, 10, 5), fuente="conciliacion_extracto",
                           notas=f"Importado desde extracto nu · {MARCA_TRASLADO_PROPIO}")
            db.add(m)
            db.flush()
            cuenta.saldo += monto_viejo
            dup.nuevo_movimiento(db, m, dup.ORIGEN_EXTRACTO, dup.huella_extracto("fp-viejo", 1))
            ids["viejo"] = m.id
            review.append({"fecha": FECHA, "descripcion": desc_viejo, "monto": monto_viejo, "tipo": "income",
                           "fingerprint": "fp-viejo", "estado": "importado", "movimiento_id": m.id})
        if nuevo_ya:
            n = Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion=DESC_NUEVA, categoria=CATEGORIA_PAGO_TARJETA,
                           tipo="income", monto=A, fecha=datetime(2026, 10, 5), fuente="conciliacion_extracto",
                           notas=f"Importado desde extracto nu · {MARCA_TRASLADO_PROPIO}")
            db.add(n)
            db.flush()
            cuenta.saldo += A
            dup.nuevo_movimiento(db, n, dup.ORIGEN_EXTRACTO, dup.huella_extracto("fp-nuevo", 1))
            ids["nuevo"] = n.id
        fp_nuevo = compute_fingerprint(FECHA, A, cuenta.id, DESC_NUEVA, "income")
        linea = _linea_pago(cuenta.id)
        if not marca:
            linea.pop("corrige_lectura")
        review.append({**linea, "fingerprint": fp_nuevo, "estado": "importado" if nuevo_ya else "faltante",
                       **({"movimiento_id": ids["nuevo"]} if nuevo_ya else {})})
        h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta.id, banco_detectado="nu", estado="pendiente_revision",
                              total_movimientos=len(review), review_json=json.dumps(review))
        db.add(h)
        db.flush()
        db.add(ExtractoCorreo(usuario_id=uid, gmail_msg_id=f"m-{uid}", archivo="nu.pdf", estado="procesado", historial_id=h.id))
        db.commit()
        return {"hid": h.id, "cuenta": cuenta.id, "fp": fp_nuevo, **ids}
    finally:
        db.close()


def _revision(hid):
    db = SessionLocal()
    try:
        h = db.get(HistorialExtracto, hid)
        return h.estado, json.loads(h.review_json)
    finally:
        db.close()


def _movs(cuenta_id):
    db = SessionLocal()
    try:
        return [(m.id, m.monto, m.descripcion, m.categoria, m.notas, m.tipo) for m in
                db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta_id).order_by(Movimiento.monto).all()]
    finally:
        db.close()


def _saldo(cuenta_id):
    db = SessionLocal()
    try:
        return db.get(Cuenta, cuenta_id).saldo
    finally:
        db.close()


def _marcar_y_guardar(uid, e):
    db = SessionLocal()
    try:
        _, review = _revision(e["hid"])
        n = cp.marcar(db, uid, e["cuenta"], review)
        db.get(HistorialExtracto, e["hid"]).review_json = json.dumps(review)
        db.commit()
        return n
    finally:
        db.close()


def _importar(e, fps):
    return client.post(f"/conciliacion/historial/{e['hid']}/importar", json={"fingerprints": fps})


# ── relectura ─────────────────────────────────────────────────────────────────────────────────────
def test_relectura_marca_corregir_monto(monkeypatch):
    e = _escena("cp-1")
    monkeypatch.setattr(rx, "_leer_lineas", lambda texto: [_linea_pago(e["cuenta"])])
    r = client.post(f"/conciliacion/historial/{e['hid']}/releer")
    assert r.status_code == 200, r.text
    assert r.json()["correcciones"] == 1 and "corrección" in r.json()["mensaje"]
    estado, review = _revision(e["hid"])
    linea = next(i for i in review if i["descripcion"] == DESC_NUEVA)
    assert linea["estado"] == "corregir_monto" and linea["monto_anterior"] == B and linea["corrige_movimiento_id"] == e["viejo"]
    assert linea["marcar_por_defecto"] is True and estado == "pendiente_revision"
    # solo se propone: un movimiento, mismo saldo
    assert [m[1] for m in _movs(e["cuenta"])] == [B] and _saldo(e["cuenta"]) == -1000000.0 + B


def test_relectura_sin_movimiento_viejo_es_pago_normal(monkeypatch):
    e = _escena("cp-2", viejo=False)
    monkeypatch.setattr(rx, "_leer_lineas", lambda texto: [_linea_pago(e["cuenta"])])
    client.post(f"/conciliacion/historial/{e['hid']}/releer")
    _, review = _revision(e["hid"])
    assert next(i for i in review if i["descripcion"] == DESC_NUEVA)["estado"] == "faltante"


def test_sin_la_marca_del_lector_no_corrige_por_parecido():
    """Mismo día, mismo tipo y un monto cercano NO bastan: solo corrige una regla explícita del lector."""
    e = _escena("cp-3", marca=False, monto_viejo=590000.0)
    assert _marcar_y_guardar("cp-3", e) == 0
    _, review = _revision(e["hid"])
    assert next(i for i in review if i["descripcion"] == DESC_NUEVA)["estado"] == "faltante"
    j = _importar(e, [e["fp"]]).json()
    assert j["importados"] == 1 and j["corregidos"] == 0
    assert sorted(m[1] for m in _movs(e["cuenta"])) == [590000.0, A]


def test_la_regla_no_toca_una_descripcion_distinta():
    e = _escena("cp-3b", desc_viejo="Pago de la luz")
    assert _marcar_y_guardar("cp-3b", e) == 0


# ── importar ──────────────────────────────────────────────────────────────────────────────────────
def test_importar_corrige_el_monto_sin_crear_otro_movimiento():
    e = _escena("cp-4")
    assert _marcar_y_guardar("cp-4", e) == 1
    saldo_antes = _saldo(e["cuenta"])
    r = _importar(e, [e["fp"]])
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["corregidos"], j["importados"], j["repetidos_quitados"]) == (1, 0, 0)
    movs = _movs(e["cuenta"])
    assert len(movs) == 1 and movs[0][0] == e["viejo"] and movs[0][1] == A  # mismo id, monto de hoy
    assert movs[0][3] == CATEGORIA_PAGO_TARJETA and MARCA_TRASLADO_PROPIO in movs[0][4] and movs[0][2] == DESC_NUEVA
    assert _saldo(e["cuenta"]) == saldo_antes + (A - B)  # el saldo cambia en A−B
    estado, review = _revision(e["hid"])
    assert estado == "conciliado"
    assert [i["descripcion"] for i in review] == [DESC_NUEVA]  # la línea vieja ya no estorba
    assert review[0]["estado"] == "importado" and review[0]["movimiento_id"] == e["viejo"] and review[0]["monto_anterior"] == B
    db = SessionLocal()
    try:  # sigue siendo un traslado propio (regla única de contabilidad) y las huellas llevan el monto de hoy
        m = db.get(Movimiento, e["viejo"])
        assert delta_saldo(m) == A and MARCA_TRASLADO_PROPIO in m.notas
        fotos = db.query(HuellaOrigen).filter(HuellaOrigen.movimiento_id == e["viejo"]).all()
        assert fotos and all(f.monto == A for f in fotos)
    finally:
        db.close()
    r2 = _importar(e, [e["fp"]])  # idempotente
    assert r2.json().get("ya_importado") is True
    assert _saldo(e["cuenta"]) == saldo_antes + (A - B) and len(_movs(e["cuenta"])) == 1


def test_si_el_movimiento_desaparece_antes_de_importar_se_crea_un_pago_normal():
    e = _escena("cp-6")
    _marcar_y_guardar("cp-6", e)
    db = SessionLocal()
    try:
        m = db.get(Movimiento, e["viejo"])
        db.get(Cuenta, e["cuenta"]).saldo -= m.monto
        db.delete(m)
        db.commit()
    finally:
        db.close()
    j = _importar(e, [e["fp"]]).json()
    assert (j["corregidos"], j["importados"]) == (0, 1)
    assert [m[1] for m in _movs(e["cuenta"])] == [A]


def test_aislamiento_un_id_de_otra_persona_no_se_corrige():
    otro = _escena("cp-7b")
    e = _escena("cp-7")
    db = SessionLocal()
    try:
        _, review = _revision(e["hid"])
        linea = next(i for i in review if i["descripcion"] == DESC_NUEVA)
        linea.update({"estado": "corregir_monto", "corrige_movimiento_id": otro["viejo"], "monto_anterior": B})
        propio = db.get(Movimiento, e["viejo"])  # el propio ya no existe: la única «pareja» sería la ajena
        db.get(Cuenta, e["cuenta"]).saldo -= propio.monto
        db.delete(propio)
        db.get(HistorialExtracto, e["hid"]).review_json = json.dumps(review)
        db.commit()
    finally:
        db.close()
    _como("cp-7")
    assert _importar(e, [e["fp"]]).json()["corregidos"] == 0
    assert [m[1] for m in _movs(otro["cuenta"])] == [B]  # intacto
    assert _saldo(otro["cuenta"]) == -1000000.0 + B


def test_otra_persona_no_puede_importar_en_este_historial():
    e = _escena("cp-8")
    _como("cp-8-intruso")
    assert _importar(e, [e["fp"]]).status_code == 404


# ── ya duplicado ──────────────────────────────────────────────────────────────────────────────────
def test_ya_duplicado_ofrece_quitar_el_repetido_y_lo_borra_sin_fantasma():
    e = _escena("cp-9", nuevo_ya=True)
    assert _marcar_y_guardar("cp-9", e) == 1
    _, review = _revision(e["hid"])
    viejo = next(i for i in review if i["fingerprint"] == "fp-viejo")
    assert viejo["estado"] == "quitar_repetido" and viejo["monto_correcto"] == A and viejo["movimiento_id"] == e["viejo"]
    saldo_antes = _saldo(e["cuenta"])
    j = _importar(e, ["fp-viejo"]).json()
    assert (j["repetidos_quitados"], j["corregidos"], j["importados"]) == (1, 0, 0)
    movs = _movs(e["cuenta"])
    assert [m[1] for m in movs] == [A] and movs[0][0] == e["nuevo"]
    assert _saldo(e["cuenta"]) == saldo_antes - B  # se revierte el efecto del repetido
    db = SessionLocal()
    try:  # motivo «error»: sin fantasma que bloquee la línea buena
        assert db.query(HuellaOrigen).filter(HuellaOrigen.movimiento_id == e["viejo"]).count() == 0
        assert db.query(HuellaOrigen).filter(HuellaOrigen.usuario_id == "cp-9", HuellaOrigen.estado == dup.ESTADO_DESCARTADO).count() == 0
    finally:
        db.close()
    estado, review = _revision(e["hid"])
    assert [i["fingerprint"] for i in review] == [e["fp"]] and estado == "conciliado"


def test_marcar_es_idempotente_y_revierte_si_ya_no_aplica():
    e = _escena("cp-10", nuevo_ya=True)
    db = SessionLocal()
    try:
        _, review = _revision(e["hid"])
        assert cp.marcar(db, "cp-10", e["cuenta"], review) == 1
        assert cp.marcar(db, "cp-10", e["cuenta"], review) == 0
        db.delete(db.get(Movimiento, e["viejo"]))  # el repetido desapareció por otro lado
        db.flush()
        assert cp.marcar(db, "cp-10", e["cuenta"], review) == 1
        assert next(i for i in review if i["fingerprint"] == "fp-viejo")["estado"] == "importado"
    finally:
        db.rollback()
        db.close()


def test_relectura_despues_de_corregir_no_vuelve_a_ofrecer(monkeypatch):
    e = _escena("cp-11")
    monkeypatch.setattr(rx, "_leer_lineas", lambda texto: [_linea_pago(e["cuenta"])])
    client.post(f"/conciliacion/historial/{e['hid']}/releer")
    assert _importar(e, [e["fp"]]).json()["corregidos"] == 1
    limites._eventos.pop(f"releer-extracto:{e['hid']}", None)
    j = client.post(f"/conciliacion/historial/{e['hid']}/releer").json()
    assert j.get("correcciones", 0) == 0
    estado, review = _revision(e["hid"])
    assert [i["estado"] for i in review] == ["importado"] and len(_movs(e["cuenta"])) == 1 and estado == "conciliado"


def test_conteo_y_resumen_cuentan_la_correccion():
    from app import estado_traer as et
    c = et.contar_review([{"estado": "corregir_monto"}, {"estado": "quitar_repetido"}, {"estado": "importado"}])
    assert c["correcciones"] == 2 and c["por_revisar"] == 2
    assert "incluye 2 correcciones" in et.frase(et.POR_REVISAR, c, mes="2026-10", cuenta="Nu")
