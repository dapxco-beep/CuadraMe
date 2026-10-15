"""Cuadre encadenado mes a mes. Datos 100 % inventados.

Patrón sintético (reproduce el caso real sin sus cifras):
  mayo   banco 500.000 -> 700.000   app: +300.000 -100.000            (el saldo inicial de 500.000 no está registrado)
  junio  banco 700.000 -> 1.750.000 app: +400.000 -150.000            (el banco trae además un ingreso de 800.000 sin importar)
  julio  banco 1.750.000 -> 1.700.000 app: -50.000
"""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'cuadre_enc.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import cuadre_encadenado as ce  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import HistorialExtracto  # noqa: E402

client = TestClient(app)
USUARIO = {"u": UsuarioActual(id="ce-0", email="c@test.com", nombre="Ce")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["u"]
    yield


def como(uid):
    USUARIO["u"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def _mov(cuenta, tipo, monto, fecha, desc="x"):
    r = client.post("/movimientos", json={"cuenta_id": cuenta, "tipo": tipo, "monto": monto, "descripcion": desc,
                                          "categoria": "Otros", "fecha": fecha, "confirmar_nuevo": True})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _hist(uid, cuenta, *, ini, fin, inicio, corte, review=None, **extra):
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta, banco_detectado="prueba", estado="pendiente_revision",
                              review_json=json.dumps(review or []), saldo_inicial_extracto=ini, saldo_final_extracto=fin,
                              periodo_inicio=inicio, fecha_corte=corte, saldos_origen="extracto", **extra)
        db.add(h)
        db.commit()
        return h.id
    finally:
        db.close()


LINEA = {"fecha": "2026-06-16", "descripcion": "Abono prueba", "monto": 800_000, "tipo": "income",
         "fingerprint": "fp-800", "estado": "faltante", "referencia": ""}


def _escenario(uid, *, junio=True, cadena_mala=False, con_linea=True):
    como(uid)
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "tipo": "ahorro", "saldo": 0}).json()["id"]
    _mov(cuenta, "income", 300_000, "2026-05-05T10:00:00", "Pago")
    _mov(cuenta, "expense", 100_000, "2026-05-10T10:00:00", "Compra")
    _mov(cuenta, "income", 400_000, "2026-06-03T10:00:00", "Pago")
    _mov(cuenta, "expense", 150_000, "2026-06-20T10:00:00", "Compra")
    _mov(cuenta, "expense", 50_000, "2026-07-08T10:00:00", "Compra")
    h = {"mayo": _hist(uid, cuenta, ini=500_000, fin=700_000, inicio="2026-05-01", corte="2026-05-31")}
    if junio:
        h["junio"] = _hist(uid, cuenta, ini=700_000, fin=1_750_000, inicio="2026-06-01", corte="2026-06-30",
                           review=[dict(LINEA)] if con_linea else [])
    h["julio"] = _hist(uid, cuenta, ini=(1_700_000 if cadena_mala else 1_750_000),
                       fin=(1_650_000 if cadena_mala else 1_700_000),
                       inicio="2026-07-01", corte="2026-07-31")
    return cuenta, h


def _enc(cuenta):
    r = client.get(f"/conciliacion/cuadre/encadenado?cuenta_id={cuenta}")
    assert r.status_code == 200, r.text
    return r.json()


def _por_mes(r):
    return {m["mes"]: m for m in r["meses"]}


