"""
Registro de países de CuadraMe: UN solo lugar con lo que cambia de un país a otro.

Espejo en el frontend: pwa/src/lib/paises.js (generado desde este archivo; la prueba
tests/test_paises.py falla si dejan de coincidir). Para agregar un país o un banco se
edita SOLO aquí y se regenera el espejo con `python tools/generar_paises_js.py`.

Reglas:
- Nada de lógica compartida debe asumir Colombia: se pregunta aquí por país.
- Un dato que no se pudo verificar va con `"verificado": False` en su país y se
  documenta en docs/LATAM_EXPANSION.md. Mejor menos bancos que bancos inventados.
- Los remitentes (`dominios`) de países fuera de CO NO están probados con correos reales.
"""
from __future__ import annotations

PAIS_POR_DEFECTO_LEGADO = "CO"  # perfiles anteriores a esta función: todos eran colombianos


def _b(nombre, mono=None, bg=None, fg="#ffffff", popular=False, dominios=(), alias=(), tipo="banco"):
    return {
        "nombre": nombre,
        "mono": mono,
        "bg": bg,
        "fg": fg if bg else None,
        "popular": popular,
        "tipo": tipo,
        "dominios": list(dominios),
        "alias": list(alias),
    }


# Colombia: las marcas y los remitentes viven en entidadesFinancierasCO.js y en
# extractos_gmail.DOMINIOS_BANCOS (ya probados con correos reales). Aquí van los nombres.
_BANCOS_CO = [
    _b("Bancolombia", popular=True), _b("Davivienda", popular=True), _b("BBVA Colombia", popular=True),
    _b("Banco de Bogotá", popular=True), _b("Banco de Occidente"), _b("Banco Popular"),
    _b("Banco Caja Social"), _b("Banco AV Villas"), _b("Scotiabank Colpatria"), _b("Itaú"),
    _b("Banco Falabella"), _b("Banco Pichincha"), _b("Banco Agrario"), _b("Banco W"),
    _b("Bancamía"), _b("Mibanco"), _b("Coltefinanciera"), _b("Finandina"), _b("Banco Serfinanza"),
    _b("Bancoomeva"), _b("Confiar"), _b("Cotrafá"), _b("Tuya"),
    _b("Nequi", popular=True, tipo="billetera"), _b("Daviplata", popular=True, tipo="billetera"),
    _b("Nu Colombia", popular=True, tipo="billetera"), _b("Lulo Bank", popular=True, tipo="billetera"),
    _b("Movii", tipo="billetera"), _b("RappiPay", tipo="billetera"), _b("RappiCard", tipo="billetera"),
    _b("Ualá", tipo="billetera"), _b("Tpaga", tipo="billetera"), _b("Dale!", tipo="billetera"),
]

_PALABRAS_EXTRACTO_ES = ["extracto", "estado de cuenta", "resumen de cuenta", "resumen mensual"]

