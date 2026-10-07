"""Lectura de Nequi con casos sintéticos raros: líneas partidas, signos y separadores distintos,
movimientos consecutivos idénticos y líneas que no se pueden leer (que deben avisar)."""
from app.conciliacion import _num_flexible, cuadra_con_el_resumen, fijar_nombre_titular, parse_texto_con_regex

ENCABEZADO = """Extracto de depósito de bajo monto de:
ANA MARIA LOPEZ ROJAS
Resumen
Saldo anterior $10,000.00 Saldo promedio $1,000.00
Total abonos $50,000.00 Cuentas por cobrar $0.00
Total cargos $33,700.00 Valor de intereses pagados $5.00
Saldo actual $26,300.00 Retefuente $0.00
Fecha del movimiento Descripción Valor Saldo
"""


def _leer(cuerpo, encabezado=ENCABEZADO):
    fijar_nombre_titular("Ana Maria Lopez Rojas")
    texto = encabezado + cuerpo
    movs, descartados = parse_texto_con_regex(texto)
    return texto, movs, descartados


def test_numeros_en_varios_estilos():
    assert _num_flexible("8,200.00") == 8200 and _num_flexible("8.200,00") == 8200
    assert _num_flexible("8,200") == 8200 and _num_flexible("8.200") == 8200
    assert _num_flexible("1,234,567") == 1234567 and _num_flexible("1.234.567,5") == 1234567.5
    assert _num_flexible("8.20") == 8.2 and _num_flexible("abc") is None


def test_signos_y_formatos_raros_se_leen_y_la_cadena_cierra():
    cuerpo = """28/03/2026 Compra tienda uno $-8,200.00 $41,800.00
27/03/2026 Compra tienda dos -$5,500.00 $36,300.00
26/03/2026 Compra tienda tres $ -20,000.00 $16,300.00
25/03/2026 Pago recibido $50,000.00 $66,300.00
"""
    # abonos 50.000; cargos 8.200 + 5.500 + 20.000 = 33.700; 10.000 + 50.000 - 33.700 = 26.300
    texto, movs, d = _leer(cuerpo)
    assert len(movs) == 4 and d == 0
    assert sorted(m["monto"] for m in movs) == [5500, 8200, 20000, 50000]
    assert [m["tipo"] for m in movs] == ["expense", "expense", "expense", "income"]
    assert cuadra_con_el_resumen(texto, movs) is True


def test_linea_partida_en_varios_renglones_se_une():
    cuerpo = """28/03/2026 Compra tienda uno
sucursal centro $-8,200.00 $41,800.00
27/03/2026
Compra tienda dos
$-5,500.00
26/03/2026 Compra tienda tres $-20,000.00 $16,300.00
25/03/2026 Pago recibido $50,000.00 $66,300.00
"""
    texto, movs, d = _leer(cuerpo)
    assert len(movs) == 4 and d == 0
    assert movs[0]["descripcion"] == "Compra tienda uno sucursal centro" and movs[0]["monto"] == 8200


def test_movimientos_consecutivos_identicos_son_dos():
    cuerpo = """28/03/2026 Compra tienda $-8,200.00 $41,800.00
28/03/2026 Compra tienda $-8,200.00 $33,600.00
28/03/2026 Otro cargo $-17,300.00 $16,300.00
25/03/2026 Pago recibido $50,000.00 $66,300.00
"""
    texto, movs, d = _leer(cuerpo)
    assert len(movs) == 4 and sum(1 for m in movs if m["monto"] == 8200) == 2 and d == 0
    assert cuadra_con_el_resumen(texto, movs) is True


def test_linea_ilegible_se_cuenta_y_avisa():
    cuerpo = """28/03/2026 Compra tienda uno $-8,200.00 $41,800.00
27/03/2026 Compra tienda dos monto ilegible
26/03/2026 Compra tienda tres $-17,300.00 $16,300.00
25/03/2026 Pago recibido $50,000.00 $66,300.00
"""
    texto, movs, d = _leer(cuerpo)
    assert len(movs) == 3
    assert d >= 1  # una línea con forma de movimiento no se pudo leer
    assert cuadra_con_el_resumen(texto, movs) is False


def test_si_falta_un_cargo_la_cadena_de_saldos_avisa_aunque_no_haya_resumen_de_totales():
    sin_totales = ENCABEZADO.replace("Total abonos $50,000.00 Cuentas por cobrar $0.00\n", "").replace(
        "Total cargos $33,700.00 Valor de intereses pagados $5.00\n", "")
    cuerpo = """28/03/2026 Compra tienda uno $-8,200.00 $41,800.00
26/03/2026 Compra tienda tres $-17,300.00 $16,300.00
25/03/2026 Pago recibido $50,000.00 $66,300.00
"""
    texto, movs, d = _leer(cuerpo, sin_totales)
    assert len(movs) == 3 and cuadra_con_el_resumen(texto, movs) is None
    assert d == 1  # 10.000 + 50.000 - 33.700 != 26.300 con lo leído (faltan 8.200... o sobra algo)


def test_lectura_completa_sin_perdidas_no_avisa():
    cuerpo = """28/03/2026 Compra tienda uno $-8,200.00 $41,800.00
27/03/2026 Compra tienda dos $-5,500.00 $36,300.00
26/03/2026 Compra tienda tres $-20,000.00 $16,300.00
25/03/2026 Pago recibido $50,000.00 $66,300.00
"""
    _t, movs, d = _leer(cuerpo)
    assert len(movs) == 4 and d == 0
