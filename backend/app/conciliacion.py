"""
Conciliación de extractos bancarios: detección de banco, parsers regex,
fingerprinting y matching contra el libro mayor (ledger).
Migrado de PdfReconciliation.js y zzProduction.js.
"""
import hashlib
import re
import unicodedata
from datetime import datetime, timedelta

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

NOMBRE_PROPIO = re.compile(r"\bDaniel\b", re.IGNORECASE)


def detectar_banco(texto: str) -> str:
    t = texto.lower()
    if re.search(r"nequi.*bancolombia|bancolombia.*nequi|nequi", t):
        return "nequi"
    if re.search(r"nu bank|nubank|nu colombia|cuenta nu", t):
        return "nu"
    if re.search(r"bancolombia", t):
        return "bancolombia"
    if re.search(r"davivienda", t):
        return "davivienda"
    if re.search(r"bbva", t):
        return "bbva"
    if re.search(r"scotiabank|colpatria", t):
        return "scotiabank"
    if re.search(r"av villas", t):
        return "avvillas"
    if re.search(r"banco de bogota|bogota", t):
        return "bogota"
    return "generico"


def parse_monto_cop(valor: str) -> float:
    if not valor:
        return float("nan")
    limpio = re.sub(r"[+\-$\s]", "", str(valor))
    limpio = limpio.replace(".", "").replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return float("nan")


def es_transferencia_propia(desc: str) -> bool:
    if re.search(r"BRE-?B", desc, re.IGNORECASE) and NOMBRE_PROPIO.search(desc):
        return True
    if re.search(r"enviaste\s+a\s+Daniel", desc, re.IGNORECASE):
        return True
    if re.search(r"\b(nequi|nu|daviplata)\b", desc, re.IGNORECASE) and re.search(
        r"\b(enviaste\s+a|recibiste\s+de|traslado|desde|hacia)\b", desc, re.IGNORECASE
    ):
        return True
    return False


def _tipo_por_signo(monto: float, desc: str) -> str:
    if es_transferencia_propia(desc):
        return "transfer"
    if re.search(r"gravamen", desc, re.IGNORECASE):
        return "expense"
    return "income" if monto > 0 else "expense"


def parse_texto_con_regex(texto: str) -> list[dict]:
    """Intenta parsers específicos por banco; retorna [] si ninguno matchea."""
    anio_match = re.search(r"\b(20\d{2})\b", texto)
    anio = anio_match.group(1) if anio_match else str(datetime.utcnow().year)
    banco = detectar_banco(texto)
    movimientos: list[dict] = []

    if banco in ("nequi", "generico"):
        movimientos = _parse_nequi(texto)

    if not movimientos and banco in ("nu", "nequi", "generico"):
        movimientos = _parse_nu(texto, anio)

    if not movimientos and banco == "bancolombia":
        movimientos = _parse_bancolombia(texto)

    if not movimientos and banco in ("davivienda", "bbva", "avvillas", "bogota", "scotiabank"):
        movimientos = _parse_davivienda_generico(texto)

    if not movimientos and banco == "generico":
        movimientos = _parse_bancolombia(texto) or _parse_davivienda_generico(texto)

    if not movimientos:
        movimientos = _parse_generico(texto)

    return movimientos


def _parse_nequi(texto: str) -> list[dict]:
    movimientos = []
    patron_a = re.compile(
        r"(\d{2})/(\d{2})/(\d{4})\s+(.+?)\s+\$(-?[\d,]+\.?\d*)\s+\$([\d,]+\.?\d*)", re.MULTILINE
    )
    for m in patron_a.finditer(texto):
        desc = m.group(4).strip()
        if re.search(r"fecha|descripci[oó]n|valor|saldo", desc, re.IGNORECASE):
            continue
        try:
            monto = float(m.group(5).replace(",", ""))
        except ValueError:
            continue
        if monto == 0:
            continue
        fecha = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        tipo = _tipo_por_signo(monto, desc)
        movimientos.append({
            "fecha": fecha, "descripcion": desc, "monto": abs(monto),
            "tipo": tipo, "referencia": "", "saldo": None,
        })

    if movimientos:
        return movimientos

    lineas = [l.strip() for l in texto.split("\n") if l.strip()]
    i = 0
    while i < len(lineas):
        fecha_m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", lineas[i])
        if fecha_m:
            desc, monto_str = "", ""
            for j in range(i + 1, min(i + 5, len(lineas))):
                monto_m = re.match(r"^\$(-?[\d,]+\.?\d*)$", lineas[j])
                if monto_m:
                    monto_str = monto_m.group(1)
                    desc = " ".join(lineas[i + 1:j]).strip()
                    i = j + 1
                    break
            if not desc or not monto_str or re.search(r"fecha|descripci[oó]n|valor|saldo", desc, re.IGNORECASE):
                i += 1
                continue
            try:
                monto = float(monto_str.replace(",", ""))
            except ValueError:
                i += 1
                continue
            if monto == 0:
                i += 1
                continue
            fecha = f"{fecha_m.group(3)}-{fecha_m.group(2)}-{fecha_m.group(1)}"
            movimientos.append({
                "fecha": fecha, "descripcion": desc, "monto": abs(monto),
                "tipo": _tipo_por_signo(monto, desc), "referencia": "", "saldo": None,
            })
        else:
            i += 1
    return movimientos


