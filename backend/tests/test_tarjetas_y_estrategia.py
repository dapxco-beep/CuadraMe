"""Tarjetas de crédito (cupo, fechas, alertas) y simulador avalancha vs bola de nieve."""
import os
import tempfile
from datetime import datetime
from types import SimpleNamespace

import pytest

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'test3.db')}")

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.estrategia_deudas import comparar_estrategias, simular  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Deuda, PushSubscription  # noqa: E402
from app.tarjetas import calc_tarjeta, proxima_fecha, tarjetas_por_avisar  # noqa: E402

client = TestClient(app)
CABECERA = {"X-Cron-Secret": "secreto-de-prueba"}


@pytest.fixture(autouse=True)
def _usuario():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id="user-tc", email="tc@test.com", nombre="Tarjeta Test"
    )
    yield


def _tarjeta(**kw):
    base = dict(tipo="credito", saldo=-800_000, cupo_total=2_000_000, dia_corte=15, dia_pago=30,
                tasa_ea=30.0, ultima_alerta_pago=None, nombre="Visa", usuario_id="user-tc")
    base.update(kw)
    return SimpleNamespace(**base)


# ── Tarjetas: lógica pura ─────────────────────────────

def test_utilizacion_y_niveles():
    hoy = datetime(2026, 10, 3, 9, 0)
    t = calc_tarjeta(_tarjeta(), hoy)
    assert t["cupo_usado"] == 800_000
    assert t["cupo_disponible"] == 1_200_000
    assert t["utilizacion_pct"] == 40.0
    assert t["nivel_utilizacion"] == "alerta"  # >30%
    assert calc_tarjeta(_tarjeta(saldo=-300_000), hoy)["nivel_utilizacion"] == "ok"  # 15%
    assert calc_tarjeta(_tarjeta(saldo=-1_700_000), hoy)["nivel_utilizacion"] == "critico"  # 85%
    # justo en el umbral todavía no alerta (es "mayor que")
    assert calc_tarjeta(_tarjeta(saldo=-600_000), hoy)["nivel_utilizacion"] == "ok"


def test_saldo_positivo_o_sin_cupo():
    hoy = datetime(2026, 10, 3)
    a_favor = calc_tarjeta(_tarjeta(saldo=50_000), hoy)
    assert a_favor["cupo_usado"] == 0 and a_favor["pago_minimo_estimado"] == 0
    sin_cupo = calc_tarjeta(_tarjeta(cupo_total=None), hoy)
    assert sin_cupo["utilizacion_pct"] is None and sin_cupo["nivel_utilizacion"] == "sin_cupo"
    assert sin_cupo["cupo_disponible"] is None


def test_proximas_fechas_con_cambio_de_mes_y_anio():
    assert proxima_fecha(15, datetime(2026, 10, 3).date()).isoformat() == "2026-10-15"
    assert proxima_fecha(3, datetime(2026, 10, 3).date()).isoformat() == "2026-10-03"  # hoy cuenta
    assert proxima_fecha(2, datetime(2026, 10, 3).date()).isoformat() == "2026-11-02"
    assert proxima_fecha(5, datetime(2026, 12, 20).date()).isoformat() == "2027-01-05"
    # día 31 en un mes de 30 días / febrero: se ajusta al último día real
    assert proxima_fecha(31, datetime(2026, 11, 10).date()).isoformat() == "2026-11-30"
    assert proxima_fecha(31, datetime(2027, 2, 10).date()).isoformat() == "2027-02-28"


def test_interes_y_pago_minimo():
    hoy = datetime(2026, 10, 3)
    t = calc_tarjeta(_tarjeta(saldo=-1_000_000, tasa_ea=30.0), hoy)
    # 30% EA -> (1.3)^(1/12)-1 = 2.2104% mensual (no 2.5 = 30/12)
    assert t["interes_estimado"] == 22_104
    assert t["pago_minimo_estimado"] == 50_000 + 22_104
    sin_tasa = calc_tarjeta(_tarjeta(saldo=-1_000_000, tasa_ea=None), hoy)
    assert sin_tasa["interes_estimado"] is None and sin_tasa["pago_minimo_estimado"] == 50_000