def test_mes_culpable_es_junio_por_la_linea_que_falta_y_julio_solo_arrastra():
    cuenta, h = _escenario("ce-1")
    r = _enc(cuenta)
    m = _por_mes(r)
    assert m["2026-05"]["estado"] == "solo_saldo_inicial" and m["2026-05"]["arrastre"] == 500_000
    assert m["2026-05"]["diferencia"] == 0
    j = m["2026-06"]
    assert j["estado"] == "diferencia" and j["diferencia"] == 800_000
    assert j["banco_cambio"] == 1_050_000 and j["app_cambio"] == 250_000
    causa = next(c for c in j["causas"] if c["codigo"] == "falta_importar")
    assert causa["efecto"] == 800_000 and len(causa["lineas"]) == 1
    assert "1 línea" in causa["texto"] and "$800.000" in causa["texto"]
    acc = next(a for a in j["acciones"] if a["tipo"] == "importar_lineas")
    assert acc["fingerprints"] == ["fp-800"] and acc["historial_id"] == h["junio"] and acc["confirmacion"]
    assert m["2026-07"]["estado"] == "arrastra" and m["2026-07"]["diferencia"] == 0
    assert "junio" in m["2026-07"]["texto"]
    assert r["culpables"] == ["2026-05", "2026-06"] and r["cuadra"] is False
    assert not any(f.get("cadena_rota") for f in r["meses"])  # la cadena del banco es consistente
    assert "$800.000" in r["resumen"] and "1 línea" in r["resumen"] and "junio" in r["resumen"]
    assert r["saldo_corregido"]["queda_diferencia"] == 0 and r["saldo_corregido"]["saldo_app_corregido"] == 1_700_000


def test_reparar_importando_la_linea_y_el_saldo_inicial_cuadra_todo_el_historial():
    cuenta, h = _escenario("ce-2")
    r = client.post(f"/conciliacion/historial/{h['junio']}/importar", json={"fingerprints": ["fp-800"]})
    assert r.status_code == 200, r.text
    m = _por_mes(_enc(cuenta))
    # recalculado, no guardado al subir: junio ya no tiene diferencia propia; solo arrastra el saldo inicial de mayo
    assert m["2026-06"]["diferencia"] == 0 and m["2026-06"]["estado"] == "arrastra" and "mayo" in m["2026-06"]["texto"]
    assert m["2026-05"]["estado"] == "solo_saldo_inicial"
    r = client.post("/conciliacion/cuadre/saldo-inicial", json={
        "cuenta_id": cuenta, "modo": "extracto", "historial_id": h["mayo"], "saldo_inicial": 500_000,
        "periodo_inicio": "2026-05-01", "confirmar": True})
    assert r.status_code == 200, r.text
    r = _enc(cuenta)
    assert [f["estado"] for f in r["meses"]] == ["cuadra", "cuadra", "cuadra"]
    assert r["cuadra"] is True and r["culpables"] == []
    db = SessionLocal()
    try:
        hh = db.get(HistorialExtracto, h["junio"])
        assert hh.cuadre_estado == "cuadra" and hh.cuadre_en is not None  # caché con fecha
    finally:
        db.close()


def test_hueco_por_extracto_ausente_y_cadena_rota():
    cuenta, _ = _escenario("ce-3", junio=False)
    m = _por_mes(_enc(cuenta))
    assert m["2026-06"]["estado"] == "falta_extracto" and "Falta el extracto de junio" in m["2026-06"]["texto"]
    assert m["2026-07"]["arrastre"] != 0  # el hueco se ve como arrastre, no como error de julio
    cuenta2, _ = _escenario("ce-4", cadena_mala=True)
    j = _por_mes(_enc(cuenta2))["2026-07"]
    assert j["cadena_rota"] is True and "Hueco o extracto faltante entre Junio 2026 y Julio 2026" in j["texto"]


def test_movimiento_repetido_con_monto_igual_a_la_diferencia():
    como("ce-5")
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "tipo": "ahorro", "saldo": 0}).json()["id"]
    _mov(cuenta, "income", 100_000, "2026-08-02T10:00:00", "Pago")
    _mov(cuenta, "expense", 30_000, "2026-08-10T10:00:00", "Cafe uno")
    _mov(cuenta, "expense", 30_000, "2026-08-10T11:00:00", "Cafe dos")
    _hist("ce-5", cuenta, ini=0, fin=70_000, inicio="2026-08-01", corte="2026-08-31")
    j = _por_mes(_enc(cuenta))["2026-08"]
    assert j["estado"] == "diferencia" and j["diferencia"] == 30_000
    c = next(c for c in j["causas"] if c["codigo"] == "movimiento_de_mas")
    assert c["movimiento_id"]
    assert any(a["tipo"] == "revisar_duplicado" for a in j["acciones"])
    assert not any(a["tipo"] == "ajuste" for a in j["acciones"])  # hay causa: no se ofrece el ajuste


