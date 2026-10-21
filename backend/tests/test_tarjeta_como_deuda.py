"""La tarjeta de crédito es DEUDA. Cadena de 3 extractos SINTÉTICOS (números inventados).

Con un cupo de 1.000.000 y una deuda previa desconocida de 100.000:
  mayo  (corte 15-may): compra 200.000 + compra en cuotas 300.000 COMPLETA + manejo 10.000 - pago 150.000  -> debe 460.000
  junio (corte 14-jun): compra  80.000 + intereses 5.000 + manejo 10.000 - pago 200.000                      -> debe 355.000
  julio (corte 15-jul): compra 120.000 + manejo 10.000 - pago 100.000                                        -> debe 385.000
"""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'tarjeta_deuda.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import deuda_tarjeta as dt  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, HistorialExtracto, Movimiento  # noqa: E402

client = TestClient(app)
USUARIO = {"u": UsuarioActual(id="td-0", email="td@test.com", nombre="Td")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["u"]
    yield


def como(uid):
    USUARIO["u"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def _mov(cuenta, tipo, monto, fecha, desc, categoria="Otros"):
    r = client.post("/movimientos", json={"cuenta_id": cuenta, "tipo": tipo, "monto": monto, "descripcion": desc,
                                          "categoria": categoria, "fecha": fecha, "confirmar_nuevo": True})
    assert r.status_code in (200, 201), r.text
    return r.json().get("id")


def _linea(fecha, desc, monto, tipo):
    return {"fecha": fecha, "descripcion": desc, "monto": monto, "tipo": tipo, "estado": "importado", "fingerprint": f"{fecha}-{desc}-{monto}"}


def _extracto(uid, cuenta, *, inicio, corte, usado, lineas, completa=True, cupo=1_000_000, minimo=40_000, limite="2026-08-04"):
    resumen = {"corte": corte, "limite_pago": limite, "periodo": {"inicio": inicio, "fin": corte}, "cupo": cupo, "usado": usado,
               "disponible": cupo - usado, "pago_minimo": minimo, "deuda_a_pagar": 0.0, "deuda_restante": 0.0}
    lectura = {"resumen_tarjeta": resumen, "lectura_completa": completa, "lineas_leidas": len(lineas), "verificacion": [],
               "mensaje_lectura": "x"}
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta, banco_detectado="nu", estado="conciliado", fecha_corte=corte,
                              periodo_inicio=inicio, review_json=json.dumps(lineas), lectura_json=json.dumps(lectura))
        db.add(h)
        db.commit()
        return h.id
    finally:
        db.close()


MAYO = [_linea("2026-04-20", "Tienda Alfa", 200_000, "expense"), _linea("2026-05-02", "Computador Beta en cuotas", 300_000, "expense"),
        _linea("2026-05-10", "Cobro por cuota de manejo", 10_000, "expense"), _linea("2026-05-12", "Pago de tu tarjeta", 150_000, "income")]
JUNIO = [_linea("2026-05-20", "Tienda Gamma", 80_000, "expense"), _linea("2026-06-14", "Intereses de tu tarjeta", 5_000, "expense"),
         _linea("2026-06-10", "Cobro por cuota de manejo", 10_000, "expense"), _linea("2026-06-05", "Pago de tu tarjeta", 200_000, "income")]
JULIO = [_linea("2026-06-20", "Tienda Delta", 120_000, "expense"), _linea("2026-07-10", "Cobro por cuota de manejo", 10_000, "expense"),
         _linea("2026-07-01", "Pago de tu tarjeta", 100_000, "income")]


def _escenario(uid, *, completa=True, con_junio=True):
    """Tarjeta con sus movimientos importados y los extractos de mayo, junio y julio. Devuelve (cuenta, {mes: historial_id}, {desc: mov_id})."""
    como(uid)
    cuenta = client.post("/cuentas", json={"nombre": "Nu Tarjeta", "tipo": "credito", "saldo": 0}).json()["id"]
    ids = {}
    for lineas in (MAYO, JUNIO, JULIO):
        for l in lineas:
            if l["tipo"] == "income":
                ids[l["fecha"] + l["descripcion"]] = _mov(cuenta, "income", l["monto"], l["fecha"] + "T10:00:00", l["descripcion"], "Pago de tarjeta")
            else:
                ids[l["fecha"] + l["descripcion"]] = _mov(cuenta, "expense", l["monto"], l["fecha"] + "T10:00:00", l["descripcion"])
    h = {"mayo": _extracto(uid, cuenta, inicio="2026-04-16", corte="2026-05-15", usado=460_000, lineas=MAYO, completa=completa),
         "junio": _extracto(uid, cuenta, inicio="2026-05-16", corte="2026-06-14", usado=355_000, lineas=JUNIO),
         "julio": _extracto(uid, cuenta, inicio="2026-06-15", corte="2026-07-15", usado=385_000, lineas=JULIO)}
    return cuenta, h, ids


def _registrar():
    r = client.post("/conciliacion/cuadre/saldo-inicial-auto")
    assert r.status_code == 200, r.text
    return r.json()["registrados"]


def _saldo(cuenta):
    return next(c for c in client.get("/cuentas").json() if c["id"] == cuenta)["saldo"]


def _hist(hid):
    db = SessionLocal()
    try:
        h = db.get(HistorialExtracto, hid)
        return h.saldo_inicial_extracto, h.saldo_final_extracto, h.saldos_origen
    finally:
        db.close()


def _autos(cuenta):
    db = SessionLocal()
    try:
        return [(m.descripcion, m.tipo, m.monto, m.fecha.date().isoformat(), m.fuente) for m in
                db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta, Movimiento.fuente == "ajuste_saldo").all()]
    finally:
        db.close()


