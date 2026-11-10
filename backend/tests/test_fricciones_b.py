"""Fricción B: la app resuelve sola lo SEGURO (siempre con «Deshacer») y, ante la duda, no hace nada.

  1. Traslados exactos 1:1 entre cuentas propias se marcan solos; ambiguos o con comisión siguen preguntando.
  2. Descuadre con UNA causa exacta (línea que falta / copia repetida / extracto de otra cuenta) se arregla si el mes cierra en 0.
  3. Un sobrante que está como línea en el extracto de OTRA cuenta tuya pasa a esa cuenta.
  4. Varias tarjetas del mismo banco: los últimos 4 dígitos del PDF desempatan si coinciden con UNA.
Datos 100 % inventados."""
import json
import os
import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'friccionb.db')}")

import pytest  # noqa: E402

from app import autoarreglo as aa  # noqa: E402
from app import limites  # noqa: E402
from app import reasignar_extracto as ra  # noqa: E402
from app.contabilidad import MARCA_ES_TRASLADO  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402,F401  (registra todos los modelos)
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento, Perfil  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

Base.metadata.create_all(bind=engine)

AHORA = ahora_co().replace(hour=12, minute=0, second=0, microsecond=0)


@pytest.fixture(autouse=True)
def _limpio():
    limites._eventos.clear()
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _usuario(db, uid, cuentas):
    db.add(Perfil(usuario_id=uid, plan="free"))
    out = {}
    for nombre, saldo, *resto in cuentas:
        c = Cuenta(usuario_id=uid, nombre=nombre, tipo=(resto[0] if resto else "ahorro"), saldo=saldo)
        db.add(c)
        db.flush()
        out[nombre] = c
    db.commit()
    return out


def _mov(db, cuenta, tipo, monto, fecha, desc="Movimiento", fuente="manual", conciliado=False, notas=""):
    m = Movimiento(usuario_id=cuenta.usuario_id, cuenta_id=cuenta.id, tipo=tipo, monto=monto, fecha=fecha, descripcion=desc,
                   categoria="Otros", fuente=fuente, notas=notas, conciliado_en=AHORA if conciliado else None)
    db.add(m)
    db.commit()
    return m


def _correr(db, uid):
    r = aa.correr(db, uid, 3, usuario=SimpleNamespace(id=uid, email="", nombre="Persona Prueba", nombre_pila=""))
    assert not r.get("error"), r
    return r


def _deshacer(db, uid, r):
    assert r["lote_id"], r
    out = aa.deshacer_lote(db, uid, r["lote_id"])
    assert out["ok"]
    db.expire_all()


# ═══════════════════════════ 1. Traslados ═══════════════════════════
def test_par_exacto_unico_se_marca_solo_y_se_deshace(db):
    uid = "fb-t1"
    c = _usuario(db, uid, [("Bancolombia", 900_000), ("Nequi", 100_000)])
    g = _mov(db, c["Bancolombia"], "expense", 100_000, AHORA - timedelta(days=3), "Compra libreria")
    i = _mov(db, c["Nequi"], "income", 100_000, AHORA - timedelta(days=3, hours=-4), "Abono cliente")
    r = _correr(db, uid)
    db.expire_all()
    assert MARCA_ES_TRASLADO in db.get(Movimiento, g.id).notas and MARCA_ES_TRASLADO in db.get(Movimiento, i.id).notas
    assert "marqué 1 traslado entre tus cuentas" in r["resumen"]["texto"]
    _deshacer(db, uid, r)
    assert MARCA_ES_TRASLADO not in (db.get(Movimiento, g.id).notas or "")
    assert MARCA_ES_TRASLADO not in (db.get(Movimiento, i.id).notas or "")


def test_dos_pagos_reales_identicos_no_se_marcan_como_traslado(db):
    uid = "fb-t2"
    c = _usuario(db, uid, [("Bancolombia", 900_000), ("Nequi", 100_000)])
    dia = AHORA - timedelta(days=2)
    a = _mov(db, c["Bancolombia"], "expense", 50_000, dia, "Pago uno")
    b = _mov(db, c["Bancolombia"], "expense", 50_000, dia + timedelta(hours=1), "Pago dos")
    i = _mov(db, c["Nequi"], "income", 50_000, dia, "Abono cliente")
    _correr(db, uid)
    db.expire_all()
    for m in (a, b, i):
        assert MARCA_ES_TRASLADO not in (db.get(Movimiento, m.id).notas or "")