PAISES: dict[str, dict] = {
    "CO": {
        "codigo": "CO", "nombre": "Colombia", "estado": "completo", "disponible": True,
        "moneda": "COP", "simbolo": "$", "decimales": 0, "locale": "es-CO",
        "zona_horaria": "America/Bogota", "idioma": "es-CO", "tratamiento": "tu",
        "separador_miles": ".", "separador_decimal": ",",
        "unidad_tributaria": {"sigla": "UVT", "nombre": "Unidad de Valor Tributario"},
        "funciones_fiscales": ["renta_dian", "gmf", "uvt"],
        "impuestos": [
            {"id": "renta_dian", "nombre": "Declaración de renta (DIAN)", "informativo": False},
            {"id": "gmf", "nombre": "Gravamen a los movimientos financieros (4x1000)", "informativo": False},
        ],
        "pago_inmediato": {"nombre": "Bre-B", "texto": "Bre-B (llaves)"},
        "banco_central": {"sigla": "BanRep", "nombre": "Banco de la República", "tasa_referencia": "Tasa de usura / IBR"},
        "ley_datos": {"nombre": "Ley 1581 de 2012", "autoridad": "Superintendencia de Industria y Comercio (SIC)"},
        "formatos_extracto": ["pdf_con_clave", "excel_csv"],
        "palabras_extracto": _PALABRAS_EXTRACTO_ES,
        "bancos": _BANCOS_CO,
    },
    "MX": {
        "codigo": "MX", "nombre": "México", "estado": "inicial", "disponible": True,
        "moneda": "MXN", "simbolo": "$", "decimales": 2, "locale": "es-MX",
        "zona_horaria": "America/Mexico_City", "idioma": "es-MX", "tratamiento": "tu",
        "separador_miles": ",", "separador_decimal": ".",
        "unidad_tributaria": {"sigla": "UMA", "nombre": "Unidad de Medida y Actualización"},
        "funciones_fiscales": ["declaracion_anual_informativa"],
        "impuestos": [
            {"id": "declaracion_anual_informativa", "nombre": "Declaración anual de personas físicas (SAT)",
             "informativo": True, "mes": 4},
        ],
        "pago_inmediato": {"nombre": "SPEI", "texto": "SPEI / CoDi"},
        "banco_central": {"sigla": "Banxico", "nombre": "Banco de México", "tasa_referencia": "TIIE / tasa objetivo"},
        "ley_datos": {"nombre": "Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP, texto de 2025)",
                      "autoridad": "Secretaría Anticorrupción y Buen Gobierno"},
        "formatos_extracto": ["pdf_con_clave", "excel_csv"],
        "palabras_extracto": _PALABRAS_EXTRACTO_ES + ["estado de cuenta"],
        "bancos": [
            _b("BBVA México", "BBVA", "#072146", popular=True, dominios=["bbva.mx", "bbva.com.mx"], alias=["bbva", "bancomer"]),
            _b("Banorte", "BN", "#EB0029", popular=True, dominios=["banorte.com"]),
            _b("Santander México", "SAN", "#EC0000", popular=True, dominios=["santander.com.mx"], alias=["santander"]),
            _b("Citibanamex", "CB", "#056DAE", popular=True, dominios=["banamex.com", "citibanamex.com"], alias=["banamex"]),
            _b("HSBC México", "HS", "#DB0011", dominios=["hsbc.com.mx"], alias=["hsbc"]),
            _b("Scotiabank México", "SC", "#EC111A", dominios=["scotiabank.com.mx"]),
            _b("Inbursa", "IN", "#0033A0", dominios=["inbursa.com"]),
            _b("Banco Azteca", "AZ", "#00A94F", dominios=["bancoazteca.com.mx"]),
            _b("Nu México", "Nu", "#820AD1", popular=True, tipo="billetera", dominios=["nu.com.mx"], alias=["nu", "nubank"]),
            _b("Mercado Pago", "MP", "#00B1EA", popular=True, tipo="billetera", dominios=["mercadopago.com.mx", "mercadopago.com"], alias=["mercadopago"]),
            _b("Spin by OXXO", "SP", "#E4002B", tipo="billetera", dominios=["spinbyoxxo.com.mx"], alias=["spin"]),
            _b("Hey Banco", "HB", "#000000", popular=True, dominios=["heybanco.com"], alias=["hey"]),
            _b("Klar", "K", "#1A1A1A", tipo="billetera", dominios=["klar.mx"]),
            _b("Stori", "ST", "#6C2BD9", tipo="billetera", dominios=["storicard.com"]),
            _b("Ualá México", "U", "#2D2D2D", tipo="billetera", dominios=["uala.mx"], alias=["uala"]),
        ],
    },
    "CL": {
        "codigo": "CL", "nombre": "Chile", "estado": "inicial", "disponible": True,
        "moneda": "CLP", "simbolo": "$", "decimales": 0, "locale": "es-CL",
        "zona_horaria": "America/Santiago", "idioma": "es-CL", "tratamiento": "tu",
        "separador_miles": ".", "separador_decimal": ",",
        "unidad_tributaria": {"sigla": "UTM", "nombre": "Unidad Tributaria Mensual"},
        "funciones_fiscales": ["declaracion_anual_informativa"],
        "impuestos": [
            {"id": "declaracion_anual_informativa", "nombre": "Operación Renta (SII)", "informativo": True, "mes": 4},
        ],
        "pago_inmediato": {"nombre": "Transferencia", "texto": "transferencia electrónica"},
        "banco_central": {"sigla": "BCCh", "nombre": "Banco Central de Chile", "tasa_referencia": "Tasa de política monetaria (TPM)"},
        "ley_datos": {"nombre": "Ley 19.628 (vigente) y Ley 21.719 (entra en vigencia el 1 dic 2026; hay proyecto para postergarla)",
                      "autoridad": "Agencia de Protección de Datos Personales (en constitución)"},
        "formatos_extracto": ["pdf_con_clave", "excel_csv"],
        "palabras_extracto": _PALABRAS_EXTRACTO_ES + ["cartola", "estado de cuenta"],
        "bancos": [
            _b("BancoEstado", "BE", "#F26B21", popular=True, dominios=["bancoestado.cl"], alias=["cuentarut", "cuenta rut"]),
            _b("Banco de Chile", "BCh", "#003595", popular=True, dominios=["bancochile.cl", "bancoedwards.cl"], alias=["edwards"]),
            _b("Santander Chile", "SAN", "#EC0000", popular=True, dominios=["santander.cl"], alias=["santander"]),
            _b("BCI", "BCI", "#00A0DF", popular=True, dominios=["bci.cl"]),
            _b("Scotiabank Chile", "SC", "#EC111A", dominios=["scotiabank.cl"]),
            _b("Itaú Chile", "IT", "#FF6200", dominios=["itau.cl"], alias=["itau"]),
            _b("Banco Falabella", "F", "#00B14F", dominios=["bancofalabella.cl"], alias=["falabella"]),
            _b("Banco Ripley", "R", "#7A2E8E", dominios=["bancoripley.cl"], alias=["ripley"]),
            _b("Banco Security", "SE", "#00457C", dominios=["bancosecurity.cl"]),
            _b("Mach", "M", "#6B2FD9", popular=True, tipo="billetera", dominios=["somosmach.com", "mach.cl"]),
            _b("Tenpo", "T", "#00D3AB", fg="#0A0F2C", popular=True, tipo="billetera", dominios=["tenpo.cl"]),
            _b("Mercado Pago", "MP", "#00B1EA", tipo="billetera", dominios=["mercadopago.cl"], alias=["mercadopago"]),
            _b("Fintual", "Fi", "#1B3A5C", tipo="billetera", dominios=["fintual.cl"]),
        ],
    },
    "PE": {
        "codigo": "PE", "nombre": "Perú", "estado": "inicial", "disponible": True,
        "moneda": "PEN", "simbolo": "S/", "decimales": 2, "locale": "es-PE",
        "zona_horaria": "America/Lima", "idioma": "es-PE", "tratamiento": "tu",
        "separador_miles": ",", "separador_decimal": ".",
        "unidad_tributaria": {"sigla": "UIT", "nombre": "Unidad Impositiva Tributaria"},
        "funciones_fiscales": ["declaracion_anual_informativa"],
        "impuestos": [
            {"id": "declaracion_anual_informativa", "nombre": "Declaración anual de renta (SUNAT)", "informativo": True, "mes": 3},
            {"id": "itf", "nombre": "Impuesto a las Transacciones Financieras (ITF)", "informativo": True},
        ],
        "pago_inmediato": {"nombre": "Yape / Plin", "texto": "Yape o Plin"},
        "banco_central": {"sigla": "BCRP", "nombre": "Banco Central de Reserva del Perú", "tasa_referencia": "Tasa de referencia"},
        "ley_datos": {"nombre": "Ley 29733 de Protección de Datos Personales", "autoridad": "Autoridad Nacional de Protección de Datos Personales (MINJUSDH)"},
        "formatos_extracto": ["pdf_con_clave", "excel_csv"],
        "palabras_extracto": _PALABRAS_EXTRACTO_ES + ["estado de cuenta"],
        "bancos": [
            _b("BCP", "BCP", "#002A8D", popular=True, dominios=["viabcp.com", "bcp.com.pe"], alias=["banco de credito", "yape"]),
            _b("Interbank", "IB", "#00A651", popular=True, dominios=["interbank.pe"], alias=["plin"]),
            _b("BBVA Perú", "BBVA", "#072146", popular=True, dominios=["bbva.pe"], alias=["bbva"]),
            _b("Scotiabank Perú", "SC", "#EC111A", popular=True, dominios=["scotiabank.com.pe"]),
            _b("Banco de la Nación", "BN", "#C8102E", dominios=["bn.com.pe"]),
            _b("Mibanco", "MB", "#D91F5C", dominios=["mibanco.com.pe"]),
            _b("Banco Pichincha", "BP", "#FFD100", fg="#003DA5", dominios=["pichincha.pe"]),
            _b("Banco Falabella", "F", "#00B14F", dominios=["bancofalabella.pe"], alias=["falabella"]),
            _b("Yape", "Y", "#742384", popular=True, tipo="billetera", dominios=["yape.com.pe"]),
            _b("Plin", "P", "#00C2A8", fg="#0A0F2C", tipo="billetera"),
            _b("Mercado Pago", "MP", "#00B1EA", tipo="billetera", dominios=["mercadopago.com.pe"], alias=["mercadopago"]),
            _b("Ualá Perú", "U", "#2D2D2D", tipo="billetera", alias=["uala"]),
        ],
    },
    "AR": {
        "codigo": "AR", "nombre": "Argentina", "estado": "basico", "disponible": True,
        "moneda": "ARS", "simbolo": "$", "decimales": 2, "locale": "es-AR",
        "zona_horaria": "America/Argentina/Buenos_Aires", "idioma": "es-AR", "tratamiento": "vos",
        "separador_miles": ".", "separador_decimal": ",",
        "unidad_tributaria": {"sigla": "MNI", "nombre": "Mínimo no imponible (Ganancias)"},
        "funciones_fiscales": ["declaracion_anual_informativa"],
        "impuestos": [
            {"id": "declaracion_anual_informativa", "nombre": "Ganancias y Bienes Personales (ARCA)", "informativo": True},
            {"id": "debitos_creditos", "nombre": "Impuesto a los débitos y créditos bancarios", "informativo": True},
        ],
        "pago_inmediato": {"nombre": "Transferencias 3.0", "texto": "Transferencias 3.0 (CBU/CVU/alias)"},
        "banco_central": {"sigla": "BCRA", "nombre": "Banco Central de la República Argentina", "tasa_referencia": "Tasa de política monetaria"},
        "ley_datos": {"nombre": "Ley 25.326 de Protección de los Datos Personales", "autoridad": "Agencia de Acceso a la Información Pública (AAIP)"},
        "formatos_extracto": ["pdf_con_clave", "excel_csv"],
        "palabras_extracto": _PALABRAS_EXTRACTO_ES + ["resumen de cuenta"],
        "bancos": [
            _b("Mercado Pago", popular=True, tipo="billetera"), _b("Ualá", popular=True, tipo="billetera"),
            _b("Brubank", popular=True), _b("Banco Galicia", popular=True), _b("Santander Argentina"),
            _b("BBVA Argentina"), _b("Naranja X", tipo="billetera"), _b("Banco Nación"), _b("Banco Macro"),
            _b("Banco Provincia"), _b("ICBC Argentina"), _b("Personal Pay", tipo="billetera"),
        ],
    },
    "UY": {
        "codigo": "UY", "nombre": "Uruguay", "estado": "basico", "disponible": True,
        "moneda": "UYU", "simbolo": "$", "decimales": 2, "locale": "es-UY",
        "zona_horaria": "America/Montevideo", "idioma": "es-UY", "tratamiento": "vos",
        "separador_miles": ".", "separador_decimal": ",",
        "unidad_tributaria": {"sigla": "BPC", "nombre": "Base de Prestaciones y Contribuciones"},
        "funciones_fiscales": ["declaracion_anual_informativa"],
        "impuestos": [{"id": "declaracion_anual_informativa", "nombre": "IRPF (DGI)", "informativo": True}],
        "pago_inmediato": {"nombre": "Transferencia", "texto": "transferencia bancaria"},
        "banco_central": {"sigla": "BCU", "nombre": "Banco Central del Uruguay", "tasa_referencia": "Tasa de política monetaria"},
        "ley_datos": {"nombre": "Ley 18.331 de Protección de Datos Personales", "autoridad": "Unidad Reguladora y de Control de Datos Personales (URCDP)"},
        "formatos_extracto": ["pdf_con_clave", "excel_csv"],
        "palabras_extracto": _PALABRAS_EXTRACTO_ES,
        "bancos": [
            _b("BROU", popular=True), _b("Santander Uruguay", popular=True), _b("Itaú Uruguay", popular=True),
            _b("BBVA Uruguay"), _b("Scotiabank Uruguay"), _b("Prex", tipo="billetera"), _b("Mercado Pago", tipo="billetera"),
        ],
    },
    "EC": {
        "codigo": "EC", "nombre": "Ecuador", "estado": "basico", "disponible": True,
        "moneda": "USD", "simbolo": "$", "decimales": 2, "locale": "es-EC",
        "zona_horaria": "America/Guayaquil", "idioma": "es-EC", "tratamiento": "tu",
        "separador_miles": ".", "separador_decimal": ",",
        "unidad_tributaria": {"sigla": "FB", "nombre": "Fracción básica desgravada"},
        "funciones_fiscales": ["declaracion_anual_informativa"],
        "impuestos": [
            {"id": "declaracion_anual_informativa", "nombre": "Impuesto a la renta (SRI)", "informativo": True, "mes": 3},
            {"id": "isd", "nombre": "Impuesto a la salida de divisas (ISD)", "informativo": True},
        ],
        "pago_inmediato": {"nombre": "Transferencia", "texto": "transferencia interbancaria"},
        "banco_central": {"sigla": "BCE", "nombre": "Banco Central del Ecuador", "tasa_referencia": "Tasas referenciales"},
        "ley_datos": {"nombre": "Ley Orgánica de Protección de Datos Personales (2021)", "autoridad": "Superintendencia de Protección de Datos Personales"},
        "formatos_extracto": ["pdf_con_clave", "excel_csv"],
        "palabras_extracto": _PALABRAS_EXTRACTO_ES,
        "bancos": [
            _b("Banco Pichincha", popular=True), _b("Banco del Pacífico", popular=True),
            _b("Produbanco", popular=True), _b("Banco de Guayaquil", popular=True),
            _b("Banco Bolivariano"), _b("Banco Internacional"), _b("Deuna", tipo="billetera"),
        ],
    },
    "PA": {
        "codigo": "PA", "nombre": "Panamá", "estado": "basico", "disponible": True,
        "moneda": "USD", "simbolo": "$", "decimales": 2, "locale": "es-PA",
        "zona_horaria": "America/Panama", "idioma": "es-PA", "tratamiento": "tu",
        "separador_miles": ",", "separador_decimal": ".",
        "unidad_tributaria": {"sigla": "", "nombre": ""},
        "funciones_fiscales": ["declaracion_anual_informativa"],
        "impuestos": [{"id": "declaracion_anual_informativa", "nombre": "Impuesto sobre la renta (DGI)", "informativo": True, "mes": 3}],
        "pago_inmediato": {"nombre": "ACH / Yappy", "texto": "ACH o Yappy"},
        "banco_central": {"sigla": "SBP", "nombre": "Superintendencia de Bancos de Panamá", "tasa_referencia": ""},
        "ley_datos": {"nombre": "Ley 81 de 2019 de Protección de Datos Personales", "autoridad": "ANTAI"},
        "formatos_extracto": ["pdf_con_clave", "excel_csv"],
        "palabras_extracto": _PALABRAS_EXTRACTO_ES,
        "bancos": [
            _b("Banco General", popular=True), _b("Banistmo", popular=True), _b("Global Bank"),
            _b("BAC Panamá"), _b("Banco Nacional de Panamá"), _b("Yappy", tipo="billetera", popular=True),
        ],
    },
    "CR": {
        "codigo": "CR", "nombre": "Costa Rica", "estado": "basico", "disponible": True,
        "moneda": "CRC", "simbolo": "₡", "decimales": 0, "locale": "es-CR",
        "zona_horaria": "America/Costa_Rica", "idioma": "es-CR", "tratamiento": "tu",
        "separador_miles": " ", "separador_decimal": ",",
        "unidad_tributaria": {"sigla": "", "nombre": ""},
        "funciones_fiscales": ["declaracion_anual_informativa"],
        "impuestos": [{"id": "declaracion_anual_informativa", "nombre": "Impuesto sobre la renta (Hacienda)", "informativo": True}],
        "pago_inmediato": {"nombre": "SINPE Móvil", "texto": "SINPE Móvil"},
        "banco_central": {"sigla": "BCCR", "nombre": "Banco Central de Costa Rica", "tasa_referencia": "Tasa de política monetaria"},
        "ley_datos": {"nombre": "Ley 8968 de Protección de la Persona frente al tratamiento de sus datos personales", "autoridad": "PRODHAB"},
        "formatos_extracto": ["pdf_con_clave", "excel_csv"],
        "palabras_extracto": _PALABRAS_EXTRACTO_ES,
        "bancos": [
            _b("Banco Nacional de Costa Rica", popular=True), _b("BAC Credomatic", popular=True),
            _b("Banco de Costa Rica", popular=True), _b("Scotiabank Costa Rica"), _b("Davivienda Costa Rica"),
            _b("SINPE Móvil", tipo="billetera"),
        ],
    },
    "BR": {
        # Fase posterior: requiere portugués (pt-BR). No aparece en el selector hasta entonces.
        "codigo": "BR", "nombre": "Brasil", "estado": "pendiente_idioma", "disponible": False,
        "moneda": "BRL", "simbolo": "R$", "decimales": 2, "locale": "pt-BR",
        "zona_horaria": "America/Sao_Paulo", "idioma": "pt-BR", "tratamiento": "voce",
        "separador_miles": ".", "separador_decimal": ",",
        "unidad_tributaria": {"sigla": "", "nombre": ""},
        "funciones_fiscales": ["declaracion_anual_informativa"],
        "impuestos": [{"id": "declaracion_anual_informativa", "nombre": "Imposto de Renda Pessoa Física (IRPF)", "informativo": True, "mes": 5}],
        "pago_inmediato": {"nombre": "PIX", "texto": "PIX"},
        "banco_central": {"sigla": "BCB", "nombre": "Banco Central do Brasil", "tasa_referencia": "Selic"},
        "ley_datos": {"nombre": "LGPD (Lei 13.709/2018)", "autoridad": "ANPD"},
        "formatos_extracto": ["pdf_con_clave", "excel_csv", "ofx"],
        "palabras_extracto": ["extrato", "fatura"],
        "bancos": [
            _b("Nubank", popular=True, tipo="billetera"), _b("Itaú", popular=True), _b("Bradesco", popular=True),
            _b("Banco do Brasil", popular=True), _b("Caixa", popular=True), _b("Santander Brasil"), _b("Inter"),
            _b("C6 Bank"), _b("Mercado Pago", tipo="billetera"), _b("PicPay", tipo="billetera"),
        ],
    },
}