def _parse_nu(texto: str, anio: str) -> list[dict]:
    movimientos = []
    patron = re.compile(
        r"(\d{1,2})\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\.?\s+(.+?)\s+([+\-]?)\s*\$?\s*([\d][\d.,]*\d|\d)\b",
        re.IGNORECASE,
    )
    for m in patron.finditer(texto):
        mes = MESES.get(m.group(2).lower())
        if not mes:
            continue
        monto_str = m.group(4) + m.group(5)
        monto = parse_monto_cop(monto_str)
        if monto != monto or abs(monto) < 1:  # NaN check
            continue
        desc = m.group(3).strip()
        if re.search(r"saldo|total|per[ií]odo|extracto|n[uú]mero de cuenta|^cuenta\b", desc, re.IGNORECASE):
            continue
        if not m.group(4) and abs(monto) < 100:
            continue
        signo = -1 if m.group(4) == "-" else 1
        tipo = "transfer" if es_transferencia_propia(desc) else ("income" if signo > 0 else "expense")
        movimientos.append({
            "fecha": f"{anio}-{mes:02d}-{int(m.group(1)):02d}",
            "descripcion": desc, "monto": abs(monto), "tipo": tipo,
            "referencia": "", "saldo": None,
        })
    return movimientos


def _parse_bancolombia(texto: str) -> list[dict]:
    movimientos = []
    patron = re.compile(
        r"(\d{2})[/\-](\d{2})[/\-](\d{2,4})\s{2,}(.+?)\s{2,}([\d.,]+)?\s{2,}([\d.,]+)?\s{2,}([\d.,]+)",
        re.MULTILINE,
    )
    for m in patron.finditer(texto):
        anio = "20" + m.group(3) if len(m.group(3)) == 2 else m.group(3)
        desc = m.group(4).strip()
        debito = parse_monto_cop(m.group(5)) if m.group(5) else 0
        credito = parse_monto_cop(m.group(6)) if m.group(6) else 0
        if debito == 0 and credito == 0:
            continue
        monto = debito if debito > 0 else credito
        tipo = "income" if credito > 0 else ("transfer" if re.search(r"transfer", desc, re.IGNORECASE) else "expense")
        movimientos.append({
            "fecha": f"{anio}-{m.group(2)}-{m.group(1)}",
            "descripcion": desc, "monto": abs(monto), "tipo": tipo,
            "referencia": "", "saldo": None,
        })
    return movimientos


def _parse_davivienda_generico(texto: str) -> list[dict]:
    movimientos = []
    patron = re.compile(r"(\d{2})[/\-](\d{2})[/\-](\d{2,4})\s+(.+?)\s+([\-]?\$?[\d.,]+)\s*$", re.MULTILINE)
    for m in patron.finditer(texto):
        anio = "20" + m.group(3) if len(m.group(3)) == 2 else m.group(3)
        desc = m.group(4).strip()
        monto = parse_monto_cop(m.group(5))
        if monto != monto or monto == 0:
            continue
        movimientos.append({
            "fecha": f"{anio}-{m.group(2)}-{m.group(1)}",
            "descripcion": desc, "monto": abs(monto),
            "tipo": "expense" if monto < 0 else "income",
            "referencia": "", "saldo": None,
        })
    return movimientos


