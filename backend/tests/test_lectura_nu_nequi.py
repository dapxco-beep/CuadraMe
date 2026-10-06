"""Lectura de extractos de Nu y Nequi con textos SINTÉTICOS (misma estructura que los
extractos reales, datos inventados). Cubre los fallos hallados al medir con extractos
reales: números sueltos en la descripción ('OXXO CENTRO 114'), banco mal detectado
y transferencias propias confundidas con las de otra persona del mismo nombre."""
from app.conciliacion import detectar_banco, es_transferencia_propia, fijar_nombre_titular, parse_texto_con_regex

NU = """Hola, Ana Maria
Llegó tu extracto de Octubre
Ana Maria Lopez Rojas
Calle 2020 # 5-5
Nu Placa Número de Cuenta Período
ABC123 11112222 01 - 31 OCT 2025
Tu dinero al inicio del mes $1.000.000,00
Lo que entró a tu cuenta +$500.000,00
Lo que salió de tu cuenta -$300.000,00
Movimientos
01 oct Compra en TIENDA UNO 72 SUR con tarjeta débito -$22.000,00
01 oct Compra en MERCADO XYZ 114 con tarjeta débito -$11.400,00
02 oct Recibiste de Banco Ejemplo +$500.000,00
Nu Financiera Los rendimientos que genera tu cuenta los
2 / 2
Movimientos
03 oct Compra en ALMACEN GRANDE AVX 68 con tarjeta débito -$2.299.070,00
03 oct Enviaste a Pepito nequi -$15.000,00
03 oct Enviaste a Ana Maria Lopez Rojas -$17.000,00
04 oct Enviaste a Ana Gomez -$9.000,00
"""


def _por_desc(movs, fragmento):
    return [m for m in movs if fragmento in m["descripcion"]]


def test_nu_numeros_sueltos_en_la_descripcion_no_son_el_monto():
    fijar_nombre_titular("Ana Maria Lopez Rojas")
    movs, descartados = parse_texto_con_regex(NU)
    assert descartados == 0
    assert len(movs) == 7
    assert _por_desc(movs, "TIENDA UNO 72 SUR")[0]["monto"] == 22000
    assert _por_desc(movs, "MERCADO XYZ 114")[0]["monto"] == 11400
    assert _por_desc(movs, "ALMACEN GRANDE")[0]["monto"] == 2299070


def test_nu_cadena_de_totales_cierra_sin_perder_ni_duplicar_lineas_entre_paginas():
    fijar_nombre_titular("Ana Maria Lopez Rojas")
    movs, _ = parse_texto_con_regex(NU)
    entradas = sum(m["monto"] for m in movs if m["tipo"] == "income")
    assert entradas == 500000
    salidas = sum(m["monto"] for m in movs if m["tipo"] == "expense")
    propias = sum(m["monto"] for m in movs if m["tipo"] == "transfer")
    # salidas del extracto = 22.000 + 11.400 + 2.299.070 + 15.000 + 17.000 + 9.000
    assert salidas + propias == 2373470


def test_nu_el_anio_sale_del_periodo_no_de_la_direccion():
    movs, _ = parse_texto_con_regex(NU)
    assert {m["fecha"][:4] for m in movs} == {"2025"}


def test_nu_banco_se_detecta_aunque_un_movimiento_mencione_nequi():
    assert detectar_banco(NU) == "nu"


def test_nequi_banco_se_detecta_aunque_un_movimiento_mencione_nu_bank():
    texto = ("Extracto de depósito de bajo monto de:\nAna Maria\nEstado de depósito de bajo monto para el período de: 2026/03/01 a 2026/03/31\n"
             "28/03/2026 Para NU BANK $-7,000.00 $4,212.75\n")
    assert detectar_banco(texto) == "nequi"


def test_banco_no_se_confunde_por_palabras_que_contienen_una_marca_corta():
    # 'dale' y 'uala' dentro de otra palabra no son Nequi/Dale/Uala.
    assert detectar_banco("Extracto\nCosto de gestion adicionalidades vendale\n") == "generico"


def test_transferencia_propia_exige_que_la_contraparte_sea_el_titular():
    fijar_nombre_titular("Ana Maria Lopez Rojas")
    assert es_transferencia_propia("Enviaste a Ana Maria Lopez Rojas")
    assert es_transferencia_propia("Enviaste a Ana nequi")
    assert es_transferencia_propia("RECIBI POR BRE-B DE: ANA")
    assert not es_transferencia_propia("Enviaste a Ana Gomez")
    assert not es_transferencia_propia("Para ANA BELEN RUIZ")
    assert not es_transferencia_propia("Enviaste a Pepito nequi")


NEQUI = """Extracto de depósito de bajo monto de:
ANA MARIA LOPEZ ROJAS
Estado de depósito de bajo monto para el período de: 2026/03/01 a 2026/03/31
Resumen
Saldo anterior $2,000.00 Saldo promedio $1,000.00
Total abonos $60,000.00 Cuentas por cobrar $0.00
Total cargos $57,028.00 Valor de intereses pagados $5.00
Saldo actual $4,972.00 Retefuente $0.00
Fecha del movimiento Descripción Valor Saldo
28/03/2026 Para JUAN PEREZ $-7,000.00 $4,972.00
28/03/2026 Gravamen al Movimiento $-28.00 $11,972.00
Fecha del movimiento Descripción Valor Saldo
27/03/2026 PAGO EN QR BRE-B: TIENDA $-50,000.00 $12,000.00
26/03/2026 RECIBI POR BRE-B DE: LUIS $60,000.00 $62,000.00
"""


def test_nequi_formato_dolar_con_coma_de_miles_lee_todo_y_cierra_la_cadena():
    fijar_nombre_titular("Ana Maria Lopez Rojas")
    movs, _ = parse_texto_con_regex(NEQUI)
    assert len(movs) == 4
    assert sum(m["monto"] for m in movs if m["tipo"] == "income") == 60000
    assert sum(m["monto"] for m in movs if m["tipo"] == "expense") == 57028
    assert 2000 + 60000 - 57028 == 4972
