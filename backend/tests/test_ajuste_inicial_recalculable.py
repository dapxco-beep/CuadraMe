"""Ajuste inicial RECALCULABLE (app/saldo_inicial_auto.py). Datos 100 % inventados.

Cuenta de ahorros "Nu de prueba": 3 extractos encadenados (mar, abr, may) con sus movimientos. El libro de la cuenta solo
cuadra si alguien registra con cuánto empezó (100.000 al 1 de marzo); eso es el ajuste inicial, y se RECALCULA si llega un
extracto más antiguo, aparecen movimientos anteriores, se borran, se mueve el extracto de cuenta o se borra el extracto.
"""
import os
import tempfile
import threading

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'ajuste_ini.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import cierre_extractos as ce  # noqa: E402
from app import cuadre_encadenado  # noqa: E402
from app import saldo_inicial_auto as sia  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import HistorialExtracto, Movimiento  # noqa: E402

client = TestClient(app)
USUARIO = {"u": UsuarioActual(id="aj-0", email="a@test.com", nombre="Aj")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["u"]
    yield


def como(uid):
    USUARIO["u"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def _cuenta(nombre="Nu de prueba", tipo="ahorro", saldo=0):
    r = client.post("/cuentas", json={"nombre": nombre, "tipo": tipo, "saldo": saldo})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _mov(cuenta, tipo, monto, fecha, desc="x"):
    r = client.post("/movimientos", json={"cuenta_id": cuenta, "tipo": tipo, "monto": monto, "descripcion": desc,
                                          "categoria": "Otros", "fecha": fecha, "confirmar_nuevo": True})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _hist(uid, cuenta, ini, fin, inicio, corte, origen="extracto"):
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta, banco_detectado="prueba", estado="pendiente_revision",
                              review_json="[]", saldo_inicial_extracto=ini, saldo_final_extracto=fin,
                              periodo_inicio=inicio, fecha_corte=corte, saldos_origen=origen)
        db.add(h)
        db.commit()
        return h.id
    finally:
        db.close()


def _saldo(cuenta):
    return next(c for c in client.get("/cuentas").json() if c["id"] == cuenta)["saldo"]


def _autos(cuenta):
    db = SessionLocal()
    try:
        return [m for m in db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta, Movimiento.fuente == "ajuste_saldo").all()
                if sia.es_automatico(m)]
    finally:
        db.close()


def _auto():
    r = client.post("/conciliacion/cuadre/saldo-inicial-auto")
    assert r.status_code == 200, r.text
    return r.json()["registrados"]


def _tres_meses(uid):
    """mar +50k (100→150), abr +20k (150→170), may +30k (170→200). Sin ajuste el libro queda 100.000 por debajo."""
    como(uid)
    c = _cuenta()
    _mov(c, "income", 50_000, "2026-03-10T10:00:00", "Pago marzo")
    _mov(c, "income", 20_000, "2026-04-10T10:00:00", "Pago abril")
    _mov(c, "income", 30_000, "2026-05-10T10:00:00", "Pago mayo")
    h_mar = _hist(uid, c, 100_000, 150_000, "2026-03-01", "2026-03-31")
    _hist(uid, c, 150_000, 170_000, "2026-04-01", "2026-04-30")
    _hist(uid, c, 170_000, 200_000, "2026-05-01", "2026-05-31")
    return c, h_mar


def test_tres_extractos_un_ajuste_igual_a_S0_y_todos_los_meses_cuadran():
    c, _ = _tres_meses("aj-1")
    assert _saldo(c) == 100_000
    reg = _auto()
    assert len(reg) == 1 and reg[0]["cambio"] == "creado" and reg[0]["monto"] == 100_000 and reg[0]["fecha"] == "2026-02-28"
    assert _saldo(c) == 200_000  # = saldo final del último extracto
    assert len(_autos(c)) == 1
    enc = client.get(f"/conciliacion/cuadre/encadenado?cuenta_id={c}").json()
    assert enc["cuadra"] is True and all(m["estado"] == "cuadra" for m in enc["meses"])
    assert enc["desde"]["estado"] == "cuadra" and enc["desde"]["texto"] == "Tu cuenta cuadra desde marzo."
    assert not any(m["estado"] == "solo_saldo_inicial" for m in enc["meses"])


def test_llega_un_extracto_mas_antiguo_el_ajuste_se_mueve_y_el_anterior_se_elimina():
    c, _ = _tres_meses("aj-2")
    _auto()
    antes = _autos(c)[0].id
    _mov(c, "income", 20_000, "2026-02-10T10:00:00", "Pago febrero")  # movimiento anterior al primer extracto
    assert _saldo(c) == 200_000  # el ajuste absorbe lo anterior: el libro al 1 de marzo sigue valiendo 100.000
    _hist("aj-2", c, 80_000, 100_000, "2026-02-01", "2026-02-28")  # llega febrero
    _auto()
    autos = _autos(c)
    assert len(autos) == 1 and autos[0].id == antes and autos[0].monto == 80_000
    assert autos[0].fecha.date().isoformat() == "2026-01-31"
    assert _saldo(c) == 200_000
    assert _auto() == []  # idempotente