# ── Modelo: saldo = −deuda ────────────────────────────────────────────────────────────────────────
def test_la_cadena_deja_el_saldo_en_menos_la_deuda_y_coincide_con_el_extracto():
    cuenta, h, _ = _escenario("td-1")
    assert _saldo(cuenta) == -285_000  # sin ancla: la deuda previa de 100.000 falta
    reg = _registrar()
    assert len(reg) == 1 and "debías $100.000" in reg[0]["texto"]
    assert _saldo(cuenta) == -385_000  # = −usado de julio
    assert _hist(h["mayo"]) == (-100_000, -460_000, "extracto")  # inicial derivado de las líneas, final = −usado
    assert _hist(h["junio"])[:2] == (-460_000, -355_000)  # la cadena: el inicial es el final del anterior
    assert _hist(h["julio"])[:2] == (-355_000, -385_000)
    assert _autos(cuenta) == [("Deuda inicial", "expense", 100_000.0, "2026-04-15", "ajuste_saldo")]


def test_idempotente_y_un_solo_ajuste():
    cuenta, _, _ = _escenario("td-2")
    assert len(_registrar()) == 1
    assert _registrar() == [] and _registrar() == []
    assert len(_autos(cuenta)) == 1 and _saldo(cuenta) == -385_000


def test_si_la_tarjeta_empezo_en_el_primer_extracto_la_deuda_inicial_es_cero():
    como("td-3")
    cuenta = client.post("/cuentas", json={"nombre": "Nu Tarjeta", "tipo": "credito", "saldo": 0}).json()["id"]
    _mov(cuenta, "expense", 200_000, "2026-04-20T10:00:00", "Tienda Alfa")
    _mov(cuenta, "income", 50_000, "2026-05-12T10:00:00", "Pago de tu tarjeta", "Pago de tarjeta")
    lineas = [_linea("2026-04-20", "Tienda Alfa", 200_000, "expense"), _linea("2026-05-12", "Pago de tu tarjeta", 50_000, "income")]
    h = _extracto("td-3", cuenta, inicio="2026-04-16", corte="2026-05-15", usado=150_000, lineas=lineas)
    assert _registrar() == [] and _autos(cuenta) == []
    assert _hist(h) == (0.0, -150_000, "extracto") and _saldo(cuenta) == -150_000


def test_no_se_inventa_la_deuda_inicial_si_la_lectura_del_primer_extracto_no_esta_completa():
    cuenta, _, _ = _escenario("td-4", completa=False)
    assert _registrar() == [] and _autos(cuenta) == []
    est = client.get(f"/conciliacion/cuadre/saldo-inicial-auto/{cuenta}").json()
    assert est["tarjeta"] is True and est["falta"] == "Aún no puedo calcular con cuánto empezó tu tarjeta: faltan líneas del extracto de mayo."
    r = client.post("/conciliacion/cuadre/saldo-inicial-auto/recalcular", json={"cuenta_id": cuenta}).json()
    assert r["estado"] == "sin_lectura" and "faltan líneas del extracto de mayo" in r["texto"]
    assert _saldo(cuenta) == -285_000


