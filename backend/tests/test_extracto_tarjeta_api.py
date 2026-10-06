"""Del extracto de la tarjeta a la propuesta 'Tu extracto dice...' y a aplicarla.
Textos INVENTADOS: validan la lógica, no el formato de un banco real."""
import os
import tempfile
from datetime import datetime
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'extapi.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.tarjetas import calc_tarjeta, estado_extracto, tarjetas_por_avisar  # noqa: E402
from datetime import date  # noqa: E402

client = TestClient(app)

TEXTO = """Extracto tarjeta de crédito Nu
Cupo total: $5.000.000
Cupo disponible: $3.120.500
Pago total: $1.879.500
Pago mínimo: $187.950
Fecha límite de pago: 30 de octubre de 2026
Fecha de corte: 15 de octubre de 2026
Tasa efectiva anual: 27,86% E.A.
"""


@pytest.fixture(autouse=True)
def _usuario():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-extapi", email="e@t.com", nombre="E")
    yield


def _procesar(monkeypatch, cuenta_id, texto=TEXTO):
    from app.routers import conciliacion as mod
    monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: texto)
    monkeypatch.setattr(mod, "detectar_banco", lambda t: "nu")
    items = [{"fecha": "2026-10-10", "descripcion": "EXITO", "monto": 50_000, "tipo": "expense", "referencia": ""}]
    monkeypatch.setattr(mod, "parse_texto_con_regex", lambda t: (items, 0))
    return client.post("/conciliacion/procesar", json={"cuenta_id": cuenta_id, "pdf_base64": "x"})


def test_extracto_de_una_tarjeta_trae_propuesta_y_no_cambia_nada(monkeypatch):
    c = client.post("/cuentas", json={"nombre": "Nu Crédito", "tipo": "credito", "saldo": -1_000_000,
                                      "cupo_total": 4_000_000, "dia_corte": 15, "dia_pago": 28}).json()
    r = _procesar(monkeypatch, c["id"])
    assert r.status_code == 200, r.text
    p = r.json()["propuesta_tarjeta"]
    assert p["cambios"] == {"cupo_total": 5_000_000, "dia_pago": 30, "tasa_ea": 27.86}
    assert p["texto"].startswith("Tu extracto dice: cupo $5.000.000, pago total $1.879.500")
    # NUNCA se aplica solo
    despues = next(x for x in client.get("/cuentas").json() if x["id"] == c["id"])
    assert despues["cupo_total"] == 4_000_000 and despues["dia_pago"] == 28 and despues["tasa_ea"] is None


def test_extracto_de_una_cuenta_normal_no_trae_propuesta(monkeypatch):
    n = client.post("/cuentas", json={"nombre": "Ahorros Ext", "saldo": 100_000}).json()
    assert _procesar(monkeypatch, n["id"]).json()["propuesta_tarjeta"] is None


def test_extracto_sin_datos_legibles_no_trae_propuesta(monkeypatch):
    c = client.post("/cuentas", json={"nombre": "Visa Vacia", "tipo": "credito"}).json()
    assert _procesar(monkeypatch, c["id"], "movimientos sin datos de resumen").json()["propuesta_tarjeta"] is None


def test_aplicar_actualiza_la_tarjeta_y_guarda_el_pago_minimo_real():
    c = client.post("/cuentas", json={"nombre": "Nu Aplicar", "tipo": "credito", "saldo": -1_879_500,
                                      "cupo_total": 4_000_000, "dia_corte": 15, "dia_pago": 28}).json()
    r = client.post(f"/tarjetas/{c['id']}/aplicar-extracto", json={
        "cupo_total": 5_000_000, "dia_pago": 30, "tasa_ea": 27.86,
        "pago_total": 1_879_500, "pago_minimo": 187_950, "fecha_limite_pago": "2099-12-30", "fecha_corte": "2099-12-15",
    })
    assert r.status_code == 200, r.text
    assert set(r.json()["cambiadas"]) == {"cupo_total", "dia_pago", "tasa_ea"}
    t = next(x for x in client.get("/cuentas").json() if x["id"] == c["id"])
    assert t["cupo_total"] == 5_000_000 and t["dia_pago"] == 30 and t["tasa_ea"] == 27.86
    assert t["tarjeta"]["pago_minimo"] == 187_950 and t["tarjeta"]["pago_minimo_del_extracto"] is True
    # una cuenta normal o ajena no se puede
    n = client.post("/cuentas", json={"nombre": "Ahorros Aplicar"}).json()
    assert client.post(f"/tarjetas/{n['id']}/aplicar-extracto", json={"cupo_total": 1}).status_code == 404
    assert client.post(f"/tarjetas/{c['id']}/aplicar-extracto", json={"dia_pago": 40}).status_code == 422