def _parse_generico(texto: str) -> list[dict]:
    movimientos = []
    patron = re.compile(r"(\d{2})[/\-](\d{2})[/\-](\d{2,4})\s+(.+?)\s+([\-]?[\d.,]+)\s*$", re.MULTILINE)
    for m in patron.finditer(texto):
        anio = "20" + m.group(3) if len(m.group(3)) == 2 else m.group(3)
        desc = m.group(4).strip()
        monto = parse_monto_cop(m.group(5))
        if monto != monto or monto == 0:
            continue
        movimientos.append({
            "fecha": f"{anio}-{m.group(2)}-{m.group(1)}",
            "descripcion": desc, "monto": abs(monto),
            "tipo": "expense" if monto < 0 else "income",
            "referencia": "", "saldo": None,
        })
    return movimientos


# ── Normalización, fingerprint y matching ──────────────────────────


def normalize_texto(valor: str) -> str:
    texto = str(valor or "").strip().lower()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    texto = re.sub(r"[^a-z0-9 ]", "", texto)
    return texto.strip()


def parse_bank_date(valor) -> datetime | None:
    if isinstance(valor, datetime):
        return valor
    if not valor:
        return None
    s = str(valor).strip()
    iso = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", s)
    if iso:
        return datetime(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    latam = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})$", s)
    if latam:
        anio = int(latam.group(3))
        anio = 2000 + anio if anio < 100 else anio
        return datetime(anio, int(latam.group(2)), int(latam.group(1)))
    return None


def compute_fingerprint(fecha, monto: float, cuenta: str, descripcion: str, tipo: str) -> str:
    fecha_dt = parse_bank_date(fecha) if not isinstance(fecha, datetime) else fecha
    date_key = fecha_dt.strftime("%Y-%m-%d") if fecha_dt else "sin-fecha"
    amount_key = f"{abs(monto):.2f}"
    account_key = normalize_texto(cuenta)
    desc_key = normalize_texto(descripcion)
    raw = "|".join([date_key, amount_key, account_key, desc_key, tipo])
    return hashlib.md5(raw.encode()).hexdigest()


def find_approx_match(ledger: list[dict], movimiento: dict) -> dict | None:
    """Busca el movimiento del ledger más cercano (±3 días, ±5% monto)."""
    fecha_obj = parse_bank_date(movimiento.get("fecha"))
    target_date = fecha_obj.timestamp() if fecha_obj else 0
    target_amount = abs(movimiento.get("monto", 0))
    max_diff_seconds = 3 * 86400
    amount_tolerance = max(500, target_amount * 0.05)

    best_match, best_score = None, float("inf")
    for row in ledger:
        row_date = row.get("fecha")
        if not row_date:
            continue
        row_amount = abs(row.get("monto", 0))
        date_diff = abs(row_date.timestamp() - target_date)
        if date_diff > max_diff_seconds:
            continue
        amount_diff = abs(row_amount - target_amount)
        if amount_diff > amount_tolerance:
            continue
        score = (date_diff / 86400) + (amount_diff / max(target_amount, 1)) * 3
        if score < best_score:
            best_score = score
            best_match = row
    return best_match


def auditar_movimientos(movimientos_extracto: list[dict], ledger: list[dict]) -> dict:
    """
    Compara movimientos del extracto contra el ledger existente.
    Clasifica cada uno como: exacto (fingerprint/fecha+monto igual),
    aproximado (dentro de tolerancia), o faltante (no está registrado).
    """
    review = []
    exactos = aproximados = faltantes = 0

    ledger_por_fingerprint = {r["fingerprint"]: r for r in ledger if r.get("fingerprint")}

    for mov in movimientos_extracto:
        fecha_dt = parse_bank_date(mov.get("fecha"))
        fp = compute_fingerprint(fecha_dt, mov["monto"], mov.get("cuenta", ""), mov["descripcion"], mov["tipo"])

        if fp in ledger_por_fingerprint:
            review.append({**mov, "fingerprint": fp, "estado": "exacto"})
            exactos += 1
            continue

        aproximado = find_approx_match(ledger, {**mov, "fecha": fecha_dt})
        if aproximado:
            review.append({**mov, "fingerprint": fp, "estado": "aproximado", "match_id": aproximado.get("id")})
            aproximados += 1
        else:
            review.append({**mov, "fingerprint": fp, "estado": "faltante"})
            faltantes += 1

    return {
        "review": review,
        "total_movimientos": len(movimientos_extracto),
        "exactos": exactos,
        "aproximados": aproximados,
        "faltantes": faltantes,
    }
