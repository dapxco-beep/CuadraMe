"""Bre-B, pasarelas de pago (BOLD*, PayU*, Wompi*...) y billeteras (Mercado Pago, Rappi Pay)."""
import pytest

from app.comercios_conocidos import clasificar_por_diccionario as clasificar


@pytest.mark.parametrize("texto,tipo", [
    ("Bre-B Enviado a Juan Perez", "expense"),
    ("BREB 3001234567", "expense"),
    ("Pago Bre B llave @maria", "expense"),
    ("Transferencia inmediata Bancolombia", "expense"),
    ("TRANSFERENCIA BRE-B RECIBIDA", "income"),
    ("Recibiste por Bre-B de Ana", "income"),
])
def test_bre_b_es_transferencia_nunca_otros(texto, tipo):
    r = clasificar(texto)
    assert r and r["categoria"] == "Transferencias" and r["tipo"] == tipo
    assert r["confianza"] <= 0.5  # nunca se auto-importa sola


@pytest.mark.parametrize("texto,categoria", [
    ("BOLD*Cafe Luna", "Comida"),
    ("COMPRA BOLD*DROGUERIA SAN JORGE", "Salud"),
    ("BOLD*Taller El Rayo", "Transporte"),
    ("PAYU*SPOTIFY", "Suscripciones"),
    ("WOMPI*GIMNASIO FIT", "Salud"),
    ("MERCADOPAGO*NETFLIX", "Suscripciones"),
    ("MP*Rappi", "Comida"),
    ("EPAYCO*Udemy", "Educación"),
    ("Addi*ZARA", "Compras"),
])
def test_pasarela_clasifica_el_comercio_real(texto, categoria):
    r = clasificar(texto)
    assert r and r["categoria"] == categoria
    assert "pagado con" in r["razon"]


def test_pasarela_sola_no_inventa_categoria():
    assert clasificar("BOLD*") is None
    assert clasificar("PAGO PSE") is None
    assert clasificar("Wompi") is None


def test_billeteras_no_son_comida():
    assert clasificar("Mercado Pago")["categoria"] == "Transferencias"
    assert clasificar("RAPPI PAY")["categoria"] == "Transferencias"
    # ...pero lo que ya funcionaba sigue igual
    assert clasificar("Mercado Libre")["categoria"] == "Compras"
    assert clasificar("compra en el mercado")["categoria"] == "Comida"
    assert clasificar("Rappi domicilio")["categoria"] == "Comida"
