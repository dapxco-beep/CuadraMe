"""Pago para no pagar intereses = deuda al último corte (no el cupo usado de hoy).
Todas las cifras están hechas a mano con fechas fijas."""
import os
import tempfile
from datetime import date, datetime, timedelta
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'extr.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.tarjetas import (  # noqa: E402
    calc_tarjeta, estado_extracto, limite_pago_del_corte, tarjetas_por_avisar, ultimo_corte,
)
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _usuario():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-extr", email="e@t.com", nombre="E")
    yield


def mov(dia, tipo, monto, mes=10, anio=2026, fuente="manual", notas=""):
    return SimpleNamespace(fecha=datetime(anio, mes, dia, 12, 0), tipo=tipo, monto=monto, fuente=fuente, notas=notas)


# ── fechas ──

def test_ultimo_corte_y_limite_de_pago():
    assert ultimo_corte(15, date(2026, 10, 20)) == date(2026, 10, 15)
    assert ultimo_corte(15, date(2026, 10, 15)) == date(2026, 10, 15)  # el día del corte ya cerró
    assert ultimo_corte(15, date(2026, 10, 10)) == date(2026, 9, 15)
    assert ultimo_corte(31, date(2027, 3, 5)) == date(2027, 2, 28)  # mes corto: se ajusta
    assert ultimo_corte(25, date(2027, 1, 5)) == date(2026, 12, 25)  # cambio de año
    assert limite_pago_del_corte(date(2026, 10, 15), 30) == date(2026, 10, 30)  # pago el mismo mes
    assert limite_pago_del_corte(date(2026, 10, 25), 10) == date(2026, 11, 10)  # pago al mes siguiente
    assert limite_pago_del_corte(date(2026, 12, 25), 10) == date(2027, 1, 10)  # y pasa de año
    assert limite_pago_del_corte(date(2027, 2, 28), 15) == date(2027, 3, 15)
    assert limite_pago_del_corte(date(2027, 2, 15), 30) == date(2027, 2, 28)  # 30 de febrero -> 28


# ── extracto ──

def test_extracto_con_compras_antes_y_despues_del_corte_y_un_abono_parcial():
    # Deuda al corte (15 oct): 1.000.000. Después: compra 200.000 (17), abono 300.000 (18),
    # compra 50.000 (19). Saldo de hoy = -(1.000.000 + 200.000 + 50.000 - 300.000) = -950.000.
    # La compra del 10 de oct es anterior al corte y ya está en el saldo: no se pasa.
    movs = [mov(17, "expense", 200_000), mov(18, "income", 300_000), mov(19, "expense", 50_000)]
    e = estado_extracto(-950_000, movs, 15, 30, date(2026, 10, 20))
    assert e["total_extracto"] == 1_000_000
    assert e["pagado_desde_corte"] == 300_000
    assert e["falta_para_evitar_intereses"] == 700_000
    assert e["compras_despues_corte"] == 250_000
    assert e["fecha_limite_pago"] == "2026-10-30"
    assert e["fecha_ultimo_corte"] == "2026-10-15"
    assert e["dias_para_limite"] == 10
    assert e["pagado_pct"] == 30.0
    assert e["vencido"] is False


def test_un_movimiento_del_dia_del_corte_entra_al_extracto_no_al_siguiente():
    e = estado_extracto(-1_000_000, [mov(15, "expense", 100_000)], 15, 30, date(2026, 10, 20))
    # el del día 15 no es "después del corte": el total es la deuda de hoy
    assert e["total_extracto"] == 1_000_000 and e["compras_despues_corte"] == 0


def test_pagar_de_mas_no_deja_falta_negativa_y_el_total_pagado_se_topa():
    movs = [mov(18, "income", 1_200_000)]
    e = estado_extracto(200_000, movs, 15, 30, date(2026, 10, 20))  # saldo a favor tras sobrepagar
    # saldo al corte = 200.000 - 1.200.000 = -1.000.000
    assert e["total_extracto"] == 1_000_000
    assert e["falta_para_evitar_intereses"] == 0
    assert e["pagado_desde_corte"] == 1_000_000 and e["pagado_pct"] == 100.0


def test_sin_deuda_al_corte():
    e = estado_extracto(-80_000, [mov(18, "expense", 80_000)], 15, 30, date(2026, 10, 20))
    assert e["total_extracto"] == 0 and e["falta_para_evitar_intereses"] == 0
    assert e["compras_despues_corte"] == 80_000 and e["pagado_pct"] is None


def test_el_traslado_a_la_tarjeta_cuenta_como_pago_y_el_ajuste_no_es_compra():
    movs = [
        mov(18, "transfer", 400_000, fuente="transferencia_interna", notas="TRF:g1:in"),
        mov(19, "expense", 30_000, fuente="ajuste_saldo"),
        mov(19, "transfer", 99_000, fuente="importado"),  # transfer de extracto: no movió saldo
    ]
    # saldo hoy = -(1.000.000 - 400.000 + 30.000) = -630.000
    e = estado_extracto(-630_000, movs, 15, 30, date(2026, 10, 20))
    assert e["total_extracto"] == 1_000_000
    assert e["pagado_desde_corte"] == 400_000
    assert e["compras_despues_corte"] == 0  # el ajuste no es una compra
    assert e["falta_para_evitar_intereses"] == 600_000


