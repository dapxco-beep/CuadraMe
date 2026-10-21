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
