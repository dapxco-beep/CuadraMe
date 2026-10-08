"""
Conciliación de extractos bancarios: detección de banco, parsers regex,
fingerprinting y matching contra el libro mayor (ledger).
Migrado de PdfReconciliation.js y zzProduction.js.
"""
import hashlib
from contextvars import ContextVar
import re
import unicodedata
from datetime import datetime, timedelta

from app.contabilidad import MARCA_TRASLADO_PROPIO
from app.duplicados import Cand, ORIGEN_ATAJO, ORIGEN_EXTRACTO, ORIGEN_MANUAL, emparejar

# El libro que se compara es de UNA sola cuenta: para la regla central todas comparten la misma.
_CUENTA_UNICA = frozenset({"_cuenta"})

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

# Nombre del titular de la cuenta (el usuario que sube el extracto). Sirve para
# reconocer "transferencias propias" (ej. "Enviaste a <mi nombre>"). Es un
# ContextVar para no tener que pasar el nombre por cada parser: cada request
# fija el suyo y no se mezcla con el de otros usuarios que lleguen a la vez.
_nombre_titular: ContextVar[str] = ContextVar("nombre_titular", default="")


def fijar_nombre_titular(nombre: str) -> None:
    """Se llama una vez por request, antes de parsear el extracto."""
    _nombre_titular.set((nombre or "").strip())


def _patron_nombre_propio() -> re.Pattern | None:
    # Solo el primer nombre y el primer apellido: los bancos suelen abreviar o
    # truncar el resto. Con menos de 3 letras se descarta (evita falsos positivos).
    partes = [p for p in re.split(r"\s+", _nombre_titular.get()) if len(p) >= 3][:2]
    if not partes:
        return None
    return re.compile(r"\b(?:" + "|".join(re.escape(p) for p in partes) + r")\b", re.IGNORECASE)


# Palabras que, junto al nombre, no cambian de quién es la cuenta: "Daniel nequi".
_PALABRAS_DE_ENTIDAD = {"nequi", "nu", "daviplata", "bancolombia", "davivienda", "bbva", "cuenta", "ahorros", "bre", "b"}


def _nombre_es_del_titular(desc: str) -> bool:
    """¿La contraparte del movimiento es el propio titular? Con el nombre completo
    (o dos de sus palabras) sí; con solo el primer nombre, solo si ese es TODO lo que
    dice la contraparte ('Enviaste a Daniel nequi'): 'Enviaste a Daniel Gómez' es otra
    persona y debe contar como gasto."""
    palabras = [p for p in re.split(r"\s+", _nombre_titular.get().lower()) if len(p) >= 3]
    if not palabras:
        return False
    desc_n = _sin_tildes_simple(desc).lower()
    contraparte = re.split(r"(?i)\b(?:enviaste a|recibiste de|bre-?b(?: a| de)?:?|para|de)\b", desc_n)[-1]
    tokens = re.findall(r"[a-z]+", contraparte)
    propios = [t for t in tokens if t in {_sin_tildes_simple(p) for p in palabras}]
    if len(set(propios)) >= 2:
        return True
    resto = [t for t in tokens if t not in propios and t not in _PALABRAS_DE_ENTIDAD]
    return bool(propios) and not resto


