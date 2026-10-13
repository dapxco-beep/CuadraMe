"""Avisos de actividad: panel «Actividad reciente» y preferencias del administrador.

Todo es solo para ADMIN_EMAIL (cualquier otra persona recibe 404, como una ruta que no existe).
El correo completo de cada persona solo sale en estas respuestas; los avisos (push/correo) llevan
el correo enmascarado. La lógica de registro y envío vive en app/avisos.py.
"""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import avisos
from app.auth import UsuarioActual, cron_autorizado
from app.config import settings
from app.database import get_db
from app.models_avisos import EventoActividad
from app.routers.comentarios import exigir_admin
from app.utiles import ahora_co

router = APIRouter(prefix="/avisos", tags=["avisos"])

COLOMBIA_UTC = timedelta(hours=5)  # Colombia no tiene horario de verano: UTC-5 todo el año
MAX_SILENCIO_HORAS = 24 * 7


def _inicio_hoy_utc() -> datetime:
    return ahora_co().replace(hour=0, minute=0, second=0, microsecond=0) + COLOMBIA_UTC


def _a_dict(e: EventoActividad) -> dict:
    try:
        meta = json.loads(e.meta) if e.meta else {}
    except ValueError:
        meta = {}
    return {
        "id": e.id, "tipo": e.tipo, "etiqueta": avisos.TIPOS.get(e.tipo, (e.tipo,))[0], "resumen": e.resumen,
        "email": e.email, "meta": meta, "creado_en": e.creado_en.isoformat(), "aviso": e.aviso_estado,
    }


def _contadores(db: Session) -> dict:
    hoy = _inicio_hoy_utc()
    hace7 = hoy - timedelta(days=6)
    por_tipo = {t: {"hoy": 0, "dias7": 0} for t in avisos.TIPOS}
    for tipo, creado in db.query(EventoActividad.tipo, EventoActividad.creado_en).filter(EventoActividad.creado_en >= hace7):
        c = por_tipo.setdefault(tipo, {"hoy": 0, "dias7": 0})
        c["dias7"] += 1
        if creado >= hoy:
            c["hoy"] += 1
    return {
        "total_hoy": sum(c["hoy"] for c in por_tipo.values()),
        "total_7d": sum(c["dias7"] for c in por_tipo.values()),
        "por_tipo": por_tipo,
    }


def _registros_por_dia(db: Session, dias: int = 30) -> list[dict]:
    inicio_co = ahora_co().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=dias - 1)
    filas = db.query(EventoActividad.creado_en).filter(
        EventoActividad.tipo == "nuevo_registro", EventoActividad.creado_en >= inicio_co + COLOMBIA_UTC).all()
    por_dia: dict[str, int] = {}
    for (creado,) in filas:
        k = (creado - COLOMBIA_UTC).strftime("%Y-%m-%d")
        por_dia[k] = por_dia.get(k, 0) + 1
    serie = []
    for i in range(dias):
        k = (inicio_co + timedelta(days=i)).strftime("%Y-%m-%d")
        serie.append({"dia": k, "registros": por_dia.get(k, 0)})
    return serie


@router.get("/actividad")
def actividad(
    tipo: str | None = None,
    pagina: int = 1,
    por_pagina: int = 30,
    db: Session = Depends(get_db),
    _admin: UsuarioActual = Depends(exigir_admin),
):
    pagina = max(1, pagina)
    por_pagina = min(max(1, por_pagina), 100)
    q = db.query(EventoActividad)
    if tipo in avisos.TIPOS:
        q = q.filter(EventoActividad.tipo == tipo)
    total = q.count()
    filas = q.order_by(EventoActividad.creado_en.desc()).offset((pagina - 1) * por_pagina).limit(por_pagina).all()
    return {
        "items": [_a_dict(e) for e in filas], "total": total, "pagina": pagina, "por_pagina": por_pagina,
        "contadores": _contadores(db),
        "registros_por_dia": _registros_por_dia(db),
        "tipos": [{"id": t, "etiqueta": v[0]} for t, v in avisos.TIPOS.items()],
    }


