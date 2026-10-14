"""Categorización automática transparente.

Cuando la app pone sola la categoría de un movimiento (por una regla del
usuario, por un comercio conocido o por parecerse a movimientos del usuario),
lo deja marcado como "sin confirmar" y guarda la razón, para que la pantalla
muestre una insignia 'Auto' y el usuario pueda confirmarla o corregirla.
"""
import re
import unicodedata

from sqlalchemy.orm import Session

from app.calidad_categorias import origen_tras_edicion  # noqa: F401  (se reexporta para los routers)
from app.classifier import aplicar_reglas, build_model, classify
from app.clave_comercio import clave_comercio, es_huella_peligrosa, huella_en_descripcion
from app.comercios_conocidos import clasificar_por_diccionario
from app.costos_financieros import NOMBRES_SISTEMA, clasificar_costo
from app.diccionario_categorias import CATEGORIA_RESPALDO
from app import memoria_usuario as mu
from app.contabilidad import CATEGORIA_PAGO_TARJETA, es_pago_tarjeta
from app.models import Categoria, Movimiento, ReglaCategoria

# fuente del clasificador -> razón que se guarda y se muestra al usuario
ORIGEN_POR_FUENTE = {
    "regla": "regla",
    "regla_tarjeta": "regla",
    "diccionario": "comercio",
    "learned": "similar",
    "historial": "similar",  # lo que ESTE usuario ya confirmó para el mismo beneficiario/comercio
    "senales": "similar",
}
# Nombres que el sistema usa por su cuenta y no dependen de la lista del usuario.
CATEGORIAS_DE_SISTEMA = {CATEGORIA_PAGO_TARJETA, "Transferencia", "Transferencias", *NOMBRES_SISTEMA}


def origen_de(fuente: str | None) -> str | None:
    return ORIGEN_POR_FUENTE.get(fuente or "")


def datos_auto(origen: str | None) -> dict:
    """Campos de Movimiento según si la categoría la puso la app o el usuario.
    'Otros' sin razón no es 'auto': simplemente no se pudo categorizar."""
    if origen:
        return {"cat_origen": origen, "cat_confirmada": False}
    return {"cat_origen": None, "cat_confirmada": True}


_BASE = {"comida", "transporte", "ocio", "hogar", "salud", "transferencias", "ingresos", "otros"}


def _activas_de(db: Session, usuario_id: str) -> set[str]:
    filas = db.query(Categoria.nombre, Categoria.activa).filter(Categoria.usuario_id == usuario_id).all()
    if not filas:
        return set(_BASE)  # aún no tiene lista: se le crearán las 8 base
    return {n.lower() for n, a in filas if a}


def _ajustar(activas: set[str], categoria: str) -> str:
    """Categoría sugerida -> una que el usuario realmente tenga. Si renombró u
    ocultó la sugerida se prueba su categoría de respaldo (Suscripciones -> Ocio);
    si tampoco existe, cae en 'Otros' (nunca queda un movimiento huérfano)."""
    if not categoria or categoria in CATEGORIAS_DE_SISTEMA:
        return categoria
    if categoria.lower() in activas:
        return categoria
    respaldo = CATEGORIA_RESPALDO.get(categoria)
    if respaldo and respaldo.lower() in activas:
        return respaldo
    return "Otros"


def ajustar_a_categorias_usuario(db: Session, usuario_id: str, categoria: str) -> str:
    return _ajustar(_activas_de(db, usuario_id), categoria)


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


# Un parecido aprendido por debajo de esta confianza cede ante una marca conocida del diccionario.
UMBRAL_APRENDIDO_FUERTE = 0.8


