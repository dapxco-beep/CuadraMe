"""«¿Tengo que declarar renta?» y 4x1000 del mes. Números hechos a mano con UVT 2025 = 49.799
(1.400 UVT = $69.718.600; 4.500 UVT = $224.095.500) y UVT 2026 = 52.374 (350 UVT = $18.330.900)."""
import os
import tempfile
from datetime import date, datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'renta.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import consejos, renta_alerta as ra  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.impuestos import gmf_mes  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import impuestos as router_imp  # noqa: E402

HOY = date(2026, 10, 12)
TOPE_1400 = 1400 * 49799      # 69.718.600
TOPE_4500 = 4500 * 49799      # 224.095.500
_n = [0]


def mov(monto, tipo="income", cuenta="c1", fecha=datetime(2025, 6, 10), fuente="manual", notas="", desc="Pago", cat="Otros"):
    _n[0] += 1
    return {"id": f"m{_n[0]}", "cuenta_id": cuenta, "fecha": fecha, "tipo": tipo, "fuente": fuente, "notas": notas,
            "descripcion": desc, "categoria": cat, "monto": monto}


def datos(movs=(), saldo=0, cuentas=None, **kw):
    base = {"cuentas": cuentas if cuentas is not None else [{"id": "c1", "tipo": "ahorro", "saldo": saldo},
                                                              {"id": "c2", "tipo": "ahorro", "saldo": 0},
                                                              {"id": "t1", "tipo": "credito", "saldo": 0}],
            "movimientos": list(movs), "activos_cop": 0, "tiene_bienes": True, "inicio_datos": date(2025, 1, 1)}
    base.update(kw)
    return base


def crit(r, id_):
    return next(c for c in r["criterios"] if c["id"] == id_)


# ── constantes ───────────────────────────────────────────────────────────────────────
def test_constantes_en_pesos():
    t = ra.topes_en_pesos(2025)
    assert t["ingresos_brutos"] == TOPE_1400 == 69_718_600
    assert t["patrimonio_bruto"] == TOPE_4500 == 224_095_500
    assert set(t) == set(ra.ORDEN)
    assert ra.PLAZOS_RENTA[2025] == (date(2026, 8, 12), date(2026, 10, 26))


def test_plazo_cuenta_atras():
    p = ra.plazo_del_anio(2025, HOY)
    assert p["dias_restantes"] == 14 and not p["vencido"] and "26 de octubre" in p["texto"]
    assert ra.plazo_del_anio(2025, date(2026, 10, 27))["vencido"]
    assert ra.plazo_del_anio(2030, HOY) is None


# ── bordes 59 / 60 / 100 % en cada criterio ─────────────────────────────────────────
def _ingreso(p):  # p = fracción del tope
    return [mov(round(TOPE_1400 * p))]


@pytest.mark.parametrize("fraccion,estado", [(0.59, "lejos"), (0.5999, "lejos"), (0.60, "cerca"), (0.99, "cerca"),
                                             (1.0, "superado"), (1.2, "superado")])
def test_ingresos_bordes(fraccion, estado):
    r = ra.calcular_renta(datos(_ingreso(fraccion)), 2025, HOY)
    c = crit(r, "ingresos_brutos")
    assert c["estado"] == estado
    assert c["tope"] == TOPE_1400


