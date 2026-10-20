"""Corregir el tipo de compras de tarjeta importadas como ingreso (app/corregir_tipo.py). Datos 100 % inventados:
un extracto de tarjeta con 4 compras y 1 pago, importado con el «lector viejo» simulado (todo `income`)."""
import json
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'corregir_tipo.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import corregir_tipo as ct  # noqa: E402
from app import duplicados as dup  # noqa: E402
from app import limites  # noqa: E402
from app import releer_extracto as rx  # noqa: E402
from app import saldo_inicial_auto  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.conciliacion import compute_fingerprint  # noqa: E402
from app.contabilidad import CATEGORIA_PAGO_TARJETA, MARCA_TRASLADO_PROPIO  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, HuellaOrigen, Movimiento, Perfil  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)

COMPRAS = [(3, "Mercpago*Tienda Uno", 40000.0), (5, "Tienda Dos Titan", 23000.0),
           (9, "Temu Com", 10500.0), (12, "Tiendas Tres", 9800.0)]
PAGO = (20, "Pago de tu tarjeta", 30000.0)
TOTAL_COMPRAS = sum(c[2] for c in COMPRAS)


def _fecha(dia):
    return f"2026-06-{dia:02d}"


def _linea_compra(cuenta_id, dia, desc, monto):
    return {"fecha": _fecha(dia), "descripcion": desc, "monto": monto, "tipo": "expense", "linea_tipo": "compra",
            "corrige_tipo": {"de": "income", "a": "expense"}, "cuenta": cuenta_id}


def _linea_pago(cuenta_id):
    d, desc, monto = PAGO
    return {"fecha": _fecha(d), "descripcion": desc, "monto": monto, "tipo": "income", "linea_tipo": "pago",
            "pago_tarjeta": True, "pista": MARCA_TRASLADO_PROPIO, "cuenta": cuenta_id}


class _Exec:
    def __init__(self, v): self.v = v
    def execute(self): return self.v


class GmailFalso:
    def users(self): return self
    def messages(self): return self
    def get(self, **kw): return _Exec({"id": kw["id"]})


LECTURAS: dict[str, list[dict]] = {}


@pytest.fixture(autouse=True)
def _simulado(monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.setattr(rx, "listar_adjuntos_pdf", lambda msg: [{"archivo": "t.pdf", "attachment_id": msg["id"]}])
    monkeypatch.setattr(rx, "descargar_adjunto", lambda g, m, a: m.encode())
    monkeypatch.setattr(rx, "abrir_pdf", lambda pdf, claves: ("ok", pdf.decode(), None))
    monkeypatch.setattr(rx, "_leer_lineas", lambda texto: [dict(m) for m in LECTURAS.get(texto, [])])
    monkeypatch.setattr(router_correos, "cliente_gmail", lambda _t: GmailFalso())
    yield
    app.dependency_overrides.clear()


def _como(uid):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.com", nombre="Persona Prueba")


def _mov(db, uid, cuenta, dia, desc, monto, tipo, fuente="conciliacion_extracto", categoria="Otros", notas="", fp=None):
    m = Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion=desc, categoria=categoria, tipo=tipo, monto=monto,
                   fecha=datetime(2026, 6, dia), fuente=fuente, notas=notas)
    db.add(m)
    db.flush()
    cuenta.saldo += monto if tipo == "income" else -monto
    dup.nuevo_movimiento(db, m, dup.ORIGEN_EXTRACTO if fuente.startswith("conciliacion") else dup.ORIGEN_MANUAL,
                         dup.huella_extracto(fp, 1) if fp else None)
    return m


