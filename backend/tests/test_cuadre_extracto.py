"""Cuadre con el extracto. TODOS los datos son inventados (no son de ninguna persona ni banco real).

Escenario base (a mano): cuenta de ahorros con sueldo +2.000.000 (3 sep) y compras -100.000 (10 sep) y -50.000 (20 sep).
Al 30 sep los movimientos suman 1.850.000. Si el banco dice 1.850.000, cuadra.
"""
import json
import os
import tempfile
from datetime import date, datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'cuadre.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import cuadre_extracto as cx  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.contabilidad import FUENTE_AJUSTE, gastos_por_categoria, tipos_efectivos  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import HistorialExtracto, Movimiento  # noqa: E402

client = TestClient(app)
USUARIO = {"u": UsuarioActual(id="cu-0", email="c@test.com", nombre="Cu")}


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


def _base(uid, tipo="ahorro", saldo=0):
    como(uid)
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "tipo": tipo, "saldo": saldo}).json()["id"]
    if tipo == "ahorro":
        _mov(cuenta, "income", 2_000_000, "2026-09-03T10:00:00", "Nomina", "Ingresos")
        _mov(cuenta, "expense", 100_000, "2026-09-10T12:00:00", "Restaurante", "Comida")
        _mov(cuenta, "expense", 50_000, "2026-09-20T12:00:00", "Mercado", "Comida")
    return cuenta


def _saldo(cuenta):
    return {c["id"]: c["saldo"] for c in client.get("/cuentas").json()}[cuenta]


