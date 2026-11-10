"""MODO AUTOMÁTICO (app/modo_automatico.py): lo SEGURO se resuelve solo y se puede deshacer; lo dudoso no se toca.

Cada fase tiene su caso positivo y su caso NEGATIVO (ambigüedad, repetido, remitente falso, monto atípico, diferencia grande).
Datos 100 % inventados; nada sale de la base de pruebas."""
import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'modo_auto.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import autoarreglo as aa  # noqa: E402
from app import duplicados as dup  # noqa: E402
from app import limites, modo_automatico  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CorreoGasto, Cuenta, HistorialExtracto, Movimiento  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)
REMITENTE_BANCO = "Alertas <alertasynotificaciones@notificacionesbancolombia.com>"


@pytest.fixture
def uid():
    app.dependency_overrides.clear()
    limites._eventos.clear()
    u = f"u-{uuid.uuid4().hex[:10]}"
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=u, email=f"{u}@t.com", nombre="Persona Prueba")
    yield u
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def _correr(db, uid):
    db.expire_all()
    return aa.correr(db, uid, usuario=SimpleNamespace(id=uid, email="", nombre="", nombre_pila=""))


def _cuenta(db, uid, nombre="Bancolombia Ahorros", saldo=1_000_000.0, tipo="ahorro"):
    c = Cuenta(usuario_id=uid, nombre=nombre, tipo=tipo, saldo=saldo)
    db.add(c)
    db.commit()
    return c


def _correo(db, uid, monto=25_000.0, remitente=REMITENTE_BANCO, comercio="Tienda Ejemplo", asunto=None, dias=0, tipo="expense"):
    c = CorreoGasto(usuario_id=uid, gmail_msg_id=f"g-{uuid.uuid4().hex[:8]}", remitente=remitente,
                    asunto=asunto or f"Compra por ${int(monto):,} en {comercio}".replace(",", "."),
                    snippet=f"Realizaste una compra por ${int(monto):,} en {comercio} con tu tarjeta".replace(",", "."),
                    recibido_en=datetime.utcnow() - timedelta(days=dias), monto=monto, comercio=comercio, tipo_sugerido=tipo,
                    categoria_sugerida="Restaurantes", estado="pendiente")
    db.add(c)
    db.commit()
    return c


def _movs(db, uid):
    return db.query(Movimiento).filter(Movimiento.usuario_id == uid).all()


# ── Interruptor ──────────────────────────────────────────────────────────────────────────────────
def test_interruptor_activado_por_defecto_y_se_apaga(uid, db):
    assert client.get("/autoarreglo/modo").json() == {"activo": True}
    assert client.put("/autoarreglo/modo", json={"activo": False}).json() == {"activo": False}
    assert client.get("/autoarreglo/modo").json() == {"activo": False}
    assert client.put("/autoarreglo/modo", json={"activo": True}).json() == {"activo": True}
    assert modo_automatico.activo(db, uid) is True


def test_apagado_no_hace_nada_solo(uid, db):
    _cuenta(db, uid)
    _correo(db, uid)
    client.put("/autoarreglo/modo", json={"activo": False})
    r = _correr(db, uid)
    assert r["automatico"] == {}
    assert _movs(db, uid) == []
    assert db.query(CorreoGasto).filter(CorreoGasto.usuario_id == uid).one().estado == "pendiente"


