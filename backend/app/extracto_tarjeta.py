"""
Lee los datos de un EXTRACTO DE TARJETA DE CRÉDITO (texto de un PDF o de un correo):
cupo total, cupo disponible, pago total, pago mínimo, fecha límite de pago, fecha de
corte y tasa efectiva anual.

Diseño: es TOLERANTE y CONSERVADOR. Busca por etiquetas (sin importar mayúsculas ni
tildes), lee el monto o la fecha que viene justo después y descarta lo que no cuadra
(p. ej. pago mínimo mayor que el total, cupo disponible mayor que el cupo). Devuelve solo
lo que encontró con confianza: si una etiqueta no aparece o su valor es dudoso, esa clave
no está en el resultado. NUNCA aplica nada: solo propone (ver proponer_actualizacion).

Limitación honesta: está probado con textos de ejemplo de 3 estilos, no con extractos
reales de cada banco. Si un banco pone las etiquetas en una fila y los valores en otra
(tabla en columnas), no las asocia y simplemente no devuelve ese dato.
"""
import re
import unicodedata
from datetime import date

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}
_MES_RE = r"(?:ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic)[a-z]*"

# clave -> etiquetas (ya sin tildes y en minúscula), de la más a la menos específica.
ETIQUETAS_MONTO = {
    "cupo_total": ["cupo total", "cupo aprobado", "cupo autorizado", "cupo de credito", "limite de credito"],
    "cupo_disponible": ["cupo disponible", "disponible para compras", "cupo libre", "disponible para avances"],
    "pago_total": ["pago total", "valor total a pagar", "total a pagar", "pago para no generar intereses",
                   "pago de contado", "pago contado"],
    "pago_minimo": ["pago minimo", "valor minimo a pagar", "minimo a pagar", "pago min"],
}
ETIQUETAS_FECHA = {
    "fecha_limite_pago": ["fecha limite de pago", "fecha limite pago", "fecha maxima de pago", "pague hasta",
                          "pagar hasta", "pagar antes del", "fecha de vencimiento", "vence el"],
    "fecha_corte": ["fecha de corte", "fecha corte", "fecha de cierre", "corte del extracto"],
}
ETIQUETAS_TASA = ["tasa efectiva anual", "tasa e.a", "tasa ea", "interes efectivo anual", "tasa de interes efectiva anual"]


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[ \t\r\f\v ]+", " ", t.lower())


def _a_numero(tok: str) -> float | None:
    """'1.234.567' / '1.234.567,89' / '1,234,567.89' / '12\'000.000' / '1234567' -> float."""
    tok = tok.replace("'", ".").strip(".,")  # 12'000.000 (apóstrofo de millones) = 12.000.000
    if not tok:
        return None
    tiene_punto, tiene_coma = "." in tok, "," in tok
    if tiene_punto and tiene_coma:
        decimal = "." if tok.rfind(".") > tok.rfind(",") else ","
        miles = "," if decimal == "." else "."
        tok = tok.replace(miles, "").replace(decimal, ".")
    elif tiene_punto or tiene_coma:
        sep = "." if tiene_punto else ","
        partes = tok.split(sep)
        # 1.234.567 o 5.000 -> miles; 1234,5 o 27.86 -> decimal
        if len(partes) > 2 or (len(partes[-1]) == 3 and 1 <= len(partes[0]) <= 3):
            tok = "".join(partes)
        else:
            tok = tok.replace(sep, ".")
    try:
        return float(tok)
    except ValueError:
        return None


_NUM = re.compile(r"(\$)?\s*(\d[\d.,']*)")


def _monto_en(ventana: str) -> float | None:
    """Primer monto plausible de la ventana: con signo $, con separadores de miles o de
    5+ dígitos. Descarta lo que parece parte de una fecha (30 de oct, 05/11/2026)."""
    for m in _NUM.finditer(ventana):
        signo, tok = m.group(1), m.group(2)
        resto = ventana[m.end():m.end() + 14]
        if re.match(r"\s*(?:de\s+)?" + _MES_RE, resto) or re.match(r"[/\-]\d", resto) or re.match(r"\s*%", resto):
            continue
        digitos = re.sub(r"\D", "", tok)
        if not (signo or re.search(r"[.,']", tok) or len(digitos) >= 5):
            continue
        valor = _a_numero(tok)
        if valor is not None:
            return round(valor, 2)
    return None


