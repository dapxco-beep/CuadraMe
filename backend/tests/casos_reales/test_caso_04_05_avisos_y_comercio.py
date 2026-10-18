"""CASOS REALES 4 y 5.

4. Avisos que NO son transacciones llegaron a «Por revisar» con montos absurdos (el NIT del pie, el número de
   cuenta): «extracto listo», «tarjeta agregada a Apple Pay», pago fallido («Faltan fondos»), tarjeta en
   creación, publicidad / novedades. Ninguno debe contarse como movimiento.
5. Comercio vacío: «Pagaste en:\nICETEX» (el nombre en la línea de abajo) o «Compraste en:» sin nada dejaban
   el movimiento sin descripción o con el nombre del banco. Debe salir «Pago a Icetex» o un respaldo claro
   («Gasto sin detalle»), nunca vacío ni el remitente.
"""
import pytest

from app import extractos_gmail as eg
from app.gmail_extract import detectar_tipo, extraer_comercio, extraer_monto

REM = "Nu <nu@nu.com.co>"


@pytest.mark.parametrize("asunto", [
    "El extracto de tu Cuenta Nu ya está aquí",          # extracto listo
    "Llegó el extracto de tu tarjeta de crédito Nu",
    "Agregaste tu tarjeta Nu a Apple Pay",               # tarjeta agregada
    "Faltan fondos para pagar en Didi",                  # pago fallido
    "Estamos creando tu tarjeta de crédito",
    "ANA, novedades Nu en septiembre",                   # publicidad
])
def test_caso4_avisos_no_son_transacciones(asunto):
    assert eg.es_aviso_no_transaccion(asunto, "") is True
    assert eg.es_notificacion_transaccion(asunto, "pago movimientos compra") is False


@pytest.mark.parametrize("asunto", [
    "¡Recibiste plata por Bre-B!", "¡Enviaste plata por Bre-B!", "¡Ya entró tu pago!",
    "Pagaste en TECNIPAGOS S A con Cuenta Nu", "Compra aprobada",
])
def test_caso4_las_transacciones_reales_siguen_pasando(asunto):
    assert eg.es_aviso_no_transaccion(asunto, "") is False


def test_caso4_un_aviso_con_nit_no_produce_monto():
    cuerpo = "Tu extracto ya está disponible. NIT 901.658.107-2 cuenta 12345678901 línea 3001234567 año 2026."
    assert extraer_monto(cuerpo, estricto=True) == 0


@pytest.mark.parametrize("cuerpo,esperado", [
    ("Hola. Pagaste en: ICETEX. La cantidad de: $1.000.000,00.", "Pago a Icetex"),
    ("Hola: Pagaste en:\nICETEX\nLa cantidad de: $1.000.000,00.", "Pago a Icetex"),   # nombre en la línea de abajo
    ("Hola. Compraste en: Rappi. La cantidad de: $32.900,00.", "Compra en Rappi"),
])
def test_caso5_comercio_se_lee_aunque_este_en_otra_linea(cuerpo, esperado):
    asunto = "Pagaste con tu Cuenta de ahorros Nu"
    assert extraer_comercio(REM, asunto, cuerpo) == esperado
    assert detectar_tipo(f"{asunto} {cuerpo}") == "expense"


@pytest.mark.parametrize("cuerpo", [
    "Pagaste en: . La cantidad de: $9.000,00.",
    "Pagaste en:",
    "Compraste en:\n\nLa cantidad de: $5.000,00.",
])
def test_caso5_comercio_vacio_nunca_queda_en_blanco_ni_es_el_banco(cuerpo):
    r = extraer_comercio(REM, "Pagaste con tu Cuenta de ahorros Nu", cuerpo)
    assert r.strip(), "el movimiento no puede quedar sin descripción"
    assert "nu" not in r.lower().split() and "cantidad" not in r.lower()
