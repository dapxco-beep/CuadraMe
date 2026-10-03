"""Endpoints de /planificacion con SQLite temporal."""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'planificacion.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Meta, Movimiento, Presupuesto, PushSubscription, Recurrente  # noqa: E402
from app.models_patrimonio import SnapshotPatrimonio  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
CRON = {"X-Cron-Secret": "secreto-de-prueba"}
USUARIO = {"actual": UsuarioActual(id="plan-1", email="p@test.com", nombre="P")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def como(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def _cuenta():
    return client.post("/cuentas", json={"nombre": "Banco", "saldo": 5_000_000}).json()["id"]


def test_config_por_defecto_y_validacion():
    como("plan-cfg")
    c = client.get("/planificacion/config").json()
    assert c["dia_pago"] is None and c["periodo_defecto"] == "monthly"
    assert c["regla"] == {"necesidades": 50, "deseos": 30, "ahorro": 20}
    r = client.put("/planificacion/config", json={"dia_pago": 5, "periodo_defecto": "quincenal",
                                                  "regla_necesidades": 60, "regla_deseos": 20, "regla_ahorro": 20})
    assert r.status_code == 200 and r.json()["periodo_defecto"] == "biweekly" and r.json()["dia_pago"] == 5
    # no suma 100
    assert client.put("/planificacion/config", json={"regla_ahorro": 50}).status_code == 422
    assert client.put("/planificacion/config", json={"dia_pago": 40}).status_code == 422
    assert client.put("/planificacion/config", json={"sin_dia_pago": True}).json()["dia_pago"] is None


def test_proyeccion_por_periodo_y_presupuesto_antiguo_mensual():
    como("plan-proy")
    cuenta = _cuenta()
    antiguo = client.post("/presupuestos", json={"categoria": "Comida", "limite": 400_000}).json()
    quincenal = client.post("/presupuestos", json={"categoria": "Ocio", "limite": 100_000, "periodo": "biweekly"}).json()
    assert antiguo["periodo"] == "monthly"
    for cat, monto in (("Comida", 30_000), ("Ocio", 20_000)):
        client.post("/movimientos", json={"cuenta_id": cuenta, "descripcion": cat, "monto": monto,
                                          "tipo": "expense", "categoria": cat})
    j = client.get("/planificacion/proyeccion").json()
    por_cat = {i["categoria"]: i for i in j["items"]}
    assert por_cat["Comida"]["periodo"] == "monthly" and por_cat["Comida"]["gastado"] == 30_000
    assert por_cat["Ocio"]["periodo"] == "biweekly" and por_cat["Ocio"]["gastado"] == 20_000
    assert por_cat["Ocio"]["dias_totales"] in (13, 14, 15, 16)
    assert set(j["totales"]) == {"monthly", "biweekly"}
    # disponible-hoy sigue respondiendo con ambos periodos
    d = client.get("/presupuestos/disponible-hoy").json()
    assert {c["categoria"] for c in d["categorias"]} == {"Comida", "Ocio"}
    assert quincenal["id"]


def test_arrastre_del_sobrante_del_periodo_anterior():
    como("plan-arr")
    cuenta = _cuenta()
    pr = client.post("/presupuestos", json={"categoria": "Comida", "limite": 500_000}).json()
    hoy = ahora_co()
    mes_pasado = (hoy.replace(day=1) - timedelta(days=1)).replace(day=10, hour=12)
    client.post("/movimientos", json={"cuenta_id": cuenta, "descripcion": "Mercado", "monto": 380_000,
                                      "tipo": "expense", "categoria": "Comida", "fecha": mes_pasado.isoformat()})
    sin = client.get("/planificacion/proyeccion").json()["items"][0]
    assert sin["limite"] == 500_000 and sin["arrastre"] == 0
    client.put("/planificacion/config", json={"arrastre_ids": [pr["id"]]})
    con = client.get("/planificacion/proyeccion").json()["items"][0]
    assert con["arrastre"] == 120_000 and con["limite"] == 620_000  # sobraron 500.000 - 380.000


def test_distribuir_ingreso_es_solo_sugerencia():
    como("plan-dist")
    db = SessionLocal()
    db.add(Recurrente(usuario_id="plan-dist", nombre="Arriendo", monto=1_500_000, tipo="expense"))
    db.add(Meta(usuario_id="plan-dist", nombre="Viaje", monto_objetivo=1_200_000, monto_actual=0,
                aporte_automatico=300_000))
    db.add(Presupuesto(usuario_id="plan-dist", categoria="Comida", limite=600_000))
    db.commit()
    db.close()
    r = client.post("/planificacion/distribuir-ingreso", json={"monto": 4_000_000}).json()
    # fijos 1.500.000; resto 2.500.000; ahorro 40 % = 1.000.000; libre 1.500.000.
    assert r["necesidades"] == 1_500_000 and r["ahorro_total"] == 1_000_000
    assert r["metas"][0]["monto"] == 300_000 and r["ahorro_libre"] == 700_000
    assert r["sobres"][0]["monto"] == 1_500_000
    assert client.post("/planificacion/distribuir-ingreso", json={"monto": 0}).status_code == 422
    # no se movió plata ni se creó nada
    assert client.get("/metas").json()[0]["monto_actual"] == 0


def test_plan_meta_usa_el_ahorro_historico():
    como("plan-meta")
    cuenta = _cuenta()
    hoy = ahora_co()
    # 3 meses completos atrás: ingresos 3M y gastos 2,4M cada mes => ahorro real 600.000/mes
    y, m = hoy.year, hoy.month
    for _ in range(3):
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        fecha = datetime(y, m, 10, 12).isoformat()
        client.post("/movimientos", json={"cuenta_id": cuenta, "descripcion": "Nómina", "monto": 3_000_000,
                                          "tipo": "income", "categoria": "Ingresos", "fecha": fecha})
        client.post("/movimientos", json={"cuenta_id": cuenta, "descripcion": "Vida", "monto": 2_400_000,
                                          "tipo": "expense", "categoria": "Otros", "fecha": fecha})
    fecha_obj = (hoy + timedelta(days=366)).isoformat()
    r = client.post("/planificacion/plan-meta",
                    json={"objetivo": 12_000_000, "saldo_actual": 0, "fecha_objetivo": fecha_obj}).json()
    assert r["historico"]["ahorro"] == pytest.approx(600_000)
    assert r["capacidad_ahorro"] == pytest.approx(600_000)
    assert r["meses_a_ritmo_actual"] == 20          # 12M / 600.000
    assert r["viabilidad"] == "incompatible"        # requiere ~1.000.000 > 600.000
    sin = client.post("/planificacion/plan-meta", json={"objetivo": 1_000_000}).json()
    assert sin["aporte_requerido"] is None


def test_descomposicion_de_patrimonio_desde_snapshots():
    como("plan-pat")
    db = SessionLocal()
    for mes, act, cta, deu in (("2026-08", 10_000_000, 2_000_000, 5_000_000),
                               ("2026-09", 11_000_000, 2_500_000, 4_500_000)):
        db.add(SnapshotPatrimonio(usuario_id="plan-pat", mes=mes, total_activos=act, total_cuentas=cta,
                                  total_deudas=deu, patrimonio_neto=act + cta - deu))
    db.commit()
    db.close()
    r = client.get("/planificacion/patrimonio-descomposicion").json()["meses"]
    assert len(r) == 1 and r[0]["mes"] == "2026-09"
    assert r[0]["neto_delta"] == 2_000_000
    assert r[0]["valorizacion"] == 1_000_000 and r[0]["reduccion_deuda"] == 500_000 and r[0]["ahorro"] == 500_000
    como("plan-pat-vacio")
    assert client.get("/planificacion/patrimonio-descomposicion").json() == {"meses": []}


def test_cron_alerta_predictiva_una_sola_vez_por_periodo(monkeypatch):
    """Presupuesto que NO ha llegado al umbral pero que al ritmo actual se pasaría."""
    from app.routers import push as mod
    from app import planificacion as plan

    enviados = []
    monkeypatch.setattr(mod, "enviar_push", lambda *a, **k: enviados.append(a[3]))
    # Fijamos "hoy" para controlar los días transcurridos: día 10 de un mes de 31 días.
    falso_hoy = datetime(ahora_co().year, ahora_co().month, 10, 12)
    monkeypatch.setattr(mod, "ahora_co", lambda: falso_hoy)

    db = SessionLocal()
    db.add(PushSubscription(usuario_id="plan-cron", endpoint="https://push.test/pc", p256dh="x", auth="y"))
    from app.models import Cuenta
    cuenta = Cuenta(usuario_id="plan-cron", nombre="B", saldo=1, moneda="COP")
    db.add(cuenta)
    db.flush()
    # 10 días, 60.000 gastados de 150.000 (40 %, bajo el umbral 80 %): ritmo 6.000/día
    # => cierra en 60.000 + 6.000*21 = 186.000 > 150.000.
    db.add(Presupuesto(usuario_id="plan-cron", categoria="Ocio", limite=150_000, alerta_pct=80))
    db.add(Movimiento(usuario_id="plan-cron", cuenta_id=cuenta.id, descripcion="Cine", categoria="Ocio",
                      tipo="expense", monto=60_000, fecha=falso_hoy))
    db.commit()
    db.close()

    # cierre esperado: 60.000 + 6.000/día * días que faltan del mes (sin histórico)
    rest = plan.rango_periodo(falso_hoy, "monthly")["dias_restantes"]
    esperado = plan.formato_cop(60_000 + 6_000 * rest)
    primera = client.post("/push/cron/revisar-presupuestos", headers=CRON).json()
    segunda = client.post("/push/cron/revisar-presupuestos", headers=CRON).json()
    assert primera["notificados"] == 1 and segunda["notificados"] == 0
    assert f"cerrarías en {esperado}" in enviados[0]
