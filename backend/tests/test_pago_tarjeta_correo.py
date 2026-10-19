"""Aviso de Nu «Pagaste con tu Cuenta de ahorros Nu» cuando lo que se paga es la tarjeta Nu propia. Todo sintético.

Antes el comercio salía «Pago a linea Costo de transacción» y el pago se contaba como gasto. Ahora: comercio «Pago de tarjeta
Nu», categoría «Pago de tarjeta» (traslado entre tus productos, no gasto), y el «impuesto del 4xmil» del aviso NO se registra
aparte: el «Impuesto del 4x1000» del extracto del mes ya lo incluye."""
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'pago_tarjeta_correo.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import cuadre_encadenado as ce  # noqa: E402
from app import limites  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.autocat import ClasificadorUsuario  # noqa: E402
from app.contabilidad import CATEGORIA_PAGO_TARJETA, es_pago_tarjeta, tipos_efectivos  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.gmail_extract import (  # noqa: E402
    detectar_tipo, es_posible_traslado_propio, extraer_comercio, extraer_impuesto_4xmil, extraer_monto,
)
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento  # noqa: E402
from app.routers import conciliacion as mod  # noqa: E402

client = TestClient(app)
REM = "Nu <nu@nu.com.co>"
ASUNTO = "Pagaste con tu Cuenta de ahorros Nu"
CUERPO = ("Hola, Persona Prueba: Acá está el detalle de tu pago. Pagaste en: linea Costo de transacción. La cantidad de: $300.000,00. "
          "Más el impuesto del 4xmil de: $1.200,00. Si no fuiste tú, contáctanos vía chat.")


def test_el_comercio_es_el_pago_de_la_tarjeta_y_no_la_linea_del_banco():
    assert extraer_comercio(REM, ASUNTO, CUERPO) == "Pago de tarjeta Nu"
    assert es_pago_tarjeta("Pago de tarjeta Nu")
    # con otras formas de nombrar la tarjeta en el aviso
    assert extraer_comercio(REM, ASUNTO, "Pagaste en: Tarjeta de crédito Nu. La cantidad de: $50.000,00.") == "Pago de tarjeta Nu"
    assert extraer_comercio(REM, ASUNTO, "Pagaste en: Línea de crédito, pago. La cantidad de: $50.000,00.") == "Pago de tarjeta Nu"


def test_un_comercio_comun_o_un_prestamo_siguen_siendo_gasto_real():
    assert extraer_comercio(REM, ASUNTO, "Pagaste en: ICETEX. La cantidad de: $1.000.000,00.") == "Pago a Icetex"
    assert extraer_comercio(REM, ASUNTO, "Pagaste en: Línea Directa Seguros. La cantidad de: $90.000,00.") == "Pago a Línea Directa Seguros"
    assert extraer_comercio(REM, ASUNTO, "Pagaste en: Crédito Fácil Cuota. La cantidad de: $90.000,00.") == "Pago a Crédito Fácil Cuota"


def test_el_monto_es_la_cantidad_y_el_4xmil_se_lee_aparte_sin_sumarse():
    texto = f"{ASUNTO} {CUERPO}"
    assert extraer_monto(texto) == 300_000 and extraer_impuesto_4xmil(texto) == 1_200
    assert extraer_impuesto_4xmil("Más el impuesto del 4xmil de: $0,00.") == 0
    assert extraer_impuesto_4xmil("Pagaste en: Rappi. La cantidad de: $5.000,00.") == 0
    assert detectar_tipo(texto) == "expense"
    assert es_posible_traslado_propio("Pago de tarjeta Nu")


