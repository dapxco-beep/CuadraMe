"""El autoarreglo no se inanicia: 4 extractos de tarjeta que NO verifican no pueden dejar sin lecturas a los ajustes de ahorros
(4x1000, rendimientos, costos por retiro) ni a las correcciones de tipo. Datos 100 % inventados (mismo mundo que test_autoarreglo).

Antes: cada llamada tenía 3 lecturas de Gmail y las tarjetas se las gastaban todas; los pasos siguientes recibían 0.
Ahora: la verificación se cachea por (extracto, versión del lector), las tarjetas dejan una lectura a los ajustes y lo que
midió un lector anterior se vuelve a medir una sola vez."""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'sin_inanicion.db')}")

import pytest  # noqa: E402

from app import autoarreglo as aa  # noqa: E402
from app.crons import MarcaCron  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento  # noqa: E402
from tests.test_autoarreglo import (  # noqa: E402  # noqa: F401  (el fixture simulado de Gmail y el lector se reutilizan)
    DUDOSOS, AHORRO_FINAL, _simulado, _tarjeta_en, correr_todo, foto, mundo,
)


def _llamar(uid, max_pasos=3):
    db = SessionLocal()
    try:
        return aa.correr(db, uid, max_pasos)
    finally:
        db.close()


def _agregar_tarjetas_que_no_verifican(uid, ids, meses=(2, 3, 4, 5)):
    """4 extractos de tarjeta más, en la tarjeta, cuya lectura de hoy NO cuadra con su resumen (como los formatos viejos)."""
    db = SessionLocal()
    try:
        credito = db.get(Cuenta, ids["credito"])
        for mes in meses:
            _tarjeta_en(db, uid, credito, credito.id, mes, [(2, f"Tienda Vieja {mes}", 5_000.0)])
            DUDOSOS.add(f"m-{uid}-tarjeta-{mes}")
        db.commit()
    finally:
        db.close()


def _categorias(ids):
    db = SessionLocal()
    try:
        return {m.categoria for m in db.query(Movimiento).filter(Movimiento.cuenta_id == ids["ahorro"])}
    finally:
        db.close()


def _marcas_sv(uid):
    db = SessionLocal()
    try:
        return {m.clave: m.valor for m in db.query(MarcaCron).filter(MarcaCron.usuario_id == uid, MarcaCron.clave.like(aa.PREFIJO_SV + "%"))}
    finally:
        db.close()


def test_la_primera_llamada_ya_registra_ajustes_aunque_haya_cuatro_tarjetas_sin_verificar(monkeypatch):
    uid = "ai-1"
    ids = mundo(uid, monkeypatch)
    _agregar_tarjetas_que_no_verifican(uid, ids)
    assert not ({"Rendimientos", "4x1000 (GMF)"} & _categorias(ids))
    r = _llamar(uid, 3)
    assert "Rendimientos" in _categorias(ids) or "4x1000 (GMF)" in _categorias(ids), "la 1.ª llamada debe avanzar los ajustes de ahorros"
    ajustes = next(p for p in r["pasos"] if p["paso"] == "ajustes")
    assert ajustes["estado"] == "ok" and ajustes["hecho"] >= 1


