"""Piezas PURAS de la lista «Todos los extractos»: de qué MES es un extracto, de qué TIPO (cuenta o
tarjeta), por qué NO se pudo leer y cómo se dice cada cosa en lenguaje llano.

La regla de oro de la pantalla: cada fila dice banco + tipo + mes, su estado y una frase honesta de
lo que pasó. Aquí vive la parte que no toca la base de datos (se prueba sin ella).

── De qué mes es un extracto (en este orden; gana la primera fuente que lo sepa) ──────────────────
  1. periodo      el periodo guardado en el extracto («julio 2026», «01/07/2026 a 31/07/2026»).
  2. asunto       el asunto del correo («Tu extracto de julio»; sin año vale el del correo).
  3. archivo      el nombre del archivo: «Extracto_julio_2026.pdf» dice el mes; una fecha suelta
                  («2026-08-04») vale su mes, SALVO en Nu (ver abajo).
  4. lineas       las fechas de los movimientos leídos (el mes de la última): es lo que dice el banco.
  5. recepcion    el mes anterior a la fecha en que llegó el correo (los bancos mandan el extracto al
                  cerrar el periodo). Es una suposición: se marca «deducido» y se puede corregir.
  Si nada sirve: «Mes por confirmar» con un selector para fijarlo.
  (Las líneas van ANTES que la recepción: es un dato del banco, y la recepción siempre «responde»,
  así que si fuera antes nunca se usarían las líneas.)

── Regla de Nu ────────────────────────────────────────────────────────────────────────────────────
  Los PDF de Nu se llaman «Nu_AAAA-MM-DD.pdf» y esa fecha es la FECHA DE PAGO / de envío, no el
  periodo. El extracto que llega el 4 de agosto es el del corte anterior (julio). Por eso, para Nu,
  una fecha en el nombre del archivo vale el MES ANTERIOR.
"""
from __future__ import annotations

import re
from datetime import datetime

from app.extractos_conciliados import mes_del_extracto, periodo_en_asunto
from app.extractos_gmail import _sin_acentos

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]
_MES_CORTO = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

FUENTE_PERIODO, FUENTE_ASUNTO, FUENTE_ARCHIVO = "periodo", "asunto", "archivo"
FUENTE_LINEAS, FUENTE_RECEPCION = "lineas", "recepcion"
# Las que se pueden guardar en ExtractoCorreo.periodo sin miedo (la recepción es solo una suposición).
FUENTES_SEGURAS = (FUENTE_PERIODO, FUENTE_ASUNTO, FUENTE_ARCHIVO, FUENTE_LINEAS)

_FECHA_ARCHIVO = re.compile(r"(?<!\d)(20\d{2})[-_.](\d{1,2})[-_.](\d{1,2})(?!\d)|(?<!\d)(\d{1,2})[-_.](\d{1,2})[-_.](20\d{2})(?!\d)")
_CLAVE_MES = re.compile(r"^(20\d{2})-(0[1-9]|1[0-2])$")


def mes_anterior(clave: str) -> str:
    a, m = int(clave[:4]), int(clave[5:7])
    return f"{a - 1:04d}-12" if m == 1 else f"{a:04d}-{m - 1:02d}"


def es_nu(banco: str | None, remitente: str = "", archivo: str = "") -> bool:
    texto = _sin_acentos(f"{banco or ''} {remitente or ''} {archivo or ''}")
    return bool(re.search(r"(^|[^a-z])nu([^a-z]|$)|nubank", texto))


def _fecha_de_archivo(archivo: str) -> tuple[int, int] | None:
    """(año, mes) de una fecha escrita en el nombre del archivo; None si no hay o es imposible."""
    m = _FECHA_ARCHIVO.search(archivo or "")
    if not m:
        return None
    if m.group(1):
        a, mes, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        d, mes, a = int(m.group(4)), int(m.group(5)), int(m.group(6))
    if not (1 <= mes <= 12 and 1 <= d <= 31):
        return None
    return a, mes


def mes_de_archivo(archivo: str, *, banco: str = "", remitente: str = "", recibido_en: datetime | None = None) -> str | None:
    """Mes que dice el nombre del archivo. Una fecha suelta de Nu es la de pago: vale el mes anterior."""
    f = _fecha_de_archivo(archivo)
    if f:
        clave = f"{f[0]:04d}-{f[1]:02d}"
        return mes_anterior(clave) if es_nu(banco, remitente, archivo) else clave
    nombre = _sin_acentos(re.sub(r"[_\-.]+", " ", archivo or ""))
    return mes_del_extracto(periodo_en_asunto(nombre, recibido_en), None)


