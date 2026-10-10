"""Metas con sugerencia automática: cálculo puro (números hechos a mano), endpoint y regla de consejo."""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'metas_sug.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import consejos as c  # noqa: E402
from app import metas_plan as mp  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.derechos_titular import borrar_todo  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Meta, Movimiento  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

HOY = datetime(2026, 10, 15, 12, 0)


# ── cálculo puro ─────────────────────────────────────────────────────────────────────
def test_opciones_son_30_50_70_por_ciento_redondeadas_hacia_abajo():
    ops = mp.opciones_de_aporte(1_000_000)
    assert [(o["id"], o["monto"]) for o in ops] == [("comodo", 300_000), ("recomendado", 500_000), ("acelerado", 700_000)]
    assert [o["monto"] for o in mp.opciones_de_aporte(333_333)] == [95_000, 165_000, 230_000]


def test_sin_sobrante_no_hay_opciones():
    assert mp.opciones_de_aporte(None) == [] and mp.opciones_de_aporte(0) == [] and mp.opciones_de_aporte(-5) == []


def test_si_apartas_x_llegas_en_mes_y_anio():
    plan = mp.plan_de_meta({"monto_objetivo": 6_000_000, "monto_actual": 0}, 1_000_000, HOY)
    rec = next(o for o in plan["opciones"] if o["id"] == "recomendado")
    assert rec["meses"] == 12 and rec["llegas"] == "octubre de 2027"
    assert rec["texto"] == "Si apartas $500.000 al mes llegas en octubre de 2027"
    assert plan["estado_ritmo"] == "sin_fecha" and plan["aporte_necesario_mes"] is None


def test_aporte_necesario_para_llegar_a_tiempo():
    fin = datetime(2027, 4, 15, 12, 0)  # 6 meses exactos
    plan = mp.plan_de_meta({"monto_objetivo": 3_000_000, "monto_actual": 600_000, "fecha_objetivo": fin,
                            "fecha_inicio": HOY}, 800_000, HOY)
    assert plan["faltante"] == 2_400_000 and plan["aporte_necesario_mes"] == 400_000
    assert plan["texto_necesario"] == "Para llegar a tiempo necesitas $400.000 al mes"
    # 30 % de 800.000 = 240.000 no alcanza; 50 % = 400.000 sí llega a tiempo y es la sugerida
    por_id = {o["id"]: o for o in plan["opciones"]}
    assert por_id["comodo"]["a_tiempo"] is False and por_id["recomendado"]["a_tiempo"] is True
    assert plan["opcion_sugerida"] == "recomendado"


def test_adelantado_al_dia_y_atrasado():
    ini, fin = datetime(2026, 7, 15), datetime(2027, 1, 15)  # mitad del camino hoy: ~esperado 50 %
    base = {"monto_objetivo": 1_000_000, "fecha_inicio": ini, "fecha_objetivo": fin}
    assert mp.plan_de_meta({**base, "monto_actual": 800_000}, None, HOY)["estado_ritmo"] == "adelantado"
    assert mp.plan_de_meta({**base, "monto_actual": 500_000}, None, HOY)["estado_ritmo"] == "al_dia"
    atras = mp.plan_de_meta({**base, "monto_actual": 100_000}, None, HOY)
    assert atras["estado_ritmo"] == "atrasado" and "Vas atrasado" in atras["frase_ritmo"]
    assert mp.plan_de_meta({**base, "monto_actual": 1_000_000}, None, HOY)["estado_ritmo"] == "lograda"


def test_sin_datos_y_fecha_vencida_hablan_claro():
    p = mp.plan_de_meta({"monto_objetivo": 1_000_000, "monto_actual": 0}, None, HOY)
    assert p["opciones"] == [] and "mes completo" in p["aviso_sobrante"]
    v = mp.plan_de_meta({"monto_objetivo": 1_000_000, "monto_actual": 0, "fecha_objetivo": HOY - timedelta(days=3)}, 100_000, HOY)
    assert v["estado_ritmo"] == "vencida" and v["aporte_necesario_mes"] is None
    s = mp.plan_de_meta({"monto_objetivo": 1_000_000, "monto_actual": 0}, -50_000, HOY)
    assert s["opciones"] == [] and "no te ha sobrado" in s["aviso_sobrante"]


def test_sumar_meses_en_fin_de_mes():
    assert mp.sumar_meses(datetime(2026, 1, 31), 1) == datetime(2026, 2, 28)
    assert mp.sumar_meses(datetime(2026, 11, 30), 3) == datetime(2027, 2, 28)


# ── regla de consejo «meta sin aporte este mes» ───────────────────────────────────────
def _meta(**kw):
    m = {"id": "m1", "nombre": "Viaje", "monto_actual": 100_000, "monto_objetivo": 1_000_000, "activa": True,
         "creada_en": HOY - timedelta(days=60), "ultimo_aporte": None}
    m.update(kw)
    return m


def _datos(metas):
    return {"cuentas": [], "movimientos": [], "movimientos_neutros": [], "presupuestos": [], "metas": metas,
            "deudas": [], "recurrentes": []}


def _sin_aporte(metas, hoy=HOY):
    return [x for x in c.generar(_datos(metas), hoy) if x["tipo"] == "meta_sin_aporte"]


def test_meta_sin_aporte_este_mes_genera_consejo_con_id_de_meta():
    r = _sin_aporte([_meta()])
    assert len(r) == 1 and r[0]["meta_id"] == "m1" and r[0]["accion"]["ruta"] == "/metas"
    assert r[0]["id"] == "meta-sin-aporte:m1:2026-10" and r[0]["cifra"] == "$900.000"