def decidir_categoria(
    descripcion: str, reglas: list, modelo: dict, activas: set[str], texto_extra: str = "",
    historial: dict | None = None, contexto: dict | None = None,
) -> dict | None:
    """Decisión PURA (sin base de datos) de la categoría: pago de tarjeta -> reglas
    del usuario -> modelo aprendido -> diccionario. La usan ClasificadorUsuario y
    el script de evaluación offline (tools/evaluar_clasificador.py), así lo que se
    mide es exactamente lo que corre en producción.

    `historial` = {"memoria", "senales"} (memoria_usuario, del propio usuario) y `contexto` =
    {monto, fecha, tipo, cuenta_tipo}: ambos opcionales. Con historial: lo que el usuario ya
    confirmó para ese beneficiario/comercio (también personas) gana al parecido por palabras;
    dos categorías en pugna = ambiguo (no se propone); y al final las señales (monto, día,
    pasarela...) proponen solo si están seguras, si no se abstiene."""
    if es_pago_tarjeta(descripcion):
        # El pago de una tarjeta no es un gasto (las compras ya se contaron).
        return {"categoria": CATEGORIA_PAGO_TARJETA, "tipo": "expense", "confianza": 1.0,
                "fuente": "regla_tarjeta", "origen": "regla", "razon": "es el pago de una tarjeta"}
    r = aplicar_reglas(descripcion, reglas)
    if not r:
        # Los cobros/rendimientos del banco (4x1000, cuota de manejo, intereses...) son categorías de
        # SISTEMA: ni el historial ni una palabra suelta los pisan (solo una regla explícita del usuario).
        r = clasificar_costo(descripcion)
    memoria = (historial or {}).get("memoria")
    if not r and memoria:
        h = mu.consultar_memoria(descripcion, memoria)
        if h and h["estado"] == "ambiguo":
            return None  # dos categorías en pugna: que decida el usuario (ver opciones_ambiguas)
        if h and h["categoria"]:
            cat = _ajustar(activas, h["categoria"])
            if cat != "Otros" or h["categoria"] == "Otros":
                veces = f"{h['n']} veces" if h["n"] > 1 else "1 vez"
                r = {"categoria": cat, "tipo": (contexto or {}).get("tipo") or h.get("tipo") or "expense",
                     "confianza": h["confianza"], "fuente": "historial",
                     "razon": f"aprendida de tu historial ({veces})"}
    if not r:
        aprendido = classify(descripcion, modelo)
        r = aprendido
        if aprendido and aprendido.get("confianza", 1.0) < UMBRAL_APRENDIDO_FUERTE:
            # Parecido débil con otros movimientos (palabras sueltas en común): si el diccionario
            # reconoce una MARCA concreta, esa señal pública pesa más que el parecido.
            d = clasificar_por_diccionario(f"{descripcion} {texto_extra}".strip())
            if d and d.get("palabra") and d["categoria"] not in ("Transferencias",) and d["categoria"] != aprendido["categoria"]:
                r = None
    if not r:
        r = clasificar_por_diccionario(f"{descripcion} {texto_extra}".strip())
        if r:
            r = {**r, "categoria": _ajustar(activas, r["categoria"])}
            if r["categoria"] == "Otros":
                r = None  # la categoría sugerida no existe para él: mejor preguntarle
    sen = (historial or {}).get("senales")
    if sen and (not r or (r.get("fuente") == "diccionario" and r.get("categoria") == "Transferencias"
                          and r.get("confianza", 1) < mu.UMBRAL_PROPUESTA)):
        # Sin nada mejor (o solo un «Transferencias» a ciegas): las señales proponen si están seguras.
        s = mu.predecir_senales(descripcion, contexto, sen, memoria)
        if s:
            cat = _ajustar(activas, s["categoria"])
            if cat != "Otros":
                r = {"categoria": cat, "tipo": (contexto or {}).get("tipo") or "expense",
                     "confianza": s["confianza"], "fuente": "senales", "razon": s["razon"]}
    if not r:
        return None
    return {**r, "origen": origen_de(r.get("fuente")), "tentativa": r.get("confianza", 1) < mu.UMBRAL_PROPUESTA}


