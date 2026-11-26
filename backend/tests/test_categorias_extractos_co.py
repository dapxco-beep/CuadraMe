"""Categorías que se sugieren para movimientos de extractos reales de bancos colombianos (Bancolombia, BBVA, Caja Social,
Davivienda). Las descripciones tienen la forma que imprime cada banco (cortadas a 20 letras, con palabras pegadas…) pero solo
con nombres de comercios públicos: nada de personas ni cuentas.

Salieron de revisar ~2.600 movimientos de extractos modelo: antes el diccionario no reconocía el 46 % y, de lo que sí
reconocía, había errores de precisión (el canal «INTERNET» mandaba cosas a Hogar, un cajero dentro de un Cafam salía como Salud).
"""
import pytest

from app.autocat import decidir_categoria
from app.comercios_conocidos import clasificar_por_diccionario
from app.contabilidad import es_pago_tarjeta
from app.costos_financieros import clasificar_costo


def cat(desc: str) -> str | None:
    r = clasificar_por_diccionario(desc)
    return r["categoria"] if r else None


# ── Cobros y rendimientos del banco: categorías de sistema ──
@pytest.mark.parametrize("desc,esperada,tipo", [
    ("IMPTO GOBIERNO 4X1000", "4x1000 (GMF)", "expense"),
    ("CXC IMPTO GOBIERNO 4X1000", "4x1000 (GMF)", "expense"),
    ("CARGO POR IMPUESTO 4X1.000", "4x1000 (GMF)", "expense"),
    ("IMP/TRANS FINANC/ACUM MES", "4x1000 (GMF)", "expense"),
    ("REV IMPTO GOBIERNO 4X1000", "4x1000 (GMF)", "income"),  # el reverso devuelve la plata
    ("MANEJO TARJETA DEB", "Cuota de manejo", "expense"),
    ("C MANEJO TARJ DEB", "Cuota de manejo", "expense"),
    ("CUOTA DE MANEJO TD NOV-2025", "Cuota de manejo", "expense"),
    ("MORA TARJETA AMEX PESOS", "Intereses de tarjeta", "expense"),
    ("INTERES INV VIRT", "Rendimientos", "income"),
    ("PAGO DE INTERES GENERADO", "Rendimientos", "income"),
    ("ABONO INTERESES AHORROS", "Rendimientos", "income"),
    ("COMIS SWIFT GIRO VTA", "Comisiones y seguros", "expense"),
    ("RETIRO CAJERO AJENO", "Comisiones y seguros", "expense"),  # el cobro por cajero de otra red SÍ es un costo
])
def test_cobros_y_rendimientos_del_banco(desc, esperada, tipo):
    r = clasificar_costo(desc)
    assert r and r["categoria"] == esperada and r["tipo"] == tipo


def test_un_comercio_llamado_comisiones_no_es_un_cobro():
    assert clasificar_costo("COMPRA EN COMISIONES EXPRESS") is None


# ── Efectivo y movimientos propios ──
@pytest.mark.parametrize("desc,esperada", [
    ("RETIRO EN CAJERO BBVA A8131 PUENTE LARGO", "Efectivo"),
    ("RETIRO EN CAJERO AUTOMATICO", "Efectivo"),
    ("RETIRO RED PROPIA CC SANTA FE", "Efectivo"),
    ("RETIRO ATM DAVI BTA OCCA", "Efectivo"),
    ("Transferencia de dinero a bolsillo", "Transferencias"),
    ("Abono De Bolsillo A Cuenta", "Transferencias"),
    ("TRASLADO DESDE BOLSILLO", "Transferencias"),
    ("RECIBIDO DE CUENTA DEBITO AUTOMATICO", "Transferencias"),
    ("Rec.Inter TFR FR-16350501", "Transferencias"),
    ("APERTURA INV VIRTUAL APP", "Ahorro e inversión"),
])
def test_efectivo_y_movimientos_propios(desc, esperada):
    assert cat(desc) == esperada


def test_un_cajero_dentro_de_un_comercio_no_cambia_la_categoria_del_retiro():
    # Antes salía como Salud por la palabra «cafam» (solo era el lugar del cajero).
    assert cat("RETIRO EN CAJERO BBVA A8131 CAFAM FLORESTA") == "Efectivo"
    assert cat("COMPRA EN CAFAM FLORESTA") == "Salud"  # la compra en el comercio sigue igual


def test_internet_como_canal_no_es_el_servicio_del_hogar():
    # En Caja Social «INTERNET» es el CANAL de la operación, no el pago del internet de la casa.
    for desc in ("COMPRA INTERNET", "DEBITO POR RECAUDO INTERNET", "ENVIADO HACIA CUENTA INTERNET"):
        assert cat(desc) != "Hogar", desc
    assert cat("PAGO INTERNET HOGAR") == "Hogar"
    assert cat("PLAN DE INTERNET") == "Hogar"
    assert cat("PAGO CLARO") == "Hogar"