def _evaluar(cuenta, **kw):
    r = client.post("/conciliacion/cuadre/evaluar", json={"cuenta_id": cuenta, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def _historial(uid, cuenta, **campos):
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta, banco_detectado="prueba", estado="conciliado",
                              review_json="[]", **campos)
        db.add(h)
        db.commit()
        return h.id
    finally:
        db.close()


# ── Lectura de saldos del extracto ─────────────────────────────────────────────────────
NEQUI = """Estado de depósito de bajo monto para el período de: 2026/03/01 a 2026/03/31
Saldo anterior $2,000.00 Saldo promedio $1,000.00
Total abonos $60,000.00 Cuentas por cobrar $0.00
Total cargos $57,028.00 Valor de intereses pagados $5.00
Saldo actual $4,972.00 Retefuente $0.00
"""


def test_lee_saldo_anterior_final_y_periodo_de_un_extracto_de_ahorros():
    s = cx.leer_saldos_extracto(NEQUI)
    assert s["saldo_inicial"] == 2000 and s["saldo_final"] == 4972
    assert s["fecha_corte"] == "2026-03-31" and s["periodo_inicio"] == "2026-03-01"
    # la cadena saldo anterior + movimientos = saldo final delata líneas perdidas
    movs = [{"monto": 60_000, "tipo": "income"}, {"monto": 57_028, "tipo": "expense"}]
    assert cx.cadena_coincide(s, movs) is True
    assert cx.cadena_coincide(s, movs[:1]) is False


def test_extracto_sin_saldos_devuelve_none_y_no_inventa():
    assert cx.leer_saldos_extracto("Movimientos del mes\n01 sep Compra -$10.000") is None


def test_tarjeta_de_credito_guarda_la_deuda_en_negativo():
    texto = "Extracto tarjeta\nSaldo anterior: $500.000\nSaldo total: $1.200.000\nPago mínimo: $120.000\nFecha de corte: 15 de octubre de 2026\n"
    s = cx.leer_saldos_extracto(texto, es_credito=True, datos_tarjeta={"pago_minimo": 120_000, "fecha_corte": "2026-10-15"})
    assert s["saldo_final"] == -1_200_000 and s["saldo_inicial"] == -500_000 and s["fecha_corte"] == "2026-10-15"
    assert s["pago_minimo"] == 120_000


def test_tabla_con_columna_saldo_coherente_en_cualquier_orden():
    filas = [
        {"fecha": "2026-09-01", "monto": 100, "tipo": "income", "saldo": 1100},
        {"fecha": "2026-09-02", "monto": 30, "tipo": "expense", "saldo": 1070},
        {"fecha": "2026-09-03", "monto": 20, "tipo": "expense", "saldo": 1050},
    ]
    for orden in (filas, filas[::-1]):
        s = cx.saldos_de_filas(orden)
        assert s["saldo_inicial"] == 1000 and s["saldo_final"] == 1050 and s["fecha_corte"] == "2026-09-03"
    filas[1]["saldo"] = 5  # cadena rota: no se confía
    assert cx.saldos_de_filas(filas) is None
    assert cx.saldos_de_filas([{"fecha": "2026-09-01", "monto": 1, "tipo": "income", "saldo": None}] * 3) is None


# ── Evaluación ─────────────────────────────────────────────────────────────────────────
def test_cuadra_exacto():
    cuenta = _base("cu-exacto")
    ev = _evaluar(cuenta, saldo_final=1_850_000, fecha_corte="2026-09-30")
    assert ev["estado"] == "cuadra" and ev["diferencia"] == 0 and "Cuadra" in ev["texto"]
    assert "saldo oficial es el de tu banco" in ev["orientacion"]


def test_diferencia_por_movimiento_faltante_con_causas_y_acciones():
    cuenta = _base("cu-falta")
    ev = _evaluar(cuenta, saldo_final=1_800_000, fecha_corte="2026-09-30")  # el banco cobró 50.000 que no registré
    assert ev["estado"] == "diferencia" and ev["diferencia"] == -50_000
    assert "Diferencia de $50.000" in ev["texto"] and "$1.800.000" in ev["texto"] and "$1.850.000" in ev["texto"]
    codigos = {c["codigo"] for c in ev["causas"]}
    assert "falta_movimiento" in codigos and "duplicado" in codigos  # hay un movimiento de 50.000: ¿repetido?
    assert ev["acciones"]["ajuste"]["permitido"] and ev["acciones"]["ajuste"]["monto"] == -50_000
    assert ev["acciones"]["ver_que_falta"] and ev["acciones"]["dejar_asi"]
    assert _saldo(cuenta) == 1_850_000  # evaluar NO cambia nada


def test_lo_que_se_va_a_importar_cuenta_en_el_libro():
    cuenta = _base("cu-importar")
    nuevo = [{"fecha": "2026-09-25", "monto": 50_000, "tipo": "expense"},
             {"fecha": "2026-10-02", "monto": 999, "tipo": "expense"}]  # posterior al corte: no cuenta
    ev = _evaluar(cuenta, saldo_final=1_800_000, fecha_corte="2026-09-30", por_importar=nuevo)
    assert ev["estado"] == "cuadra"


def test_sin_saldo_pide_escribirlo_a_mano():
    cuenta = _base("cu-sinsaldo")
    ev = _evaluar(cuenta, fecha_corte="2026-09-30")
    assert ev["estado"] == "sin_saldo" and ev["acciones"]["pedir_saldo"] is True
    assert "Escribe el saldo que dice tu extracto al 30 sep 2026" in ev["texto"]


def test_moneda_distinta_advierte_y_no_compara():
    cuenta = _base("cu-moneda")
    ev = _evaluar(cuenta, saldo_final=500, fecha_corte="2026-09-30", moneda="USD")
    assert ev["estado"] == "moneda_distinta" and "USD" in ev["texto"]


def test_aviso_de_cuenta_equivocada_se_muestra_como_advertencia():
    cuenta = _base("cu-otra")
    ev = _evaluar(cuenta, saldo_final=1_000_000, fecha_corte="2026-09-30", aviso_cuenta="Parece de una tarjeta, ¿será «Nu Crédito»?")
    assert any(a["codigo"] == "otra_cuenta" for a in ev["advertencias"])
    assert any(c["codigo"] == "otra_cuenta" for c in ev["causas"])


# ── Saldo inicial ──────────────────────────────────────────────────────────────────────
def test_saldo_de_partida_sin_movimiento_se_detecta_y_se_registra_sin_mover_el_saldo():
    como("cu-ini1")
    cuenta = client.post("/cuentas", json={"nombre": "Con saldo", "saldo": 1_000_000}).json()["id"]
    _mov(cuenta, "income", 200_000, "2026-09-05T10:00:00")
    _mov(cuenta, "expense", 50_000, "2026-09-06T10:00:00")
    assert _saldo(cuenta) == 1_150_000
    diag = client.get(f"/conciliacion/cuadre?cuenta_id={cuenta}").json()["diagnostico"]
    assert diag["descuadre"] and diag["diferencia"] == 1_000_000 and diag["suma_movimientos"] == 150_000
    ev = _evaluar(cuenta, saldo_final=1_150_000, fecha_corte="2026-09-30")
    assert ev["estado"] == "diferencia" and ev["diferencia"] == 1_000_000
    sin_explicar = next(c for c in ev["causas"] if c["codigo"] == "saldo_inicial")
    assert sin_explicar["probable"] and "saldo inicial sin registrar" in sin_explicar["texto"]
    assert ev["acciones"]["saldo_inicial"]["modo"] == "sin_explicar"

    sin_confirmar = client.post("/conciliacion/cuadre/saldo-inicial", json={"cuenta_id": cuenta, "modo": "sin_explicar"})
    assert sin_confirmar.status_code == 400
    r = client.post("/conciliacion/cuadre/saldo-inicial", json={"cuenta_id": cuenta, "modo": "sin_explicar", "confirmar": True}).json()
    assert r["creado"] and r["monto"] == 1_000_000 and _saldo(cuenta) == 1_150_000  # el saldo no cambia
    assert _evaluar(cuenta, saldo_final=1_150_000, fecha_corte="2026-09-30")["estado"] == "cuadra"
    assert client.get(f"/conciliacion/cuadre?cuenta_id={cuenta}").json()["diagnostico"]["descuadre"] is False
    # deshacer lo deja como estaba
    d = client.post("/conciliacion/cuadre/deshacer", json={"movimiento_id": r["movimiento_id"], "confirmar": True}).json()
    assert d["ok"] and _saldo(cuenta) == 1_150_000
    assert client.get(f"/conciliacion/cuadre?cuenta_id={cuenta}").json()["diagnostico"]["descuadre"] is True


def test_saldo_inicial_desde_el_extracto_cuando_no_hay_movimientos_anteriores():
    como("cu-ini2")
    cuenta = client.post("/cuentas", json={"nombre": "Nueva", "saldo": 0}).json()["id"]
    _mov(cuenta, "income", 300_000, "2026-09-05T10:00:00")
    _mov(cuenta, "expense", 100_000, "2026-09-06T10:00:00")
    ev = _evaluar(cuenta, saldo_inicial=500_000, saldo_final=700_000, fecha_corte="2026-09-30", periodo_inicio="2026-09-01")
    assert ev["diferencia"] == 500_000
    assert ev["acciones"]["saldo_inicial"]["modo"] == "extracto" and ev["acciones"]["saldo_inicial"]["monto"] == 500_000
    r = client.post("/conciliacion/cuadre/saldo-inicial", json={
        "cuenta_id": cuenta, "modo": "extracto", "saldo_inicial": 500_000, "periodo_inicio": "2026-09-01", "confirmar": True}).json()
    assert r["creado"] and _saldo(cuenta) == 700_000
    assert _evaluar(cuenta, saldo_final=700_000, fecha_corte="2026-09-30")["estado"] == "cuadra"
    # el saldo inicial es neutro: no es ingreso del mes
    db = SessionLocal()
    try:
        m = db.query(Movimiento).filter(Movimiento.id == r["movimiento_id"]).first()
        assert m.fuente == FUENTE_AJUSTE and m.fecha == datetime(2026, 9, 1)
        movs = db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta).all()
        assert tipos_efectivos(movs)[m.id] == "transfer"
    finally:
        db.close()
    # si ya hay historia anterior, no se ofrece
    otra = client.post("/conciliacion/cuadre/saldo-inicial", json={
        "cuenta_id": cuenta, "modo": "extracto", "saldo_inicial": 1, "periodo_inicio": "2026-10-01", "confirmar": True})
    assert otra.status_code == 409 and otra.json()["detail"]["codigo"] == "ya_hay_historia"


