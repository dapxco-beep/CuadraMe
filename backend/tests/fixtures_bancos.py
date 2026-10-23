"""Extractos de texto 100 % INVENTADOS de dos bancos que NO son Nu ni Nequi, con formatos de columnas distintos, más un tercero
que ningún lector conoce. Sirven para comprobar que el flujo genérico (lector -> clasificación -> importar -> cuadre) no asume Nu.
Nombres, descripciones y montos son ficticios: ninguna cifra viene de una persona real. No son lectores nuevos: son solo textos.

  Banco Ejemplo A   una línea por movimiento: fecha dd/mm/aaaa, descripción y UN valor con signo (-45.000,00 sale; 45.000,00 entra).
  Banco Ejemplo B   columnas separadas: fecha dd-mm-aaaa, descripción, DÉBITO, CRÉDITO y SALDO (la celda vacía de la columna que no aplica).
  Banco Ejemplo C   un formato sin tabla que ningún lector reconoce (fechas en palabras): debe quedar «aprendiendo» y sin tocar nada."""

# Saldo anterior 1.000.000 + 500.000 - 120.000 - 35.500 - 80.000 = 1.264.500
EJEMPLO_A = """Banco Ejemplo A
Extracto de cuenta de ahorros
Saldo anterior 1.000.000,00
Fecha Descripcion Valor
03/08/2026 Abono Cliente Ficticio Uno 500.000,00
07/08/2026 Compra Tienda Ficticia Alfa -120.000,00
12/08/2026 Compra Panaderia Ficticia -35.500,00
20/08/2026 Pago Servicio Ficticio -80.000,00
Saldo final 1.264.500,00
"""
EJEMPLO_A_ESPERADO = {"saldo_inicial": 1_000_000.0, "saldo_final": 1_264_500.0,
                      "movimientos": [("2026-08-03", "income", 500_000.0), ("2026-08-07", "expense", 120_000.0),
                                      ("2026-08-12", "expense", 35_500.0), ("2026-08-20", "expense", 80_000.0)]}

# Saldo anterior 2.000.000 + 750.000 - 60.000 - 15.250 = 2.674.750
EJEMPLO_B = """Banco Ejemplo B
Extracto de cuenta de ahorros
Movimientos del mes
Saldo anterior 2.000.000,00
Fecha        Descripcion                      Debito        Credito       Saldo
04-09-2026   Consignacion Empresa Ficticia                  750.000,00    2.750.000,00
09-09-2026   Compra Libreria Ficticia         60.000,00                   2.690.000,00
18-09-2026   Retiro Cajero Ficticio           15.250,00                   2.674.750,00
Saldo final 2.674.750,00
"""
EJEMPLO_B_ESPERADO = {"movimientos": [("2026-09-04", "income", 750_000.0), ("2026-09-09", "expense", 60_000.0),
                                      ("2026-09-18", "expense", 15_250.0)]}

# Sin tabla que se pueda leer: tiene señales de extracto (saldo, movimientos, fecha...) pero las fechas van en palabras.
EJEMPLO_C_ILEGIBLE = """Banco Ejemplo C
Extracto de tu cuenta
Movimientos de octubre
El cinco de octubre abonaron quinientos mil pesos por concepto de nomina ficticia
El diez de octubre cargaron cuarenta mil pesos por una compra ficticia
Saldo anterior un millon, saldo final un millon cuatrocientos sesenta mil
Fecha, descripcion y valor se detallan en la pagina siguiente
"""