def mes_de_texto_periodo(periodo: str) -> str | None:
    """Mes de un periodo guardado, SIN inventar nada a partir de la fecha del correo."""
    return mes_del_extracto(periodo or "", None)


def deducir_periodo(*, periodo: str = "", asunto: str = "", archivo: str = "", recibido_en: datetime | None = None,
                    mes_lineas: str | None = None, banco: str = "", remitente: str = "") -> dict:
    """{'mes': 'AAAA-MM' | None, 'fuente': ..., 'deducido': bool}. Ver el orden en la cabecera del módulo."""
    mes = mes_de_texto_periodo(periodo)
    if mes:
        return {"mes": mes, "fuente": FUENTE_PERIODO, "deducido": False}
    mes = mes_del_extracto(periodo_en_asunto(asunto, recibido_en), None)
    if mes:
        return {"mes": mes, "fuente": FUENTE_ASUNTO, "deducido": False}
    mes = mes_de_archivo(archivo, banco=banco, remitente=remitente, recibido_en=recibido_en)
    if mes:
        return {"mes": mes, "fuente": FUENTE_ARCHIVO, "deducido": False}
    if mes_lineas and _CLAVE_MES.match(mes_lineas):
        return {"mes": mes_lineas, "fuente": FUENTE_LINEAS, "deducido": False}
    if recibido_en:
        mes = mes_del_extracto("", recibido_en)
        if mes:
            return {"mes": mes, "fuente": FUENTE_RECEPCION, "deducido": True}
    return {"mes": None, "fuente": None, "deducido": True}


def periodo_texto(mes: str) -> str:
    """'2026-07' -> 'julio 2026': el formato que ExtractoCorreo.periodo ya entiende (mes_del_extracto)."""
    if not _CLAVE_MES.match(mes or ""):
        raise ValueError("mes inválido")
    return f"{MESES[int(mes[5:7]) - 1]} {mes[:4]}"


def etiqueta_mes(mes: str | None) -> str:
    """'2026-07' -> 'Julio 2026'; sin mes: 'Mes por confirmar'."""
    if not mes or not _CLAVE_MES.match(mes):
        return "Mes por confirmar"
    return f"{MESES[int(mes[5:7]) - 1].capitalize()} {mes[:4]}"


