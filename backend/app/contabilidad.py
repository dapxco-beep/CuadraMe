"""
Regla contable central: qué movimientos cuentan como GASTO o INGRESO real.

Por qué existe: la plata solo "cambia de bolsillo" en tres casos y ninguno es
gasto ni ingreso, pero si cada pantalla decide por su cuenta se cuenta dos veces:

1. Pago de una tarjeta de crédito (cuenta -> tarjeta). El gasto ya se contó
   cuando se hizo cada COMPRA con la tarjeta; pagar el extracto solo salda esa
   deuda. Si además cuenta como gasto, todo lo comprado con tarjeta se suma 2 veces.
2. Transferencias entre cuentas propias (Nequi -> Bancolombia, etc.).
3. El abono que "entra" a la cuenta de la tarjeta cuando la pagas: no es un
   ingreso, es la otra pata del mismo pago.

Los movimientos se guardan con su `tipo` original (income/expense/transfer)
porque ese tipo mueve el saldo de la cuenta; aquí solo se calcula el tipo
EFECTIVO para estadísticas (resumen, presupuestos, insights, reportes, salud,
wrapped, cierre mensual, impuestos). Todo es puro: sin base de datos ni red.
"""
import re
import unicodedata
from functools import lru_cache
from bisect import bisect_left, bisect_right
from datetime import datetime

FUENTE_TRANSFERENCIA = "transferencia_interna"
# Ajuste de saldo: el usuario escribe su saldo real y la diferencia se guarda como
# movimiento para que saldo e historial cuadren, pero NO es plata ganada ni gastada
# (corrige un descuadre), así que tampoco cuenta como ingreso/gasto en reportes.
FUENTE_AJUSTE = "ajuste_saldo"
# Importado de un archivo SIN ajustar el saldo (el banco ya lo reflejaba): el movimiento
# cuenta en reportes, pero editarlo o borrarlo NO debe mover el saldo de la cuenta.
FUENTE_IMPORTADO_SIN_SALDO = "importado_sin_saldo"
# Aporte automático a una meta: la plata sale de la cuenta (el saldo baja y el
# movimiento queda en el historial) pero NO es un gasto: sigue siendo del usuario,
# solo cambió de bolsillo (cuenta -> meta). En `notas` guarda "META:<id de la meta>".
FUENTE_APORTE_META = "aporte_meta"
CATEGORIA_PAGO_TARJETA ="Pago de tarjeta"
CATEGORIA_AJUSTE = "Ajuste de saldo"
CATEGORIA_APORTE_META = "Aporte a meta"
CATEGORIAS_NEUTRAS = {"transferencia", "pago de tarjeta", "ajuste de saldo", "aporte a meta"}

# "pago tarjeta", "pago de tarjeta de crédito", "abono a TC", "pago visa", "pago tarj credito".
# NO casa con "pago con tarjeta en Éxito" (eso es una COMPRA): después de pago/abono solo
# se admiten conectores (de, a, la, mi, total, mínimo), no "con".
# También "Pago Nu Tarjeta", "Pago Bancolombia TC" (el banco va ENTRE el verbo y la palabra tarjeta:
# caso típico del pago de la tarjeta Nu desde la cuenta Nu). Solo con entidades conocidas, para no
# confundirlo con una compra.
_ENTIDAD_TARJETA = (
    r"nu|nubank|nu\s+colombia|bancolombia|davivienda|bbva|banco\s+de\s+bogota|bogota|falabella|rappi|rappicard|"
    r"lulo|scotiabank|colpatria|itau|av\s+villas|banco\s+popular|occidente|santander|citibank|tuya|exito"
)
PATRON_PAGO_TARJETA = re.compile(
    r"\b(?:pagos?|abonos?|pagaste|abonaste)\s+(?:(?:de|a|la|mi|tu|total|minimo|del)\s+)*"
    r"(?:tarjeta|tarj\.?|tc|tdc|t\.c\.?|visa|master\s?card|amex|american\s+express|diners)\b"
    r"|\b(?:pagos?|abonos?|pagaste|abonaste)\s+(?:(?:de|a|la|mi|tu|total|minimo|del)\s+)*"
    rf"(?:{_ENTIDAD_TARJETA})\s+(?:tarjeta|tarj\.?|tc|tdc|t\.c\.?|credito)\b",
    re.IGNORECASE,
)

# Pistas de que un movimiento es un traslado entre cuentas propias (se usan solo
# para emparejar salida y entrada de igual monto en cuentas distintas).
PATRON_TRASLADO = re.compile(
    r"transfer|traslado|\btrasl\b|entre\s+cuentas|nequi|daviplata|\bdale\b|movii|"
    r"\benvi[oa]|enviaste|recibiste|bre-?b|a\s+mi\s+cuenta|desde\s+mi\s+cuenta|"
    r"a\s+tu\s+cuenta|de\s+tu\s+cuenta|^\s*para\s+\S|"
    r"\benviad[oa]\b|\brecibid[oa]\b|\bavances?\b(?!\s+de\s+obra)",
    re.IGNORECASE,
)

