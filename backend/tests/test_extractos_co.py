"""Lectores de extractos de bancos colombianos (app/extractos_co.py).

Los textos son SINTÉTICOS: inventados con la misma estructura que imprime cada banco (nombres, cuentas y cifras de mentira).
Cada formato se prueba por: reconocerse por su encabezado (no por un «NEQUI» suelto en un movimiento), leer fechas, signos y
descripciones, y cuadrar con los totales que imprime el propio extracto.
"""
from app import conciliacion, extractos_co
from app.cuadre_extracto import cadena_coincide, leer_saldos_extracto

# ── Davivienda «Informe del mes»: palabras pegadas, signo al final, sin año en cada fila ──
DAVIVIENDA = """H.01
CUENTA DE AHORROS
000000000000
INFORMEDELMES:MARZO/2026
ApreciadoCliente
TITULARDEPRUEBA
SaldoAnterior $1,000,000.00
MásCréditos $500,000.00
MenosDébitos $350,000.00
NuevoSaldo $1,150,000.00
EXTRACTOCUENTADEAHORROS
Fecha Valor Doc. ClasedeMovimiento Oficina
01 03 $120,000.00- 8151 CompraTIENDAEJEMPLO FRANQUICIAMASTERCARD
02 03 $200,000.00- 3258 TransferenciaenviadaaNequi AppDavivienda
05 03 $500,000.00+ 1113 AbonoPorTransferenciaDeFondos5501089000707579014853652 PORTALPYMES
TRANSFERENCIATERCEROS
Esteproductocuentaconsegurodedepósitos
CUENTA DE AHORROS
Fecha Valor Doc. ClasedeMovimiento Oficina
10 03 $30,000.00- 4758 RetiroenCajeroAutomatico. CENTROCIALEJEMPLO
BancoDaviviendaS.ANIT.000.000.000-0
"""

# ── Bancolombia «Estado de cuenta»: D/MM, valor con signo, dos periodos que cruzan de año ──
BANCOLOMBIA_ESTADO = """ESTADO DE CUENTA
DESDE: 2025/12/31 HASTA: 2026/03/31
CUENTA DE AHORROS
TITULAR DE PRUEBA
NÚMERO 00000000000
RESUMEN
SALDO ANTERIOR $ 1,000,000.00 SALDO PROMEDIO $ 500,000
TOTAL ABONOS $ 800,000.50 CUENTAS X COBRAR $ .00
TOTAL CARGOS $ 600,000.00 VALOR INTERESES PAGADOS $ 3.50
SALDO ACTUAL $ 1,200,000.50 RETEFUENTE $ .00
FECHA DESCRIPCIÓN SUCURSAL DCTO. VALOR SALDO
31/12 PAGO DE PROV EMPRESA EJEMPLO 800,000.00 1,800,000.00
5/01 TRANSFERENCIAS A NEQUI -550,000.00 1,250,000.00
6/01 ABONO INTERESES AHORROS .50 1,250,000.50
PÁGINA: 1
ESTADO DE CUENTA
DESDE: 2025/12/31 HASTA: 2026/03/31
FECHA DESCRIPCIÓN SUCURSAL DCTO. VALOR SALDO
6/03 COMPRA EN TIENDA EJEMPLO -50,000.00 1,200,000.50
DCF:defensor@bancolombia.com.co
"""

BANCOLOMBIA_SUCURSAL = """Sucursal Virtual Personas Lunes, 24 de agosto de 2026, 1:55 p. m.
TITULAR DE PRUEBA
Movimientos: Cuentas
Cuenta de Ahorros
Ahorros 000 - 000000 - 00
Fecha Descripción Referencia Valor
16 ago 2026 ABONO INTERESES AHORROS $ 59,51
16 ago 2026 TRANSFERENCIAS A NEQUI -$ 15.000,00
16 ago 2026 PAGO PSE EMPRESA 570996936 -$ 323.010,00
27607893973
15 ago 2026 CANCELA INV VIRT $ 110.000.000,00
Dirección IP 000.00.00.00
"""

CAJA_SOCIAL = """Banco Caja Social
www.bancocajasocial.com
Periodo del Informe
Cuentamiga 1 de Marzo a 31 de Marzo de 2026
Saldo Anterior Más Créditos y Depósitos Menos Débitos y Retiros Intereses del Periodo Nuevo Saldo
100,000.00 500,000.00 -150,000.00 0.00 450,000.00
Detalle de productos
Fecha Transacción Documento Lugar Débitos Créditos Saldos
MAR 02 TRANSFERENCIA OTRA ENTIDA 91240256 ACH 500,000.00 600,000.00
000000052214913 TRANSFER xyz
MAR 05 COMPRA INTERNET 6332430 INTERNET 100,000.00 500,000.00
5259037954 Pago de factura Postpago
MAR 06 DEBITO POR RECAUDO INTERNET 50,000.00 450,000.00
"""

