"""Regla de producto: TODO movimiento importado tiene dirección y mueve el saldo de su cuenta.
Un traslado a/de uno mismo sale 'income'/'expense' con la pista 'posible_traslado_propio';
nunca 'transfer' sin dirección. Números hechos a mano."""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'trasdir.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.conciliacion import fijar_nombre_titular, parse_texto_con_regex  # noqa: E402
from app.contabilidad import MARCA_TRASLADO_PROPIO, delta_saldo, direccion_por_descripcion, tipo_con_direccion  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import HistorialExtracto  # noqa: E402

client = TestClient(app)

NU = """Nu Placa Número de Cuenta Período
ABC123 11112222 01 - 31 OCT 2025
Movimientos
02 oct Recibiste de Ana Maria Lopez Rojas +$500.000,00
03 oct Enviaste a Ana Maria Lopez Rojas -$300.000,00
04 oct Enviaste a Pepito Perez -$15.000,00
"""

NEQUI = """Extracto de depósito de bajo monto de:
ANA MARIA LOPEZ ROJAS
Estado de depósito de bajo monto para el período de: 2026/03/01 a 2026/03/31
Fecha del movimiento Descripción Valor Saldo
28/03/2026 Para ANA MARIA LOPEZ ROJAS $-7,000.00 $4,972.00
27/03/2026 Transfer RECIBI POR BRE-B DE: ANA $60,000.00 $62,000.00
"""


def test_nu_transferencias_salen_con_direccion_y_pista_nunca_transfer():
    fijar_nombre_titular("Ana Maria Lopez Rojas")
    movs, _ = parse_texto_con_regex(NU)
    por = {m["descripcion"]: m for m in movs}
    assert {m["tipo"] for m in movs} <= {"income", "expense"}
    rec = por["Recibiste de Ana Maria Lopez Rojas"]
    env = por["Enviaste a Ana Maria Lopez Rojas"]
    ter = por["Enviaste a Pepito Perez"]
    assert (rec["tipo"], rec["monto"], rec.get("pista")) == ("income", 500000, MARCA_TRASLADO_PROPIO)
    assert (env["tipo"], env["monto"], env.get("pista")) == ("expense", 300000, MARCA_TRASLADO_PROPIO)
    assert (ter["tipo"], ter.get("pista")) == ("expense", None)  # a un tercero: gasto real, sin pista
    # saldo neto = +500.000 - 300.000 - 15.000 = 185.000
    assert sum(delta_saldo(m) for m in movs) == 185000


def test_nequi_transfer_firmado_por_el_valor():
    fijar_nombre_titular("Ana Maria Lopez Rojas")
    movs, _ = parse_texto_con_regex(NEQUI)
    assert [(m["tipo"], m["monto"]) for m in movs] == [("expense", 7000), ("income", 60000)]
    assert all(m.get("pista") == MARCA_TRASLADO_PROPIO for m in movs)


def test_bancolombia_debito_sale_credito_entra():
    from app.conciliacion import _parse_bancolombia
    texto = ("01/10/2025  TRANSFERENCIA A CUENTA NEQUI   500.000   0   1.000.000\n"
             "02/10/2025  TRANSFERENCIA DE TERCERO   0   200.000   1.200.000\n")
    movs = _parse_bancolombia(texto)
    assert [(m["tipo"], m["monto"]) for m in movs] == [("expense", 500000), ("income", 200000)]


def test_direccion_por_descripcion_solo_si_es_inequivoca():
    assert direccion_por_descripcion("Para JUAN PEREZ") == "expense"
    assert direccion_por_descripcion("Enviaste a Ana") == "expense"
    assert direccion_por_descripcion("De Luis Gomez") == "income"
    assert direccion_por_descripcion("Recibiste de Luis") == "income"
    assert direccion_por_descripcion("Transfer") is None
    assert direccion_por_descripcion("COMPRA EXITO") is None
    assert tipo_con_direccion("income", "x") == "income"
    assert tipo_con_direccion("transfer", "Para Juan") == "expense"
    assert tipo_con_direccion("transfer", "Transfer") is None


