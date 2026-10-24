"""Regla contable: el pago de una tarjeta de crédito y los traslados entre cuentas propias
NO son gasto ni ingreso (las compras con la tarjeta ya se contaron). Pruebas de regresión
de los dobles conteos en resumen, presupuestos, insights, reportes, salud, wrapped y exportar.

Escenario base (números hechos a mano):
  Cuenta Banco (ahorro):   sueldo +2.000.000, "Pago tarjeta Visa" -150.000
  Tarjeta Visa (credito):  compras Comida 100.000 y Transporte 50.000, abono +150.000
  => ingresos reales 2.000.000 | gastos reales 150.000 (NO 300.000) | ahorro 1.850.000
"""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'conta.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.contabilidad import (  # noqa: E402
    es_pago_tarjeta,
    tipo_efectivo_receta,
    tipos_efectivos,
)
from app.main import app  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="conta-0", email="c@test.com", nombre="Conta")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def como(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


# ── Lógica pura ──────────────────────────────────────

def _m(id, tipo, monto, desc="x", cuenta="A", cat="Otros", fecha=None, fuente="manual"):
    return {"id": id, "tipo": tipo, "monto": monto, "descripcion": desc, "cuenta_id": cuenta,
            "categoria": cat, "fecha": fecha or datetime(2026, 10, 5), "fuente": fuente}


@pytest.mark.parametrize("texto,esperado", [
    ("Pago tarjeta Visa", True),
    ("PAGO DE TARJETA DE CREDITO DAVIVIENDA", True),
    ("Abono a tarjeta crédito", True),
    ("PAGO TC MASTERCARD", True),
    ("Pago tarj credito", True),
    ("Pago visa", True),
    ("Pago con tarjeta en Éxito", False),     # es una COMPRA con tarjeta
    ("Compra tarjeta débito Rappi", False),
    ("Pago arriendo", False),
    ("Tarjeta de regalo", False),
])
def test_deteccion_pago_de_tarjeta(texto, esperado):
    assert es_pago_tarjeta(texto) is esperado


def test_pago_de_tarjeta_y_su_abono_no_son_gasto_ni_ingreso():
    tipos = {"A": "ahorro", "T": "credito"}
    movs = [
        _m("sueldo", "income", 2_000_000, "Nómina", "A"),
        _m("c1", "expense", 100_000, "Restaurante", "T", "Comida"),
        _m("c2", "expense", 50_000, "Uber", "T", "Transporte"),
        _m("pago", "expense", 150_000, "Pago tarjeta Visa", "A"),
        _m("abono", "income", 150_000, "Pago recibido", "T"),
    ]
    te = tipos_efectivos(movs, tipos)
    assert te == {"sueldo": "income", "c1": "expense", "c2": "expense", "pago": "transfer", "abono": "transfer"}
    assert sum(m["monto"] for m in movs if te[m["id"]] == "expense") == 150_000   # no 300.000
    assert sum(m["monto"] for m in movs if te[m["id"]] == "income") == 2_000_000  # no 2.150.000


def test_transferencia_propia_registrada_como_gasto_e_ingreso_se_empareja():
    tipos = {"A": "ahorro", "N": "ahorro"}
    movs = [
        _m("sale", "expense", 300_000, "Envío a Nequi", "A", fecha=datetime(2026, 10, 5, 10)),
        _m("entra", "income", 300_000, "Recibiste de Bancolombia", "N", fecha=datetime(2026, 10, 6, 9)),
        # mismo monto pero SIN pistas de traslado: son un gasto y un ingreso reales
        _m("arriendo", "expense", 800_000, "Arriendo", "A"),
        _m("venta", "income", 800_000, "Venta de bicicleta", "N"),
    ]
    te = tipos_efectivos(movs, tipos)
    assert te["sale"] == te["entra"] == "transfer"
    assert te["arriendo"] == "expense" and te["venta"] == "income"


def test_emparejar_no_cruza_mas_de_dos_dias_ni_misma_cuenta():
    tipos = {"A": "ahorro", "N": "ahorro"}
    lejos = [_m("s", "expense", 100_000, "Transferencia", "A", fecha=datetime(2026, 10, 1)),
             _m("e", "income", 100_000, "Transferencia", "N", fecha=datetime(2026, 10, 5))]
    assert set(tipos_efectivos(lejos, tipos).values()) == {"expense", "income"}
    misma = [_m("s", "expense", 100_000, "Transferencia", "A"), _m("e", "income", 100_000, "Transferencia", "A")]
    assert set(tipos_efectivos(misma, tipos).values()) == {"expense", "income"}


def test_cada_ingreso_se_usa_una_sola_vez_al_emparejar():
    tipos = {"A": "ahorro", "N": "ahorro"}
    movs = [_m("s1", "expense", 50_000, "Envío Nequi", "A"), _m("s2", "expense", 50_000, "Envío Nequi", "A"),
            _m("e1", "income", 50_000, "Recibiste", "N")]
    te = tipos_efectivos(movs, tipos)
    assert sorted(te.values()) == ["expense", "transfer", "transfer"]  # solo una pareja; el otro envío sigue siendo gasto


def test_categoria_y_fuente_de_traslado_son_neutras():
    movs = [_m("a", "expense", 10, "algo", cat="Pago de tarjeta"), _m("b", "expense", 10, "algo", cat="Transferencia"),
            _m("c", "transfer", 10), _m("d", "expense", 10, "algo", fuente="transferencia_interna")]
    assert set(tipos_efectivos(movs, {}).values()) == {"transfer"}


def test_recurrente_de_pago_de_tarjeta_no_es_gasto():
    assert tipo_efectivo_receta("expense", "Otros", "Pago tarjeta Visa") == "transfer"
    assert tipo_efectivo_receta("expense", "Servicios", "Netflix") == "expense"


# ── Regresión de punta a punta (API) ───────────────────

def _escenario(uid):
    como(uid)
    banco = client.post("/cuentas", json={"nombre": "Banco", "tipo": "ahorro", "saldo": 0}).json()["id"]
    visa = client.post("/cuentas", json={"nombre": "Visa", "tipo": "credito", "saldo": 0, "cupo_total": 5_000_000}).json()["id"]

    def mov(cuenta, tipo, monto, desc, cat=None):
        body = {"cuenta_id": cuenta, "tipo": tipo, "monto": monto, "descripcion": desc}
        if cat:
            body["categoria"] = cat
        r = client.post("/movimientos", json=body)
        assert r.status_code == 200, r.text
        return r.json()

    mov(banco, "income", 2_000_000, "Nómina octubre", "Ingresos")
    mov(visa, "expense", 100_000, "Restaurante Andrés", "Comida")
    mov(visa, "expense", 50_000, "Uber viaje", "Transporte")
    pago = mov(banco, "expense", 150_000, "Pago tarjeta Visa", "Deudas")   # el usuario eligió "Deudas"
    mov(visa, "income", 150_000, "Abono pago recibido")
    return banco, visa, pago


def test_reporte_mensual_no_cuenta_el_pago_de_tarjeta():
    _escenario("conta-rep")
    r = client.get("/reportes/mensual").json()
    assert r["ingresos"] == 2_000_000
    assert r["gastos"] == 150_000
    assert r["ahorro"] == 1_850_000
    assert {c["categoria"] for c in r["top_categorias"]} == {"Comida", "Transporte"}


def test_saldos_siguen_siendo_correctos():
    banco, visa, _ = _escenario("conta-saldos")
    cuentas = {c["id"]: c["saldo"] for c in client.get("/cuentas").json()}
    assert cuentas[banco] == 2_000_000 - 150_000
    assert cuentas[visa] == -100_000 - 50_000 + 150_000  # tarjeta pagada = 0


def test_presupuesto_no_cuenta_el_pago_de_tarjeta_aunque_se_categorice_como_deudas():
    _escenario("conta-pres")
    client.post("/presupuestos", json={"categoria": "Deudas", "limite": 1_000_000})
    client.post("/presupuestos", json={"categoria": "Comida", "limite": 500_000})
    r = client.get("/presupuestos/disponible-hoy").json()
    por_cat = {c["categoria"]: c["gastado"] for c in r["categorias"]}
    assert por_cat["Deudas"] == 0           # antes: 150.000
    assert por_cat["Comida"] == 100_000


def test_tendencias_wrapped_y_resumen_semanal():
    _escenario("conta-tend")
    mes = ahora_co().strftime("%Y-%m")
    t = client.get("/reportes/tendencias?meses=1").json()
    assert t["meses"][-1]["gastos"] == 150_000 and t["meses"][-1]["ingresos"] == 2_000_000
    w = client.get(f"/reportes/wrapped?mes={mes}").json()
    assert w["gasto_total"] == 150_000 and w["ingresos"] == 2_000_000
    assert w["categoria_top"]["categoria"] == "Comida"
    s = client.get("/insights/resumen-semanal").json()
    assert s["gastos"] == 150_000 and s["ingresos"] == 2_000_000


def test_salud_financiera_usa_gastos_reales():
    _escenario("conta-salud")
    r = client.get("/insights/salud-financiera")
    assert r.status_code == 200
    j = r.json()
    texto = str(j)
    # tasa de ahorro = (2.000.000 - 150.000) / 2.000.000 = 92,5 %
    assert "92.5" in texto or "0.925" in texto or "92,5" in texto


def test_exportar_marca_el_pago_de_tarjeta_como_no_cuenta():
    _escenario("conta-exp")
    csv = client.get("/exportar/movimientos.csv").text
    assert "Cuenta en resúmenes como" in csv
    linea_pago = [l for l in csv.splitlines() if "Pago tarjeta Visa" in l][0]
    assert "No cuenta" in linea_pago
    linea_compra = [l for l in csv.splitlines() if "Restaurante Andrés" in l][0]
    assert ",Gasto," in linea_compra  # la última columna ahora es «Texto del banco»


def test_clasificar_sugiere_pago_de_tarjeta():
    como("conta-clas")
    r = client.post("/movimientos/clasificar", json={"descripcion": "PAGO TARJETA CREDITO"}).json()
    assert r["categoria"] == "Pago de tarjeta"
    assert client.post("/movimientos/clasificar", json={"descripcion": "Pago con tarjeta Éxito"}).json()["categoria"] != "Pago de tarjeta"


def test_pagar_deuda_de_tarjeta_no_crea_un_gasto():
    como("conta-deuda")
    banco = client.post("/cuentas", json={"nombre": "Banco", "saldo": 1_000_000}).json()["id"]
    deuda = client.post("/deudas", json={"nombre": "Visa vieja", "tipo": "tarjeta", "saldo_inicial": 400_000,
                                         "cuenta_pago_id": banco}).json()["id"]
    client.post(f"/deudas/{deuda}/pagar", json={"monto_pagado": 400_000, "crear_movimiento": True})
    assert client.get("/reportes/mensual").json()["gastos"] == 0
    # pero el dinero sí salió de la cuenta
    assert [c for c in client.get("/cuentas").json() if c["id"] == banco][0]["saldo"] == 600_000


def test_deuda_de_prestamo_si_sigue_contando_como_gasto():
    como("conta-prestamo")
    banco = client.post("/cuentas", json={"nombre": "Banco", "saldo": 1_000_000}).json()["id"]
    deuda = client.post("/deudas", json={"nombre": "Moto", "tipo": "credito", "saldo_inicial": 400_000,
                                         "cuenta_pago_id": banco}).json()["id"]
    client.post(f"/deudas/{deuda}/pagar", json={"monto_pagado": 100_000, "crear_movimiento": True})
    assert client.get("/reportes/mensual").json()["gastos"] == 100_000


def test_recurrente_de_pago_de_tarjeta_no_entra_en_el_flujo_de_caja():
    como("conta-flujo")
    banco = client.post("/cuentas", json={"nombre": "Banco", "saldo": 1_000_000}).json()["id"]
    client.post("/recurrentes", json={"nombre": "Pago tarjeta Visa", "monto": 200_000, "tipo": "expense", "cuenta_id": banco})
    client.post("/recurrentes", json={"nombre": "Netflix", "monto": 30_000, "tipo": "expense", "cuenta_id": banco})
    f = client.get("/reportes/flujo-caja-futuro?meses=1").json()
    assert f["meses"][0]["gastos_esperados"] == 30_000


def test_ingreso_en_tarjeta_marcado_como_real_si_cuenta():
    """Un reembolso (o un ingreso anotado a mano en la tarjeta) que la persona marca «es un ingreso real» suma;
    sin esa marca se sigue leyendo como abono de pago de la tarjeta."""
    tipos = {"T": "credito"}
    sin_marca = _m("r1", "income", 80_000, "Reembolso", "T")
    con_marca = {**_m("r2", "income", 90_000, "Sk", "T"), "notas": "no_es_traslado"}
    te = tipos_efectivos([sin_marca, con_marca], tipos)
    assert te["r1"] == "transfer"
    assert te["r2"] == "income"
