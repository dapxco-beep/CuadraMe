"""GUARDIA DE COHERENCIA (app/guardia_coherencia.py): lo importado debe tener respaldo en el extracto. Datos 100 % inventados.

Cubre las seis formas del mismo problema: compra con su ingreso falso, pago repetido, pareja en otra cuenta, línea completada
sin pareja, compra emparejada con otro comercio y residuo (movimiento sin línea). Y que la guardia NO escribe nada."""
import json
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'guardia.db')}")

from app import autoarreglo as aa  # noqa: E402
from app import guardia_coherencia as gc  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Cuenta, HistorialExtracto, Movimiento, Perfil  # noqa: E402

Base.metadata.create_all(bind=engine)


def _cuenta(db, uid, nombre="Banco Ejemplo A Ahorros", tipo="ahorro"):
    c = Cuenta(usuario_id=uid, nombre=nombre, tipo=tipo, saldo=0)
    db.add(c)
    db.flush()
    return c


def _mov(db, uid, cuenta, dia, desc, monto, tipo, fuente="conciliacion_extracto"):
    m = Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion=desc, categoria="Otros", tipo=tipo, monto=monto,
                   fecha=datetime(2026, 8, dia), fuente=fuente)
    db.add(m)
    db.flush()
    return m


def _linea(dia, desc, monto, tipo, estado="importado", mov=None, clave="movimiento_id"):
    i = {"fecha": f"2026-08-{dia:02d}", "descripcion": desc, "monto": monto, "tipo": tipo, "estado": estado, "fingerprint": f"fp-{dia}-{desc}"}
    if mov is not None:
        i[clave] = mov
    return i


def _extracto(db, uid, cuenta, lineas, completo=True, creado=None):
    """Extracto de agosto de una cuenta de ahorros; con saldos que SÍ explican las líneas (lectura completa) o no."""
    neto = sum(i["monto"] * (1 if i["tipo"] == "income" else -1) for i in lineas)
    h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta.id, banco_detectado="ejemplo", estado="conciliado", review_json=json.dumps(lineas),
                          periodo_inicio="2026-08-01", fecha_corte="2026-08-31", saldo_inicial_extracto=100_000.0,
                          saldo_final_extracto=100_000.0 + neto + (0 if completo else 777.0), saldos_origen="extracto")
    if creado:
        h.creado_en = creado
    db.add(h)
    db.flush()
    return h


def _motivos(hallazgos):
    return sorted(h["motivo"] for h in hallazgos)


def test_una_cuenta_coherente_no_tiene_hallazgos():
    db = SessionLocal()
    try:
        uid = "g-ok"
        c = _cuenta(db, uid)
        a = _mov(db, uid, c, 5, "Tienda Uno", 20_000.0, "expense")
        b = _mov(db, uid, c, 9, "Abono Cliente", 50_000.0, "income")
        _extracto(db, uid, c, [_linea(5, "Tienda Uno", 20_000.0, "expense", mov=a.id), _linea(9, "Abono Cliente", 50_000.0, "income", mov=b.id)])
        assert gc.revisar(db, uid, c) == []
    finally:
        db.close()


def test_ingreso_falso_con_su_compra_buena_y_residuo_sin_linea():
    db = SessionLocal()
    try:
        uid = "g-1"
        c = _cuenta(db, uid)
        buena = _mov(db, uid, c, 5, "Tienda Uno", 20_000.0, "expense")
        falso = _mov(db, uid, c, 5, "Tienda Uno", 20_000.0, "income")
        residuo = _mov(db, uid, c, 12, "2026", 300.0, "expense")
        _extracto(db, uid, c, [_linea(5, "Tienda Uno", 20_000.0, "expense", mov=buena.id)])
        h = {x["movimiento_id"]: x for x in gc.revisar(db, uid, c)}
        assert h[falso.id]["motivo"] == "tipo_distinto_al_extracto" and h[falso.id]["severidad"] == "alta"
        assert h[residuo.id]["motivo"] == "sin_respaldo_en_extracto"
        assert buena.id not in h
        assert "5 ago 2026" in h[falso.id]["texto"] and "ingreso" in h[falso.id]["texto"]
    finally:
        db.close()


def test_pago_repetido_y_uno_solo_queda_respaldado():
    db = SessionLocal()
    try:
        uid = "g-2"
        c = _cuenta(db, uid)
        p1 = _mov(db, uid, c, 10, "Pago de tu tarjeta", 60_000.0, "income")
        p2 = _mov(db, uid, c, 10, "Pago tarjeta", 60_000.0, "income")
        _extracto(db, uid, c, [_linea(10, "Pago de tu tarjeta", 60_000.0, "income", mov=p1.id)])
        r = gc.revisar(db, uid, c)
        assert [(x["movimiento_id"], x["motivo"]) for x in r] == [(p2.id, "repetido_frente_al_extracto")]
    finally:
        db.close()


