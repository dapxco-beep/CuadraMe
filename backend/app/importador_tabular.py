"""
Lectura de archivos tabulares (.csv, .xlsx, .xls) de un banco o propios y
conversión a movimientos PROPUESTOS. Todo puro: recibe bytes y devuelve datos;
no toca la base de datos (eso lo hace el router, que reutiliza la conciliación
para detectar duplicados).

Formatos colombianos que maneja:
- Montos: "1.234.567,89", "1,234,567.89", "$ 45.000", "(45.000)", "45.000-", "45000".
  Con un solo separador y tres dígitos después ("1.234") se asume separador de
  MILES (en pesos casi nunca hay centavos); con 1-2 dígitos, decimal.
- Fechas: dd/mm/aaaa (por defecto), dd-mm-aa, aaaa-mm-dd, "15 ene 2026", fechas
  de Excel (datetime o número serial).
- Signos: monto con signo, columnas débito/crédito separadas, o columna D/C.

Límites (protegen la memoria del servidor): 5 MB, 3.000 movimientos.
"""
import csv
import io
import re
import unicodedata
from datetime import date, datetime, timedelta

from app.conciliacion import es_transferencia_propia
from app.contabilidad import MARCA_TRASLADO_PROPIO

MAX_BYTES = 5 * 1024 * 1024
MAX_FILAS = 3000          # movimientos aceptados por archivo
MAX_FILAS_LEIDAS = 20000  # filas crudas que se recorren buscando datos
MAX_COLUMNAS = 30
FILAS_BUSCAR_ENCABEZADO = 30

MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8,
         "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}

CAMPOS = ("fecha", "descripcion", "monto", "debito", "credito", "saldo", "tipo")


class ErrorArchivo(ValueError):
    """Error que se le muestra tal cual al usuario (en español)."""


def _norm(t) -> str:
    t = "" if t is None else str(t)
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9/ ]", " ", t.lower())).strip()


# ------------------------------------------------------------------ lectura