def test_converge_en_pocas_llamadas_con_todo_corregido_y_lo_que_no_verifica_no_bloquea_a_los_demas(monkeypatch):
    uid = "ai-2"
    ids = mundo(uid, monkeypatch)
    _agregar_tarjetas_que_no_verifican(uid, ids)
    r, llamadas = correr_todo(uid, max_pasos=3, rondas=8)
    assert r["estado"] == "listo" and llamadas <= 5, f"tardó {llamadas} llamadas"
    despues = foto(uid)
    assert despues["cuentas"]["Nu Colombia"] == pytest.approx(AHORRO_FINAL)  # 4x1000, rendimientos y costos registrados
    assert {"Rendimientos", "4x1000 (GMF)", "Comisiones y seguros"} <= _categorias(ids)
    db = SessionLocal()
    try:  # las compras viejas de julio y agosto (leídas como ingreso) ya son gasto
        assert db.query(Movimiento).filter(Movimiento.cuenta_id == ids["credito"], Movimiento.descripcion.like("Tienda Un%"),
                                           Movimiento.tipo == "income").count() == 0
        # los 4 extractos que no verifican quedaron intactos
        for mes in (2, 3, 4, 5):
            h = db.query(HistorialExtracto).join(ExtractoCorreo, ExtractoCorreo.historial_id == HistorialExtracto.id).filter(
                ExtractoCorreo.gmail_msg_id == f"m-{uid}-tarjeta-{mes}").one()
            assert [i["estado"] for i in json.loads(h.review_json)] == ["importado"] and h.lectura_json is None
    finally:
        db.close()
    assert next(d for d in r["decisiones"] if d["tipo"] == "tarjeta_sin_verificar")["cantidad"] >= 4  # decisión clara para la persona


def test_la_verificacion_se_guarda_y_no_se_vuelve_a_descargar(monkeypatch):
    uid = "ai-3"
    ids = mundo(uid, monkeypatch)
    _agregar_tarjetas_que_no_verifican(uid, ids)
    correr_todo(uid, max_pasos=3, rondas=8)
    marcas = _marcas_sv(uid)
    assert len(marcas) >= 4 and all(v.startswith(aa.rx.VERSION_LECTOR + "|") for v in marcas.values())
    assert sum(1 for v in marcas.values() if "|falso|" in v) >= 4  # «no suma» se recuerda para esta versión del lector
    descargas = []
    original = aa._lectura_del_pdf
    monkeypatch.setattr(aa, "_lectura_del_pdf", lambda *a, **k: descargas.append(1) or original(*a, **k))
    for _ in range(2):
        _llamar(uid, 3)
    assert descargas == [], "con la verificación en caché no se baja ningún PDF más"


def test_un_resultado_nulo_se_reintenta_pasado_un_rato_y_uno_falso_no():
    from datetime import datetime, timedelta

    ahora = datetime.utcnow()
    v = aa.rx.VERSION_LECTOR
    assert aa._marca_sv_vigente(v)  # marca de versiones anteriores del código: cuenta como falso
    assert aa._marca_sv_vigente(f"{v}|falso|{(ahora - timedelta(days=30)).isoformat()}")
    assert aa._marca_sv_vigente(f"{v}|nulo|{ahora.isoformat()}")
    assert not aa._marca_sv_vigente(f"{v}|nulo|{(ahora - timedelta(hours=7)).isoformat()}")
    assert not aa._marca_sv_vigente("2020-vieja|falso|" + ahora.isoformat())


def test_lo_que_midio_un_lector_anterior_como_no_cuadra_se_vuelve_a_medir_una_vez(monkeypatch):
    """Un extracto de tarjeta con lectura_completa=False guardada por el lector viejo se re-mide con el de hoy: si ahora
    verifica, se corrige; si no, queda en caché y no se vuelve a bajar."""
    uid = "ai-4"
    ids = mundo(uid, monkeypatch, tarjeta_extra=True)
    db = SessionLocal()
    try:
        h = db.get(HistorialExtracto, ids["tarjeta_dudosa"])
        h.lectura_json = json.dumps({"lectura_completa": False, "lineas_leidas": 1, "mensaje_lectura": "x"})
        db.commit()
    finally:
        db.close()
    DUDOSOS.discard(f"m-{uid}-tarjeta-9")  # el lector de hoy SÍ lo verifica
    r, _ = correr_todo(uid, max_pasos=3, rondas=8)
    db = SessionLocal()
    try:
        h = db.get(HistorialExtracto, ids["tarjeta_dudosa"])
        assert h.lectura_completa is True  # se re-midió y se actualizó
    finally:
        db.close()
    assert r["estado"] == "listo"