# Marca que dejan los lectores de extractos en `notas` cuando la contraparte parece el propio
# titular u otra cuenta propia: el movimiento SÍ mueve saldo (tiene dirección) y los informes
# lo tratan como traslado solo si aparece su otra pata (ver tipos_efectivos).
MARCA_TRASLADO_PROPIO = "posible_traslado_propio"
# El usuario dijo "es un gasto/ingreso real": nunca se empareja como traslado.
MARCA_NO_TRASLADO = "no_es_traslado"
# El usuario dijo "es un traslado entre mis cuentas": neutral siempre y su otra pata se empareja.
MARCA_ES_TRASLADO = "es_traslado_propio"
# Diferencia máxima (pesos) entre lo que sale y lo que entra para seguir llamándolo traslado (comisión).
TOLERANCIA_COMISION = 2000.0


def _descartado(m) -> bool:
    return MARCA_NO_TRASLADO in (_g(m, "notas", "") or "")

# Dirección deducible con certeza de una descripción de transferencia (solo al inicio).
_RE_SALE = re.compile(r"^\s*(?:para\b|enviaste\b|envio\b|transferencia\s+a\b|trf\s+a\b|transferiste\b)", re.IGNORECASE)
_RE_ENTRA = re.compile(r"^\s*(?:de\b|recibi(?:ste)?\b|transferencia\s+de\b|trf\s+de\b|giro\s+de\b|te\s+enviaron\b)", re.IGNORECASE)


def direccion_por_descripcion(descripcion: str) -> str | None:
    """'expense' / 'income' si la descripción lo dice sin ambigüedad ('Para …', 'Enviaste a …',
    'De …', 'Recibiste de …'); None si no. Pura."""
    d = _sin_acentos(descripcion or "")
    sale, entra = bool(_RE_SALE.search(d)), bool(_RE_ENTRA.search(d))
    if sale == entra:
        return None
    return "expense" if sale else "income"


def con_marca_traslado(notas: str | None) -> str:
    n = notas or ""
    return n if MARCA_TRASLADO_PROPIO in n else (f"{n} · {MARCA_TRASLADO_PROPIO}" if n else MARCA_TRASLADO_PROPIO)


def delta_saldo(m) -> float:
    """Cuánto mueve el saldo de SU cuenta un movimiento (regla única). Todo movimiento tiene
    dirección: income suma, expense resta. Las dos patas de un traslado creado en la app
    (tipo 'transfer', fuente transferencia_interna) llevan la dirección en notas: ':in' suma,
    ':out' resta. Un 'transfer' heredado sin dirección (importado antes de esta regla) vale 0:
    no se puede saber hacia dónde fue; la migración retipar_transfers.sql lo corrige.
    Los importados 'sin saldo' (el banco ya lo reflejaba) nunca lo movieron."""
    if _g(m, "fuente") == FUENTE_IMPORTADO_SIN_SALDO:
        return 0.0
    tipo, monto = _g(m, "tipo"), float(_g(m, "monto", 0) or 0)
    if tipo == "income":
        return monto
    if tipo == "expense":
        return -monto
    if tipo == "transfer" and _g(m, "fuente") == FUENTE_TRANSFERENCIA:
        notas = _g(m, "notas") or ""
        return monto if notas.endswith(":in") else -monto if notas.endswith(":out") else 0.0
    return 0.0


def tipo_con_direccion(tipo: str | None, descripcion: str = "") -> str | None:
    """Todo movimiento importado tiene dirección. 'income'/'expense' pasan igual; un 'transfer'
    heredado (extractos viejos guardados) se resuelve por la descripción o devuelve None."""
    if tipo in ("income", "expense"):
        return tipo
    return direccion_por_descripcion(descripcion)


PATRON_INTERES = re.compile(r"\binter[eé]s(?:es)?\b", re.IGNORECASE)

VENTANA_EMPAREJAR_SEG = 2 * 86400
# Puentes festivos de Colombia: viernes -> martes son 4 días. Solo se acepta esa distancia
# cuando las pistas son fuertes (suma >= 3), para no emparejar de más.
VENTANA_FESTIVO_SEG = 4 * 86400


def _g(m, campo, defecto=None):
    """Lee un campo de un objeto ORM o de un dict."""
    if isinstance(m, dict):
        return m.get(campo, defecto)
    return getattr(m, campo, defecto)


@lru_cache(maxsize=50_000)
def _sin_acentos(t: str) -> str:
    # Memorizada: es una función pura del texto y los informes la llaman decenas de miles de veces por petición.
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")