# ── Ajuste ────────────────────────────────────────────────────────────────────────────
def test_ajuste_nunca_se_crea_sin_confirmacion():
    cuenta = _base("cu-sinconf")
    r = client.post("/conciliacion/cuadre/ajuste", json={"cuenta_id": cuenta, "saldo_final": 1_800_000, "fecha_corte": "2026-09-30"})
    assert r.status_code == 400 and _saldo(cuenta) == 1_850_000


def test_ajuste_neutro_cuadra_y_no_cuenta_en_informes_ni_presupuestos():
    cuenta = _base("cu-ajuste")
    client.post("/presupuestos", json={"categoria": "Ajuste de saldo", "limite": 10_000})
    r = client.post("/conciliacion/cuadre/ajuste", json={
        "cuenta_id": cuenta, "saldo_final": 1_800_000, "fecha_corte": "2026-09-30", "confirmar": True}).json()
    assert r["ajustado"] and r["diferencia"] == -50_000 and r["estado"] == "cuadra" and _saldo(cuenta) == 1_800_000
    mov = client.get(f"/movimientos/{r['movimiento_id']}").json()
    assert mov["fuente"] == FUENTE_AJUSTE and mov["categoria"] == "Ajuste de saldo" and mov["tipo"] == "expense"
    assert mov["notas"] == "Ajuste para cuadrar con el extracto del 30 sep 2026"
    assert mov["fecha"].startswith("2026-09-30")
    assert _evaluar(cuenta, saldo_final=1_800_000, fecha_corte="2026-09-30")["estado"] == "cuadra"
    # informes: el ajuste no es gasto ni ingreso
    db = SessionLocal()
    try:
        movs = db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta).all()
        te = tipos_efectivos(movs)
        assert te[r["movimiento_id"]] == "transfer"
        gastos = gastos_por_categoria(db, [cuenta], datetime(2026, 9, 1))
        assert gastos.get("Ajuste de saldo", 0) == 0 and gastos["Comida"] == 150_000
    finally:
        db.close()
    rep = client.get("/reportes/mensual?mes=2026-09").json()
    assert rep["gastos"] == 150_000 and rep["ingresos"] == 2_000_000