def test_sin_causa_ofrece_ajuste_como_ultimo_recurso_con_advertencia():
    como("ce-6")
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "tipo": "ahorro", "saldo": 0}).json()["id"]
    _mov(cuenta, "income", 100_000, "2026-08-02T10:00:00", "Pago")
    _hist("ce-6", cuenta, ini=0, fin=123_456, inicio="2026-08-01", corte="2026-08-31")
    j = _por_mes(_enc(cuenta))["2026-08"]
    a = next(a for a in j["acciones"] if a["tipo"] == "ajuste")
    assert a["ultimo_recurso"] and "puede ocultar" in a["confirmacion"]


def test_subconjunto_que_explica_la_diferencia():
    assert ce.subconjunto_que_explica([500, -200, 300, 50], 800) == [0, 2]
    assert ce.subconjunto_que_explica([100, 200, 300, 400], 1000) is None  # exigiría 4 líneas
    assert ce.subconjunto_que_explica([10, 20], 0) is None


def test_dos_lineas_pendientes_explican_la_diferencia():
    como("ce-7")
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "tipo": "ahorro", "saldo": 0}).json()["id"]
    _mov(cuenta, "income", 100_000, "2026-08-02T10:00:00", "Pago")
    lineas = [{"fecha": "2026-08-05", "descripcion": "A", "monto": 20_000, "tipo": "income", "fingerprint": "a", "estado": "faltante"},
              {"fecha": "2026-08-06", "descripcion": "B", "monto": 5_000, "tipo": "income", "fingerprint": "b", "estado": "faltante"},
              {"fecha": "2026-08-07", "descripcion": "C", "monto": 9_000, "tipo": "expense", "fingerprint": "c", "estado": "faltante"}]
    _hist("ce-7", cuenta, ini=0, fin=125_000, inicio="2026-08-01", corte="2026-08-31", review=lineas)
    j = _por_mes(_enc(cuenta))["2026-08"]
    c = next(c for c in j["causas"] if c["codigo"] == "falta_importar")
    assert sorted(l["fingerprint"] for l in c["lineas"]) == ["a", "b"]
    acc = next(a for a in j["acciones"] if a["tipo"] == "importar_lineas")
    assert sorted(acc["fingerprints"]) == ["a", "b"]


def test_extracto_sin_saldo_pide_escribirlo_y_se_guarda_como_manual():
    como("ce-8")
    cuenta = client.post("/cuentas", json={"nombre": "Nu", "tipo": "ahorro", "saldo": 0}).json()["id"]
    _mov(cuenta, "income", 100_000, "2026-09-02T10:00:00", "Pago")
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id="ce-8", cuenta_id=cuenta, banco_detectado="nu", estado="conciliado",
                              review_json=json.dumps([{"fecha": "2026-09-02", "descripcion": "Pago", "monto": 100000,
                                                       "tipo": "income", "estado": "exacto", "fingerprint": "z"}]))
        db.add(h)
        db.commit()
        hid = h.id
    finally:
        db.close()
    r = _enc(cuenta)
    assert r["meses"] == [] and len(r["sin_saldo"]) == 1
    assert "No pude leer el saldo" in r["sin_saldo"][0]["texto"] and not r["sin_saldo"][0]["releyendo"]
    ok = client.post("/conciliacion/cuadre/saldos", json={"historial_id": hid, "saldo_final": 100_000, "fecha_corte": "2026-09-30",
                                                           "saldo_inicial": 0, "confirmar": True})
    assert ok.status_code == 200, ok.text
    r = _enc(cuenta)
    assert r["sin_saldo"] == [] and r["meses"][0]["estado"] == "cuadra" and r["meses"][0]["saldos_origen"] == "manual"