def es_pago_tarjeta(descripcion: str) -> bool:
    return bool(PATRON_PAGO_TARJETA.search(_sin_acentos(descripcion)))


def es_interes(categoria: str, descripcion: str) -> bool:
    return "interes" in _sin_acentos(categoria or "").lower() or bool(PATRON_INTERES.search(descripcion or ""))


def _razon_dura(m, tipos_cuenta: dict[str, str] | None = None) -> str | None:
    """Motivo por el que UN movimiento es neutral mirándolo solo a él (sin emparejar), o None."""
    tipo = _g(m, "tipo")
    if tipo not in ("income", "expense"):
        return "traslado_app"
    fuente = _g(m, "fuente")
    if fuente == FUENTE_TRANSFERENCIA:
        return "traslado_app"
    if fuente == FUENTE_AJUSTE:
        return "ajuste"
    if fuente == FUENTE_APORTE_META:
        return "aporte_meta"
    cat = _sin_acentos(_g(m, "categoria", "") or "").strip().lower()
    if cat in CATEGORIAS_NEUTRAS and not _descartado(m):
        # Categorías neutras que el sistema o la persona ponen a propósito. «Transferencias» (plural,
        # la de un tercero) NO está en la lista: la neutralidad de un traslado se decide por
        # emparejamiento, decisión o regla, no por la categoría.
        return {"pago de tarjeta": "pago_tarjeta", "ajuste de saldo": "ajuste", "aporte a meta": "aporte_meta"}.get(cat, "categoria")
    if tipo == "expense" and es_pago_tarjeta(_g(m, "descripcion", "") or ""):
        return "pago_tarjeta"
    # Lo que ENTRA a una cuenta de crédito es el abono de un pago, no un ingreso.
    if tipo == "income" and (tipos_cuenta or {}).get(_g(m, "cuenta_id")) == "credito":
        return "abono_tarjeta"
    return None


def tipo_base(m, tipos_cuenta: dict[str, str] | None = None) -> str:
    """Tipo efectivo de UN movimiento mirándolo solo a él (sin emparejar)."""
    return "transfer" if _razon_dura(m, tipos_cuenta) else _g(m, "tipo")


class TiposCuenta(dict):
    """{cuenta_id: tipo} que además lleva, para que todo informe que ya llama
    tipos_efectivos(movs, tipos_cuenta_de(...)) decida igual sin cambiar cada llamada:
      .monedas {cuenta_id: moneda}  (no se emparejan monedas distintas)
      .reglas  {huella: 'traslado'|'real'}  (lo que la persona decidió y pidió recordar)
      .nombres [nombre, ...]  (nombre del perfil / completo: «Enviaste a <tu nombre>» es propio)
      .tolerancia_comision  (pesos de diferencia admitidos entre salida y entrada de un traslado)"""
    monedas: dict[str, str] = {}
    reglas: dict[str, str] = {}
    nombres: list[str] = []
    tolerancia_comision: float = TOLERANCIA_COMISION


# ── Pistas de traslado propio ────────────────────────────────────────────────────────────────
_BANCOS_PROPIOS = r"nu|nequi|bancolombia|davivienda|daviplata|dale|bbva|movii|bre-?b|lulo|rappipay"
# Frases que casi siempre significan «entre MIS cuentas» (pista FUERTE, vale por dos).
PATRON_PROPIO_FUERTE = re.compile(
    r"entre\s+(?:tus|mis)\s+cuentas|\b(?:a|de|desde|hacia)\s+(?:tu|mi)\s+(?:propia\s+)?cuenta\b|\bcajita\b|\bbolsillo\b|"
    rf"\brecarga\s+(?:de\s+|a\s+|en\s+|desde\s+)?(?:mi\s+|tu\s+)?(?:{_BANCOS_PROPIOS})\b|"
    rf"\b(?:{_BANCOS_PROPIOS})\s*(?:→|->|=>|\ba\b|\bhacia\b)\s*(?:{_BANCOS_PROPIOS})\b",
    re.IGNORECASE,
)
_PROPIOS_DESTINO = (
    r"cuenta|nequi|nu|nubank|bancolombia|davivienda|daviplata|dale|bbva|movii|lulo|rappipay|llave|"
    r"bre-?b|ahorros?|cajita|bolsillo|meta|alcancia|vault"
)
# Más frases que significan «es mío» aunque no traigan el nombre: «Envío a mi Nequi», «Bre-B a mi llave»,
# «Consignación a cuenta propia», «Movimiento entre cuentas», «Traslado a ahorro», «Avance en efectivo».
PATRON_PROPIO_FRASES = re.compile(
    rf"\b(?:a|de|desde|hacia|para)\s+(?:mi|tu)\s+(?:propia\s+)?(?:{_PROPIOS_DESTINO})\b|"
    r"\bcuentas?\s+propias?\b|\bpropias?\s+cuentas?\b|\bmismo\s+titular\b|"
    r"\b(?:movimientos?|traslados?)\s+entre\s+cuentas\b|"
    r"\btraslados?\s+(?:a|hacia|de)\s+(?:mi\s+)?(?:cajita|bolsillo|ahorros?|meta|alcancia|vault)\b|"
    r"\bavances?\s+(?:en\s+)?(?:efectivo|cajero|tarjeta|tc|tdc|credito|cupo)\b",
    re.IGNORECASE,
)
_PALABRAS_NOMBRE_VACIAS = {"de", "del", "la", "las", "los", "el", "y", "san", "da", "van"}