def test_no_aplica_si_ya_aporto_es_nueva_esta_completa_o_es_inicio_de_mes():
    assert _sin_aporte([_meta(ultimo_aporte=HOY - timedelta(days=3))]) == []
    assert _sin_aporte([_meta(creada_en=HOY - timedelta(days=2))]) == []
    assert _sin_aporte([_meta(monto_actual=1_000_000)]) == []
    assert _sin_aporte([_meta(activa=False)]) == []
    assert _sin_aporte([_meta()], hoy=datetime(2026, 10, 3)) == []
    # un aporte del mes anterior NO cuenta
    assert len(_sin_aporte([_meta(ultimo_aporte=datetime(2026, 9, 28))])) == 1


# ── endpoint ─────────────────────────────────────────────────────────────────────────
client = TestClient(app)
U = UsuarioActual(id="metas-sug-u", email="metas-sug@test.com", nombre="Ana")


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: U
    yield
    app.dependency_overrides.pop(get_current_user, None)
    db = SessionLocal()
    try:
        borrar_todo(db, U.id, U.email)
    finally:
        db.close()


def _mes_atras(n):
    hoy = ahora_co()
    total = hoy.year * 12 + hoy.month - 1 - n
    return datetime(total // 12, total % 12 + 1, 10, 12, 0)


def _sembrar_tres_meses():
    cta = client.post("/cuentas", json={"nombre": "Banco", "saldo": 5_000_000}).json()["id"]
    otra = client.post("/cuentas", json={"nombre": "Efectivo", "saldo": 0}).json()["id"]
    for n in (1, 2, 3):
        f = _mes_atras(n).isoformat()
        for desc, monto, tipo in (("Nómina", 3_000_000, "income"), ("Arriendo", 1_500_000, "expense"),
                                  ("Mercado", 500_000, "expense")):
            r = client.post("/movimientos", json={"cuenta_id": cta, "descripcion": desc, "monto": monto,
                                                  "tipo": tipo, "fecha": f, "categoria": "Otros"})
            assert r.status_code == 200, r.text
        # un traslado propio grande NO debe contar como gasto ni ingreso
        client.post("/movimientos/transferencia", json={"cuenta_origen_id": cta, "cuenta_destino_id": otra,
                                                        "monto": 700_000, "fecha": f})
    return cta, otra


def test_sugerencias_usa_el_sobrante_real_sin_traslados():
    _sembrar_tres_meses()
    meta = client.post("/metas", json={"nombre": "Viaje", "monto_objetivo": 6_000_000,
                                       "fecha_objetivo": (ahora_co() + timedelta(days=365)).isoformat()}).json()
    r = client.get("/metas/sugerencias")
    assert r.status_code == 200
    d = r.json()
    assert d["sobrante_mensual"] == 1_000_000 and d["meses_con_datos"] == 3
    plan = d["metas"][meta["id"]]
    assert [o["monto"] for o in plan["opciones"]] == [300_000, 500_000, 700_000]
    assert plan["aporte_necesario_mes"] is not None and plan["texto_necesario"].startswith("Para llegar a tiempo")


def test_simular_meta_que_aun_no_existe_y_sin_historial():
    r = client.post("/metas/simular", json={"monto_objetivo": 2_000_000})
    assert r.status_code == 200
    assert r.json()["sobrante_mensual"] is None and r.json()["opciones"] == []
    assert client.post("/metas/simular", json={"monto_objetivo": 0}).status_code == 422


def test_aportar_desde_cuenta_deja_traslado_neutro_y_fecha_de_aporte():
    cta, _ = _sembrar_tres_meses()
    meta = client.post("/metas", json={"nombre": "Moto", "monto_objetivo": 1_000_000}).json()
    r = client.post(f"/metas/{meta['id']}/aportar?monto=250000&cuenta_id={cta}")
    assert r.status_code == 200 and r.json()["monto_actual"] == 250_000
    db = SessionLocal()
    try:
        mov = db.query(Movimiento).filter(Movimiento.usuario_id == U.id, Movimiento.fuente == "aporte_meta").one()
        assert mov.notas == f"META:{meta['id']}" and mov.monto == 250_000 and mov.categoria == "Aporte a meta"
        assert db.query(Meta).filter(Meta.id == meta["id"]).one().ultimo_aporte is not None
    finally:
        db.close()
    # el aporte no cuenta como gasto en los números que alimentan la sugerencia
    assert client.get("/metas/sugerencias").json()["sobrante_mensual"] == 1_000_000


def test_aportar_sin_cuenta_no_crea_movimiento_pero_si_fecha():
    meta = client.post("/metas", json={"nombre": "Moto", "monto_objetivo": 1_000_000}).json()
    assert client.post(f"/metas/{meta['id']}/aportar?monto=100000").status_code == 200
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.usuario_id == U.id).count() == 0
        assert db.query(Meta).filter(Meta.id == meta["id"]).one().ultimo_aporte is not None
    finally:
        db.close()


def test_consejos_endpoint_incluye_meta_sin_aporte(monkeypatch):
    # el motor lee la hora real: se fija un día > 8 del mes y una meta creada hace semanas
    meta = client.post("/metas", json={"nombre": "Casa", "monto_objetivo": 5_000_000}).json()
    db = SessionLocal()
    try:
        m = db.query(Meta).filter(Meta.id == meta["id"]).one()
        m.creado_en = datetime(2026, 8, 1)
        db.commit()
    finally:
        db.close()
    from app.routers import consejos as rc

    monkeypatch.setattr(rc, "ahora_co", lambda: datetime(2026, 10, 20, 12, 0))
    cons = client.get("/consejos").json()["consejos"]
    assert any(x["tipo"] == "meta_sin_aporte" and x["meta_id"] == meta["id"] for x in cons)
