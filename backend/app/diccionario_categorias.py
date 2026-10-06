"""Diccionario de palabras clave -> categoría para extractos y notificaciones
de bancos colombianos. ES SOLO DATOS: para enseñarle algo nuevo al sistema
basta con agregar una línea a SECCIONES.

Formato de cada entrada:  "palabra o frase": "Categoría"
  - Va en minúscula y sin tildes (se compara así contra la descripción).
  - Coincide por PALABRAS COMPLETAS ('ara' no se activa dentro de 'para').
  - Un '*' al final significa "empieza con" ('droguer*' -> droguería, droguerías).
  - Si dos entradas coinciden, gana la más específica (más palabras / más larga):
    'uber eats' le gana a 'uber'.
  - Para un ingreso se escribe ('palabra', 'Categoría', 'income') en INGRESOS.

Las categorías base de la app son: Comida, Transporte, Ocio, Hogar, Salud,
Transferencias, Ingresos y Otros. Las demás ('Suscripciones', 'Educación',
'Comisiones y costos financieros'...) solo se sugieren si el usuario las tiene
activas; si no, se usa su categoría de respaldo (CATEGORIA_RESPALDO) o 'Otros'
(ver autocat.ajustar_a_categorias_usuario).
"""

COMISIONES = "Comisiones y costos financieros"

# Si el usuario no tiene la categoría sugerida, se prueba con esta antes de 'Otros'.
CATEGORIA_RESPALDO: dict[str, str] = {
    "Suscripciones": "Ocio",
    "Compras": "Otros",
    "Educación": "Otros",
    "Seguros": "Otros",
    "Impuestos": "Otros",
    "Ahorro e inversión": "Transferencias",  # es plata que cambia de bolsillo, no un gasto de consumo
    COMISIONES: "Otros",
}

