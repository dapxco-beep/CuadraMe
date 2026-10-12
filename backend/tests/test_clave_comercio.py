"""Huella de comercio y diccionario de palabras clave (puro, sin base de datos)."""
import pytest

from app.clave_comercio import clave_comercio, es_huella_peligrosa, huella_en_descripcion
from app.comercios_conocidos import clasificar_por_diccionario

HUELLAS = [
    ("PAGO EN VENTO COLIVING 0105", "vento coliving"),
    ("COMPRA VENTO COLIVING BOGOTA", "vento coliving"),
    ("Compra en VENTO COLIVING S.A.S.", "vento coliving"),
    ("COMPRA EN JUAN VALDEZ SKANDIA CON TARJETA DEBITO", "juan valdez skandia"),
    ("Compra en EXITO CHAPINERO 12/03/2025", "exito chapinero"),
    ("PAGO PSE CLARO COLOMBIA S.A.S.", "claro"),
    ("COMPRA EN PAN PA' YA BOGOTA CO", "pan pa ya"),
    ("D1 SUC 4521 MEDELLIN", "d1"),
    ("COMPRA MERCADO LIBRE COLOMBIA 123456789", "mercado libre"),
    ("Compra en Rappi", "rappi"),
    ("RAPPI*PEDIDO 8841234 BOGOTA", "rappi pedido"),
    ("PAGO EN OLIMPICA SA BARRANQUILLA", "olimpica"),
    ("Compra en CARULLA PUNTO FIJO 0099", "carulla punto fijo"),
    ("TRANSFERENCIA A NEQUI JUAN PEREZ", "juan perez"),
    ("Pago PSE EPM EMPRESAS PUBLICAS DE MEDELLIN ESP", "epm empresas publicas"),
    ("ABONO INTERESES AHORROS", "intereses ahorros"),
    ("COMPRA INTERNACIONAL NETFLIX.COM", "netflix"),
    ("RETIRO CAJERO ATM 0455", "cajero atm"),
    ("Compra en DROGUERIA CRUZ VERDE 123", "drogueria cruz verde"),
    ("Pago en CINEMARK UNICENTRO CALI", "cinemark unicentro"),
    ("TARJETA DEBITO COMPRA STARBUCKS 7788", "starbucks"),
    ("compra   en   ZARA   cc andino  ", "zara cc andino"),
    ("PAGO EN UBER   *TRIP 05/03", "uber trip"),
    ("COMPRA EN FALABELLA.COM LTDA", "falabella"),
    ("COMPRA EN PANADERÍA LA ESPIGA REF 4455", "panaderia la espiga"),
    ("Pago factura Vanti 2024-10-05", "factura vanti"),
    ("PAGO EN SMART FIT BOG", "smart fit"),
]


@pytest.mark.parametrize("descripcion,esperada", HUELLAS)
def test_clave_comercio(descripcion, esperada):
    assert clave_comercio(descripcion) == esperada


def test_misma_huella_para_descripciones_distintas_del_mismo_comercio():
    assert clave_comercio("PAGO EN VENTO COLIVING 0105") == clave_comercio("COMPRA VENTO COLIVING BOGOTA")
    assert clave_comercio("Compra en JUAN VALDEZ SKANDIA") == clave_comercio("PAGO JUAN VALDEZ SKANDIA ref 9981")


def test_vacio_y_ruido_puro():
    assert clave_comercio("") == "" and clave_comercio(None) == ""
    assert clave_comercio("PAGO EN 0105 BOGOTA CO") == ""


def test_huella_en_descripcion_por_palabras_completas():
    assert huella_en_descripcion("uber", "UBER *TRIP HELP.UBER.COM")
    assert not huella_en_descripcion("ara", "COMPRA PARAGUAS LA 14")  # 'ara' dentro de otra palabra no cuenta
    assert huella_en_descripcion("vento coliving", "COMPRA VENTO COLIVING BOGOTA")


def test_huellas_peligrosas():
    assert es_huella_peligrosa("") is not None            # nada reconocible
    assert es_huella_peligrosa("d1") is not None          # una palabra de menos de 4 letras
    assert es_huella_peligrosa("pago") is not None        # palabra vacía
    assert es_huella_peligrosa("tienda") is not None
    assert es_huella_peligrosa("vento coliving") is None
    assert es_huella_peligrosa("rappi") is None


