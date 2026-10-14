"""Lector de extractos de tarjeta de crédito. IMPORTANTE: los textos son INVENTADOS
(realistas pero no copiados de extractos reales de ningún banco); validan la lógica,
no garantizan el formato exacto de cada banco."""
from types import SimpleNamespace

import pytest

from app.extracto_tarjeta import _a_numero, leer_datos_tarjeta, proponer_actualizacion

# Formato 1: correo estilo "neobanco": etiquetas con dos puntos, fechas en palabras.
CORREO_NU = """
Llegó el extracto de tu tarjeta de crédito Nu
Hola Daniel, este es el resumen de tu extracto:

Cupo total: $5.000.000
Cupo disponible: $3.120.500
Pago total: $1.879.500
Pago mínimo: $187.950
Fecha límite de pago: 30 de octubre de 2026
Fecha de corte: 15 de octubre de 2026
Tasa efectiva anual: 27,86% E.A.
"""

# Formato 2: texto de PDF en MAYÚSCULAS, sin tildes, columnas separadas por espacios,
# decimales con coma y fechas dd/mm/aaaa.
PDF_BANCOLOMBIA = """
EXTRACTO TARJETA DE CREDITO VISA          PAGINA 1 DE 3
CUPO TOTAL                       $ 8.000.000,00
CUPO DISPONIBLE                  $ 2.350.000,00
PAGO MINIMO                      $ 310.450,00
PAGO TOTAL                       $ 5.650.000,00
FECHA LIMITE DE PAGO             05/11/2026
FECHA DE CORTE                   20/10/2026
TASA EFECTIVA ANUAL              29,41 %
"""

# Formato 3: otro vocabulario (cupo aprobado, valor total a pagar, pague hasta...),
# fecha con mes abreviado y tasa con punto decimal.
PDF_DAVIVIENDA = """
Davivienda - Extracto Tarjeta Crédito Mastercard
Cupo autorizado: $12.000.000
Disponible para compras: $9.400.000
Valor total a pagar: $2.600.000
Valor mínimo a pagar: $260.000
Pague hasta: 12-nov-2026
Fecha de cierre: 27 oct 2026
Tasa de interés efectiva anual (E.A.): 28.10%
"""


def test_formato_correo_con_etiquetas_y_fechas_en_palabras():
    d = leer_datos_tarjeta(CORREO_NU)
    assert d == {
        "cupo_total": 5_000_000, "cupo_disponible": 3_120_500, "pago_total": 1_879_500, "pago_minimo": 187_950,
        "fecha_limite_pago": "2026-10-30", "dia_pago": 30, "fecha_corte": "2026-10-15", "dia_corte": 15,
        "tasa_ea": 27.86,
    }


def test_formato_pdf_en_mayusculas_sin_tildes_y_decimales_con_coma():
    d = leer_datos_tarjeta(PDF_BANCOLOMBIA)
    assert d["cupo_total"] == 8_000_000 and d["cupo_disponible"] == 2_350_000
    assert d["pago_minimo"] == 310_450 and d["pago_total"] == 5_650_000
    assert d["fecha_limite_pago"] == "2026-11-05" and d["dia_pago"] == 5
    assert d["fecha_corte"] == "2026-10-20" and d["dia_corte"] == 20
    assert d["tasa_ea"] == 29.41


def test_formato_con_otro_vocabulario_y_mes_abreviado():
    d = leer_datos_tarjeta(PDF_DAVIVIENDA)
    assert d["cupo_total"] == 12_000_000 and d["cupo_disponible"] == 9_400_000
    assert d["pago_total"] == 2_600_000 and d["pago_minimo"] == 260_000
    assert d["fecha_limite_pago"] == "2026-11-12" and d["dia_pago"] == 12
    assert d["fecha_corte"] == "2026-10-27" and d["dia_corte"] == 27
    assert d["tasa_ea"] == 28.10


def test_devuelve_solo_lo_que_encuentra():
    d = leer_datos_tarjeta("Tu extracto está listo.\nPago mínimo: $50.000\nGracias por usar tu tarjeta.")
    assert d == {"pago_minimo": 50_000}
    assert leer_datos_tarjeta("") == {}
    assert leer_datos_tarjeta("Hola, este correo no trae nada de una tarjeta") == {}


def test_fecha_sin_anio_da_solo_el_dia():
    d = leer_datos_tarjeta("Fecha límite de pago: 30 de octubre\nFecha de corte: 15 oct")
    assert d == {"dia_pago": 30, "dia_corte": 15}