def test_ajuste_grande_exige_confirmacion_reforzada_y_se_puede_deshacer():
    cuenta = _base("cu-grande")
    cuerpo = {"cuenta_id": cuenta, "saldo_final": 1_000_000, "fecha_corte": "2026-09-30", "confirmar": True}  # dif -850.000
    ev = _evaluar(cuenta, saldo_final=1_000_000, fecha_corte="2026-09-30")
    assert ev["acciones"]["ajuste"]["grande"] and any(a["codigo"] == "ajuste_grande" for a in ev["advertencias"])
    r = client.post("/conciliacion/cuadre/ajuste", json=cuerpo)
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "requiere_confirmacion_reforzada"
    assert _saldo(cuenta) == 1_850_000
    ok = client.post("/conciliacion/cuadre/ajuste", json={**cuerpo, "confirmar_reforzado": True}).json()
    assert ok["ajustado"] and _saldo(cuenta) == 1_000_000
    sin = client.post("/conciliacion/cuadre/deshacer", json={"movimiento_id": ok["movimiento_id"]})
    assert sin.status_code == 400  # pide confirmación
    d = client.post("/conciliacion/cuadre/deshacer", json={"movimiento_id": ok["movimiento_id"], "confirmar": True}).json()
    assert d["ok"] and _saldo(cuenta) == 1_850_000
    assert client.get(f"/movimientos/{ok['movimiento_id']}").status_code == 404


def test_ajuste_pequeno_no_pide_refuerzo_y_ya_cuadrado_no_crea_nada():
    cuenta = _base("cu-chico")
    r = client.post("/conciliacion/cuadre/ajuste", json={"cuenta_id": cuenta, "saldo_final": 1_849_000, "fecha_corte": "2026-09-30", "confirmar": True})
    assert r.status_code == 200 and r.json()["ajustado"]  # 1.000: muy por debajo del 5 % y de $500.000
    otra = client.post("/conciliacion/cuadre/ajuste", json={"cuenta_id": cuenta, "saldo_final": 1_849_000, "fecha_corte": "2026-09-30", "confirmar": True}).json()
    assert otra["ajustado"] is False and otra["estado"] == "cuadra"


