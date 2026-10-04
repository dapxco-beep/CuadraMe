"""Registro 'cierre_app' (Atajo al cerrar Nequi) y cruce 1:1 con el extracto.

Los casos numéricos del cruce están calculados a mano (puntaje = días de
diferencia + 3 * diferencia de monto / monto del extracto)."""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'cierre.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.conciliacion import auditar_movimientos, emparejar_rapidos, hora_del_extracto, parse_bank_date  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Movimiento  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="c-0", email="c@test.com", nombre="C")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def _usuario(uid, cuentas):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)
    ids = {}
    for nombre, saldo in cuentas:
        ids[nombre] = client.post("/cuentas", json={"nombre": nombre, "saldo": saldo}).json()["id"]
    return client.get("/perfil/api-key").json()["api_key"], ids


def _saldos():
    return {c["nombre"]: c["saldo"] for c in client.get("/cuentas").json()}


# ---------- registro cierre_app ----------

def test_cierre_app_con_nota_clasifica_y_queda_por_confirmar():
    key, ids = _usuario("c-nota", [("Nequi", 100_000)])
    antes = ahora_co()
    r = client.post("/movimientos/rapido", headers={"X-Api-Key": key}, json={
        "tipo": "Gasto", "monto": "25.000", "descripcion": "Uber", "cuenta": "Nequi", "fuente": "cierre_app",
    })
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["fuente"] == "cierre_app" and m["cat_origen"] == "cierre_app" and m["cat_confirmada"] is False
    assert m["tipo"] == "expense" and m["monto"] == 25_000 and m["descripcion"] == "Uber"
    assert m["cuenta_id"] == ids["Nequi"] and m["por_confirmar"] is True
    assert m["categoria"] != "Otros"  # el clasificador usó la nota
    # hora exacta del registro, en hora de Colombia
    hora = datetime.fromisoformat(m["fecha"])
    assert antes - timedelta(seconds=5) <= hora <= ahora_co() + timedelta(seconds=5)
    assert _saldos()["Nequi"] == 75_000
    assert m["id"] in [x["id"] for x in client.get("/movimientos/por-confirmar").json()]


def test_cierre_app_sin_nota_usa_descripcion_por_defecto_y_otros():
    key, _ = _usuario("c-sin-nota", [("Nequi", 0)])
    r = client.post("/movimientos/rapido", headers={"X-Api-Key": key}, json={
        "tipo": "ingreso", "monto": 50000, "cuenta": "nequi", "fuente": "Cierre_App",
    })
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["descripcion"] == "Movimiento en Nequi" and m["categoria"] == "Otros"
    assert m["tipo"] == "income" and m["fuente"] == "cierre_app"
    assert _saldos()["Nequi"] == 50_000


def test_cierre_app_idempotente_por_monto_cuenta_y_tipo_en_un_minuto():
    key, _ = _usuario("c-dup", [("Nequi", 100_000), ("Daviplata", 100_000)])
    h = {"X-Api-Key": key}
    base = {"tipo": "gasto", "monto": "12.000", "cuenta": "Nequi", "fuente": "cierre_app"}
    a = client.post("/movimientos/rapido", headers=h, json=base)
    b = client.post("/movimientos/rapido", headers=h, json={**base, "descripcion": "otra nota"})
    assert b.json()["id"] == a.json()["id"] and b.json()["duplicado"] is True
    assert _saldos()["Nequi"] == 88_000
    # otra cuenta, otro tipo u otro monto sí son movimientos distintos
    assert client.post("/movimientos/rapido", headers=h, json={**base, "cuenta": "Daviplata"}).json()["duplicado"] is False
    assert client.post("/movimientos/rapido", headers=h, json={**base, "tipo": "ingreso"}).json()["duplicado"] is False
    assert client.post("/movimientos/rapido", headers=h, json={**base, "monto": "12.500"}).json()["duplicado"] is False
    # el mismo movimiento hace más de un minuto ya no cuenta como reintento
    db = SessionLocal()
    try:
        db.query(Movimiento).filter(Movimiento.id == a.json()["id"]).update({"fecha": ahora_co() - timedelta(minutes=3)})
        db.commit()
    finally:
        db.close()
    assert client.post("/movimientos/rapido", headers=h, json=base).json()["duplicado"] is False


