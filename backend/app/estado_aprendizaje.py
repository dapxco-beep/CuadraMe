"""«Estamos aprendiendo el formato de tu banco»: un estado claro y NO accionable para extractos de un formato sin lector verificado.

Antes la app le pedía a la persona «Mándame el extracto para aprender su formato». Eso es trabajo nuestro, no suyo: aquí se
da un estado estructurado (`estado_aprendizaje: 'aprendiendo'` + `texto_aprendizaje`) para que la pantalla diga que no hay nada
que hacer. Es solo una etiqueta sobre datos que ya existen: no cambia ningún dato ni decide nada.

Un extracto está «aprendiendo» cuando:
  · no se pudo leer porque el formato no se reconoce (`motivo_error == 'formato_no_reconocido'`), o
  · su lector midió que lo leído NO suma lo que dice el resumen del banco (`lectura_completa is False`).
Los demás casos (clave del PDF, PDF escaneado, error pasajero...) siguen con su propio texto: ahí SÍ hay algo que hacer."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import HistorialExtracto

APRENDIENDO = "aprendiendo"
TEXTO = "Estamos aprendiendo el formato de tu banco; no tienes que hacer nada."
MOTIVO_FORMATO = "formato_no_reconocido"


def esta_aprendiendo(motivo_error: str | None = None, lectura_completa: bool | None = None) -> bool:
    return motivo_error == MOTIVO_FORMATO or lectura_completa is False


def campos(motivo_error: str | None = None, lectura_completa: bool | None = None) -> dict:
    """Campos para añadir a cualquier respuesta: `{estado_aprendizaje, texto_aprendizaje}` (ambos None si no aplica)."""
    if esta_aprendiendo(motivo_error, lectura_completa):
        return {"estado_aprendizaje": APRENDIENDO, "texto_aprendizaje": TEXTO}
    return {"estado_aprendizaje": None, "texto_aprendizaje": None}


def de_historial(h: HistorialExtracto | None) -> dict:
    return campos(h.motivo_error, h.lectura_completa) if h is not None else campos()


def resumen_usuario(db: Session, usuario_id: str) -> dict | None:
    """`{estado_aprendizaje, texto_aprendizaje, cantidad, historial_ids}` de los extractos de la persona que se están aprendiendo,
    o None si no hay ninguno. Solo lee. (Las lecturas viejas de un mismo corte que ya se reemplazaron por una nueva no cuentan.)"""
    from app import fechas_extracto

    ids = []
    for h in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == usuario_id).all():
        if fechas_extracto.es_duplicado(h) or not esta_aprendiendo(h.motivo_error, h.lectura_completa):
            continue
        ids.append(h.id)
    if not ids:
        return None
    return {**campos(MOTIVO_FORMATO), "cantidad": len(ids), "historial_ids": ids[:20]}
