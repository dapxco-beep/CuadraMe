"""Diccionario y huella de comercio con descripciones SINTÉTICAS, con la forma de las que
traen los extractos de Nu y Nequi (nombres y comercios inventados)."""
import pytest

from app.clave_comercio import clave_comercio
from app.comercios_conocidos import clasificar_por_diccionario
from app.contabilidad import es_pago_tarjeta


def _cat(desc):
    r = clasificar_por_diccionario(desc)
    return r["categoria"] if r else None


@pytest.mark.parametrize("desc,esperada", [
    ("Compra en OXXO CENTRO 114 con tarjeta débito", "Comida"),
    ("Compra en EDS LA ESQUINA 12 con tarjeta débito", "Transporte"),
    ("Compra en SERVICENTRO EL PASO con tarjeta débito", "Transporte"),
    ("Compra en DOLLARCITY NORTE 3 con tarjeta débito", "Compras"),
    ("Compra en NOVAVENTA BOG CODIGO M con tarjeta débito", "Compras"),
    ("Compra en R46 CREPESYWAFFLES CENTRO con tarjeta débito", "Comida"),
    ("Enviaste a FONDO DE INVERSIÓN COLECTIVA EJEMPLO", "Ahorro e inversión"),
    ("Enviaste a Acciones y Valores S.A.", "Ahorro e inversión"),
    ("Traslado a cajita Vacaciones", "Ahorro e inversión"),
    ("Recarga desde Bancolombia", "Transferencias"),
    ("Otros bancos de NU BANK", "Transferencias"),
    ("Para MARIA PEREZ", "Transferencias"),
    ("De JUAN GOMEZ", "Transferencias"),
    ("Gravamen al Movimiento", "4x1000 (GMF)"),
    ("GRAVAMEN AL MOVIMIENTO", "4x1000 (GMF)"),
    ("Pago de Intereses", "Rendimientos"),
    ("Reembolso realizado", "Ingresos"),
    ("BARBERIA LOS CRACKS", "Salud"),
])
def test_conceptos_y_comercios_frecuentes_se_reconocen(desc, esperada):
    assert _cat(desc) == esperada


def test_para_en_medio_de_una_compra_no_es_transferencia():
    assert _cat("Compra en ARTICULOS PARA TI con tarjeta débito") != "Transferencias"


def test_pago_de_intereses_es_ingreso_y_no_comision():
    r = clasificar_por_diccionario("Pago de Intereses")
    assert r["tipo"] == "income"


def test_la_tarjeta_pagada_desde_la_cuenta_no_es_gasto():
    assert es_pago_tarjeta("Pagaste tu tarjeta")
    assert es_pago_tarjeta("Pagaste la tarjeta de crédito")
    assert not es_pago_tarjeta("Compra en TIENDA con tarjeta débito")


@pytest.mark.parametrize("a,b", [
    ("Compra en R46 CREPESYWAFFLES con tarjeta débito", "Compra en H11 CREPESYWAFFLES H T con tarjeta débito"),
    ("Compra en OXXO CENTRO 114 con tarjeta débito", "Compra en OXXO CENTRO 22 con tarjeta débito"),
    ("Compra en BOLD*Cafe Luna con tarjeta débito", "Compra en Cafe Luna con tarjeta débito"),
    ("Compra en EDS PRIMAX NORTE con tarjeta débito", "Compra en PRIMAX NORTE con tarjeta débito"),
])
def test_la_huella_agrupa_el_mismo_comercio_con_codigos_distintos(a, b):
    assert clave_comercio(a) == clave_comercio(b) != ""


def test_la_huella_no_funde_comercios_distintos():
    assert clave_comercio("Compra en TIENDA D1 NORTE con tarjeta débito") != clave_comercio("Compra en OXXO NORTE con tarjeta débito")
    # 'd1' es una marca real y se conserva aunque parezca un código
    assert "d1" in clave_comercio("Compra en TIENDA D1 NORTE con tarjeta débito").split()