def _sin_tildes_simple(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")



# Entidades financieras colombianas reconocidas, mapeadas a la "familia" de
# parser cuyo formato de extracto más se les parece. No es necesario un
# parser distinto por cada banco: casi todos exportan un extracto tabular
# (fecha | descripción | valor[es]) que cae en alguna de estas 3 familias.
_BANCOS_FAMILIA_NEQUI = ("nequi", "daviplata", "movii", "rappipay", "rappicard", "uala", "tpaga", "dale")
_BANCOS_FAMILIA_NU = ("nu bank", "nubank", "nu colombia", "cuenta nu", "lulo bank", "lulobank")
_BANCOS_FAMILIA_TABULAR = (
    ("bancolombia", "bancolombia"),
    ("davivienda", "davivienda"),
    ("bbva", "bbva"),
    ("scotiabank", "scotiabank"),
    ("colpatria", "scotiabank"),
    ("av villas", "avvillas"),
    ("banco de bogota", "bogota"),
    ("banco popular", "popular"),
    ("banco de occidente", "occidente"),
    ("caja social", "cajasocial"),
    ("banco falabella", "falabella"),
    ("banco pichincha", "pichincha"),
    ("banco agrario", "agrario"),
    ("itau", "itau"),
    ("itaú", "itau"),
    ("bancamia", "bancamia"),
    ("banco w", "bancow"),
    ("coltefinanciera", "coltefinanciera"),
    ("confiar", "confiar"),
    ("bancoomeva", "bancoomeva"),
    ("banco serfinanza", "serfinanza"),
    ("tuya", "tuya"),
    ("cotrafa", "cotrafa"),
    ("finandina", "finandina"),
    ("mibanco", "mibanco"),
    ("juriscoop", "juriscoop"),
    ("coofinep", "coofinep"),
    ("banco unión", "banco union"),
)


# Entre las marcas de la familia Nequi hay nombres cortos ("dale", "uala") que
# aparecen DENTRO de otras palabras: se buscan como palabra completa.
_RE_FAMILIA_NEQUI = re.compile(r"\b(?:" + "|".join(_BANCOS_FAMILIA_NEQUI) + r")\b")
# Encabezados propios del extracto de cada marca. Valen más que cualquier mención
# suelta: en la lista de movimientos aparecen otros bancos ("Enviaste a ... nequi").
_FIRMA_NEQUI = re.compile(r"dep[oó]sito de bajo monto|extracto de dep[oó]sito")
_FIRMA_NU = re.compile(r"tu dinero al inicio del mes|nu placa\s+n[uú]mero de cuenta|nu financiera")


def _banco_en(t: str) -> str | None:
    if re.search(r"nequi.*bancolombia|bancolombia.*nequi", t):
        return "nequi"
    if _RE_FAMILIA_NEQUI.search(t):
        return "nequi"
    for clave in _BANCOS_FAMILIA_NU:
        if clave in t:
            return "nu"
    for clave, nombre in _BANCOS_FAMILIA_TABULAR:
        if clave in t:
            return nombre
    return None


def detectar_banco(texto: str) -> str:
    t = texto.lower()
    if _FIRMA_NEQUI.search(t[:1500]):
        return "nequi"
    if _FIRMA_NU.search(t[:2500]):
        return "nu"
    # Primero el encabezado (donde el banco se identifica); si no, todo el texto.
    return _banco_en(t[:1500]) or _banco_en(t) or "generico"


# Bancos cuyo extracto sigue el patrón tabular de Davivienda/BBVA/etc.
# (fecha + descripción + un único valor con signo). Se agregan aquí todas
# las entidades de _BANCOS_FAMILIA_TABULAR salvo bancolombia, que tiene su
# propio parser de columnas débito/crédito separadas.
_BANCOS_PARSER_TABULAR_SIMPLE = {nombre for _, nombre in _BANCOS_FAMILIA_TABULAR if nombre != "bancolombia"}


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
    nombre = _patron_nombre_propio()
    if nombre:
        if re.search(r"BRE-?B|enviaste\s+a\s+|recibiste\s+de\s+|\bde:|\bpara\b", desc, re.IGNORECASE):
            # Con el nombre del titular conocido, solo es propia si la contraparte ES el titular.
            return nombre.search(desc) is not None and _nombre_es_del_titular(desc)
    if re.search(r"\b(nequi|nu|daviplata)\b", desc, re.IGNORECASE) and re.search(
        r"\b(enviaste\s+a|recibiste\s+de|traslado|desde|hacia)\b", desc, re.IGNORECASE
    ):
        return True
    return False


def _pista(desc: str) -> dict:
    """{'pista': 'posible_traslado_propio'} cuando la contraparte parece el titular o una cuenta
    propia; {} si no. El movimiento conserva su dirección (income/expense) y mueve saldo."""
    return {"pista": MARCA_TRASLADO_PROPIO} if es_transferencia_propia(desc) else {}


def _tipo_por_signo(monto: float, desc: str) -> str:
    """Siempre con dirección: el signo manda (una transferencia que sale es 'expense', la que
    entra es 'income'); nunca 'transfer'."""
    if re.search(r"gravamen", desc, re.IGNORECASE):
        return "expense"
    return "income" if monto > 0 else "expense"


def _num_es(s: str) -> float:  # 1.234,56
    return float(s.replace(".", "").replace(",", "."))


def _num_en(s: str) -> float:  # 1,234.56
    return float(s.replace(",", ""))


def total_impreso_del_extracto(texto: str) -> float | None:
    """Lo que el propio extracto dice que se movió (entradas + salidas), si trae el
    resumen de Nu ('Lo que entró / salió') o el de Nequi ('Total abonos / cargos').
    None si el extracto no trae un resumen que sepamos leer."""
    try:
        ent = re.search(r"Lo que entró a tu cuenta\s+\+?\$([\d.,]+)", texto)
        sal = re.search(r"Lo que salió de tu cuenta\s+-?\$([\d.,]+)", texto)
        if ent and sal:
            return _num_es(ent.group(1)) + _num_es(sal.group(1))
        ab = re.search(r"Total abonos\s+\$([\d.,]+)", texto)
        ca = re.search(r"Total cargos\s+\$([\d.,]+)", texto)
        if ab and ca:
            return _num_en(ab.group(1)) + _num_en(ca.group(1))
    except ValueError:
        pass
    return None


def cuadra_con_el_resumen(texto: str, movimientos: list[dict]) -> bool | None:
    """¿Lo leído suma lo mismo que dice el resumen del extracto? True/False, o None si el
    extracto no trae resumen. Detecta líneas que se perdieron (o se leyeron de más) sin
    que nadie lo note. Compara entradas + salidas en valor absoluto: no depende de cómo se
    clasificó cada movimiento (transferencia propia, ingreso o gasto)."""
    esperado = total_impreso_del_extracto(texto)
    if esperado is None:
        return None
    leido = sum(abs(m["monto"]) for m in movimientos)
    return abs(leido - esperado) < 1


def parse_texto_con_regex(texto: str) -> tuple[list[dict], int]:
    """Intenta parsers específicos por banco; retorna ([], 0) si ninguno matchea.
    El segundo valor es cuántas líneas parecían un movimiento pero se descartaron
    por ser ambiguas (ej. montos muy pequeños sin signo claro) — se usa para
    avisarle al usuario que el conteo final puede no ser el total real, en vez
    de fallar en silencio."""
    anio_match = re.search(r"\b(20\d{2})\b", texto)
    anio = anio_match.group(1) if anio_match else str(datetime.utcnow().year)
    banco = detectar_banco(texto)
    movimientos: list[dict] = []
    descartados = 0

    if banco in ("nequi", "generico"):
        movimientos, descartados = _parse_nequi_con_perdidas(texto)
        if not movimientos:
            descartados = 0  # no era un extracto de Nequi: lo que contó no vale para los otros lectores

    if not movimientos and banco in ("nu", "nequi", "generico"):
        movimientos, descartados = _parse_nu(texto, anio)

    if not movimientos and banco == "bancolombia":
        movimientos = _parse_bancolombia(texto)

    if not movimientos and banco in _BANCOS_PARSER_TABULAR_SIMPLE:
        movimientos = _parse_davivienda_generico(texto)

    if not movimientos and banco == "generico":
        movimientos = _parse_bancolombia(texto) or _parse_davivienda_generico(texto)

    if not movimientos:
        movimientos = _parse_generico(texto)

    # Si el extracto trae su propio resumen y lo leído no suma lo mismo, falta (o sobra)
    # algo: se avisa con el contador de "descartados" en vez de dejarlo pasar en silencio.
    if movimientos and cuadra_con_el_resumen(texto, movimientos) is False and descartados == 0:
        descartados += 1

    return movimientos, descartados


# Palabras propias de un extracto (cada grupo cuenta una vez). Una carta, una factura o una
# inscripción rara vez traen dos de estos grupos a la vez junto a una tabla de movimientos.
_SENALES_EXTRACTO = (
    r"extracto", r"saldo\s+(?:anterior|inicial|final|disponible|actual)|nuevo saldo",
    r"movimientos?|transacciones", r"d[eé]bitos?|cr[eé]ditos?|abonos?|cargos?",
    r"fecha", r"descripci[oó]n|detalle|concepto", r"valor|monto|importe",
)
MIN_MOVIMIENTOS_GENERICO = 3
MOTIVO_NO_EXTRACTO = "Este archivo no parece un extracto bancario."


def senales_extracto(texto: str) -> int:
    t = (texto or "").lower()
    return sum(1 for s in _SENALES_EXTRACTO if re.search(s, t))


def _fecha_valida(valor) -> datetime | None:
    try:
        return parse_bank_date(valor)
    except ValueError:
        return None


def evaluar_extracto(texto: str, banco: str, movimientos: list[dict]) -> tuple[bool, str]:
    """¿Este texto parece un extracto bancario? Conservador: es mejor pedir confirmación que
    importar basura. Con un banco reconocido se confía (lo demás lo valida el resumen del
    extracto). Con el parser genérico (banco desconocido) se exigen señales de extracto Y una
    tabla coherente: al menos MIN_MOVIMIENTOS_GENERICO líneas con fecha válida, monto y
    descripción, dentro de un rango de fechas razonable (≤ 15 meses)."""
    if banco != "generico":
        return True, ""
    if senales_extracto(texto) < 2:
        return False, MOTIVO_NO_EXTRACTO
    plausibles = []
    for m in movimientos:
        f = _fecha_valida(m.get("fecha"))
        monto = m.get("monto") or 0
        if f and monto >= 1 and len((m.get("descripcion") or "").strip()) >= 3 and f.year >= 2000:
            plausibles.append(f)
    if len(plausibles) < MIN_MOVIMIENTOS_GENERICO or len(plausibles) < 0.7 * len(movimientos):
        return False, MOTIVO_NO_EXTRACTO
    if (max(plausibles) - min(plausibles)).days > 460:
        return False, MOTIVO_NO_EXTRACTO
    return True, ""


def _num_flexible(s: str) -> float | None:
    """Número con separadores de miles/decimales en cualquier estilo: 1,234.56 · 1.234,56 ·
    8,200 · 8.200 · 8200.5. Si hay un solo separador seguido de exactamente 3 dígitos es de
    miles; si hay dos tipos, el último es el decimal."""
    s = s.strip().strip(".,")
    if not s or not re.fullmatch(r"[\d.,]+", s):
        return None
    ultimo = max(s.rfind("."), s.rfind(","))
    if ultimo == -1:
        return float(s)
    sep = s[ultimo]
    otro = "," if sep == "." else "."
    entero, frac = s[:ultimo], s[ultimo + 1:]
    if otro in entero or (s.count(sep) == 1 and len(frac) != 3):
        return float(entero.replace(otro, "").replace(sep, "") + "." + frac) if frac else float(entero.replace(otro, "").replace(sep, ""))
    return float(s.replace(".", "").replace(",", ""))  # solo miles ('8,200' o '1.234.567')


# Un valor de Nequi: '$8,200.00', '$-8,200.00', '-$8,200.00', '$ 8.200', '($8,200.00)'.
_VALOR_NEQUI = r"\(?[-–−]?\s*\$\s*[-–−]?\s*[\d][\d.,]*\)?"
_RE_REGISTRO_NEQUI = re.compile(
    r"^(\d{2})/(\d{2})/(\d{4})\s+(.*?)\s*(" + _VALOR_NEQUI + r")(?:\s+(" + _VALOR_NEQUI + r"))?\s*$", re.DOTALL
)
_RE_FECHA_NEQUI = re.compile(r"^\s*(\d{2})/(\d{2})/(\d{4})(?!\d)")
_RE_ENCABEZADO_NEQUI = re.compile(r"fecha|descripci[oó]n|valor|saldo", re.IGNORECASE)


def _valor_nequi(token: str) -> float | None:
    negativo = bool(re.search(r"[-–−]|^\(.*\)$", token))
    n = _num_flexible(re.sub(r"[^\d.,]", "", token))
    return None if n is None else (-n if negativo else n)


def _parse_nequi_con_perdidas(texto: str) -> tuple[list[dict], int]:
    """Lee el extracto de Nequi registro por registro. Un movimiento empieza en una línea que
    arranca con fecha dd/mm/aaaa y puede ocupar hasta 5 líneas (descripción partida, valor en
    otra línea). Devuelve (movimientos, perdidas): `perdidas` cuenta lo que parecía un
    movimiento y no se pudo leer, y se suma 1 si la cadena saldo anterior + abonos - cargos
    no llega al saldo actual impreso. Nada se pierde en silencio."""
    lineas = [l.strip() for l in texto.split("\n")]
    movimientos: list[dict] = []
    perdidas = 0
    firmados = 0.0
    i = 0
    while i < len(lineas):
        if not _RE_FECHA_NEQUI.match(lineas[i]):
            i += 1
            continue
        # Se une la línea de fecha con las siguientes hasta que cierre en un valor (o aparezca
        # otra fecha / una línea vacía / pasen 5 líneas).
        m = None
        usadas = 1
        for extra in range(0, 5):
            if i + extra >= len(lineas):
                break
            if extra and (not lineas[i + extra] or _RE_FECHA_NEQUI.match(lineas[i + extra])):
                break
            candidato = " ".join(l for l in lineas[i:i + extra + 1] if l)
            m = _RE_REGISTRO_NEQUI.match(candidato)
            if m:
                usadas = extra + 1
                break
        if not m:
            perdidas += 1  # empezaba como movimiento pero no se pudo leer
            i += 1
            continue
        i += usadas
        desc = re.sub(r"\s+", " ", m.group(4)).strip()
        valor = _valor_nequi(m.group(5))
        if valor is None:
            perdidas += 1
            continue
        if valor == 0:
            continue
        if len(_RE_ENCABEZADO_NEQUI.findall(desc)) >= 2:
            continue  # fila de encabezado de la tabla
        firmados += valor
        movimientos.append({
            "fecha": f"{m.group(3)}-{m.group(2)}-{m.group(1)}", "descripcion": desc, "monto": abs(valor),
            "tipo": _tipo_por_signo(valor, desc), "referencia": "", "saldo": None, **_pista(desc),
        })

    # Cadena del extracto: saldo anterior + abonos - cargos = saldo actual.
    ini = re.search(r"Saldo (?:anterior|inicial)\s+\$\s*([\d.,]+)", texto, re.IGNORECASE)
    fin = re.search(r"Saldo (?:actual|final)\s+\$\s*([\d.,]+)", texto, re.IGNORECASE)
    if movimientos and ini and fin:
        a, b = _num_flexible(ini.group(1)), _num_flexible(fin.group(1))
        if a is not None and b is not None and abs(a + firmados - b) >= 1:
            perdidas += 1
    return movimientos, perdidas


def _parse_nequi(texto: str) -> list[dict]:
    return _parse_nequi_con_perdidas(texto)[0]


_MES_RE = r"(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)"
# "01 - 31 OCT 2025" (encabezado "Período"): de ahí sale el año, no de la primera
# cifra de 4 dígitos del texto (podría ser parte de una dirección o un NIT).
_RE_PERIODO_NU = re.compile(r"\b\d{1,2}\s*-\s*\d{1,2}\s+(" + _MES_RE + r")[a-z]*\.?\s+(20\d{2})\b", re.IGNORECASE)
# Línea de movimiento de Nu: "01 oct <descripción> -$1.234,00". El monto va SIEMPRE
# al final de la línea, con signo y $. La descripción puede traer números sueltos
# ("OXXO NAVARRA 114", "ALKOSTO AVX 68") que NO son el monto.
_RE_LINEA_NU = re.compile(
    r"^\s*(\d{1,2})\s+(" + _MES_RE + r")\.?\s+(.+?)\s+([+\-])\s*\$\s*(\d[\d.,]*)\s*$", re.IGNORECASE
)
_RE_INICIA_FECHA_NU = re.compile(r"^\s*\d{1,2}\s+" + _MES_RE + r"\.?\s+\S", re.IGNORECASE)


def _anio_del_periodo(texto: str) -> str | None:
    m = _RE_PERIODO_NU.search(texto)
    return m.group(2) if m else None


def _parse_nu_por_lineas(texto: str, anio: str) -> list[dict]:
    """Lector estricto por líneas del extracto de Nu. Si la descripción de un movimiento
    se parte en dos líneas, se une con las siguientes hasta encontrar el monto."""
    lineas = texto.split("\n")
    movimientos = []
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        if not _RE_INICIA_FECHA_NU.match(linea):
            i += 1
            continue
        m = _RE_LINEA_NU.match(linea)
        usadas = 1
        if not m:
            # ¿La descripción continúa en la(s) línea(s) siguiente(s)? (máx. 2)
            acumulada = linea.strip()
            for extra in range(1, 3):
                if i + extra >= len(lineas) or _RE_INICIA_FECHA_NU.match(lineas[i + extra]) or not lineas[i + extra].strip():
                    break
                acumulada += " " + lineas[i + extra].strip()
                m = _RE_LINEA_NU.match(acumulada)
                if m:
                    usadas = extra + 1
                    break
        i += usadas
        if not m:
            continue
        monto = parse_monto_cop(m.group(5))
        desc = re.sub(r"\s+", " ", m.group(3)).strip()
        if monto != monto or monto < 1 or re.search(r"saldo|total|per[ií]odo|extracto|n[uú]mero de cuenta|^cuenta\b", desc, re.IGNORECASE):
            continue
        mes = MESES[m.group(2).lower()]
        positivo = m.group(4) == "+"
        movimientos.append({
            "fecha": f"{anio}-{mes:02d}-{int(m.group(1)):02d}",
            "descripcion": desc, "monto": monto,
            "tipo": "income" if positivo else "expense",
            "referencia": "", "saldo": None, **_pista(desc),
        })
    return movimientos


def _parse_nu(texto: str, anio: str) -> tuple[list[dict], int]:
    anio = _anio_del_periodo(texto) or anio
    estrictos = _parse_nu_por_lineas(texto, anio)
    if estrictos:
        return estrictos, 0
    movimientos = []
    descartados = 0
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
            # Sin signo explícito y monto muy pequeño: probablemente ruido del
            # PDF (ej. un número de página capturado por el regex), no un
            # movimiento real. Se cuenta para poder avisarle al usuario, en
            # vez de perderlo sin que se note.
            descartados += 1
            continue
        signo = -1 if m.group(4) == "-" else 1
        tipo = "income" if signo > 0 else "expense"
        movimientos.append({
            "fecha": f"{anio}-{mes:02d}-{int(m.group(1)):02d}",
            "descripcion": desc, "monto": abs(monto), "tipo": tipo,
            "referencia": "", "saldo": None, **_pista(desc),
        })
    return movimientos, descartados


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
        tipo = "income" if credito > 0 else "expense"  # débito = sale, crédito = entra (nunca 'transfer')
        movimientos.append({
            "fecha": f"{anio}-{m.group(2)}-{m.group(1)}",
            "descripcion": desc, "monto": abs(monto), "tipo": tipo,
            "referencia": "", "saldo": None, **_pista(desc),
        })
    return movimientos


_RE_NO_MOVIMIENTO = re.compile(r"saldo|total|per[ií]odo|extracto|n[uú]mero de cuenta", re.IGNORECASE)


def _parse_tabular_por_linea(texto: str, patron: re.Pattern) -> list[dict]:
    """Lector de una línea por movimiento: fecha, descripción y UN valor al final. Solo
    espacios dentro de la línea (nunca salta de renglón: antes pegaba la fecha de un
    encabezado con el 'Saldo anterior' de la línea de abajo) y el signo '-' del valor
    decide gasto o ingreso (antes se perdía al limpiar el número y todo salía como ingreso)."""
    movimientos = []
    for m in patron.finditer(texto):
        anio = "20" + m.group(3) if len(m.group(3)) == 2 else m.group(3)
        desc = m.group(4).strip()
        valor = m.group(5)
        monto = parse_monto_cop(valor)
        if monto != monto or monto == 0 or _RE_NO_MOVIMIENTO.search(desc):
            continue
        movimientos.append({
            "fecha": f"{anio}-{m.group(2)}-{m.group(1)}",
            "descripcion": desc, "monto": abs(monto),
            "tipo": "expense" if valor.strip().startswith("-") else "income",
            "referencia": "", "saldo": None,
        })
    return movimientos


def _parse_davivienda_generico(texto: str) -> list[dict]:
    return _parse_tabular_por_linea(
        texto, re.compile(r"(\d{2})[/\-](\d{2})[/\-](\d{2,4})[ \t]+(.+?)[ \t]+(\-?\$?[\d.,]+)[ \t]*$", re.MULTILINE))


def _parse_generico(texto: str) -> list[dict]:
    return _parse_tabular_por_linea(
        texto, re.compile(r"(\d{2})[/\-](\d{2})[/\-](\d{2,4})[ \t]+(.+?)[ \t]+(\-?[\d.,]+)[ \t]*$", re.MULTILINE))


# ── Normalización, fingerprint y matching ──────────────────────────


def normalize_texto(valor: str) -> str:
    texto = str(valor or "").strip().lower()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    texto = re.sub(r"[^a-z0-9 ]", "", texto)
    return texto.strip()


# Algunos extractos traen la hora pegada a la fecha ("2026-10-03 14:32"); la
# fecha sigue siendo solo el día (la hora se lee aparte con hora_del_extracto).
_SUFIJO_HORA = r"(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?$"


def parse_bank_date(valor) -> datetime | None:
    if isinstance(valor, datetime):
        return valor
    if not valor:
        return None
    s = str(valor).strip()
    iso = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})" + _SUFIJO_HORA, s)
    if iso:
        return datetime(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    latam = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})" + _SUFIJO_HORA, s)
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