def test_aviso_de_pago_solo_cerca_y_una_vez():
    cerca = _tarjeta(dia_pago=5)  # hoy 3 oct -> faltan 2 días
    lejos = _tarjeta(dia_pago=25)
    sin_deuda = _tarjeta(dia_pago=5, saldo=0)
    hoy = datetime(2026, 10, 3)
    assert [c for c, _ in tarjetas_por_avisar([cerca, lejos, sin_deuda], hoy)] == [cerca]
    cerca.ultima_alerta_pago = "2026-10-05"  # ya avisada para ese pago
    assert tarjetas_por_avisar([cerca], hoy) == []


# ── Tarjetas: API y cron ──────────────────────────────

def test_crear_y_editar_tarjeta_por_api():
    r = client.post("/cuentas", json={
        "nombre": "Visa Bancolombia", "tipo": "credito", "saldo": -500000,
        "cupo_total": 2000000, "dia_corte": 10, "dia_pago": 25, "tasa_ea": 28.5,
    })
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["tarjeta"]["utilizacion_pct"] == 25.0 and c["tarjeta"]["nivel_utilizacion"] == "ok"
    assert c["tarjeta"]["proximo_pago"] is not None

    r = client.put(f"/cuentas/{c['id']}", json={"cupo_total": 1000000, "dia_pago": 20})
    assert r.json()["tarjeta"]["utilizacion_pct"] == 50.0
    assert r.json()["dia_pago"] == 20

    # días fuera de rango se rechazan
    assert client.put(f"/cuentas/{c['id']}", json={"dia_corte": 40}).status_code == 422

    # una cuenta normal no trae bloque de tarjeta
    n = client.post("/cuentas", json={"nombre": "Ahorros", "tipo": "ahorro"}).json()
    assert n["tarjeta"] is None
    assert any(x["id"] == c["id"] for x in client.get("/cuentas").json())


def test_cron_avisa_pago_de_tarjeta_una_sola_vez():
    from app.utiles import ahora_co

    dia_pago = ahora_co().day  # el pago es hoy -> dentro de la ventana de aviso
    db = SessionLocal()
    try:
        db.add(Cuenta(usuario_id="u-tc-cron", nombre="Master", tipo="credito", saldo=-400000,
                      cupo_total=1000000, dia_corte=1, dia_pago=dia_pago))
        db.add(PushSubscription(usuario_id="u-tc-cron", endpoint="https://push.test/tc", p256dh="x", auth="y"))
        db.commit()
    finally:
        db.close()
    primera = client.post("/push/cron/recordar-recurrentes", headers=CABECERA).json()
    segunda = client.post("/push/cron/recordar-recurrentes", headers=CABECERA).json()
    assert primera["tarjetas_avisadas"] == 1
    assert segunda["tarjetas_avisadas"] == 0


# ── Estrategia de deudas ──────────────────────────────

DEUDAS = [
    {"id": "a", "nombre": "Tarjeta", "saldo": 1_000_000, "tasa_mensual": 3.0, "cuota": 60_000},   # alta tasa, saldo medio
    {"id": "b", "nombre": "Préstamo", "saldo": 400_000, "tasa_mensual": 1.0, "cuota": 40_000},   # menor saldo, baja tasa
    {"id": "c", "nombre": "Libre inversión", "saldo": 3_000_000, "tasa_mensual": 1.5, "cuota": 120_000},
]


def test_una_deuda_sin_interes_es_exacta():
    r = simular([{"id": "x", "nombre": "Amigo", "saldo": 1000, "tasa_mensual": 0, "cuota": 100}], 0, "avalancha")
    assert r["meses"] == 10 and r["intereses_totales"] == 0
    r = simular([{"id": "x", "nombre": "Amigo", "saldo": 1000, "tasa_mensual": 0, "cuota": 100}], 100, "avalancha")
    assert r["meses"] == 5