# ── 1. Correos bancarios ─────────────────────────────────────────────────────────────────────────
def test_correo_de_banco_con_cuenta_unica_se_registra_y_se_deshace(uid, db):
    cuenta = _cuenta(db, uid)
    correo = _correo(db, uid, 25_000.0)
    r = _correr(db, uid)
    assert r["automatico"]["correos"] == 1
    movs = _movs(db, uid)
    assert len(movs) == 1 and movs[0].monto == 25_000.0 and movs[0].fuente == "email" and movs[0].cuenta_id == cuenta.id
    assert dup.origen_de_movimiento(movs[0]) == dup.ORIGEN_CORREO
    db.refresh(correo)
    assert correo.estado == "aprobado"
    assert "registré 1 movimiento de tus correos" in r["resumen"]["texto"]
    db.refresh(cuenta)
    assert cuenta.saldo == 975_000.0

    # Deshacer: se borra el movimiento, el saldo vuelve y el correo regresa a «por revisar» (y no se aprueba solo otra vez).
    d = client.post(f"/autoarreglo/lotes/{r['lote_id']}/deshacer")
    assert d.status_code == 200
    db.expire_all()
    assert _movs(db, uid) == []
    assert db.get(Cuenta, cuenta.id).saldo == 1_000_000.0
    assert db.get(CorreoGasto, correo.id).estado == "pendiente"
    pend = client.get("/correos/pendientes").json()
    assert [p["id"] for p in pend] == [correo.id]
    db.query(aa.MarcaCron).filter(aa.MarcaCron.usuario_id == uid, aa.MarcaCron.clave == aa.CLAVE_PAUSA).delete()
    db.commit()
    _correr(db, uid)
    assert _movs(db, uid) == []


def test_correo_con_nombre_de_banco_pero_dominio_falso_no_se_registra(uid, db):
    _cuenta(db, uid)
    _correo(db, uid, remitente='"Bancolombia" <alertas.seguridad@gmail.com>')
    _correr(db, uid)
    assert _movs(db, uid) == []


def test_correo_con_dos_cuentas_del_banco_no_se_registra(uid, db):
    _cuenta(db, uid, "Bancolombia Ahorros")
    _cuenta(db, uid, "Bancolombia Nómina")
    _correo(db, uid)
    _correr(db, uid)
    assert _movs(db, uid) == []


def test_correo_de_banco_sin_cuenta_de_ese_banco_no_se_registra(uid, db):
    _cuenta(db, uid, "Davivienda Ahorros")  # el correo es de Bancolombia: falta la cuenta
    _correo(db, uid)
    _correr(db, uid)
    assert _movs(db, uid) == []


def test_correo_sin_monto_no_se_registra(uid, db):
    _cuenta(db, uid, "Bancolombia Ahorros")
    _correo(db, uid, monto=0.0)
    _correr(db, uid)
    assert _movs(db, uid) == []


def test_correo_repetido_de_otro_canal_no_crea_un_segundo_movimiento(uid, db):
    cuenta = _cuenta(db, uid)
    m = Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion="Tienda Ejemplo", tipo="expense", monto=25_000.0,
                   fecha=ahora_co(), fuente="manual", categoria="Restaurantes")
    db.add(m)
    db.commit()
    _correo(db, uid, 25_000.0)
    _correr(db, uid)
    assert len(_movs(db, uid)) == 1  # solo el que ya estaba


def test_dos_correos_iguales_el_mismo_dia_se_dejan_a_la_persona(uid, db):
    _cuenta(db, uid)
    _correo(db, uid, 40_000.0)
    _correo(db, uid, 40_000.0)
    _correr(db, uid)
    assert _movs(db, uid) == []


def test_tope_de_20_correos_por_dia(uid, db):
    _cuenta(db, uid, saldo=10_000_000.0)
    for i in range(25):
        _correo(db, uid, 10_000.0 + 1_111 * i, comercio=f"Comercio {i}", dias=i // 25)
    r = _correr(db, uid)
    assert r["automatico"]["correos"] == 20
    assert len(_movs(db, uid)) == 20
    db.expire_all()
    assert db.query(CorreoGasto).filter(CorreoGasto.usuario_id == uid, CorreoGasto.estado == "pendiente").count() == 5
    assert modo_automatico._registrados_hoy(db, uid) == 20
    # una segunda corrida el mismo día no pasa del tope
    db.query(aa.MarcaCron).filter(aa.MarcaCron.usuario_id == uid, aa.MarcaCron.clave == aa.CLAVE_ULTIMA).delete()
    db.commit()
    _correr(db, uid)
    assert len(_movs(db, uid)) == 20


# ── 2. Bandeja «¿son tuyos?» ─────────────────────────────────────────────────────────────────────
def _wallet(db, uid, cuenta, monto=15_000.0, desc="Cafe Ejemplo", categoria="Restaurantes", origen="regla", horas=1):
    m = Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion=desc, tipo="expense", monto=monto, fuente="wallet",
                   fecha=ahora_co() - timedelta(hours=horas), categoria=categoria, cat_confirmada=False, cat_origen=origen)
    db.add(m)
    db.commit()
    return m


