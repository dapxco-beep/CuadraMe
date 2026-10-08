"""
Métricas propias de uso, para saber cuándo se acerca el momento de subir de
plan en algún servicio (Railway, Supabase, Resend, Sentry). No sustituye los
paneles de cada proveedor — esos tienen las cuotas reales de infraestructura
(requests, storage en disco, cuota de envío de correos, eventos de error) —
pero da una señal temprana basada en lo que el propio negocio puede medir:
cuántos usuarios hay y qué tan activos están.
"""
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, cron_autorizado, get_current_user
from app.crecimiento import armar_panel, es_admin, procesar_avisos, registrar_correo_enviado
from app.config import settings
from app.database import get_db
from app.models import Movimiento, Perfil

router = APIRouter(prefix="/metricas", tags=["metricas"])

# Umbrales de referencia para saber cuándo un plan gratuito/básico se va a
# quedar corto. Son aproximados a propósito: la señal real de "hay que subir
# de plan" siempre debe confirmarse en el panel del proveedor (Railway,
# Supabase, Resend, Sentry), esto solo avisa que ya vale la pena ir a mirar.
UMBRAL_USUARIOS_SUPABASE_FREE = 400  # Supabase Free soporta bien hasta unos cientos de usuarios con auth + datos ligeros
UMBRAL_MOVIMIENTOS_ALERTA = 200_000  # a este volumen de filas, Supabase Free (500MB) empieza a apretar
UMBRAL_USUARIOS_ACTIVOS_RAILWAY_HOBBY = 300  # Railway Hobby ($5) empieza a quedarse corto en requests concurrentes


def _calcular_uso(db: Session) -> dict:
    total_usuarios = db.query(func.count(Perfil.usuario_id)).scalar() or 0
    total_movimientos = db.query(func.count(Movimiento.id)).scalar() or 0

    hace_7_dias = datetime.utcnow() - timedelta(days=7)
    usuarios_activos_7d = (
        db.query(func.count(func.distinct(Movimiento.usuario_id)))
        .filter(Movimiento.fecha >= hace_7_dias)
        .scalar()
        or 0
    )

    alertas = []
    if total_usuarios >= UMBRAL_USUARIOS_SUPABASE_FREE * 0.7:
        alertas.append(
            f"Usuarios totales ({total_usuarios}) cerca del umbral de referencia "
            f"para Supabase Free ({UMBRAL_USUARIOS_SUPABASE_FREE}) — revisa storage en el panel de Supabase."
        )
    if total_movimientos >= UMBRAL_MOVIMIENTOS_ALERTA * 0.7:
        alertas.append(
            f"Movimientos totales ({total_movimientos}) cerca del umbral de referencia "
            f"({UMBRAL_MOVIMIENTOS_ALERTA}) — revisa el uso de storage en Supabase."
        )
    if usuarios_activos_7d >= UMBRAL_USUARIOS_ACTIVOS_RAILWAY_HOBBY * 0.7:
        alertas.append(
            f"Usuarios activos últimos 7 días ({usuarios_activos_7d}) cerca del umbral de referencia "
            f"para Railway Hobby ({UMBRAL_USUARIOS_ACTIVOS_RAILWAY_HOBBY}) — revisa métricas de uso en Railway."
        )

    return {
        "usuarios_totales": total_usuarios,
        "usuarios_activos_7d": usuarios_activos_7d,
        "movimientos_totales": total_movimientos,
        "alertas": alertas,
    }


@router.get("/uso")
def uso_actual(
    x_cron_secret: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Protegido igual que los crons (no es información que deba ser pública).
    Devuelve conteos propios; las cuotas de infraestructura hay que
    verificarlas en el panel de cada proveedor."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    return _calcular_uso(db)


@router.post("/cron/revisar-uso-semanal")
def cron_revisar_uso_semanal(
    x_cron_secret: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Pensado para llamarse una vez a la semana. Solo manda correo si hay
    algo cerca de un umbral — nada si todo va bien, para no generar ruido
    semana tras semana con un simple 'todo normal'."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")

    uso = _calcular_uso(db)
    if not uso["alertas"]:
        return {"ok": True, "enviado": False, "procesados": 1, "fallidos": 0, **uso}

    if not settings.resend_api_key:
        return {"ok": False, "enviado": False, "error": "Resend no configurado",
                "procesados": 0, "fallidos": 1, **uso}

    cuerpo = "Uso actual de CuadraMe que vale la pena revisar:\n\n" + "\n\n".join(
        f"• {a}" for a in uso["alertas"]
    ) + (
        f"\n\n—\nUsuarios totales: {uso['usuarios_totales']}"
        f"\nUsuarios activos (7 días): {uso['usuarios_activos_7d']}"
        f"\nMovimientos totales: {uso['movimientos_totales']}"
    )

    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": settings.resend_from,
            "to": [settings.backup_email],
            "subject": "CuadraMe — uso acercándose a un límite de plan",
            "text": cuerpo,
        },
        timeout=30,
    )
    resp.raise_for_status()
    registrar_correo_enviado()
    return {"ok": True, "enviado": True, "procesados": 1, "fallidos": 0, **uso}


@router.post("/cron/avisos-crecimiento")
def cron_avisos_crecimiento(
    x_cron_secret: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Monitor de capacidad y crecimiento. Pensado para correr a diario (08:00 Bogotá).
    Idempotente por umbral (marcas_cron): repetirlo no repite el mismo aviso. Cada medición y
    cada recurso son tolerantes a fallos. Detalle y umbrales: app/crecimiento.py."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    return procesar_avisos(db)


@router.get("/panel")
def panel_salud_negocio(
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«Salud del negocio»: solo el administrador (ADMIN_EMAIL). Para cualquier otra persona responde
    404, igual que una ruta que no existe, para no revelar que hay un panel."""
    if not es_admin(usuario.email):
        raise HTTPException(status_code=404, detail="No encontrado")
    return armar_panel(db)