def test_delta_saldo_regla_unica():
    assert delta_saldo({"tipo": "income", "monto": 100}) == 100
    assert delta_saldo({"tipo": "expense", "monto": 100}) == -100
    assert delta_saldo({"tipo": "transfer", "fuente": "transferencia_interna", "notas": "TRF:g:out", "monto": 100}) == -100
    assert delta_saldo({"tipo": "transfer", "fuente": "transferencia_interna", "notas": "TRF:g:in", "monto": 100}) == 100
    assert delta_saldo({"tipo": "transfer", "monto": 100}) == 0  # heredado sin dirección
    assert delta_saldo({"tipo": "expense", "fuente": "importado_sin_saldo", "monto": 100}) == 0


# ── API ───────────────────────────────────────────────

@pytest.fixture()
def usuario(request):
    uid = f"user-trd-{request.node.name}"[:60]
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email="t@test.com", nombre="T")
    yield uid


def test_confirmar_traslado_propio_mueve_saldo_y_deja_la_marca(usuario):
    fijar_nombre_titular("Ana Maria Lopez Rojas")
    cuenta = client.post("/cuentas", json={"nombre": "Nequi", "saldo": 0}).json()["id"]
    filas = [
        {"fecha": "2025-10-02", "descripcion": "Recibiste de Ana Maria Lopez Rojas", "monto": 500000, "tipo": "income"},
        {"fecha": "2025-10-03", "descripcion": "Enviaste a Ana Maria Lopez Rojas", "monto": 300000, "tipo": "expense"},
        {"fecha": "2025-10-04", "descripcion": "Enviaste a Pepito Perez", "monto": 15000, "tipo": "expense"},
    ]
    j = client.post("/importar/confirmar", json={"cuenta_id": cuenta, "nombre_archivo": "n.csv", "filas": filas}).json()
    assert j["importados"] == 3 and j["saldo"] == 185000
    movs = {m["descripcion"]: m for m in client.get("/movimientos").json()}
    assert MARCA_TRASLADO_PROPIO in movs["Recibiste de Ana Maria Lopez Rojas"]["notas"]
    assert MARCA_TRASLADO_PROPIO not in (movs["Enviaste a Pepito Perez"]["notas"] or "")


def test_importar_faltantes_resuelve_transfer_heredado_y_omite_el_ambiguo(usuario):
    cuenta = client.post("/cuentas", json={"nombre": "Nequi", "saldo": 100000}).json()["id"]
    review = [
        {"fecha": "2025-10-03", "descripcion": "Para JUAN PEREZ", "monto": 20000, "tipo": "transfer",
         "referencia": "", "fingerprint": "fp-a", "estado": "faltante"},
        {"fecha": "2025-10-04", "descripcion": "De LUIS GOMEZ", "monto": 50000, "tipo": "transfer",
         "referencia": "", "fingerprint": "fp-b", "estado": "faltante"},
        {"fecha": "2025-10-05", "descripcion": "Transfer", "monto": 7000, "tipo": "transfer",
         "referencia": "", "fingerprint": "fp-c", "estado": "faltante"},
    ]
    with SessionLocal() as db:
        h = HistorialExtracto(usuario_id=usuario, cuenta_id=cuenta, banco_detectado="nequi", total_movimientos=3,
                              exactos=0, aproximados=0, faltantes=3, importados=0, estado="pendiente_revision",
                              review_json=json.dumps(review))
        db.add(h)
        db.commit()
        hid = h.id
    r = client.post(f"/conciliacion/historial/{hid}/importar", json={
        "fingerprints": ["fp-a", "fp-b", "fp-c"], "categorias": {}, "recordar": [], "aplicar_anteriores": []}).json()
    assert r["importados"] == 2 and r["sin_direccion"] == 1
    # 100.000 - 20.000 + 50.000 = 130.000 (el ambiguo no se adivina)
    saldo = [c for c in client.get("/cuentas").json() if c["id"] == cuenta][0]["saldo"]
    assert saldo == 130000
    tipos = sorted(m["tipo"] for m in client.get("/movimientos").json())
    assert tipos == ["expense", "income"]