# Dos meses; el segundo NO arranca donde terminó el primero: falta un extracto en el PDF
BBVA = """BANCO BBVA COLOMBIA
PERÍODO DESDE: 01-11-2025 HASTA: 30-11-2025
SALDO CIERRE MES ANTERIOR 1,000,000.00 - IVA 1 100.00
+ ABONOS 1 500,000.00 - 4 POR MIL 2 600.00
- CARGOS 2 299,300.00 - RETENCIONES 0.00
- INTERESES PAGADOS DE SOBREGIRO SALDO FINAL 1,200,600.00
13686 01-11-2025 04-11-2025 CARGO POR IMPUESTO 4X1.000 400.00 999,600.00
13687 01-11-2025 04-11-2025 COMPRA EN TIENDA EJEMPLO 99,000.00 900,600.00
13688 05-11-2025 05-11-2025 ABONO NOMINA EMPRESA 500,000.00 1,400,600.00
13689 10-11-2025 10-11-2025 COMPRA EN OTRA TIENDA 200,000.00 1,200,600.00
PERÍODO DESDE: 01-02-2026 HASTA: 28-02-2026
SALDO CIERRE MES ANTERIOR 1,500,000.00 - IVA 0 0.00
+ ABONOS 0 0.00 - 4 POR MIL 1 400.00
- CARGOS 1 100,000.00 - RETENCIONES 0.00
- INTERESES PAGADOS DE SOBREGIRO SALDO FINAL 1,399,600.00
14000 03-02-2026 04-02-2026 COMPRA EN TIENDA EJEMPLO 100,000.00 1,400,000.00
14001 03-02-2026 04-02-2026 CARGO POR IMPUESTO 4X1.000 400.00 1,399,600.00
"""

DAVIBANK = """CUENTA DE AHORROS
No 0000000000
RESUMEN CUENTA AHORROS
SALDO ANTERIOR DEPOSITOS Y OTROS CREDITOS RETIROS Y OTROS DEBITOS NUEVO SALDO
100.000,00 800.011,00 351.000,00 549.011,00
DETALLE DE CUENTA
FECHA OFICINA No DOCUM DESCRIPCION MONTO SALDO
1/12/2025 CENTRAL DE C Pago por PSE -20.000,00 80.000,00
Recarga Nequi PSE
1/12/2025 CENTRAL DE C CREDITO RECIBIDO ACH 800.000,00 880.000,00
3/12/2025 CENTRAL DE C Pago por PSE -300.000,00 580.000,00
31/12/2025 BOGOTA CENTR PAGO DE INTERES GENERADO 9,00 580.009,00
31/12/2025 BOGOTA CENTR PAGO DE INTERES GENERADO 1,00 580.010,00
31/12/2025 BOGOTA CENTR PAGO DE INTERES GENERADO 1,00 580.011,00
IMP/TRANS FINANC/ACUM MES -31.000,00 549.011,00
"""


def _tipos(l):
    return [(m["fecha"], m["tipo"], m["monto"]) for m in l["movimientos"]]


# ── Detección: el encabezado manda, no un «Nequi» suelto entre los movimientos ──
def test_cada_formato_se_reconoce_por_su_encabezado():
    esperado = {
        "davivienda_informe": (DAVIVIENDA, "davivienda"), "bancolombia_estado": (BANCOLOMBIA_ESTADO, "bancolombia"),
        "bancolombia_sucursal": (BANCOLOMBIA_SUCURSAL, "bancolombia"), "cajasocial": (CAJA_SOCIAL, "cajasocial"),
        "bbva_cuenta": (BBVA, "bbva"), "davibank": (DAVIBANK, "davivienda"),
    }
    for formato, (texto, banco) in esperado.items():
        assert extractos_co.detectar_formato(texto) == formato, formato
        assert conciliacion.detectar_banco(texto) == banco, formato  # antes varios salían como «nequi»


def test_un_texto_cualquiera_no_se_toma_por_uno_de_estos_formatos():
    assert extractos_co.detectar_formato("") is None
    assert extractos_co.detectar_formato("Factura de servicios públicos\nTotal a pagar $120.000") is None
    assert extractos_co.leer("Hola, esto no es un extracto") is None