def test_llega_un_extracto_mas_antiguo_y_la_deuda_inicial_se_recalcula():
    cuenta, _, _ = _escenario("td-5")
    _registrar()
    _extracto("td-5", cuenta, inicio="2026-03-16", corte="2026-04-15", usado=100_000, lineas=[])
    reg = _registrar()
    assert len(reg) == 1 and reg[0]["cambio"] == "actualizado"
    assert _autos(cuenta) == [("Deuda inicial", "expense", 100_000.0, "2026-03-15", "ajuste_saldo")]  # ahora parte del extracto de abril
    assert _saldo(cuenta) == -385_000


def test_la_persona_deshace_la_deuda_inicial_y_no_se_vuelve_a_crear():
    cuenta, _, _ = _escenario("td-6")
    mov = _registrar()[0]["movimiento_id"]
    assert client.post("/conciliacion/cuadre/deshacer", json={"movimiento_id": mov, "confirmar": True}).status_code == 200
    assert _saldo(cuenta) == -285_000 and _registrar() == [] and _autos(cuenta) == []


# ── Cuadre por extracto ───────────────────────────────────────────────────────────────────────────
def test_cada_extracto_cuadra_con_el_formato_de_deuda():
    cuenta, _, _ = _escenario("td-7")
    _registrar()
    r = client.get(f"/conciliacion/cuadre/encadenado?cuenta_id={cuenta}").json()
    assert r["cuadra"] is True and [m["estado"] for m in r["meses"]] == ["cuadra"] * 3
    junio = next(m for m in r["meses"] if m["mes"] == "2026-06")["tarjeta"]
    assert (junio["debia_inicio"], junio["compras_cargos"], junio["intereses"], junio["pagos"], junio["debo_calculado"],
            junio["segun_extracto"], junio["cuadra"]) == (460_000, 90_000, 5_000, 200_000, 355_000, 355_000, True)
    assert junio["texto"] == ("Debía al inicio $460.000 · Compras y cargos $90.000 · Intereses $5.000 · Pagos $200.000 · "
                              "Debo al corte $355.000 (calculado) · Según tu extracto $355.000 ✓")
    mayo = next(m for m in r["meses"] if m["mes"] == "2026-05")["tarjeta"]
    assert mayo["debia_inicio"] == 100_000 and mayo["compras_cargos"] == 510_000  # la compra en cuotas, completa


def test_una_linea_faltante_hace_fallar_ese_extracto_por_la_diferencia_exacta():
    cuenta, _, ids = _escenario("td-8")
    _registrar()
    db = SessionLocal()
    try:  # se pierde el movimiento de intereses de junio
        m = db.get(Movimiento, ids["2026-06-14Intereses de tu tarjeta"])
        c = db.get(Cuenta, cuenta)
        c.saldo = round(c.saldo + m.monto, 2)
        db.delete(m)
        db.commit()
    finally:
        db.close()
    r = client.get(f"/conciliacion/cuadre/encadenado?cuenta_id={cuenta}").json()
    junio = next(m for m in r["meses"] if m["mes"] == "2026-06")
    assert junio["estado"] == "diferencia" and r["cuadra"] is False
    t = junio["tarjeta"]
    assert t["cuadra"] is False and abs(t["diferencia"]) == 5_000 and "✕ por $5.000" in t["texto"]
    assert any(c_["codigo"] == "lineas_sin_importar" for c_ in junio["causas"]) is False  # la línea está "importada" en el extracto
    assert next(m for m in r["meses"] if m["mes"] == "2026-05")["estado"] == "cuadra"