def _decodificar(contenido: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return contenido.decode(enc)
        except UnicodeDecodeError:
            continue
    return contenido.decode("latin-1", errors="replace")


def _delimitador(texto: str) -> str:
    muestra = [l for l in texto.splitlines()[:30] if l.strip()]
    if not muestra:
        return ","
    mejor, mejor_score = ",", -1
    for d in (";", ",", "\t", "|"):
        conteos = [l.count(d) for l in muestra]
        # El delimitador correcto aparece una cantidad estable de veces por línea.
        frecuente = max(set(conteos), key=conteos.count)
        score = frecuente * conteos.count(frecuente) if frecuente else 0
        if score > mejor_score:
            mejor, mejor_score = d, score
    return mejor


def leer_filas(nombre: str, contenido: bytes, hoja: int = 0) -> tuple[list[list], list[str]]:
    """Devuelve (filas crudas, nombres de hojas). Levanta ErrorArchivo con mensajes claros."""
    if not contenido:
        raise ErrorArchivo("El archivo está vacío.")
    if len(contenido) > MAX_BYTES:
        raise ErrorArchivo(f"El archivo pesa más de {MAX_BYTES // (1024 * 1024)} MB. Sube un periodo más corto.")
    ext = (nombre or "").lower().rsplit(".", 1)[-1] if "." in (nombre or "") else ""

    if ext == "xlsx" or contenido[:2] == b"PK":
        return _leer_xlsx(contenido, hoja)
    if ext == "xls" or contenido[:4] == b"\xd0\xcf\x11\xe0":
        return _leer_xls(contenido, hoja)
    if ext in ("csv", "txt", "tsv", ""):
        return _leer_csv(contenido), []
    raise ErrorArchivo("Formato no soportado. Sube un archivo .csv, .xlsx o .xls.")


def _leer_csv(contenido: bytes) -> list[list]:
    texto = _decodificar(contenido)
    delim = _delimitador(texto)
    filas = []
    for i, fila in enumerate(csv.reader(io.StringIO(texto), delimiter=delim)):
        if i >= MAX_FILAS_LEIDAS:
            break
        filas.append([c.strip() for c in fila[:MAX_COLUMNAS]])
    return _limpiar(filas)


def _leer_xlsx(contenido: bytes, hoja: int) -> tuple[list[list], list[str]]:
    from openpyxl import load_workbook  # ya es dependencia (exportar a Excel)

    try:
        wb = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception:
        raise ErrorArchivo("No se pudo abrir el Excel. Verifica que no tenga clave y que sea .xlsx válido.")
    try:
        nombres = list(wb.sheetnames)
        if not nombres:
            raise ErrorArchivo("El Excel no tiene hojas.")
        ws = wb[nombres[min(max(hoja, 0), len(nombres) - 1)]]
        filas = []
        for i, fila in enumerate(ws.iter_rows(values_only=True)):
            if i >= MAX_FILAS_LEIDAS:
                break
            filas.append(list(fila[:MAX_COLUMNAS]))
    finally:
        wb.close()
    return _limpiar(filas), nombres


def _leer_xls(contenido: bytes, hoja: int) -> tuple[list[list], list[str]]:
    try:
        import xlrd  # solo para .xls antiguo (pure-Python, ~100 KB); se importa si hace falta
    except ImportError:
        raise ErrorArchivo("Los .xls antiguos no están disponibles en este servidor. Ábrelo en Excel y guárdalo como .xlsx o .csv.")
    try:
        libro = xlrd.open_workbook(file_contents=contenido)
    except Exception:
        raise ErrorArchivo("No se pudo abrir el archivo .xls. Guárdalo como .xlsx o .csv e inténtalo de nuevo.")
    nombres = libro.sheet_names()
    hoja_x = libro.sheet_by_index(min(max(hoja, 0), len(nombres) - 1))
    filas = []
    for r in range(min(hoja_x.nrows, MAX_FILAS_LEIDAS)):
        fila = []
        for c in range(min(hoja_x.ncols, MAX_COLUMNAS)):
            celda = hoja_x.cell(r, c)
            if celda.ctype == xlrd.XL_CELL_DATE:
                try:
                    fila.append(xlrd.xldate.xldate_as_datetime(celda.value, libro.datemode))
                    continue
                except Exception:
                    pass
            fila.append(celda.value if celda.value != "" else None)
        filas.append(fila)
    return _limpiar(filas), nombres


def _limpiar(filas: list[list]) -> list[list]:
    """Quita filas totalmente vacías al final/entre datos y recorta columnas vacías al final."""
    filas = [f for f in filas if any(c not in (None, "") for c in f)]
    ancho = max((len(f) for f in filas), default=0)
    return [list(f) + [None] * (ancho - len(f)) for f in filas]


# ----------------------------------------------------------------- parsers

def parse_monto(valor, separador_decimal: str = "auto") -> float | None:
    """separador_decimal: 'auto' | 'coma' | 'punto'. Devuelve None si no es un monto."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return None
    negativo = False
    if s.startswith("(") and s.endswith(")"):
        negativo, s = True, s[1:-1]
    if re.search(r"(db|d[eé]bito)\.?\s*$", s, re.IGNORECASE):
        negativo = True
    s = re.sub(r"(cr[eé]dito|d[eé]bito|cr|db|cop|usd|eur)\.?", "", s, flags=re.IGNORECASE)
    s = s.replace("$", "").replace(" ", "").replace(" ", "")
    if s.endswith("-"):
        negativo, s = True, s[:-1]
    if s.startswith("-"):
        negativo, s = True, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if not s or not re.fullmatch(r"[\d.,]+", s) or not re.search(r"\d", s):
        return None

    coma, punto = s.count(","), s.count(".")
    if separador_decimal == "coma":
        s = s.replace(".", "").replace(",", ".")
    elif separador_decimal == "punto":
        s = s.replace(",", "")
    elif coma and punto:
        # El que aparece al final es el decimal.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif coma or punto:
        sep = "," if coma else "."
        cantidad = coma or punto
        despues = s.rsplit(sep, 1)[1]
        if cantidad > 1 or len(despues) == 3:
            s = s.replace(sep, "")          # miles
        else:
            s = s.replace(sep, ".")         # decimal
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if negativo else n


def detectar_separador_decimal(valores) -> str:
    """'coma' si los textos usan 1.234,56; 'punto' si usan 1,234.56; si no hay pistas, 'auto'."""
    coma = punto = 0
    for v in valores:
        if not isinstance(v, str):
            continue
        t = re.sub(r"[^\d.,]", "", v)
        if re.search(r",\d{1,2}$", t):
            coma += 1
        elif re.search(r"\.\d{1,2}$", t):
            punto += 1
    if coma > punto:
        return "coma"
    if punto > coma:
        return "punto"
    return "auto"


def parse_fecha(valor, orden: str = "dmy") -> datetime | None:
    """orden: 'dmy' (día primero, lo normal en Colombia) o 'mdy'."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, datetime):
        return valor.replace(hour=0, minute=0, second=0, microsecond=0)
    if isinstance(valor, date):
        return datetime(valor.year, valor.month, valor.day)
    if isinstance(valor, (int, float)):
        if 20000 < valor < 80000:  # número serial de Excel
            return datetime(1899, 12, 30) + timedelta(days=int(valor))
        return None
    s = str(valor).strip()
    if not s:
        return None
    s = re.split(r"[ T]\d{1,2}:\d{2}", s)[0].strip()   # quita la hora
    try:
        m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
        if m:
            return datetime(int(m[1]), int(m[2]), int(m[3]))
        m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", s)
        if m:
            a, b, anio = int(m[1]), int(m[2]), int(m[3])
            anio = 2000 + anio if anio < 100 else anio
            dia, mes = (a, b) if orden == "dmy" else (b, a)
            return datetime(anio, mes, dia)
        m = re.fullmatch(r"(\d{1,2})[ \-/.]*([a-zA-Z]{3,10})\.?[ \-/.,]*(?:de\s+)?(\d{2,4})", _norm(s).replace("de ", " "))
        if m and m[2][:3] in MESES:
            anio = int(m[3])
            anio = 2000 + anio if anio < 100 else anio
            return datetime(anio, MESES[m[2][:3]], int(m[1]))
    except ValueError:
        return None
    return None


def detectar_orden_fecha(valores) -> str:
    """'mdy' solo si hay evidencia (algún segundo campo > 12 y ningún primero > 12)."""
    primero_grande = segundo_grande = False
    for v in valores:
        if isinstance(v, str):
            m = re.fullmatch(r"\s*(\d{1,2})[-/.](\d{1,2})[-/.]\d{2,4}.*", v)
            if m:
                primero_grande |= int(m[1]) > 12
                segundo_grande |= int(m[2]) > 12
    return "mdy" if segundo_grande and not primero_grande else "dmy"


# ------------------------------------------------------------ detección de columnas

_SINONIMOS = {
    "fecha": ["fecha", "fecha transaccion", "fecha movimiento", "fecha operacion", "fecha valor",
              "fecha contable", "date", "dia"],
    "descripcion": ["descripcion", "detalle", "concepto", "descripcion movimiento", "movimiento",
                    "transaccion", "observaciones", "observacion", "comercio", "establecimiento",
                    "description", "referencia", "nombre"],
    "debito": ["debito", "debitos", "cargo", "cargos", "retiro", "retiros", "egreso", "egresos",
               "salida", "salidas", "valor debito", "debit"],
    "credito": ["credito", "creditos", "abono", "abonos", "deposito", "depositos", "ingreso",
                "ingresos", "entrada", "entradas", "valor credito", "credit"],
    "monto": ["monto", "valor", "importe", "amount", "valor transaccion", "valor movimiento", "total"],
    "saldo": ["saldo", "saldo disponible", "saldo final", "balance"],
    "tipo": ["tipo", "naturaleza", "tipo movimiento", "tipo transaccion", "d/c", "dc", "signo"],
}


def _puntaje_encabezado(fila) -> int:
    puntos = 0
    for c in fila:
        n = _norm(c)
        if n and any(n == s or (len(s) > 3 and s in n) for lista in _SINONIMOS.values() for s in lista):
            puntos += 1
    return puntos


def detectar_fila_encabezado(filas: list[list]) -> int | None:
    """Índice de la fila de encabezados (los bancos suelen poner títulos antes), o None."""
    mejor, mejor_i = 0, None
    for i, fila in enumerate(filas[:FILAS_BUSCAR_ENCABEZADO]):
        p = _puntaje_encabezado(fila)
        if p > mejor:
            mejor, mejor_i = p, i
    return mejor_i if mejor >= 2 else None


def detectar_mapeo(encabezados: list, muestra: list[list]) -> dict[str, int | None]:
    """Mapa campo -> índice de columna. Primero por nombre del encabezado; lo que
    falte se infiere por el contenido (columna que parece fecha, columna numérica)."""
    mapeo: dict[str, int | None] = {c: None for c in CAMPOS}
    usadas: set[int] = set()
    nombres = [_norm(h) for h in encabezados]

    for campo in ("fecha", "debito", "credito", "saldo", "tipo", "monto", "descripcion"):
        for sin in _SINONIMOS[campo]:               # exacto, en orden de prioridad
            for i, n in enumerate(nombres):
                if i not in usadas and n == sin:
                    mapeo[campo] = i
                    usadas.add(i)
                    break
            if mapeo[campo] is not None:
                break
        if mapeo[campo] is None:
            for sin in _SINONIMOS[campo]:           # "contiene"
                if len(sin) <= 3:
                    continue
                for i, n in enumerate(nombres):
                    if i not in usadas and sin in n:
                        mapeo[campo] = i
                        usadas.add(i)
                        break
                if mapeo[campo] is not None:
                    break

    def fraccion(i, f):
        vals = [fila[i] for fila in muestra if i < len(fila) and fila[i] not in (None, "")]
        return sum(1 for v in vals if f(v)) / len(vals) if vals else 0.0

    ancho = max((len(f) for f in muestra), default=len(encabezados))
    if mapeo["fecha"] is None:
        cand = [(fraccion(i, lambda v: parse_fecha(v) is not None), i) for i in range(ancho) if i not in usadas]
        cand = [c for c in cand if c[0] >= 0.7]
        if cand:
            mapeo["fecha"] = max(cand)[1]
            usadas.add(mapeo["fecha"])
    if mapeo["monto"] is None and mapeo["debito"] is None and mapeo["credito"] is None:
        cand = [(fraccion(i, lambda v: parse_monto(v) is not None), i) for i in range(ancho) if i not in usadas]
        cand = [c for c in cand if c[0] >= 0.7]
        if cand:
            # Si hay varias numéricas, la última suele ser el saldo; el monto es la primera.
            mapeo["monto"] = min(cand, key=lambda c: c[1])[1]
            usadas.add(mapeo["monto"])
    if mapeo["descripcion"] is None:
        cand = [(sum(len(str(f[i])) for f in muestra if i < len(f) and f[i]), i)
                for i in range(ancho) if i not in usadas
                and fraccion(i, lambda v: parse_monto(v) is None and parse_fecha(v) is None) >= 0.7]
        if cand:
            mapeo["descripcion"] = max(cand)[1]
    return mapeo


# ------------------------------------------------------------- filas -> movimientos

_ES_DEBITO = re.compile(r"^(d|db|deb|debito|cargo|egreso|retiro|salida|pago|compra|-)$")
_ES_CREDITO = re.compile(r"^(c|cr|cre|credito|abono|ingreso|deposito|entrada|\+)$")
_FILA_RESUMEN = re.compile(r"\b(total|saldo (anterior|inicial|final|actual)|resumen)\b")


def _tipo_desde_columna(valor) -> str | None:
    n = _norm(valor)
    if _ES_DEBITO.match(n):
        return "expense"
    if _ES_CREDITO.match(n):
        return "income"
    return None


def filas_a_movimientos(filas: list[list], mapeo: dict, opciones: dict | None = None) -> dict:
    """filas: ya SIN encabezado. mapeo: {campo: índice|None}.
    opciones: separador_decimal, orden_fecha, invertir_signo.
    Devuelve {movimientos, errores, ignoradas, truncado}."""
    op = opciones or {}
    sep = op.get("separador_decimal", "auto")
    orden = op.get("orden_fecha", "dmy")
    invertir = bool(op.get("invertir_signo", False))

    def celda(fila, campo):
        i = mapeo.get(campo)
        return fila[i] if i is not None and i < len(fila) else None

    movimientos, errores, ignoradas = [], [], 0
    truncado = False
    for n, fila in enumerate(filas, start=1):
        desc = celda(fila, "descripcion")
        desc = re.sub(r"\s+", " ", str(desc)).strip() if desc not in (None, "") else ""
        fecha = parse_fecha(celda(fila, "fecha"), orden)

        monto_firmado = None
        if mapeo.get("debito") is not None or mapeo.get("credito") is not None:
            deb = parse_monto(celda(fila, "debito"), sep)
            cre = parse_monto(celda(fila, "credito"), sep)
            if cre and abs(cre) > 0:
                monto_firmado = abs(cre)
            elif deb and abs(deb) > 0:
                monto_firmado = -abs(deb)
            elif deb is not None or cre is not None:
                monto_firmado = 0.0
        if monto_firmado is None and mapeo.get("monto") is not None:
            m = parse_monto(celda(fila, "monto"), sep)
            if m is not None:
                t = _tipo_desde_columna(celda(fila, "tipo")) if mapeo.get("tipo") is not None else None
                monto_firmado = (abs(m) if t == "income" else -abs(m)) if t else m
                if invertir and not t:
                    monto_firmado = -monto_firmado

        if fecha is None and monto_firmado is None:
            ignoradas += 1  # encabezados repetidos, títulos o filas vacías
            continue
        if fecha is None:
            # "Total" suele caer en la columna de fecha, "Saldo anterior" en la de descripción.
            if _FILA_RESUMEN.search(_norm(desc) + " " + _norm(celda(fila, "fecha"))):
                ignoradas += 1
            else:
                errores.append({"fila": n, "motivo": "Fecha no reconocida"})
            continue
        if monto_firmado is None:
            errores.append({"fila": n, "motivo": "Monto no reconocido"})
            continue
        if monto_firmado == 0:
            ignoradas += 1
            continue
        if not desc:
            desc = "Sin descripción"
        if len(movimientos) >= MAX_FILAS:
            truncado = True
            break
        saldo = parse_monto(celda(fila, "saldo"), sep) if mapeo.get("saldo") is not None else None
        movimientos.append({
            "fila": n,
            "fecha": fecha.strftime("%Y-%m-%d"),
            "descripcion": desc[:200],
            "monto": round(abs(monto_firmado), 2),
            "tipo": "income" if monto_firmado > 0 else "expense",
            "saldo": saldo,
            # Dirección siempre explícita (signo / columnas débito-crédito); la pista solo avisa.
            **({"pista": MARCA_TRASLADO_PROPIO} if es_transferencia_propia(desc) else {}),
        })
    return {"movimientos": movimientos, "errores": errores, "ignoradas": ignoradas, "truncado": truncado}


def analizar(nombre: str, contenido: bytes, mapeo: dict | None = None, opciones: dict | None = None,
             fila_encabezado: int | None = None, hoja: int = 0) -> dict:
    """Punto de entrada: lee el archivo, detecta (o respeta) mapeo y opciones y
    devuelve todo lo que la vista previa necesita."""
    filas, hojas = leer_filas(nombre, contenido, hoja)
    if not filas:
        raise ErrorArchivo("No encontré datos en el archivo.")

    if fila_encabezado is None:
        fila_encabezado = detectar_fila_encabezado(filas)
    tiene_enc = fila_encabezado is not None and 0 <= fila_encabezado < len(filas)
    ancho = max(len(f) for f in filas)
    if tiene_enc:
        encabezados = [("" if c is None else str(c)) for c in filas[fila_encabezado]]
        datos = filas[fila_encabezado + 1:]
    else:
        encabezados = [f"Columna {i + 1}" for i in range(ancho)]
        datos = filas
    encabezados = (encabezados + [""] * ancho)[:ancho]
    encabezados = [h or f"Columna {i + 1}" for i, h in enumerate(encabezados)]

    muestra = datos[:60]
    mapeo_detectado = detectar_mapeo(encabezados if tiene_enc else [""] * ancho, muestra)
    mapeo_usado = {c: (mapeo or {}).get(c, mapeo_detectado[c]) if mapeo else mapeo_detectado[c] for c in CAMPOS}
    for c, v in list(mapeo_usado.items()):
        if v is not None and not (isinstance(v, int) and 0 <= v < ancho):
            mapeo_usado[c] = None

    texto_monto = []
    for c in ("monto", "debito", "credito"):
        i = mapeo_usado.get(c)
        if i is not None:
            texto_monto += [f[i] for f in muestra if i < len(f)]
    i_fecha = mapeo_usado.get("fecha")
    opciones_usadas = {
        "separador_decimal": (opciones or {}).get("separador_decimal") or detectar_separador_decimal(texto_monto),
        "orden_fecha": (opciones or {}).get("orden_fecha")
        or detectar_orden_fecha([f[i_fecha] for f in muestra if i_fecha is not None and i_fecha < len(f)]),
        "invertir_signo": bool((opciones or {}).get("invertir_signo", False)),
    }

    res = filas_a_movimientos(datos, mapeo_usado, opciones_usadas)
    return {
        "hojas": hojas,
        "fila_encabezado": fila_encabezado if tiene_enc else None,
        "columnas": [{"indice": i, "nombre": h} for i, h in enumerate(encabezados)],
        "muestra": [[_texto_celda(c) for c in f] for f in datos[:6]],
        "mapeo": mapeo_usado,
        "opciones": opciones_usadas,
        "total_filas": len(datos),
        **res,
    }


def _texto_celda(c) -> str:
    if c is None:
        return ""
    if isinstance(c, datetime):
        return c.strftime("%Y-%m-%d")
    return str(c)[:60]