# ── Davivienda ──
def test_davivienda_lee_signos_fechas_y_descripciones_y_cuadra():
    l = extractos_co.leer(DAVIVIENDA)
    assert _tipos(l) == [
        ("2026-03-01", "expense", 120000.0), ("2026-03-02", "expense", 200000.0),
        ("2026-03-05", "income", 500000.0), ("2026-03-10", "expense", 30000.0),
    ]
    assert l["movimientos"][0]["descripcion"] == "Compra TIENDAEJEMPLO"
    assert l["movimientos"][1]["descripcion"] == "Transferencia enviada a Nequi"
    assert l["movimientos"][3]["descripcion"].startswith("Retiro en cajero")
    assert l["saldo_inicial"] == 1000000.0 and l["saldo_final"] == 1150000.0
    assert l["lectura_completa"] is True
    assert l["periodo_inicio"] == "2026-03-01" and l["periodo_fin"] == "2026-03-31"


def test_davivienda_si_falta_una_fila_avisa_que_no_cuadra():
    sin_una = DAVIVIENDA.replace("02 03 $200,000.00- 3258 TransferenciaenviadaaNequi AppDavivienda\n", "")
    movs, descartados = conciliacion.parse_texto_con_regex(sin_una)
    assert len(movs) == 3 and descartados == 1  # el aviso de «puede faltar algo», en vez de importar a ciegas
    assert extractos_co.leer(sin_una)["lectura_completa"] is False


def test_davivienda_informe_de_enero_con_un_movimiento_de_diciembre():
    texto = DAVIVIENDA.replace("MARZO/2026", "ENERO/2026").replace("01 03 ", "30 12 ")
    assert extractos_co.leer(texto)["movimientos"][0]["fecha"] == "2025-12-30"


# ── Bancolombia ──
def test_bancolombia_estado_resuelve_el_año_en_un_periodo_que_cruza_de_año():
    l = extractos_co.leer(BANCOLOMBIA_ESTADO)
    assert _tipos(l) == [
        ("2025-12-31", "income", 800000.0), ("2026-01-05", "expense", 550000.0),
        ("2026-01-06", "income", 0.5), ("2026-03-06", "expense", 50000.0),
    ]
    assert l["lectura_completa"] is True
    assert (l["saldo_inicial"], l["saldo_final"]) == (1000000.0, 1200000.5)
    assert conciliacion.detectar_banco(BANCOLOMBIA_ESTADO) == "bancolombia"  # «TRANSFERENCIAS A NEQUI» no lo cambia


def test_bancolombia_estado_con_dos_extractos_suma_los_dos_resumenes():
    segundo = """ESTADO DE CUENTA
DESDE: 2026/03/31 HASTA: 2026/06/30
RESUMEN
SALDO ANTERIOR $ 1,200,000.50 SALDO PROMEDIO $ 1
TOTAL ABONOS $ 100,000.00 CUENTAS X COBRAR $ .00
TOTAL CARGOS $ 20,000.00 VALOR INTERESES PAGADOS $ 1
SALDO ACTUAL $ 1,280,000.50 RETEFUENTE $ .00
FECHA DESCRIPCIÓN SUCURSAL DCTO. VALOR SALDO
2/04 ABONO POR PAGO 100,000.00 1,300,000.50
3/04 COMPRA EN TIENDA -20,000.00 1,280,000.50
"""
    l = extractos_co.leer(BANCOLOMBIA_ESTADO + segundo)
    assert len(l["movimientos"]) == 6 and l["lectura_completa"] is True
    assert l["movimientos"][-1]["fecha"] == "2026-04-03"
    assert l["saldo_final"] == 1280000.5 and l["periodo_fin"] == "2026-06-30"


def test_bancolombia_sucursal_lee_numeros_en_español_y_signos():
    l = extractos_co.leer(BANCOLOMBIA_SUCURSAL)
    assert _tipos(l) == [
        ("2026-08-16", "income", 59.51), ("2026-08-16", "expense", 15000.0),
        ("2026-08-16", "expense", 323010.0), ("2026-08-15", "income", 110000000.0),
    ]
    assert l["lectura_completa"] is None  # esta vista no trae totales: no se puede comprobar, y se dice