def _lista_tokens(texto: str) -> list[str]:
    t = _sin_acentos(texto or "").lower()
    return [x for x in re.findall(r"[a-z]{3,}", t) if x not in _PALABRAS_NOMBRE_VACIAS]


def _tokens_nombre(texto: str) -> set[str]:
    return set(_lista_tokens(texto))


def _es_propio_por_frase(desc: str) -> bool:
    d = _sin_acentos(desc or "")
    return bool(PATRON_PROPIO_FUERTE.search(d) or PATRON_PROPIO_FRASES.search(d))


def menciones_propias(descripcion: str, nombres) -> int:
    """Cuántas palabras del nombre de la persona aparecen en la descripción (apellidos parciales,
    sin tildes ni mayúsculas): 'ENVIASTE A DANIEL PARRADO' con 'Daniel Alfonso Parrado Cárdenas' = 2."""
    toks = _lista_tokens(descripcion)
    d = set(toks)
    if not d:
        return 0
    # Los bancos truncan el nombre al final («DANIEL ALFONSO PARR»): la última palabra puede ser
    # un prefijo (>= 4 letras) de una palabra del nombre que aún no coincidió.
    ult = toks[-1]
    mejor = 0
    for n in nombres or []:
        nt = _tokens_nombre(n)
        c = len(d & nt)
        if len(ult) >= 4 and ult not in nt and any(x.startswith(ult) and x not in d for x in nt):
            c += 1
        mejor = max(mejor, c)
    return mejor


_STOP_HUELLA = {
    "de", "del", "la", "el", "los", "las", "a", "para", "por", "en", "con", "y", "mi", "tu", "su",
    "enviaste", "envio", "envia", "recibiste", "recibi", "transferencia", "transferiste", "transf", "trf",
    "traslado", "pago", "abono", "deposito", "giro", "nequi", "daviplata", "bre", "bancolombia",
    "davivienda", "nu", "movimiento", "cuenta", "ahorros", "desde", "hacia", "pse", "llave",
}


def huella_traslado(descripcion: str) -> str:
    """Huella estable de una descripción para recordar decisiones de traslado: palabras que
    identifican a la contraparte, sin números, fechas ni verbos bancarios. '' si no queda nada útil."""
    t = _sin_acentos(descripcion or "").lower()
    t = re.sub(r"\d+", " ", t)
    toks = [x for x in re.findall(r"[a-z]{2,}", t) if x not in _STOP_HUELLA]
    huella = " ".join(toks[:4])
    return huella if len(huella) >= 4 else ""


def _sin_costo(m) -> bool:
    """False para intereses, comisiones, 4x1000 y rendimientos: jamás son un traslado."""
    from app.costos_financieros import es_costo_o_rendimiento, NOMBRES_SISTEMA
    return not (_g(m, "categoria") in NOMBRES_SISTEMA or es_costo_o_rendimiento(_g(m, "descripcion", "") or ""))


def _fuerza_pista(m, nombres=None) -> int:
    """Cuántas pistas de 'traslado' tiene UN movimiento: descripción tipo traslado (1), marca del
    lector (2), frase de «entre mis cuentas» (2), tu nombre completo (2) o parcial (1), y la
    confirmación de la persona (2)."""
    if not _sin_costo(m):
        return 0
    desc = _g(m, "descripcion", "") or ""
    notas = _g(m, "notas", "") or ""
    f = 0
    if PATRON_TRASLADO.search(_sin_acentos(desc)):  # sin tildes: «Envío» también cuenta
        f += 1
    if MARCA_TRASLADO_PROPIO in notas:
        f += 2
    if MARCA_ES_TRASLADO in notas:
        f += 2
    if _es_propio_por_frase(desc):
        f += 2
    menc = menciones_propias(desc, nombres)
    f += 2 if menc >= 2 else menc
    return f


def _es_pista_fuerte(m, nombres=None) -> bool:
    """Pista que sola basta para decir «posible traslado» aunque no aparezca la otra pata."""
    if not _sin_costo(m):
        return False
    desc = _g(m, "descripcion", "") or ""
    return (MARCA_TRASLADO_PROPIO in (_g(m, "notas", "") or "")
            or _es_propio_por_frase(desc)
            or menciones_propias(desc, nombres) >= 2)