def test_dos_ingresos_identicos_para_un_egreso_es_ambiguo(db):
    uid = "fb-t3"
    c = _usuario(db, uid, [("Bancolombia", 900_000), ("Nequi", 100_000), ("Nu", 0)])
    dia = AHORA - timedelta(days=2)
    g = _mov(db, c["Bancolombia"], "expense", 70_000, dia, "Compra libreria")
    i1 = _mov(db, c["Nequi"], "income", 70_000, dia, "Abono cliente")
    i2 = _mov(db, c["Nu"], "income", 70_000, dia, "Abono cliente dos")
    _correr(db, uid)
    db.expire_all()
    for m in (g, i1, i2):
        assert MARCA_ES_TRASLADO not in (db.get(Movimiento, m.id).notas or "")


def test_par_con_comision_o_misma_cuenta_o_fuera_de_ventana_no_se_marca(db):
    uid = "fb-t4"
    c = _usuario(db, uid, [("Bancolombia", 900_000), ("Nequi", 100_000)])
    dia = AHORA - timedelta(days=10)
    con_comision = (_mov(db, c["Bancolombia"], "expense", 100_000, dia, "Compra uno"), _mov(db, c["Nequi"], "income", 99_500, dia, "Abono uno"))
    misma = (_mov(db, c["Nequi"], "expense", 30_000, dia, "Compra dos"), _mov(db, c["Nequi"], "income", 30_000, dia, "Abono dos"))
    lejos = (_mov(db, c["Bancolombia"], "expense", 45_000, dia, "Compra tres"),
             _mov(db, c["Nequi"], "income", 45_000, dia + timedelta(days=5), "Abono tres"))
    _correr(db, uid)
    db.expire_all()
    for m in (*con_comision, *misma, *lejos):
        assert MARCA_ES_TRASLADO not in (db.get(Movimiento, m.id).notas or "")


# ═══════════════════ 2. Cuadre con UNA causa exacta ═══════════════════
def _extracto(db, cuenta, review, saldo_final, saldo_inicial=0.0, estado="pendiente_revision"):
    h = HistorialExtracto(usuario_id=cuenta.usuario_id, cuenta_id=cuenta.id, banco_detectado="bancolombia", estado=estado,
                          total_movimientos=len(review), review_json=json.dumps(review), fecha_corte="2026-08-31",
                          periodo_inicio="2026-08-01", saldo_inicial_extracto=saldo_inicial, saldo_final_extracto=saldo_final,
                          saldos_origen="extracto")
    db.add(h)
    db.commit()
    return h


def _linea(fp, dia, desc, monto, tipo, estado="exacto", **extra):
    return {"fecha": f"2026-08-{dia:02d}", "descripcion": desc, "monto": monto, "tipo": tipo, "fingerprint": fp, "estado": estado,
            "categoria_sugerida": "Otros", **extra}


def _ago(dia, hora=12):
    return datetime(2026, 8, dia, hora)


def _cuadra_agosto(db, cuenta, h_id):
    from app import cuadre_encadenado as ce

    r = ce.calcular(db, cuenta, None)
    f = next(x for x in r["meses"] if x.get("historial_id") == h_id)
    return abs(f["diferencia"]) < ce.TOL, f


def test_copia_repetida_de_otra_fuente_se_quita_sola_y_se_deshace(db):
    uid = "fb-c1"
    c = _usuario(db, uid, [("Bancolombia", 400_000)])
    cta = c["Bancolombia"]
    _mov(db, cta, "income", 500_000, _ago(5), "Abono cliente", fuente="conciliacion_extracto", conciliado=True)
    sobra = _mov(db, cta, "income", 500_000, _ago(5, 9), "Abono cliente (correo)", fuente="email")
    _mov(db, cta, "expense", 100_000, _ago(9), "Compra", fuente="conciliacion_extracto", conciliado=True)
    cta.saldo = 900_000  # lo que suma la app con la copia
    db.commit()
    h = _extracto(db, cta, [_linea("a", 5, "Abono cliente", 500_000, "income"), _linea("b", 9, "Compra", 100_000, "expense")], 400_000)
    assert _cuadra_agosto(db, cta, h.id)[0] is False
    r = _correr(db, uid)
    db.expire_all()
    assert db.get(Movimiento, sobra.id) is None
    assert _cuadra_agosto(db, db.get(Cuenta, cta.id), h.id)[0] is True
    assert "quité 1 movimiento repetido" in r["resumen"]["texto"]
    _deshacer(db, uid, r)
    assert db.get(Movimiento, sobra.id) is not None


