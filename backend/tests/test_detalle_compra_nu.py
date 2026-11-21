"""Detalle de una compra con tarjeta en la app de Nu (pantallazo del atajo «Registrar»). Datos inventados."""
from app import notificaciones as notif

TEXTO = ("Tienda Ejemplo $120.500,00 12:26, Viernes, 13 de Noviembre de 2026 Comprobante Reportar problema "
         "Establecimiento Tienda Ejemplo Categoría Transporte Tarjeta física ···· 1234 Cuotas 1 cuota de $120.500,00")


def test_compra_con_tarjeta_de_nu_se_lee_completa():
    n = notif.interpretar("auto", "", TEXTO)
    assert n.monto == 120500 and n.tipo == "expense" and not n.tipo_incierto
    assert n.comercio == "Tienda Ejemplo"
    assert n.tarjeta == "1234"
    assert n.fecha == "2026-11-13T12:26:00"


def test_compra_a_cuotas_lo_dice_en_el_comercio():
    n = notif.interpretar("auto", "", TEXTO.replace("1 cuota de", "3 cuotas de"))
    assert n.comercio == "Tienda Ejemplo (3 cuotas)"
    assert n.tipo == "expense" and not n.tipo_incierto
