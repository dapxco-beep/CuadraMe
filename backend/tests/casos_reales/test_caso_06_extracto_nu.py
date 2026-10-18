"""CASO REAL 6: lectura del extracto PDF de Nu (cuenta y tarjeta).

Qué pasó: el extracto de la TARJETA Nu trae filas que parecen gastos y no lo son, y el de la CUENTA trae
saldos que hay que leer para cuadrar:
  * «Tu dinero al inicio / a final del mes» = saldos de la cuenta (con cajitas), no movimientos.
  * «Pago $A -$B -$C» con C = A - B es el resumen de la factura anterior: A = total que se debía, B = lo
    pagado, C = lo que quedó pendiente. Lo real es UN pago de B (traslado), no un gasto de C ni de A.
  * «Cobro por cuota $X - $X -» repite el mismo monto: se lee UNA vez (X), no como dos importes.
  * Una línea de dos montos que no cumple C = A - B es ambigua: se marca dudosa con ambos montos
    alternativos para que el usuario decida; jamás se elige uno en silencio.
Datos 100 % inventados.
"""
from app import conciliacion as c
from app import cuadre_extracto as cx
from app.contabilidad import MARCA_TRASLADO_PROPIO

CUENTA = """Nu Colombia
Número de Cuenta 1234567890
Período 01 - 30 SEP 2026
Resumen de tus movimientos
Tu dinero al inicio del mes $500.000,00
Lo que entró a tu cuenta +$900.000,00
Lo que salió de tu cuenta -$400.000,00
Impuesto del 4x1000 $0,00
Costos por retiro $0,00
Rendimiento total de tu cuenta +$1.000,00
Tu dinero a final del mes $1.001.000,00
Dinero en tu Cuenta Nu $1.000,00
Dinero en tus cajitas $1.000.000,00
"""

TARJETA = """Extracto de tu tarjeta de crédito Nu
Período 01 - 31 OCT 2026
Pago mínimo $60.000
05 oct Pago $400.000,00 -$250.000,00 -$150.000,00
06 oct Tienda de prueba -$30.000,00
14 oct Cobro por cuota $7.000,00 - $7.000,00 -$7.000,00
"""


def test_caso6_saldos_de_la_cuenta_no_son_movimientos():
    s = cx.leer_saldos_extracto(CUENTA)
    assert s["saldo_inicial"] == 500000.0 and s["saldo_final"] == 1001000.0
    assert s["saldo_cuenta_principal"] == 1000.0 and s["saldo_cajitas"] == 1000000.0
    assert s["resumen_cuadra"] is True and s["desglose_cuadra"] is True  # 500.000 + 900.000 - 400.000 + 1.000
    assert s["fecha_corte"] == "2026-09-30"
    movs, _ = c._parse_nu(CUENTA, "2026")
    assert not [m for m in movs if "dinero al inicio" in m["descripcion"].lower()]


def test_caso6_resumen_de_la_factura_anterior_es_un_solo_pago_de_lo_abonado():
    movs, _ = c._parse_nu(TARJETA, "2026")
    assert not [m for m in movs if m["monto"] == 150000.0]  # no hay «gasto» de A - B
    pago = next(m for m in movs if m.get("resumen_factura"))
    assert pago["monto"] == 250000.0 and pago["tipo"] == "income" and pago["fecha"] == "2026-10-05"
    assert pago["resumen_factura"] == {"factura_anterior": 400000.0, "pagado": 250000.0, "saldo_pendiente": 150000.0}
    assert pago["pista"] == MARCA_TRASLADO_PROPIO and pago["pago_tarjeta"] is True
    assert "lectura_dudosa" not in pago


def test_caso6_cobro_por_cuota_cuenta_el_monto_una_vez():
    movs, _ = c._parse_nu(TARJETA, "2026")
    cobro = next(m for m in movs if m["descripcion"] == "Cobro por cuota")
    assert cobro["monto"] == 7000.0 and cobro["tipo"] == "expense" and "lectura_dudosa" not in cobro
    assert c.limpiar_descripcion_cobro("2026 Cobro por cuota $7.000,00 - $7.000,00 -", 7000.0) == "Cobro por cuota"


def test_caso6_dos_montos_que_no_cuadran_se_marcan_dudosos_con_ambas_cifras():
    texto = TARJETA.replace("-$150.000,00", "-$100.000,00")  # 400.000 - 250.000 != 100.000
    movs, _ = c._parse_nu(texto, "2026")
    d = next(m for m in movs if m["descripcion"].startswith("Pago"))
    assert d["lectura_dudosa"] is True and d["montos_alternativos"] == [400000.0, 250000.0]
    assert "resumen_factura" not in d


def test_caso6_la_tarjeta_no_inventa_saldos_de_cuenta():
    s = cx.leer_saldos_extracto(
        "Nu Colombia\nTarjeta de crédito\nFecha de corte 14 oct 2026\nTotal a pagar $600.000,00\nPago mínimo $60.000,00\n",
        es_credito=True)
    assert s["saldo_final"] == -600000.0 and "saldo_cuenta_principal" not in s
