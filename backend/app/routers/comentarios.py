"""Buzón de opinión («Tu opinión cuenta») y su panel para la administración.

Personas: POST /comentarios (enviar) y GET /comentarios/mios (ver el estado de los suyos).
Administración (ADMIN_EMAIL; cualquier otra persona recibe 404, como una ruta que no existe):
lista con filtros y conteos, PATCH para cambiar estado / nota interna / respuesta, marcar
varios como vistos y exportar CSV.
"""
import csv
import io
import logging
import re
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app import avisos
from app.auth import UsuarioActual, get_current_user
from app.crecimiento import SISTEMA, es_admin
from app.crons import reclamar_marca
from app.database import get_db
from app.limites import verificar_limite
from app.limites_diarios import consumir_cupo_diario
from app.models_comentarios import ESTADOS, TIPOS, Comentario
from app.utiles import ahora_co, celda_segura

logger = logging.getLogger("app.comentarios")
router = APIRouter(prefix="/comentarios", tags=["comentarios"])

MAX_MENSAJE = 2000
MAX_NOTA = 2000
MAX_RESPUESTA = 1000
POR_HORA = 10
UMBRAL_AVISO_NUEVOS = 5
CLAVE_AVISO = "comentarios:aviso"

# Cómo ve su comentario quien lo escribió (palabras llanas, sin jerga interna).
ESTADO_PUBLICO = {
    "nuevo": "Recibido",
    "visto": "Recibido",
    "en_curso": "Lo estamos revisando",
    "resuelto": "Ya lo resolvimos",
    "descartado": "Gracias, lo tendremos en cuenta",
}

_ETIQUETAS = re.compile(r"<[^>]*>")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def limpiar_texto(valor: str | None, maximo: int | None = None) -> str:
    """Quita etiquetas HTML y caracteres de control, y recorta espacios. Conserva saltos de línea."""
    t = _CONTROL.sub("", str(valor or ""))
    t = _ETIQUETAS.sub("", t).replace("<", "").replace(">", "").strip()
    return t[:maximo].strip() if maximo else t


def _pantalla(valor: str | None) -> str | None:
    """Solo la ruta (sin query ni parámetros, que podrían traer datos): '/movimientos'."""
    t = limpiar_texto(valor, 300).split("?")[0].split("#")[0]
    t = re.sub(r"[^\w/\-.]", "", t)[:120]
    return t or None


def exigir_admin(usuario: UsuarioActual = Depends(get_current_user)) -> UsuarioActual:
    if not es_admin(usuario.email):
        raise HTTPException(status_code=404, detail="No encontrado")
    return usuario


class NuevoComentario(BaseModel):
    tipo: str = "sugerencia"
    mensaje: str
    pantalla: str | None = None
    version_app: str | None = None
    dispositivo: str | None = None
    puede_contactar: bool = True


class CambioComentario(BaseModel):
    estado: str | None = None
    nota_admin: str | None = None
    respuesta_publica: str | None = None


class MarcarVistos(BaseModel):
    ids: list[str]