def test_bandeja_confirma_lo_de_comercio_conocido_y_se_deshace(uid, db):
    cuenta = _cuenta(db, uid)
    m = _wallet(db, uid, cuenta, origen="regla")
    r = _correr(db, uid)
    assert r["automatico"]["bandeja"] == 1
    db.refresh(m)
    assert m.cat_confirmada is True
    assert client.get("/movimientos/por-confirmar").json() == []
    assert "confirmé 1 movimiento que ya reconocía" in r["resumen"]["texto"]
    assert client.post(f"/autoarreglo/lotes/{r['lote_id']}/deshacer").status_code == 200
    db.refresh(m)
    assert m.cat_confirmada is False
    assert [x["id"] for x in client.get("/movimientos/por-confirmar").json()] == [m.id]


def test_bandeja_espera_24h_si_la_categoria_es_solo_sugerida(uid, db):
    cuenta = _cuenta(db, uid)
    reciente = _wallet(db, uid, cuenta, origen="sugerida", horas=2)
    viejo = _wallet(db, uid, cuenta, desc="Panaderia Ejemplo", origen="sugerida", horas=30)
    _correr(db, uid)
    db.refresh(reciente)
    db.refresh(viejo)
    assert reciente.cat_confirmada is False and viejo.cat_confirmada is True


def test_bandeja_deja_los_montos_atipicos_y_lo_sin_categoria(uid, db):
    cuenta = _cuenta(db, uid, saldo=50_000_000.0)
    for i in range(10):  # historial normal de la persona
        db.add(Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion=f"Compra {i}", tipo="expense", monto=20_000.0,
                          fecha=ahora_co() - timedelta(days=20 + i), categoria="Mercado", fuente="manual"))
    db.commit()
    atipico = _wallet(db, uid, cuenta, monto=900_000.0, desc="Tienda Desconocida", origen="regla")
    sin_cat = _wallet(db, uid, cuenta, desc="Algo Raro", categoria="Otros", origen="sugerida", horas=40)
    ok = _wallet(db, uid, cuenta, monto=18_000.0, desc="Fruver Ejemplo", origen="comercio")
    _correr(db, uid)
    for x in (atipico, sin_cat, ok):
        db.refresh(x)
    assert atipico.cat_confirmada is False and sin_cat.cat_confirmada is False and ok.cat_confirmada is True
    ids = {x["id"] for x in client.get("/movimientos/por-confirmar").json()}
    assert ids == {atipico.id, sin_cat.id}


# ── 3. Ajuste de saldo pequeño ───────────────────────────────────────────────────────────────────
def _extracto(db, uid, cuenta, saldo_final, review=None):
    corte = (ahora_co() - timedelta(days=3)).date().isoformat()
    h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta.id, banco_detectado="Bancolombia", estado="conciliado",
                          review_json=json.dumps(review or []), saldo_final_extracto=saldo_final, fecha_corte=corte,
                          lectura_json=json.dumps({"lectura_completa": True}))
    db.add(h)
    db.commit()
    return h


def _cuenta_con_un_ingreso(db, uid):
    cuenta = _cuenta(db, uid, saldo=0.0)
    db.add(Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion="Nómina", tipo="income", monto=100_000.0,
                      fecha=ahora_co() - timedelta(days=10), categoria="Ingresos", fuente="manual"))
    cuenta.saldo = 100_000.0
    db.commit()
    return cuenta