# Orden en que se ofrecen en el selector (el resto del mundo va al final).
ORDEN = ["CO", "MX", "CL", "PE", "AR", "UY", "EC", "PA", "CR", "BR"]


def pais_valido(codigo: str | None) -> bool:
    return bool(codigo) and codigo in PAISES and PAISES[codigo]["disponible"]


def config_pais(codigo: str | None) -> dict | None:
    """La configuración de un país, o None si no es uno de los soportados (nunca cae a CO)."""
    return PAISES.get((codigo or "").upper())


def tiene_funcion(codigo: str | None, funcion: str) -> bool:
    """¿Esta función fiscal aplica en este país? Un país desconocido no tiene ninguna."""
    c = config_pais(codigo)
    return bool(c and funcion in c["funciones_fiscales"])


def dominios_del_pais(codigo: str | None) -> dict[str, str]:
    """dominio -> nombre del banco, solo para ese país (los de CO viven en extractos_gmail)."""
    c = config_pais(codigo)
    if not c:
        return {}
    return {d: b["nombre"] for b in c["bancos"] for d in b["dominios"]}


def todos_los_dominios() -> dict[str, str]:
    """Remitentes de todos los países excepto CO. Un dominio repetido conserva el primero."""
    out: dict[str, str] = {}
    for cod in ORDEN:
        if cod == "CO":
            continue
        for d, n in dominios_del_pais(cod).items():
            out.setdefault(d, n)
    return out