class TipoPref(BaseModel):
    push: bool = False
    correo: bool = False


class PreferenciasIn(BaseModel):
    tipos: dict[str, TipoPref] | None = None
    silenciar_horas: int | None = Field(default=None, ge=0, le=MAX_SILENCIO_HORAS)  # 0 = quitar el silencio
    resumen_diario: bool | None = None


def _estado_preferencias(db: Session, fila) -> dict:
    ahora = datetime.utcnow()
    silencio = fila.silenciado_hasta if fila is not None and fila.silenciado_hasta and fila.silenciado_hasta > ahora else None
    return {
        "tipos": [
            {"id": t, "etiqueta": v[0], **avisos.leer_preferencias(fila)[t]} for t, v in avisos.TIPOS.items()
        ],
        "silenciado_hasta": silencio.isoformat() if silencio else None,
        "resumen_diario": bool(fila.resumen_diario) if fila is not None else False,
        "max_por_hora": avisos.MAX_AVISOS_POR_HORA,
        "canales": {
            "push_activo": bool(fila is not None and avisos.tiene_push(db, fila.usuario_id)),
            "correo_configurado": bool(avisos._destino() and settings.resend_api_key),
            "correo_error": fila.correo_error if fila is not None else None,
        },
    }


@router.get("/preferencias")
def preferencias(db: Session = Depends(get_db), admin: UsuarioActual = Depends(exigir_admin)):
    fila = avisos.asegurar_fila_admin(db, admin.id)
    return _estado_preferencias(db, fila)


@router.put("/preferencias")
def guardar_preferencias(
    datos: PreferenciasIn,
    db: Session = Depends(get_db),
    admin: UsuarioActual = Depends(exigir_admin),
):
    fila = avisos.asegurar_fila_admin(db, admin.id)
    if datos.tipos is not None:
        actuales = avisos.leer_preferencias(fila)
        for t, p in datos.tipos.items():
            if t in avisos.TIPOS:
                actuales[t] = {"push": p.push, "correo": p.correo}
        fila.tipos = json.dumps(actuales)
    if datos.silenciar_horas is not None:
        fila.silenciado_hasta = (datetime.utcnow() + timedelta(hours=datos.silenciar_horas)) if datos.silenciar_horas else None
    if datos.resumen_diario is not None:
        fila.resumen_diario = datos.resumen_diario
    db.commit()
    return _estado_preferencias(db, fila)


@router.post("/probar")
def probar(db: Session = Depends(get_db), admin: UsuarioActual = Depends(exigir_admin)):
    """Manda un aviso de prueba por los dos canales para comprobar que llegan."""
    fila = avisos.asegurar_fila_admin(db, admin.id)
    r = avisos.notificar(db, "Aviso de prueba", "Así llegarán los avisos de CuadraMe. Sin datos de nadie.",
                         push=True, correo=True, fila=fila)
    db.refresh(fila)
    return {"ok": True, "push": r["push"], "correo": r["correo"], "correo_error": fila.correo_error}


@router.get("/retencion")
def retencion_vigente(db: Session = Depends(get_db), admin: UsuarioActual = Depends(exigir_admin)):
    """Solo administración (404 al resto): plazos de retención de datos de Gmail vigentes y, como
    simulación, cuántos registros caerían bajo cada plazo si estuviera activo. No devuelve contenido."""
    from app import retencion

    return retencion.simular(db)


@router.post("/cron/resumen-diario")
def cron_resumen_diario(x_cron_secret: str = Header(default=""), db: Session = Depends(get_db)):
    """Una vez al día (p. ej. 20:00 Bogotá). Junta en un solo aviso los eventos que quedaron en espera
    por el «resumen diario» o por el tope de avisos por hora. Idempotente por día."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    r = avisos.enviar_resumen(db)
    return {**r, "procesados": 1, "fallidos": 0 if r["ok"] else 1}