SECCIONES: dict[str, dict[str, str]] = {
    # ── Vivienda ────────────────────────────────────────────────────
    "Hogar": {
        "arriendo": "Hogar", "arrendamiento": "Hogar", "canon": "Hogar", "canon de arrendamiento": "Hogar",
        "alquiler": "Hogar", "administracion": "Hogar", "cuota administracion": "Hogar",
        "propiedad horizontal": "Hogar", "conjunto residencial": "Hogar", "coliving": "Hogar",
        "inmobiliaria": "Hogar", "inmobiliaria*": "Hogar", "finca raiz": "Hogar",
        "homecenter": "Hogar", "easy": "Hogar", "sodimac": "Hogar", "ferreteria": "Hogar", "ferreteria*": "Hogar",
        "pintuco": "Hogar", "falabella hogar": "Hogar", "muebles": "Hogar", "colchones": "Hogar",
        "empleada domestica": "Hogar", "servicio domestico": "Hogar", "jardineria": "Hogar",
        "plomeria": "Hogar", "plomero": "Hogar", "electricista": "Hogar", "cerrajeria": "Hogar",
        "lavanderia": "Hogar", "tintoreria": "Hogar", "mudanza": "Hogar",
        # servicios públicos
        "epm": "Hogar", "codensa": "Hogar", "enel": "Hogar", "enel colombia": "Hogar", "afinia": "Hogar",
        "air e": "Hogar", "electricaribe": "Hogar", "celsia": "Hogar", "essa": "Hogar",
        "vanti": "Hogar", "gas natural": "Hogar", "gases del caribe": "Hogar", "alcanos": "Hogar",
        "acueducto": "Hogar", "alcantarillado": "Hogar", "empresas publicas": "Hogar", "triple a": "Hogar",
        "aguas de": "Hogar", "aseo": "Hogar", "servicios publicos": "Hogar",
        "factura de energia": "Hogar", "factura de agua": "Hogar", "factura de gas": "Hogar",
        # telecomunicaciones
        "claro": "Hogar", "claro hogar": "Hogar", "movistar": "Hogar", "tigo": "Hogar", "tigo une": "Hogar",
        "wom": "Hogar", "virgin": "Hogar", "virgin mobile": "Hogar", "etb": "Hogar", "une": "Hogar",
        "directv": "Hogar", "colombia telecomunicaciones": "Hogar", "avantel": "Hogar", "internet": "Hogar",
        "plan de datos": "Hogar", "recarga celular": "Hogar", "recarga claro": "Hogar", "recarga movistar": "Hogar",
        "recarga tigo": "Hogar",
    },

    # ── Mercado y comida ────────────────────────────────────────────
    "Comida": {
        # supermercados y mercado
        "supermercado": "Comida", "supermercado*": "Comida", "minimarket": "Comida", "tienda": "Comida",
        "tienda de barrio": "Comida", "exito": "Comida", "almacenes exito": "Comida", "carulla": "Comida",
        "jumbo": "Comida", "d1": "Comida", "tiendas d1": "Comida", "ara": "Comida", "olimpica": "Comida",
        "justo y bueno": "Comida", "justo bueno": "Comida", "metro supermercado": "Comida", "tiendas metro": "Comida",
        "surtimax": "Comida", "super inter": "Comida", "makro": "Comida", "pricesmart": "Comida",
        "price smart": "Comida", "merqueo": "Comida", "la 14": "Comida", "colsubsidio supermercado": "Comida",
        "plaza de mercado": "Comida", "plaza minorista": "Comida", "fruver": "Comida", "fruteria": "Comida",
        "verduras": "Comida", "carniceria": "Comida", "carnes": "Comida", "pescaderia": "Comida",
        "avicola": "Comida", "huevos": "Comida", "licores": "Comida", "licorera": "Comida", "mercado": "Comida",
        "mercado libre alimentos": "Comida", "abarrotes": "Comida", "granero": "Comida", "salsamentaria": "Comida",
        # panaderías y comida
        "pan": "Comida", "panaderia": "Comida", "panaderia*": "Comida", "pasteleria": "Comida",
        "pasteleria*": "Comida", "pan pa ya": "Comida", "mimos": "Comida", "bakery": "Comida", "reposteria": "Comida",
        "cafeteria": "Comida", "heladeria": "Comida", "helados": "Comida", "cafe": "Comida", "panes": "Comida",
        "crepes": "Comida", "crepes and waffles": "Comida", "crepes waffles": "Comida", "frisby": "Comida",
        "presto": "Comida", "mcdonalds": "Comida", "mc donalds": "Comida", "kfc": "Comida",
        "burger king": "Comida", "dominos": "Comida", "papa johns": "Comida", "pizza hut": "Comida",
        "subway": "Comida", "juan valdez": "Comida", "tostao": "Comida", "oma": "Comida", "oma cafe": "Comida",
        "starbucks": "Comida", "el corral": "Comida", "sandwich qbano": "Comida", "qbano": "Comida",
        "kokoriko": "Comida", "wok": "Comida", "rappi": "Comida", "ifood": "Comida", "domicilio": "Comida",
        "domicilios": "Comida", "uber eats": "Comida", "didi food": "Comida", "restaurante": "Comida",
        "restaurante*": "Comida", "almuerzo": "Comida", "almuerzos": "Comida", "desayuno": "Comida",
        "pizza": "Comida", "pizzeria": "Comida", "hamburguesa": "Comida", "hamburguesas": "Comida",
        "asadero": "Comida", "pollo": "Comida", "sushi": "Comida", "parrilla": "Comida", "comidas rapidas": "Comida",
        "corrientazo": "Comida", "bogota beer": "Comida", "cervezeria": "Comida", "bar": "Comida", "cerveza": "Comida",
        # tiendas de conveniencia y comida que se repite en los extractos
        "oxxo": "Comida", "tiendas ya": "Comida", "crepesywaffles": "Comida", "polleria*": "Comida",
        "cantina": "Comida", "tamales": "Comida", "yogurt": "Comida", "goyurt": "Comida", "burger": "Comida",
        "butchery": "Comida", "rossopomodoro": "Comida", "empanadas": "Comida", "arepas": "Comida",
        "sandwich": "Comida", "parrilla*": "Comida", "brasa": "Comida", "tostadas": "Comida", "rustica": "Comida",
    },

    # ── Transporte ──────────────────────────────────────────────────
    "Transporte": {
        "uber": "Transporte", "uber rides": "Transporte", "uber trip": "Transporte", "didi": "Transporte",
        "cabify": "Transporte", "beat": "Transporte", "indriver": "Transporte", "in driver": "Transporte",
        "picap": "Transporte", "taxis libres": "Transporte", "taxi": "Transporte", "taxi*": "Transporte",
        "terpel": "Transporte", "primax": "Transporte", "biomax": "Transporte", "texaco": "Transporte",
        "esso": "Transporte", "zeuss": "Transporte", "gasolina": "Transporte", "combustible": "Transporte",
        "estacion de servicio": "Transporte", "parqueadero": "Transporte", "parqueadero*": "Transporte",
        "parking": "Transporte", "peaje": "Transporte", "peajes": "Transporte", "sitp": "Transporte",
        "transmilenio": "Transporte", "metro de medellin": "Transporte", "mio cali": "Transporte",
        "megabus": "Transporte", "transcaribe": "Transporte", "tullave": "Transporte", "civica": "Transporte",
        "recarga tarjeta": "Transporte", "avianca": "Transporte", "latam": "Transporte", "wingo": "Transporte",
        "easyfly": "Transporte", "satena": "Transporte", "viva air": "Transporte", "aerolinea": "Transporte",
        "tiquete aereo": "Transporte", "bus": "Transporte", "flota": "Transporte", "bolivariano": "Transporte",
        "rentacar": "Transporte", "rent a car": "Transporte", "alquiler vehiculo": "Transporte",
        "taller": "Transporte", "taller mecanico": "Transporte", "llantas": "Transporte", "lavado de carro": "Transporte",
        "lavadero": "Transporte", "soat": "Transporte", "revision tecnomecanica": "Transporte",
        "tecnomecanica": "Transporte", "multa transito": "Transporte", "comparendo": "Transporte",
        "grua": "Transporte", "bicicleta": "Transporte",
        # estaciones de servicio ("EDS" = estación de servicio) y bicicletas compartidas
        "eds": "Transporte", "servicentro": "Transporte", "autocombustibles": "Transporte",
        "combustibles": "Transporte", "gasolinera": "Transporte", "tembici": "Transporte", "bicicletas": "Transporte",
    },

    # ── Salud y bienestar ───────────────────────────────────────────
    "Salud": {
        "eps": "Salud", "prepagada": "Salud", "medicina prepagada": "Salud", "colsanitas": "Salud",
        "sanitas": "Salud", "sura": "Salud", "sura eps": "Salud", "eps sura": "Salud", "compensar": "Salud",
        "compensar salud": "Salud", "coomeva medicina": "Salud", "famisanar": "Salud", "nueva eps": "Salud",
        "salud total": "Salud", "medimas": "Salud", "cafam": "Salud", "colmedica": "Salud", "allianz salud": "Salud",
        "copago": "Salud", "cuota moderadora": "Salud", "consulta medica": "Salud",
        "medico": "Salud", "clinica": "Salud", "hospital": "Salud", "urgencias": "Salud",
        "farmacia": "Salud", "farmacia*": "Salud", "farmatodo": "Salud", "cruz verde": "Salud",
        "la rebaja": "Salud", "droguer*": "Salud", "locatel": "Salud", "medicamentos": "Salud",
        "odontologia": "Salud", "odontologo": "Salud", "dentista": "Salud", "ortodoncia": "Salud",
        "laboratorio": "Salud", "laboratorio clinico": "Salud", "examenes": "Salud", "optica": "Salud",
        "psicologo": "Salud", "psicologia": "Salud", "terapia": "Salud", "fisioterapia": "Salud",
        "veterinaria": "Salud", "gimnasio": "Salud", "gimnasio*": "Salud", "gym": "Salud", "bodytech": "Salud",
        "smart fit": "Salud", "spinning center": "Salud", "crossfit": "Salud", "yoga": "Salud", "pilates": "Salud",
    },

    # ── Ocio, suscripciones y digital ───────────────────────────────
    "Ocio": {
        "cine": "Ocio", "cine colombia": "Ocio", "cinemark": "Ocio", "procinal": "Ocio", "royal films": "Ocio",
        "boleteria": "Ocio", "tuboleta": "Ocio", "eventbrite": "Ocio", "concierto": "Ocio", "discoteca": "Ocio",
        "billar": "Ocio", "bolera": "Ocio", "parque de diversiones": "Ocio", "salon de apuestas": "Ocio",
        "betplay": "Ocio", "wplay": "Ocio", "rushbet": "Ocio", "codere": "Ocio", "teatro": "Ocio",
        "museo": "Ocio", "hotel": "Ocio", "hostal": "Ocio", "airbnb": "Ocio", "booking": "Ocio",
        "despegar": "Ocio", "viaje": "Ocio", "steam": "Ocio", "playstation": "Ocio", "nintendo": "Ocio",
        "xbox": "Ocio", "epic games": "Ocio", "riot games": "Ocio", "tinder": "Ocio", "bumble": "Ocio",
        "duolingo": "Ocio", "libreria": "Ocio", "panamericana": "Ocio",
    },
    "Suscripciones": {
        "netflix": "Suscripciones", "spotify": "Suscripciones", "disney": "Suscripciones",
        "disney plus": "Suscripciones", "hbo": "Suscripciones", "max app": "Suscripciones",
        "amazon prime": "Suscripciones", "prime video": "Suscripciones", "youtube": "Suscripciones",
        "youtube premium": "Suscripciones", "youtube music": "Suscripciones", "apple music": "Suscripciones",
        "apple tv": "Suscripciones", "apple": "Suscripciones", "apple com bill": "Suscripciones",
        "icloud": "Suscripciones", "google": "Suscripciones", "google one": "Suscripciones",
        "google play": "Suscripciones", "google workspace": "Suscripciones", "app store": "Suscripciones",
        "itunes": "Suscripciones", "microsoft": "Suscripciones", "microsoft 365": "Suscripciones",
        "chatgpt": "Suscripciones", "openai": "Suscripciones", "claude ai": "Suscripciones",
        "anthropic": "Suscripciones", "canva": "Suscripciones", "notion": "Suscripciones",
        "dropbox": "Suscripciones", "adobe": "Suscripciones", "github": "Suscripciones", "zoom": "Suscripciones",
        "linkedin": "Suscripciones", "midjourney": "Suscripciones", "deezer": "Suscripciones",
        "paramount": "Suscripciones", "star plus": "Suscripciones", "crunchyroll": "Suscripciones",
        "twitch": "Suscripciones", "patreon": "Suscripciones", "suscripcion": "Suscripciones",
    },

    # ── Educación ───────────────────────────────────────────────────
    "Educación": {
        "pension colegio": "Educación", "matricula": "Educación", "matricula universidad": "Educación",
        "icetex": "Educación", "colegio": "Educación", "universidad": "Educación", "universidad*": "Educación",
        "jardin infantil": "Educación", "guarderia": "Educación", "curso": "Educación", "curso online": "Educación",
        "cursos": "Educación", "diplomado": "Educación", "udemy": "Educación", "coursera": "Educación",
        "platzi": "Educación", "edx": "Educación", "instituto": "Educación", "academia": "Educación",
        "ingles": "Educación", "utiles escolares": "Educación", "papeleria": "Educación",
    },

    # ── Compras y ropa ──────────────────────────────────────────────
    "Compras": {
        "falabella": "Compras", "zara": "Compras", "h and m": "Compras", "h m": "Compras", "mercado libre": "Compras",
        "mercadolibre": "Compras", "amazon": "Compras", "temu": "Compras", "shein": "Compras",
        "aliexpress": "Compras", "dafiti": "Compras", "alkosto": "Compras", "ktronix": "Compras",
        "adidas": "Compras", "nike": "Compras", "bershka": "Compras", "pull and bear": "Compras",
        "studio f": "Compras", "arturo calle": "Compras", "bogota outlets": "Compras",
        "linio": "Compras", "ikea": "Compras", "decathlon": "Compras", "juguetes": "Compras", "zapateria": "Compras",
        "ropa": "Compras", "calzado": "Compras", "joyeria": "Compras", "perfumeria": "Compras",
        "novaventa": "Compras", "dollarcity": "Compras", "dollar city": "Compras", "miniso": "Compras",
        "mallplaza": "Compras", "mall plaza": "Compras", "hym": "Compras", "koaj": "Compras",
        "centro comercial": "Compras",
    },

    # ── Seguros, impuestos, ahorro ──────────────────────────────────
    "Cuidado personal": {
        "barberia*": "Salud", "peluqueria*": "Salud", "salon de belleza": "Salud", "spa": "Salud",
        "manicure": "Salud", "estetica": "Salud",
    },
    "Seguros": {
        "seguro": "Seguros", "seguros": "Seguros", "seguros bolivar": "Seguros", "seguros sura": "Seguros",
        "mapfre": "Seguros", "liberty": "Seguros", "axa colpatria": "Seguros", "prima de seguro": "Seguros",
        "poliza": "Seguros", "seguro de vida": "Seguros", "seguro vehiculo": "Seguros", "seguro deudor": "Seguros",
    },
    "Impuestos": {
        "dian": "Impuestos", "impuesto timbre": "Impuestos", "declaracion renta": "Impuestos",
        "impuesto vehicular": "Impuestos", "impuesto de vehiculos": "Impuestos", "predial": "Impuestos",
        "impuesto predial": "Impuestos", "industria y comercio": "Impuestos", "retefuente": "Impuestos",
        "secretaria de hacienda": "Impuestos", "impuesto": "Impuestos", "impuestos": "Impuestos",
    },
    "Ahorro e inversión": {
        "colpensiones": "Ahorro e inversión", "proteccion pension": "Ahorro e inversión", "proteccion": "Ahorro e inversión",
        "porvenir": "Ahorro e inversión", "skandia": "Ahorro e inversión", "old mutual": "Ahorro e inversión",
        "fondo de pensiones": "Ahorro e inversión", "cdt": "Ahorro e inversión", "fiducia": "Ahorro e inversión",
        "aportes voluntarios": "Ahorro e inversión", "trii": "Ahorro e inversión",
    },

    # ── Conceptos BANCARIOS (no son gasto de consumo) ───────────────
    COMISIONES: {
        "cuota de manejo": COMISIONES, "cuota manejo": COMISIONES, "comision": COMISIONES, "comision*": COMISIONES,
        "cargo por servicio": COMISIONES, "gmf": COMISIONES, "4x1000": COMISIONES, "gravamen movimientos financieros": COMISIONES,
        "gravamen": COMISIONES, "iva": COMISIONES, "iva comision": COMISIONES, "iva cuota de manejo": COMISIONES,
        "intereses": COMISIONES, "intereses corrientes": COMISIONES, "interes de mora": COMISIONES, "intereses de mora": COMISIONES,
        "retiro cajero": COMISIONES, "retiro atm": COMISIONES, "retiro en efectivo": COMISIONES, "retiro sin tarjeta": COMISIONES,
        "retiro cajero electronico": COMISIONES, "avance": COMISIONES, "avance en efectivo": COMISIONES, "avance tarjeta": COMISIONES,
        "seguro tarjeta": COMISIONES, "cobro seguro": COMISIONES, "costo transaccion": COMISIONES, "cobro por transferencia": COMISIONES,
        "servicio pse": COMISIONES, "sobregiro": COMISIONES, "cuota de apertura": COMISIONES,
    },
    "Transferencias": {
        "transferencia nequi": "Transferencias", "transferencia daviplata": "Transferencias", "nequi": "Transferencias",
        "daviplata": "Transferencias", "bre b": "Transferencias", "bre-b": "Transferencias", "envio bre b": "Transferencias",
        "transferencia bre b": "Transferencias", "movii": "Transferencias",
        "transferencia entre cuentas": "Transferencias", "traslado entre cuentas": "Transferencias",
    },
}