def test_estado_de_sincronizacion_trae_la_insignia_y_por_hacer_dice_la_cifra():
    _escenario("ce-9")
    r = client.get("/sincronizacion/estado")
    assert r.status_code == 200, r.text
    d = r.json()
    t = {x["id"]: x for x in d["tareas"]}.get("cuadre_no_cuadra")
    assert t and "$800.000" in t["detalle"] and "junio" in t["detalle"]
    assert d["cuadre_mensual"] and d["cuadre_mensual"][0]["culpables"]
    e = client.get("/sincronizacion/extractos").json()
    assert "items" in e


# ── Estado a la vista (GET /conciliacion/cuadre/resumen) ───────────────────────────────
def _resumen():
    r = client.get("/conciliacion/cuadre/resumen")
    assert r.status_code == 200, r.text
    return r.json()


def test_resumen_no_cuadra_dice_mes_diferencia_y_accion():
    cuenta, _ = _escenario("ce-10")
    r = _resumen()
    it = next(x for x in r["cuentas"] if x["cuenta_id"] == cuenta)
    assert it["estado"] == "no_cuadra" and it["mes"] == "2026-05"  # primer mes con problema: falta el saldo inicial
    assert it["texto"].startswith("No cuadra en mayo (dif. $")
    assert "saldo inicial" in it["accion"] and it["ruta"] == "/sincronizacion#cuadre"
    assert r["hay_problema"] is True and r["n_no_cuadran"] == 1 and r["aviso"]


def test_resumen_cuadra_cuando_todo_cierra_y_no_hay_aviso():
    como("ce-11")
    cuenta = client.post("/cuentas", json={"nombre": "Banco ok", "tipo": "ahorro", "saldo": 0}).json()["id"]
    _mov(cuenta, "income", 100_000, "2026-09-02T10:00:00", "Pago")
    _hist("ce-11", cuenta, ini=0, fin=100_000, inicio="2026-09-01", corte="2026-09-30")
    r = _resumen()
    it = r["cuentas"][0]
    assert it["estado"] == "cuadra" and it["texto"] == "Cuadra a septiembre" and it["accion"] is None
    assert r["hay_problema"] is False and r["aviso"] is None


def test_resumen_extracto_sin_saldo_es_de_datos_y_pide_escribirlo():
    como("ce-12")
    client.post("/cuentas", json={"nombre": "Nu", "tipo": "ahorro", "saldo": 0})
    cuenta = _resumen()["cuentas"][0]["cuenta_id"]
    db = SessionLocal()
    try:
        db.add(HistorialExtracto(usuario_id="ce-12", cuenta_id=cuenta, banco_detectado="nu", estado="conciliado",
                                 review_json=json.dumps([{"fecha": "2026-09-02", "descripcion": "Pago", "monto": 1,
                                                          "tipo": "income", "estado": "exacto", "fingerprint": "q"}])))
        db.commit()
    finally:
        db.close()
    it = _resumen()["cuentas"][0]
    assert it["estado"] == "sin_saldo" and it["de_datos"] is True
    assert it["texto"] == "Sin saldo del extracto para cuadrar" and "Escribe el saldo" in it["accion"]


def test_resumen_cuenta_sin_extractos_pide_subirlos_y_no_avisa():
    como("ce-13")
    client.post("/cuentas", json={"nombre": "Sin nada", "tipo": "ahorro", "saldo": 0})
    r = _resumen()
    assert r["cuentas"][0]["estado"] == "sin_extractos" and "Sube el extracto" in r["cuentas"][0]["accion"]
    assert r["hay_problema"] is False


def test_resumen_solo_ve_cuentas_propias():
    _escenario("ce-14")
    como("ce-15")
    assert _resumen()["cuentas"] == []