# ── el extracto real manda sobre la estimación (función pura, fechas fijas) ──

def test_total_del_banco_reemplaza_al_calculado_si_es_el_mismo_ciclo():
    movs = []  # sin movimientos tras el corte: deuda al corte = deuda de hoy = 1.800.000
    guardado = {"pago_total": 1_879_500, "pago_minimo": 187_950, "fecha_limite_pago": "2026-10-30"}
    e = estado_extracto(-1_800_000, movs, 15, 30, date(2026, 10, 20), guardado)
    assert e["total_extracto"] == 1_879_500 and e["total_del_banco"] is True  # incluye intereses/cargos del banco
    assert e["falta_para_evitar_intereses"] == 1_879_500 and e["pago_minimo_extracto"] == 187_950
    # de otro ciclo (fecha límite distinta) se ignora el total pero el mínimo vigente se conserva
    e2 = estado_extracto(-1_800_000, movs, 15, 30, date(2026, 10, 20), {**guardado, "fecha_limite_pago": "2026-11-30"})
    assert e2["total_extracto"] == 1_800_000 and e2["total_del_banco"] is False
    # vencido el extracto guardado: ya no vale
    e3 = estado_extracto(-1_800_000, movs, 15, 30, date(2026, 11, 2), guardado)
    assert e3["pago_minimo_extracto"] is None and e3["total_del_banco"] is False


def test_calc_tarjeta_prefiere_el_pago_minimo_del_extracto():
    c = SimpleNamespace(saldo=-1_800_000, cupo_total=5_000_000, dia_corte=15, dia_pago=30, tasa_ea=None)
    hoy = datetime(2026, 10, 20)
    sin = calc_tarjeta(c, hoy, [], None)
    assert sin["pago_minimo"] == sin["pago_minimo_estimado"] == 90_000 and sin["pago_minimo_del_extracto"] is False  # 5%
    con = calc_tarjeta(c, hoy, [], {"pago_total": 1_879_500, "pago_minimo": 187_950, "fecha_limite_pago": "2026-10-30"})
    assert con["pago_minimo"] == 187_950 and con["pago_minimo_del_extracto"] is True


def test_texto_del_push_con_dias_monto_y_pago_minimo_del_extracto(monkeypatch):
    from app.routers import push as mod
    enviados = []
    monkeypatch.setattr(mod, "enviar_push", lambda db, uid, titulo, cuerpo, url: enviados.append((titulo, cuerpo)))
    db = SimpleNamespace(commit=lambda: None)
    cuenta = SimpleNamespace(usuario_id="u", nombre="Nu", ultima_alerta_pago=None)
    info = {"dias_aviso": 2, "monto_aviso": 1_379_500, "fecha_aviso": "2026-10-30", "pago_minimo": 187_950,
            "pago_minimo_del_extracto": True}
    mod._avisar_pago_tarjeta(db, cuenta, info)
    assert enviados[0] == ("Paga tu Nu", "Te quedan 2 días para el pago: paga 1,379,500 antes del 2026-10-30 "
                                         "para no pagar intereses. Pago mínimo del extracto: 187,950")
    assert cuenta.ultima_alerta_pago == "2026-10-30"
    # el día del pago y sin mínimo conocido
    mod._avisar_pago_tarjeta(db, cuenta, {**info, "dias_aviso": 0, "pago_minimo_del_extracto": False})
    assert enviados[1][1] == "Hoy vence el pago: paga 1,379,500 antes del 2026-10-30 para no pagar intereses"


def test_el_aviso_usa_el_total_del_banco_menos_lo_pagado():
    def mov(dia, tipo, monto):
        return SimpleNamespace(fecha=datetime(2026, 10, dia, 12), tipo=tipo, monto=monto, fuente="manual", notas="")

    t =SimpleNamespace(id="t9", tipo="credito", saldo=-1_379_500, cupo_total=5_000_000, dia_corte=15, dia_pago=30,
                        tasa_ea=None, ultima_alerta_pago=None, nombre="Nu", usuario_id="u")
    movs = {"t9": [mov(20, "income", 500_000)]}  # abonó 500.000 después del corte
    g = {"t9": {"pago_total": 1_879_500, "pago_minimo": 187_950, "fecha_limite_pago": "2026-10-30"}}
    lista = tarjetas_por_avisar([t], datetime(2026, 10, 28), movs, g)
    assert lista[0][1]["monto_aviso"] == 1_379_500  # 1.879.500 - 500.000
    assert lista[0][1]["pago_minimo"] == 187_950