def test_fuente_distinta_a_cierre_app_sigue_exigiendo_descripcion():
    key, _ = _usuario("c-422", [("Nequi", 0)])
    assert client.post("/movimientos/rapido", headers={"X-Api-Key": key}, json={"monto": 5000}).status_code == 422


# ---------- cruce 1:1 (puro) ----------

D = datetime(2026, 10, 3)


def fila(id_, hora, monto, tipo="expense", dia=D, **extra):
    return {"id": id_, "fecha": dia.replace(hour=hora[0], minute=hora[1]), "monto": monto, "tipo": tipo,
            "descripcion": id_, "fingerprint": f"fp-{id_}", "rapido": True, "conciliado": False, **extra}


def ext(monto, fecha="2026-10-03", tipo="expense", desc="COMPRA", **extra):
    return {"fecha": fecha, "descripcion": desc, "monto": monto, "tipo": tipo, "cuenta": "c1", **extra}


def cruce(extracto, ledger):
    r = auditar_movimientos(extracto, ledger, cruzar_rapidos=True)
    return [(i["estado"], i.get("match_id")) for i in r["review"]], r


def test_dos_gastos_del_mismo_monto_el_mismo_dia_se_emparejan_uno_a_uno():
    # Registrados: L1 10:00 y L2 15:00 por 20.000; el banco trae dos de 20.000.
    # Todos los puntajes son 0; gana el orden: extracto #1 con el más temprano.
    ledger = [fila("L2", (15, 0), 20_000), fila("L1", (10, 0), 20_000)]
    estados, r = cruce([ext(20_000), ext(20_000)], ledger)
    assert estados == [("completado", "L1"), ("completado", "L2")]
    assert r["completados"] == 2 and r["sobrantes"] == []


def test_un_movimiento_del_extracto_solo_empareja_con_uno_registrado():
    # Dos registrados iguales y un solo movimiento del banco: uno completado, el otro sobrante.
    ledger = [fila("L1", (10, 0), 20_000), fila("L2", (11, 0), 20_000)]
    estados, r = cruce([ext(20_000)], ledger)
    assert estados == [("completado", "L1")]
    assert [s["id"] for s in r["sobrantes"]] == ["L2"]
    # Un solo registrado y dos del banco: el segundo queda faltante.
    estados, r = cruce([ext(20_000), ext(20_000)], [fila("L1", (10, 0), 20_000)])
    assert estados == [("completado", "L1"), ("faltante", None)]
    assert r["faltantes"] == 1 and r["sobrantes"] == []


def test_gana_el_de_menor_diferencia_de_monto():
    # Banco 20.300. L1=20.000 -> dif 300, puntaje 3*300/20300 = 0,0443.
    # L2=20.400 -> dif 100, puntaje 3*100/20300 = 0,0148  => gana L2.
    ledger = [fila("L1", (12, 0), 20_000), fila("L2", (12, 0), 20_400)]
    estados, _ = cruce([ext(20_300)], ledger)
    assert estados == [("completado", "L2")]


def test_la_hora_del_extracto_desempata():
    # Mismo monto y mismo día; el banco dice 14:30. L2 (14:20) está a 600 s, L1 (10:00) a 16.200 s.
    ledger = [fila("L1", (10, 0), 20_000), fila("L2", (14, 20), 20_000)]
    estados, _ = cruce([ext(20_000, hora="14:30")], ledger)
    assert estados == [("completado", "L2")]
    # La hora también puede venir pegada a la fecha.
    estados, _ = cruce([ext(20_000, fecha="2026-10-03 10:05")], ledger)
    assert estados == [("completado", "L1")]
    assert hora_del_extracto({"fecha": "2026-10-03 10:05"}) == (10, 5, 0)
    assert hora_del_extracto({"fecha": "03/10/2026"}) is None
    assert parse_bank_date("03/10/2026 10:05") == datetime(2026, 10, 3)


