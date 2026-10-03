"""
Ahorcado con palabras de finanzas — la gamificación de CuadraMe. Las vidas
(intentos de juego) se ganan cumpliendo hitos financieros reales, no se
compran ni se regalan gratis: constancia (rachas) y metas cumplidas.
"""
import random
import unicodedata

PALABRAS = [
    ("AHORRO", "Guardar dinero para el futuro"),
    ("PRESUPUESTO", "Plan de cuánto vas a gastar"),
    ("INTERES", "Lo que te cobra o te paga el banco"),
    ("INVERSION", "Poner tu dinero a producir más dinero"),
    ("DEUDA", "Dinero que debes pagar"),
    ("PATRIMONIO", "Todo lo que tienes menos lo que debes"),
    ("LIQUIDEZ", "Qué tan fácil puedes convertir algo en efectivo"),
    ("DIVIDENDO", "Ganancia que reparte una empresa a sus accionistas"),
    ("HIPOTECA", "Crédito para comprar vivienda"),
    ("RECURRENTE", "Un gasto que se repite cada mes"),
    ("SUSCRIPCION", "Pago mensual por un servicio, como streaming"),
    ("EFECTIVO", "Dinero en billetes y monedas"),
    ("TRANSFERENCIA", "Mover dinero de una cuenta a otra"),
    ("CATEGORIA", "Grupo en el que clasificas un gasto"),
    ("SALDO", "Cuánto dinero tienes disponible"),
    ("CUOTA", "Pago parcial y periódico de una deuda"),
    ("REEMBOLSO", "Devolución de un dinero pagado de más"),
    ("EXTRACTO", "Documento con el detalle de movimientos de una cuenta"),
    ("BOLSILLO", "Compartimento donde guardas dinero para un propósito"),
    ("CONCILIACION", "Comparar tus registros contra el banco"),
]

ABECEDARIO = "ABCDEFGHIJKLMNÑOPQRSTUVWXYZ"


def _sin_tilde(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def palabra_aleatoria() -> tuple[str, str]:
    return random.choice(PALABRAS)


def progreso_palabra(palabra: str, letras_intentadas: list[str]) -> str:
    return " ".join(letra if letra in letras_intentadas else "_" for letra in palabra)


def estado_partida(palabra: str, letras_intentadas: list[str], intentos_restantes: int) -> str:
    if all(letra in letras_intentadas for letra in palabra):
        return "ganada"
    if intentos_restantes <= 0:
        return "perdida"
    return "jugando"