def _escena(uid, *, nuevo_ya=False, extra=None):
    """Tarjeta Nu (deuda inicial 0) con las 4 compras y el pago importados por el lector viejo (todo ingreso)."""
    _como(uid)
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", gmail_conectado=True, gmail_refresh_token_enc="t", gmail_email="x@g.com"))
        cuenta = Cuenta(usuario_id=uid, nombre="Nu Colombia Crédito", tipo="credito", saldo=0.0)
        db.add(cuenta)
        db.flush()
        review, ids = [], {}
        for dia, desc, monto in COMPRAS:
            fp = compute_fingerprint(_fecha(dia), monto, cuenta.id, desc, "income")
            m = _mov(db, uid, cuenta, dia, desc, monto, "income", fp=fp)
            ids[desc] = m.id
            review.append({"fecha": _fecha(dia), "descripcion": desc, "monto": monto, "tipo": "income",
                           "fingerprint": fp, "estado": "importado", "movimiento_id": m.id})
        d, desc, monto = PAGO
        fp = compute_fingerprint(_fecha(d), monto, cuenta.id, desc, "income")
        pago = _mov(db, uid, cuenta, d, desc, monto, "income", categoria=CATEGORIA_PAGO_TARJETA,
                    notas=f"Importado desde extracto nu · {MARCA_TRASLADO_PROPIO}", fp=fp)
        ids["pago"] = pago.id
        review.append({"fecha": _fecha(d), "descripcion": desc, "monto": monto, "tipo": "income", "fingerprint": fp,
                       "estado": "importado", "movimiento_id": pago.id})
        if nuevo_ya:  # la persona ya importó la primera compra como gasto nuevo
            dia, desc, monto = COMPRAS[0]
            n = _mov(db, uid, cuenta, dia, desc, monto, "expense", fp="fp-gasto-nuevo")
            ids["nuevo"] = n.id
            review.append({**_linea_compra(cuenta.id, dia, desc, monto), "fingerprint": "fp-gasto-nuevo",
                           "estado": "importado", "movimiento_id": n.id})
        for k, v in (extra or {}).items():
            ids[k] = v(db, uid, cuenta)
        h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta.id, banco_detectado="nu", estado="conciliado",
                              total_movimientos=len(review), review_json=json.dumps(review), fecha_corte="2026-06-25")
        db.add(h)
        db.flush()
        msg = f"m-{uid}"
        db.add(ExtractoCorreo(usuario_id=uid, gmail_msg_id=msg, archivo="t.pdf", asunto="Extracto de tu tarjeta de crédito",
                              estado="procesado", historial_id=h.id, recibido_en=datetime(2026, 6, 26)))
        LECTURAS[msg] = [_linea_compra(cuenta.id, *c) for c in COMPRAS] + [_linea_pago(cuenta.id)]
        db.commit()
        return {"hid": h.id, "cuenta": cuenta.id, **ids}
    finally:
        db.close()


def _movs(cuenta_id):
    db = SessionLocal()
    try:
        return {m.id: (m.descripcion, m.tipo, m.monto, m.categoria, m.fecha) for m in
                db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta_id).all()}
    finally:
        db.close()


def _saldo(cuenta_id):
    db = SessionLocal()
    try:
        return db.get(Cuenta, cuenta_id).saldo
    finally:
        db.close()


def _revision(hid):
    db = SessionLocal()
    try:
        h = db.get(HistorialExtracto, hid)
        return h.estado, json.loads(h.review_json)
    finally:
        db.close()


def _arreglar():
    limites._eventos.clear()
    return client.post("/conciliacion/tarjetas/arreglar", json={"confirmar": True})


# ── flujo completo «Arreglar mis extractos de la tarjeta» ─────────────────────────────────────────
def test_arreglar_corrige_las_compras_sin_crear_movimientos():
    e = _escena("ct-1")
    antes = _movs(e["cuenta"])
    assert _saldo(e["cuenta"]) == TOTAL_COMPRAS + PAGO[2]  # la tarjeta sale «a favor»: el síntoma

    p = client.get("/conciliacion/tarjetas/arreglar/previa").json()
    assert p["movimientos_a_corregir"] == 4
    c = p["correcciones"]["por_cuenta"][0]
    assert c["n"] == 4 and c["saldo_antes"] == TOTAL_COMPRAS + PAGO[2] and c["saldo_despues"] == -TOTAL_COMPRAS + PAGO[2]
    assert _movs(e["cuenta"]) == antes  # la previa no cambia nada

    j = _arreglar().json()
    assert j["arreglados"] == 1 and j["corregidos"] == 4 and j["por_importar"] == 0
    assert "corregí 4 compras que estaban como ingresos" in j["resumen"]
    despues = _movs(e["cuenta"])
    assert set(despues) == set(antes)  # ningún movimiento nuevo ni borrado
    for dia, desc, monto in COMPRAS:
        assert despues[e[desc]][1] == "expense" and despues[e[desc]][2] == monto and despues[e[desc]][4] == antes[e[desc]][4]
    assert despues[e["pago"]][1] == "income"  # el pago sigue siendo ingreso
    assert _saldo(e["cuenta"]) == -TOTAL_COMPRAS + PAGO[2]  # deuda de compras menos el pago
    estado, review = _revision(e["hid"])
    assert estado == "conciliado" and len(review) == 5
    assert all(i["estado"] == "importado" for i in review)
    assert sum(1 for i in review if i.get("corregido")) == 4

    # idempotente: la segunda vez no hay nada
    j2 = _arreglar().json()
    assert j2["sin_cambios"] and _movs(e["cuenta"]) == despues and _saldo(e["cuenta"]) == -TOTAL_COMPRAS + PAGO[2]