def test_montos_en_formatos_distintos():
    assert leer_datos_tarjeta("Cupo total $ 12'000.000")["cupo_total"] == 12_000_000  # apóstrofo de millones
    assert leer_datos_tarjeta("Cupo total: 5,000,000.00")["cupo_total"] == 5_000_000  # estilo US
    assert leer_datos_tarjeta("Cupo total 4500000")["cupo_total"] == 4_500_000  # sin separadores
    assert leer_datos_tarjeta("Cupo total\n$ 3.000.000")["cupo_total"] == 3_000_000  # valor en la línea siguiente


def test_una_fecha_no_se_lee_como_monto():
    # tras 'pago total' viene una fecha: no hay monto, no se inventa uno
    assert "pago_total" not in leer_datos_tarjeta("Pago total antes del 30 de octubre de 2026")
    assert "pago_total" not in leer_datos_tarjeta("Pago total 30/10/2026")


def test_descarta_datos_incoherentes():
    # pago mínimo mayor que el total y disponible mayor que el cupo: lo dudoso se descarta
    d = leer_datos_tarjeta("Cupo total: $1.000.000\nCupo disponible: $9.000.000\nPago total: $200.000\nPago mínimo: $900.000")
    assert d == {"cupo_total": 1_000_000, "pago_total": 200_000}
    # tasa absurda
    assert "tasa_ea" not in leer_datos_tarjeta("Tasa efectiva anual: 450%")


def test_pago_total_cero_es_valido():
    assert leer_datos_tarjeta("Pago total: $0\nPago mínimo: $0") == {"pago_total": 0, "pago_minimo": 0}


@pytest.mark.parametrize("tok,esperado", [
    ("1.234.567", 1234567), ("1.234.567,89", 1234567.89), ("1,234,567.89", 1234567.89),
    ("5.000", 5000), ("1234,5", 1234.5), ("27.86", 27.86), ("0,5", 0.5),
])
def test_conversion_de_numeros(tok, esperado):
    assert _a_numero(tok) == esperado


# ── propuesta (nunca se aplica sola) ──

def _cuenta(**kw):
    base = dict(cupo_total=4_000_000, dia_corte=15, dia_pago=28, tasa_ea=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_propone_solo_lo_que_cambia_con_el_texto_pedido():
    d = leer_datos_tarjeta(CORREO_NU)
    p = proponer_actualizacion(_cuenta(), d)
    assert p["cambios"] == {"cupo_total": 5_000_000, "dia_pago": 30, "tasa_ea": 27.86}  # el corte 15 ya era igual
    assert p["texto"] == "Tu extracto dice: cupo $5.000.000, pago total $1.879.500, pago mínimo $187.950, vence el 30. ¿Actualizar tu tarjeta?"


def test_si_todo_coincide_igual_informa_pero_sin_cambios():
    d = leer_datos_tarjeta(CORREO_NU)
    p = proponer_actualizacion(_cuenta(cupo_total=5_000_000, dia_corte=15, dia_pago=30, tasa_ea=27.86), d)
    assert p["cambios"] == {} and "pago total" in p["texto"]


def test_sin_datos_no_propone():
    assert proponer_actualizacion(_cuenta(), {}) is None
    assert proponer_actualizacion(_cuenta(), {"tasa_ea": 20.0}) is None  # nada que mostrar en el texto


# ── desglose de costos (campos opcionales) ──────────────────────────────────────────
EXTRACTO_CON_COSTOS = """
EXTRACTO TARJETA DE CREDITO
Cupo total $ 5.000.000
Pago total $ 1.234.500
Pago minimo $ 98.000
Fecha limite de pago 25/11/2026
Fecha de corte 10/11/2026
Intereses corrientes $ 87.400
Intereses de mora $ 0
Cuota de manejo $ 28.900
Comisiones $ 4.500
Seguro deudores $ 12.300
Tasa efectiva anual 27,50% Tasa M.V. 2,04%
"""


def test_lee_el_desglose_de_costos():
    from app.extracto_tarjeta import leer_datos_tarjeta
    d = leer_datos_tarjeta(EXTRACTO_CON_COSTOS)
    assert d["intereses_corrientes"] == 87400 and d["intereses_mora"] == 0
    assert d["cuota_manejo"] == 28900 and d["comisiones"] == 4500 and d["seguros"] == 12300
    assert d["tasa_ea"] == 27.5 and d["tasa_mv"] == 2.04
    assert d["pago_total"] == 1234500  # lo que ya leía sigue igual


def test_sin_desglose_no_inventa_nada():
    from app.extracto_tarjeta import leer_datos_tarjeta
    d = leer_datos_tarjeta("Cupo total $ 5.000.000\nPago total $ 100.000\nPago minimo $ 10.000")
    assert not any(k in d for k in ("intereses_corrientes", "intereses_mora", "cuota_manejo", "comisiones", "seguros", "tasa_mv"))