# Ingresos: (palabra, categoría) -> el tipo es 'income'.
INGRESOS: dict[str, str] = {
    "nomina": "Ingresos", "salario": "Ingresos", "pago de nomina": "Ingresos", "consignacion": "Ingresos",
    "honorarios": "Ingresos", "pago factura": "Ingresos", "pago servicio prestado": "Ingresos",
    "bonificacion": "Ingresos", "prima": "Ingresos", "prima de servicios": "Ingresos", "cesantias": "Ingresos",
    "liquidacion": "Ingresos", "abono intereses": "Ingresos", "rendimientos": "Ingresos",
    "rendimientos financieros": "Ingresos", "devolucion": "Ingresos", "reembolso": "Ingresos",
    "reintegro": "Ingresos", "nota credito": "Ingresos", "dividendos": "Ingresos", "comisiones ganadas": "Ingresos",
    # intereses A FAVOR (Nu, Nequi, bancos): ganarlos no es una comisión ni un costo
    "pago de intereses": "Ingresos", "intereses ganados": "Ingresos", "intereses de ahorro": "Ingresos",
    "intereses abonados": "Ingresos", "rendimiento*": "Ingresos", "reembolso realizado": "Ingresos",
    "cashback": "Ingresos",
}

# Inversión y ahorro: se evalúan ANTES que las frases de transferencia, porque lo que
# parece "Enviaste a <entidad>" es plata que se invierte, no un giro a una persona.
INVERSION_PRIORITARIA = [
    "fondo de inversion", "fondo de inversion colectiva", "fondo voluntario", "fondo de pensiones",
    "acciones y valores", "comisionista de bolsa", "fiduciaria*", "fiducia", "cdt", "cajita", "cajitas",
    "aportes voluntarios", "bolsa de valores", "trii", "tyba", "finaccess",
]

