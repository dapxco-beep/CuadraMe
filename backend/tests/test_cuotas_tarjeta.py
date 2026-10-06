"""Compras a cuotas con tarjeta: fórmula, fechas, estado del plan, API y compromiso del mes.
Las cifras están hechas a mano."""
import os
import tempfile
from datetime import date

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'cuo.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.cuotas import (  # noqa: E402
    calcular_cuota, capital_pendiente, cuota_en_mes, estado_plan, fechas_corte_cuotas, primera_fecha_por_defecto,
)
from app.main import app  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _usuario():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-cuo", email="c@t.com", nombre="C")
    yield


# ── fórmula ──

def test_sin_interes_se_divide_en_partes_iguales():
    assert calcular_cuota(1_200_000, 12, 0) == 100_000


def test_formula_francesa_mil_millones_al_dos_por_ciento():
    # 1.000.000 * 0,02 / (1 - 1,02^-12) = 94.559,5966... -> 94.560 al peso
    c = calcular_cuota(1_000_000, 12, 2)
    assert abs(c - 94_559.5966) < 0.01
    assert round(c) == 94_560


def test_un_plan_de_una_cuota_es_el_total_mas_un_mes_de_interes():
    assert calcular_cuota(500_000, 1, 0) == 500_000
    assert abs(calcular_cuota(500_000, 1, 2) - 510_000) < 0.01


def test_cuotas_invalidas():
    with pytest.raises(ValueError):
        calcular_cuota(100, 0, 0)


def test_capital_pendiente():
    assert capital_pendiente(1_200_000, 12, 0, 3) == 900_000
    assert capital_pendiente(1_000_000, 12, 2, 0) == pytest.approx(1_000_000, abs=1)
    # tras la 1ª cuota: 1.000.000 * 1,02 - 94.559,60 = 925.440,40
    assert capital_pendiente(1_000_000, 12, 2, 1) == pytest.approx(925_440.4, abs=1)
    assert capital_pendiente(1_000_000, 12, 2, 12) == 0


# ── fechas ──

def test_cortes_conservan_el_dia_y_se_ajustan_en_meses_cortos():
    assert fechas_corte_cuotas(date(2027, 1, 31), 3) == [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31)]
    assert fechas_corte_cuotas(date(2026, 11, 15), 3) == [date(2026, 11, 15), date(2026, 12, 15), date(2027, 1, 15)]


def test_la_primera_cuota_cae_en_el_proximo_corte():
    assert primera_fecha_por_defecto(15, date(2026, 10, 10)) == date(2026, 10, 15)
    assert primera_fecha_por_defecto(15, date(2026, 10, 20)) == date(2026, 11, 15)
    assert primera_fecha_por_defecto(None, date(2026, 10, 20)) == date(2026, 11, 20)


# ── estado del plan (corte 15, pago 30) ──

PLAN = dict(total=1_200_000, n=12, cuota=100_000, tasa=0, primera=date(2026, 10, 15), dia_pago=30)


def _est(hoy, manual=0):
    return estado_plan(PLAN["total"], PLAN["n"], PLAN["cuota"], PLAN["tasa"], manual, PLAN["primera"], hoy, PLAN["dia_pago"])


def test_plan_recien_creado():
    e = _est(date(2026, 10, 20))
    assert e["pagadas"] == 0 and e["numero_actual"] == 1 and e["pendientes"] == 12
    assert e["saldo_pendiente"] == 1_200_000 and e["por_pagar"] == 1_200_000
    assert e["proxima_fecha_pago"] == "2026-10-30" and e["vence_este_mes"] is True
    assert e["termina_en"] == "2027-09" and e["terminado"] is False


def test_las_cuotas_se_marcan_solas_al_pasar_su_fecha_de_pago():
    # pagos: 30 oct, 30 nov, 30 dic. El 31 dic ya pasaron las tres: va en la 4 de 12.
    e = _est(date(2026, 12, 31))
    assert e["pagadas"] == 3 and e["numero_actual"] == 4
    assert e["saldo_pendiente"] == 900_000 and e["por_pagar"] == 900_000
    assert e["proxima_fecha_pago"] == "2027-01-30" and e["vence_este_mes"] is False
    # el mismo día del pago todavía no cuenta como pagada (puede pagar ese día)
    assert _est(date(2026, 10, 30))["pagadas"] == 0
    assert _est(date(2026, 10, 31))["pagadas"] == 1


def test_marcar_a_mano_adelanta_y_nunca_retrocede():
    assert _est(date(2026, 10, 20), manual=5)["pagadas"] == 5
    assert _est(date(2026, 12, 31), manual=1)["pagadas"] == 3  # lo automático manda si es mayor


def test_plan_terminado():
    e = _est(date(2027, 10, 1))
    assert e["terminado"] is True and e["pagadas"] == 12 and e["saldo_pendiente"] == 0
    assert e["proxima_fecha_pago"] is None and e["vence_este_mes"] is False