def test_borde_exacto_y_estados():
    assert crit(ra.calcular_renta(datos([mov(TOPE_1400 * 6 // 10)]), 2025, HOY), "ingresos_brutos")["pct"] == 60.0
    assert ra.estado_de(59.9) == "lejos" and ra.estado_de(60.0) == "cerca" and ra.estado_de(99.9) == "cerca"
    assert ra.estado_de(100.0) == "superado"


@pytest.mark.parametrize("fraccion,estado", [(0.59, "lejos"), (0.6, "cerca"), (1.0, "superado")])
def test_patrimonio_bordes(fraccion, estado):
    r = ra.calcular_renta(datos([mov(1)], saldo=round(TOPE_4500 * fraccion)), 2025, date(2025, 12, 31))
    assert crit(r, "patrimonio_bruto")["estado"] == estado


def test_patrimonio_cuenta_activos_y_no_resta_deudas():
    d = datos([mov(1)], saldo=100_000_000, activos_cop=130_000_000)
    d["cuentas"][2]["saldo"] = -50_000_000  # tarjeta: es deuda, no se resta del bruto
    c = crit(ra.calcular_renta(d, 2025, HOY), "patrimonio_bruto")
    assert c["valor"] == 230_000_000 and c["estado"] == "superado"


def test_patrimonio_al_31_dic_resta_lo_movido_despues():
    # hoy hay 300 M, pero en 2026 entraron 200 M: al 31-dic-2025 había 100 M
    d = datos([mov(200_000_000, fecha=datetime(2026, 3, 1))], saldo=300_000_000)
    assert crit(ra.calcular_renta(d, 2025, HOY), "patrimonio_bruto")["valor"] == 100_000_000


def test_tarjeta_y_compras_bordes():
    compras = [mov(round(TOPE_1400 * 0.6), "expense", "t1"), mov(round(TOPE_1400 * 0.1), "expense", "c1")]
    r = ra.calcular_renta(datos(compras), 2025, HOY)
    assert crit(r, "consumos_tarjeta")["estado"] == "cerca"
    c = crit(r, "compras_consumos")
    assert c["valor"] == round(TOPE_1400 * 0.6) + round(TOPE_1400 * 0.1) and c["estado"] == "cerca"
    r = ra.calcular_renta(datos([mov(TOPE_1400, "expense", "t1")]), 2025, HOY)
    assert crit(r, "consumos_tarjeta")["estado"] == "superado" and crit(r, "compras_consumos")["estado"] == "superado"
    r = ra.calcular_renta(datos([mov(round(TOPE_1400 * 0.59), "expense", "t1")]), 2025, HOY)
    assert crit(r, "consumos_tarjeta")["estado"] == "lejos"


def test_pago_de_tarjeta_no_duplica_compras():
    movs = [mov(1_000_000, "expense", "t1"), mov(1_000_000, "expense", "c1", desc="Pago tarjeta Visa"),
            mov(1_000_000, "income", "t1", desc="Abono")]
    r = ra.calcular_renta(datos(movs), 2025, HOY)
    assert crit(r, "compras_consumos")["valor"] == 1_000_000
    assert crit(r, "consignaciones")["valor"] == 0   # el abono a la tarjeta no es una consignación


# ── traslados como consignaciones, pero no como ingresos ────────────────────────────
def test_traslados_cuentan_como_consignaciones_no_como_ingresos():
    movs = [mov(30_000_000, "income", desc="Nómina"),
            mov(50_000_000, "transfer", "c1", fuente="transferencia_interna", notas="TRF:1:out"),
            mov(50_000_000, "transfer", "c2", fuente="transferencia_interna", notas="TRF:1:in")]
    r = ra.calcular_renta(datos(movs), 2025, HOY)
    assert crit(r, "ingresos_brutos")["valor"] == 30_000_000
    c = crit(r, "consignaciones")
    assert c["valor"] == 80_000_000 and c["de_los_cuales_traslados"] == 50_000_000
    assert c["estado"] == "superado" and crit(r, "ingresos_brutos")["estado"] == "lejos"
    assert r["resultado"]["clave"] == "si"
    assert crit(r, "compras_consumos")["valor"] == 0   # un traslado no es compra


def test_ajuste_de_saldo_no_es_consignacion():
    r = ra.calcular_renta(datos([mov(90_000_000, "income", fuente="ajuste_saldo", cat="Ajuste de saldo")]), 2025, HOY)
    assert crit(r, "consignaciones")["valor"] == 0 and crit(r, "ingresos_brutos")["valor"] == 0


# ── año parcial y sin datos ──────────────────────────────────────────────────────────
def test_anio_parcial_lejos_es_sin_datos_pero_superado_se_mantiene():
    movs = [mov(10_000_000, fecha=datetime(2025, 9, 1))]
    r = ra.calcular_renta(datos(movs, inicio_datos=date(2025, 8, 1)), 2025, HOY)
    assert r["cobertura"]["parcial"]
    assert crit(r, "ingresos_brutos")["estado"] == "sin_datos"
    assert r["resultado"]["clave"] == "no_se_sabe" and "faltan datos de" in r["resultado"]["titulo"]
    r = ra.calcular_renta(datos([mov(round(TOPE_1400 * 1.1), fecha=datetime(2025, 9, 1))], inicio_datos=date(2025, 8, 1)), 2025, HOY)
    assert crit(r, "ingresos_brutos")["estado"] == "superado" and r["resultado"]["clave"] == "si"


def test_respeta_punto_de_partida_posterior_al_anio():
    r = ra.calcular_renta(datos([mov(5, fecha=datetime(2026, 2, 1))], inicio_datos=date(2026, 1, 20)), 2025, HOY)
    assert all(c["estado"] == "sin_datos" for c in r["criterios"])
    assert r["resultado"]["clave"] == "no_se_sabe"


def test_sin_cuentas_no_se_sabe():
    r = ra.calcular_renta(datos(cuentas=[], inicio_datos=None), 2025, HOY)
    assert r["resultado"]["clave"] == "no_se_sabe"


def test_anio_completo_y_lejos_es_probablemente_no():
    r = ra.calcular_renta(datos([mov(1_000_000), mov(500_000, "expense")], saldo=1_000_000), 2025, HOY)
    assert r["resultado"]["clave"] == "no" and r["resultado"]["titulo"] == "Probablemente no"
    assert "No es asesoría tributaria" in r["aviso"] and r["enlaces"]["dian"] == "https://www.dian.gov.co"
    assert len(r["limites"]) >= 3


def test_cerca_sin_ser_superado():
    r = ra.calcular_renta(datos(_ingreso(0.7)), 2025, HOY)
    assert r["resultado"]["clave"] == "cerca" and r["resultado"]["titulo"] == "Estás cerca"


def test_csv_sin_movimientos_individuales():
    r = ra.calcular_renta(datos([mov(1_234_567, desc="SECRETO-COMERCIO")]), 2025, HOY)
    csv = ra.resumen_csv(r)
    assert "SECRETO-COMERCIO" not in csv and "Ingresos;1234567" in csv


# ── 4x1000 del mes (tope 2026: 350 UVT = 18.330.900) ─────────────────────────────────
def gm(monto, cuenta="a1", tipo="expense", desc="Compra", cat="Otros", dia=5, fuente="manual", notas=""):
    return {"fecha": datetime(2026, 10, dia), "monto": monto, "tipo": tipo, "fuente": fuente, "notas": notas,
            "descripcion": desc, "categoria": cat, "cuenta_id": cuenta}


TIPOS = {"a1": "ahorro", "a2": "ahorro", "t1": "credito"}


def test_gmf_mes_pagado_por_categoria_y_por_texto():
    movs = [gm(1_200, cat="4x1000 (GMF)", desc="Cobro"), gm(800, desc="GRAVAMEN MOVIMIENTOS FINANCIEROS"),
            gm(1_000_000), gm(500, cuenta="t1")]
    r = gmf_mes(movs, TIPOS, None, "2026-10")
    assert r["gmf_pagado"] == 2_000 and r["debitos_total"] == 1_000_000
    assert r["tope_exento_mensual"] == 18_330_900 and not r["alerta"]


def test_gmf_alerta_al_80_por_ciento_con_cuenta_exenta():
    tope = 18_330_900
    r = gmf_mes([gm(tope * 79 // 100), gm(tope, cuenta="a2")], TIPOS, "a1", "2026-10")
    assert not r["alerta"] and r["uso_pct"] == 79.0
    r = gmf_mes([gm(tope * 80 // 100)], TIPOS, "a1", "2026-10")
    assert r["alerta"] and r["mensaje"] == "Te acercas al tope de tu cuenta exenta"
    assert any("pedir en tu banco" in t for t in r["recordatorio"])


def test_gmf_otro_mes_no_cuenta():
    r = gmf_mes([gm(5_000_000)], TIPOS, None, "2026-09")
    assert r["debitos_total"] == 0


# ── endpoints, aislamiento, consejo y cron ──────────────────────────────────────────
client = TestClient(app)
A = UsuarioActual(id="renta-a", email="ra@test.com", nombre="A")
B = UsuarioActual(id="renta-b", email="rb@test.com", nombre="B")
ACTUAL = {"u": A}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_endpoint_aislado_y_calcula_con_datos_propios():
    ACTUAL["u"] = A
    c = client.post("/cuentas", json={"nombre": "ZZRenta Cuenta", "tipo": "ahorro", "saldo": 1000}).json()
    for i in range(2):
        r = client.post("/movimientos", json={"cuenta_id": c["id"], "descripcion": "ZZRenta nómina", "monto": 40_000_000,
                                              "tipo": "income", "fecha": f"2025-0{i + 3}-10T10:00:00"})
        assert r.status_code in (200, 201), r.text
    r = client.get("/impuestos/renta-estimada?anio=2025")
    assert r.status_code == 200
    j = r.json()
    ing = next(x for x in j["criterios"] if x["id"] == "ingresos_brutos")
    assert ing["valor"] == 80_000_000 and ing["estado"] == "superado" and j["resultado"]["clave"] == "si"
    ACTUAL["u"] = B
    jb = client.get("/impuestos/renta-estimada?anio=2025").json()
    assert "zzrenta" not in str(jb).lower()
    assert next(x for x in jb["criterios"] if x["id"] == "ingresos_brutos")["valor"] == 0
    assert jb["resultado"]["clave"] == "no_se_sabe"
    csv = client.get("/impuestos/renta-resumen.csv?anio=2025")
    assert csv.status_code == 200 and "zzrenta" not in csv.text.lower()
    assert client.get("/impuestos/renta-estimada?anio=1999").status_code == 422
    assert client.get("/impuestos/gmf-estimado?mes=2026-13").status_code == 422
    assert client.get("/impuestos/gmf-estimado?mes=2026-10").status_code == 200


def test_consejo_renta_solo_si_o_cerca_y_dentro_del_plazo():
    hoy = datetime(2026, 10, 12, 10)
    base = {"cuentas": [], "movimientos": [], "movimientos_neutros": [], "presupuestos": [], "metas": [],
            "deudas": [], "recurrentes": []}

    def pedir(clave, dias=14, abierto=True):
        d = {**base, "renta": {"anio": 2025, "clave": clave, "dias_restantes": dias, "abierto": abierto}}
        return [x for x in consejos.generar(d, hoy) if x["tipo"] == "renta"]

    assert pedir("no") == [] and pedir("no_se_sabe") == [] and pedir("si", abierto=False) == []
    assert pedir("si", dias=-1) == []
    c = pedir("si")[0]
    assert c["titulo"] == "Faltan 14 días para declarar renta" and c["accion"]["ruta"] == "/impuestos"
    assert pedir("cerca")[0]["id"] == "renta:2025"
    assert pedir("si", dias=1)[0]["titulo"] == "Falta 1 día para declarar renta"


def test_hitos_del_aviso():
    h = router_imp.hito_aviso
    assert h(20) is None and h(14) == 14 and h(4) == 14 and h(3) == 3 and h(0) == 3 and h(-1) is None


def test_cron_exige_secreto_e_idempotente(monkeypatch):
    assert client.post("/impuestos/cron/avisar-renta").status_code == 401
    assert client.post("/impuestos/cron/avisar-renta", headers={"X-Cron-Secret": "mal"}).status_code == 401
    from app.database import SessionLocal
    from app.models import PushSubscription

    enviados = []
    import app.push as push
    monkeypatch.setattr(push, "enviar_push", lambda db, uid, t, c, url="/", boton=None: enviados.append((uid, t, url)) or 1)
    monkeypatch.setattr(router_imp, "cron_autorizado", lambda s: True)
    reloj = {"t": datetime(2026, 10, 12, 9)}
    monkeypatch.setattr(router_imp, "ahora_co", lambda: reloj["t"])
    db = SessionLocal()
    try:
        db.add(PushSubscription(usuario_id=A.id, endpoint="https://x/ep-renta", p256dh="p", auth="a"))
        db.add(PushSubscription(usuario_id=B.id, endpoint="https://x/ep-renta-b", p256dh="p", auth="a"))
        db.commit()
    finally:
        db.close()
    monkeypatch.setattr(router_imp.renta_alerta, "renta_de_usuario",
                        lambda db, uid, anio, hoy: {"resultado": {"clave": "si" if uid == A.id else "no"}})
    r1 = client.post("/impuestos/cron/avisar-renta").json()
    assert r1["enviados"] == 1 and [e[0] for e in enviados] == [A.id] and enviados[0][2] == "/impuestos"
    r2 = client.post("/impuestos/cron/avisar-renta").json()
    assert r2["enviados"] == 0 and len(enviados) == 1               # mismo hito: no repite
    reloj["t"] = datetime(2026, 10, 23, 9)
    assert client.post("/impuestos/cron/avisar-renta").json()["enviados"] == 1   # hito de 3 días
    reloj["t"] = datetime(2026, 10, 28, 9)
    assert client.post("/impuestos/cron/avisar-renta").json()["motivo"] == "fuera_de_ventana"
    from app.derechos_titular import borrar_todo
    db = SessionLocal()
    try:
        for u in (A, B):
            borrar_todo(db, u.id, u.email)
    finally:
        db.close()
