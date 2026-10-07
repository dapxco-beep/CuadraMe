"""Tablero "Conexiones y estado": una sola llamada que dice si cada conexión
(Gmail, Atajo de iPhone / clave API, conciliación, notificaciones) está
funcionando, con semáforo (verde / ambar / rojo) y una frase de explicación.
Solo lee: nunca modifica datos ni devuelve secretos (ni la clave API)."""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.compartidos import cuentas_ids_accesibles
from app.conciliacion import parse_bank_date
from app.database import get_db
from app.models import (
    ClavePdf, Cuenta, CorreoGasto, ExtractoCorreo, HistorialExtracto, Movimiento,
    Perfil, PushSubscription, SyncGmail,
)
from app.utiles import ahora_co
from app.wallet import FUENTES_POR_CONFIRMAR

router = APIRouter(prefix="/conexiones", tags=["conexiones"])

HORAS_SYNC_VIEJA = 48
DIAS_ATAJO_INACTIVO = 7


def _semaforo(color: str, mensaje: str, **datos) -> dict:
    return {"semaforo": color, "mensaje": mensaje, **datos}


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def _gmail(db: Session, usuario_id: str, perfil: Perfil | None) -> dict:
    conectado = bool(perfil and perfil.gmail_conectado)
    sync = db.query(SyncGmail).filter(SyncGmail.usuario_id == usuario_id).first()
    extractos = db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == usuario_id)
    datos = {
        "conectado": conectado,
        "email": perfil.gmail_email if conectado else None,
        "ultima_sync": _iso(sync.ultima_sync) if sync else None,
        "correos_leidos": (sync.ultimo_leidos or 0) if sync else 0,
        "notificaciones": db.query(func.count(CorreoGasto.id))
        .filter(CorreoGasto.usuario_id == usuario_id, CorreoGasto.estado != "ignorado").scalar() or 0,
        "extractos": extractos.filter(ExtractoCorreo.estado.in_(("nuevo", "falta_clave", "procesado", "error"))).count(),
        "extractos_falta_clave": extractos.filter(ExtractoCorreo.estado == "falta_clave").count(),
        "clave_pdf": db.query(ClavePdf).filter(ClavePdf.usuario_id == usuario_id).first() is not None,
        "en_curso": bool(sync and sync.en_curso),
        "progreso": {"leidos": sync.leidos or 0, "total": max(sync.total_estimado or 0, sync.leidos or 0)}
        if sync and sync.en_curso else None,
    }
    if not conectado:
        return _semaforo("ambar", "Gmail no está conectado: conéctalo para que CuadraMe lea tus notificaciones y extractos.", **datos)
    if sync and sync.ultimo_error and (not sync.ultima_sync or (sync.ultimo_error_en and sync.ultimo_error_en > sync.ultima_sync)):
        return _semaforo("rojo", "La última sincronización falló. Inténtalo de nuevo; si sigue igual, reconecta Gmail.", **datos)
    if not sync or not sync.ultima_sync:
        msg = "Conectado, pero aún no se completó la primera sincronización." if not (sync and sync.en_curso) else "Sincronizando tus correos..."
        return _semaforo("ambar", msg, **datos)
    if datetime.utcnow() - sync.ultima_sync > timedelta(hours=HORAS_SYNC_VIEJA):
        return _semaforo("ambar", "Hace más de 2 días que no se sincroniza. Pulsa Sincronizar todo.", **datos)
    if datos["extractos_falta_clave"]:
        n = datos["extractos_falta_clave"]
        return _semaforo("ambar", f"{n} extracto{'s' if n != 1 else ''} esperan la clave del PDF (normalmente tu cédula).", **datos)
    return _semaforo("verde", "Todo al día: tus correos se están leyendo bien.", **datos)