def test_el_pago_a_la_tarjeta_se_categoriza_y_cuenta_como_traslado_no_gasto():
    como("pt-1")
    db = SessionLocal()
    try:
        r = ClasificadorUsuario(db, "pt-1").clasificar("Pago de tarjeta Nu", f"{ASUNTO} {CUERPO}")
        assert r["categoria"] == CATEGORIA_PAGO_TARJETA
    finally:
        db.close()
    mov = {"id": "m1", "tipo": "expense", "monto": 300_000, "descripcion": "Pago de tarjeta Nu", "categoria": CATEGORIA_PAGO_TARJETA,
           "cuenta_id": "ahorros", "fuente": "email", "notas": "", "fecha": datetime(2026, 8, 17)}
    assert tipos_efectivos([mov], {"ahorros": "ahorro"})["m1"] == "transfer"
    # Y como estaba antes («Pago a linea ...» sin categoría de sistema) contaba como gasto: ya no sale así.
    viejo = {**mov, "descripcion": "Pago a linea Costo de transacción", "categoria": "Otros"}
    assert tipos_efectivos([viejo], {"ahorros": "ahorro"})["m1"] == "expense"


# ── El 4x1000 del aviso no se cuenta dos veces con el del extracto ──────────────────────────
EXTRACTO = """Nu Colombia
Número de Cuenta 1234567890
Período 01 - 31 AGO 2026
Resumen de tus movimientos
Tu dinero al inicio del mes $1.000.000,00
Lo que entró a tu cuenta +$500.000,00
Lo que salió de tu cuenta -$300.000,00
Impuesto del 4x1000 $1.200,00
Rendimiento total de tu cuenta +$0,00
Tu dinero a final del mes $1.198.800,00
05 ago Sueldo Empresa Inventada +$500.000,00
17 ago Pago de tarjeta Nu -$300.000,00
"""


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["u"]
    limites._eventos.clear()
    yield
    app.dependency_overrides.pop(get_current_user, None)


USUARIO = {"u": UsuarioActual(id="pt-0", email="p@test.com", nombre="Persona Prueba")}


def como(uid):
    USUARIO["u"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre="Persona Prueba")


def test_el_4x1000_del_extracto_se_registra_una_sola_vez_aunque_el_pago_vino_por_correo(monkeypatch):
    como("pt-2")
    cuenta = client.post("/cuentas", json={"nombre": "Nu Colombia", "tipo": "ahorro", "saldo": 0}).json()["id"]
    db = SessionLocal()
    try:  # el aviso del pago ya se había aprobado: gasto de $300.000 (la cantidad) y NO un segundo movimiento por el 4xmil
        db.add(Movimiento(usuario_id="pt-2", cuenta_id=cuenta, descripcion="Pago de tarjeta Nu", categoria=CATEGORIA_PAGO_TARJETA, tipo="expense",
                          monto=300_000, fecha=datetime(2026, 8, 17, 14, 30), fuente="email"))
        db.get(Cuenta, cuenta).saldo -= 300_000
        db.commit()
    finally:
        db.close()
    monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: EXTRACTO)
    r = client.post("/conciliacion/procesar", json={"cuenta_id": cuenta, "pdf_base64": "x"}).json()
    fps = [i["fingerprint"] for i in r["review"] if i["estado"] == "faltante"]
    assert client.post(f"/conciliacion/historial/{r['historial_id']}/importar", json={"fingerprints": fps}).status_code == 200
    db = SessionLocal()
    try:
        ms = db.query(Movimiento).filter(Movimiento.usuario_id == "pt-2").all()
        gmf = [m for m in ms if m.categoria == "4x1000 (GMF)"]
        assert [m.monto for m in gmf] == [1200.0]  # una vez, con lo que dice el extracto
        pagos = [m for m in ms if m.categoria == CATEGORIA_PAGO_TARJETA]
        assert len(pagos) == 1 and pagos[0].monto == 300_000  # el pago del correo y el del extracto son UNO
        fila = ce.calcular(db, db.get(Cuenta, cuenta))["meses"][0]
        assert fila["estado"] == "cuadra" and fila["diferencia"] == 0
        tipos = tipos_efectivos(ms, {cuenta: "ahorro"})
        reales = sorted(tipos[m.id] for m in ms if m.fuente != "ajuste_saldo")  # sin el saldo inicial automático
        assert reales == ["expense", "income", "transfer"]  # sueldo, 4x1000 (gasto real) y pago de tarjeta (traslado)
    finally:
        db.close()
