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
PATRON_PAGO_TARJETA = re.compile(
    r"\b(?:pagos?|abonos?|pagaste|abonaste)\s+(?:(?:de|a|la|mi|tu|total|minimo|del)\s+)*"
    r"(?:tarjeta|tarj\.?|tc|tdc|t\.c\.?|visa|master\s?card|amex|american\s+express|diners)\b",
    re.IGNORECASE,
)

# Pistas de que un movimiento es un traslado entre cuentas propias (se usan solo
# para emparejar salida y entrada de igual monto en cuentas distintas).
PATRON_TRASLADO = re.compile(
    r"transfer|traslado|\btrasl\b|entre\s+cuentas|nequi|daviplata|\bdale\b|movii|"
    r"\benvi[oa]|enviaste|recibiste|bre-?b|a\s+mi\s+cuenta|desde\s+mi\s+cuenta",
    re.IGNORECASE,
)

# Marca que dejan los lectores de extractos en `notas` cuando la contraparte parece el propio
# titular u otra cuenta propia: el movimiento SÍ mueve saldo (tiene dirección) y los informes
# lo tratan como traslado solo si aparece su otra pata (ver tipos_efectivos).
MARCA_TRASLADO_PROPIO = "posible_traslado_propio"

# Dirección deducible con certeza de una descripción de transferencia (solo al inicio).
_RE_SALE = re.compile(r"^\s*(?:para\b|enviaste\b|envio\b|transferencia\s+a\b|trf\s+a\b|transferiste\b)", re.IGNORECASE)
_RE_ENTRA = re.compile(r"^\s*(?:de\b|recibiste\b|transferencia\s+de\b|trf\s+de\b|giro\s+de\b|te\s+enviaron\b)", re.IGNORECASE)


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


def tipos_efectivos(movs, tipos_cuenta: dict[str, str] | None = None) -> dict[str, str]:
    """{id_movimiento: 'income'|'expense'|'transfer'} para toda la lista.

    Además de la regla individual, empareja traslados que quedaron registrados
    como un gasto en una cuenta y un ingreso en otra (típico al importar los
    extractos de dos bancos): mismo monto, cuentas distintas, <= 2 días y al menos
    una de las dos descripciones parece traslado. Cada movimiento se usa una vez."""
    movs = list(movs)
    res = {_g(m, "id"): tipo_base(m, tipos_cuenta) for m in movs}

    gastos = [m for m in movs if res[_g(m, "id")] == "expense"]
    ingresos = [m for m in movs if res[_g(m, "id")] == "income"]
    if not gastos or not ingresos:
        return res

    por_monto: dict[int, list] = {}
    for i in ingresos:
        por_monto.setdefault(round(abs(_g(i, "monto", 0) or 0)), []).append(i)

    usados: set = set()
    for g in sorted(gastos, key=lambda x: _g(x, "fecha") or datetime.min):
        candidatos = []
        for i in por_monto.get(round(abs(_g(g, "monto", 0) or 0)), []):
            iid = _g(i, "id")
            if iid in usados or _g(i, "cuenta_id") == _g(g, "cuenta_id"):
                continue
            if abs((_g(i, "monto", 0) or 0) - (_g(g, "monto", 0) or 0)) >= 1:
                continue
            fg, fi = _g(g, "fecha"), _g(i, "fecha")
            if not fg or not fi:
                continue
            dif = abs((fg - fi).total_seconds())
            if dif > VENTANA_EMPAREJAR_SEG:
                continue
            if not (PATRON_TRASLADO.search(_g(g, "descripcion", "") or "")
                    or PATRON_TRASLADO.search(_g(i, "descripcion", "") or "")):
                continue
            candidatos.append((dif, iid, i))
        if candidatos:
            candidatos.sort(key=lambda c: (c[0], str(c[1])))
            _, iid, _i = candidatos[0]
            usados.add(iid)
            res[_g(g, "id")] = "transfer"
            res[iid] = "transfer"
    return res


def tipos_cuenta_de(db, ids) -> dict[str, str]:
    """{cuenta_id: tipo} para las cuentas dadas (import perezoso: este módulo es puro)."""
    from app.models import Cuenta
    return {c.id: c.tipo for c in db.query(Cuenta).filter(Cuenta.id.in_(list(ids))).all()}


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