def _decision(m, reglas) -> str | None:
    """'traslado' | 'real' | None: lo que la persona decidió en este movimiento o por regla."""
    notas = _g(m, "notas", "") or ""
    if MARCA_NO_TRASLADO in notas:
        return "real"
    if MARCA_ES_TRASLADO in notas:
        return "traslado"
    if reglas:
        return reglas.get(huella_traslado(_g(m, "descripcion", "") or ""))
    return None


def clasificar(movs, tipos_cuenta: dict[str, str] | None = None) -> dict[str, dict]:
    """{id: {'tipo': 'income'|'expense'|'transfer', 'razon': str, 'par': id|None}} para toda la lista.

    REGLA ÚNICA de qué cuenta como ingreso o gasto. Es neutral ('transfer') lo que NO es plata
    ganada ni gastada: (a) traslados creados en la app, ajustes de saldo y aportes a meta;
    (b) pagos de tarjeta y su abono; (c) PARES detectados entre cuentas propias: un egreso y un
    ingreso del mismo monto y moneda en cuentas distintas del mismo usuario, a <= 2 días, 1:1, con
    al menos una pista de traslado (nombre propio, «a tu cuenta», Bre-B, Nequi...); también con una
    comisión pequeña de diferencia (<= tolerancia, con pistas fuertes); (d) lo que la persona
    marcó («Es un traslado») o recordó por regla; (e) un «posible traslado»: pista fuerte (tu
    nombre, «entre tus cuentas») sin la otra pata todavía. Lo que la persona marcó «No es un
    traslado» nunca es neutral por emparejamiento. Todo lo demás es ingreso/gasto real.
    La neutralidad no depende de la categoría «Transferencias» ni del tipo guardado: una
    transferencia a un tercero es gasto; un traslado propio se reconoce por su pareja o decisión.

    Rendimiento: índice por monto redondeado y ventana de fechas con bisección."""
    movs = list(movs)
    tc = tipos_cuenta if tipos_cuenta is not None else {}
    reglas = getattr(tc, "reglas", None) or {}
    nombres = getattr(tc, "nombres", None) or []
    tol = float(getattr(tc, "tolerancia_comision", TOLERANCIA_COMISION) or 0)
    monedas = getattr(tc, "monedas", None) or {}

    res: dict[str, dict] = {}
    gastos, ingresos = [], []
    for m in movs:
        mid = _g(m, "id")
        razon = _razon_dura(m, tc)
        if razon:
            res[mid] = {"tipo": "transfer", "razon": razon, "par": None}
            continue
        res[mid] = {"tipo": _g(m, "tipo"), "razon": "normal", "par": None}
        dec = _decision(m, reglas)
        if dec == "real":
            continue
        if dec == "traslado":
            res[mid] = {"tipo": "transfer", "razon": "decision" if MARCA_ES_TRASLADO in (_g(m, "notas", "") or "") else "regla", "par": None}
        (gastos if _g(m, "tipo") == "expense" else ingresos).append(m)

    def moneda(m):
        return monedas.get(_g(m, "cuenta_id")) or _g(m, "moneda")

    usados: set = set()

    def emparejar(g, i, razon):
        usados.add(_g(i, "id"))
        usados.add(_g(g, "id"))
        res[_g(g, "id")] = {"tipo": "transfer", "razon": razon, "par": _g(i, "id")}
        res[_g(i, "id")] = {"tipo": "transfer", "razon": razon, "par": _g(g, "id")}

    pg = [x for x in gastos if _g(x, "fecha")]
    pi = [x for x in ingresos if _g(x, "fecha")]
    if pg and pi:
        fuerza = {_g(x, "id"): _fuerza_pista(x, nombres) for x in pg + pi}
        por_monto: dict[int, list] = {}
        for i in pi:
            por_monto.setdefault(round(abs(_g(i, "monto", 0) or 0)), []).append(i)
        claves = {}
        for k, lista in por_monto.items():
            lista.sort(key=lambda x: _g(x, "fecha"))
            claves[k] = [_g(x, "fecha").timestamp() for x in lista]

        orden = sorted(pg, key=lambda x: (_g(x, "fecha"), str(_g(x, "id"))))
        # Pasada 1: mismo monto (a $1), con alguna pista de traslado.
        for g in orden:
            k = round(abs(_g(g, "monto", 0) or 0))
            lista = por_monto.get(k)
            if not lista:
                continue
            t = _g(g, "fecha").timestamp()
            desde = bisect_left(claves[k], t - VENTANA_FESTIVO_SEG)
            hasta = bisect_right(claves[k], t + VENTANA_FESTIVO_SEG)
            fg = fuerza[_g(g, "id")]
            mejor = None
            for i in lista[desde:hasta]:
                iid = _g(i, "id")
                if iid in usados or _g(i, "cuenta_id") == _g(g, "cuenta_id"):
                    continue
                if abs((_g(i, "monto", 0) or 0) - (_g(g, "monto", 0) or 0)) >= 1:
                    continue
                mg, mi = moneda(g), moneda(i)
                if mg and mi and mg != mi:
                    continue
                f = fg + fuerza[iid]
                if not f:
                    continue
                dt = abs(_g(i, "fecha").timestamp() - t)
                if dt > VENTANA_EMPAREJAR_SEG and f < 3:
                    continue  # puente festivo: solo con pistas fuertes
                clave = (-f, dt, str(iid))
                if mejor is None or clave < mejor[0]:
                    mejor = (clave, i)
            if mejor:
                emparejar(g, mejor[1], "par")

        # Pasada 2: con una comisión pequeña de diferencia (sale un poco más de lo que entra);
        # exige pistas fuertes (suma >= 3) porque el monto ya no es idéntico.
        if tol > 0:
            libres_i = sorted((i for i in pi if _g(i, "id") not in usados), key=lambda x: _g(x, "fecha"))
            tiempos = [_g(x, "fecha").timestamp() for x in libres_i]
            for g in orden:
                if _g(g, "id") in usados:
                    continue
                t = _g(g, "fecha").timestamp()
                mejor = None
                for i in libres_i[bisect_left(tiempos, t - VENTANA_EMPAREJAR_SEG):bisect_right(tiempos, t + VENTANA_EMPAREJAR_SEG)]:
                    iid = _g(i, "id")
                    dif = (_g(g, "monto", 0) or 0) - (_g(i, "monto", 0) or 0)
                    if iid in usados or _g(i, "cuenta_id") == _g(g, "cuenta_id") or not (0 < dif <= tol):
                        continue
                    mg, mi = moneda(g), moneda(i)
                    if mg and mi and mg != mi:
                        continue
                    if fuerza[_g(g, "id")] + fuerza[iid] < 3:
                        continue
                    clave = (dif, abs(_g(i, "fecha").timestamp() - t), str(iid))
                    if mejor is None or clave < mejor[0]:
                        mejor = (clave, i)
                if mejor:
                    emparejar(g, mejor[1], "par_comision")

    # «Posible traslado»: pista fuerte y la otra pata aún no está. Neutral hasta que la persona responda.
    for m in gastos + ingresos:
        mid = _g(m, "id")
        if res[mid]["razon"] == "normal" and _es_pista_fuerte(m, nombres):
            res[mid] = {"tipo": "transfer", "razon": "posible", "par": None}
    return res