def test_el_paso_de_errores_devuelve_las_lecturas_que_no_uso(monkeypatch):
    """Si reintentó menos de las que reservó, el resto vuelve al presupuesto: antes reservaba las 3 de la llamada aunque no
    leyera ninguna y las tarjetas se quedaban sin lecturas (en la cuenta real no se movía nada)."""
    from types import SimpleNamespace

    from app import autoarreglo as aa

    class _Q:
        def filter(self, *a, **k):
            return self

        def count(self):
            return 4

        def first(self):
            return ("hay clave",)

    ctx = SimpleNamespace(db=SimpleNamespace(query=lambda *a, **k: _Q()), uid="u", usuario=SimpleNamespace(id="u"), unidades=0,
                          presupuesto=3, decisiones={}, cerrar_fase=lambda paso: 0, sin_tiempo=lambda: False,
                          limite_alcanzado=False)

    def reservar(n=1, *, dejar=0):
        dadas = min(n, ctx.presupuesto - dejar)
        ctx.presupuesto -= dadas
        return dadas

    ctx.reservar = reservar
    monkeypatch.setattr("app.extractos_error.reintentar_errores_clave",
                        lambda db, usuario, maximo: {"reintentados": 1, "leidos": 1, "pendientes": 3})
    r = aa._paso_errores(ctx)
    assert r["reintentados"] == 1
    assert ctx.presupuesto == 2  # usó 1 de 3: quedan 2 para las tarjetas y los ajustes


def test_una_linea_no_se_traga_un_movimiento_que_ya_vino_de_otro_extracto_con_otro_comercio():
    from datetime import datetime

    from app import conciliacion as cc

    ledger = [{"id": "uber", "fecha": datetime(2025, 10, 30), "monto": 24934.0, "tipo": "expense", "descripcion": "Compra en UBER RIDES con tarjeta débito",
               "fingerprint": "otra", "rapido": False, "conciliado": False, "extracto_id": "oct", "origen": None, "canales": set(), "emparejable": True}]
    linea = {"fecha": "2025-11-01", "monto": 23800.0, "tipo": "expense", "descripcion": "Compra en TJV ZONA T con tarjeta débito"}
    r = cc._auditar_con_cruce_rapido([linea], ledger)
    assert r["review"][0]["estado"] == "faltante"
    ledger[0]["descripcion"] = "Compra en TJV ZONA T con tarjeta débito"  # mismo comercio: sí se reconoce
    assert cc._auditar_con_cruce_rapido([linea], ledger)["review"][0]["estado"] in ("aproximado", "completado")


def test_el_pago_de_tarjeta_con_desglose_es_elegible_y_otra_cosa_con_desglose_no():
    from app import autoarreglo as aa

    pago = {"estado": "faltante", "tipo": "income", "monto": 170000.0, "fingerprint": "f", "fecha": "2026-04-20", "pago_tarjeta": True,
            "pago_detalle": {"capital": 170000.0, "intereses": 0.0, "cargos": 0.0}}
    assert aa._elegible(pago, None) is True
    assert aa._elegible({**pago, "pago_tarjeta": False}, None) is False
    assert aa._elegible({**pago, "aviso_linea": "revisa"}, None) is False