def test_el_saldo_cambia_exactamente_en_el_doble_de_las_compras():
    e = _escena("ct-2")
    antes = _saldo(e["cuenta"])
    _arreglar()
    assert _saldo(e["cuenta"]) == antes - 2 * TOTAL_COMPRAS


def test_releer_solo_propone_y_el_usuario_confirma_en_la_hoja():
    e = _escena("ct-3")
    r = client.post(f"/conciliacion/historial/{e['hid']}/releer")
    assert r.status_code == 200, r.text
    assert r.json()["correcciones"] == 4 and r.json()["por_importar"] == 0
    estado, review = _revision(e["hid"])
    assert estado == "pendiente_revision"
    lineas = [i for i in review if i["estado"] == "corregir_tipo"]
    assert len(lineas) == 4 and all(i["tipo_anterior"] == "income" and i["marcar_por_defecto"] for i in lineas)
    assert all(m[1] == "income" for m in _movs(e["cuenta"]).values())  # nada cambió todavía
    saldo = _saldo(e["cuenta"])
    fps = [i["fingerprint"] for i in lineas]
    j = client.post(f"/conciliacion/historial/{e['hid']}/importar", json={"fingerprints": fps}).json()
    assert j["corregidos"] == 4 and j["importados"] == 0 and j["tipos_corregidos"] == 4
    assert _saldo(e["cuenta"]) == saldo - 2 * TOTAL_COMPRAS
    assert _revision(e["hid"])[0] == "conciliado"
    otra = client.post(f"/conciliacion/historial/{e['hid']}/importar", json={"fingerprints": fps})
    assert otra.json().get("ya_importado") is True and _saldo(e["cuenta"]) == saldo - 2 * TOTAL_COMPRAS


def test_categoria_de_ingreso_se_cambia_pero_la_elegida_se_respeta():
    e = _escena("ct-4")
    db = SessionLocal()
    try:
        a, b = db.get(Movimiento, e[COMPRAS[0][1]]), db.get(Movimiento, e[COMPRAS[1][1]])
        a.categoria, a.cat_confirmada = "Ingresos", True
        b.categoria, b.cat_confirmada = "Comida", True  # la eligió la persona
        db.commit()
    finally:
        db.close()
    client.post(f"/conciliacion/historial/{e['hid']}/releer")
    _, review = _revision(e["hid"])
    for i in review:
        if i["estado"] == "corregir_tipo":
            i["categoria_sugerida"] = "Compras"
    db = SessionLocal()
    try:
        db.get(HistorialExtracto, e["hid"]).review_json = json.dumps(review)
        db.commit()
    finally:
        db.close()
    client.post(f"/conciliacion/historial/{e['hid']}/importar",
                json={"fingerprints": [i["fingerprint"] for i in review if i["estado"] == "corregir_tipo"]})
    m = _movs(e["cuenta"])
    assert m[e[COMPRAS[0][1]]][3] == "Compras"  # era de ingreso: toma la de la línea nueva
    assert m[e[COMPRAS[1][1]]][3] == "Comida"  # la elegida no se pisa
    assert m[e[COMPRAS[2][1]]][3] == "Compras"  # «Otros» tampoco era una elección


