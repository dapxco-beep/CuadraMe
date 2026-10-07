"""Un archivo que NO es un extracto (carta, inscripción, factura) se rechaza con un mensaje claro y
no importa nada; un extracto de banco desconocido con tabla coherente sí se acepta. Textos inventados."""
import os
import tempfile
import uuid

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'no_extracto.db')}")

import pytest  # noqa: E402

from app.conciliacion import evaluar_extracto, parse_texto_con_regex  # noqa: E402
from tests.test_extractos_gmail import GmailFalso, client, conectar_usuario  # noqa: E402

pytest.importorskip("reportlab.pdfgen.canvas")

CARTA = """Corporación Ejemplo
Inscripción en línea
Estimado participante, su inscripción quedó registrada el 12/03/2026 con el número 32.
Valor de la inscripción 32
Gracias por su interés. Atentamente, Secretaría."""

FACTURA = """Papelería La Esquina S.A.S. NIT 900.000.000-1
Factura de venta 0045
Fecha 05/09/2026
Descripción Cantidad Valor
Resma de papel 2 18.000
Total a pagar 36.000"""

EXTRACTO_GENERICO = """Cooperativa Ejemplo - Extracto de cuenta de ahorros
Periodo 01/09/2026 al 30/09/2026
Saldo anterior 500.000
Fecha Descripcion Valor
03/09/2026 COMPRA SUPERMERCADO CENTRO -45.000
10/09/2026 ABONO NOMINA EMPRESA 1.200.000
15/09/2026 RETIRO CAJERO AUTOMATICO -100.000
28/09/2026 COBRO CUOTA DE MANEJO -9.500
Saldo final 1.545.500"""


def test_evaluar_rechaza_una_carta():
    movs, _ = parse_texto_con_regex(CARTA)
    ok, motivo = evaluar_extracto(CARTA, "generico", movs)
    assert ok is False and "no parece un extracto" in motivo


def test_factura_con_una_tabla_pequena_se_rechaza():
    movs, _ = parse_texto_con_regex(FACTURA)
    assert evaluar_extracto(FACTURA, "generico", movs)[0] is False


def test_extracto_generico_plausible_se_acepta():
    movs, _ = parse_texto_con_regex(EXTRACTO_GENERICO)
    assert len(movs) == 4
    assert evaluar_extracto(EXTRACTO_GENERICO, "generico", movs) == (True, "")


def test_fechas_imposibles_o_dispersas_se_rechazan():
    base = {"descripcion": "Compra tienda", "monto": 1000.0, "tipo": "expense"}
    rotas = [dict(base, fecha=f) for f in ("2026-13-45", "2026-02-30", "2026-01-01")]
    assert evaluar_extracto("extracto saldo fecha valor", "generico", rotas)[0] is False
    dispersas = [dict(base, fecha=f) for f in ("2024-01-05", "2025-03-05", "2026-09-05")]
    assert evaluar_extracto("extracto saldo fecha valor", "generico", dispersas)[0] is False


def test_banco_conocido_no_se_cuestiona():
    assert evaluar_extracto("lo que sea", "nu", [])[0] is True


@pytest.fixture()
def cuenta_api(monkeypatch):
    conectar_usuario(f"no-extracto-{uuid.uuid4().hex[:8]}", GmailFalso([], {}), monkeypatch)
    return client.post("/cuentas", json={"nombre": "Nu", "saldo": 0}).json()


def _subir(monkeypatch, cuenta, texto):
    from app.routers import conciliacion as mod
    monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: texto)
    # Si el código llegara a la IA con una carta, que se note.
    monkeypatch.setattr(mod, "extraer_via_ia", lambda *a, **k: [
        {"fecha": "2026-03-12", "descripcion": "Inventado", "monto": 32, "tipo": "income", "referencia": ""}])
    return client.post("/conciliacion/procesar", json={"cuenta_id": cuenta["id"], "pdf_base64": "x"}).json()


@pytest.mark.parametrize("texto", [CARTA, FACTURA])
def test_api_rechaza_lo_que_no_es_extracto_y_no_importa_nada(monkeypatch, cuenta_api, texto):
    r = _subir(monkeypatch, cuenta_api, texto)
    assert r["ok"] is False and r["parece_extracto"] is False
    assert "no parece un extracto bancario" in r["error"] and r["motivo_rechazo"]
    assert r["review"] == [] and r["auto_importados"] == 0
    assert client.get("/movimientos").json() == []
    assert [c for c in client.get("/cuentas").json() if c["id"] == cuenta_api["id"]][0]["saldo"] == 0


def test_api_acepta_extracto_generico_plausible(monkeypatch, cuenta_api):
    r = _subir(monkeypatch, cuenta_api, EXTRACTO_GENERICO)
    assert r["ok"] is True and r["parece_extracto"] is True
    assert r["total_movimientos"] == 4