def _atajo(db: Session, usuario_id: str, perfil: Perfil | None) -> dict:
    ultimo = perfil.api_key_ultimo_uso if perfil else None
    hace7 = ahora_co() - timedelta(days=7)  # las fechas de movimientos van en hora de Colombia
    ids = cuentas_ids_accesibles(db, usuario_id)
    recibidos = (
        db.query(func.count(Movimiento.id))
        .filter(
            Movimiento.cuenta_id.in_(ids), Movimiento.fuente.in_(FUENTES_POR_CONFIRMAR),
            Movimiento.fecha >= hace7,
        )
        .scalar() or 0
    )
    datos = {"tiene_clave": bool(perfil and perfil.api_key), "ultimo_uso": _iso(ultimo), "movimientos_7d": recibidos}
    if not datos["tiene_clave"]:
        return _semaforo("ambar", "Aún no tienes clave: genérala para conectar el Atajo de tu iPhone.", **datos)
    if not ultimo:
        return _semaforo("ambar", "La clave existe pero nunca se ha usado. Usa Probar conexión.", **datos)
    if datetime.utcnow() - ultimo > timedelta(days=DIAS_ATAJO_INACTIVO):
        return _semaforo("ambar", "Hace más de una semana que el Atajo no envía nada. Revisa que siga activo.", **datos)
    return _semaforo("verde", "El Atajo está enviando movimientos.", **datos)


def _conciliacion(db: Session, usuario_id: str) -> dict:
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).order_by(Cuenta.nombre).all()
    filas = []
    for c in cuentas:
        h = (
            db.query(HistorialExtracto)
            .filter(HistorialExtracto.usuario_id == usuario_id, HistorialExtracto.cuenta_id == c.id)
            .order_by(HistorialExtracto.creado_en.desc())
            .first()
        )
        if not h:
            filas.append({"cuenta_id": c.id, "cuenta": c.nombre, "icono": c.icono, "extracto": False})
            continue
        try:
            review = json.loads(h.review_json or "[]")
        except ValueError:
            review = []
        cruzados = (h.exactos or 0) + (h.aproximados or 0) + (h.importados or 0)
        fechas = [f for f in (parse_bank_date(i.get("fecha")) for i in review) if f]
        sin_extracto = 0
        if fechas:
            # Movimientos de la app dentro del rango del extracto que no cruzaron.
            en_app = (
                db.query(func.count(Movimiento.id))
                .filter(Movimiento.cuenta_id == c.id, Movimiento.fecha >= min(fechas),
                        Movimiento.fecha < max(fechas) + timedelta(days=1))
                .scalar() or 0
            )
            sin_extracto = max(en_app - cruzados, 0)
        faltantes = h.faltantes or 0
        filas.append({
            "cuenta_id": c.id, "cuenta": c.nombre, "icono": c.icono, "extracto": True,
            "historial_id": h.id, "banco": h.banco_detectado, "ultimo_cruce": _iso(h.creado_en),
            "cruzados": cruzados, "faltantes": faltantes, "sin_extracto": sin_extracto,
            "estado": h.estado,
        })
    con = [f for f in filas if f["extracto"]]
    if not con:
        return _semaforo("ambar", "Aún no has cruzado ningún extracto. Importa uno para verificar tus movimientos.", cuentas=filas)
    pend = sum(f["faltantes"] for f in con)
    if pend:
        return _semaforo("ambar", f"Hay {pend} movimiento{'s' if pend != 1 else ''} del banco sin registrar en tus cuentas.", cuentas=filas)
    return _semaforo("verde", "Tus extractos cruzan con lo que registraste.", cuentas=filas)


def _push(db: Session, usuario_id: str) -> dict:
    n = db.query(func.count(PushSubscription.id)).filter(PushSubscription.usuario_id == usuario_id).scalar() or 0
    if n:
        return _semaforo("verde", "Las notificaciones están activas.", suscripciones=n)
    return _semaforo("ambar", "No tienes notificaciones activas en ningún dispositivo.", suscripciones=0)


@router.get("/estado")
def estado_conexiones(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario.id).first()
    gmail = _gmail(db, usuario.id, perfil)
    atajo = _atajo(db, usuario.id, perfil)
    conciliacion = _conciliacion(db, usuario.id)
    push = _push(db, usuario.id)
    # Rojo = algo que se rompió; el Inicio solo avisa por rojo o por Gmail sin sincronizar.
    hay_falla = any(x["semaforo"] == "rojo" for x in (gmail, atajo, conciliacion, push))
    return {
        "gmail": gmail, "atajo": atajo, "conciliacion": conciliacion, "push": push,
        "hay_falla": hay_falla,
    }