def sugerir_pais(idioma_navegador: str | None, zona_horaria: str | None) -> str | None:
    """Sugerencia (NUNCA decisión): zona horaria y, si no, la región del idioma del navegador.
    Sin IP ni geolocalización. None si no hay una pista clara; la persona siempre confirma."""
    if zona_horaria:
        for cod, c in PAISES.items():
            if c["disponible"] and c["zona_horaria"] == zona_horaria:
                return cod
    if idioma_navegador and "-" in idioma_navegador:
        region = idioma_navegador.split("-")[-1].upper()
        if pais_valido(region):
            return region
    return None


def catalogo_publico() -> list[dict]:
    """Lo que el selector necesita (sin bancos completos): país, moneda, formato y estado."""
    claves = ("codigo", "nombre", "estado", "moneda", "simbolo", "decimales", "locale", "zona_horaria",
              "idioma", "tratamiento", "funciones_fiscales")
    return [{k: PAISES[c][k] for k in claves} for c in ORDEN if PAISES[c]["disponible"]]


def pais_de_usuario(db, usuario_id: str) -> str:
    """País guardado del usuario. Perfiles anteriores sin país (todos eran de Colombia) -> CO.
    Si la columna aún no existe en la base, también CO (comportamiento de siempre)."""
    try:
        from app.models import Perfil

        p = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
        cod = getattr(p, "pais", None) if p else None
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        cod = None
    return cod if pais_valido(cod) else PAIS_POR_DEFECTO_LEGADO