def test_el_orden_de_cada_metodo():
    av = simular(DEUDAS, 100_000, "avalancha")
    bn = simular(DEUDAS, 100_000, "bola_de_nieve")
    # bola de nieve liquida primero la de menor saldo (b)
    assert bn["orden"][0]["id"] == "b"
    # avalancha apunta a la de mayor tasa (a) con el extra, así que a cae antes que en bola de nieve
    mes_a_av = next(o["mes_libre"] for o in av["orden"] if o["id"] == "a")
    mes_a_bn = next(o["mes_libre"] for o in bn["orden"] if o["id"] == "a")
    assert mes_a_av <= mes_a_bn


def test_avalancha_paga_menos_intereses_y_extra_ahorra_frente_a_base():
    hoy = datetime(2026, 10, 3)
    res = comparar_estrategias(DEUDAS, 150_000, hoy)
    assert res["avalancha"]["intereses_totales"] <= res["bola_de_nieve"]["intereses_totales"]
    assert res["mejor"] == "avalancha"
    assert res["avalancha"]["ahorro_intereses"] > 0
    assert res["avalancha"]["meses"] < res["sin_extra"]["meses"]
    assert res["avalancha"]["meses_ahorrados"] == res["sin_extra"]["meses"] - res["avalancha"]["meses"]
    assert res["deuda_total"] == 4_400_000
    # la deuda total baja mes a mes hasta 0
    serie = res["avalancha"]["saldo_por_mes"]
    assert serie[0] == 4_400_000 and serie[-1] == 0
    assert all(a >= b for a, b in zip(serie, serie[1:]))
    # fecha libre = hoy + meses
    meses = res["avalancha"]["meses"]
    total = 2026 * 12 + 9 + meses
    assert res["avalancha"]["fecha_libre"] == f"{total // 12}-{total % 12 + 1:02d}"


def test_sin_extra_los_metodos_coinciden_con_la_base():
    res = comparar_estrategias(DEUDAS, 0, datetime(2026, 10, 3))
    # con extra 0 el efecto bola de nieve (reasignar cuotas liberadas) sigue
    # siendo igual o mejor que la base, nunca peor
    assert res["avalancha"]["intereses_totales"] <= res["sin_extra"]["intereses_totales"]
    assert res["bola_de_nieve"]["meses"] <= res["sin_extra"]["meses"]


def test_cuota_menor_al_interes_no_termina():
    imposible = [{"id": "z", "nombre": "Usura", "saldo": 1_000_000, "tasa_mensual": 5.0, "cuota": 10_000}]
    res = comparar_estrategias(imposible, 0, datetime(2026, 10, 3))
    assert res["sin_extra"]["meses"] is None and res["sin_extra"]["fecha_libre"] is None
    assert res["avalancha"]["ahorro_intereses"] is None
    # con extra suficiente sí termina
    res = comparar_estrategias(imposible, 200_000, datetime(2026, 10, 3))
    assert res["avalancha"]["meses"] is not None


def test_sin_deudas_y_cuota_vacia():
    res = comparar_estrategias([], 100_000, datetime(2026, 10, 3))
    assert res["deuda_total"] == 0 and res["avalancha"]["meses"] == 0
    # cuota 0: se asume interés + 1% del saldo, así que termina
    r = simular([{"id": "q", "nombre": "Sin cuota", "saldo": 100_000, "tasa_mensual": 2.0, "cuota": 0}], 0, "avalancha")
    assert r["meses"] is not None


def test_endpoint_estrategia():
    db = SessionLocal()
    try:
        db.add(Deuda(usuario_id="user-tc", nombre="Visa", saldo_inicial=1_000_000, saldo_actual=1_000_000,
                     tasa_mensual=2.5, cuota_mensual=80_000))
        db.add(Deuda(usuario_id="user-tc", nombre="Moto", saldo_inicial=500_000, saldo_actual=500_000,
                     tasa_mensual=1.2, cuota_mensual=50_000))
        db.add(Deuda(usuario_id="otro", nombre="Ajena", saldo_inicial=9, saldo_actual=9, cuota_mensual=1))
        db.commit()
    finally:
        db.close()
    r = client.get("/deudas/estrategia?extra=100000")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["deuda_total"] == 1_500_000  # no incluye deudas de otro usuario
    assert data["avalancha"]["ahorro_intereses"] > 0
    assert data["mejor"] in ("avalancha", "bola_de_nieve")
    assert client.get("/deudas/estrategia?extra=-5").status_code == 422