# ~80 descripciones realistas (inventadas) -> categoría esperada del diccionario
CASOS = [
    ("PAGO EN VENTO COLIVING ARRIENDO", "Hogar"), ("PAGO ARRIENDO APTO 502", "Hogar"),
    ("Pago PSE Administracion Conjunto Torres", "Hogar"), ("PAGO INMOBILIARIA CENTURY 21", "Hogar"),
    ("PAGO PSE EPM FACTURA", "Hogar"), ("Pago Codensa 99887", "Hogar"), ("ENEL COLOMBIA PAGO", "Hogar"),
    ("PSE VANTI GAS NATURAL", "Hogar"), ("ACUEDUCTO DE BOGOTA PAGO", "Hogar"),
    ("PAGO CLARO MOVIL", "Hogar"), ("Movistar Colombia recarga", "Hogar"), ("TIGO UNE FACTURA HOGAR", "Hogar"),
    ("ETB INTERNET PAGO", "Hogar"), ("WOM COLOMBIA", "Hogar"), ("Virgin Mobile Colombia", "Hogar"),
    ("COMPRA EXITO SUBA", "Comida"), ("Compra JUMBO CALLE 80", "Comida"), ("CARULLA PARQUE 93", "Comida"),
    ("D1 SUC CHAPINERO", "Comida"), ("TIENDAS ARA LOS HEROES", "Comida"), ("OLIMPICA SUPERSTORE", "Comida"),
    ("JUSTO Y BUENO TIENDA 2210", "Comida"), ("PRICESMART BOGOTA", "Comida"), ("SURTIMAX FONTIBON", "Comida"),
    ("COMPRA PLAZA DE MERCADO PALOQUEMAO", "Comida"), ("FRUVER LA ESQUINA", "Comida"), ("CARNICERIA DON PEPE", "Comida"),
    ("COMPRA PAN TIENDA LA 45", "Comida"), ("PANADERIA SAN JORGE", "Comida"), ("PASTELERIA MIMOS CC ANDINO", "Comida"),
    ("PAN PA YA CALLE 100", "Comida"), ("CREPES Y WAFFLES CALLE 82", "Comida"), ("FRISBY UNICENTRO", "Comida"),
    ("PRESTO CRA 15", "Comida"), ("MCDONALDS CHAPINERO", "Comida"), ("KFC CALLE 80", "Comida"),
    ("SUBWAY ZONA T", "Comida"), ("JUAN VALDEZ CAFE", "Comida"), ("STARBUCKS PARQUE 93", "Comida"),
    ("OMA CAFE 93", "Comida"), ("RAPPI COLOMBIA", "Comida"), ("PAGO RESTAURANTE LA CABRERA", "Comida"),
    ("ALMUERZO EJECUTIVO", "Comida"), ("PIZZERIA DE LA 85", "Comida"), ("Hamburguesas El Corral", "Comida"),
    ("ASADERO POLLO DORADO", "Comida"), ("UBER EATS PEDIDO", "Comida"),
    ("UBER *TRIP", "Transporte"), ("DIDI RIDES", "Transporte"), ("INDRIVER COLOMBIA", "Transporte"),
    ("CABIFY COLOMBIA", "Transporte"), ("RECARGA TULLAVE", "Transporte"), ("TRANSMILENIO RECARGA", "Transporte"),
    ("PEAJE LA CABANA", "Transporte"), ("PARQUEADERO CENTRO 93", "Transporte"), ("TERPEL ESTACION CALLE 53", "Transporte"),
    ("PRIMAX ESTACION", "Transporte"), ("BIOMAX", "Transporte"), ("TEXACO LA 30", "Transporte"), ("ZEUSS COMBUSTIBLE", "Transporte"),
    ("PAGO EPS SURA", "Salud"), ("COLSANITAS MEDICINA PREPAGADA", "Salud"), ("COMPENSAR EPS APORTE", "Salud"),
    ("FARMACIA CRUZ VERDE", "Salud"), ("LOCATEL SUCURSAL 12", "Salud"), ("LA REBAJA DROGUERIAS", "Salud"),
    ("DROGUERIA SAN JORGE", "Salud"), ("ODONTOLOGIA SONRISA", "Salud"), ("LABORATORIO CLINICO COLSANITAS", "Salud"),
    ("BODYTECH CHICO", "Salud"), ("PAGO GIMNASIO MENSUALIDAD", "Salud"),
    ("NETFLIX.COM", "Suscripciones"), ("SPOTIFY P1234", "Suscripciones"), ("DISNEY PLUS", "Suscripciones"),
    ("HBO MAX", "Suscripciones"), ("AMAZON PRIME", "Suscripciones"), ("YOUTUBE PREMIUM", "Suscripciones"),
    ("APPLE.COM/BILL", "Suscripciones"), ("ICLOUD STORAGE", "Suscripciones"), ("GOOGLE ONE", "Suscripciones"),
    ("OPENAI CHATGPT SUBSCR", "Suscripciones"), ("CANVA PTY", "Suscripciones"), ("NOTION LABS", "Suscripciones"),
    ("MICROSOFT 365", "Suscripciones"),
    ("CINE COLOMBIA", "Ocio"), ("TUBOLETA EVENTO", "Ocio"), ("PROCINAL", "Ocio"),
    ("FALABELLA CC ANDINO", "Compras"), ("ZARA ANDINO", "Compras"), ("H&M UNICENTRO", "Compras"),
    ("MERCADO LIBRE COLOMBIA", "Compras"), ("AMAZON MKTPLACE", "Compras"), ("TEMU.COM", "Compras"),
    ("ALKOSTO CALLE 13", "Compras"), ("KTRONIX", "Compras"), ("HOMECENTER CALLE 80", "Hogar"),
    ("PAGO SEGUROS BOLIVAR", "Seguros"), ("PAGO DIAN IMPUESTOS", "Impuestos"), ("IMPUESTO PREDIAL 2025", "Impuestos"),
    ("IMPUESTO DE VEHICULOS", "Impuestos"), ("MATRICULA UNIVERSIDAD", "Educación"), ("UDEMY ONLINE COURSE", "Educación"),
    ("CUOTA DE MANEJO TARJETA", "Cuota de manejo"), ("COMISION TRANSFERENCIA", "Comisiones y seguros"),
    ("INTERESES CORRIENTES", "Intereses de tarjeta"), ("IVA CUOTA DE MANEJO", "Cuota de manejo"),
    ("GMF 4X1000", "4x1000 (GMF)"), ("RETIRO CAJERO ATM", "Comisiones y costos financieros"),
    ("AVANCE EN EFECTIVO", "Comisiones y costos financieros"),
    ("TRANSFERENCIA NEQUI", "Transferencias"), ("BRE-B ENVIO", "Transferencias"), ("PAGO BRE B", "Transferencias"),
    ("NOMINA SKANDIA", "Ingresos"), ("ABONO INTERESES", "Rendimientos"),
]


@pytest.mark.parametrize("descripcion,categoria", CASOS)
def test_diccionario_clasifica(descripcion, categoria):
    r = clasificar_por_diccionario(descripcion)
    assert r is not None, descripcion
    assert r["categoria"] == categoria, (descripcion, r)
    assert r["razon"].startswith("por palabra clave «")


def test_hay_al_menos_80_casos():
    assert len(CASOS) >= 80


def test_palabra_completa_no_prefijo():
    # 'ara' (tiendas Ara) no se activa dentro de 'para' / 'paraguas'; 'pan' no dentro de 'japan'
    assert clasificar_por_diccionario("PAGO PARA LA FIESTA") is None
    assert clasificar_por_diccionario("TOURS JAPAN") is None


def test_mas_especifico_gana():
    assert clasificar_por_diccionario("UBER EATS BOGOTA")["categoria"] == "Comida"
    assert clasificar_por_diccionario("UBER TRIP")["categoria"] == "Transporte"


def test_persona_a_persona_no_es_gasto():
    r = clasificar_por_diccionario("Transferencia a Juan Perez")
    assert r["categoria"] == "Transferencias" and r["confianza"] < 0.6
    assert clasificar_por_diccionario("Recibiste de Ana Lopez")["tipo"] == "income"