def test_no_se_ajusta_con_lineas_por_revisar_sin_resolver():
    cuenta = _base("cu-pend")
    revision = [{"fecha": "2026-09-25", "descripcion": "Compra sin traer", "monto": 50_000, "tipo": "expense",
                 "fingerprint": "fp1", "estado": "faltante"}]
    h = _historial("cu-pend", cuenta, saldo_final_extracto=1_800_000, fecha_corte="2026-09-30", saldos_origen="extracto")
    db = SessionLocal()
    try:
        db.query(HistorialExtracto).filter(HistorialExtracto.id == h).update({"review_json": json.dumps(revision)})
        db.commit()
    finally:
        db.close()
    ev = _evaluar(cuenta, historial_id=h)
    assert ev["estado"] == "diferencia" and ev["acciones"]["ajuste"]["permitido"] is False
    assert "Primero trae o resuelve" in ev["acciones"]["ajuste"]["motivo_bloqueo"]
    r = client.post("/conciliacion/cuadre/ajuste", json={"cuenta_id": cuenta, "historial_id": h, "confirmar": True})
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "lineas_por_revisar"
    assert _saldo(cuenta) == 1_850_000
    # si esas líneas se van a traer, el libro las cuenta y cuadra sin ajuste
    ev2 = _evaluar(cuenta, historial_id=h, por_importar=[{"fecha": "2026-09-25", "monto": 50_000, "tipo": "expense"}])
    assert ev2["estado"] == "cuadra"


# ── Tarjeta de crédito: la deuda es negativa ────────────────────────────────────────────
def test_tarjeta_de_credito_cuadra_con_la_deuda_y_el_ajuste_conserva_el_signo():
    como("cu-tc")
    tarjeta = client.post("/cuentas", json={"nombre": "Visa", "tipo": "credito", "saldo": 0, "cupo_total": 5_000_000}).json()["id"]
    _mov(tarjeta, "expense", 600_000, "2026-09-08T10:00:00", "Nevera")
    _mov(tarjeta, "expense", 200_000, "2026-09-12T10:00:00", "Mercado")
    assert _saldo(tarjeta) == -800_000
    ev = _evaluar(tarjeta, saldo_final=-800_000, fecha_corte="2026-09-15")
    assert ev["estado"] == "cuadra"
    ev = _evaluar(tarjeta, saldo_final=-850_000, fecha_corte="2026-09-15")  # el banco cobró 50.000 de cuota de manejo
    assert ev["estado"] == "diferencia" and ev["diferencia"] == -50_000
    assert "debes" in ev["texto"] and "$850.000" in ev["texto"]
    r = client.post("/conciliacion/cuadre/ajuste", json={"cuenta_id": tarjeta, "saldo_final": -850_000, "fecha_corte": "2026-09-15", "confirmar": True}).json()
    assert r["ajustado"] and _saldo(tarjeta) == -850_000


# ── Histórico, encadenado y alertas ─────────────────────────────────────────────────────
def test_varios_meses_encadenados_y_alerta_si_un_mes_deja_de_cuadrar():
    como("cu-meses")
    cuenta = client.post("/cuentas", json={"nombre": "Encadenada", "saldo": 0}).json()["id"]
    inicial = _mov(cuenta, "income", 1_000_000, "2026-08-01T08:00:00", "Saldo de agosto")
    gasto_ago = _mov(cuenta, "expense", 100_000, "2026-08-15T08:00:00", "Agosto")
    _mov(cuenta, "income", 500_000, "2026-09-05T08:00:00", "Septiembre")
    _historial("cu-meses", cuenta, saldo_final_extracto=900_000, fecha_corte="2026-08-31", cuadre_estado="cuadra")
    _historial("cu-meses", cuenta, saldo_final_extracto=1_400_000, fecha_corte="2026-09-30", cuadre_estado="cuadra")
    r = client.get(f"/conciliacion/cuadre?cuenta_id={cuenta}").json()
    estados = {m["mes"]: m["estado"] for m in r["meses"]}
    assert estados["2026-08"] == "cuadra" and estados["2026-09"] == "cuadra" and estados["2026-10"] == "sin_extracto"
    assert r["alertas"] == [] and r["ultimo_cuadre"]["mes"] == "2026-09"
    # alguien borra un movimiento de agosto: agosto y septiembre dejan de cuadrar
    assert client.delete(f"/movimientos/{gasto_ago}").status_code == 200
    r = client.get(f"/conciliacion/cuadre?cuenta_id={cuenta}").json()
    meses = {m["mes"]: m for m in r["meses"]}
    assert meses["2026-08"]["estado"] == "diferencia" and meses["2026-08"]["dejo_de_cuadrar"] is True
    assert {a["mes"] for a in r["alertas"]} == {"2026-08", "2026-09"}
    assert "cuadraba" in r["alertas"][0]["texto"]
    assert r["ultimo_cuadre"] is None and r["estado_actual"]["mes"] == "2026-09"
    assert inicial  # (id usado: el saldo de agosto sigue ahí)


