"""Varias cuentas del MISMO banco (p. ej. 'Nu Colombia' de ahorros y 'Nu Tarjeta' de crédito).

El nombre del banco no basta para saber a cuál va un movimiento, un correo o un
extracto. Este módulo usa el TIPO de producto como señal de desempate:

  texto ('tarjeta de crédito', 'cupo', 'pago mínimo' ...)  ->  'credito'
  texto ('cuenta de ahorros', 'saldo disponible', 'Cajita' ...) -> 'debito'

Regla de oro: si tras usar dígitos, alias y tipo sigue habiendo empate, NO se
adivina; quien llama decide (preguntar, o el camino más seguro de cada flujo).
"""
import re
import unicodedata

CREDITO = "credito"
DEBITO = "debito"
# Tipos de cuenta que se comportan como "débito/ahorro" para este desempate.
_TIPOS_DEBITO = {"ahorro", "ahorros", "corriente", "debito", "nomina", None, ""}

# (patrón sobre texto sin acentos y en minúscula, peso)
_SENALES_CREDITO = [
    (r"tarjetas? (?:de )?credito", 3), (r"\bcredito\b", 1), (r"\bcupo\b", 2),
    (r"fecha (?:limite )?de pago", 2), (r"pago minimo", 2), (r"pago total", 1),
    (r"\bt\.?c\.?\b", 1), (r"\btdc\b", 1), (r"cuotas? (?:pendientes|por pagar)", 1),
    (r"extracto (?:de )?(?:la )?tarjeta", 3), (r"intereses? de (?:mora|financiacion)", 1),
]
_SENALES_DEBITO = [
    (r"tarjetas? (?:de )?debito", 3), (r"\bdebito\b", 1), (r"cuentas? de ahorros?", 3),
    (r"\bahorros?\b", 1), (r"saldo disponible", 2), (r"\bcajita\b", 3), (r"cuenta corriente", 3),
    (r"\bbolsillos?\b", 1), (r"retiro en cajero", 1),
]

# Palabras que describen el producto, no el banco: no sirven para casar nombres.
_GENERICAS = {
    "tarjeta", "credito", "debito", "ahorro", "ahorros", "cuenta", "visa", "mastercard", "master",
    "amex", "banco", "colombia", "tdc", "tc", "de", "del", "la", "el", "mi", "mis", "para", "con", "wallet",
}


def sin_acentos(texto: str | None) -> str:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def palabras_marca(texto: str | None) -> set[str]:
    """Palabras que identifican la entidad ('nu', 'bancolombia'), sin las genéricas del producto."""
    return {
        w for w in re.split(r"[^a-z0-9]+", sin_acentos(texto))
        if len(w) >= 2 and not w.isdigit() and w not in _GENERICAS
    }


def producto_de_texto(texto: str | None) -> str | None:
    """'credito' | 'debito' | None según las pistas del texto. Si pesan igual, None."""
    t = sin_acentos(texto)
    if not t.strip():
        return None
    c = sum(p for rx, p in _SENALES_CREDITO if re.search(rx, t))
    d = sum(p for rx, p in _SENALES_DEBITO if re.search(rx, t))
    if c == d:
        return None
    return CREDITO if c > d else DEBITO


def producto_de_cuenta(cuenta) -> str | None:
    """'credito' para tarjetas, 'debito' para ahorro/corriente; None para efectivo/inversión."""
    tipo = (getattr(cuenta, "tipo", None) or "").lower()
    if tipo == "credito":
        return CREDITO
    if tipo in _TIPOS_DEBITO:
        return DEBITO
    return None


def filtrar_por_producto(candidatas: list, producto: str | None) -> list:
    """Candidatas del tipo pedido; si el filtro no deja ninguna, devuelve la lista original."""
    if not producto:
        return candidatas
    hit = [c for c in candidatas if producto_de_cuenta(c) == producto]
    return hit or candidatas


def etiqueta_producto(cuenta) -> str:
    """Rótulo en lenguaje simple para mostrarle a la persona."""
    p = producto_de_cuenta(cuenta)
    return "Tarjeta de crédito" if p == CREDITO else ("Débito/Ahorros" if p == DEBITO else "Otra cuenta")


def pregunta_de_cuentas(cuentas: list) -> str:
    """'¿Es la tarjeta de crédito (Nu Tarjeta) o la cuenta de ahorros (Nu Colombia)?'"""
    partes = [
        f"{'la tarjeta de crédito' if producto_de_cuenta(c) == CREDITO else 'la cuenta de ahorros/débito'} ({c.nombre})"
        for c in cuentas
    ]
    return "¿Es " + " o ".join(partes) + "?"


def aviso_cuenta_distinta(cuenta, texto: str, cuentas: list) -> str | None:
    """Aviso (no bloquea) cuando el extracto parece de OTRO producto del mismo banco:
    p. ej. el PDF habla de cupo y pago mínimo pero se eligió la cuenta de ahorros, y la
    persona tiene una tarjeta del mismo banco. Solo avisa si hay una candidata clara."""
    producto = producto_de_texto(texto)
    if not producto or producto_de_cuenta(cuenta) in (producto, None):
        return None
    marca = palabras_marca(getattr(cuenta, "nombre", ""))
    otras = [
        c for c in cuentas
        if c.id != cuenta.id and producto_de_cuenta(c) == producto and marca & palabras_marca(getattr(c, "nombre", ""))
    ]
    if len(otras) != 1:
        return None
    que = "una tarjeta de crédito" if producto == CREDITO else "una cuenta de ahorros o débito"
    return f"Este extracto parece de {que}, pero lo vas a conciliar con «{cuenta.nombre}». ¿Será «{otras[0].nombre}»?"
