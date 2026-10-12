"""Tu plata trabajando: cálculo, cajitas neutrales, patrimonio sin doble conteo, tasas (admin 404)."""
import os
import tempfile
from datetime import date, datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'rend.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import consejos, rendimientos as calc  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
U = UsuarioActual(id="rend-u", email="u-rend@test.com", nombre="U")
V = UsuarioActual(id="rend-v", email="v-rend@test.com", nombre="V")
ADMIN = UsuarioActual(id="rend-admin", email="dueno-rend@test.com", nombre="Admin")
ACTUAL = {"u": U}


@pytest.fixture(autouse=True)
def _auth(monkeypatch):
    monkeypatch.setattr(settings, "admin_email", "dueno-rend@test.com")
    ACTUAL["u"] = U
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    yield
    app.dependency_overrides.pop(get_current_user, None)
    from app.derechos_titular import borrar_todo

    db = SessionLocal()
    try:
        for x in (U, V, ADMIN):
            borrar_todo(db, x.id, x.email)
    finally:
        db.close()


def _cuenta(saldo=1_000_000, tasa=None, tipo="ahorro", nombre="Mi ahorro"):
    r = client.post("/cuentas", json={"nombre": nombre, "saldo": saldo, "tipo": tipo, "tasa_ea": tasa})
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ── cálculo puro ─────────────────────────────────────────────────────────────────────
def test_ganancia_compuesta_ea():
    # 1.000.000 al 10 % E.A. durante un año = 100.000 exactos; durante medio año (1,1^0,5 - 1).
    assert calc.ganancia(1_000_000, 10, 365) == pytest.approx(100_000)
    assert calc.ganancia(1_000_000, 10, 365 / 2) == pytest.approx(1_000_000 * (1.1 ** 0.5 - 1))
    assert calc.ganancia(1_000_000, 0, 365) == 0
    assert calc.ganancia(0, 10, 30) == 0 and calc.ganancia(1000, None, 30) == 0


def test_estimar_dia_mes_anio():
    e = calc.estimar(1_000_000, 10, datetime(2026, 10, 15))
    assert e["anio"] == pytest.approx(100_000)
    assert e["mes_corrido"] == pytest.approx(1_000_000 * (1.1 ** (15 / 365) - 1))
    assert e["dia"] == pytest.approx(1_000_000 * (1.1 ** (1 / 365) - 1))
    assert calc.estimar(1000, None, datetime(2026, 10, 15)) is None
    assert calc.tasa_diaria_pct(10) == pytest.approx((1.1 ** (1 / 365) - 1) * 100)


def test_ahorro_extra_y_mediana():
    assert calc.ahorro_extra_anual(2_000_000, 0.10, 9.0) == pytest.approx(178_000)
    assert calc.ahorro_extra_anual(2_000_000, 10, 9) == 0
    assert calc.mediana([9, 11, 10]) == 10 and calc.mediana([9, 11]) == 10 and calc.mediana([]) is None


# ── cajitas: neutralidad y patrimonio ────────────────────────────────────────────────
def test_cajita_no_cambia_saldo_ni_patrimonio_ni_disponible():
    cid = _cuenta(1_000_000, tasa=0.1)
    antes_pat = client.get("/patrimonio").json()
    antes_cuentas = client.get("/cuentas/resumen").json()
    r = client.post("/rendimientos/cajitas", json={"cuenta_id": cid, "nombre": "Viaje", "saldo": 400_000, "tasa_ea": 9})
    assert r.status_code == 200, r.text
    k = r.json()["id"]
    assert client.post(f"/rendimientos/cajitas/{k}/mover", json={"monto": 100_000, "sentido": "entrar"}).status_code == 200
    assert client.post(f"/rendimientos/cajitas/{k}/mover", json={"monto": 50_000, "sentido": "salir"}).status_code == 200
    despues = client.get("/patrimonio").json()
    antes_pat.pop("historial", None)
    despues.pop("historial", None)  # la foto mensual solo cambia de hora
    assert despues == antes_pat
    assert client.get("/cuentas/resumen").json() == antes_cuentas
    cuentas = {c["id"]: c for c in client.get("/cuentas").json()}
    assert cuentas[cid]["saldo"] == 1_000_000
    # Mover plata no genera movimientos (no es gasto ni ingreso).
    assert client.get(f"/cuentas/{cid}/detalle").json()["movimientos"] == []
    res = client.get("/rendimientos").json()["cuentas"][0]
    assert res["saldo"] == 1_000_000 and res["principal"] == 550_000
    assert res["cajitas"][0]["saldo"] == 450_000