class ClasificadorUsuario:
    """ÚNICO punto donde se decide la categoría de un movimiento nuevo. Orden:
      1) reglas del usuario (huella exacta primero, luego 'contiene'),
      2) modelo aprendido de sus movimientos confirmados,
      3) diccionario de palabras clave,
      4) sin resultado -> 'Otros' y se le pregunta.
    Cada resultado trae la RAZÓN ('por tu regla «vento coliving»'). Carga reglas,
    modelo y categorías una sola vez: sirve para clasificar lotes grandes."""

    def __init__(self, db: Session, usuario_id: str):
        self.db = db
        self.usuario_id = usuario_id
        self.reglas = (
            db.query(ReglaCategoria).filter(ReglaCategoria.usuario_id == usuario_id)
            .order_by(ReglaCategoria.prioridad.desc()).all()
        )
        self.modelo = build_model(movimientos_confirmados(db, usuario_id))
        self.activas = _activas_de(db, usuario_id)

    def clasificar(self, descripcion: str, texto_extra: str = "") -> dict | None:
        """dict con categoria, tipo, confianza, fuente, origen, razon; None si no se reconoce."""
        return decidir_categoria(descripcion, self.reglas, self.modelo, self.activas, texto_extra)

    def detalle(self, descripcion: str) -> tuple[str, str | None]:
        r = self.clasificar(descripcion)
        return (r["categoria"], r["origen"]) if r else ("Otros", None)


def clasificar_lote_detalle(db: Session, usuario_id: str, descripciones: list[str]) -> list[tuple[str, str | None]]:
    """(categoría, origen) para cada descripción. Modelo armado una sola vez."""
    c = ClasificadorUsuario(db, usuario_id)
    return [c.detalle(d) for d in descripciones]


def aplicar_a_anteriores(
    db: Session, usuario_id: str, huella: str, categoria: str, excluir_ids: set[str] | None = None,
) -> int:
    """'Aplicar también a los anteriores': recategoriza (y confirma) los movimientos
    pasados del usuario cuya huella de comercio coincide. Respeta permisos de edición
    y no toca transferencias internas. Sin commit."""
    if not huella:
        return 0
    from app.compartidos import cuentas_ids_accesibles, puede_editar_cuenta
    from app.models import Cuenta

    excluir_ids = excluir_ids or set()
    ids_cuentas = cuentas_ids_accesibles(db, usuario_id)
    movs = (
        db.query(Movimiento)
        .filter(
            Movimiento.cuenta_id.in_(ids_cuentas),
            Movimiento.tipo != "transfer",
            Movimiento.fuente != "transferencia_interna",
        )
        .all()
    )
    editables: dict[str, bool] = {}
    n = 0
    for m in movs:
        if m.id in excluir_ids or not huella_en_descripcion(huella, m.descripcion or ""):
            continue
        if m.categoria == categoria and m.cat_confirmada is not False:
            continue  # ya está así y confirmada
        if m.cuenta_id not in editables:
            c = db.query(Cuenta).filter(Cuenta.id == m.cuenta_id).first()
            editables[m.cuenta_id] = bool(c and puede_editar_cuenta(db, usuario_id, c))
        if not editables[m.cuenta_id]:
            continue
        m.cat_origen = origen_tras_edicion(m.cat_origen, m.categoria, categoria)
        m.categoria = categoria
        m.cat_confirmada = True
        n += 1
    return n


# --- reglas aprendidas (una por huella de comercio) ---------------------------

def guardar_regla_aprendida(
    db: Session, usuario_id: str, descripcion: str, categoria: str, tipo: str | None = None,
    confirmar_peligrosa: bool = False,
) -> dict:
    """Guarda (o actualiza) la regla del comercio de esta descripción.
    - Si ya hay una regla con la misma huella, se ACTUALIZA: nunca dos reglas
      contradictorias para el mismo comercio.
    - Huellas demasiado amplias (una palabra de <4 letras, palabras vacías) no se
      guardan sin confirmar. No hace commit: lo hace quien llama."""
    huella = clave_comercio(descripcion)
    peligro = es_huella_peligrosa(huella)
    if peligro and not confirmar_peligrosa:
        return {"guardada": False, "huella": huella, "motivo": peligro, "requiere_confirmacion": bool(huella)}
    existentes = db.query(ReglaCategoria).filter(ReglaCategoria.usuario_id == usuario_id).all()
    regla = next((r for r in existentes if clave_comercio(r.patron) == huella), None)
    actualizada = regla is not None
    if regla:
        regla.categoria = categoria
        if tipo:
            regla.tipo = tipo
    else:
        regla = ReglaCategoria(usuario_id=usuario_id, patron=huella, categoria=categoria, tipo=tipo, prioridad=0)
        db.add(regla)
    return {"guardada": True, "huella": huella, "actualizada": actualizada, "motivo": None, "requiere_confirmacion": False}


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