# ── Caja Social ──
def test_caja_social_decide_entrada_o_salida_con_los_saldos_del_banco():
    l = extractos_co.leer(CAJA_SOCIAL)
    assert _tipos(l) == [("2026-03-02", "income", 500000.0), ("2026-03-05", "expense", 100000.0), ("2026-03-06", "expense", 50000.0)]
    assert l["lectura_completa"] is True
    assert (l["saldo_inicial"], l["saldo_final"]) == (100000.0, 450000.0)
    # sin el número de documento ni el «lugar» (INTERNET, ACH), y con el detalle que el banco imprime debajo
    assert l["movimientos"][0]["descripcion"] == "TRANSFERENCIA OTRA ENTIDA"
    assert l["movimientos"][1]["descripcion"] == "COMPRA INTERNET · Pago de factura Postpago"


# ── BBVA ──
def test_bbva_se_verifica_con_el_saldo_final_de_cada_mes_y_detecta_un_mes_que_falta():
    l = extractos_co.leer(BBVA)
    assert len(l["movimientos"]) == 6
    assert l["movimientos"][0]["fecha"] == "2025-11-01"
    assert [m["tipo"] for m in l["movimientos"][:4]] == ["expense", "expense", "income", "expense"]
    assert l["lectura_completa"] is True  # cada mes termina exactamente en su SALDO FINAL
    assert l["huecos"] == 1  # el saldo inicial de febrero no es el final de noviembre: falta un extracto


def test_bbva_una_devolucion_no_rompe_la_verificacion():
    # El banco resta las devoluciones de «cargos» en vez de listarlas como abono: por eso se verifica con la cadena de saldos.
    texto = BBVA.replace("14001 03-02-2026 04-02-2026 CARGO POR IMPUESTO 4X1.000 400.00 1,399,600.00",
                         "14001 03-02-2026 04-02-2026 DEVOLUCION COMPRA 4,000.00 1,404,000.00").replace("SALDO FINAL 1,399,600.00", "SALDO FINAL 1,404,000.00")
    l = extractos_co.leer(texto)
    assert l["movimientos"][-1]["tipo"] == "income" and l["lectura_completa"] is True


# ── Davibank ──
def test_davibank_lee_la_fila_de_fin_de_mes_sin_fecha_y_cuadra():
    l = extractos_co.leer(DAVIBANK)
    assert len(l["movimientos"]) == 7
    assert [m["tipo"] for m in l["movimientos"]][:5] == ["expense", "income", "expense", "income", "income"]
    assert l["movimientos"][-1]["fecha"] == "2025-12-31"  # la fila sin fecha lleva la de la anterior
    assert l["movimientos"][0]["descripcion"] == "Pago por PSE · Recarga Nequi PSE"  # sin la columna «oficina», con el detalle de la línea de abajo
    assert l["movimientos"][3]["descripcion"] == "PAGO DE INTERES GENERADO"  # otra oficina («BOGOTA CENTR») tampoco queda pegada
    assert l["lectura_completa"] is True
    assert (l["saldo_inicial"], l["saldo_final"]) == (100000.0, 549011.0)


# ── Integración con el resto de la app ──
def test_parse_texto_con_regex_usa_el_lector_y_marca_la_pista_de_traslado():
    for texto in (DAVIVIENDA, BANCOLOMBIA_ESTADO, CAJA_SOCIAL, BBVA, DAVIBANK, BANCOLOMBIA_SUCURSAL):
        movs, descartados = conciliacion.parse_texto_con_regex(texto)
        assert movs and descartados == 0
        assert all(m["tipo"] in ("income", "expense") and m["monto"] > 0 for m in movs)


def test_los_saldos_del_cuadre_salen_del_lector_y_la_cadena_cierra():
    for texto in (DAVIVIENDA, BANCOLOMBIA_ESTADO, CAJA_SOCIAL, DAVIBANK):
        saldos = leer_saldos_extracto(texto)
        assert saldos["saldo_inicial"] is not None and saldos["saldo_final"] is not None
        movs, _ = conciliacion.parse_texto_con_regex(texto)
        assert cadena_coincide(saldos, movs) is True
    # BBVA con un mes faltante: la cadena global NO cierra, y eso es verdad (el PDF no trae todo)
    saldos = leer_saldos_extracto(BBVA)
    movs, _ = conciliacion.parse_texto_con_regex(BBVA)
    assert cadena_coincide(saldos, movs) is False


def test_extractos_de_nequi_y_nu_siguen_leyéndose_por_su_camino():
    nequi = "Extracto de depósito de bajo monto\nFecha Descripción Valor Saldo\n05/10/2026 Enviaste a Maria $-8,200.00 $50,000.00\n"
    assert conciliacion.detectar_banco(nequi) == "nequi"
    assert extractos_co.detectar_formato(nequi) is None