def fecha_corta(iso: str | None) -> str:
    """'2026-07-14' -> '14 jul 2026'; '' si no es una fecha."""
    try:
        d = datetime.strptime((iso or "")[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return f"{d.day} {_MES_CORTO[d.month - 1]} {d.year}"


def corte_del_periodo(periodo: str) -> str:
    """Si el periodo guardado es un rango («01/06/2026 a 14/07/2026»), la fecha final en AAAA-MM-DD; si no, ''."""
    fechas = []
    for m in re.finditer(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", periodo or ""):
        fechas.append((int(m.group(3)), int(m.group(2)), int(m.group(1))))
    if not fechas:
        for m in re.finditer(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", periodo or ""):
            fechas.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    if not fechas:
        return ""
    a, mes, d = fechas[-1]
    try:
        return datetime(a, mes, d).strftime("%Y-%m-%d")
    except ValueError:
        return ""


# ── Tipo: cuenta o tarjeta ─────────────────────────────────────────────────────────────────────
def tipo_de_extracto(cuenta_tipo: str | None, *textos: str) -> str:
    """'tarjeta' | 'cuenta' | ''. Manda la cuenta del usuario; sin cuenta se mira lo que dicen el asunto o el
    archivo; si no se sabe, '' (la fila no inventa)."""
    if cuenta_tipo:
        return "tarjeta" if cuenta_tipo == "credito" else "cuenta"
    t = _sin_acentos(" ".join(textos))
    if "tarjeta" in t or "credit card" in t:
        return "tarjeta"
    if re.search(r"cuenta|ahorro|nomina|corriente", t):
        return "cuenta"
    return ""


def nombre_corto_banco(banco: str) -> str:
    """'Nu Colombia' -> 'Nu' (para «Tarjeta Nu»)."""
    return re.sub(r"\s+colombia$", "", (banco or "").strip(), flags=re.IGNORECASE) or (banco or "")


def banco_para_titulo(banco: str, cuenta: str = "") -> str:
    """Nombre del banco para el título. Lo detectado en el PDF viene en minúscula o genérico («nu», «generico»):
    en ese caso se usa el nombre de la cuenta de la persona (o el banco con mayúscula inicial)."""
    b = (banco or "").strip()
    if b and b.lower() not in ("generico", "desconocido") and not b.islower():
        return b
    if cuenta:
        return cuenta
    return "" if b.lower() in ("generico", "desconocido") else b.capitalize()


def titulo_extracto(*, banco: str, tipo: str, mes: str | None, corte: str = "") -> str:
    """Lo primero que se lee en la fila. «Nu Colombia · Cuenta · Julio 2026» /
    «Tarjeta Nu · corte 14 jul 2026» (tarjeta con fecha de corte conocida)."""
    banco = (banco or "").strip() or "Banco sin identificar"
    if tipo == "tarjeta" and corte and fecha_corta(corte):
        return f"Tarjeta {nombre_corto_banco(banco)} · corte {fecha_corta(corte)}"
    partes = [banco]
    if tipo:
        partes.append("Tarjeta" if tipo == "tarjeta" else "Cuenta")
    partes.append(etiqueta_mes(mes))
    return " · ".join(partes)


# ── Estados de la lista ────────────────────────────────────────────────────────────────────────
REVISADO, POR_REVISAR, SIN_PROCESAR = "revisado", "por_revisar", "sin_procesar"
NECESITA_CLAVE, NO_SE_PUDO_LEER, ANTERIOR = "necesita_clave", "no_se_pudo_leer", "anterior_al_inicio"
# Orden de importancia al contar y al ofrecer filtros.
ESTADOS_VISTA = (POR_REVISAR, NECESITA_CLAVE, NO_SE_PUDO_LEER, SIN_PROCESAR, REVISADO, ANTERIOR)

ETIQUETA_ESTADO = {
    REVISADO: "Revisado", POR_REVISAR: "Por revisar", NECESITA_CLAVE: "Necesita clave",
    NO_SE_PUDO_LEER: "No se pudo leer", SIN_PROCESAR: "Sin procesar", ANTERIOR: "Anterior a tu fecha de inicio",
}


def estado_de_vista(estado: str, tiene_revision: bool) -> str:
    """Estado interno (estado_traer) -> el de la lista. «Por revisar» solo si ya se leyó y faltan líneas;
    un extracto que llegó y nadie ha abierto es «Sin procesar»."""
    if estado in ("al_dia", "sin_movimientos_reales"):
        return REVISADO
    if estado == "por_revisar":
        return POR_REVISAR if tiene_revision else SIN_PROCESAR
    return {"necesita_clave": NECESITA_CLAVE, "no_se_pudo_leer": NO_SE_PUDO_LEER,
            "anterior_al_inicio": ANTERIOR}.get(estado, SIN_PROCESAR)


def frase_contadores(cuentas: dict[str, int]) -> str:
    """«6 revisados · 3 con clave pendiente · 4 sin procesar · 3 con error». Solo lo que no es cero."""
    def n(clave, uno, varios):
        c = cuentas.get(clave, 0)
        return f"{c} {uno if c == 1 else varios}" if c else ""
    partes = [
        n(REVISADO, "revisado", "revisados"), n(POR_REVISAR, "por revisar", "por revisar"),
        n(NECESITA_CLAVE, "con clave pendiente", "con clave pendiente"), n(SIN_PROCESAR, "sin procesar", "sin procesar"),
        n(NO_SE_PUDO_LEER, "con error", "con error"), n(ANTERIOR, "anterior al inicio", "anteriores al inicio"),
    ]
    return " · ".join(p for p in partes if p)


# ── Por qué no se pudo leer ────────────────────────────────────────────────────────────────────
# código -> (qué pasó, siguiente paso). Nunca «error» a secas (GUIA_DE_TEXTOS).
MOTIVOS = {
    "clave_faltante": ("el PDF tiene clave y no tenemos una guardada",
                       "Guarda la clave del PDF (casi siempre es tu cédula) y toca «Probar la clave»."),
    "clave_incorrecta": ("la clave guardada no abrió el PDF",
                         "Revisa la clave del PDF y toca «Probar la clave»."),
    "formato_no_reconocido": ("no reconocimos el formato de este extracto",
                              "Toca «Mi banco no está» para que lo revisemos, o agrega los movimientos a mano."),
    "pdf_escaneado": ("el PDF es una imagen y no trae texto que podamos leer",
                      "Descarga el extracto en Excel o CSV desde tu banco y súbelo, o agrega los movimientos a mano."),
    "archivo_vacio": ("el archivo llegó vacío o dañado",
                      "Toca «Intentar de nuevo»; si sigue igual, descárgalo otra vez desde tu banco."),
    "error_temporal": ("hubo un problema momentáneo al descargarlo",
                       "Toca «Intentar de nuevo» en un rato."),
}
FRASE_SIN_MOTIVO = "No se pudo leer (motivo no guardado)"
PASO_SIN_MOTIVO = "Toca «Intentar de nuevo»."


def clasificar_motivo(*, texto: str = "", pide_clave: bool = False, clave_dada: bool = False,
                      pdf_vacio: bool = False, sin_senales: bool = False, hay_texto_pdf: bool | None = None) -> str:
    """Código de MOTIVOS para un archivo del que no salieron movimientos. Pura.
    pide_clave: el PDF está cifrado · clave_dada: se probó con alguna clave · pdf_vacio: 0 bytes ·
    sin_senales: tiene texto pero no parece un extracto de ningún banco."""
    if pdf_vacio:
        return "archivo_vacio"
    if pide_clave:
        return "clave_incorrecta" if clave_dada else "clave_faltante"
    if not (texto or "").strip():
        return "pdf_escaneado"
    return "formato_no_reconocido"


def texto_motivo(codigo: str | None) -> tuple[str, str]:
    """(qué pasó, siguiente paso) del motivo; con código desconocido o vacío, el texto de «motivo no guardado»."""
    if codigo in MOTIVOS:
        return MOTIVOS[codigo]
    return ("", PASO_SIN_MOTIVO)


def frase_error(codigo: str | None) -> str:
    """«No pudimos leer este extracto: <motivo>. <paso>» o el texto de los errores antiguos."""
    if codigo in MOTIVOS:
        que, paso = MOTIVOS[codigo]
        return f"No pudimos leer este extracto: {que}. {paso}"
    return f"{FRASE_SIN_MOTIVO}. {PASO_SIN_MOTIVO}"


# ── La frase de resultado ──────────────────────────────────────────────────────────────────────
def _n(c: int, uno: str, varios: str) -> str:
    return f"{c} {uno if c == 1 else varios}"


def frase_resultado(vista: str, conteo: dict, *, clave_estado: str | None = None, motivo: str | None = None,
                    copias: int = 1) -> str:
    """Lo que pasó con ESE extracto, dicho claro. Nunca «0 movimientos coinciden con el banco»."""
    if vista == NO_SE_PUDO_LEER:
        return frase_error(motivo)
    if vista == NECESITA_CLAVE:
        if clave_estado == "no_abrio":
            return "La clave guardada no abrió este PDF. Revísala y toca «Probar la clave»."
        return "Está protegido con clave. Guarda la clave del PDF para poder leerlo."
    if vista == ANTERIOR:
        return "Es anterior a tu fecha de inicio, así que no se trae."
    if vista == SIN_PROCESAR:
        return "Llegó a tu correo y aún no lo hemos leído. Toca «Revisar» para traer sus movimientos."
    leidas, ya, nuevas, falta = (conteo.get(k, 0) for k in ("leidas", "ya_estaban", "nuevas_agregadas", "por_revisar"))
    if leidas == 0:
        return "No encontramos movimientos en este extracto."
    cab = f"Leímos {_n(leidas, 'movimiento', 'movimientos')}: "
    if vista == POR_REVISAR:
        return cab + f"{ya} ya estaban y {_n(falta, 'falta registrar', 'faltan por registrar')}."
    if nuevas == 0:
        return cab + (f"{ya} ya estaban registrados, 0 nuevos." if ya != 1 else "1 ya estaba registrado, 0 nuevos.")
    return cab + (f"{_n(nuevas, 'nuevo agregado', 'nuevos agregados')}, {ya} ya estaban.")


RAZON_SIN_ADJUNTO = "El correo habla de un extracto pero no trae el PDF adjunto (o el archivo no parece un extracto)."


def estado_corto(vista: str, conteo: dict, *, clave_estado: str | None = None) -> str:
    """Una frase corta y fija por extracto (lo primero que se lee en la fila):
    «Conciliado ✓ · 37 movimientos», «Falta importar 5», «No se pudo leer: falta la clave del PDF»."""
    leidas, falta = conteo.get("leidas", 0), conteo.get("por_revisar", 0)
    if vista == NECESITA_CLAVE:
        return "No se pudo leer: la clave del PDF no abrió" if clave_estado == "no_abrio" else "No se pudo leer: falta la clave del PDF"
    if vista == NO_SE_PUDO_LEER:
        return "No se pudo leer el archivo"
    if vista == ANTERIOR:
        return "Anterior a tu fecha de inicio"
    if vista == SIN_PROCESAR:
        return "Sin revisar todavía"
    if vista == POR_REVISAR:
        return f"Falta importar {falta}" if falta else "Falta revisarlo"
    return f"Conciliado ✓ · {_n(leidas, 'movimiento', 'movimientos')}"
