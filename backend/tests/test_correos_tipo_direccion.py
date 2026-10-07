"""
Los correos bancarios siempre se leen con dirección (income/expense), nunca 'transfer'.
Un traslado entre cuentas propias mueve saldo y queda marcado con la pista
posible_traslado_propio, como hacen los lectores de extractos.
"""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'correos_tipo.db')}")

import pytest  # noqa: E402

from app.gmail_extract import detectar_tipo, es_posible_traslado_propio  # noqa: E402
from tests.test_extractos_gmail import GmailFalso, client, conectar_usuario, mensaje  # noqa: E402

NU = "Nu Colombia <notificaciones@nu.com.co>"


@pytest.mark.parametrize("texto,esperado", [
    ("Recibiste $80.000 de Carlos Gómez", "income"),
    ("Te enviaron $20.000 por Nequi", "income"),
    ("Abono a tu cuenta por $1.000.000", "income"),
    ("Enviaste $50.000 a Ana Pérez", "expense"),
    ("Transferiste $30.000 a Juan", "expense"),
    ("Pago de servicios realizado", "expense"),
    ("Transferencia entre tus cuentas por $100.000", "expense"),
    ("Recibiste una transferencia entre cuentas por $100.000", "income"),
    ("Mensaje sin pistas", "expense"),
    ("", "expense"),
])
def test_detectar_tipo_siempre_tiene_direccion(texto, esperado):
    assert detectar_tipo(texto) == esperado


def test_traslado_propio_se_marca_como_pista():
    assert es_posible_traslado_propio("Transferencia entre tus cuentas por $100.000")
    assert not es_posible_traslado_propio("Compra en Juan Valdez")


def test_aprobar_traslado_propio_mueve_saldo_y_deja_la_marca(monkeypatch):
    conectar_usuario("cc-traslado", GmailFalso(
        [mensaje("m9", NU, "Transferencia entre tus cuentas", "Por $10.000")], {}), monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Nu", "saldo": 100000}).json()
    client.post("/correos/sincronizar")
    pendientes = client.get("/correos/pendientes").json()
    assert pendientes[0]["tipo_sugerido"] == "expense"
    r = client.post(f"/correos/{pendientes[0]['id']}/aprobar", json={"cuenta_id": cuenta["id"]})
    assert r.status_code == 200, r.text
    movs = client.get("/movimientos").json()
    movs = movs["items"] if isinstance(movs, dict) else movs
    assert movs[0]["tipo"] == "expense"
    assert "posible_traslado_propio" in (movs[0].get("notas") or "")
    assert client.get("/cuentas").json()[0]["saldo"] == 90000