def hora_del_extracto(mov: dict) -> tuple[int, int, int] | None:
    """Hora (h, m, s) de un movimiento del extracto, si el banco la trae: en un
    campo 'hora' o pegada a la fecha ('2026-10-03 14:32'). None si no hay."""
    for texto in (mov.get("hora"), mov.get("fecha")):
        m = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?(?!\d)", str(texto or ""))
        if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
            return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    return None


def emparejar_rapidos(items: list[dict], candidatos: list[dict], excluidos: set | None = None) -> dict[int, dict]:
    """Cruce 1:1 entre movimientos del extracto y movimientos registrados a mano
    rápida (Wallet, atajos, cierre de app, voz) que aún no se concilian.

    Cada item del extracto se empareja con UN solo registrado y viceversa. Entre
    todos los pares posibles gana el de menor puntaje (greedy global), donde
        puntaje = diferencia de fecha/hora en días + 3 * (diferencia de monto / monto)
    Un par es posible si: mismo tipo, fecha a ≤3 días y monto dentro de
    ±5% o $500 (lo que sea mayor). Si el extracto trae hora, la diferencia de
    fecha se mide en segundos (la hora desempata); si no, en días enteros y el
    empate lo resuelve el orden (extracto en orden ↔ registrados por hora).
    Devuelve {posición del item: fila del ledger}."""
    excluidos = excluidos or set()
    pares = []
    for i, it in enumerate(items):
        fecha = parse_bank_date(it.get("fecha"))
        if not fecha:
            continue
        hora = hora_del_extracto(it)
        objetivo = fecha.replace(hour=hora[0], minute=hora[1], second=hora[2]) if hora else fecha
        monto = abs(it.get("monto", 0))
        tolerancia = max(500, monto * 0.05)
        for j, row in enumerate(candidatos):
            if row.get("id") in excluidos or not row.get("fecha") or row.get("tipo") != it.get("tipo"):
                continue
            dif_monto = abs(abs(row.get("monto", 0)) - monto)
            if dif_monto > tolerancia:
                continue
            if hora:
                segundos = abs((row["fecha"] - objetivo).total_seconds())
            else:
                segundos = abs((row["fecha"].date() - fecha.date()).days) * 86400
            if segundos > 3 * 86400:
                continue
            puntaje = segundos / 86400 + (dif_monto / max(monto, 1)) * 3
            pares.append((puntaje, i, row["fecha"], j))
    pares.sort(key=lambda p: (p[0], p[1], p[2], p[3]))
    usados_items, usados_filas, resultado = set(), set(), {}
    for _p, i, _f, j in pares:
        if i in usados_items or j in usados_filas:
            continue
        usados_items.add(i)
        usados_filas.add(j)
        resultado[i] = candidatos[j]
    return resultado


