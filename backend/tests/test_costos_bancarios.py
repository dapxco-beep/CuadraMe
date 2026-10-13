"""«Lo que te cuesta tu plata»: análisis, alertas, cargos inusuales, suscripciones y endpoint.
Todo con datos SINTÉTICOS (números hechos a mano)."""
import os
import tempfile
from datetime import date, datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'costos.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import cargos_inusuales as ci  # noqa: E402
from app import consejos  # noqa: E402
from app import costos_bancarios as cb  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

HOY = datetime(2026, 10, 15, 12, 0)
_n = [0]
CUENTAS = {"v": {"nombre": "Visa Nu", "tipo": "credito", "dia_pago": 28}, "a": {"nombre": "Ahorros", "tipo": "ahorro", "dia_pago": None}}


def mov(mes, dia, monto, desc, cat, tipo="expense", cuenta="v"):
    _n[0] += 1
    a, m = int(mes[:4]), int(mes[5:7])
    return {"id": f"m{_n[0]}", "cuenta_id": cuenta, "fecha": datetime(a, m, dia, 10), "descripcion": desc,
            "categoria": cat, "tipo": tipo, "monto": monto}


def actividad(cuenta, meses):
    """Un gasto cualquiera por mes para que la cuenta tenga historia."""
    return [mov(m, 3, 20_000, "Compra Exito", "Comida", cuenta=cuenta) for m in meses]


MESES = ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]


def analizar(movs, desgloses=(), pagos=(), cuentas=CUENTAS, hoy=HOY, desde=date(2026, 6, 1), hasta=date(2026, 10, 15)):
    return cb.analizar(movs, cuentas, list(desgloses), list(pagos), hoy, desde, hasta)


def ids(r):
    return {a["id"] for a in r["alertas"]}


# ── análisis ────────────────────────────────────────────────────────────────────────
def test_suma_por_tipo_mes_y_costo_neto():
    movs = [
        mov("2026-09", 20, 80_000, "INTERESES CORRIENTES", "Intereses de tarjeta"),
        mov("2026-10", 20, 100_000, "INTERESES CORRIENTES", "Intereses de tarjeta"),
        mov("2026-10", 5, 28_000, "CUOTA DE MANEJO", "Cuota de manejo"),
        mov("2026-10", 6, 4_000, "GMF 4X1000", "4x1000 (GMF)", cuenta="a"),
        mov("2026-10", 7, 9_000, "Seguro deudores", "Comisiones y seguros"),
        mov("2026-10", 8, 30_000, "Rendimientos cajita", "Rendimientos", tipo="income", cuenta="a"),
        mov("2026-10", 9, 70_000, "Compra Exito", "Comida"),
    ]
    r = analizar(movs)
    m = r["mes"]
    assert (m["intereses"], m["cuota"], m["gmf"], m["comisiones"]) == (100_000, 28_000, 4_000, 9_000)
    assert m["total"] == 141_000 and m["rendimientos"] == 30_000 and m["costo_neto"] == 111_000
    assert m["mes_anterior_total"] == 80_000 and m["variacion_pct"] == 76
    assert r["anio"]["total"] == 221_000
    assert {c["cuenta_id"] for c in r["por_cuenta"]} == {"v", "a"}
    assert r["promedio_mensual"] == 80_000


def test_excluye_traslados_pagos_de_tarjeta_y_ajustes():
    movs = [
        mov("2026-10", 5, 500_000, "PAGO TARJETA", "Pago de tarjeta", tipo="transfer"),
        mov("2026-10", 5, 90_000, "Ajuste", "Ajuste de saldo", tipo="transfer"),
        mov("2026-10", 6, 12_000, "Comision", "Comisiones y seguros", tipo="transfer"),  # traslado: no cuenta
    ]
    r = analizar(movs)
    assert r["mes"]["total"] == 0 and not r["tiene_datos"]