def test_emparejado_global_no_deja_que_uno_robe_el_par_de_otro():
    # Banco: 20.000 y 20.400. Registrados: 20.400 y 20.000. Cada uno con su gemelo exacto.
    ledger = [fila("A", (9, 0), 20_400), fila("B", (9, 30), 20_000)]
    estados, _ = cruce([ext(20_000), ext(20_400)], ledger)
    assert estados == [("completado", "B"), ("completado", "A")]


def test_tolerancias_de_fecha_monto_y_tipo():
    ledger = [fila("L1", (12, 0), 20_000)]
    # monto: 5% de 20.000 = 1.000 (>500) => 21.000 entra, 21.100 no
    assert cruce([ext(21_000)], ledger)[0][0][0] == "completado"
    assert cruce([ext(21_100)], ledger)[0][0][0] == "faltante"
    # monto chico: tolerancia mínima de 500 (5% sería 275) => 5.000 vs 5.500 entra, 5.501 no
    chico = [fila("S", (12, 0), 5_000)]
    assert cruce([ext(5_500)], chico)[0][0][0] == "completado"
    assert cruce([ext(5_501)], chico)[0][0][0] == "faltante"
    # fecha: 3 días entra, 4 no
    assert cruce([ext(20_000, fecha="2026-10-06")], ledger)[0][0][0] == "completado"
    assert cruce([ext(20_000, fecha="2026-10-07")], ledger)[0][0][0] == "faltante"
    # tipo distinto (un ingreso no completa un gasto)
    assert cruce([ext(20_000, tipo="income")], ledger)[0][0][0] == "faltante"


def test_no_toca_conciliados_ni_los_que_no_son_rapidos_y_sobrantes_son_del_periodo():
    ya = fila("YA", (12, 0), 20_000, conciliado=True)
    manual = fila("MAN", (12, 0), 20_000, rapido=False)
    # el rápido de otro periodo (mes anterior) no es sobrante de este extracto
    viejo = fila("VIEJO", (12, 0), 7_000, dia=datetime(2026, 9, 1))
    libre = fila("OK", (13, 0), 20_000)
    estados, r = cruce([ext(20_000)], [ya, manual, viejo, libre])
    assert estados == [("completado", "OK")]
    assert r["sobrantes"] == []
    # sin 'libre': el conciliado se ignora, el manual cae al aproximado clásico
    estados, r = cruce([ext(20_000)], [ya, manual, viejo])
    assert estados == [("aproximado", "MAN")]


def test_emparejar_rapidos_ignora_filas_sin_fecha():
    assert emparejar_rapidos([ext(1000)], [{"id": "x", "fecha": None, "monto": 1000, "tipo": "expense"}]) == {}


# ---------- flujo completo por /conciliacion/procesar ----------

def _procesar(monkeypatch, cuenta_id, items):
    from app.routers import conciliacion as mod
    monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: "texto del extracto")
    monkeypatch.setattr(mod, "detectar_banco", lambda t: "nequi")
    monkeypatch.setattr(mod, "parse_texto_con_regex", lambda t: (items, 0))
    return client.post("/conciliacion/procesar", json={"cuenta_id": cuenta_id, "pdf_base64": "x"})


