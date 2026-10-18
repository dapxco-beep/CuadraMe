"""Asuntos típicos de bancos y billeteras colombianas: cada transacción se detecta como tal y los avisos
(extracto listo, pago fallido, publicidad) siguen sin ofrecerse. Textos sintéticos."""
import pytest

from app.extractos_gmail import es_aviso_no_transaccion, es_notificacion_transaccion

TRANSACCIONES = [
    ("¡Pago exitoso!", "Pagaste $20.000 a Juan"),
    ("Pago exitoso", "Nequi: pagaste $8.000"),
    ("Transferencia exitosa", "Tu transferencia por $50.000 fue exitosa"),
    ("Compra aprobada", "Tu compra por $30.000 en Exito fue aprobada"),
    ("Retiro exitoso", "Retiraste $100.000"),
    ("Recibiste plata", "Juan te envió $40.000"),
    ("Pagaste en CAMARA DE COMERCIO DE BOGOTA con Cuenta Nu", "$390.500"),
    ("Pagaste en Rappi con Tarjeta Nu", "$12.000"),
    ("Enviaste plata por Bre-B", "$30.000"),
    ("Realizaste una compra", "por $15.000"),
    ("Tu pago fue recibido", "Recibimos $200.000"),
    ("Pago PSE aprobado", "Tu pago PSE por $90.000"),
    ("Abono a tu cuenta", "$5.000"),
    ("Débito automático", "Se debitó $50.000"),
    ("Daviplata: envío de dinero", "Enviaste $20.000"),
    ("Recibiste dinero en Daviplata", "$10.000"),
    ("Compra por $45.000 en EXITO", "Bancolombia"),
    ("Transacción exitosa", "Davivienda: transacción por $80.000"),
    # Las que antes se perdían
    ("Te llegó plata", "Ana te envió $10.000"),
    ("Plata recibida", "$10.000"),
    ("Dinero recibido", "$30.000"),
    ("Recarga exitosa", "Recargaste $10.000 a tu celular"),
    ("Recargaste tu Nequi", "$20.000"),
    ("Depósito recibido", "$100.000"),
    ("Te depositaron", "$100.000"),
    ("Te consignaron", "$100.000"),
    ("Te transfirieron", "$100.000"),
    ("Transferiste $50.000", "a Ana"),
    ("Gastaste $20.000 en Uber", ""),
    ("Sacaste plata del cajero", "$100.000"),
    ("Nómina recibida", "$100.000"),
    ("Operación exitosa", "Valor $100.000"),
]

AVISOS = [
    ("Tu extracto está listo", "Descárgalo"),
    ("Compra rechazada", "No pudimos procesarla"),
    ("Aviso: tu pago no se pudo realizar", "Faltan fondos"),
    ("Oferta: pago en cuotas", "Promoción para ti"),
    ("Código de verificación", "Tu clave dinámica"),
]


@pytest.mark.parametrize("asunto,snippet", TRANSACCIONES, ids=[a for a, _ in TRANSACCIONES])
def test_se_detecta_como_transaccion(asunto, snippet):
    assert es_notificacion_transaccion(asunto, snippet)


@pytest.mark.parametrize("asunto,snippet", AVISOS, ids=[a for a, _ in AVISOS])
def test_los_avisos_no_se_ofrecen_como_movimiento(asunto, snippet):
    assert es_aviso_no_transaccion(asunto, snippet) or not es_notificacion_transaccion(asunto, snippet)
    assert not es_notificacion_transaccion(asunto, snippet)