def test_mes_corto_corte_31_y_febrero():
    # Corte 31 -> 28 feb 2027; pago 15 -> 15 mar. Compra el 3 de marzo va al próximo extracto.
    e = estado_extracto(-1_500_000, [mov(3, "expense", 500_000, mes=3, anio=2027)], 31, 15, date(2027, 3, 5))
    assert e["fecha_ultimo_corte"] == "2027-02-28"
    assert e["total_extracto"] == 1_000_000 and e["compras_despues_corte"] == 500_000
    assert e["fecha_limite_pago"] == "2027-03-15" and e["dias_para_limite"] == 10


def test_cambio_de_anio():
    # hoy 5 ene 2027, corte 25 / pago 10: corte 25 dic 2026, pago 10 ene 2027
    e = estado_extracto(-700_000, [mov(2, "expense", 100_000, mes=1, anio=2027)], 25, 10, date(2027, 1, 5))
    assert e["fecha_ultimo_corte"] == "2026-12-25"
    assert e["total_extracto"] == 600_000
    assert e["fecha_limite_pago"] == "2027-01-10" and e["dias_para_limite"] == 5


def test_vencido_cuando_pasa_el_limite_sin_pagar():
    e = estado_extracto(-1_000_000, [], 15, 30, date(2026, 11, 3))  # hoy 3 nov: aún no llega el corte del 15 nov
    assert e["fecha_ultimo_corte"] == "2026-10-15" and e["dias_para_limite"] == -4 and e["vencido"] is True


def test_sin_dia_de_corte_todo_en_none():
    e = estado_extracto(-500_000, [], None, 30, date(2026, 10, 20))
    assert e["total_extracto"] is None and e["falta_para_evitar_intereses"] is None


def test_calc_tarjeta_incluye_extracto_solo_si_recibe_movimientos():
    c = SimpleNamespace(saldo=-950_000, cupo_total=2_000_000, dia_corte=15, dia_pago=30, tasa_ea=None)
    sin = calc_tarjeta(c, datetime(2026, 10, 20))
    assert sin["total_extracto"] is None and sin["cupo_usado"] == 950_000
    con = calc_tarjeta(c, datetime(2026, 10, 20), [mov(17, "expense", 200_000), mov(18, "income", 300_000), mov(19, "expense", 50_000)])
    assert con["total_extracto"] == 1_000_000 and con["falta_para_evitar_intereses"] == 700_000


# ── aviso push ──

def _t(**kw):
    base = dict(id="t1", tipo="credito", saldo=-950_000, cupo_total=2_000_000, dia_corte=15, dia_pago=30,
                tasa_ea=None, ultima_alerta_pago=None, nombre="Visa", usuario_id="u")
    base.update(kw)
    return SimpleNamespace(**base)


def test_aviso_usa_lo_que_falta_y_no_el_cupo_usado():
    movs = {"t1": [mov(17, "expense", 200_000), mov(18, "income", 300_000), mov(19, "expense", 50_000)]}
    lista = tarjetas_por_avisar([_t()], datetime(2026, 10, 28), movs)
    assert len(lista) == 1
    info = lista[0][1]
    assert info["monto_aviso"] == 700_000  # NO 950.000 (cupo usado)
    assert info["fecha_aviso"] == "2026-10-30" and info["dias_aviso"] == 2
    # 10 días antes todavía no toca
    assert tarjetas_por_avisar([_t()], datetime(2026, 10, 20), movs) == []


def test_aviso_no_sale_si_el_extracto_ya_esta_pagado():
    movs = {"t1": [mov(20, "income", 1_000_000)]}
    t = _t(saldo=0)  # deuda al corte 1.000.000, pagada entera
    assert tarjetas_por_avisar([t], datetime(2026, 10, 28), movs) == []


def test_aviso_no_se_repite_para_el_mismo_pago():
    movs = {"t1": [mov(17, "expense", 50_000)]}
    t = _t(saldo=-1_050_000, ultima_alerta_pago="2026-10-30")
    assert tarjetas_por_avisar([t], datetime(2026, 10, 28), movs) == []


# ── API ──

def test_api_de_cuentas_trae_el_extracto():
    hoy = ahora_co()
    corte = (hoy - timedelta(days=2)).day  # el corte fue hace dos días
    r = client.post("/cuentas", json={
        "nombre": "Visa Extracto", "tipo": "credito", "saldo": -1_000_000, "cupo_total": 5_000_000,
        "dia_corte": corte, "dia_pago": min(28, corte),  # el pago exacto da igual aquí
    })
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert client.post("/movimientos", json={"cuenta_id": cid, "descripcion": "Compra", "monto": 200_000, "tipo": "expense"}).status_code == 200
    assert client.post("/movimientos", json={"cuenta_id": cid, "descripcion": "Abono", "monto": 300_000, "tipo": "income"}).status_code == 200
    t = next(c for c in client.get("/cuentas").json() if c["id"] == cid)["tarjeta"]
    # saldo hoy = -900.000; deuda al corte = 1.000.000; abonado 300.000
    assert t["cupo_usado"] == 900_000
    assert t["total_extracto"] == 1_000_000
    assert t["pagado_desde_corte"] == 300_000
    assert t["falta_para_evitar_intereses"] == 700_000
    assert t["compras_despues_corte"] == 200_000
    d = client.get(f"/cuentas/{cid}/detalle").json()["cuenta"]["tarjeta"]
    assert d["falta_para_evitar_intereses"] == 700_000