# ── ya duplicado ──────────────────────────────────────────────────────────────────────────────────
def test_ingreso_repetido_se_quita_sin_fantasma_y_con_saldo_revertido():
    e = _escena("ct-5", nuevo_ya=True)
    db = SessionLocal()
    try:
        _, review = _revision(e["hid"])
        assert ct.marcar(db, "ct-5", e["cuenta"], review) == 1
        assert ct.marcar(db, "ct-5", e["cuenta"], review) == 0  # idempotente
        viejo = next(i for i in review if i.get("movimiento_id") == e[COMPRAS[0][1]])
        assert viejo["estado"] == "quitar_repetido" and viejo["quita_por"] == "tipo" and viejo["nuevo_movimiento_id"] == e["nuevo"]
        db.get(HistorialExtracto, e["hid"]).review_json = json.dumps(review)
        db.commit()
    finally:
        db.close()
    saldo = _saldo(e["cuenta"])
    j = client.post(f"/conciliacion/historial/{e['hid']}/importar", json={"fingerprints": [viejo["fingerprint"]]}).json()
    assert j["repetidos_quitados"] == 1 and j["importados"] == 0
    movs = _movs(e["cuenta"])
    assert e[COMPRAS[0][1]] not in movs and e["nuevo"] in movs and movs[e["nuevo"]][1] == "expense"
    assert _saldo(e["cuenta"]) == saldo - COMPRAS[0][2]  # se revierte el ingreso falso
    db = SessionLocal()
    try:
        assert db.query(HuellaOrigen).filter(HuellaOrigen.movimiento_id == e[COMPRAS[0][1]]).count() == 0
        assert db.query(HuellaOrigen).filter(HuellaOrigen.usuario_id == "ct-5", HuellaOrigen.estado == dup.ESTADO_DESCARTADO).count() == 0
    finally:
        db.close()


def test_el_ingreso_repetido_no_se_quita_si_la_compra_buena_ya_no_esta():
    e = _escena("ct-5b", nuevo_ya=True)
    db = SessionLocal()
    try:
        _, review = _revision(e["hid"])
        ct.marcar(db, "ct-5b", e["cuenta"], review)
        viejo = next(i for i in review if i.get("quita_por") == "tipo")
        db.delete(db.get(Movimiento, e["nuevo"]))
        db.flush()
        cuenta = db.get(Cuenta, e["cuenta"])
        assert ct.quitar(db, "ct-5b", cuenta, viejo) is False
        assert ct.marcar(db, "ct-5b", e["cuenta"], review) == 0 or viejo["estado"] == "importado"
    finally:
        db.rollback()
        db.close()


# ── seguridad ─────────────────────────────────────────────────────────────────────────────────────
def test_no_toca_manuales_ni_de_correo_ni_pagos():
    def manual(db, uid, cuenta):
        return _mov(db, uid, cuenta, 3, "Mercpago*Tienda Uno", 40000.0, "income", fuente="manual").id

    def correo(db, uid, cuenta):
        return _mov(db, uid, cuenta, 5, "Tienda Dos Titan", 23000.0, "income", fuente="email").id

    e = _escena("ct-6", extra={"manual": manual, "correo": correo})
    db = SessionLocal()
    try:
        # Un review que solo vincula el manual, el de correo y el pago: ninguno se corrige.
        review = [{"fecha": _fecha(3), "descripcion": "Mercpago*Tienda Uno", "monto": 40000.0, "tipo": "income",
                   "fingerprint": "x1", "estado": "importado", "movimiento_id": e["manual"]},
                  {"fecha": _fecha(5), "descripcion": "Tienda Dos Titan", "monto": 23000.0, "tipo": "income",
                   "fingerprint": "x2", "estado": "importado", "movimiento_id": e["correo"]},
                  {"fecha": _fecha(20), "descripcion": PAGO[1], "monto": PAGO[2], "tipo": "income",
                   "fingerprint": "x3", "estado": "importado", "movimiento_id": e["pago"]},
                  {**_linea_compra(e["cuenta"], 3, "Mercpago*Tienda Uno", 40000.0), "fingerprint": "n1", "estado": "faltante"},
                  {**_linea_compra(e["cuenta"], 5, "Tienda Dos Titan", 23000.0), "fingerprint": "n2", "estado": "faltante"},
                  {**_linea_compra(e["cuenta"], 20, PAGO[1], PAGO[2]), "fingerprint": "n3", "estado": "faltante"}]
        assert ct.marcar(db, "ct-6", e["cuenta"], review) == 0
        assert [i["estado"] for i in review[3:]] == ["faltante"] * 3
    finally:
        db.close()


