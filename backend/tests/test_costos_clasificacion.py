"""Clasificación de cobros y rendimientos bancarios por patrón de línea (datos SINTÉTICOS)."""
import pytest

from app.comercios_conocidos import clasificar_por_diccionario
from app.contabilidad import tipos_efectivos
from app.costos_financieros import (
    CAT_COMISIONES, CAT_CUOTA, CAT_GMF, CAT_INTERESES, CAT_RENDIMIENTOS, bucket_de, clasificar_costo,
)

CASOS = [
    # Nu
    ("Intereses ganados", CAT_RENDIMIENTOS, "income"),
    ("Rendimientos cajita Nu", CAT_RENDIMIENTOS, "income"),
    ("Intereses cajita", CAT_RENDIMIENTOS, "income"),
    ("INTERESES DE COMPRAS", CAT_INTERESES, "expense"),
    ("Intereses de mora", CAT_INTERESES, "expense"),
    # Nequi
    ("Rendimientos bolsillo Nequi", CAT_RENDIMIENTOS, "income"),
    ("IMPUESTO 4X1000", CAT_GMF, "expense"),
    ("Costo transacción Nequi", CAT_COMISIONES, "expense"),
    # Bancolombia
    ("ABONO INTERESES AHORROS", CAT_RENDIMIENTOS, "income"),
    ("CUOTA MANEJO TARJETA DEB", CAT_CUOTA, "expense"),
    ("IVA CUOTA DE MANEJO", CAT_CUOTA, "expense"),
    ("COBRO IVA COMISION", CAT_COMISIONES, "expense"),
    ("RETIRO CAJERO AJENO", CAT_COMISIONES, "expense"),
    ("GRAVAMEN MOVIMIENTOS FINANCIEROS", CAT_GMF, "expense"),
    # Davivienda
    ("Interés cuenta de ahorros", CAT_RENDIMIENTOS, "income"),
    ("INTERESES CORRIENTES", CAT_INTERESES, "expense"),
    ("Seguro deudores", CAT_COMISIONES, "expense"),
    ("Cobro seguro de vida tarjeta", CAT_COMISIONES, "expense"),
    # BBVA
    ("Intereses de corriente", CAT_INTERESES, "expense"),
    ("Cuota de manejo", CAT_CUOTA, "expense"),
    ("4 por mil", CAT_GMF, "expense"),
    ("Rendimiento CDT", CAT_RENDIMIENTOS, "income"),
    # Daviplata
    ("Gravamen al Movimiento", CAT_GMF, "expense"),
    ("Cuota de administración tarjeta", CAT_COMISIONES, "expense"),
    ("Devolución GMF", CAT_GMF, "income"),
]


@pytest.mark.parametrize("linea,cat,tipo", CASOS)
def test_lineas_de_extracto(linea, cat, tipo):
    r = clasificar_por_diccionario(linea)
    assert r and r["categoria"] == cat and r["tipo"] == tipo


@pytest.mark.parametrize("linea", [
    "Comisiones Express", "SEGUROS BOLIVAR", "Cena con intereses comunes", "Pago de administración conjunto",
    "Cuota de administración Conjunto Los Pinos", "Seguro de vida Sura", "Compra en Cobro Cafe",
    "Comisiones ganadas",
])
def test_no_confunde_comercios(linea):
    r = clasificar_costo(linea)
    assert r is None, linea


def test_sin_tildes_ni_mayusculas():
    assert clasificar_costo("INTERÉS MORA")["categoria"] == CAT_INTERESES
    assert clasificar_costo("interes mora")["categoria"] == CAT_INTERESES


def test_bucket_respeta_categoria_guardada_y_la_antigua():
    assert bucket_de(CAT_GMF) == "gmf"
    assert bucket_de("Comisiones y costos financieros", "CUOTA DE MANEJO") == "cuota"
    assert bucket_de("Comisiones y costos financieros", "AVANCE EN EFECTIVO") == "comisiones"
    assert bucket_de("Comida", "Comisiones") is None


def test_no_se_marcan_como_traslado():
    from datetime import datetime
    f = datetime(2026, 9, 5)
    movs = [
        {"id": "1", "cuenta_id": "a", "tipo": "expense", "monto": 12000, "fecha": f, "descripcion": "Costo transacción Nequi", "categoria": CAT_COMISIONES, "notas": ""},
        {"id": "2", "cuenta_id": "b", "tipo": "income", "monto": 12000, "fecha": f, "descripcion": "Rendimientos Nequi", "categoria": CAT_RENDIMIENTOS, "notas": ""},
    ]
    assert tipos_efectivos(movs) == {"1": "expense", "2": "income"}


def test_lector_nequi_no_marca_traslado_en_rendimientos():
    from app.conciliacion import _pista
    assert _pista("Rendimientos Nequi desde bolsillo") == {}
