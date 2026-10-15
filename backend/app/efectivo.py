"""Efectivo: reconocer retiros de cajero y depósitos en efectivo. Puro, sin base de datos.

Regla (ver contabilidad.py y docs/REGLA_UNICA_INGRESOS_GASTOS.md): sacar plata del cajero NO es
un gasto, es pasarla de tu banco a tu bolsillo. Se ofrece convertirlo en traslado hacia la cuenta
«Efectivo»: mueve saldos pero no suma ni resta a ingresos/gastos. Un depósito/consignación en
efectivo es el traslado inverso (del Efectivo al banco).
"""
import re
import unicodedata

NOMBRE_CUENTA_EFECTIVO = "Efectivo"
ICONO_EFECTIVO = "💵"

_RETIRO = re.compile(r"\b(retiro|retiros|cajero|corresponsal|atm|avance en efectivo)\b")
# «Retiro» de un costo («comision retiro cajero ajeno») es un cobro: sigue siendo gasto.
_COBRO = re.compile(r"\b(comision|cobro|costo|cuota de manejo|iva)\b")
_DEPOSITO = re.compile(r"\b(deposito|consignacion|consig)\b.*\b(efectivo|cajero|corresponsal|ventanilla|sucursal)\b"
                       r"|\b(deposito|consignacion) en efectivo\b|\bconsignacion\b")


def _norm(texto: str | None) -> str:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def sugerencia_efectivo(tipo: str | None, descripcion: str | None) -> str | None:
    """'retiro' (salida del banco -> Efectivo), 'deposito' (entrada al banco <- Efectivo) o None.
    Solo con la dirección correcta: un retiro es expense; un depósito es income."""
    d = _norm(descripcion)
    if not d:
        return None
    if tipo == "expense" and _RETIRO.search(d) and not _COBRO.search(d):
        return "retiro"
    if tipo == "income" and _DEPOSITO.search(d):
        return "deposito"
    return None