def test_el_barrido_quita_el_ingreso_falso_con_su_compra_buena_y_el_pago_repetido_pero_deja_lo_demas(monkeypatch):
    from app import ingresos_sueltos
    from tests.test_autoarreglo import _mov

    uid = "ai-barrido"
    ids = mundo(uid, monkeypatch)
    db = SessionLocal()
    try:
        c = db.get(Cuenta, ids["credito"])
        for m in db.query(Movimiento).filter(Movimiento.cuenta_id == c.id).all():
            db.delete(m)
        c.saldo = 0.0
        db.commit()
        falso = _mov(db, uid, c, 8, 10, "Comercio Alfa", 40_000.0, "income", "Comida")
        buena = _mov(db, uid, c, 8, 10, "Comercio Alfa", 40_000.0, "expense", "Comida")
        falso2 = _mov(db, uid, c, 8, 11, "Mercpago*Pando", 50_000.0, "income", "Hogar")  # «Mercpago» contiene «pago» y no es un pago
        buena2 = _mov(db, uid, c, 8, 11, "Mercpago*Pandora", 50_000.0, "expense", "Otros")
        sola = _mov(db, uid, c, 8, 12, "Comercio Beta", 15_000.0, "income", "Comida")  # sin compra buena: se queda
        pago = _mov(db, uid, c, 8, 20, "Pago de tu tarjeta", 90_000.0, "income", "Pago de tarjeta")
        repetido = _mov(db, uid, c, 8, 20, "2026 Pago", 90_000.0, "income", "Otros")
        residuo = _mov(db, uid, c, 8, 14, "2026", 14.0, "expense", "Otros")
        mal_pago = _mov(db, uid, c, 7, 2, "Pago", 70_000.0, "expense", "Pago de tarjeta")
        for m in (falso, buena, falso2, buena2, sola, pago, repetido, residuo):
            m.fuente = "conciliacion_extracto"
        db.flush()
        ids_ = {n: m.id for n, m in dict(falso=falso, buena=buena, falso2=falso2, buena2=buena2, sola=sola, pago=pago, repetido=repetido).items()}
        db.commit()
        r = ingresos_sueltos.barrer(db, uid, c)
        db.commit()
        vivos = {n for n, i in ids_.items() if db.get(Movimiento, i) is not None}
        assert r == {"ingresos_falsos": 2, "pagos_repetidos": 1, "residuos": 1, "retipados": 0, "pagos_corregidos": 1, "reabiertos": 0, "pagos_fuera": 0}
        assert vivos == {"buena", "buena2", "sola", "pago"} and db.get(Movimiento, residuo.id) is None and db.get(Movimiento, mal_pago.id).tipo == "income"
        # la segunda pasada no cambia nada
        assert ingresos_sueltos.barrer(db, uid, c) == {"ingresos_falsos": 0, "pagos_repetidos": 0, "residuos": 0, "retipados": 0, "pagos_corregidos": 0, "reabiertos": 0, "pagos_fuera": 0}
    finally:
        db.close()


def test_reabrir_pago_huerfano_solo_si_no_hay_otro_igual_en_la_tarjeta(monkeypatch):
    from app import ingresos_sueltos

    uid = "ai-reabrir"
    ids = mundo(uid, monkeypatch)
    db = SessionLocal()
    try:
        c = db.get(Cuenta, ids["credito"])
        review = [
            {"fecha": "2026-07-02", "descripcion": "Pago", "monto": 501_713.13, "tipo": "income", "estado": "completado", "match_id": "otra-cuenta", "fingerprint": "a"},
            {"fecha": "2026-07-20", "descripcion": "Pago", "monto": 90_000.0, "tipo": "income", "estado": "importado", "movimiento_id": "borrado", "fingerprint": "b"},
            {"fecha": "2026-07-10", "descripcion": "Mercpago*Pando", "monto": 5_000.0, "tipo": "income", "estado": "exacto", "fingerprint": "c"},
        ]
        h = HistorialExtracto(usuario_id=uid, cuenta_id=c.id, banco_detectado="nu", estado="conciliado", total_movimientos=3, importados=3,
                              review_json=json.dumps(review))
        db.add(h)
        db.add(Movimiento(usuario_id=uid, cuenta_id=c.id, descripcion="Pago de tu tarjeta", categoria="Pago de tarjeta", tipo="income", monto=90_000.0,
                          fecha=__import__("datetime").datetime(2026, 7, 20), fuente="conciliacion_extracto"))
        db.commit()
        assert ingresos_sueltos.reabrir_pagos_huerfanos(db, uid, c) == 1  # solo el de $501.713 (el de $90.000 ya está; Mercpago no es pago)
        db.commit()
        db.refresh(h)
        estados = [i["estado"] for i in json.loads(h.review_json)]
        assert estados == ["faltante", "importado", "exacto"] and h.estado == "pendiente_revision"
    finally:
        db.close()