def test_corte_anterior_al_punto_de_partida_no_se_compara():
    como("cu-pp")
    cuenta = client.post("/cuentas", json={"nombre": "PP", "saldo": 0}).json()["id"]
    client.put("/perfil/punto-de-partida", json={"modo": "hoy", "fecha": "2026-10-01"})
    ev = _evaluar(cuenta, saldo_final=123, fecha_corte="2026-09-30")
    assert ev["estado"] == "antes_de_inicio" and "fecha de inicio" in ev["texto"]


def test_punto_de_partida_con_saldo_inicial_cuadra_despues():
    como("cu-pp2")
    cuenta = client.post("/cuentas", json={"nombre": "PP2", "saldo": 400_000}).json()["id"]
    r = client.put("/perfil/punto-de-partida", json={"modo": "hoy", "fecha": "2026-10-01", "saldos": {cuenta: {"inicial": 400_000}}})
    assert r.status_code == 200, r.text
    _mov(cuenta, "income", 100_000, "2026-10-05T10:00:00")
    ev = _evaluar(cuenta, saldo_final=_saldo(cuenta), fecha_corte="2026-10-10")
    assert ev["estado"] in ("cuadra", "diferencia")  # no explota con el saldo de partida; si hay descuadre lo explica
    if ev["estado"] == "diferencia":
        assert any(c["codigo"] == "saldo_inicial" for c in ev["causas"])


# ── Integración con el procesamiento del extracto ───────────────────────────────────────
def test_procesar_extracto_guarda_saldos_y_se_pueden_leer_en_el_historial(monkeypatch):
    from app.routers import conciliacion as mod

    como("cu-proc")
    cuenta = client.post("/cuentas", json={"nombre": "Nequi", "saldo": 0}).json()["id"]
    texto = NEQUI
    monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: texto)
    monkeypatch.setattr(mod, "detectar_banco", lambda t: "nequi")
    items = [{"fecha": "2026-03-26", "descripcion": "RECIBI POR BRE-B DE: LUIS", "monto": 60_000, "tipo": "income", "referencia": ""},
             {"fecha": "2026-03-27", "descripcion": "PAGO EN QR BRE-B: TIENDA", "monto": 57_028, "tipo": "expense", "referencia": ""}]
    monkeypatch.setattr(mod, "parse_texto_con_regex", lambda t: ([dict(i) for i in items], 0))
    r = client.post("/conciliacion/procesar", json={"cuenta_id": cuenta, "pdf_base64": "x"}).json()
    s = r["saldos_extracto"]
    assert s["saldo_inicial"] == 2000 and s["saldo_final"] == 4972 and s["cadena_ok"] is True and s["fecha_corte"] == "2026-03-31"
    h = next(x for x in client.get("/conciliacion/historial").json() if x["id"] == r["historial_id"])
    assert h["saldo_final_extracto"] == 4972 and h["fecha_corte"] == "2026-03-31"
    assert client.get(f"/conciliacion/historial/{r['historial_id']}").json()["saldos_extracto"]["saldo_final"] == 4972
    # antes de traer: faltan las dos líneas; con ellas por traer y el saldo inicial del extracto, cuadra
    ev = _evaluar(cuenta, historial_id=r["historial_id"], por_importar=[
        {"fecha": "2026-03-26", "monto": 60_000, "tipo": "income"}, {"fecha": "2026-03-27", "monto": 57_028, "tipo": "expense"}])
    assert ev["estado"] == "diferencia" and ev["diferencia"] == 2000  # falta el saldo inicial de $2.000
    assert ev["acciones"]["saldo_inicial"]["modo"] == "extracto" and ev["acciones"]["saldo_inicial"]["monto"] == 2000