def notas_con_decision(notas: str | None, decision: str) -> str:
    """`notas` con la decisión de la persona: 'traslado' deja la marca de «es un traslado entre mis
    cuentas»; 'real' deja «no es un traslado» (y quita la pista del lector). La otra marca se retira."""
    partes = [x for x in (notas or "").split(" · ")
              if x and x not in (MARCA_ES_TRASLADO, MARCA_NO_TRASLADO)]
    if decision == "real":
        partes = [x for x in partes if x != MARCA_TRASLADO_PROPIO]
    partes.append(MARCA_ES_TRASLADO if decision == "traslado" else MARCA_NO_TRASLADO)
    return " · ".join(partes)


def sugerir_traslados(movs, tipos_cuenta: dict[str, str] | None = None) -> list[dict]:
    """Sugerencias para la herramienta «Revisar posibles traslados» (nada se aplica solo):
      - 'par': un egreso y un ingreso de igual monto (o con una comisión pequeña) en cuentas distintas,
        a <= 2 días, que NO traen ninguna pista de traslado y por eso hoy cuentan como gasto e ingreso.
      - 'posible': un movimiento con pista fuerte (tu nombre, «entre tus cuentas») cuya otra pata aún
        no se ha importado; hoy es neutral y se pregunta «¿Fue entre tus cuentas?».
    Lo que la persona ya decidió («No es un traslado») no se vuelve a sugerir.
    Devuelve [{'tipo', 'ids': [...], 'diferencia': pesos}] (par: [id_egreso, id_ingreso])."""
    movs = list(movs)
    tc = tipos_cuenta if tipos_cuenta is not None else {}
    reglas = getattr(tc, "reglas", None) or {}
    monedas = getattr(tc, "monedas", None) or {}
    tol = float(getattr(tc, "tolerancia_comision", TOLERANCIA_COMISION) or 0)
    cl = clasificar(movs, tc)
    out = [{"tipo": "posible", "ids": [_g(m, "id")], "diferencia": 0.0}
           for m in movs if cl[_g(m, "id")]["razon"] == "posible"]

    def libre(m):
        return cl[_g(m, "id")]["razon"] == "normal" and _decision(m, reglas) != "real" and _sin_costo(m) and _g(m, "fecha")

    gastos = sorted((m for m in movs if _g(m, "tipo") == "expense" and libre(m)), key=lambda m: (_g(m, "fecha"), str(_g(m, "id"))))
    ingresos = sorted((m for m in movs if _g(m, "tipo") == "income" and libre(m)), key=lambda m: _g(m, "fecha"))
    tiempos = [_g(m, "fecha").timestamp() for m in ingresos]
    usados: set = set()
    for g in gastos:
        t = _g(g, "fecha").timestamp()
        mejor = None
        for i in ingresos[bisect_left(tiempos, t - VENTANA_EMPAREJAR_SEG):bisect_right(tiempos, t + VENTANA_EMPAREJAR_SEG)]:
            iid = _g(i, "id")
            if iid in usados or _g(i, "cuenta_id") == _g(g, "cuenta_id"):
                continue
            dt = abs(_g(i, "fecha").timestamp() - t)
            dif = (_g(g, "monto", 0) or 0) - (_g(i, "monto", 0) or 0)
            if dt > VENTANA_EMPAREJAR_SEG or not (-1 < dif < 1 or 0 < dif <= tol):
                continue
            mg, mi = monedas.get(_g(g, "cuenta_id")) or _g(g, "moneda"), monedas.get(_g(i, "cuenta_id")) or _g(i, "moneda")
            if mg and mi and mg != mi:
                continue
            clave = (abs(dif) >= 1, dt, str(iid))
            if mejor is None or clave < mejor[0]:
                mejor = (clave, i, dif)
        if mejor:
            usados.add(_g(mejor[1], "id"))
            out.append({"tipo": "par", "ids": [_g(g, "id"), _g(mejor[1], "id")], "diferencia": max(round(mejor[2]), 0)})
    return out