def test_sin_la_marca_del_lector_no_corrige_por_parecido():
    e = _escena("ct-7")
    db = SessionLocal()
    try:
        _, review = _revision(e["hid"])
        nueva = {**_linea_compra(e["cuenta"], *COMPRAS[0]), "fingerprint": "n1", "estado": "faltante"}
        nueva.pop("corrige_tipo")
        review.append(nueva)
        assert ct.marcar(db, "ct-7", e["cuenta"], review) == 0 and nueva["estado"] == "faltante"
        nueva["corrige_tipo"] = {"de": "income", "a": "expense"}
        nueva["linea_tipo"] = "pago"  # un pago nunca es una compra
        assert ct.marcar(db, "ct-7", e["cuenta"], review) == 0
    finally:
        db.close()


def test_no_empareja_otro_monto_ni_otro_dia_ni_otro_comercio_y_es_uno_a_uno():
    e = _escena("ct-8")
    db = SessionLocal()
    try:
        _, review = _revision(e["hid"])
        lejos = {**_linea_compra(e["cuenta"], 8, COMPRAS[0][1], COMPRAS[0][2]), "fingerprint": "a", "estado": "faltante"}
        otro_monto = {**_linea_compra(e["cuenta"], 3, COMPRAS[0][1], COMPRAS[0][2] + 500), "fingerprint": "b", "estado": "faltante"}
        otro_comercio = {**_linea_compra(e["cuenta"], 3, "Zapateria Completamente Distinta", COMPRAS[0][2]),
                         "fingerprint": "c", "estado": "faltante"}
        gemela1 = {**_linea_compra(e["cuenta"], 3, COMPRAS[0][1], COMPRAS[0][2]), "fingerprint": "d", "estado": "faltante"}
        gemela2 = {**_linea_compra(e["cuenta"], 3, COMPRAS[0][1], COMPRAS[0][2]), "fingerprint": "e", "estado": "faltante"}
        review += [lejos, otro_monto, otro_comercio, gemela1, gemela2]
        ct.marcar(db, "ct-8", e["cuenta"], review)
        assert [x["estado"] for x in (lejos, otro_monto, otro_comercio)] == ["faltante"] * 3
        assert sorted([gemela1["estado"], gemela2["estado"]]) == ["corregir_tipo", "faltante"]  # un ingreso corrige una sola
    finally:
        db.close()


def test_aislamiento_un_movimiento_de_otra_persona_no_se_corrige():
    otro = _escena("ct-9b")
    e = _escena("ct-9")
    db = SessionLocal()
    try:
        linea = {**_linea_compra(e["cuenta"], *COMPRAS[0]), "fingerprint": "z", "estado": "corregir_tipo",
                 "corrige_movimiento_id": otro[COMPRAS[0][1]]}
        cuenta = db.get(Cuenta, e["cuenta"])
        assert ct.corregir(db, "ct-9", cuenta, e["hid"], linea, None) is None
    finally:
        db.close()
    assert _movs(otro["cuenta"])[otro[COMPRAS[0][1]]][1] == "income"


def test_recalcula_el_ajuste_inicial(monkeypatch):
    e = _escena("ct-10")
    llamadas = []
    monkeypatch.setattr(saldo_inicial_auto, "registrar", lambda db, cuenta, inicio=None: llamadas.append(cuenta.id))
    _arreglar()
    assert llamadas == [e["cuenta"]]


def test_conteo_cuenta_la_correccion_de_tipo():
    from app import estado_traer as et
    c = et.contar_review([{"estado": "corregir_tipo"}, {"estado": "importado"}])
    assert c["correcciones"] == 1 and c["por_revisar"] == 1