def test_categoria_antigua_se_reparte_por_la_linea():
    movs = [mov("2026-10", 5, 28_000, "CUOTA DE MANEJO", "Comisiones y costos financieros"),
            mov("2026-10", 6, 5_000, "AVANCE EN EFECTIVO", "Comisiones y costos financieros")]
    m = analizar(movs)["mes"]
    assert m["cuota"] == 28_000 and m["comisiones"] == 5_000


def test_devolucion_de_un_cobro_resta():
    movs = [mov("2026-10", 5, 28_000, "CUOTA DE MANEJO", "Cuota de manejo"),
            mov("2026-10", 9, 28_000, "Devolución cuota de manejo", "Cuota de manejo", tipo="income")]
    assert analizar(movs)["mes"]["cuota"] == 0


def test_el_extracto_manda_sin_duplicar_lo_registrado():
    movs = [mov("2026-10", 20, 90_000, "INTERESES CORRIENTES", "Intereses de tarjeta")]
    d = {"cuenta_id": "v", "periodo": "2026-10", "intereses_corrientes": 100_000, "intereses_mora": 0, "cuota_manejo": 28_000,
         "comisiones": None, "seguros": 9_000}
    m = analizar(movs, [d])["mes"]
    assert m["intereses"] == 100_000 and m["cuota"] == 28_000 and m["comisiones"] == 9_000


def test_rango_solo_cuenta_lo_pedido():
    movs = [mov("2026-08", 5, 50_000, "INTERESES CORRIENTES", "Intereses de tarjeta"),
            mov("2026-10", 5, 10_000, "INTERESES CORRIENTES", "Intereses de tarjeta")]
    r = analizar(movs, desde=date(2026, 10, 1))
    assert r["periodo"]["total"] == 10_000 and len(r["meses"]) == 1


# ── alertas de costos ───────────────────────────────────────────────────────────────
def test_costo_que_sube_mas_de_30_por_ciento():
    movs = actividad("v", MESES) + [mov(m, 20, 50_000, "INTERESES CORRIENTES", "Intereses de tarjeta") for m in MESES[:-1]]
    movs.append(mov("2026-10", 20, 80_000, "INTERESES CORRIENTES", "Intereses de tarjeta"))
    a = {x["id"]: x for x in analizar(movs)["alertas"]}
    assert "costos-sube:2026-10" in a and "60 %" in a["costos-sube:2026-10"]["titulo"]
    # 20 % de aumento: no avisa
    movs[-1]["monto"] = 60_000
    assert "costos-sube:2026-10" not in ids(analizar(movs))


def test_cuota_de_manejo_en_tarjeta_que_estaba_exenta():
    movs = actividad("v", MESES) + [mov("2026-10", 5, 28_000, "CUOTA DE MANEJO", "Cuota de manejo")]
    r = analizar(movs)
    a = [x for x in r["alertas"] if x["tipo"] == "cuota_nueva"]
    assert len(a) == 1 and a[0]["id"] == "costos-cuota-nueva:v:2026-10" and "exoneración" in a[0]["texto"]
    # si la cobran todos los meses, no es nueva
    movs += [mov(m, 5, 28_000, "CUOTA DE MANEJO", "Cuota de manejo") for m in MESES[:-1]]
    assert not [x for x in analizar(movs)["alertas"] if x["tipo"] == "cuota_nueva"]


def test_cobro_nuevo_necesita_historia():
    nuevo = [mov("2026-10", 5, 15_000, "Costo transacción", "Comisiones y seguros")]
    assert not [a for a in analizar(actividad("v", ["2026-10"]) + nuevo)["alertas"] if a["tipo"] == "cobro_nuevo"]
    assert [a for a in analizar(actividad("v", MESES) + nuevo)["alertas"] if a["tipo"] == "cobro_nuevo"]