# ── Ingresos ──
@pytest.mark.parametrize("desc,esperada", [
    ("PAGO DE PROV COMESTIBLES EL SOL", "Ingresos"),
    ("PAGO DE NOMI EMPRESA EJEMPLO", "Ingresos"),
    ("PAGO INTERBANC DLOCAL COLOMBIA", "Ingresos"),
    ("DEPOSITO IDM 8018 251201", "Ingresos"),
    ("CONSIG LOCAL EFECTIVO FRIGORIFICOS", "Ingresos"),
    ("ABONO DOMI EMPRESA EJEMPLO", "Ingresos"),
    ("Deposito Efectivocon Volante Oficina", "Ingresos"),
    ("CREDITO RECIBIDO ACH", "Transferencias"),
])
def test_ingresos_y_transferencias_que_entran(desc, esperada):
    assert cat(desc) == esperada


def test_un_gasto_nunca_queda_como_ingresos():
    # Una compra de Caja Social cuyo detalle dice «Pago factura hogar» disparaba «pago factura» -> Ingresos.
    desc = "COMPRA INTERNET · Pago factura hogar - Multiplay"
    r = decidir_categoria(desc, [], {"total": 0, "tokens": {}, "cats": {}, "cat_tipo": {}}, {"ingresos", "otros", "hogar"},
                          contexto={"tipo": "expense", "monto": 80000})
    assert r is None or r["categoria"] != "Ingresos"


# ── Comercios: nombres cortados a 20 letras, comida y marcas internacionales ──
@pytest.mark.parametrize("desc,esperada", [
    ("COMPRA EN SUPERM AUT", "Comida"),
    ("COMPRA EN SUPERTIEND", "Comida"),
    ("COMPRA EN TIENDAS AR", "Comida"),
    ("COMPRA EN CORRAL GOU", "Comida"),
    ("COMPRA EN HAMBURGUES", "Comida"),
    ("COMPRA EN MADAMIA TORTAS TO", "Comida"),
    ("COMPRA EN HORNITOS CAL", "Comida"),
    ("COMPRA INTL DOORDASHBURGERKIN", "Comida"),
    ("COMPRA INTL MCDONALD S", "Comida"),
    ("COMPRA INTL COSTCO WHOLESALE", "Comida"),
    ("COMPRA EN CAC DROG N", "Salud"),
    ("COMPRA INTL SHOPPERS DRUG MART", "Salud"),
    ("COMPRA EN EDS TERPEL", "Transporte"),
    ("COMPRA EN CITY PARKI", "Transporte"),
    ("COMPRA INTL MARSHALLS", "Compras"),
    ("COMPRA EN CINEPOLIS", "Ocio"),
    ("COMPRA INTL FIGMA", "Suscripciones"),
    ("COMPRA EN LICEO SAN", "Educación"),
    ("PAGO PLAN PROTEGE TU VIDA CAJICA", "Seguros"),
    ("COMPRA EN COMCEL CAV", "Hogar"),
    ("COMPRA EN CASAIDEAS", "Hogar"),
])
def test_comercios_de_extractos_reales(desc, esperada):
    assert cat(desc) == esperada


# ── Davivienda pega las palabras: «COMPRAEXITOOCCIDENTE» ──
@pytest.mark.parametrize("desc,esperada", [
    ("Compra EXITOOCCIDENTE", "Comida"),
    ("Compra JUMBOCARRERA30", "Comida"),
    ("Compra FARMATODOHAYUELOS", "Salud"),
    ("Compra STARBUCKSTITANPLAZA", "Comida"),
    ("Compra ALKOSTOAVX68", "Compras"),
])
def test_nombres_pegados_se_reconocen_con_menos_confianza(desc, esperada):
    r = clasificar_por_diccionario(desc)
    assert r and r["categoria"] == esperada
    assert r["confianza"] <= 0.6  # la persona lo confirma: no es tan seguro como una palabra suelta


def test_un_nombre_pegado_no_se_activa_por_una_palabra_corta():
    # 'ara' (3 letras) no debe activarse dentro de 'arandanos'.
    assert cat("Compra ARANDANOSLOCOS") is None


def test_estaciones_eds_pegadas_se_reconocen_por_prefijo():
    assert cat("Compra EDSENGATIVAFR") == "Transporte"
    assert cat("Compra EDSCLL80") == "Transporte"


# ── Pagos de tarjeta ──
def test_pago_de_tarjeta_desde_la_sucursal_virtual():
    assert es_pago_tarjeta("PAGO SUC VIRT TC")
    assert es_pago_tarjeta("PAGO TARJETA DE CREDITO")
    assert not es_pago_tarjeta("PAGO PSE SUPERMERCADO EXITO")


# ── El modelo aprendido no se llena de ruido bancario ──
def test_el_modelo_ignora_el_canal_y_la_operacion_del_banco():
    from app.classifier import tokenize
    for ruido in ("intl", "internet", "ach", "tfr", "impto", "gobierno"):
        assert ruido not in tokenize(f"COMPRA {ruido.upper()} TIENDA EJEMPLO ZIPAQUIRA")
    assert "ejemplo" in tokenize("COMPRA INTL TIENDA EJEMPLO")