def tipos_efectivos(movs, tipos_cuenta: dict[str, str] | None = None) -> dict[str, str]:
    """{id_movimiento: 'income'|'expense'|'transfer'}: el tipo que cuenta para informes. Ver `clasificar`."""
    return {k: v["tipo"] for k, v in clasificar(movs, tipos_cuenta).items()}


def _contexto_de_decisiones(db, owners, out: "TiposCuenta", nombres_extra=None) -> None:
    """Carga en `out` las reglas de traslado y los nombres de las personas dueñas de las cuentas.
    Tolerante: si la tabla aún no existe (script SQL sin correr) sigue sin reglas."""
    from app.models import Perfil
    owners = [o for o in set(owners) if o]
    out.reglas, out.nombres = {}, list(nombres_extra or [])
    if not owners or db is None:
        return
    try:
        from app.models_pendientes import ReglaTraslado
        for r in db.query(ReglaTraslado).filter(ReglaTraslado.usuario_id.in_(owners)).all():
            out.reglas[r.huella] = r.decision
    except Exception:  # noqa: BLE001  (tabla opcional)
        db.rollback()
    for p in db.query(Perfil).filter(Perfil.usuario_id.in_(owners)).all():
        if p.nombre_preferido:
            out.nombres.append(p.nombre_preferido)
        # Nombre completo del titular (de Google), solo para reconocer «Enviaste a <TU NOMBRE>».
        # Columna opcional (perfil_nombre_titular.sql): sin ella solo se usa el nombre preferido.
        try:
            if p.nombre_titular:
                out.nombres.append(p.nombre_titular)
        except Exception:  # noqa: BLE001
            db.rollback()
            break


def tipos_de_cuentas(cuentas, db=None, nombres_extra=None) -> TiposCuenta:
    """TiposCuenta desde objetos Cuenta ya cargados (tipo y moneda). Con `db` también trae las
    reglas de traslado y el nombre de las personas dueñas (mismas decisiones en todos los informes)."""
    out = TiposCuenta()
    out.monedas = {}
    out.reglas, out.nombres = {}, list(nombres_extra or [])
    for c in cuentas:
        out[c.id] = c.tipo
        out.monedas[c.id] = c.moneda
    if db is not None:
        _contexto_de_decisiones(db, [c.usuario_id for c in cuentas], out, nombres_extra)
    return out


def tipos_cuenta_de(db, ids, nombres_extra=None) -> dict[str, str]:
    """{cuenta_id: tipo} para las cuentas dadas (import perezoso: este módulo es puro)."""
    from app.models import Cuenta
    return tipos_de_cuentas(db.query(Cuenta).filter(Cuenta.id.in_(list(ids))).all(), db, nombres_extra)


# ── Moneda base ──────────────────────────────────────────────────────────────────────
# Regla única: todo total se expresa en la moneda base del perfil. Un monto en otra moneda se
# convierte con una tasa (1 origen = tasa base). Sin tasa NO se suma a ciegas: la moneda queda
# marcada en `sin_tasa` para que la pantalla lo avise. Espejo: pwa/src/lib/contabilidad.js (aBase).
def a_base(monto, origen, base, tasas=None):
    """(valor_en_base, convertido). `tasas` = {moneda: unidades de base por 1 de esa moneda}."""
    b = (base or "COP").upper()
    o = (origen or b).upper()
    monto = float(monto or 0)
    if o == b:
        return monto, True
    t = (tasas or {}).get(o)
    if not t or t <= 0:
        return monto, False
    return monto * t, True


