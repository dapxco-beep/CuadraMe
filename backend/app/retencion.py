"""Retención de datos de Gmail: MINIMIZACIÓN con plazos configurables (todos APAGADOS por defecto).

Qué hace (cuando el plazo es > 0):
  * Correos `ignorado`/`descartado` (no son movimientos) pasados RETENCION_CORREOS_IGNORADOS_DIAS:
    se BORRA su contenido (remitente, asunto, snippet, comercio).
  * Correos ya convertidos en movimiento (`aprobado`/`ya_registrado`) pasados
    RETENCION_CORREOS_PROCESADOS_DIAS: igual, se borra el contenido.
  * Lo mismo para `extractos_correo` (remitente y asunto): descartado/ignorado con el plazo de ignorados,
    procesado/ya_conciliado con el de procesados.
  * `eventos_actividad` más viejos que RETENCION_EVENTOS_DIAS se eliminan (salvo `nuevo_registro:*`,
    que es la marca que evita registrar dos veces a la misma persona).

Qué NO hace, a propósito: no elimina la FILA de los correos/extractos. Se conserva lo mínimo para la
regla anti-duplicados (app/duplicados.py): id del mensaje de Gmail, estado, fecha, monto, movimiento_id
(y el nombre de archivo del extracto, parte de su llave única). Así el correo que ya se leyó no se
vuelve a leer ni «resucita» en la bandeja, y un periodo `ya_conciliado` sigue contando como conciliado.
Los correos pendientes o con error nunca se tocan. Es idempotente: una fila ya minimizada no vuelve
a seleccionarse. Nunca se registra contenido, solo conteos.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CorreoGasto, ExtractoCorreo
from app.models_avisos import EventoActividad

logger = logging.getLogger("cuadrame.retencion")

LOTE = 500
PRESUPUESTO_SEGUNDOS = 40
ESTADOS_CORREO_IGNORADOS = ("ignorado", "descartado")
ESTADOS_CORREO_PROCESADOS = ("aprobado", "ya_registrado")
ESTADOS_EXTRACTO_IGNORADOS = ("ignorado", "descartado")
ESTADOS_EXTRACTO_PROCESADOS = ("procesado", "ya_conciliado")

_reloj = time.monotonic  # sustituible en pruebas


def configuracion() -> dict:
    return {
        "correos_ignorados_dias": max(0, int(settings.retencion_correos_ignorados_dias or 0)),
        "correos_procesados_dias": max(0, int(settings.retencion_correos_procesados_dias or 0)),
        "eventos_dias": max(0, int(settings.retencion_eventos_dias or 0)),
    }


def _con_contenido_correo():
    vacio = lambda c: func.coalesce(c, "") != ""  # noqa: E731
    return or_(vacio(CorreoGasto.remitente), vacio(CorreoGasto.asunto), vacio(CorreoGasto.snippet),
               vacio(CorreoGasto.comercio))


def _con_contenido_extracto():
    return or_(func.coalesce(ExtractoCorreo.remitente, "") != "", func.coalesce(ExtractoCorreo.asunto, "") != "")


def _filtros(dias: dict, ahora: datetime) -> list[tuple[str, object, object, str]]:
    """(clave, modelo, condición, acción) por cada plazo activo. acción: 'minimizar' | 'borrar'."""
    f: list = []
    d = dias["correos_ignorados_dias"]
    if d > 0:
        corte = ahora - timedelta(days=d)
        f.append(("correos_ignorados", CorreoGasto, and_(
            CorreoGasto.estado.in_(ESTADOS_CORREO_IGNORADOS), CorreoGasto.creado_en < corte,
            _con_contenido_correo()), "minimizar"))
        f.append(("extractos_ignorados", ExtractoCorreo, and_(
            ExtractoCorreo.estado.in_(ESTADOS_EXTRACTO_IGNORADOS), ExtractoCorreo.creado_en < corte,
            _con_contenido_extracto()), "minimizar"))
    d = dias["correos_procesados_dias"]
    if d > 0:
        corte = ahora - timedelta(days=d)
        f.append(("correos_procesados", CorreoGasto, and_(
            CorreoGasto.estado.in_(ESTADOS_CORREO_PROCESADOS), CorreoGasto.creado_en < corte,
            _con_contenido_correo()), "minimizar"))
        f.append(("extractos_procesados", ExtractoCorreo, and_(
            ExtractoCorreo.estado.in_(ESTADOS_EXTRACTO_PROCESADOS), ExtractoCorreo.creado_en < corte,
            _con_contenido_extracto()), "minimizar"))
    d = dias["eventos_dias"]
    if d > 0:
        corte = ahora - timedelta(days=d)
        f.append(("eventos", EventoActividad, and_(
            EventoActividad.creado_en < corte,
            or_(EventoActividad.clave_unica.is_(None), ~EventoActividad.clave_unica.like("nuevo_registro:%"))),
            "borrar"))
    return f


_CLAVES = ("correos_ignorados", "extractos_ignorados", "correos_procesados", "extractos_procesados", "eventos")


def simular(db: Session, ahora: datetime | None = None) -> dict:
    """Cuántos registros caerían bajo cada plazo ACTIVO (sin cambiar nada)."""
    ahora = ahora or datetime.utcnow()
    cfg = configuracion()
    conteos = {k: 0 for k in _CLAVES}
    for clave, modelo, cond, _ in _filtros(cfg, ahora):
        conteos[clave] = db.query(func.count(modelo.id)).filter(cond).scalar() or 0
    return {"configuracion": cfg, "activo": any(v > 0 for v in cfg.values()), "alcanzaria": conteos}


def _poner_vacio(modelo) -> dict:
    if modelo is CorreoGasto:
        return {"remitente": "", "asunto": "", "snippet": "", "comercio": ""}
    return {"remitente": "", "asunto": ""}


def purgar(db: Session, ahora: datetime | None = None, presupuesto: float = PRESUPUESTO_SEGUNDOS,
           lote: int = LOTE) -> dict:
    """Aplica los plazos activos por lotes con tope de tiempo. Un fallo en una categoría no detiene
    las demás. Devuelve conteos (nunca contenido). `completo` False = quedó trabajo para la próxima."""
    ahora = ahora or datetime.utcnow()
    cfg = configuracion()
    res = {k: 0 for k in _CLAVES}
    res["fallidos"] = 0
    res["completo"] = True
    res["configuracion"] = cfg
    inicio = _reloj()
    for clave, modelo, cond, accion in _filtros(cfg, ahora):
        try:
            while True:
                if _reloj() - inicio >= presupuesto:
                    res["completo"] = False
                    break
                ids = [r[0] for r in db.query(modelo.id).filter(cond).limit(lote).all()]
                if not ids:
                    break
                q = db.query(modelo).filter(modelo.id.in_(ids))
                if accion == "borrar":
                    q.delete(synchronize_session=False)
                else:
                    q.update(_poner_vacio(modelo), synchronize_session=False)
                db.commit()
                res[clave] += len(ids)
        except Exception:  # noqa: BLE001 - un fallo no detiene las demás categorías
            db.rollback()
            res["fallidos"] += 1
            res["completo"] = False
            logger.exception("Retención: falló la categoría %s", clave)
    logger.info("Retención: %s", {k: v for k, v in res.items() if k in _CLAVES or k in ("fallidos", "completo")})
    return res