def test_dos_pagos_identicos_de_la_misma_fuente_no_se_quitan(db):
    uid = "fb-c2"
    c = _usuario(db, uid, [("Bancolombia", 900_000)])
    cta = c["Bancolombia"]
    a = _mov(db, cta, "income", 500_000, _ago(5), "Abono cliente", fuente="email")
    b = _mov(db, cta, "income", 500_000, _ago(5, 9), "Abono cliente", fuente="email")
    _mov(db, cta, "expense", 100_000, _ago(9), "Compra", fuente="conciliacion_extracto", conciliado=True)
    _extracto(db, cta, [_linea("b", 9, "Compra", 100_000, "expense")], 400_000)
    _correr(db, uid)
    db.expire_all()
    assert db.get(Movimiento, a.id) is not None and db.get(Movimiento, b.id) is not None


def test_copia_sin_nada_respaldado_no_se_quita(db):
    uid = "fb-c3"
    c = _usuario(db, uid, [("Bancolombia", 900_000)])
    cta = c["Bancolombia"]
    a = _mov(db, cta, "income", 500_000, _ago(5), "Abono a mano", fuente="manual")
    b = _mov(db, cta, "income", 500_000, _ago(5, 9), "Abono correo", fuente="email")
    _mov(db, cta, "expense", 100_000, _ago(9), "Compra", fuente="conciliacion_extracto", conciliado=True)
    _extracto(db, cta, [_linea("b", 9, "Compra", 100_000, "expense")], 400_000)
    _correr(db, uid)
    db.expire_all()
    assert db.get(Movimiento, a.id) is not None and db.get(Movimiento, b.id) is not None


def test_linea_unica_que_falta_se_importa_si_cierra_en_cero_y_se_deshace(db):
    uid = "fb-c4"
    c = _usuario(db, uid, [("Bancolombia", 500_000)])
    cta = c["Bancolombia"]
    _mov(db, cta, "income", 500_000, _ago(5), "Abono cliente", fuente="conciliacion_extracto", conciliado=True)
    h = _extracto(db, cta, [_linea("a", 5, "Abono cliente", 500_000, "income"),
                            _linea("falta", 12, "Compra Tienda", 30_000, "expense", estado="faltante")], 470_000)
    assert _cuadra_agosto(db, cta, h.id)[0] is False
    r = _correr(db, uid)
    db.expire_all()
    assert _cuadra_agosto(db, db.get(Cuenta, cta.id), h.id)[0] is True
    assert db.query(Movimiento).filter(Movimiento.cuenta_id == cta.id).count() == 2
    _deshacer(db, uid, r)
    assert db.query(Movimiento).filter(Movimiento.cuenta_id == cta.id).count() == 1


def test_dos_lineas_que_faltan_o_causa_que_no_cierra_no_se_tocan(db):
    uid = "fb-c5"
    c = _usuario(db, uid, [("Bancolombia", 500_000)])
    cta = c["Bancolombia"]
    _mov(db, cta, "income", 500_000, _ago(5), "Abono cliente", fuente="conciliacion_extracto", conciliado=True)
    _extracto(db, cta, [_linea("a", 5, "Abono cliente", 500_000, "income"),
                        _linea("f1", 12, "Compra Uno", 30_000, "expense", estado="faltante"),
                        _linea("f2", 13, "Compra Dos", 30_000, "expense", estado="faltante")], 470_000)
    _correr(db, uid)
    db.expire_all()
    assert db.query(Movimiento).filter(Movimiento.cuenta_id == cta.id).count() == 1


def test_extracto_de_otra_cuenta_se_pasa_si_es_la_unica_candidata(db):
    uid = "fb-c6"
    c = _usuario(db, uid, [("Cuenta A", 0), ("Cuenta B", 250_000)])
    a, b = c["Cuenta A"], c["Cuenta B"]
    _mov(db, a, "expense", 40_000, _ago(7), "Cosa de A")
    a.saldo = -40_000
    _mov(db, b, "income", 250_000, _ago(10), "Abono de B")
    h = _extracto(db, a, [_linea("x", 10, "Abono de B", 250_000, "income", estado="faltante", lectura_dudosa=True)], 250_000)
    r = _correr(db, uid)
    db.expire_all()
    assert db.get(HistorialExtracto, h.id).cuenta_id == b.id
    assert _cuadra_agosto(db, db.get(Cuenta, b.id), h.id)[0] is True
    _deshacer(db, uid, r)
    assert db.get(HistorialExtracto, h.id).cuenta_id == a.id