def test_actualizar_dice_cuanto_era_antes():
    c, _ = _tres_meses("aj-2b")
    _auto()
    _hist("aj-2b", c, 60_000, 100_000, "2026-02-01", "2026-02-28")  # llega febrero con otro saldo inicial
    reg = _auto()
    assert reg[0]["cambio"] == "actualizado" and reg[0]["monto"] == 60_000 and reg[0]["monto_antes"] == 100_000
    assert reg[0]["texto"] == "Actualicé con cuánto empezó tu cuenta: $60.000 al 31 ene 2026 (antes $100.000)."
    assert reg[0]["movimiento_id"]


def test_movimiento_anterior_recalcula_A_igual_S0_menos_M_y_borrarlo_lo_devuelve():
    c, _ = _tres_meses("aj-3")
    _auto()
    mid = _mov(c, "income", 15_000, "2026-02-20T10:00:00", "Anterior")
    a = _autos(c)[0]
    assert a.monto == 85_000 and a.fecha.date().isoformat() == "2026-02-19"  # 100.000 - 15.000, un día antes del primer movimiento
    assert _saldo(c) == 200_000
    assert client.delete(f"/movimientos/{mid}").status_code == 200
    a = _autos(c)[0]
    assert a.monto == 100_000 and a.fecha.date().isoformat() == "2026-02-28"
    assert _saldo(c) == 200_000


def test_el_ajuste_es_neutro_no_cuenta_como_ingreso_ni_gasto():
    c, _ = _tres_meses("aj-4")
    _auto()
    ig = client.get("/informes/ingresos-gastos?desde=2026-02-01&hasta=2026-05-31")
    if ig.status_code == 200:
        assert ig.json().get("ingresos") == 100_000  # 50k + 20k + 30k, sin los 100k del saldo inicial
    a = _autos(c)[0]
    assert a.fuente == "ajuste_saldo" and a.notas.endswith("automático")


def test_deshacer_lo_desactiva_y_volver_a_calcular_lo_reactiva():
    c, _ = _tres_meses("aj-5")
    mid = _auto()[0]["movimiento_id"]
    assert client.post("/conciliacion/cuadre/deshacer", json={"movimiento_id": mid, "confirmar": True}).status_code == 200
    assert _saldo(c) == 100_000
    assert _auto() == []  # no se vuelve a crear solo
    est = client.get(f"/conciliacion/cuadre/saldo-inicial-auto/{c}").json()
    assert est["desactivado"] is True and est["automatico"] is False and est["propuesto"]["monto"] == 100_000
    r = client.post("/conciliacion/cuadre/saldo-inicial-auto/recalcular", json={"cuenta_id": c}).json()
    assert r["cambio"] == "creado" and r["monto"] == 100_000
    assert _saldo(c) == 200_000


def test_borrar_a_mano_el_ajuste_tambien_lo_desactiva():
    c, _ = _tres_meses("aj-5b")
    mid = _auto()[0]["movimiento_id"]
    assert client.delete(f"/movimientos/{mid}").status_code == 200
    assert _auto() == [] and _autos(c) == []


def test_saldo_fijado_a_mano_no_se_toca_y_se_avisa():
    como("aj-6")
    c = _cuenta(saldo=70_000)
    _mov(c, "income", 50_000, "2026-03-10T10:00:00")
    _hist("aj-6", c, 100_000, 150_000, "2026-03-01", "2026-03-31")
    assert _auto() == []
    assert _saldo(c) == 120_000
    r = client.post("/conciliacion/cuadre/saldo-inicial-auto/recalcular", json={"cuenta_id": c}).json()
    assert r["estado"] == "saldo_fijado" and "fijado a mano" in r["texto"]
    assert _autos(c) == []


def test_tarjeta_no_recibe_ajuste_y_recalcular_responde_409():
    como("aj-7")
    c = _cuenta(nombre="Visa de prueba", tipo="credito")
    _hist("aj-7", c, 100_000, 150_000, "2026-03-01", "2026-03-31")
    assert _auto() == [] and _autos(c) == []
    assert client.post("/conciliacion/cuadre/saldo-inicial-auto/recalcular", json={"cuenta_id": c}).status_code == 409


def test_modo_hoy_no_inventa_el_pasado():
    c, _ = _tres_meses("aj-8")
    assert client.put("/perfil/punto-de-partida", json={"modo": "hoy", "fecha": "2026-06-01"}).status_code in (200, 201)
    assert _auto() == [] and _autos(c) == []


def test_sin_extractos_o_extracto_sin_saldo_inicial_no_hay_ajuste():
    como("aj-9")
    c = _cuenta()
    _mov(c, "income", 5_000, "2026-03-10T10:00:00")
    assert _auto() == []
    _hist("aj-9", c, None, 150_000, "2026-03-01", "2026-03-31")
    assert _auto() == [] and _autos(c) == []