def _cand_extracto(i: int, mov: dict) -> Cand:
    """Una línea del extracto como aviso entrante de la regla central de duplicados."""
    fecha = parse_bank_date(mov.get("fecha"))
    hora = hora_del_extracto(mov)
    if fecha and hora:
        fecha = fecha.replace(hour=hora[0], minute=hora[1], second=hora[2])
    return Cand(id=str(i), origen=ORIGEN_EXTRACTO, tipo=mov.get("tipo"), monto=abs(float(mov.get("monto") or 0)),
                fecha=fecha or datetime(1970, 1, 1), cuentas=_CUENTA_UNICA, texto=mov.get("descripcion", ""),
                con_hora=hora is not None, ref=mov)


def _cand_ledger(r: dict) -> Cand:
    """Una fila del libro (ya filtrada por cuenta) como movimiento existente. Los datos de canal
    (`origen`, `canales`, `flexible`) los pone _cargar_ledger; sin ellos, rápido = atajo."""
    origen = r.get("origen") or (ORIGEN_ATAJO if r.get("rapido") else ORIGEN_MANUAL)
    return Cand(id=r.get("id"), origen=origen, tipo=r.get("tipo"), monto=abs(float(r.get("monto") or 0)),
                fecha=r["fecha"], cuentas=_CUENTA_UNICA, texto=r.get("descripcion", ""),
                flexible=bool(r.get("flexible")), canales=frozenset(set(r.get("canales") or ()) | {origen}),
                con_hora=True, ref=r)