def test_extracto_de_otra_cuenta_con_dos_candidatas_no_se_mueve(db):
    uid = "fb-c7"
    c = _usuario(db, uid, [("Cuenta A", 0), ("Cuenta B", 250_000), ("Cuenta C", 250_000)])
    a = c["Cuenta A"]
    _mov(db, a, "expense", 40_000, _ago(7), "Cosa de A")
    _mov(db, c["Cuenta B"], "income", 250_000, _ago(10), "Abono de B")
    _mov(db, c["Cuenta C"], "income", 250_000, _ago(11), "Abono de C")
    h = _extracto(db, a, [_linea("x", 10, "Abono", 250_000, "income", estado="faltante", lectura_dudosa=True)], 250_000)
    _correr(db, uid)
    db.expire_all()
    assert db.get(HistorialExtracto, h.id).cuenta_id == a.id


# ═══════════════════════════ 3. Sobrantes ═══════════════════════════
def _mundo_sobrante(db, uid, *, extra_destino=0):
    c = _usuario(db, uid, [("Nequi", 920_000), ("Bancolombia", 500_000)] + ([("Nu", 100_000)] if extra_destino else []))
    nequi, banco = c["Nequi"], c["Bancolombia"]
    ap = _mov(db, nequi, "expense", 80_000, _ago(14), "Apple Pay Spotify", fuente="apple_pay")
    h_n = _extracto(db, nequi, [{"fecha": "2026-08-14", "descripcion": "Apple Pay Spotify", "monto": 80_000.0, "tipo": "expense",
                                 "fingerprint": f"sobrante-{ap.id}", "estado": "sobrante", "match_id": ap.id}], None)
    h_b = _extracto(db, banco, [_linea("spot", 14, "Spotify", 80_000.0, "expense", estado="faltante")], None)
    if extra_destino:
        _extracto(db, c["Nu"], [_linea("spot2", 15, "Spotify", 80_000.0, "expense", estado="faltante")], None)
    return c, ap, h_n, h_b


def test_sobrante_que_esta_en_el_extracto_de_otra_cuenta_se_mueve_y_se_deshace(db):
    uid = "fb-s1"
    c, ap, h_n, h_b = _mundo_sobrante(db, uid)
    r = _correr(db, uid)
    db.expire_all()
    m = db.get(Movimiento, ap.id)
    assert m.cuenta_id == c["Bancolombia"].id and m.conciliado_en is not None
    assert round(db.get(Cuenta, c["Bancolombia"].id).saldo) == 420_000
    ni = json.loads(db.get(HistorialExtracto, h_n.id).review_json)[0]
    assert ni["estado"] == "sobrante_resuelto" and ni["resuelto"] == "movido"
    assert json.loads(db.get(HistorialExtracto, h_b.id).review_json)[0]["estado"] == "completado"
    assert "pasé 1 movimiento a la cuenta donde está en tu extracto" in r["resumen"]["texto"]
    _deshacer(db, uid, r)
    m = db.get(Movimiento, ap.id)
    assert m.cuenta_id == c["Nequi"].id and m.conciliado_en is None
    assert round(db.get(Cuenta, c["Bancolombia"].id).saldo) == 500_000
    assert json.loads(db.get(HistorialExtracto, h_n.id).review_json)[0]["estado"] == "sobrante"
    assert json.loads(db.get(HistorialExtracto, h_b.id).review_json)[0]["estado"] == "faltante"


def test_sobrante_con_dos_cuentas_candidatas_no_se_mueve(db):
    uid = "fb-s2"
    c, ap, *_ = _mundo_sobrante(db, uid, extra_destino=1)
    _correr(db, uid)
    db.expire_all()
    assert db.get(Movimiento, ap.id).cuenta_id == c["Nequi"].id