def test_no_se_puede_apartar_mas_que_el_saldo_principal():
    cid = _cuenta(100_000)
    assert client.post("/rendimientos/cajitas", json={"cuenta_id": cid, "nombre": "A", "saldo": 150_000}).status_code == 400
    k = client.post("/rendimientos/cajitas", json={"cuenta_id": cid, "nombre": "A", "saldo": 60_000}).json()["id"]
    assert client.post(f"/rendimientos/cajitas/{k}/mover", json={"monto": 50_000, "sentido": "entrar"}).status_code == 400
    assert client.post(f"/rendimientos/cajitas/{k}/mover", json={"monto": 70_000, "sentido": "salir"}).status_code == 400
    # Borrar la cajita devuelve la plata al saldo principal; el saldo de la cuenta no cambia.
    assert client.delete(f"/rendimientos/cajitas/{k}").status_code == 200
    r = client.get("/rendimientos").json()["cuentas"][0]
    assert r["principal"] == 100_000 and r["cajitas"] == []


def test_cajitas_solo_en_cuentas_de_ahorro_propias():
    tarjeta = _cuenta(0, tipo="credito", nombre="Visa")
    assert client.post("/rendimientos/cajitas", json={"cuenta_id": tarjeta, "nombre": "x"}).status_code == 400
    cid = _cuenta(500_000)
    ACTUAL["u"] = V
    assert client.post("/rendimientos/cajitas", json={"cuenta_id": cid, "nombre": "x"}).status_code == 404


def test_resumen_total_y_estimacion():
    cid = _cuenta(1_000_000, tasa=0.1)
    client.post("/rendimientos/cajitas", json={"cuenta_id": cid, "nombre": "Viaje", "saldo": 500_000, "tasa_ea": 10})
    r = client.get("/rendimientos").json()
    esperado_anio = calc.ganancia(500_000, 0.1, 365) + calc.ganancia(500_000, 10, 365)
    assert r["total"]["anio"] == pytest.approx(esperado_anio)
    assert r["total"]["hay_estimacion"] is True
    assert "estimación" in r["aviso_estimacion"].lower()
    assert r["cuentas"][0]["cajitas"][0]["tasa_fecha"]  # fecha de la tasa


def test_cuenta_sin_tasa_no_inventa_rendimiento():
    _cuenta(1_000_000, tasa=None)
    r = client.get("/rendimientos").json()
    assert r["cuentas"][0]["estimado"] is None and r["cuentas"][0]["sin_tasa"] is True
    assert r["total"]["hay_estimacion"] is False


def test_rendimientos_reales_leidos_por_nombre_de_categoria():
    cid = _cuenta(1_000_000, tasa=9)
    assert client.get("/rendimientos").json()["total"]["recibido_mes"] is None
    client.post("/movimientos", json={"cuenta_id": cid, "descripcion": "Abono intereses", "monto": 1234,
                                      "tipo": "income", "categoria": "Rendimientos"})
    assert client.get("/rendimientos").json()["total"]["recibido_mes"] == 1234


# ── comparación y consejo ────────────────────────────────────────────────────────────
def test_comparacion_plata_ociosa_y_consejo():
    cid = _cuenta(3_000_000, tasa=0.1)
    comp = client.get("/rendimientos").json()["comparacion"]
    assert len(comp["ociosa"]) == 1 and comp["ociosa"][0]["cuenta_id"] == cid
    assert comp["tasa_ref"] is not None and "no es asesoría" in comp["aviso"]
    assert comp["ociosa"][0]["extra_anual"] == pytest.approx(3_000_000 * (comp["tasa_ref"] - 0.1) / 100)
    # Opciones en orden neutral (alfabético), sin recomendar.
    nombres = [o["entidad"] for o in comp["opciones"]]
    assert nombres == sorted(nombres, key=str.lower)
    cs = client.get("/consejos").json()["consejos"]
    ids = [c["id"] for c in cs if c["id"].startswith("plata-ociosa:")]
    assert len(ids) == 1 and f":{cid}:" in ids[0]
    c = next(c for c in cs if c["id"] == ids[0])
    assert c["silenciable"] and c["aprende"] == "donde-rinde-mi-plata" and "recomend" not in c["texto"].lower()