def _fecha_en(ventana: str) -> tuple[int | None, date | None]:
    """(día, fecha completa si trae año) de la primera fecha de la ventana."""
    patrones = [
        (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "iso"),
        (re.compile(r"\b(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{2,4})\b"), "dmy"),
        (re.compile(r"\b(\d{1,2})\s*(?:de\s+)?[/\-]?\s*(" + _MES_RE + r")\.?\s*[/\-]?\s*(?:de[l]?\s+)?(\d{4}|\d{2})?\b"), "texto"),
    ]
    mejor = None
    for rx, tipo in patrones:
        m = rx.search(ventana)
        if m and (mejor is None or m.start() < mejor[0]):
            mejor = (m.start(), m, tipo)
    if not mejor:
        return None, None
    _, m, tipo = mejor
    try:
        if tipo == "iso":
            a, mes, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        elif tipo == "dmy":
            d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
            a = a + 2000 if a < 100 else a
        else:
            d, mes = int(m.group(1)), MESES[m.group(2)[:3]]
            a = m.group(3)
            a = (int(a) + 2000 if len(a) == 2 else int(a)) if a else None
        if not 1 <= d <= 31 or not 1 <= mes <= 12:
            return None, None
        if a is None:
            return d, None
        return d, date(a, mes, d)
    except (ValueError, KeyError):
        return None, None


def _ventana(texto: str, etiquetas: list[str], largo: int = 60):
    """Texto que sigue a la primera etiqueta que aparezca (la más específica gana)."""
    for et in etiquetas:
        m = re.search(r"(?<![a-z])" + re.escape(et).replace(r"\ ", r"\s+") + r"(?![a-z])", texto)
        if m:
            return texto[m.end():m.end() + largo]
    return None


def leer_datos_tarjeta(texto: str) -> dict:
    """Datos del extracto de una tarjeta de crédito. Solo trae las claves que halló con
    confianza: cupo_total, cupo_disponible, pago_total, pago_minimo (montos), fecha_limite_pago y
    fecha_corte (ISO) con su dia_pago / dia_corte, y tasa_ea (% efectivo anual)."""
    t = _norm(texto)
    out: dict = {}

    for clave, etiquetas in ETIQUETAS_MONTO.items():
        v = _ventana(t, etiquetas)
        monto = _monto_en(v) if v else None
        if monto is not None and (monto > 0 or clave in ("pago_total", "pago_minimo")):
            out[clave] = monto

    for clave, etiquetas in ETIQUETAS_FECHA.items():
        v = _ventana(t, etiquetas)
        dia, fecha = _fecha_en(v) if v else (None, None)
        if dia:
            out["dia_pago" if clave == "fecha_limite_pago" else "dia_corte"] = dia
        if fecha:
            out[clave] = fecha.isoformat()

    v = _ventana(t, ETIQUETAS_TASA)
    if v:
        m = re.search(r"(\d{1,3}(?:[.,]\d{1,4})?)\s*%", v) or re.search(r"(\d{1,3}[.,]\d{1,4})\s*(?:e\.?\s?a)", v)
        if m:
            tasa = float(m.group(1).replace(",", "."))  # una tasa nunca lleva separador de miles
            if 0 < tasa <= 100:
                out["tasa_ea"] = round(tasa, 2)

    # Coherencia: si algo no cuadra, se descarta el dato dudoso (mejor nada que algo mal).
    cupo = out.get("cupo_total")
    if cupo and out.get("cupo_disponible", 0) > cupo * 1.01:
        out.pop("cupo_disponible")
    if cupo and out.get("pago_total", 0) > cupo * 1.2:
        out.pop("pago_total")
    if "pago_total" in out and out.get("pago_minimo", 0) > out["pago_total"] * 1.01:
        out.pop("pago_minimo")
    return out


def _pesos(v: float) -> str:
    return "$" + f"{v:,.0f}".replace(",", ".")


def proponer_actualizacion(cuenta, datos: dict) -> dict | None:
    """Compara lo leído con la tarjeta y arma una PROPUESTA (nada se aplica solo).
    Devuelve {cambios, datos, texto} o None si no hay nada útil que proponer.
    `cambios` usa los nombres de campo de la cuenta (cupo_total, dia_corte, dia_pago, tasa_ea)
    y solo trae los que difieren de lo que ya tiene guardado."""
    if not datos:
        return None
    cambios = {}
    for campo in ("cupo_total", "dia_corte", "dia_pago", "tasa_ea"):
        nuevo = datos.get(campo)
        if nuevo is not None and nuevo != getattr(cuenta, campo, None):
            cambios[campo] = nuevo
    partes = []
    if "cupo_total" in datos:
        partes.append(f"cupo {_pesos(datos['cupo_total'])}")
    if "pago_total" in datos:
        partes.append(f"pago total {_pesos(datos['pago_total'])}")
    if "pago_minimo" in datos:
        partes.append(f"pago mínimo {_pesos(datos['pago_minimo'])}")
    if "dia_pago" in datos:
        partes.append(f"vence el {datos['dia_pago']}")
    if not partes:
        return None
    return {
        "cambios": cambios,
        "datos": datos,
        "texto": f"Tu extracto dice: {', '.join(partes)}. ¿Actualizar tu tarjeta?",
    }