def test_cuota_en_mes():
    primera = date(2026, 10, 15)
    assert cuota_en_mes(12, 100_000, 0, primera, 2026, 10, 30) == 100_000
    assert cuota_en_mes(12, 100_000, 0, primera, 2026, 11, 30) == 100_000
    assert cuota_en_mes(12, 100_000, 0, primera, 2027, 10, 30) == 0  # ya terminó
    assert cuota_en_mes(12, 100_000, 1, primera, 2026, 10, 30) == 0  # la de octubre ya se pagó


# ── API ──

def _tarjeta(**kw):
    body = {"nombre": "Visa Cuotas", "tipo": "credito", "saldo": -1_200_000, "cupo_total": 5_000_000,
            "dia_corte": 1, "dia_pago": 31}
    body.update(kw)
    r = client.post("/cuentas", json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_crud_de_cuotas_no_toca_el_saldo_de_la_tarjeta():
    cid = _tarjeta(nombre="Visa API")
    r = client.post("/cuotas-tarjeta", json={"cuenta_id": cid, "descripcion": "Nevera", "total": 1_200_000, "num_cuotas": 12})
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["cuota_mensual"] == 100_000 and plan["pagadas"] == 0 and plan["numero_actual"] == 1
    assert plan["tasa_mensual"] == 0 and plan["terminado"] is False

    con_interes = client.post("/cuotas-tarjeta", json={
        "cuenta_id": cid, "descripcion": "TV", "total": 1_000_000, "num_cuotas": 12, "tasa_mensual": 2,
    }).json()
    assert con_interes["cuota_mensual"] == 94_560

    lista = client.get(f"/cuotas-tarjeta?cuenta_id={cid}").json()
    assert {p["descripcion"] for p in lista["planes"]} == {"Nevera", "TV"}

    marcada = client.post(f"/cuotas-tarjeta/{plan['id']}/pagar-cuota").json()
    assert marcada["pagadas"] >= 1 and marcada["numero_actual"] == marcada["pagadas"] + 1
    editada = client.put(f"/cuotas-tarjeta/{plan['id']}", json={"descripcion": "Nevera LG"}).json()
    assert editada["descripcion"] == "Nevera LG"

    assert client.delete(f"/cuotas-tarjeta/{con_interes['id']}").json() == {"ok": True}
    assert len(client.get(f"/cuotas-tarjeta?cuenta_id={cid}").json()["planes"]) == 1

    tarjeta = next(c for c in client.get("/cuentas").json() if c["id"] == cid)
    assert tarjeta["saldo"] == -1_200_000  # nada de esto movió el saldo


def test_solo_tarjetas_propias_y_datos_validos():
    ahorro = client.post("/cuentas", json={"nombre": "Ahorros Cuotas", "tipo": "ahorro"}).json()["id"]
    assert client.post("/cuotas-tarjeta", json={"cuenta_id": ahorro, "descripcion": "x", "total": 100, "num_cuotas": 2}).status_code == 404
    cid = _tarjeta(nombre="Visa Valida")
    assert client.post("/cuotas-tarjeta", json={"cuenta_id": cid, "descripcion": "x", "total": 100, "num_cuotas": 0}).status_code == 422
    assert client.post("/cuotas-tarjeta", json={"cuenta_id": cid, "descripcion": "x", "total": -5, "num_cuotas": 3}).status_code == 422
    # un plan de otro usuario no se ve ni se toca
    plan = client.post("/cuotas-tarjeta", json={"cuenta_id": cid, "descripcion": "mio", "total": 300, "num_cuotas": 3}).json()
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="otro", email="o@t.com", nombre="O")
    assert client.delete(f"/cuotas-tarjeta/{plan['id']}").status_code == 404
    assert client.get("/cuotas-tarjeta").json()["planes"] == []


def test_el_compromiso_del_mes_alimenta_el_bolsillo_y_el_flujo_de_caja_solo_si_se_pide():
    hoy = ahora_co()
    cid = _tarjeta(nombre="Visa Bolsillo")
    # Plan de 100.000 con corte el día 1 del mes actual y pago el último día: vence este mes.
    primera = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    r = client.post("/cuotas-tarjeta", json={
        "cuenta_id": cid, "descripcion": "Compromiso", "total": 1_200_000, "num_cuotas": 12,
        "primera_fecha": primera.isoformat(),
    })
    assert r.status_code == 200, r.text

    base = client.get("/presupuestos/en-mi-bolsillo").json()
    con = client.get("/presupuestos/en-mi-bolsillo?incluir_cuotas=true").json()
    assert base["cuotas_tarjeta_mes"] >= 100_000  # (otros planes de pruebas anteriores también suman)
    assert con["disponible_real"] == base["disponible_real"] - base["cuotas_tarjeta_mes"]

    f0 = client.get("/reportes/flujo-caja-futuro?meses=2").json()
    f1 = client.get("/reportes/flujo-caja-futuro?meses=2&incluir_cuotas=true").json()
    assert f0["meses"][0]["cuotas_tarjeta"] >= 100_000
    cuotas = f0["meses"][0]["cuotas_tarjeta"]
    assert f1["meses"][0]["gastos_esperados"] == f0["meses"][0]["gastos_esperados"] + cuotas
    assert f0["meses"][0]["gastos_esperados"] == f0["meses"][1]["gastos_esperados"]  # por defecto no se suman
