"""«Por categorizar»: UNA sola definición de qué movimientos esperan categoría.

Antes, todo movimiento con cat_confirmada = False contaba como pendiente, incluso el que una
regla del usuario, el aprendizaje o el diccionario ya habían categorizado con seguridad; por
eso «casi todo» salía por categorizar. Ahora SOLO cuenta (y esta función es lo único que
deciden el contador de Inicio, el de Movimientos, la lista de pendientes y los consejos):

  a) «otros»    -> categoría «Otros» o vacía (y el usuario no dijo «dejar como está»),
  b) «baja»     -> la puso la app sola con poca confianza (origen distinto de regla,
                   comercio conocido o aprendizaje: «sugerida» desde un correo, Wallet/atajo
                   sin confirmar; estos últimos además están en la bandeja «¿son tuyos?»),
  c) «marcada»  -> el usuario la marcó él mismo para revisar (cat_origen = 'marcada').

NO cuentan: lo categorizado con confianza alta (origen regla | comercio | similar, aunque siga
«Auto»: se puede corregir cuando quiera), los comercios silenciados por el usuario, traslados, pagos de tarjeta,
ajustes de saldo, aportes a metas y los rendimientos/costos que pone el sistema.

Estados guardados (sin columnas nuevas): cat_origen = 'dejada' (usuario: «dejar como está»,
sale de pendientes aunque siga en Otros) y cat_origen = 'marcada'. Los silencios por comercio
viven en la tabla comercios_silenciados (models_pendientes.py).
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.clave_comercio import clave_comercio, es_huella_peligrosa
from app.contabilidad import FUENTE_AJUSTE, FUENTE_APORTE_META, FUENTE_TRANSFERENCIA, tipo_base
from app.costos_financieros import NOMBRES_SISTEMA
from app.models import Movimiento
from app.models_pendientes import TIPOS_SILENCIO, ComercioSilenciado

ORIGEN_DEJADA = "dejada"
ORIGEN_MARCADA = "marcada"
# Quién categorizó con seguridad: regla del usuario, diccionario de comercios, aprendizaje de sus movimientos.
ORIGENES_CONFIANZA_ALTA = {"regla", "comercio", "similar"}
CATEGORIAS_SIN_DEFINIR = {"", "otros", "sin categoria", "sin categoría"}
_SISTEMA_MIN = {n.lower() for n in NOMBRES_SISTEMA}
SILENCIOS_QUE_OCULTAN = ("no_preguntar", "ocultar")

MOTIVOS = ("marcada", "otros", "baja")
# Regla única de Daniel: la app solo pide categorizar lo que se repite MÁS de 3 veces (>= 4) o lo que
# el cliente marcó él mismo. El resto queda con la categoría que le asignó el modelo/reglas (o «Otros»)
# sin pedir nada y sin contar como pendiente; sigue visible y editable en Movimientos.
MIN_REPETICIONES_PENDIENTE = 4


def _g(m, campo, defecto=None):
    if isinstance(m, dict):
        return m.get(campo, defecto)
    return getattr(m, campo, defecto)


def huella_de(descripcion: str) -> str:
    """Huella del comercio; si no se reconoce, la descripción en minúsculas (para agrupar igual)."""
    return clave_comercio(descripcion or "") or (descripcion or "").strip().lower()[:60]


def es_neutro(m) -> bool:
    """Traslados, pagos de tarjeta, ajustes de saldo, aportes a metas y lo que el sistema categoriza."""
    if _g(m, "fuente") in (FUENTE_TRANSFERENCIA, FUENTE_AJUSTE, FUENTE_APORTE_META) or _g(m, "tipo") == "transfer":
        return True
    cat = (_g(m, "categoria") or "").strip().lower()
    if cat in _SISTEMA_MIN:
        return True
    return tipo_base(m) == "transfer"


def motivo(m, huellas_silenciadas: frozenset | set = frozenset()) -> str | None:
    """Por qué espera categoría: 'marcada' | 'otros' | 'baja'; None si NO es pendiente.
    Sirve para un Movimiento o un dict con categoria, cat_confirmada, cat_origen, fuente, tipo, descripcion."""
    if es_neutro(m):
        return None
    origen = _g(m, "cat_origen")
    if origen == ORIGEN_MARCADA:
        return "marcada"  # lo pidió el usuario: gana sobre cualquier silencio
    if huellas_silenciadas and huella_de(_g(m, "descripcion", "")) in huellas_silenciadas:
        return None
    if origen == ORIGEN_DEJADA:
        return None
    categoria = (_g(m, "categoria") or "").strip().lower()
    if categoria in CATEGORIAS_SIN_DEFINIR:
        return "otros"
    if _g(m, "cat_confirmada", True) is False:
        if origen in ORIGENES_CONFIANZA_ALTA:
            return None
        return "baja"
    return None


# --- silencios -------------------------------------------------------------------------

def silencios(db: Session, usuario_id: str, tipos=SILENCIOS_QUE_OCULTAN) -> set[str]:
    filas = (
        db.query(ComercioSilenciado.huella)
        .filter(ComercioSilenciado.usuario_id == usuario_id, ComercioSilenciado.tipo.in_(tipos))
        .all()
    )
    return {h for (h,) in filas}


def silenciar(db: Session, usuario_id: str, huellas, tipo: str) -> int:
    """Crea los silencios que falten (idempotente). Sin commit. Devuelve cuántos nuevos."""
    if tipo not in TIPOS_SILENCIO:
        raise ValueError("tipo de silencio inválido")
    ya = silencios(db, usuario_id, (tipo,))
    nuevos = 0
    for h in {x for x in huellas if x}:
        if h not in ya:
            db.add(ComercioSilenciado(usuario_id=usuario_id, huella=h, tipo=tipo))
            nuevos += 1
    return nuevos


def quitar_silencios(db: Session, usuario_id: str, huellas, tipos=TIPOS_SILENCIO) -> int:
    hs = [h for h in huellas if h]
    if not hs:
        return 0
    return (
        db.query(ComercioSilenciado)
        .filter(ComercioSilenciado.usuario_id == usuario_id, ComercioSilenciado.huella.in_(hs),
                ComercioSilenciado.tipo.in_(tipos))
        .delete(synchronize_session=False)
    )


# --- consultas --------------------------------------------------------------------------

def _candidatos(db: Session, ids_cuentas):
    """Filtro grueso en SQL; la decisión fina la toma motivo()."""
    cat = func.lower(func.coalesce(Movimiento.categoria, ""))
    return db.query(Movimiento).filter(
        Movimiento.cuenta_id.in_(ids_cuentas),
        Movimiento.tipo != "transfer",
        or_(Movimiento.fuente.is_(None), Movimiento.fuente.notin_([FUENTE_TRANSFERENCIA, FUENTE_AJUSTE, FUENTE_APORTE_META])),
        or_(cat.in_(list(CATEGORIAS_SIN_DEFINIR)), Movimiento.cat_confirmada.is_(False),
            Movimiento.cat_origen == ORIGEN_MARCADA),
    )


def seleccionar(items, huellas_silenciadas=frozenset()) -> list[tuple]:
    """[(item, motivo)] aplicando la regla única: motivo() no vacío Y (marcada por el cliente, o su
    comercio/huella se repite >= MIN_REPETICIONES_PENDIENTE veces entre lo que espera categoría).
    Sirve para Movimiento o dict. Es lo ÚNICO que decide qué cuenta como pendiente."""
    con_motivo = []
    por_huella: dict[str, int] = defaultdict(int)
    for m in items:
        mot = motivo(m, huellas_silenciadas)
        if mot:
            con_motivo.append((m, mot))
            por_huella[huella_de(_g(m, "descripcion", ""))] += 1
    return [
        (m, mot) for m, mot in con_motivo
        if mot == "marcada" or por_huella[huella_de(_g(m, "descripcion", ""))] >= MIN_REPETICIONES_PENDIENTE
    ]


def pendientes(db: Session, usuario_id: str, ids_cuentas) -> list[tuple[Movimiento, str]]:
    """[(movimiento, motivo)] de lo que espera categoría, del más reciente al más antiguo."""
    if not ids_cuentas:
        return []
    sil = silencios(db, usuario_id)
    return seleccionar(_candidatos(db, ids_cuentas).order_by(Movimiento.fecha.desc()).all(), sil)


def ids_pendientes(db: Session, usuario_id: str, ids_cuentas) -> list[str]:
    return [m.id for m, _ in pendientes(db, usuario_id, ids_cuentas)]


def conteo(db: Session, usuario_id: str, ids_cuentas) -> dict:
    """El número que ven Inicio, Movimientos y los consejos (todos llaman a esto)."""
    por = defaultdict(int)
    for _, mot in pendientes(db, usuario_id, ids_cuentas):
        por[mot] += 1
    total = sum(por.values())
    return {"total": total, "otros": por["otros"], "baja": por["baja"], "marcadas": por["marcada"],
            "silenciados": len(silencios(db, usuario_id))}


def grupos(lista: list[tuple[Movimiento, str]], limite_ids: int = 300) -> list[dict]:
    """Agrupa por comercio, ordenado por impacto: primero lo que más pesa, luego lo que más se repite."""
    mapa: dict[str, dict] = {}
    for m, mot in lista:
        h = huella_de(m.descripcion)
        g = mapa.setdefault(h, {
            "huella": h, "nombre": h or (m.descripcion or ""), "conteo": 0, "monto_total": 0.0,
            "ejemplo": m.descripcion, "movimiento_id": m.id, "categorias": defaultdict(int),
            "motivos": set(), "movimiento_ids": [], "ultima_fecha": m.fecha,
        })
        g["conteo"] += 1
        g["monto_total"] += abs(m.monto or 0)
        g["categorias"][m.categoria or "Otros"] += 1
        g["motivos"].add(mot)
        if len(g["movimiento_ids"]) < limite_ids:
            g["movimiento_ids"].append(m.id)
    salida = []
    for g in mapa.values():
        cats = g.pop("categorias")
        g["categoria_actual"] = max(cats, key=cats.get) if cats else "Otros"
        g["monto_total"] = round(g["monto_total"], 2)
        g["motivos"] = sorted(g["motivos"], key=MOTIVOS.index)
        g["peligrosa"] = es_huella_peligrosa(g["huella"])
        g["ultima_fecha"] = g["ultima_fecha"].isoformat() if g["ultima_fecha"] else None
        salida.append(g)
    salida.sort(key=lambda g: (-g["monto_total"], -g["conteo"], g["huella"]))
    return salida


def es_relevante(g: dict, total_monto: float) -> bool:
    """Todo grupo pendiente ya cumplió la regla (>= 4 repeticiones o marcado por el cliente)."""
    return g["conteo"] >= MIN_REPETICIONES_PENDIENTE or "marcada" in g.get("motivos", ())


def resumen(db: Session, usuario_id: str, ids_cuentas, limite: int = 10, todos: bool = False) -> dict:
    lista = pendientes(db, usuario_id, ids_cuentas)
    gs = grupos(lista)
    total_monto = sum(g["monto_total"] for g in gs)
    for g in gs:
        g["relevante"] = es_relevante(g, total_monto)
    # «Lo que más pesa» = los relevantes primero (ya vienen por impacto); si no hay, los de mayor monto.
    relevantes = [g for g in gs if g["relevante"]]
    por_mot = defaultdict(int)
    for _, mot in lista:
        por_mot[mot] += 1
    visibles = gs if todos else gs[: max(1, min(limite, 50))]
    cubierto = sum(g["monto_total"] for g in relevantes[:limite])
    return {
        "conteo": {"total": len(lista), "otros": por_mot["otros"], "baja": por_mot["baja"],
                   "marcadas": por_mot["marcada"], "silenciados": len(silencios(db, usuario_id))},
        "total_grupos": len(gs),
        "relevantes": len(relevantes),
        "monto_total": round(total_monto, 2),
        "peso_relevantes": round(100 * cubierto / total_monto) if total_monto else 0,
        "grupos": visibles,
        "hay_mas": len(gs) > len(visibles),
    }


def anotar(db: Session, usuario_id: str, movs, ids_cuentas=None) -> None:
    """Pone `por_categorizar` (bool) en cada movimiento de una lista, para que la PWA no repita la regla.
    Con ids_cuentas usa el universo completo (la repetición se cuenta sobre todos sus movimientos)."""
    if ids_cuentas:
        ids = {m.id for m, _ in pendientes(db, usuario_id, ids_cuentas)}
    else:
        ids = {m.id for m, _ in seleccionar(movs, silencios(db, usuario_id))}
    for m in movs:
        m.por_categorizar = m.id in ids


def filtro_ids(db: Session, usuario_id: str, ids_cuentas):
    """Condición SQL «es pendiente» para listar con paginación (usa los ids ya decididos)."""
    return Movimiento.id.in_(ids_pendientes(db, usuario_id, ids_cuentas) or ["-"])


__all__ = ["motivo", "pendientes", "conteo", "resumen", "huella_de", "silenciar", "quitar_silencios",
           "seleccionar", "MIN_REPETICIONES_PENDIENTE", "ORIGEN_DEJADA", "ORIGEN_MARCADA"]