def test_idempotencia_y_concurrencia_un_solo_ajuste():
    c, _ = _tres_meses("aj-10")
    errores = []

    def correr():
        db = SessionLocal()
        try:
            sia.refrescar(db, [c])
        except Exception as e:  # noqa: BLE001
            errores.append(e)
        finally:
            db.close()

    hilos = [threading.Thread(target=correr) for _ in range(4)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert not errores
    assert len(_autos(c)) == 1 and _saldo(c) == 200_000
    assert _auto() == [] and _auto() == []


def test_aislado_por_usuario():
    c, _ = _tres_meses("aj-11")
    como("aj-12")
    assert _auto() == []
    r = client.post("/conciliacion/cuadre/saldo-inicial-auto/recalcular", json={"cuenta_id": c})
    assert r.status_code in (403, 404)
    como("aj-11")
    assert _saldo(c) == 100_000


def test_cambiar_cuenta_de_extracto_recalcula_ambas_cuentas():
    como("aj-13")
    a, b = _cuenta("Cuenta A"), _cuenta("Cuenta B")
    h = _hist("aj-13", a, 100_000, 150_000, "2026-03-01", "2026-03-31")
    _mov(a, "income", 50_000, "2026-03-10T10:00:00")
    _auto()  # (el movimiento ya lo disparó solo al registrarse)
    assert len(_autos(a)) == 1 and _saldo(a) == 150_000
    r = client.post(f"/conciliacion/historial/{h}/cambiar-cuenta", json={"cuenta_id": b, "confirmar": True})
    assert r.status_code == 200, r.text
    assert _autos(a) == [] and _saldo(a) == 50_000  # A ya no tiene extracto: sin ajuste
    assert len(_autos(b)) == 1 and _saldo(b) == 100_000  # B recibe el suyo


def test_eliminar_el_extracto_quita_el_ajuste():
    como("aj-14")
    c = _cuenta()
    h = _hist("aj-14", c, 100_000, 150_000, "2026-03-01", "2026-03-31")
    _mov(c, "income", 50_000, "2026-03-10T10:00:00")
    _auto()
    assert _saldo(c) == 150_000
    assert client.delete(f"/conciliacion/historial/{h}").status_code == 200
    assert _autos(c) == [] and _saldo(c) == 50_000


def test_cierre_de_mes_muestra_el_ajuste_y_desde_donde_cuadra():
    _tres_meses("aj-15")
    _auto()
    db = SessionLocal()
    try:
        r = ce.construir(db, "aj-15", "2026-04")
    finally:
        db.close()
    cu = r["bancos"][0]["cuentas"][0]
    assert cu["estado"] == "cuadra"
    assert cu["ajuste_inicial"]["etiqueta"] == "Saldo inicial automático" and cu["ajuste_inicial"]["monto"] == 100_000
    assert cu["ajuste_inicial"]["explicacion"] == "Es lo que tenías antes de tu primer extracto. No cuenta como ingreso ni gasto."
    assert cu["cuadre_desde"]["texto"] == "Tu cuenta cuadra desde marzo."
    assert cu["empece"] == 150_000


def test_cuadra_desde_primer_mes_que_no_cuadra():
    r = {"meses": [
        {"mes": "2026-03", "historial_id": "a", "estado": "cuadra", "diferencia": 0.0, "acumulada": 0.0},
        {"mes": "2026-04", "historial_id": "b", "estado": "diferencia", "diferencia": -12_500.0, "acumulada": -12_500.0},
        {"mes": "2026-05", "historial_id": "c", "estado": "cuadra", "diferencia": 0.0, "acumulada": 0.0}]}
    d = cuadre_encadenado.cuadra_desde(r)
    assert d["primer_mes_malo"] == "2026-04" and d["desde"] == "2026-05"
    assert d["texto"] == "Primer mes que no cuadra: abril por $12.500. Tu cuenta cuadra desde mayo."
    assert cuadre_encadenado.cuadra_desde({"meses": []}) is None


def test_mes_con_diferencia_real_no_lo_tapa_el_ajuste():
    """El ajuste arregla el punto de partida, no los meses: una línea sin importar sigue marcando el mes culpable."""
    como("aj-16")
    c = _cuenta()
    _mov(c, "income", 40_000, "2026-03-10T10:00:00")  # falta 10.000 por importar
    _hist("aj-16", c, 100_000, 150_000, "2026-03-01", "2026-03-31")
    _auto()
    enc = client.get(f"/conciliacion/cuadre/encadenado?cuenta_id={c}").json()
    assert enc["cuadra"] is False and enc["meses"][0]["estado"] == "diferencia"
    assert enc["desde"]["primer_mes_malo"] == "2026-03" and "$10.000" in enc["desde"]["texto"]
