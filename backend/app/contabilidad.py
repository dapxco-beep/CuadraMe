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
CATEGORIA_PAGO_TARJETA = "Pago de tarjeta"
CATEGORIA_AJUSTE = "Ajuste de saldo"
CATEGORIAS_NEUTRAS = {"transferencia", "pago de tarjeta", "ajuste de saldo"}

# "pago tarjeta", "pago de tarjeta de crédito", "abono a TC", "pago visa", "pago tarj credito".
# NO casa con "pago con tarjeta en Éxito" (eso es una COMPRA): después de pago/abono solo
# se admiten conectores (de, a, la, mi, total, mínimo), no "con".
PATRON_PAGO_TARJETA = re.compile(
    r"\b(?:pagos?|abonos?)\s+(?:(?:de|a|la|mi|total|minimo|del)\s+)*"
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
    if _g(m, "fuente") in (FUENTE_TRANSFERENCIA, FUENTE_AJUSTE):
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