def _aviso_admin(tipo: str, mensaje: str, pantalla: str | None) -> None:
    """Avisa a la administración por el mecanismo común de avisos (app/avisos.py): un «problema» es
    un evento `comentario_problema`; al juntarse 5 comentarios nuevos, un `comentarios_pendientes`
    (máximo 1 por hora). El push/correo, el tope de ruido y el panel «Actividad reciente» los pone
    ese mecanismo: aquí ya no se envía ningún correo propio. Nunca lanza: avisar no rompe el envío.
    Sin texto del comentario en el aviso (puede traer datos personales): solo tipo y pantalla."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        if tipo == "problema":
            avisos.registrar_evento("comentario_problema", meta={"pantalla": pantalla or ""})
            return
        nuevos = db.query(func.count(Comentario.id)).filter(Comentario.estado == "nuevo").scalar() or 0
        if nuevos < UMBRAL_AVISO_NUEVOS:
            return
        hora = ahora_co().strftime("%Y-%m-%d %H")
        if reclamar_marca(db, SISTEMA, CLAVE_AVISO, hora):  # ya se avisó en esta hora: no repetir
            avisos.registrar_evento("comentarios_pendientes", meta={"nuevos": nuevos})
    except Exception:  # noqa: BLE001
        logger.warning("Comentarios: fallo preparando el aviso", exc_info=True)
    finally:
        db.close()


@router.post("")
def enviar(
    datos: NuevoComentario,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    tipo = limpiar_texto(datos.tipo).lower()
    if tipo not in TIPOS:
        raise HTTPException(status_code=400, detail="Elige qué tipo de comentario es: idea, problema, duda o algo que te gustó.")
    mensaje = limpiar_texto(datos.mensaje)
    if not mensaje:
        raise HTTPException(status_code=400, detail="Cuéntanos algo, aunque sea una frase corta.")
    if len(mensaje) > MAX_MENSAJE:
        raise HTTPException(status_code=400, detail=f"Tu mensaje es muy largo (máximo {MAX_MENSAJE} caracteres). Resúmelo un poco.")

    verificar_limite(f"comentario:{usuario.id}", POR_HORA, 3600,
                     "Ya nos escribiste varias veces seguidas, gracias. Puedes enviar otro en {espera}.")
    consumir_cupo_diario(db, usuario.id, "comentario")

    c = Comentario(
        usuario_id=usuario.id,
        email=limpiar_texto(usuario.email, 200) or None,
        tipo=tipo,
        mensaje=mensaje,
        pantalla=_pantalla(datos.pantalla),
        version_app=limpiar_texto(datos.version_app, 40) or None,
        dispositivo=limpiar_texto(datos.dispositivo, 80) or None,
        puede_contactar=bool(datos.puede_contactar),
    )
    try:
        db.add(c)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Comentarios: no se pudo guardar")
        raise HTTPException(status_code=503, detail="No pudimos guardar tu comentario en este momento. Intenta de nuevo en unos minutos.")
    tareas.add_task(_aviso_admin, tipo, mensaje, c.pantalla)
    return {"ok": True, "id": c.id}


@router.get("/mios")
def mios(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    filas = (
        db.query(Comentario).filter(Comentario.usuario_id == usuario.id)
        .order_by(Comentario.creado_en.desc()).limit(50).all()
    )
    return [
        {
            "id": c.id, "tipo": c.tipo, "mensaje": c.mensaje, "creado_en": c.creado_en.isoformat(),
            "estado": ESTADO_PUBLICO.get(c.estado, "Recibido"), "respuesta": c.respuesta_publica or None,
        }
        for c in filas
    ]


def _filtrar(q, tipo: str | None, estado: str | None, buscar: str | None):
    if tipo in TIPOS:
        q = q.filter(Comentario.tipo == tipo)
    if estado in ESTADOS:
        q = q.filter(Comentario.estado == estado)
    termino = limpiar_texto(buscar, 80)
    if termino:
        like = "%" + termino.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        q = q.filter(or_(Comentario.mensaje.ilike(like, escape="\\"), Comentario.email.ilike(like, escape="\\"),
                         Comentario.pantalla.ilike(like, escape="\\"), Comentario.nota_admin.ilike(like, escape="\\")))
    return q


def _orden(q):
    """Primero lo nuevo, luego los problemas, luego lo más reciente."""
    return q.order_by(
        case((Comentario.estado == "nuevo", 0), else_=1),
        case((Comentario.tipo == "problema", 0), else_=1),
        Comentario.creado_en.desc(),
    )


def _a_dict(c: Comentario) -> dict:
    return {
        "id": c.id, "email": c.email, "tipo": c.tipo, "mensaje": c.mensaje, "pantalla": c.pantalla,
        "version_app": c.version_app, "dispositivo": c.dispositivo, "puede_contactar": bool(c.puede_contactar),
        "estado": c.estado, "nota_admin": c.nota_admin, "respuesta_publica": c.respuesta_publica,
        "creado_en": c.creado_en.isoformat(), "actualizado_en": c.actualizado_en.isoformat(),
    }


@router.get("")
def listar(
    tipo: str | None = None,
    estado: str | None = None,
    q: str | None = None,
    pagina: int = 1,
    por_pagina: int = 30,
    db: Session = Depends(get_db),
    _admin: UsuarioActual = Depends(exigir_admin),
):
    pagina = max(1, pagina)
    por_pagina = min(max(1, por_pagina), 100)
    base = _filtrar(db.query(Comentario), tipo, estado, q)
    total = base.count()
    filas = _orden(base).offset((pagina - 1) * por_pagina).limit(por_pagina).all()
    por_estado = {e: 0 for e in ESTADOS}
    por_estado.update(dict(db.query(Comentario.estado, func.count(Comentario.id)).group_by(Comentario.estado).all()))
    por_tipo = {t: 0 for t in TIPOS}
    por_tipo.update(dict(db.query(Comentario.tipo, func.count(Comentario.id)).group_by(Comentario.tipo).all()))
    return {
        "items": [_a_dict(c) for c in filas], "total": total, "pagina": pagina, "por_pagina": por_pagina,
        "por_estado": por_estado, "por_tipo": por_tipo,
    }


@router.get("/exportar.csv")
def exportar_csv(
    tipo: str | None = None,
    estado: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    _admin: UsuarioActual = Depends(exigir_admin),
):
    filas = _orden(_filtrar(db.query(Comentario), tipo, estado, q)).limit(10000).all()
    buffer = io.StringIO()
    w = csv.writer(buffer)
    w.writerow(["Fecha", "Tipo", "Estado", "Pantalla", "Versión", "Dispositivo", "Puede contactar", "Correo",
                "Mensaje", "Nota interna", "Respuesta pública"])
    for c in filas:
        w.writerow([
            c.creado_en.strftime("%Y-%m-%d %H:%M"), c.tipo, c.estado, celda_segura(c.pantalla or ""),
            celda_segura(c.version_app or ""), celda_segura(c.dispositivo or ""), "sí" if c.puede_contactar else "no",
            celda_segura(c.email or ""), celda_segura(c.mensaje), celda_segura(c.nota_admin or ""),
            celda_segura(c.respuesta_publica or ""),
        ])
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=comentarios_cuadrame.csv"},
    )


@router.post("/marcar-vistos")
def marcar_vistos(datos: MarcarVistos, db: Session = Depends(get_db), _admin: UsuarioActual = Depends(exigir_admin)):
    ids = [i for i in datos.ids[:200] if isinstance(i, str)]
    n = (
        db.query(Comentario).filter(Comentario.id.in_(ids or [""]), Comentario.estado == "nuevo")
        .update({Comentario.estado: "visto", Comentario.actualizado_en: datetime.utcnow()}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True, "actualizados": n}


@router.patch("/{comentario_id}")
def cambiar(
    comentario_id: str,
    datos: CambioComentario,
    db: Session = Depends(get_db),
    _admin: UsuarioActual = Depends(exigir_admin),
):
    c = db.query(Comentario).filter(Comentario.id == comentario_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="No encontrado")
    if datos.estado is not None:
        if datos.estado not in ESTADOS:
            raise HTTPException(status_code=400, detail="Estado no válido")
        c.estado = datos.estado
    if datos.nota_admin is not None:
        c.nota_admin = limpiar_texto(datos.nota_admin, MAX_NOTA) or None
    if datos.respuesta_publica is not None:
        c.respuesta_publica = limpiar_texto(datos.respuesta_publica, MAX_RESPUESTA) or None
    c.actualizado_en = datetime.utcnow()
    db.commit()
    return _a_dict(c)
