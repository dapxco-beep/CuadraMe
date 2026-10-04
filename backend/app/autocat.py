"""Categorización automática transparente.

Cuando la app pone sola la categoría de un movimiento (por una regla del
usuario, por un comercio conocido o por parecerse a movimientos del usuario),
lo deja marcado como "sin confirmar" y guarda la razón, para que la pantalla
muestre una insignia 'Auto' y el usuario pueda confirmarla o corregirla.
"""
import re
import unicodedata

from sqlalchemy.orm import Session

from app.classifier import aplicar_reglas, build_model, classify
from app.comercios_conocidos import clasificar_por_diccionario
from app.contabilidad import CATEGORIA_PAGO_TARJETA, es_pago_tarjeta
from app.models import Categoria, Movimiento, ReglaCategoria

# fuente del clasificador -> razón que se guarda y se muestra al usuario
ORIGEN_POR_FUENTE = {
    "regla": "regla",
    "regla_tarjeta": "regla",
    "diccionario": "comercio",
    "learned": "similar",
}
# Nombres que el sistema usa por su cuenta y no dependen de la lista del usuario.
CATEGORIAS_DE_SISTEMA = {CATEGORIA_PAGO_TARJETA, "Transferencia", "Transferencias"}


def origen_de(fuente: str | None) -> str | None:
    return ORIGEN_POR_FUENTE.get(fuente or "")


def datos_auto(origen: str | None) -> dict:
    """Campos de Movimiento según si la categoría la puso la app o el usuario.
    'Otros' sin razón no es 'auto': simplemente no se pudo categorizar."""
    if origen:
        return {"cat_origen": origen, "cat_confirmada": False}
    return {"cat_origen": None, "cat_confirmada": True}


def ajustar_a_categorias_usuario(db: Session, usuario_id: str, categoria: str) -> str:
    """Si el usuario renombró/ocultó una categoría base, el diccionario puede
    sugerir un nombre que ya no existe en su lista (movimiento huérfano). En ese
    caso cae en 'Otros'. Si el usuario aún no tiene lista, no se toca nada."""
    if not categoria or categoria in CATEGORIAS_DE_SISTEMA:
        return categoria
    filas = db.query(Categoria.nombre, Categoria.activa).filter(Categoria.usuario_id == usuario_id).all()
    if not filas:
        return categoria
    activas = {n.lower() for n, a in filas if a}
    if categoria.lower() in activas:
        return categoria
    return "Otros"


def movimientos_confirmados(db: Session, usuario_id: str) -> list[dict]:
    """Historial para aprender: solo lo que el usuario confirmó o escribió él
    mismo — así el modelo no se entrena con sus propias suposiciones."""
    movs = (
        db.query(Movimiento)
        .filter(
            Movimiento.usuario_id == usuario_id,
            Movimiento.categoria != "Otros",
            Movimiento.cat_confirmada.isnot(False),
        )
        .all()
    )
    return [{"descripcion": m.descripcion, "categoria": m.categoria, "tipo": m.tipo} for m in movs]


def clasificar_lote_detalle(db: Session, usuario_id: str, descripciones: list[str]) -> list[tuple[str, str | None]]:
    """(categoría, origen) para cada descripción. Modelo armado una sola vez."""
    reglas = (
        db.query(ReglaCategoria).filter(ReglaCategoria.usuario_id == usuario_id)
        .order_by(ReglaCategoria.prioridad.desc()).all()
    )
    modelo = build_model(movimientos_confirmados(db, usuario_id))
    salida = []
    for d in descripciones:
        if es_pago_tarjeta(d):
            salida.append((CATEGORIA_PAGO_TARJETA, "regla"))
            continue
        r = aplicar_reglas(d, reglas) or classify(d, modelo) or clasificar_por_diccionario(d)
        if not r:
            salida.append(("Otros", None))
        else:
            salida.append((ajustar_a_categorias_usuario(db, usuario_id, r["categoria"]), origen_de(r.get("fuente"))))
    return salida


# --- patrón de comercio para "aplicar a todos los de este comercio" -----------

_PREFIJOS = re.compile(
    r"^\s*(compra|pago|retiro|abono|cargo|transferencia|consignacion|consignación|debito|débito)"
    r"(\s+(en|a|de|por|desde|pse|nequi|tarjeta|tc|td))*\s+",
    re.IGNORECASE,
)
_CORTES = re.compile(r"\s+(con\s+tarjeta|con\s+tc|con\s+td|tarjeta|ref\b|nro\b|no\.|#|cuenta\b|cta\b|\d{3,})", re.IGNORECASE)


def patron_de_comercio(descripcion: str) -> str:
    """Saca el nombre del comercio de una descripción bancaria, p. ej.
    'Compra en JUAN VALDEZ SKANDIA con tarjeta débito' -> 'JUAN VALDEZ SKANDIA'."""
    texto = (descripcion or "").strip()
    sin_prefijo = _PREFIJOS.sub("", texto, count=1)
    m = _CORTES.search(sin_prefijo)
    if m:
        sin_prefijo = sin_prefijo[: m.start()]
    patron = re.sub(r"\s+", " ", sin_prefijo).strip(" -*.,:")
    if len(patron) < 2:
        patron = re.sub(r"\s+", " ", texto).strip()
    return patron[:60]


def es_emoji(valor: str) -> bool:
    """Valida que sea un emoji (o secuencia de emojis) y no texto: sin letras,
    números ni espacios, de 1 a 16 caracteres Unicode."""
    if not valor or len(valor) > 16:
        return False
    alguno = False
    for ch in valor:
        cat = unicodedata.category(ch)
        if cat[0] in ("L", "N", "Z") or ch in "\n\t\r":
            return False
        if cat in ("So", "Sk", "Sm", "Sc") or ord(ch) >= 0x1F000:
            alguno = True
    return alguno
