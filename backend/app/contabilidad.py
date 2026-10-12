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
    r"a\s+tu\s+cuenta|de\s+tu\s+cuenta|^\s*para\s+\S",
    re.IGNORECASE,
)

# Marca que dejan los lectores de extractos en `notas` cuando la contraparte parece el propio
# titular u otra cuenta propia: el movimiento SÍ mueve saldo (tiene dirección) y los informes
# lo tratan como traslado solo si aparece su otra pata (ver tipos_efectivos).
MARCA_TRASLADO_PROPIO = "posible_traslado_propio"
# El usuario dijo "es un gasto/ingreso real": nunca se empareja como traslado.
MARCA_NO_TRASLADO = "no_es_traslado"


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


def _g(m, campo, defecto=None):
    """Lee un campo de un objeto ORM o de un dict."""
    if isinstance(m, dict):
        return m.get(campo, defecto)
    return getattr(m, campo, defecto)


def _sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")


def es_pago_tarjeta(descripcion: str) -> bool:
    return bool(PATRON_PAGO_TARJETA.search(_sin_acentos(descripcion)))


def es_interes(categoria: str, descripcion: str) -> bool:
    return "interes" in _sin_acentos(categoria or "").lower() or bool(PATRON_INTERES.search(descripcion or ""))


def tipo_base(m, tipos_cuenta: dict[str, str] | None = None) -> str:
    """Tipo efectivo de UN movimiento mirándolo solo a él (sin emparejar)."""
    tipo = _g(m, "tipo")
    if tipo not in ("income", "expense"):
        return "transfer"
    if _g(m, "fuente") in (FUENTE_TRANSFERENCIA, FUENTE_AJUSTE, FUENTE_APORTE_META):
        return "transfer"
    if _sin_acentos(_g(m, "categoria", "") or "").strip().lower() in CATEGORIAS_NEUTRAS:
        return "transfer"
    if tipo == "expense" and es_pago_tarjeta(_g(m, "descripcion", "") or ""):
        return "transfer"
    # Lo que ENTRA a una cuenta de crédito es el abono de un pago, no un ingreso.
    if tipo == "income" and (tipos_cuenta or {}).get(_g(m, "cuenta_id")) == "credito":
        return "transfer"
    return tipo


class TiposCuenta(dict):
    """{cuenta_id: tipo} que además lleva `.monedas` {cuenta_id: moneda}: así los informes que ya
    llaman tipos_efectivos(movs, tipos_cuenta_de(...)) no emparejan traslados de monedas distintas
    sin tener que cambiar cada llamada."""
    monedas: dict[str, str] = {}


def _fuerza_pista(m) -> int:
    """Cuántas pistas de 'traslado' tiene UN movimiento (descripción tipo traslado / marca del lector)."""
    f = 0
    from app.costos_financieros import es_costo_o_rendimiento, NOMBRES_SISTEMA
    if _g(m, "categoria") in NOMBRES_SISTEMA or es_costo_o_rendimiento(_g(m, "descripcion", "") or ""):
        return 0  # intereses, comisiones, 4x1000 y rendimientos jamás se emparejan como traslado
    if PATRON_TRASLADO.search(_g(m, "descripcion", "") or ""):
        f += 1
    if MARCA_TRASLADO_PROPIO in (_g(m, "notas", "") or ""):
        f += 1
    return f