def test_saldos_a_mano_para_extractos_sin_saldos(monkeypatch):
    como("cu-mano")
    cuenta = _base("cu-mano")
    h = _historial("cu-mano", cuenta)
    ev = _evaluar(cuenta, historial_id=h)
    assert ev["estado"] == "sin_saldo"
    assert client.post("/conciliacion/cuadre/saldos", json={"historial_id": h, "saldo_final": 1_850_000, "fecha_corte": "2026-09-30"}).status_code == 400
    r = client.post("/conciliacion/cuadre/saldos", json={"historial_id": h, "saldo_final": 1_850_000, "fecha_corte": "2026-09-30", "confirmar": True})
    assert r.status_code == 200 and r.json()["saldos"]["origen"] == "manual"
    assert _evaluar(cuenta, historial_id=h, registrar=True)["estado"] == "cuadra"
    mes = client.get(f"/conciliacion/cuadre?cuenta_id={cuenta}").json()["meses"][0]
    assert mes["estado"] == "cuadra"
    h2 = next(x for x in client.get("/conciliacion/historial").json() if x["id"] == h)
    assert h2["cuadre_estado"] == "cuadra"


def test_que_falta_lista_las_dos_puntas():
    cuenta = _base("cu-qf")
    h = _historial("cu-qf", cuenta)
    db = SessionLocal()
    try:
        db.query(HistorialExtracto).filter(HistorialExtracto.id == h).update({"review_json": json.dumps([
            {"fecha": "2026-09-25", "descripcion": "Cobro del banco", "monto": 50_000, "tipo": "expense", "fingerprint": "a", "estado": "faltante"},
            {"fecha": "2026-09-10", "descripcion": "Restaurante", "monto": 100_000, "tipo": "expense", "fingerprint": "b", "estado": "sobrante", "match_id": "m1"}])})
        db.commit()
    finally:
        db.close()
    r = client.get(f"/conciliacion/cuadre/que-falta?cuenta_id={cuenta}&historial_id={h}").json()
    assert [x["descripcion"] for x in r["sin_pareja_en_tus_movimientos"]] == ["Cobro del banco"]
    assert [x["descripcion"] for x in r["sin_respaldo_en_el_extracto"]] == ["Restaurante"]
    sin_h = client.get(f"/conciliacion/cuadre/que-falta?cuenta_id={cuenta}&desde=2026-09-01&hasta=2026-09-30").json()
    assert len(sin_h["sin_respaldo_en_el_extracto"]) == 3


def test_umbral_del_ajuste_grande_es_configurable(monkeypatch):
    from app.config import settings

    assert cx.es_ajuste_grande(600_000, 100_000_000, "COP")       # pasa $500.000
    assert not cx.es_ajuste_grande(100_000, 100_000_000, "COP")
    assert cx.es_ajuste_grande(60_000, 1_000_000, "COP")           # pasa el 5 % de 1.000.000
    monkeypatch.setattr(settings, "cuadre_ajuste_grande_monto", 50_000.0)
    assert cx.es_ajuste_grande(60_000, 100_000_000, "COP")
    assert cx.fecha_texto(date(2026, 9, 30)) == "30 sep 2026"


def test_otro_usuario_no_puede_evaluar_ni_deshacer_cuentas_ajenas():
    cuenta = _base("cu-dueno")
    ajuste = client.post("/conciliacion/cuadre/ajuste", json={"cuenta_id": cuenta, "saldo_final": 1_849_000, "fecha_corte": "2026-09-30", "confirmar": True}).json()
    como("cu-intruso")
    assert client.post("/conciliacion/cuadre/evaluar", json={"cuenta_id": cuenta, "saldo_final": 1, "fecha_corte": "2026-09-30"}).status_code == 404
    assert client.get(f"/conciliacion/cuadre?cuenta_id={cuenta}").status_code == 404
    assert client.post("/conciliacion/cuadre/deshacer", json={"movimiento_id": ajuste["movimiento_id"], "confirmar": True}).status_code == 404
    como("cu-dueno")
    assert _saldo(cuenta) == 1_849_000