def _auditar_con_cruce_rapido(movimientos_extracto: list[dict], ledger: list[dict], descartados: dict | None = None) -> dict:
    """Variante con cruce 1:1 contra TODO lo ya registrado (regla central, app/duplicados.py).
    Orden de prioridad: 1) exactos por huella, 2) 'completado': el movimiento que ya tenías por
    el atajo, el correo, a mano... pendiente de conciliar (1:1; los del atajo toleran propina o
    conversión, el resto solo redondeo), 3) 'borrado_antes': algo que el usuario borró, 4)
    aproximado clásico contra el resto del ledger, 5) faltante. Los ya conciliados no se
    tocan. Además lista los 'sobrantes': rápidos pendientes del periodo del
    extracto que el banco no muestra (error de monto o aún no reflejado).

    `descartados` = {"fingerprints": Counter, "fantasmas": [Cand]} con lo que el usuario borró."""
    fingerprints = []
    for mov in movimientos_extracto:
        fecha_dt = parse_bank_date(mov.get("fecha"))
        fingerprints.append(compute_fingerprint(fecha_dt, mov["monto"], mov.get("cuenta", ""), mov["descripcion"], mov["tipo"]))

    estados: dict[int, str] = {}
    usados: set = set()
    match_ids_exactos: dict[int, str] = {}
    por_huella: dict[str, list[dict]] = {}
    for r in ledger:
        if r.get("fingerprint"):
            por_huella.setdefault(r["fingerprint"], []).append(r)
    for i, fp in enumerate(fingerprints):
        libres = [r for r in por_huella.get(fp, []) if r.get("id") not in usados]
        if libres:
            usados.add(libres[0].get("id"))
            estados[i] = "exacto"
            match_ids_exactos[i] = libres[0].get("id")

    # 2) El resto se cruza 1:1 con lo que ya tenías sin conciliar, venga del canal que venga.
    pendientes = [i for i in range(len(movimientos_extracto)) if i not in estados]
    libres_ledger = sorted(
        (r for r in ledger if not r.get("conciliado") and r.get("id") not in usados and r.get("fecha")
         and r.get("emparejable", True) and r.get("tipo") in ("income", "expense")),
        key=lambda r: r["fecha"])
    candidatos = [r for r in libres_ledger if r.get("rapido")]  # para los «sobrantes»
    entrantes = [_cand_extracto(i, movimientos_extracto[i]) for i in pendientes]
    existentes = [_cand_ledger(r) for r in libres_ledger]
    match_ids: dict[int, str] = dict(match_ids_exactos)
    for pos, j, _p in emparejar(entrantes, existentes):
        i = pendientes[pos]
        estados[i] = "completado"
        match_ids[i] = libres_ledger[j].get("id")
        usados.add(libres_ledger[j].get("id"))

    # 3) Lo que el usuario borró no resucita: por huella de línea y por datos (la foto del movimiento).
    if descartados:
        por_fp = dict(descartados.get("fingerprints") or {})
        fantasmas = list(descartados.get("fantasmas") or [])
        for i in range(len(movimientos_extracto)):
            if i in estados:
                continue
            if por_fp.get(fingerprints[i], 0) > 0:
                por_fp[fingerprints[i]] -= 1
                estados[i] = "borrado_antes"
        # Cada foto borrada absorbe UNA sola línea: se empareja y se retira, hasta que no haya más parejas.
        while fantasmas:
            pend = [i for i in range(len(movimientos_extracto)) if i not in estados]
            nuevos = emparejar([_cand_extracto(i, movimientos_extracto[i]) for i in pend], fantasmas)
            if not nuevos:
                break
            pos, j, _p = nuevos[0]
            estados[pend[pos]] = "borrado_antes"
            fantasmas = [f for k, f in enumerate(fantasmas) if k != j]

    resto = [r for r in ledger if not r.get("rapido") and not r.get("conciliado") and r.get("id") not in usados]
    for i, mov in enumerate(movimientos_extracto):
        if i in estados:
            continue
        aprox = find_approx_match(resto, {**mov, "fecha": parse_bank_date(mov.get("fecha"))})
        if aprox:
            estados[i] = "aproximado"
            match_ids[i] = aprox.get("id")
            resto = [r for r in resto if r is not aprox]  # 1:1
        else:
            estados[i] = "faltante"

    review = []
    for i, mov in enumerate(movimientos_extracto):
        item = {**mov, "fingerprint": fingerprints[i], "estado": estados[i]}
        if i in match_ids:
            item["match_id"] = match_ids[i]
        review.append(item)

    fechas = [d.date() for d in (parse_bank_date(m.get("fecha")) for m in movimientos_extracto) if d]
    sobrantes = []
    if fechas:
        desde, hasta = min(fechas), max(fechas)
        for r in candidatos:
            if r.get("id") in usados or not r.get("fecha") or not (desde <= r["fecha"].date() <= hasta):
                continue
            sobrantes.append({
                "id": r.get("id"), "fecha": r["fecha"].strftime("%Y-%m-%d %H:%M"),
                "descripcion": r.get("descripcion", ""), "monto": abs(r.get("monto", 0)),
                "tipo": r.get("tipo", "expense"),
            })
    cuenta = lambda e: sum(1 for v in estados.values() if v == e)  # noqa: E731
    return {
        "review": review,
        "total_movimientos": len(movimientos_extracto),
        "exactos": cuenta("exacto"),
        "aproximados": cuenta("aproximado"),
        "faltantes": cuenta("faltante"),
        "completados": cuenta("completado"),
        "borrados_antes": cuenta("borrado_antes"),
        "sobrantes": sobrantes,
    }


def auditar_movimientos(movimientos_extracto: list[dict], ledger: list[dict], cruzar_rapidos: bool = False,
                        descartados: dict | None = None) -> dict:
    """
    Compara movimientos del extracto contra el ledger existente.
    Clasifica cada uno como: exacto (fingerprint/fecha+monto igual),
    aproximado (dentro de tolerancia), o faltante (no está registrado).
    Con `cruzar_rapidos=True` aplica el cruce 1:1 de movimientos rápidos
    (ver _auditar_con_cruce_rapido) y suma el estado 'completado'.
    Las líneas de $0 (cuota de manejo exenta, intereses en cero, saldos) no son
    movimientos: se descartan aquí, para todos los lectores de extractos, y se
    cuentan en `ignorados_en_cero` para poder decírselo al usuario.
    """
    con_valor = [m for m in movimientos_extracto if abs(m.get("monto") or 0) >= 1]
    ignorados = len(movimientos_extracto) - len(con_valor)
    movimientos_extracto = con_valor
    if cruzar_rapidos:
        resultado = _auditar_con_cruce_rapido(movimientos_extracto, ledger, descartados)
        resultado["ignorados_en_cero"] = ignorados
        return resultado
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
        "ignorados_en_cero": ignorados,
    }