def tipos_efectivos(movs, tipos_cuenta: dict[str, str] | None = None) -> dict[str, str]:
    """{id_movimiento: 'income'|'expense'|'transfer'} para toda la lista.

    Neutral ('transfer', ni ingreso ni gasto) = (a) las dos patas de un traslado creado en la app
    (fuente transferencia_interna), (b) pagos de tarjeta y su abono, y (c) PARES DETECTADOS entre
    cuentas propias: un egreso en una cuenta y un ingreso del MISMO monto y moneda en otra cuenta
    del mismo usuario, a <= 2 días, con al menos una descripción/marca de traslado. Se emparejan
    1:1 con el mejor candidato (más pistas, luego fecha más cercana, luego id). Lo que no tiene
    pareja (transferencia a/de un tercero) sigue siendo gasto/ingreso real.

    Rendimiento: índice por monto redondeado y ventana de fechas con bisección; no hay doble
    recorrido de toda la lista."""
    movs = list(movs)
    res = {_g(m, "id"): tipo_base(m, tipos_cuenta) for m in movs}

    gastos = [m for m in movs if res[_g(m, "id")] == "expense"]
    ingresos = [m for m in movs if res[_g(m, "id")] == "income"]
    if not gastos or not ingresos:
        return res

    monedas = getattr(tipos_cuenta, "monedas", None) or {}

    def moneda(m):
        return monedas.get(_g(m, "cuenta_id")) or _g(m, "moneda")

    por_monto: dict[int, list] = {}
    for i in ingresos:
        if _g(i, "fecha") and not _descartado(i):
            por_monto.setdefault(round(abs(_g(i, "monto", 0) or 0)), []).append(i)
    claves = {}
    for k, lista in por_monto.items():
        lista.sort(key=lambda x: _g(x, "fecha"))
        claves[k] = [_g(x, "fecha").timestamp() for x in lista]

    usados: set = set()
    for g in sorted((x for x in gastos if _g(x, "fecha") and not _descartado(x)), key=lambda x: (_g(x, "fecha"), str(_g(x, "id")))):
        k = round(abs(_g(g, "monto", 0) or 0))
        lista = por_monto.get(k)
        if not lista:
            continue
        t = _g(g, "fecha").timestamp()
        desde = bisect_left(claves[k], t - VENTANA_EMPAREJAR_SEG)
        hasta = bisect_right(claves[k], t + VENTANA_EMPAREJAR_SEG)
        fg = _fuerza_pista(g)
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
            fuerza = fg + _fuerza_pista(i)
            if not fuerza:
                continue
            clave = (-fuerza, abs(_g(i, "fecha").timestamp() - t), str(iid))
            if mejor is None or clave < mejor[0]:
                mejor = (clave, iid)
        if mejor:
            usados.add(mejor[1])
            res[_g(g, "id")] = "transfer"
            res[mejor[1]] = "transfer"
    return res


def tipos_de_cuentas(cuentas) -> TiposCuenta:
    """TiposCuenta desde objetos Cuenta ya cargados (tipo y moneda)."""
    out = TiposCuenta()
    out.monedas = {}
    for c in cuentas:
        out[c.id] = c.tipo
        out.monedas[c.id] = c.moneda
    return out


def tipos_cuenta_de(db, ids) -> dict[str, str]:
    """{cuenta_id: tipo} para las cuentas dadas (import perezoso: este módulo es puro)."""
    from app.models import Cuenta
    out = TiposCuenta()
    out.monedas = {}
    for c in db.query(Cuenta).filter(Cuenta.id.in_(list(ids))).all():
        out[c.id] = c.tipo
        out.monedas[c.id] = c.moneda
    return out


def gastos_por_categoria(db, ids_accesibles, desde: datetime, monedas: dict[str, str] | None = None) -> dict[str, float]:
    """{categoria: gasto en COP} desde `desde` hasta hoy, con la regla contable
    (sin pagos de tarjeta ni traslados). Lo usan los presupuestos y los avisos.
    Se leen 3 días antes de `desde` solo para poder emparejar traslados del borde."""
    from datetime import timedelta

    from app.fx import convertir_a_cop
    from app.models import Cuenta, Movimiento

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
            out[m.categoria] = out.get(m.categoria, 0.0) + convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP"))
    return out


def tipo_efectivo_receta(tipo: str, categoria: str, descripcion: str) -> str:
    """Para registros sin movimiento aún (recurrentes): mismo criterio individual."""
    return tipo_base({"tipo": tipo, "categoria": categoria, "descripcion": descripcion, "fuente": ""}, None)