# Frases de transferencia entre personas (se evalúan antes que el diccionario).
TRANSFERENCIA_PERSONA_FUERTE = [
    "enviaste a", "recibiste de", "transferencia a", "transferencia de", "envio a",
    "giro a", "giro de", "trf a", "trf de", "traslado entre cuentas", "traslado a cuenta",
    "recarga desde", "otros bancos de",
]
# Extractos tipo Nequi: la línea EMPIEZA con "Para <persona>" (salida) o "De <persona>"
# (entrada). Solo al inicio: 'COSAS PARA TI' en medio de una compra no es una transferencia.
TRANSFERENCIA_PERSONA_INICIO = {"para": "expense", "de": "income"}
# ...y estas solo si ninguna palabra clave del diccionario aplica.
TRANSFERENCIA_PERSONA_DEBIL = ["pago a", "transferencia", "transf"]
TRANSFERENCIA_ENTRADA = {"recibiste de", "giro de", "trf de", "transferencia de", "recarga desde", "otros bancos de"}


def entradas() -> list[tuple[str, str, str]]:
    """(palabra, categoría, tipo) de todo el diccionario, listo para indexar."""
    salida: list[tuple[str, str, str]] = []
    for mapa in SECCIONES.values():
        for palabra, categoria in mapa.items():
            salida.append((palabra, categoria, "expense"))
    for palabra, categoria in INGRESOS.items():
        salida.append((palabra, categoria, "income"))
    return salida
