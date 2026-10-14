"""Calidad de la categorización automática de TODA la plataforma, para el dueño (solo conteos).

Sale de dos columnas que la app ya guarda en cada movimiento, sin leer su contenido:
  - cat_origen: por qué la app puso la categoría ('regla' | 'comercio' | 'similar' | 'sugerida'),
    o 'corregida:<categoría que sugirió>' cuando la persona la cambió.
  - cat_confirmada: si la persona ya la revisó.

  acertada  = la app sugirió y la persona la CONFIRMÓ sin cambiarla.
  corregida = la app sugirió y la persona la CAMBIÓ por otra.
  pendiente = la app sugirió y nadie la ha revisado (no cuenta para la exactitud).

No devuelve descripciones, montos, fechas exactas, nombres ni ids. Las categorías que cada persona
inventó ('Juliana', 'Lote'...) podrían ser datos personales: se agrupan como «Personalizadas».
"""
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.costos_financieros import NOMBRES_SISTEMA
from app.diccionario_categorias import SECCIONES
from app.models import Movimiento

ORIGENES_SUGERIDOS = ("regla", "comercio", "similar", "sugerida")
PREFIJO_CORREGIDA = "corregida:"
PERSONALIZADAS = "Personalizadas"
_BASE = {"Comida", "Transporte", "Ocio", "Hogar", "Salud", "Transferencias", "Ingresos", "Otros"}
CATEGORIAS_PUBLICAS = _BASE | set(SECCIONES) | set(NOMBRES_SISTEMA)


def origen_tras_edicion(origen_previo: str | None, categoria_previa: str | None, categoria_nueva: str | None) -> str | None:
    """Valor de cat_origen cuando la PERSONA elige la categoría de un movimiento.
    Si la app había sugerido otra, queda el rastro 'corregida:<la sugerida>' (es lo que permite medir
    la calidad); si aceptó la misma, se conserva el origen (cuenta como acertada); si nunca hubo
    sugerencia, queda None (la escribió ella)."""
    previo = origen_previo or ""
    if previo.startswith(PREFIJO_CORREGIDA):
        return previo
    if previo in ORIGENES_SUGERIDOS:
        if (categoria_previa or "").strip() == (categoria_nueva or "").strip():
            return previo
        return f"{PREFIJO_CORREGIDA}{(categoria_previa or '').strip()}"[:80]
    return None


def _publica(categoria: str | None) -> str:
    c = (categoria or "").strip()
    return c if c in CATEGORIAS_PUBLICAS else PERSONALIZADAS


def _tasa(acertadas: int, corregidas: int) -> float | None:
    total = acertadas + corregidas
    return round(acertadas / total, 3) if total else None


def panel_calidad(db: Session) -> dict:
    """Conteos agregados de toda la plataforma. Sin contenido de ningún movimiento."""
    por_cat: dict[str, dict] = defaultdict(lambda: {"acertadas": 0, "corregidas": 0, "pendientes": 0})
    por_origen: dict[str, dict] = defaultdict(lambda: {"acertadas": 0, "pendientes": 0})
    total = {"acertadas": 0, "corregidas": 0, "pendientes": 0}

    # acertadas y pendientes: agrupadas en la base, sin traer filas
    filas = (
        db.query(Movimiento.cat_origen, Movimiento.cat_confirmada, Movimiento.categoria, func.count(Movimiento.id))
        .filter(Movimiento.cat_origen.in_(ORIGENES_SUGERIDOS))
        .group_by(Movimiento.cat_origen, Movimiento.cat_confirmada, Movimiento.categoria)
        .all()
    )
    for origen, confirmada, categoria, n in filas:
        clave = "pendientes" if confirmada is False else "acertadas"
        por_cat[_publica(categoria)][clave] += n
        por_origen[origen][clave] += n
        total[clave] += n
    # corregidas: el nombre de la categoría que SUGIRIÓ la app va tras el prefijo
    corregidas = (
        db.query(Movimiento.cat_origen, func.count(Movimiento.id))
        .filter(Movimiento.cat_origen.like(f"{PREFIJO_CORREGIDA}%"))
        .group_by(Movimiento.cat_origen)
        .all()
    )
    for origen, n in corregidas:
        por_cat[_publica(origen[len(PREFIJO_CORREGIDA):])]["corregidas"] += n
        total["corregidas"] += n

    categorias = [
        {"categoria": c, **d, "exactitud": _tasa(d["acertadas"], d["corregidas"])}
        for c, d in sorted(por_cat.items(), key=lambda kv: -(kv[1]["acertadas"] + kv[1]["corregidas"] + kv[1]["pendientes"]))
    ]
    return {
        "acertadas": total["acertadas"], "corregidas": total["corregidas"], "pendientes": total["pendientes"],
        "exactitud": _tasa(total["acertadas"], total["corregidas"]),
        "por_categoria": categorias,
        "por_origen": [{"origen": o, **d} for o, d in sorted(por_origen.items())],
        "nota": "Exactitud = acertadas / (acertadas + corregidas); las pendientes aún no cuentan.",
    }