def test_sin_diferencia_grande_no_hay_aviso():
    _cuenta(3_000_000, tasa=9.5)
    _cuenta(50_000, tasa=0.1, nombre="Chiquita")
    assert client.get("/rendimientos").json()["comparacion"]["ociosa"] == []


def test_regla_pura_usa_ids_estables():
    d = {"plata_ociosa": [{"cuenta_id": "c1", "nombre": "Nu", "saldo": 1_000_000, "tasa_actual": 0.1,
                           "tasa_ref": 9.0, "extra_anual": 89_000}]}
    hoy = datetime(2026, 10, 12)
    a, b = consejos._regla_plata_ociosa(d, hoy), consejos._regla_plata_ociosa(d, hoy)
    assert a[0]["id"] == b[0]["id"] == "plata-ociosa:c1:2026-10"
    assert consejos._regla_plata_ociosa({}, hoy) == []


# ── tasas de referencia ──────────────────────────────────────────────────────────────
def test_tasas_lectura_para_todos_con_semilla_marcada():
    r = client.get("/rendimientos/tasas").json()
    assert r["tasas"] and any("verifica en la app de tu banco" in (t["nota"] or "").lower() for t in r["tasas"])
    assert all(t["vigente_desde"] for t in r["tasas"])


def test_tasas_edicion_solo_admin_404_al_resto():
    t = client.get("/rendimientos/tasas").json()["tasas"][0]
    cuerpo = {"entidad": "X", "producto": "Y", "tasa_ea": 5, "tipo": "ahorro_vista"}
    assert client.put(f"/rendimientos/tasas/{t['id']}", json=cuerpo).status_code == 404
    assert client.post("/rendimientos/tasas", json=cuerpo).status_code == 404
    assert client.get("/rendimientos/tasas/admin").status_code == 404
    ACTUAL["u"] = ADMIN
    r = client.put(f"/rendimientos/tasas/{t['id']}", json={**cuerpo, "vigente_desde": date.today().isoformat()})
    assert r.status_code == 200 and r.json()["tasa_ea"] == 5
    assert client.post("/rendimientos/tasas", json={**cuerpo, "tipo": "raro"}).status_code == 422
    assert client.post("/rendimientos/tasas", json=cuerpo).status_code == 200


def test_panel_admin_avisa_tasas_con_mas_de_45_dias():
    ACTUAL["u"] = ADMIN
    t = client.get("/rendimientos/tasas/admin").json()["tasas"][0]
    cuerpo = {"entidad": t["entidad"], "producto": t["producto"], "tipo": t["tipo"], "tasa_ea": 9.0,
              "vigente_desde": (date.today() - timedelta(days=60)).isoformat()}
    assert client.put(f"/rendimientos/tasas/{t['id']}", json=cuerpo).status_code == 200
    panel = client.get("/metricas/panel").json()
    assert t["id"] in [x["id"] for x in panel["tasas_referencia"]["desactualizadas"]]
    cuerpo["vigente_desde"] = date.today().isoformat()
    client.put(f"/rendimientos/tasas/{t['id']}", json=cuerpo)
    panel = client.get("/metricas/panel").json()
    assert t["id"] not in [x["id"] for x in panel["tasas_referencia"]["desactualizadas"]]


def test_aislamiento_de_resumen_entre_usuarios():
    _cuenta(3_000_000, tasa=0.1, nombre="ZZPrivada")
    ACTUAL["u"] = V
    r = client.get("/rendimientos")
    assert "ZZPrivada" not in r.text and r.json()["cuentas"] == []
