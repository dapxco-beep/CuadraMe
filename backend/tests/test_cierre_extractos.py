"""Cierre de mes contra el extracto, por banco. Datos 100 % inventados.

Dos bancos (Alfa y Beta) más una tarjeta de Alfa, con extractos encadenados de mayo a junio:
  Alfa (ahorros)  mayo: 500.000 -> 700.000 (+300.000 -100.000)   junio: 700.000 -> 950.000 (+400.000 -150.000)
                  julio: sin extracto (movimientos: -50.000)
  Beta (ahorros)  mayo: 100.000 -> 160.000 (+80.000 -20.000)      junio: 160.000 -> 260.000 pero la app suma +60.000
                  (faltan 40.000 por importar)
"""
import json
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'cierre_ext.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import informe  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.informe_datos import cargar_movs_efectivos  # noqa: E402
from app.main import app  # noqa: E402
from app.models import HistorialExtracto  # noqa: E402

client = TestClient(app)
USUARIO = {"u": UsuarioActual(id="cie-0", email="c@test.com", nombre="Cie")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["u"]
    yield


def como(uid):
    USUARIO["u"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def _mov(cuenta, tipo, monto, fecha, desc="x", categoria="Otros"):
    r = client.post("/movimientos", json={"cuenta_id": cuenta, "tipo": tipo, "monto": monto, "descripcion": desc,
                                          "categoria": categoria, "fecha": fecha, "confirmar_nuevo": True})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _hist(uid, cuenta, *, ini, fin, inicio, corte, review=None):
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta, banco_detectado="prueba", estado="pendiente_revision",
                              review_json=json.dumps(review or []), saldo_inicial_extracto=ini, saldo_final_extracto=fin,
                              periodo_inicio=inicio, fecha_corte=corte, saldos_origen="extracto")
        db.add(h)
        db.commit()
        return h.id
    finally:
        db.close()


FALTA = {"fecha": "2026-06-20", "descripcion": "Abono prueba", "monto": 40_000, "tipo": "income",
         "fingerprint": "fp-40", "estado": "faltante", "referencia": ""}


def _escenario(uid):
    como(uid)
    alfa = client.post("/cuentas", json={"nombre": "Alfa Ahorros", "tipo": "ahorro", "saldo": 0}).json()["id"]
    beta = client.post("/cuentas", json={"nombre": "Beta", "tipo": "ahorro", "saldo": 0}).json()["id"]
    tarj = client.post("/cuentas", json={"nombre": "Alfa Tarjeta", "tipo": "credito", "saldo": 0}).json()["id"]
    _mov(alfa, "income", 300_000, "2026-05-05T10:00:00", "Pago")
    _mov(alfa, "expense", 100_000, "2026-05-10T10:00:00", "Compra")
    _mov(alfa, "income", 400_000, "2026-06-03T10:00:00", "Pago")
    _mov(alfa, "expense", 150_000, "2026-06-20T10:00:00", "Compra")
    _mov(alfa, "expense", 50_000, "2026-07-08T10:00:00", "Compra")
    _mov(beta, "income", 80_000, "2026-05-06T10:00:00", "Pago")
    _mov(beta, "expense", 20_000, "2026-05-12T10:00:00", "Compra")
    _mov(beta, "income", 60_000, "2026-06-04T10:00:00", "Pago")
    h = {
        "alfa_may": _hist(uid, alfa, ini=500_000, fin=700_000, inicio="2026-05-01", corte="2026-05-31"),
        "alfa_jun": _hist(uid, alfa, ini=700_000, fin=950_000, inicio="2026-06-01", corte="2026-06-30"),
        "beta_may": _hist(uid, beta, ini=100_000, fin=160_000, inicio="2026-05-01", corte="2026-05-31"),
        "beta_jun": _hist(uid, beta, ini=160_000, fin=260_000, inicio="2026-06-01", corte="2026-06-30", review=[dict(FALTA)]),
    }
    return {"alfa": alfa, "beta": beta, "tarjeta": tarj, "h": h}


def _cierre(mes):
    r = client.get(f"/cierre-mes/extractos?mes={mes}")
    assert r.status_code == 200, r.text
    return r.json()


def _cta(r, banco, nombre):
    b = next(x for x in r["bancos"] if x["banco"] == banco)
    return next(c for c in b["cuentas"] if c["nombre"] == nombre)


def test_mayo_cuadra_con_empece_ingresos_gastos_y_termine():
    _escenario("cie-1")
    r = _cierre("2026-05")
    a = _cta(r, "Alfa", "Alfa Ahorros")
    assert (a["empece"], a["ingresos"], a["gastos"], a["otros"], a["termine"], a["segun_extracto"]) == \
        (500_000, 300_000, 100_000, 0, 700_000, 700_000)
    assert a["estado"] == "cuadra" and a["diferencia"] == 0 and a["empece_origen"] == "extracto"
    b = _cta(r, "Beta", "Beta")
    assert (b["empece"], b["termine"], b["estado"]) == (100_000, 160_000, "cuadra")


def test_meses_encadenados_cuadran_y_el_empece_es_el_termine_anterior():
    _escenario("cie-1b")
    may, jun = _cta(_cierre("2026-05"), "Alfa", "Alfa Ahorros"), _cta(_cierre("2026-06"), "Alfa", "Alfa Ahorros")
    assert jun["estado"] == "cuadra" and jun["empece"] == may["termine"] == 700_000 and jun["termine"] == 950_000


def test_mes_con_diferencia_aparece_no_cuadra_con_la_diferencia_y_la_causa():
    e = _escenario("cie-2")
    r = _cierre("2026-06")
    b = _cta(r, "Beta", "Beta")
    assert b["estado"] == "no_cuadra" and b["diferencia"] == 40_000 and b["termine"] == 220_000 and b["segun_extracto"] == 260_000
    assert any(c["codigo"] == "falta_importar" for c in b["causas"])
    assert any(x["tipo"] == "importar_lineas" for x in b["acciones"])
    assert b["motivo"] and b["historial_id"] == e["h"]["beta_jun"]
    resumen = {x["banco"]: x for x in r["resumen_bancos"]}
    assert resumen["Beta"]["estado"] == "no_cuadra" and resumen["Beta"]["diferencia"] == 40_000
    assert resumen["Alfa"]["estado"] == "cuadra"
    assert r["total"]["no_cuadran"] == 1 and r["total"]["cuadran"] == 1


def test_bancos_ordenados_y_la_tarjeta_sin_actividad_no_aparece():
    _escenario("cie-3")
    r = _cierre("2026-05")
    nombres = [b["banco"] for b in r["bancos"]]
    assert nombres == sorted(nombres, key=str.lower)
    alfa = next(b for b in r["bancos"] if b["banco"] == "Alfa")
    assert [c["nombre"] for c in alfa["cuentas"]] == ["Alfa Ahorros"]


def test_tarjeta_va_con_su_banco_y_el_total_del_banco_la_suma():
    e = _escenario("cie-3b")
    _mov(e["tarjeta"], "expense", 70_000, "2026-05-15T10:00:00", "Compra con tarjeta")
    r = _cierre("2026-05")
    alfa = next(b for b in r["bancos"] if b["banco"] == "Alfa")
    assert [c["nombre"] for c in alfa["cuentas"]] == ["Alfa Ahorros", "Alfa Tarjeta"]  # la cuenta y luego su tarjeta
    assert alfa["total"]["gastos"] == 100_000 + 70_000 and alfa["total"]["ingresos"] == 300_000
    assert r["total"]["gastos"] == 100_000 + 70_000 + 20_000  # Alfa + tarjeta + Beta


def test_mes_sin_extracto_se_etiqueta_y_usa_el_final_calculado_del_anterior():
    _escenario("cie-4")
    r = _cierre("2026-07")
    a = _cta(r, "Alfa", "Alfa Ahorros")
    assert a["estado"] == "sin_extracto" and a["etiqueta_extracto"] == "Sin extracto" and a["segun_extracto"] is None
    assert a["empece_origen"] == "calculado" and a["gastos"] == 50_000
    assert a["termine"] == a["empece"] - 50_000
    assert r["total"]["sin_extracto"] >= 1


def test_ingresos_y_gastos_iguales_al_informe_del_mes():
    _escenario("cie-5")
    for mes, (desde, hasta) in {"2026-05": (datetime(2026, 5, 1), datetime(2026, 6, 1)),
                                "2026-06": (datetime(2026, 6, 1), datetime(2026, 7, 1))}.items():
        r = _cierre(mes)
        db = SessionLocal()
        try:
            movs = cargar_movs_efectivos(db, "cie-5", desde, hasta)
        finally:
            db.close()
        tot = informe._totales(movs, informe._rango(desde, hasta, "", "mes"))
        assert round(r["total"]["ingresos"]) == tot["ingresos"] and round(r["total"]["gastos"]) == tot["gastos"], mes


def test_traslados_van_en_otros_y_la_cuenta_se_reconstruye():
    e = _escenario("cie-6")
    for cuenta, tipo, desc in ((e["alfa"], "expense", "Transferencia a Beta propia"), (e["beta"], "income", "Transferencia de Alfa propia")):
        _mov(cuenta, tipo, 25_000, "2026-05-20T10:00:00", desc, "Transferencia")
    a = _cta(_cierre("2026-05"), "Alfa", "Alfa Ahorros")
    # sea cual sea la clasificación, empecé + ingresos - gastos + otros = lo que dice el saldo calculado
    assert round(a["empece"] + a["ingresos"] - a["gastos"] + a["otros"], 2) == a["termine"] == 675_000
    assert a["otros"] != 0 or a["gastos"] == 125_000


def test_saldo_inicial_automatico_no_es_ingreso_y_deja_el_mes_cuadrado():
    como("cie-7")
    cta = client.post("/cuentas", json={"nombre": "Gama", "tipo": "ahorro", "saldo": 0}).json()["id"]
    _mov(cta, "income", 300_000, "2026-05-05T10:00:00", "Pago")
    _hist("cie-7", cta, ini=500_000, fin=800_000, inicio="2026-05-01", corte="2026-05-31")
    assert len(client.post("/conciliacion/cuadre/saldo-inicial-auto").json()["registrados"]) == 1
    g = _cta(_cierre("2026-05"), "Gama", "Gama")
    assert g["estado"] == "cuadra" and g["termine"] == 800_000
    assert g["otros"] == 0 and g["ingresos"] == 300_000  # el saldo inicial no es ingreso


def test_selector_de_12_meses_con_extractos_marcados():
    _escenario("cie-8")
    r = _cierre("2026-06")
    assert len(r["meses"]) == 12
    assert all({"mes", "etiqueta", "con_extracto"} <= set(m) for m in r["meses"])
    r2 = client.get("/cierre-mes/extractos")
    assert r2.status_code == 200 and "bancos" in r2.json()
    assert client.get("/cierre-mes/extractos?mes=junio").status_code == 422


def test_extracto_de_otra_cuenta_se_sugiere_cambiar_cuenta():
    como("cie-9")
    x = client.post("/cuentas", json={"nombre": "Delta", "tipo": "ahorro", "saldo": 0}).json()["id"]
    y = client.post("/cuentas", json={"nombre": "Epsilon", "tipo": "ahorro", "saldo": 0}).json()["id"]
    _mov(x, "income", 10_000, "2026-05-02T10:00:00")
    _mov(y, "income", 300_000, "2026-05-05T10:00:00")
    _mov(y, "expense", 100_000, "2026-05-10T10:00:00")
    # el extracto de Epsilon se cargó por error en Delta: su cambio (+200.000) es el de Epsilon
    _hist("cie-9", x, ini=0, fin=200_000, inicio="2026-05-01", corte="2026-05-31")
    d = _cta(_cierre("2026-05"), "Delta", "Delta")
    assert d["estado"] == "no_cuadra"
    assert any(c["codigo"] == "extracto_de_otra_cuenta" for c in d["causas"])
    assert any(a["tipo"] == "cambiar_cuenta" and a["destino_id"] == y for a in d["acciones"])


def test_movimientos_repetidos_se_sugieren_revisar():
    como("cie-9b")
    z = client.post("/cuentas", json={"nombre": "Zeta", "tipo": "ahorro", "saldo": 0}).json()["id"]
    _mov(z, "income", 300_000, "2026-05-05T10:00:00", "Pago")
    _mov(z, "expense", 60_000, "2026-05-10T10:00:00", "Compra A")
    _mov(z, "expense", 60_000, "2026-05-10T15:00:00", "Compra A otra vez")
    _hist("cie-9b", z, ini=0, fin=240_000, inicio="2026-05-01", corte="2026-05-31")
    c = _cta(_cierre("2026-05"), "Zeta", "Zeta")
    assert c["estado"] == "no_cuadra" and c["diferencia"] == 60_000
    assert any(x["codigo"] in ("repetidos", "movimiento_de_mas") for x in c["causas"])


def test_aislado_por_usuario():
    _escenario("cie-10")
    como("cie-11")
    r = _cierre("2026-05")
    assert r["bancos"] == [] and r["hay_datos"] is False and r["total"]["cuentas"] == 0