def test_pareja_en_otra_cuenta_inexistente_y_de_otro_comercio():
    db = SessionLocal()
    try:
        uid = "g-3"
        c = _cuenta(db, uid)
        otra = _cuenta(db, uid, "Banco Ejemplo B Ahorros")
        ajeno = _mov(db, uid, otra, 7, "Tienda Lejana", 10_000.0, "expense")
        de_otra_linea = _mov(db, uid, c, 8, "Panaderia Central", 15_000.0, "expense")
        lineas = [_linea(7, "Tienda Lejana", 10_000.0, "expense", "completado", ajeno.id, "match_id"),
                  _linea(9, "Ferreteria Norte", 5_000.0, "expense", "completado", "no-existe", "match_id"),
                  _linea(8, "Libreria Sur", 15_000.0, "expense", "aproximado", de_otra_linea.id, "match_id"),
                  _linea(8, "Panaderia Central", 15_000.0, "expense", "importado", de_otra_linea.id)]
        # la línea de la panadería está respaldada por su movimiento; la de «Libreria Sur» lo apunta a la fuerza
        _extracto(db, uid, c, lineas)
        r = gc.revisar(db, uid, c)
        assert "pareja_de_otro_comercio" in _motivos(r) and "pareja_en_otra_cuenta" in _motivos(r) and "pareja_inexistente" in _motivos(r)
        assert next(x for x in r if x["motivo"] == "pareja_inexistente")["movimiento_id"] == "no-existe"
        assert all(set(x) >= {"movimiento_id", "motivo", "texto", "severidad"} for x in r)
        assert all(x["motivo"] in gc.MOTIVOS for x in r)
    finally:
        db.close()


def test_extracto_no_verificado_no_acusa_a_nadie():
    db = SessionLocal()
    try:
        uid = "g-4"
        c = _cuenta(db, uid)
        _mov(db, uid, c, 5, "Tienda Uno", 20_000.0, "expense")
        _extracto(db, uid, c, [_linea(9, "Otra Cosa", 1_000.0, "expense")], completo=False)  # sus saldos no explican las líneas
        assert gc.revisar(db, uid, c) == []
    finally:
        db.close()


def test_de_varias_lecturas_del_mismo_corte_manda_la_mas_nueva():
    db = SessionLocal()
    try:
        uid = "g-5"
        c = _cuenta(db, uid)
        m = _mov(db, uid, c, 5, "Tienda Uno", 20_000.0, "expense")
        _extracto(db, uid, c, [], creado=datetime(2026, 9, 1))  # vieja y vacía
        _extracto(db, uid, c, [_linea(5, "Tienda Uno", 20_000.0, "expense", mov=m.id)], creado=datetime(2026, 9, 2))
        assert gc.revisar(db, uid, c) == []
    finally:
        db.close()


def test_es_de_solo_lectura_y_aislada_por_usuario():
    db = SessionLocal()
    try:
        uid = "g-6"
        c = _cuenta(db, uid)
        falso = _mov(db, uid, c, 5, "Tienda Uno", 20_000.0, "income")
        _extracto(db, uid, c, [_linea(9, "Otra", 1_000.0, "expense")])
        db.commit()
        antes = (db.query(Movimiento).count(), c.saldo, falso.tipo)
        assert gc.revisar(db, uid, c)
        assert not db.new and not db.dirty and not db.deleted
        assert (db.query(Movimiento).count(), c.saldo, falso.tipo) == antes
        assert gc.revisar(db, "otra-persona", c) == []  # una cuenta ajena no se revisa
    finally:
        db.close()


def test_correr_deja_la_coherencia_en_la_respuesta():
    db = SessionLocal()
    try:
        uid = "g-7"
        db.add(Perfil(usuario_id=uid, plan="free"))
        c = _cuenta(db, uid)
        falso = _mov(db, uid, c, 5, "Tienda Uno", 20_000.0, "income")
        _extracto(db, uid, c, [_linea(9, "Otra", 1_000.0, "expense")])
        db.commit()
        r = aa.correr(db, uid)
        assert r["coherencia"] and r["coherencia"][0]["movimiento_id"] == falso.id and r["coherencia"][0]["cuenta_id"] == c.id
        assert db.get(Movimiento, falso.id) is not None  # la guardia no borró nada
    finally:
        db.close()