def moneda_base_de(db, usuario_id: str) -> str:
    """Moneda base del perfil; sin ella, la moneda de su país (perfiles viejos -> COP)."""
    from app import paises

    try:
        from app.models import Perfil

        p = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
        base = getattr(p, "moneda_base", None) if p else None
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        base = None
    if base:
        return base.upper()
    c = paises.config_pais(paises.pais_de_usuario(db, usuario_id))
    return (c or {}).get("moneda", "COP")


class ConvertidorBase:
    """Callable (monto, moneda_origen) -> monto en base. `sin_tasa` junta las monedas que no se pudieron
    convertir (su monto se deja tal cual, marcado: la pantalla avisa y NO lo suma al total).
    Orden de tasas: la que la persona puso a mano (`tasas_usuario`, privada de ella) > app.fx."""

    def __init__(self, base: str = "COP", tasas_usuario: dict[str, float] | None = None):
        self.base = (base or "COP").upper()
        self.sin_tasa: set[str] = set()
        self._tasas: dict[str, float] = {k.upper(): v for k, v in (tasas_usuario or {}).items() if v and v > 0}

    @classmethod
    def de_usuario(cls, db, usuario_id: str) -> "ConvertidorBase":
        """Base del perfil + tasas manuales de esa persona (fase 2: todas las pantallas lo usan)."""
        base = moneda_base_de(db, usuario_id)
        return cls(base, tasas_manuales_de(db, usuario_id, base))

    def __call__(self, monto, origen=None):
        from app import fx

        o = (origen or self.base).upper()
        if o != self.base and o not in self._tasas and o not in self.sin_tasa:
            t, _f, _fuente = fx.tasa(o, self.base)
            if t:
                self._tasas[o] = t
        valor, ok = a_base(monto, o, self.base, self._tasas)
        if not ok:
            self.sin_tasa.add(o)
        return valor

    def contar(self, monto, origen=None) -> float:
        """Valor en base para SUMAR en un total: sin tasa devuelve 0.0 (no se suma a ciegas; la moneda
        queda en `sin_tasa` y la pantalla lo avisa)."""
        v = self(monto, origen)
        return 0.0 if (origen or self.base).upper() in self.sin_tasa else v

    def sumar(self, pares) -> float:
        return sum(self.contar(m, o) for m, o in pares)


def tasas_manuales_de(db, usuario_id: str, base: str) -> dict[str, float]:
    """{moneda: unidades de `base` por 1 de esa moneda} que la persona fijó a mano (aislado por usuario)."""
    try:
        from app.models import TasaManual

        filas = db.query(TasaManual).filter(TasaManual.usuario_id == usuario_id, TasaManual.base == base.upper()).all()
        return {f.moneda.upper(): f.tasa for f in filas}
    except Exception:  # tabla aún sin migrar: seguir con las tasas del proveedor
        try:
            db.rollback()
        except Exception:
            pass
        return {}


def gastos_por_categoria(db, ids_accesibles, desde: datetime, monedas: dict[str, str] | None = None,
                         base: str = "COP", conv: "ConvertidorBase | None" = None) -> dict[str, float]:
    """{categoria: gasto en moneda base (COP por defecto)} desde `desde` hasta hoy, con la regla contable
    (sin pagos de tarjeta ni traslados). Lo usan los presupuestos y los avisos.
    Se leen 3 días antes de `desde` solo para poder emparejar traslados del borde."""
    from datetime import timedelta

    from app.models import Cuenta, Movimiento

    conv = conv or ConvertidorBase(base)
    ids = list(ids_accesibles)
    if not ids:
        return {}
    if monedas is None:
        monedas = {c.id: c.moneda for c in db.query(Cuenta).filter(Cuenta.id.in_(ids)).all()}
    movs = db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids), Movimiento.fecha >= desde - timedelta(days=3)).all()
    te = tipos_efectivos(movs, tipos_cuenta_de(db, ids))
    out: dict[str, float] = {}
    for m in movs:
        if m.fecha >= desde and te[m.id] == "expense":
            out[m.categoria] = out.get(m.categoria, 0.0) + conv(m.monto, monedas.get(m.cuenta_id, "COP"))
    return out


def tipo_efectivo_receta(tipo: str, categoria: str, descripcion: str) -> str:
    """Para registros sin movimiento aún (recurrentes): mismo criterio individual."""
    return tipo_base({"tipo": tipo, "categoria": categoria, "descripcion": descripcion, "fuente": ""}, None)