def test_sobrante_conciliado_o_con_gemelo_o_con_igual_en_destino_no_se_mueve(db):
    # conciliado con otro extracto
    uid = "fb-s3"
    c, ap, *_ = _mundo_sobrante(db, uid)
    ap.conciliado_en = AHORA
    db.commit()
    _correr(db, uid)
    db.expire_all()
    assert db.get(Movimiento, ap.id).cuenta_id == c["Nequi"].id
    # dos pagos idénticos en la cuenta de origen
    uid = "fb-s4"
    c, ap, *_ = _mundo_sobrante(db, uid)
    _mov(db, c["Nequi"], "expense", 80_000, _ago(14, 18), "Spotify otra vez")
    _correr(db, uid)
    db.expire_all()
    assert db.get(Movimiento, ap.id).cuenta_id == c["Nequi"].id
    # el destino ya tiene un movimiento igual (sería un repetido, no un error de cuenta)
    uid = "fb-s5"
    c, ap, *_ = _mundo_sobrante(db, uid)
    _mov(db, c["Bancolombia"], "expense", 80_000, _ago(14, 20), "Spotify en banco")
    _correr(db, uid)
    db.expire_all()
    assert db.get(Movimiento, ap.id).cuenta_id == c["Nequi"].id
    # monto distinto (más de $1)
    uid = "fb-s6"
    c, ap, h_n, h_b = _mundo_sobrante(db, uid)
    rev = json.loads(h_b.review_json)
    rev[0]["monto"] = 80_500.0
    h_b.review_json = json.dumps(rev)
    db.commit()
    _correr(db, uid)
    db.expire_all()
    assert db.get(Movimiento, ap.id).cuenta_id == c["Nequi"].id


# ═══════════════════════ 4. Varias tarjetas: últimos 4 dígitos ═══════════════════════
def _tarjetas(db, uid, u4_extracto):
    c = _usuario(db, uid, [("Nu Colombia", 0), ("Nu Colombia Crédito 1234", 0, "credito"), ("Nu Colombia Crédito 5678", 0, "credito")])
    h = HistorialExtracto(usuario_id=uid, cuenta_id=c["Nu Colombia"].id, banco_detectado="nu", estado="conciliado", review_json="[]",
                          lectura_json=json.dumps({"ultimos4": u4_extracto}) if u4_extracto else None)
    db.add(h)
    db.flush()
    db.add(ExtractoCorreo(usuario_id=uid, gmail_msg_id=f"m-{uid}", archivo="extracto.pdf", asunto="Extracto de tu tarjeta de crédito",
                          estado="procesado", historial_id=h.id, recibido_en=datetime(2026, 8, 26)))
    db.commit()
    return c, h


def test_ultimos4_desempatan_solo_si_coinciden_con_una_tarjeta(db):
    c, h = _tarjetas(db, "fb-u1", "5678")
    cuentas = list(c.values())
    s = ra.sugerir_cuenta_credito(h, c["Nu Colombia"], cuentas, "tarjeta de credito")
    assert s and s["cuenta_id"] == c["Nu Colombia Crédito 5678"].id
    for u4 in ("9999", "", None):  # ninguna coincide, o no hay dígitos: sigue ambiguo
        c2, h2 = _tarjetas(db, f"fb-u2{u4}", u4)
        assert ra.sugerir_cuenta_credito(h2, c2["Nu Colombia"], list(c2.values()), "tarjeta de credito") is None


def test_desempate_lee_los_digitos_del_pdf_y_los_guarda(db, monkeypatch):
    uid = "fb-u3"
    c, h = _tarjetas(db, uid, None)
    monkeypatch.setattr(aa, "_texto_del_pdf", lambda *a, **k: "Tu tarjeta terminada en 5678 ...")
    ctx = aa._Ctx(db, SimpleNamespace(id=uid, email="", nombre="", nombre_pila=""), "lote-x", 3)
    assert aa._desempatar_tarjetas(ctx) == 1
    db.expire_all()
    assert json.loads(db.get(HistorialExtracto, h.id).lectura_json)["ultimos4"] == "5678"
    # PDF sin dígitos: no se guarda nada y no se vuelve a descargar de inmediato
    uid = "fb-u4"
    c, h = _tarjetas(db, uid, None)
    monkeypatch.setattr(aa, "_texto_del_pdf", lambda *a, **k: "Tu tarjeta de crédito")
    ctx = aa._Ctx(db, SimpleNamespace(id=uid, email="", nombre="", nombre_pila=""), "lote-y", 3)
    assert aa._desempatar_tarjetas(ctx) == 0
    db.expire_all()
    assert not db.get(HistorialExtracto, h.id).lectura_json