def test_flujo_completa_con_el_banco_confirma_y_lista_sobrantes(monkeypatch):
    key, ids = _usuario("c-flujo", [("Nequi", 500_000)])
    h = {"X-Api-Key": key}
    hoy = ahora_co().strftime("%Y-%m-%d")
    # 1) con nota "mi almuerzo" (queda en 'Otros' para el clasificador) -> el banco dice "RESTAURANTE EL CORRAL"
    a = client.post("/movimientos/rapido", headers=h, json={"tipo": "gasto", "monto": "25.000", "descripcion": "mi almuerzo", "cuenta": "Nequi", "fuente": "cierre_app"}).json()
    # 2) sin nota -> banco: "Envío a Juan Perez" (destinatario real)
    b = client.post("/movimientos/rapido", headers=h, json={"tipo": "gasto", "monto": "80.000", "cuenta": "Nequi", "fuente": "cierre_app"}).json()
    # 3) registrado que el banco no muestra (sobrante)
    c = client.post("/movimientos/rapido", headers=h, json={"tipo": "gasto", "monto": "9.000", "cuenta": "Nequi", "fuente": "cierre_app"}).json()
    items = [
        {"fecha": hoy, "descripcion": "RESTAURANTE EL CORRAL", "monto": 25_000, "tipo": "expense", "referencia": ""},
        {"fecha": hoy, "descripcion": "Envio a Juan Perez", "monto": 80_000, "tipo": "expense", "referencia": ""},
        {"fecha": hoy, "descripcion": "Netflix", "monto": 33_000, "tipo": "expense", "referencia": ""},
    ]
    r = _procesar(monkeypatch, ids["Nequi"], items)
    assert r.status_code == 200, r.text
    out = r.json()
    estados = {i["descripcion"]: i for i in out["review"] if i["estado"] != "sobrante"}
    assert estados["RESTAURANTE EL CORRAL"]["estado"] == "completado"
    assert estados["Envio a Juan Perez"]["estado"] == "completado"
    assert estados["Netflix"]["estado"] in ("faltante", "importado")  # Netflix: el diccionario lo auto-importa
    assert out["completados"] == 2 and out["sobrantes"] == 1 and out["faltantes"] + out["auto_importados"] == 1
    sobrante = [i for i in out["review"] if i["estado"] == "sobrante"][0]
    assert sobrante["match_id"] == c["id"] and sobrante["monto"] == 9_000

    por_id = {m["id"]: m for m in client.get("/movimientos").json()}
    ma, mb, mc = por_id[a["id"]], por_id[b["id"]], por_id[c["id"]]
    assert ma["descripcion"] == "RESTAURANTE EL CORRAL" and "Nota: mi almuerzo" in ma["notas"]
    assert mb["descripcion"] == "Envio a Juan Perez" and "Nota" not in (mb["notas"] or "")
    # categoría "Otros" tras el banco -> sigue por confirmar; sin cambios en saldo
    assert mc["descripcion"] == "Movimiento en Nequi"
    assert _saldos()["Nequi"] == 500_000 - 25_000 - 80_000 - 9_000 - (33_000 if estados["Netflix"]["estado"] == "importado" else 0)

    db = SessionLocal()
    try:
        fila_a = db.query(Movimiento).filter(Movimiento.id == a["id"]).first()
        assert fila_a.conciliado_en is not None and fila_a.extracto_id == out["historial_id"]
        assert db.query(Movimiento).filter(Movimiento.id == c["id"]).first().conciliado_en is None
        if fila_a.categoria != "Otros":
            assert fila_a.cat_confirmada is True
        else:
            assert fila_a.cat_confirmada is False
    finally:
        db.close()

    # Reabrir la revisión conserva las listas y los conteos.
    again = client.get(f"/conciliacion/historial/{out['historial_id']}").json()
    assert again["completados"] == 2 and again["sobrantes"] == 1

    # Subir otra vez el mismo extracto no vuelve a tocar lo ya conciliado.
    r2 = _procesar(monkeypatch, ids["Nequi"], items).json()
    assert r2["completados"] == 0
    assert sum(1 for i in r2["review"] if i["estado"] == "exacto") >= 2


def test_flujo_categoria_conocida_se_confirma(monkeypatch):
    key, ids = _usuario("c-cat", [("Nequi", 200_000)])
    a = client.post("/movimientos/rapido", headers={"X-Api-Key": key}, json={"tipo": "gasto", "monto": "30.000", "cuenta": "Nequi", "fuente": "cierre_app"}).json()
    hoy = ahora_co().strftime("%Y-%m-%d")
    r = _procesar(monkeypatch, ids["Nequi"], [{"fecha": hoy, "descripcion": "NETFLIX.COM", "monto": 30_000, "tipo": "expense", "referencia": ""}])
    assert r.json()["completados"] == 1
    m = {x["id"]: x for x in client.get("/movimientos").json()}[a["id"]]
    assert m["descripcion"] == "NETFLIX.COM"
    if m["categoria"] != "Otros":  # el diccionario de comercios reconoce Netflix
        assert m["cat_confirmada"] is True
        assert a["id"] not in [x["id"] for x in client.get("/movimientos/por-confirmar").json()]