def test_diferencia_de_centavos_se_ajusta_sola_y_se_deshace(uid, db):
    cuenta = _cuenta_con_un_ingreso(db, uid)
    _extracto(db, uid, cuenta, 101_500.0)  # el banco dice $1.500 más
    r = _correr(db, uid)
    assert r["automatico"]["ajuste"] == 1
    ajustes = [m for m in _movs(db, uid) if m.fuente == "ajuste_saldo"]
    assert len(ajustes) == 1 and ajustes[0].monto == 1_500.0 and ajustes[0].tipo == "income"
    assert "Ajuste automático por redondeo/centavos" in ajustes[0].notas
    assert db.get(Cuenta, cuenta.id).saldo == 101_500.0
    assert "diferencia de centavos" in r["resumen"]["texto"]
    assert client.post(f"/autoarreglo/lotes/{r['lote_id']}/deshacer").status_code == 200
    db.expire_all()
    assert [m for m in _movs(db, uid) if m.fuente == "ajuste_saldo"] == []
    assert db.get(Cuenta, cuenta.id).saldo == 100_000.0


def test_diferencia_mayor_no_se_ajusta(uid, db):
    cuenta = _cuenta_con_un_ingreso(db, uid)
    _extracto(db, uid, cuenta, 150_000.0)  # $50.000 de diferencia: eso lo ve la persona
    _correr(db, uid)
    assert [m for m in _movs(db, uid) if m.fuente == "ajuste_saldo"] == []
    assert db.get(Cuenta, cuenta.id).saldo == 100_000.0


def test_diferencia_pequena_con_lineas_pendientes_no_se_ajusta(uid, db):
    cuenta = _cuenta_con_un_ingreso(db, uid)
    _extracto(db, uid, cuenta, 101_500.0, review=[{"estado": "faltante", "fingerprint": "x", "monto": 1500, "tipo": "income",
                                                  "fecha": "2026-01-01", "descripcion": "Falta"}])
    _correr(db, uid)
    assert [m for m in _movs(db, uid) if m.fuente == "ajuste_saldo"] == []


def test_diferencia_pequena_en_tarjeta_no_se_ajusta(uid, db):
    cuenta = _cuenta(db, uid, "Bancolombia Tarjeta", saldo=-100_000.0, tipo="credito")
    _extracto(db, uid, cuenta, -101_000.0)
    _correr(db, uid)
    assert [m for m in _movs(db, uid) if m.fuente == "ajuste_saldo"] == []


def test_umbral_de_diferencia_pequena():
    f = modo_automatico.diferencia_pequena
    assert f(1_999, 500_000, "COP") and f(2_000, 500_000, "COP")
    assert not f(2_001, 500_000, "COP")  # 0,05 % de 500.000 son $250
    assert f(5_000, 20_000_000, "COP")  # 0,05 % de 20 millones son $10.000
    assert not f(0.4, 500_000, "COP")  # menos de un peso: ya cuadra


# ── 4. «¿Es el mismo gasto?» ─────────────────────────────────────────────────────────────────────
def _aprox(cuenta, mov, monto=None, fecha=None, fp="fp1"):
    return {"estado": "aproximado", "fingerprint": fp, "match_id": mov.id, "monto": monto if monto is not None else mov.monto,
            "tipo": "expense", "fecha": fecha or mov.fecha.strftime("%Y-%m-%d"), "descripcion": "COMPRA TIENDA EJEMPLO"}


def _hist_con(db, uid, cuenta, review):
    h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta.id, banco_detectado="Bancolombia", estado="pendiente_revision",
                          review_json=json.dumps(review), aproximados=len(review))
    db.add(h)
    db.commit()
    return h


def _mov_manual(db, uid, cuenta, monto=30_000.0, dias=2, desc="Tienda Ejemplo"):
    m = Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion=desc, tipo="expense", monto=monto,
                   fecha=datetime.combine((ahora_co() - timedelta(days=dias)).date(), datetime.min.time()), fuente="manual", categoria="Mercado")
    db.add(m)
    db.commit()
    return m


def _estado_item(db, h, fp="fp1"):
    db.refresh(h)
    return next(i["estado"] for i in json.loads(h.review_json) if i["fingerprint"] == fp)