def test_mora_es_urgente_con_fecha_de_pago():
    movs = actividad("v", MESES) + [mov("2026-10", 12, 45_000, "INTERESES DE MORA", "Intereses de tarjeta")]
    r = analizar(movs)
    a = next(x for x in r["alertas"] if x["tipo"] == "mora")
    assert a["prioridad"] == 1 and "28 de octubre" in a["texto"] and a["id"] == "costos-mora:v:2026-10"
    assert "Orientación" in r["aviso"]


def test_pago_solo_del_minimo_reiterado_con_cifra():
    def d(periodo, corte, limite):
        return {"cuenta_id": "v", "periodo": periodo, "pago_total": 1_000_000, "pago_minimo": 100_000,
                "fecha_corte": corte, "fecha_limite_pago": limite}
    desgloses = [d("2026-08", "2026-08-10", "2026-08-25"), d("2026-09", "2026-09-10", "2026-09-25")]
    pagos = [{"cuenta_id": "v", "fecha": datetime(2026, 8, 24), "monto": 100_000},
             {"cuenta_id": "v", "fecha": datetime(2026, 9, 24), "monto": 105_000}]
    movs = actividad("v", MESES) + [mov("2026-09", 11, 70_000, "INTERESES CORRIENTES", "Intereses de tarjeta"),
                                    mov("2026-10", 11, 75_000, "INTERESES CORRIENTES", "Intereses de tarjeta")]
    a = next(x for x in analizar(movs, desgloses, pagos)["alertas"] if x["tipo"] == "solo_minimo")
    assert a["id"].startswith("costos-solo-minimo:v:") and "$145.000" in a["texto"] and "28 de octubre" in a["texto"]
    # pagó el total en el segundo: ya no es reiterado
    pagos[1]["monto"] = 1_000_000
    assert not [x for x in analizar(movs, desgloses, pagos)["alertas"] if x["tipo"] == "solo_minimo"]


def test_todas_las_alertas_tienen_id_estable_accion_y_leccion():
    movs = actividad("v", MESES) + [mov("2026-10", 12, 45_000, "INTERESES DE MORA", "Intereses de tarjeta"),
                                    mov("2026-10", 5, 28_000, "CUOTA DE MANEJO", "Cuota de manejo")]
    r1, r2 = analizar(movs), analizar(movs)
    assert [a["id"] for a in r1["alertas"]] == [a["id"] for a in r2["alertas"]]
    assert r1["alertas"]
    for a in r1["alertas"]:
        assert a["accion"]["texto"] and a["accion"]["ruta"].startswith("/")
        assert a["aprende"] in consejos.LECCIONES


# ── cargos inusuales y suscripciones ────────────────────────────────────────────────
def gasto(dias_atras, monto, desc, id_=None):
    _n[0] += 1
    return {"id": id_ or f"g{_n[0]}", "cuenta_id": "a", "fecha": HOY - timedelta(days=dias_atras), "descripcion": desc,
            "categoria": "Otros", "tipo": "expense", "monto": monto}


def historial_normal():
    return [gasto(d, 18_000 + (d * 37) % 9_000, f"TIENDA {d % 4}") for d in range(10, 100, 5)]


def test_cargo_nuevo_y_muy_superior_a_la_mediana():
    movs = historial_normal() + [gasto(1, 400_000, "JOYERIA ESTRELLA", "mx")]
    a = next(x for x in ci.detectar(movs, HOY)["alertas"] if x["tipo"] == "cargo_inusual")
    assert a["id"] == "cargo-inusual:mx" and a["titulo"] == "Este cobro es nuevo o más alto de lo normal"
    # monto normal: no hay alerta
    assert not ci.detectar(historial_normal() + [gasto(1, 25_000, "JOYERIA ESTRELLA")], HOY)["alertas"]
    # comercio ya conocido: tampoco
    previo = [gasto(40, 20_000, "JOYERIA ESTRELLA")]
    assert not [x for x in ci.detectar(historial_normal() + previo + [gasto(1, 400_000, "JOYERIA ESTRELLA")], HOY)["alertas"]
                if x["tipo"] == "cargo_inusual"]
    # con poco historial no se avisa de todo
    assert not ci.detectar([gasto(1, 400_000, "JOYERIA ESTRELLA")], HOY)["alertas"]


