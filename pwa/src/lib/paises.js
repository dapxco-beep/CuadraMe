// GENERADO desde backend/app/paises.py con `python tools/generar_paises_js.py`. NO editar a mano:
// cambia el registro en Python y regenera (tests/test_paises.py verifica la paridad).
// Un solo lugar con lo que cambia de un país a otro: moneda, formato, bancos, funciones fiscales.
export const PAISES = {
  "CO": {
    "codigo": "CO",
    "nombre": "Colombia",
    "estado": "completo",
    "disponible": true,
    "moneda": "COP",
    "simbolo": "$",
    "decimales": 0,
    "locale": "es-CO",
    "zona_horaria": "America/Bogota",
    "idioma": "es-CO",
    "tratamiento": "tu",
    "separador_miles": ".",
    "separador_decimal": ",",
    "unidad_tributaria": {
      "sigla": "UVT",
      "nombre": "Unidad de Valor Tributario"
    },
    "funciones_fiscales": [
      "renta_dian",
      "gmf",
      "uvt"
    ],
    "impuestos": [
      {
        "id": "renta_dian",
        "nombre": "Declaración de renta (DIAN)",
        "informativo": false
      },
      {
        "id": "gmf",
        "nombre": "Gravamen a los movimientos financieros (4x1000)",
        "informativo": false
      }
    ],
    "pago_inmediato": {
      "nombre": "Bre-B",
      "texto": "Bre-B (llaves)"
    },
    "banco_central": {
      "sigla": "BanRep",
      "nombre": "Banco de la República",
      "tasa_referencia": "Tasa de usura / IBR"
    },
    "ley_datos": {
      "nombre": "Ley 1581 de 2012",
      "autoridad": "Superintendencia de Industria y Comercio (SIC)"
    },
    "formatos_extracto": [
      "pdf_con_clave",
      "excel_csv"
    ],
    "palabras_extracto": [
      "extracto",
      "estado de cuenta",
      "resumen de cuenta",
      "resumen mensual"
    ],
    "bancos": [
      {
        "nombre": "Bancolombia",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Davivienda",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "BBVA Colombia",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco de Bogotá",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco de Occidente",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Popular",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Caja Social",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco AV Villas",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Scotiabank Colpatria",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Itaú",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Falabella",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Pichincha",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Agrario",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco W",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Bancamía",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Mibanco",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Coltefinanciera",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Finandina",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Serfinanza",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Bancoomeva",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Confiar",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Cotrafá",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Tuya",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Nequi",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Daviplata",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Nu Colombia",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Lulo Bank",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Movii",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "RappiPay",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "RappiCard",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Ualá",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Tpaga",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Dale!",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      }
    ]
  },
  "MX": {
    "codigo": "MX",
    "nombre": "México",
    "estado": "inicial",
    "disponible": true,
    "moneda": "MXN",
    "simbolo": "$",
    "decimales": 2,
    "locale": "es-MX",
    "zona_horaria": "America/Mexico_City",
    "idioma": "es-MX",
    "tratamiento": "tu",
    "separador_miles": ",",
    "separador_decimal": ".",
    "unidad_tributaria": {
      "sigla": "UMA",
      "nombre": "Unidad de Medida y Actualización"
    },
    "funciones_fiscales": [
      "declaracion_anual_informativa"
    ],
    "impuestos": [
      {
        "id": "declaracion_anual_informativa",
        "nombre": "Declaración anual de personas físicas (SAT)",
        "informativo": true,
        "mes": 4
      }
    ],
    "pago_inmediato": {
      "nombre": "SPEI",
      "texto": "SPEI / CoDi"
    },
    "banco_central": {
      "sigla": "Banxico",
      "nombre": "Banco de México",
      "tasa_referencia": "TIIE / tasa objetivo"
    },
    "ley_datos": {
      "nombre": "Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP, texto de 2025)",
      "autoridad": "Secretaría Anticorrupción y Buen Gobierno"
    },
    "formatos_extracto": [
      "pdf_con_clave",
      "excel_csv"
    ],
    "palabras_extracto": [
      "extracto",
      "estado de cuenta",
      "resumen de cuenta",
      "resumen mensual",
      "estado de cuenta"
    ],
    "bancos": [
      {
        "nombre": "BBVA México",
        "mono": "BBVA",
        "bg": "#072146",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "bbva.mx",
          "bbva.com.mx"
        ],
        "alias": [
          "bbva",
          "bancomer"
        ]
      },
      {
        "nombre": "Banorte",
        "mono": "BN",
        "bg": "#EB0029",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "banorte.com"
        ],
        "alias": []
      },
      {
        "nombre": "Santander México",
        "mono": "SAN",
        "bg": "#EC0000",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "santander.com.mx"
        ],
        "alias": [
          "santander"
        ]
      },
      {
        "nombre": "Citibanamex",
        "mono": "CB",
        "bg": "#056DAE",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "banamex.com",
          "citibanamex.com"
        ],
        "alias": [
          "banamex"
        ]
      },
      {
        "nombre": "HSBC México",
        "mono": "HS",
        "bg": "#DB0011",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "hsbc.com.mx"
        ],
        "alias": [
          "hsbc"
        ]
      },
      {
        "nombre": "Scotiabank México",
        "mono": "SC",
        "bg": "#EC111A",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "scotiabank.com.mx"
        ],
        "alias": []
      },
      {
        "nombre": "Inbursa",
        "mono": "IN",
        "bg": "#0033A0",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "inbursa.com"
        ],
        "alias": []
      },
      {
        "nombre": "Banco Azteca",
        "mono": "AZ",
        "bg": "#00A94F",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "bancoazteca.com.mx"
        ],
        "alias": []
      },
      {
        "nombre": "Nu México",
        "mono": "Nu",
        "bg": "#820AD1",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "billetera",
        "dominios": [
          "nu.com.mx"
        ],
        "alias": [
          "nu",
          "nubank"
        ]
      },
      {
        "nombre": "Mercado Pago",
        "mono": "MP",
        "bg": "#00B1EA",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "billetera",
        "dominios": [
          "mercadopago.com.mx",
          "mercadopago.com"
        ],
        "alias": [
          "mercadopago"
        ]
      },
      {
        "nombre": "Spin by OXXO",
        "mono": "SP",
        "bg": "#E4002B",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "billetera",
        "dominios": [
          "spinbyoxxo.com.mx"
        ],
        "alias": [
          "spin"
        ]
      },
      {
        "nombre": "Hey Banco",
        "mono": "HB",
        "bg": "#000000",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "heybanco.com"
        ],
        "alias": [
          "hey"
        ]
      },
      {
        "nombre": "Klar",
        "mono": "K",
        "bg": "#1A1A1A",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "billetera",
        "dominios": [
          "klar.mx"
        ],
        "alias": []
      },
      {
        "nombre": "Stori",
        "mono": "ST",
        "bg": "#6C2BD9",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "billetera",
        "dominios": [
          "storicard.com"
        ],
        "alias": []
      },
      {
        "nombre": "Ualá México",
        "mono": "U",
        "bg": "#2D2D2D",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "billetera",
        "dominios": [
          "uala.mx"
        ],
        "alias": [
          "uala"
        ]
      }
    ]
  },
  "CL": {
    "codigo": "CL",
    "nombre": "Chile",
    "estado": "inicial",
    "disponible": true,
    "moneda": "CLP",
    "simbolo": "$",
    "decimales": 0,
    "locale": "es-CL",
    "zona_horaria": "America/Santiago",
    "idioma": "es-CL",
    "tratamiento": "tu",
    "separador_miles": ".",
    "separador_decimal": ",",
    "unidad_tributaria": {
      "sigla": "UTM",
      "nombre": "Unidad Tributaria Mensual"
    },
    "funciones_fiscales": [
      "declaracion_anual_informativa"
    ],
    "impuestos": [
      {
        "id": "declaracion_anual_informativa",
        "nombre": "Operación Renta (SII)",
        "informativo": true,
        "mes": 4
      }
    ],
    "pago_inmediato": {
      "nombre": "Transferencia",
      "texto": "transferencia electrónica"
    },
    "banco_central": {
      "sigla": "BCCh",
      "nombre": "Banco Central de Chile",
      "tasa_referencia": "Tasa de política monetaria (TPM)"
    },
    "ley_datos": {
      "nombre": "Ley 19.628 (vigente) y Ley 21.719 (entra en vigencia el 1 dic 2026; hay proyecto para postergarla)",
      "autoridad": "Agencia de Protección de Datos Personales (en constitución)"
    },
    "formatos_extracto": [
      "pdf_con_clave",
      "excel_csv"
    ],
    "palabras_extracto": [
      "extracto",
      "estado de cuenta",
      "resumen de cuenta",
      "resumen mensual",
      "cartola",
      "estado de cuenta"
    ],
    "bancos": [
      {
        "nombre": "BancoEstado",
        "mono": "BE",
        "bg": "#F26B21",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "bancoestado.cl"
        ],
        "alias": [
          "cuentarut",
          "cuenta rut"
        ]
      },
      {
        "nombre": "Banco de Chile",
        "mono": "BCh",
        "bg": "#003595",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "bancochile.cl",
          "bancoedwards.cl"
        ],
        "alias": [
          "edwards"
        ]
      },
      {
        "nombre": "Santander Chile",
        "mono": "SAN",
        "bg": "#EC0000",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "santander.cl"
        ],
        "alias": [
          "santander"
        ]
      },
      {
        "nombre": "BCI",
        "mono": "BCI",
        "bg": "#00A0DF",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "bci.cl"
        ],
        "alias": []
      },
      {
        "nombre": "Scotiabank Chile",
        "mono": "SC",
        "bg": "#EC111A",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "scotiabank.cl"
        ],
        "alias": []
      },
      {
        "nombre": "Itaú Chile",
        "mono": "IT",
        "bg": "#FF6200",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "itau.cl"
        ],
        "alias": [
          "itau"
        ]
      },
      {
        "nombre": "Banco Falabella",
        "mono": "F",
        "bg": "#00B14F",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "bancofalabella.cl"
        ],
        "alias": [
          "falabella"
        ]
      },
      {
        "nombre": "Banco Ripley",
        "mono": "R",
        "bg": "#7A2E8E",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "bancoripley.cl"
        ],
        "alias": [
          "ripley"
        ]
      },
      {
        "nombre": "Banco Security",
        "mono": "SE",
        "bg": "#00457C",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "bancosecurity.cl"
        ],
        "alias": []
      },
      {
        "nombre": "Mach",
        "mono": "M",
        "bg": "#6B2FD9",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "billetera",
        "dominios": [
          "somosmach.com",
          "mach.cl"
        ],
        "alias": []
      },
      {
        "nombre": "Tenpo",
        "mono": "T",
        "bg": "#00D3AB",
        "fg": "#0A0F2C",
        "popular": true,
        "tipo": "billetera",
        "dominios": [
          "tenpo.cl"
        ],
        "alias": []
      },
      {
        "nombre": "Mercado Pago",
        "mono": "MP",
        "bg": "#00B1EA",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "billetera",
        "dominios": [
          "mercadopago.cl"
        ],
        "alias": [
          "mercadopago"
        ]
      },
      {
        "nombre": "Fintual",
        "mono": "Fi",
        "bg": "#1B3A5C",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "billetera",
        "dominios": [
          "fintual.cl"
        ],
        "alias": []
      }
    ]
  },
  "PE": {
    "codigo": "PE",
    "nombre": "Perú",
    "estado": "inicial",
    "disponible": true,
    "moneda": "PEN",
    "simbolo": "S/",
    "decimales": 2,
    "locale": "es-PE",
    "zona_horaria": "America/Lima",
    "idioma": "es-PE",
    "tratamiento": "tu",
    "separador_miles": ",",
    "separador_decimal": ".",
    "unidad_tributaria": {
      "sigla": "UIT",
      "nombre": "Unidad Impositiva Tributaria"
    },
    "funciones_fiscales": [
      "declaracion_anual_informativa"
    ],
    "impuestos": [
      {
        "id": "declaracion_anual_informativa",
        "nombre": "Declaración anual de renta (SUNAT)",
        "informativo": true,
        "mes": 3
      },
      {
        "id": "itf",
        "nombre": "Impuesto a las Transacciones Financieras (ITF)",
        "informativo": true
      }
    ],
    "pago_inmediato": {
      "nombre": "Yape / Plin",
      "texto": "Yape o Plin"
    },
    "banco_central": {
      "sigla": "BCRP",
      "nombre": "Banco Central de Reserva del Perú",
      "tasa_referencia": "Tasa de referencia"
    },
    "ley_datos": {
      "nombre": "Ley 29733 de Protección de Datos Personales",
      "autoridad": "Autoridad Nacional de Protección de Datos Personales (MINJUSDH)"
    },
    "formatos_extracto": [
      "pdf_con_clave",
      "excel_csv"
    ],
    "palabras_extracto": [
      "extracto",
      "estado de cuenta",
      "resumen de cuenta",
      "resumen mensual",
      "estado de cuenta"
    ],
    "bancos": [
      {
        "nombre": "BCP",
        "mono": "BCP",
        "bg": "#002A8D",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "viabcp.com",
          "bcp.com.pe"
        ],
        "alias": [
          "banco de credito",
          "yape"
        ]
      },
      {
        "nombre": "Interbank",
        "mono": "IB",
        "bg": "#00A651",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "interbank.pe"
        ],
        "alias": [
          "plin"
        ]
      },
      {
        "nombre": "BBVA Perú",
        "mono": "BBVA",
        "bg": "#072146",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "bbva.pe"
        ],
        "alias": [
          "bbva"
        ]
      },
      {
        "nombre": "Scotiabank Perú",
        "mono": "SC",
        "bg": "#EC111A",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "banco",
        "dominios": [
          "scotiabank.com.pe"
        ],
        "alias": []
      },
      {
        "nombre": "Banco de la Nación",
        "mono": "BN",
        "bg": "#C8102E",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "bn.com.pe"
        ],
        "alias": []
      },
      {
        "nombre": "Mibanco",
        "mono": "MB",
        "bg": "#D91F5C",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "mibanco.com.pe"
        ],
        "alias": []
      },
      {
        "nombre": "Banco Pichincha",
        "mono": "BP",
        "bg": "#FFD100",
        "fg": "#003DA5",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "pichincha.pe"
        ],
        "alias": []
      },
      {
        "nombre": "Banco Falabella",
        "mono": "F",
        "bg": "#00B14F",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "banco",
        "dominios": [
          "bancofalabella.pe"
        ],
        "alias": [
          "falabella"
        ]
      },
      {
        "nombre": "Yape",
        "mono": "Y",
        "bg": "#742384",
        "fg": "#ffffff",
        "popular": true,
        "tipo": "billetera",
        "dominios": [
          "yape.com.pe"
        ],
        "alias": []
      },
      {
        "nombre": "Plin",
        "mono": "P",
        "bg": "#00C2A8",
        "fg": "#0A0F2C",
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Mercado Pago",
        "mono": "MP",
        "bg": "#00B1EA",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "billetera",
        "dominios": [
          "mercadopago.com.pe"
        ],
        "alias": [
          "mercadopago"
        ]
      },
      {
        "nombre": "Ualá Perú",
        "mono": "U",
        "bg": "#2D2D2D",
        "fg": "#ffffff",
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": [
          "uala"
        ]
      }
    ]
  },
  "AR": {
    "codigo": "AR",
    "nombre": "Argentina",
    "estado": "basico",
    "disponible": true,
    "moneda": "ARS",
    "simbolo": "$",
    "decimales": 2,
    "locale": "es-AR",
    "zona_horaria": "America/Argentina/Buenos_Aires",
    "idioma": "es-AR",
    "tratamiento": "vos",
    "separador_miles": ".",
    "separador_decimal": ",",
    "unidad_tributaria": {
      "sigla": "MNI",
      "nombre": "Mínimo no imponible (Ganancias)"
    },
    "funciones_fiscales": [
      "declaracion_anual_informativa"
    ],
    "impuestos": [
      {
        "id": "declaracion_anual_informativa",
        "nombre": "Ganancias y Bienes Personales (ARCA)",
        "informativo": true
      },
      {
        "id": "debitos_creditos",
        "nombre": "Impuesto a los débitos y créditos bancarios",
        "informativo": true
      }
    ],
    "pago_inmediato": {
      "nombre": "Transferencias 3.0",
      "texto": "Transferencias 3.0 (CBU/CVU/alias)"
    },
    "banco_central": {
      "sigla": "BCRA",
      "nombre": "Banco Central de la República Argentina",
      "tasa_referencia": "Tasa de política monetaria"
    },
    "ley_datos": {
      "nombre": "Ley 25.326 de Protección de los Datos Personales",
      "autoridad": "Agencia de Acceso a la Información Pública (AAIP)"
    },
    "formatos_extracto": [
      "pdf_con_clave",
      "excel_csv"
    ],
    "palabras_extracto": [
      "extracto",
      "estado de cuenta",
      "resumen de cuenta",
      "resumen mensual",
      "resumen de cuenta"
    ],
    "bancos": [
      {
        "nombre": "Mercado Pago",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Ualá",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Brubank",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Galicia",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Santander Argentina",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "BBVA Argentina",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Naranja X",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Nación",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Macro",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Provincia",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "ICBC Argentina",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Personal Pay",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      }
    ]
  },
  "UY": {
    "codigo": "UY",
    "nombre": "Uruguay",
    "estado": "basico",
    "disponible": true,
    "moneda": "UYU",
    "simbolo": "$",
    "decimales": 2,
    "locale": "es-UY",
    "zona_horaria": "America/Montevideo",
    "idioma": "es-UY",
    "tratamiento": "vos",
    "separador_miles": ".",
    "separador_decimal": ",",
    "unidad_tributaria": {
      "sigla": "BPC",
      "nombre": "Base de Prestaciones y Contribuciones"
    },
    "funciones_fiscales": [
      "declaracion_anual_informativa"
    ],
    "impuestos": [
      {
        "id": "declaracion_anual_informativa",
        "nombre": "IRPF (DGI)",
        "informativo": true
      }
    ],
    "pago_inmediato": {
      "nombre": "Transferencia",
      "texto": "transferencia bancaria"
    },
    "banco_central": {
      "sigla": "BCU",
      "nombre": "Banco Central del Uruguay",
      "tasa_referencia": "Tasa de política monetaria"
    },
    "ley_datos": {
      "nombre": "Ley 18.331 de Protección de Datos Personales",
      "autoridad": "Unidad Reguladora y de Control de Datos Personales (URCDP)"
    },
    "formatos_extracto": [
      "pdf_con_clave",
      "excel_csv"
    ],
    "palabras_extracto": [
      "extracto",
      "estado de cuenta",
      "resumen de cuenta",
      "resumen mensual"
    ],
    "bancos": [
      {
        "nombre": "BROU",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Santander Uruguay",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Itaú Uruguay",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "BBVA Uruguay",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Scotiabank Uruguay",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Prex",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Mercado Pago",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      }
    ]
  },
  "EC": {
    "codigo": "EC",
    "nombre": "Ecuador",
    "estado": "basico",
    "disponible": true,
    "moneda": "USD",
    "simbolo": "$",
    "decimales": 2,
    "locale": "es-EC",
    "zona_horaria": "America/Guayaquil",
    "idioma": "es-EC",
    "tratamiento": "tu",
    "separador_miles": ".",
    "separador_decimal": ",",
    "unidad_tributaria": {
      "sigla": "FB",
      "nombre": "Fracción básica desgravada"
    },
    "funciones_fiscales": [
      "declaracion_anual_informativa"
    ],
    "impuestos": [
      {
        "id": "declaracion_anual_informativa",
        "nombre": "Impuesto a la renta (SRI)",
        "informativo": true,
        "mes": 3
      },
      {
        "id": "isd",
        "nombre": "Impuesto a la salida de divisas (ISD)",
        "informativo": true
      }
    ],
    "pago_inmediato": {
      "nombre": "Transferencia",
      "texto": "transferencia interbancaria"
    },
    "banco_central": {
      "sigla": "BCE",
      "nombre": "Banco Central del Ecuador",
      "tasa_referencia": "Tasas referenciales"
    },
    "ley_datos": {
      "nombre": "Ley Orgánica de Protección de Datos Personales (2021)",
      "autoridad": "Superintendencia de Protección de Datos Personales"
    },
    "formatos_extracto": [
      "pdf_con_clave",
      "excel_csv"
    ],
    "palabras_extracto": [
      "extracto",
      "estado de cuenta",
      "resumen de cuenta",
      "resumen mensual"
    ],
    "bancos": [
      {
        "nombre": "Banco Pichincha",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco del Pacífico",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Produbanco",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco de Guayaquil",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Bolivariano",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Internacional",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Deuna",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      }
    ]
  },
  "PA": {
    "codigo": "PA",
    "nombre": "Panamá",
    "estado": "basico",
    "disponible": true,
    "moneda": "USD",
    "simbolo": "$",
    "decimales": 2,
    "locale": "es-PA",
    "zona_horaria": "America/Panama",
    "idioma": "es-PA",
    "tratamiento": "tu",
    "separador_miles": ",",
    "separador_decimal": ".",
    "unidad_tributaria": {
      "sigla": "",
      "nombre": ""
    },
    "funciones_fiscales": [
      "declaracion_anual_informativa"
    ],
    "impuestos": [
      {
        "id": "declaracion_anual_informativa",
        "nombre": "Impuesto sobre la renta (DGI)",
        "informativo": true,
        "mes": 3
      }
    ],
    "pago_inmediato": {
      "nombre": "ACH / Yappy",
      "texto": "ACH o Yappy"
    },
    "banco_central": {
      "sigla": "SBP",
      "nombre": "Superintendencia de Bancos de Panamá",
      "tasa_referencia": ""
    },
    "ley_datos": {
      "nombre": "Ley 81 de 2019 de Protección de Datos Personales",
      "autoridad": "ANTAI"
    },
    "formatos_extracto": [
      "pdf_con_clave",
      "excel_csv"
    ],
    "palabras_extracto": [
      "extracto",
      "estado de cuenta",
      "resumen de cuenta",
      "resumen mensual"
    ],
    "bancos": [
      {
        "nombre": "Banco General",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banistmo",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Global Bank",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "BAC Panamá",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco Nacional de Panamá",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Yappy",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      }
    ]
  },
  "CR": {
    "codigo": "CR",
    "nombre": "Costa Rica",
    "estado": "basico",
    "disponible": true,
    "moneda": "CRC",
    "simbolo": "₡",
    "decimales": 0,
    "locale": "es-CR",
    "zona_horaria": "America/Costa_Rica",
    "idioma": "es-CR",
    "tratamiento": "tu",
    "separador_miles": " ",
    "separador_decimal": ",",
    "unidad_tributaria": {
      "sigla": "",
      "nombre": ""
    },
    "funciones_fiscales": [
      "declaracion_anual_informativa"
    ],
    "impuestos": [
      {
        "id": "declaracion_anual_informativa",
        "nombre": "Impuesto sobre la renta (Hacienda)",
        "informativo": true
      }
    ],
    "pago_inmediato": {
      "nombre": "SINPE Móvil",
      "texto": "SINPE Móvil"
    },
    "banco_central": {
      "sigla": "BCCR",
      "nombre": "Banco Central de Costa Rica",
      "tasa_referencia": "Tasa de política monetaria"
    },
    "ley_datos": {
      "nombre": "Ley 8968 de Protección de la Persona frente al tratamiento de sus datos personales",
      "autoridad": "PRODHAB"
    },
    "formatos_extracto": [
      "pdf_con_clave",
      "excel_csv"
    ],
    "palabras_extracto": [
      "extracto",
      "estado de cuenta",
      "resumen de cuenta",
      "resumen mensual"
    ],
    "bancos": [
      {
        "nombre": "Banco Nacional de Costa Rica",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "BAC Credomatic",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco de Costa Rica",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Scotiabank Costa Rica",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Davivienda Costa Rica",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "SINPE Móvil",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      }
    ]
  },
  "BR": {
    "codigo": "BR",
    "nombre": "Brasil",
    "estado": "pendiente_idioma",
    "disponible": false,
    "moneda": "BRL",
    "simbolo": "R$",
    "decimales": 2,
    "locale": "pt-BR",
    "zona_horaria": "America/Sao_Paulo",
    "idioma": "pt-BR",
    "tratamiento": "voce",
    "separador_miles": ".",
    "separador_decimal": ",",
    "unidad_tributaria": {
      "sigla": "",
      "nombre": ""
    },
    "funciones_fiscales": [
      "declaracion_anual_informativa"
    ],
    "impuestos": [
      {
        "id": "declaracion_anual_informativa",
        "nombre": "Imposto de Renda Pessoa Física (IRPF)",
        "informativo": true,
        "mes": 5
      }
    ],
    "pago_inmediato": {
      "nombre": "PIX",
      "texto": "PIX"
    },
    "banco_central": {
      "sigla": "BCB",
      "nombre": "Banco Central do Brasil",
      "tasa_referencia": "Selic"
    },
    "ley_datos": {
      "nombre": "LGPD (Lei 13.709/2018)",
      "autoridad": "ANPD"
    },
    "formatos_extracto": [
      "pdf_con_clave",
      "excel_csv",
      "ofx"
    ],
    "palabras_extracto": [
      "extrato",
      "fatura"
    ],
    "bancos": [
      {
        "nombre": "Nubank",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Itaú",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Bradesco",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Banco do Brasil",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Caixa",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": true,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Santander Brasil",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Inter",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "C6 Bank",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "banco",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "Mercado Pago",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      },
      {
        "nombre": "PicPay",
        "mono": null,
        "bg": null,
        "fg": null,
        "popular": false,
        "tipo": "billetera",
        "dominios": [],
        "alias": []
      }
    ]
  }
}

export const ORDEN = ["CO", "MX", "CL", "PE", "AR", "UY", "EC", "PA", "CR", "BR"]

export const PAIS_POR_DEFECTO_LEGADO = 'CO'

export function paisValido(codigo) {
  return !!codigo && !!PAISES[codigo] && PAISES[codigo].disponible
}

// Un país desconocido NO cae a Colombia: devuelve null (el que llama decide).
export function configPais(codigo) {
  return PAISES[String(codigo || '').toUpperCase()] || null
}

export function tieneFuncion(codigo, funcion) {
  const c = configPais(codigo)
  return !!c && c.funciones_fiscales.includes(funcion)
}

export function paisesDisponibles() {
  return ORDEN.filter((c) => PAISES[c].disponible).map((c) => PAISES[c])
}

export function bancosDePais(codigo) {
  return (configPais(codigo) || { bancos: [] }).bancos
}

// Sugerencia (nunca decisión): zona horaria o región del idioma. Sin IP ni geolocalización.
export function sugerirPais(idiomaNavegador, zonaHoraria) {
  if (zonaHoraria) {
    const hit = Object.values(PAISES).find((c) => c.disponible && c.zona_horaria === zonaHoraria)
    if (hit) return hit.codigo
  }
  if (idiomaNavegador && idiomaNavegador.includes('-')) {
    const region = idiomaNavegador.split('-').pop().toUpperCase()
    if (paisValido(region)) return region
  }
  return null
}