def test_mismo_gasto_con_monto_identico_se_junta_solo_y_se_deshace(uid, db):
    cuenta = _cuenta(db, uid)
    m = _mov_manual(db, uid, cuenta)
    h = _hist_con(db, uid, cuenta, [_aprox(cuenta, m, fecha=(m.fecha + timedelta(days=1)).strftime("%Y-%m-%d"))])
    r = _correr(db, uid)
    assert r["automatico"]["unir"] == 1
    assert _estado_item(db, h) == "completado"
    assert len(_movs(db, uid)) == 1
    assert "junté 1 gasto que era el mismo" in r["resumen"]["texto"]
    assert client.post(f"/autoarreglo/lotes/{r['lote_id']}/deshacer").status_code == 200
    assert _estado_item(db, h) == "aproximado"


def test_mismo_gasto_con_monto_distinto_se_pregunta(uid, db):
    cuenta = _cuenta(db, uid)
    m = _mov_manual(db, uid, cuenta, 30_000.0)
    h = _hist_con(db, uid, cuenta, [_aprox(cuenta, m, monto=30_500.0)])
    _correr(db, uid)
    assert _estado_item(db, h) == "aproximado"


def test_mismo_gasto_a_mas_de_3_dias_se_pregunta(uid, db):
    cuenta = _cuenta(db, uid)
    m = _mov_manual(db, uid, cuenta)
    h = _hist_con(db, uid, cuenta, [_aprox(cuenta, m, fecha=(m.fecha + timedelta(days=5)).strftime("%Y-%m-%d"))])
    _correr(db, uid)
    assert _estado_item(db, h) == "aproximado"


def test_mismo_gasto_con_dos_candidatos_se_pregunta(uid, db):
    cuenta = _cuenta(db, uid)
    m1 = _mov_manual(db, uid, cuenta)
    _mov_manual(db, uid, cuenta, dias=1)  # otro movimiento igual: ¿cuál es?
    h = _hist_con(db, uid, cuenta, [_aprox(cuenta, m1)])
    _correr(db, uid)
    assert _estado_item(db, h) == "aproximado"


def test_dos_lineas_para_el_mismo_movimiento_se_preguntan(uid, db):
    cuenta = _cuenta(db, uid)
    m = _mov_manual(db, uid, cuenta)
    h = _hist_con(db, uid, cuenta, [_aprox(cuenta, m, fp="fp1"), _aprox(cuenta, m, fp="fp2")])
    _correr(db, uid)
    assert _estado_item(db, h, "fp1") == "aproximado" and _estado_item(db, h, "fp2") == "aproximado"


def test_correo_con_arroba_falso_en_el_nombre_en_pantalla_no_se_registra(uid, db):
    """Phishing: el nombre en pantalla trae un «@dominio» de banco, pero la dirección real es otra."""
    _cuenta(db, uid, "Bancolombia Ahorros")
    _correo(db, uid, remitente='"alertas@notificacionesbancolombia.com" <x@evil.example>', monto=9_999.0)
    _correr(db, uid)
    assert _movs(db, uid) == []
    assert modo_automatico._dominio_de_banco('"alertas@notificacionesbancolombia.com" <x@evil.example>') is False
    assert modo_automatico._dominio_de_banco("Bancolombia <alertas@notificacionesbancolombia.com>") is True


def test_correo_con_monto_grande_no_se_registra_solo(uid, db):
    _cuenta(db, uid, "Bancolombia Ahorros")
    _correo(db, uid, monto=modo_automatico.TOPE_MONTO_CORREO + 1)
    _correr(db, uid)
    assert _movs(db, uid) == []


def test_con_el_modo_apagado_no_se_ordena_nada_solo(uid, db):
    from types import SimpleNamespace

    from app import autoarreglo

    modo_automatico.poner_activo(db, uid, False)
    db.commit()
    assert autoarreglo._arreglos_seguros(SimpleNamespace(db=db, uid=uid)) == {}