def test_los_cobros_del_banco_no_son_cargos_inusuales():
    movs = historial_normal() + [gasto(1, 900_000, "INTERESES DE MORA")]
    movs[-1]["categoria"] = "Intereses de tarjeta"
    assert not ci.detectar(movs, HOY)["alertas"]


def test_suscripcion_activa_y_alerta_si_sube():
    base = [gasto(d, 29_900, "NETFLIX.COM") for d in (80, 50, 20)]
    r = ci.detectar(historial_normal() + base, HOY)
    assert [s["nombre"] for s in r["suscripciones"]] == ["Netflix"] and r["total_mensual_suscripciones"] == 29_900
    assert not [a for a in r["alertas"] if a["tipo"] == "suscripcion_sube"]
    # sube de precio
    sube = [gasto(d, 29_900, "NETFLIX.COM") for d in (110, 80, 50, 20)] + [gasto(1, 39_900, "NETFLIX.COM")]
    r = ci.detectar(historial_normal() + sube, HOY)
    s = r["suscripciones"][0]
    assert s["subio"] and s["monto"] == 39_900 and s["anterior"] == 29_900
    assert [a for a in r["alertas"] if a["tipo"] == "suscripcion_sube"]


def test_cargo_recurrente_que_cambia_mas_de_20_por_ciento():
    base = [gasto(d, m, "GIMNASIO SMART") for d, m in ((95, 100_000), (65, 140_000), (35, 120_000))]
    r = ci.detectar(historial_normal() + base + [gasto(2, 170_000, "GIMNASIO SMART")], HOY)
    a = [x for x in r["alertas"] if x["tipo"] == "cargo_cambio"]
    assert len(a) == 1 and a[0]["sube"] is True
    r = ci.detectar(historial_normal() + base + [gasto(2, 130_000, "GIMNASIO SMART")], HOY)
    assert not [x for x in r["alertas"] if x["tipo"] == "cargo_cambio"]


def test_cargo_recurrente_que_baja_no_genera_alerta():
    base = [gasto(d, 100_000, "UBER") for d in (95, 65, 35)]
    r = ci.detectar(historial_normal() + base + [gasto(2, 60_000, "UBER")], HOY)
    assert not [x for x in r["alertas"] if x["tipo"] == "cargo_cambio"]


# ── consejos ────────────────────────────────────────────────────────────────────────
def test_los_consejos_incluyen_las_alertas_de_costos():
    alerta = {"id": "costos-mora:v:2026-10", "tipo": "mora", "prioridad": 1, "titulo": "t", "texto": "x", "cifra": "$1",
              "accion": {"texto": "Ver", "ruta": "/cuentas"}, "aprende": "tarjeta-de-credito"}
    out = consejos.generar({"costos_alertas": [alerta]}, HOY)
    assert out[0]["id"] == "costos-mora:v:2026-10" and out[0]["aprende"] == "tarjeta-de-credito"


# ── endpoint ────────────────────────────────────────────────────────────────────────
client = TestClient(app)


@pytest.fixture
def usuario():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-costos", email="c@t.com", nombre="C")
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_endpoint_vacio_y_con_datos(usuario):
    r = client.get("/costos-bancarios")
    assert r.status_code == 200 and r.json()["tiene_datos"] is False
    hoy = datetime.now()
    c = client.post("/cuentas", json={"nombre": "Visa Costos", "tipo": "credito", "saldo": 0}).json()
    for desc, monto, cat in (("INTERESES CORRIENTES", 70_000, "Intereses de tarjeta"), ("CUOTA DE MANEJO", 28_000, "Cuota de manejo")):
        r = client.post("/movimientos", json={"cuenta_id": c["id"], "descripcion": desc, "monto": monto, "tipo": "expense",
                                              "categoria": cat})
        assert r.status_code in (200, 201), r.text
    j = client.get("/costos-bancarios").json()
    assert j["tiene_datos"] and j["mes"]["intereses"] == 70_000 and j["mes"]["cuota"] == 28_000
    assert j["mes"]["mes"] == hoy.strftime("%Y-%m") and j["anio"]["total"] == 98_000
    assert "suscripciones" in j and "aviso" in j


