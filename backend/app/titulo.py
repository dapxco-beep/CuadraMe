"""Nombre propio de un movimiento («Recibo de la luz») sin perder el texto original del banco.

Regla de oro: `Movimiento.descripcion` NO se toca. El anti-duplicados (duplicados.py), la conciliación
con extractos, las reglas por comercio (huella_de / reglas_categoria) y el modelo siguen leyendo la
descripción original. `titulo` es solo lo que la persona ve primero (`titulo or descripcion`).

«Recordar este nombre para este comercio» guarda una ReglaTitulo (huella -> título) y se aplica a lo que
llegue después. Solo se guarda cuando la persona lo pide: nunca se infiere un nombre por su cuenta.
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.clave_comercio import es_huella_peligrosa
from app.models import ReglaTitulo
from app.pendientes import MIN_REPETICIONES_PENDIENTE, huella_de

MAX_TITULO = 80
MIN_REPETICIONES = MIN_REPETICIONES_PENDIENTE  # desde cuántas veces se sugiere recordar el nombre

_ETIQUETAS = re.compile(r"<[^>]*>")
_ESPACIOS = re.compile(r"\s+")


def limpiar(titulo: str | None) -> str | None:
    """Sin HTML, espacios sobrantes ni más de 80 caracteres. Vacío -> None (= sin título)."""
    if not titulo:
        return None
    t = _ETIQUETAS.sub("", str(titulo)).replace("<", "").replace(">", "")
    t = _ESPACIOS.sub(" ", t).strip()[:MAX_TITULO].strip()
    return t or None


def recordado(db: Session, usuario_id: str, descripcion: str) -> str | None:
    """El nombre que la persona pidió recordar para este comercio, si hay."""
    huella = huella_de(descripcion)
    if not huella:
        return None
    r = (db.query(ReglaTitulo)
         .filter(ReglaTitulo.usuario_id == usuario_id, ReglaTitulo.huella == huella).first())
    return r.titulo if r else None


def titulo_para_nuevo(db: Session, usuario_id: str, descripcion: str, elegido: str | None = None) -> str | None:
    """Título de un movimiento que se crea: el que la persona eligió ahora o, si no, el que pidió recordar."""
    return limpiar(elegido) or recordado(db, usuario_id, descripcion)


def guardar_regla(db: Session, usuario_id: str, descripcion: str, titulo: str | None) -> dict:
    """Recuerda (o actualiza) el nombre de este comercio. Sin commit. Un comercio demasiado genérico
    («pago», «compra») no se guarda: renombraría cosas que no tienen que ver."""
    titulo = limpiar(titulo)
    huella = huella_de(descripcion)
    if not titulo or not huella:
        return {"guardada": False, "motivo": "sin nombre"}
    peligro = es_huella_peligrosa(huella)
    if peligro:
        return {"guardada": False, "motivo": peligro}
    r = (db.query(ReglaTitulo)
         .filter(ReglaTitulo.usuario_id == usuario_id, ReglaTitulo.huella == huella).first())
    if r:
        r.titulo = titulo
    else:
        db.add(ReglaTitulo(usuario_id=usuario_id, huella=huella, titulo=titulo))
    return {"guardada": True, "motivo": None}
