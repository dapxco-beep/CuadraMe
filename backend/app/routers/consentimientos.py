"""
Autorización de tratamiento de datos (Ley 1581 de 2012, Colombia).

Diseño auditable: la tabla `consentimientos` es de SOLO INSERCIÓN. Cada vez que el
usuario acepta o revoca una finalidad se agrega una fila nueva (con versión de los
textos, fecha UTC y hora Colombia, y la IP si está disponible); nunca se edita ni
se borra el histórico. El estado vigente de una finalidad es su fila más reciente.

Finalidades:
- tratamiento_basico (OBLIGATORIA): datos de la cuenta y los que el usuario escribe.
- lectura_correo (opcional): leer Gmail en solo lectura. Sin ella no se puede conectar.
- ia (opcional): procesar texto/fotos con proveedores de IA (asistente, foto de factura).
- notificaciones (opcional): avisos push y por correo.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.config import settings
from app.database import get_db
from app.models import Consentimiento
from app.utiles import ahora_co

router = APIRouter(prefix="/consentimientos", tags=["consentimientos"])

# Subir esta versión cuando cambien los textos legales: a todos los usuarios se les
# vuelve a pedir la autorización (ver `requiere_autorizacion`).
VERSION_TEXTOS = "1.1"

FINALIDADES = {
    "tratamiento_basico": {"obligatoria": True, "titulo": "Tratamiento básico de mis datos"},
    "lectura_correo": {"obligatoria": False, "titulo": "Leer mi correo (Gmail, solo lectura)"},
    "ia": {"obligatoria": False, "titulo": "Procesar mis datos con inteligencia artificial"},
    "notificaciones": {"obligatoria": False, "titulo": "Recibir notificaciones"},
}

MENSAJES_REQUERIDO = {
    "lectura_correo": "Antes de conectar Gmail necesitamos tu autorización específica para leer tus correos.",
    "ia": "Antes de usar la inteligencia artificial necesitamos tu autorización para procesar tus datos con ella.",
    "tratamiento_basico": "Necesitamos tu autorización de tratamiento de datos para continuar.",
}


class ItemConsentimiento(BaseModel):
    finalidad: str
    aceptado: bool


class RegistrarConsentimientos(BaseModel):
    version: str
    items: list[ItemConsentimiento]
    origen: str = "app"


def _ip(request: Request) -> str | None:
    """IP del cliente (opcional). Detrás de Railway llega en X-Forwarded-For."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()[:64] or None
    return request.client.host[:64] if request.client else None


def estado_vigente(db: Session, usuario_id: str) -> dict[str, dict]:
    """{finalidad: {aceptado, version, fecha_utc, fecha_co}} con la fila MÁS RECIENTE de cada una."""
    filas = (
        db.query(Consentimiento)
        .filter(Consentimiento.usuario_id == usuario_id)
        .order_by(Consentimiento.creado_en_utc.asc(), Consentimiento.id.asc())
        .all()
    )
    vigente: dict[str, dict] = {}
    for f in filas:  # orden ascendente: la última sobrescribe
        vigente[f.finalidad] = {
            "aceptado": bool(f.aceptado),
            "version": f.version,
            "fecha_utc": f.creado_en_utc.isoformat(),
            "fecha_co": f.creado_en_co.isoformat(),
        }
    return vigente


def tiene_consentimiento(db: Session, usuario_id: str, finalidad: str) -> bool:
    return bool(estado_vigente(db, usuario_id).get(finalidad, {}).get("aceptado"))


def exigir_consentimiento(db: Session, usuario_id: str, finalidad: str) -> None:
    """Bloquea (403) si el usuario no ha dado esta autorización. El detalle es un objeto
    con `codigo` para que la app muestre el consentimiento específico en vez de un error."""
    if not settings.exigir_consentimientos:
        return
    if not tiene_consentimiento(db, usuario_id, finalidad):
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "consentimiento_requerido",
                "finalidad": finalidad,
                "mensaje": MENSAJES_REQUERIDO.get(finalidad, "Falta una autorización."),
            },
        )


@router.get("")
def obtener_consentimientos(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    vigente = estado_vigente(db, usuario.id)
    basico = vigente.get("tratamiento_basico")
    requiere = not (basico and basico["aceptado"] and basico["version"] == VERSION_TEXTOS)
    return {
        "version_vigente": VERSION_TEXTOS,
        "requiere_autorizacion": requiere,
        "finalidades": {
            nombre: {**meta, **vigente.get(nombre, {"aceptado": False, "version": None, "fecha_utc": None, "fecha_co": None})}
            for nombre, meta in FINALIDADES.items()
        },
    }


@router.get("/historial")
def historial_consentimientos(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Todos los registros del usuario, del más nuevo al más viejo (sin la IP)."""
    filas = (
        db.query(Consentimiento)
        .filter(Consentimiento.usuario_id == usuario.id)
        .order_by(Consentimiento.creado_en_utc.desc(), Consentimiento.id.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": f.id, "version": f.version, "finalidad": f.finalidad, "aceptado": bool(f.aceptado),
            "fecha_utc": f.creado_en_utc.isoformat(), "fecha_co": f.creado_en_co.isoformat(), "origen": f.origen,
        }
        for f in filas
    ]


@router.post("")
def registrar_consentimientos(
    data: RegistrarConsentimientos,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Registra (INSERT) una o varias decisiones. Revocar = enviar aceptado=false."""
    if data.version != VERSION_TEXTOS:
        raise HTTPException(status_code=400, detail=f"La versión vigente de los textos es la {VERSION_TEXTOS}.")
    if not data.items:
        raise HTTPException(status_code=400, detail="No enviaste ninguna decisión.")
    vistas: set[str] = set()
    for it in data.items:
        if it.finalidad not in FINALIDADES:
            raise HTTPException(status_code=400, detail=f"Finalidad desconocida: {it.finalidad}")
        if it.finalidad in vistas:
            raise HTTPException(status_code=400, detail=f"Finalidad repetida: {it.finalidad}")
        vistas.add(it.finalidad)

    ahora_utc = datetime.utcnow()
    ahora = ahora_co()
    ip = _ip(request)
    for it in data.items:
        db.add(Consentimiento(
            usuario_id=usuario.id, version=data.version, finalidad=it.finalidad, aceptado=it.aceptado,
            creado_en_utc=ahora_utc, creado_en_co=ahora, ip=ip, origen=(data.origen or "app")[:30],
        ))
    db.commit()
    return obtener_consentimientos(db=db, usuario=usuario)