def test_quita_el_pago_que_ningun_extracto_completo_trae_y_deja_el_que_si(monkeypatch):
    from datetime import datetime

    from app import ingresos_sueltos

    uid = "ai-fuera"
    ids = mundo(uid, monkeypatch)
    db = SessionLocal()
    try:
        c = db.get(Cuenta, ids["credito"])
        review = [{"fecha": "2026-10-05", "descripcion": "Pago", "monto": 90_000.0, "tipo": "income", "estado": "importado"}]
        h = HistorialExtracto(usuario_id=uid, cuenta_id=c.id, banco_detectado="nu", estado="conciliado", total_movimientos=1, importados=1,
                              review_json=json.dumps(review), periodo_inicio="2026-09-15", fecha_corte="2026-10-15", lectura_json=json.dumps({"lectura_completa": True}))
        db.add(h)
        bueno = Movimiento(usuario_id=uid, cuenta_id=c.id, descripcion="Pago de tu tarjeta", categoria="Pago de tarjeta", tipo="income", monto=90_000.0,
                           fecha=datetime(2026, 10, 5), fuente="conciliacion_extracto")
        sobra = Movimiento(usuario_id=uid, cuenta_id=c.id, descripcion="Pago de tu tarjeta (factura anterior)", categoria="Pago de tarjeta", tipo="income",
                           monto=47_000.0, fecha=datetime(2026, 10, 5), fuente="conciliacion_extracto")
        fuera = Movimiento(usuario_id=uid, cuenta_id=c.id, descripcion="Pago de tu tarjeta", categoria="Pago de tarjeta", tipo="income", monto=1_000.0,
                           fecha=datetime(2026, 12, 5), fuente="conciliacion_extracto")  # ningún extracto cubre diciembre: no se toca
        db.add_all([bueno, sobra, fuera])
        db.commit()
        ids_ = (bueno.id, sobra.id, fuera.id)
        assert ingresos_sueltos.quitar_pagos_fuera_de_extracto(db, uid, c) == 1
        db.commit()
        assert [db.get(Movimiento, i) is not None for i in ids_] == [True, False, True]
    finally:
        db.close()


def test_reabre_la_linea_aproximada_con_un_movimiento_de_otro_extracto_y_otro_comercio(monkeypatch):
    from datetime import datetime

    from app import ingresos_sueltos

    uid = "ai-aprox"
    ids = mundo(uid, monkeypatch)
    db = SessionLocal()
    try:
        c = db.get(Cuenta, ids["ahorro"])
        uber = Movimiento(usuario_id=uid, cuenta_id=c.id, descripcion="Compra en UBER RIDES", categoria="Transporte", tipo="expense", monto=24_934.0,
                          fecha=datetime(2025, 10, 30), fuente="conciliacion_extracto", extracto_id="otro-extracto")
        db.add(uber)
        db.flush()
        review = [{"fecha": "2025-11-01", "descripcion": "Compra en TJV ZONA T", "monto": 23_800.0, "tipo": "expense", "estado": "aproximado", "match_id": uber.id},
                  {"fecha": "2025-11-02", "descripcion": "Compra en UBER RIDES", "monto": 24_900.0, "tipo": "expense", "estado": "aproximado", "match_id": uber.id}]
        h = HistorialExtracto(usuario_id=uid, cuenta_id=c.id, banco_detectado="nu", estado="conciliado", total_movimientos=2, importados=2,
                              review_json=json.dumps(review))
        db.add(h)
        db.commit()
        assert ingresos_sueltos.reabrir_aproximados_ajenos(db, uid, c) == 1  # la de otro comercio; la del mismo comercio se queda
        db.commit()
        db.refresh(h)
        assert [i["estado"] for i in json.loads(h.review_json)] == ["faltante", "aproximado"] and h.estado == "pendiente_revision"
    finally:
        db.close()