def test_endpoint_valida_fechas(usuario):
    assert client.get("/costos-bancarios?desde=mal").status_code == 422
    assert client.get("/costos-bancarios?desde=2026-10-10&hasta=2026-01-01").status_code == 422
    assert client.get("/costos-bancarios?desde=2010-01-01&hasta=2026-01-01").status_code == 422


def test_aplicar_extracto_guarda_el_desglose():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-costos-desglose", email="d@t.com", nombre="D")
    c = client.post("/cuentas", json={"nombre": "Visa Desglose", "tipo": "credito", "saldo": -500_000, "cupo_total": 3_000_000}).json()
    r = client.post(f"/tarjetas/{c['id']}/aplicar-extracto", json={
        "fecha_corte": "2026-10-10", "pago_total": 500_000, "pago_minimo": 50_000, "intereses_corrientes": 21_000,
        "cuota_manejo": 28_900, "tasa_mv": 2.04})
    assert r.status_code == 200 and r.json()["desglose_guardado"] is True
    j = client.get("/costos-bancarios?desde=2026-10-01&hasta=2026-10-31").json()
    assert j["mes"]["intereses"] == 21_000 and j["mes"]["cuota"] == 28_900
    # aplicar de nuevo el mismo periodo no duplica
    client.post(f"/tarjetas/{c['id']}/aplicar-extracto", json={"fecha_corte": "2026-10-10", "intereses_corrientes": 21_000})
    assert client.get("/costos-bancarios?desde=2026-10-01&hasta=2026-10-31").json()["mes"]["intereses"] == 21_000


def test_b_no_ve_los_costos_de_a():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-costos-a", email="a@t.com", nombre="A")
    c = client.post("/cuentas", json={"nombre": "ZZCostosA Visa", "tipo": "credito", "saldo": 0}).json()
    client.post("/movimientos", json={"cuenta_id": c["id"], "descripcion": "CUOTA DE MANEJO", "monto": 33_000, "tipo": "expense",
                                      "categoria": "Cuota de manejo"})
    assert client.get("/costos-bancarios").json()["mes"]["cuota"] == 33_000
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-costos-b", email="b@t.com", nombre="B")
    j = client.get("/costos-bancarios")
    assert j.json()["tiene_datos"] is False and "zzcostosa" not in j.text.lower()
    app.dependency_overrides.pop(get_current_user, None)


def test_cron_exige_secreto():
    assert client.post("/costos-bancarios/cron/avisar-cargos").status_code == 401


def test_categorias_de_sistema_aparecen_al_usarse_y_no_estorban_antes():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-costos-cat", email="k@t.com", nombre="K")
    base = client.get("/categorias").json()
    assert len(base) == 8 and not any(c["es_sistema"] for c in base)
    c = client.post("/cuentas", json={"nombre": "Ahorros Cat", "saldo": 0}).json()
    client.post("/movimientos", json={"cuenta_id": c["id"], "descripcion": "Rendimientos cajita", "monto": 5_000,
                                      "tipo": "income", "categoria": "Rendimientos"})
    cats = {x["nombre"]: x for x in client.get("/categorias").json()}
    assert cats["Rendimientos"]["es_sistema"] is True and cats["Rendimientos"]["icono"] == "📈"
    assert "Cuota de manejo" not in cats
    # no se duplica al volver a pedir la lista
    assert [x["nombre"] for x in client.get("/categorias").json()].count("Rendimientos") == 1
    app.dependency_overrides.pop(get_current_user, None)