def test_una_linea_sin_importar_se_senala_como_causa():
    cuenta, h, ids = _escenario("td-9")
    _registrar()
    db = SessionLocal()
    try:
        hh = db.get(HistorialExtracto, h["junio"])
        rev = json.loads(hh.review_json)
        for i in rev:
            if i["descripcion"].startswith("Intereses"):
                i["estado"] = "faltante"
        hh.review_json = json.dumps(rev)
        m = db.get(Movimiento, ids["2026-06-14Intereses de tu tarjeta"])
        c = db.get(Cuenta, cuenta)
        c.saldo = round(c.saldo + m.monto, 2)
        db.delete(m)
        db.commit()
    finally:
        db.close()
    junio = next(m for m in client.get(f"/conciliacion/cuadre/encadenado?cuenta_id={cuenta}").json()["meses"] if m["mes"] == "2026-06")
    assert any(c_["codigo"] == "falta_importar" for c_ in junio["causas"])


# ── Cupo y disponible en vivo, patrimonio e informes ──────────────────────────────────────────────
def test_cupo_y_disponible_en_vivo_con_los_movimientos_de_la_app():
    cuenta, _, _ = _escenario("td-10")
    _registrar()
    _mov(cuenta, "expense", 50_000, "2026-07-20T10:00:00", "Tienda Epsilon")
    _mov(cuenta, "income", 20_000, "2026-07-25T10:00:00", "Pago de tu tarjeta", "Pago de tarjeta")
    v = client.get("/cuentas/tarjetas/vista").json()[cuenta]
    assert v["deuda"] == 415_000 and v["deuda_al_corte"] == 385_000 and v["desde_corte"] == {"compras_cargos": 50_000, "pagos": 20_000}
    assert v["cupo"] == 1_000_000 and v["disponible"] == 585_000 and v["uso_pct"] == 41.5
    assert v["corte"] == "2026-07-15" and v["pago_minimo"] == 40_000
    assert v["deuda"] == -_saldo(cuenta)  # la vista en vivo y el saldo de la cuenta son la misma deuda
    det = client.get(f"/cuentas/{cuenta}/detalle").json()
    assert det["deuda_tarjeta"]["disponible"] == 585_000


def test_el_patrimonio_resta_la_tarjeta_como_deuda_sin_contarla_dos_veces():
    cuenta, _, _ = _escenario("td-11")
    _registrar()
    ahorro = client.post("/cuentas", json={"nombre": "Nu Ahorros", "tipo": "ahorro", "saldo": 1_000_000}).json()["id"]
    r = client.get("/cuentas/resumen").json()
    assert r["deudas_tarjeta_cop"] == 385_000 and r["disponible_cop"] == 1_000_000 and r["total_cop"] == 615_000
    assert ahorro and r["por_tipo"]["credito"] == -385_000


def test_los_pagos_de_la_tarjeta_no_son_ingresos_ni_gastos_en_informes_ni_en_el_cierre():
    cuenta, _, _ = _escenario("td-12")
    _registrar()
    ig = client.get("/informes/ingresos-gastos?desde=2026-04-01&hasta=2026-07-31")
    if ig.status_code == 200:
        assert ig.json().get("ingresos") == 0
    cierre = client.get("/cierre-mes/extractos?mes=2026-06")
    assert cierre.status_code == 200
    c = next(x for b in cierre.json()["bancos"] for x in b["cuentas"] if x["cuenta_id"] == cuenta)
    assert c["ingresos"] == 0 and c["estado"] == "cuadra"
    assert c["tarjeta_cuadre"]["pagos"] == 200_000 and c["tarjeta_cuadre"]["cuadra"] is True
    assert c["ajuste_inicial"] is None or c["ajuste_inicial"]["etiqueta"] == "Deuda inicial automática"


def test_aislamiento_entre_usuarios():
    cuenta_a, _, _ = _escenario("td-13")
    como("td-14")
    assert client.post("/conciliacion/cuadre/saldo-inicial-auto").json()["registrados"] == []
    assert cuenta_a not in client.get("/cuentas/tarjetas/vista").json()
    como("td-13")
    assert len(_registrar()) == 1


def test_funciones_puras_de_las_anclas():
    assert dt.usado_de_resumen({"usado": 65_000}) == (65_000.0, "extracto")
    assert dt.usado_de_resumen({"deuda_a_pagar": 40_000, "deuda_restante": 20_000, "cuota_manejo": 10_000, "cargos_conversion": 300,
                                "intereses": 700}) == (71_000.0, "estimado")
    assert dt.usado_de_resumen({"cupo": 1}) == (None, None) and dt.usado_de_resumen(None) == (None, None)
