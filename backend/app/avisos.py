"""Avisos de actividad para el administrador («avísame cuando alguien se registra y demás»).

Una sola puerta: `registrar_evento(...)`. Guarda el evento en `eventos_actividad` (el panel
«Actividad reciente» funciona siempre) y, si las preferencias lo piden, avisa por push al celular
del administrador y/o por correo (Resend).

Reglas que no se rompen:
  * Registrar un evento NUNCA rompe ni retrasa la operación de la persona: corre en un hilo aparte,
    con su propia sesión, y todo error se traga (queda en el log, sin datos personales).
  * Idempotente: los eventos «de una sola vez» llevan `clave_unica`; la restricción única de la base
    decide, así dos peticiones simultáneas (o dos réplicas) no duplican.
  * Privacidad: el aviso muestra el correo ENMASCARADO (d***@gmail.com), nunca nombres, montos ni
    descripciones. El correo completo solo aparece en el panel del administrador.
  * Ruido: máximo MAX_AVISOS_POR_HORA avisos por hora; lo que pase se agrupa en un solo aviso
    «N eventos nuevos». Hay silencio por horas y resumen diario opcional.
  * Correo: si Resend rechaza el envío (p. ej. el remitente de pruebas `resend.dev` solo entrega al
    dueño de la cuenta) se deja un warning claro y NO se reintenta en bucle (pausa de varias horas).
"""
import json
import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import httpx
from sqlalchemy import event, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import get_history

from app.config import settings
from app.database import SessionLocal
from app.models import Cuenta, Movimiento, Perfil, PushSubscription
from app.models_avisos import AjustesAvisos, EventoActividad
from app.push import enviar_push
from app.utiles import ahora_co

logger = logging.getLogger("app.avisos")

MAX_AVISOS_POR_HORA = 20
PAUSA_CORREO_RECHAZADO_S = 6 * 3600  # tras un rechazo de Resend no se vuelve a intentar en 6 h
PAUSA_CORREO_FALLO_S = 15 * 60
SINCRONO = False  # pruebas: ejecuta en el mismo hilo para poder comprobar el resultado

# tipo -> (etiqueta corta, push por defecto, correo por defecto)
TIPOS: dict[str, tuple[str, bool, bool]] = {
    "nuevo_registro": ("Nuevo registro", True, True),
    "primera_cuenta": ("Primera cuenta creada", True, False),
    "primer_movimiento": ("Primer movimiento (activación)", True, False),
    "gmail_conectado": ("Gmail conectado", True, False),
    "atajo_activado": ("Primer pago por atajo", True, False),
    "cuenta_eliminada": ("Cuenta eliminada", True, True),
    "comentario_problema": ("Problema reportado", True, True),
    "comentarios_pendientes": ("Comentarios sin revisar", True, True),
    "limite_alcanzado": ("Tope diario alcanzado", False, False),
    "umbral_capacidad": ("Capacidad cerca del límite", True, True),
    "errores_5xx_picos": ("Pico de errores del servidor", True, True),
}

_FRASE = {
    "nuevo_registro": "se registró en CuadraMe",
    "primera_cuenta": "creó su primera cuenta",
    "primer_movimiento": "registró su primer movimiento",
    "gmail_conectado": "conectó su Gmail",
    "atajo_activado": "hizo su primer pago por atajo",
    "limite_alcanzado": "llegó a un tope diario",
}

_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="avisos")
_envios: deque = deque()  # marcas de tiempo (time.time) de avisos enviados, para el tope por hora
_vistos: set[str] = set()  # usuarios ya revisados en este proceso
_marcados: set[tuple[str, str]] = set()  # (tipo, usuario) ya programados en este proceso
_ignorados: set[str] = set()  # cuentas eliminadas en este proceso: no son «nuevos registros»
_correo_pausado_hasta = 0.0


# ───────────────────────────── Utilidades ─────────────────────────────

def enmascarar_correo(correo: str | None) -> str:
    """d***@gmail.com. Sin correo válido: «***»."""
    c = (correo or "").strip()
    local, _, dominio = c.partition("@")
    if not local or not dominio:
        return "***"
    return f"{local[0]}***@{dominio}"


def _meta_json(meta: dict | None) -> str | None:
    """Solo valores simples y cortos: nada de estructuras grandes ni textos libres."""
    if not meta:
        return None
    limpio = {str(k)[:30]: (v if isinstance(v, (bool, int, float)) or v is None else str(v)[:60])
              for k, v in list(meta.items())[:8]}
    return json.dumps(limpio, ensure_ascii=False)[:400]


def _resumen(tipo: str, email: str | None) -> str:
    etiqueta = TIPOS[tipo][0]
    if tipo == "cuenta_eliminada":
        return "Una persona eliminó su cuenta"
    if email:
        frase = _FRASE.get(tipo)
        return f"{enmascarar_correo(email)} {frase}" if frase else f"{etiqueta}: {enmascarar_correo(email)}"
    return etiqueta


def _lanzar(fn, *args) -> None:
    if SINCRONO:
        fn(*args)
        return
    try:
        _executor.submit(fn, *args)
    except Exception:  # noqa: BLE001
        logger.warning("Avisos: no se pudo programar el evento", exc_info=True)


def _destino() -> str:
    return (settings.admin_email or "").strip()


# ───────────────────────────── Preferencias ─────────────────────────────

def preferencias_por_defecto() -> dict:
    return {t: {"push": p, "correo": c} for t, (_e, p, c) in TIPOS.items()}


def fila_admin(db: Session) -> AjustesAvisos | None:
    return db.query(AjustesAvisos).order_by(AjustesAvisos.actualizado_en.desc()).first()


def leer_preferencias(fila: AjustesAvisos | None) -> dict:
    prefs = preferencias_por_defecto()
    if fila is not None and fila.tipos:
        try:
            for t, v in json.loads(fila.tipos).items():
                if t in prefs and isinstance(v, dict):
                    prefs[t] = {"push": bool(v.get("push", prefs[t]["push"])),
                                "correo": bool(v.get("correo", prefs[t]["correo"]))}
        except (ValueError, TypeError):
            pass
    return prefs


def asegurar_fila_admin(db: Session, usuario_id: str) -> AjustesAvisos:
    """La fila de ajustes ES la forma de saber quién es el administrador (id) para el push.
    Solo se llama con una sesión ya verificada cuyo correo coincide con ADMIN_EMAIL."""
    fila = db.query(AjustesAvisos).filter(AjustesAvisos.usuario_id == usuario_id).first()
    if fila is None:
        try:
            fila = AjustesAvisos(usuario_id=usuario_id, resumen_diario=False)
            db.add(fila)
            db.commit()
        except IntegrityError:
            db.rollback()
            fila = db.query(AjustesAvisos).filter(AjustesAvisos.usuario_id == usuario_id).first()
    return fila


# ───────────────────────────── Envío ─────────────────────────────

def _cupo_hora(consumir: bool = False) -> bool:
    """¿Quedan avisos esta hora? Con consumir=True, gasta uno."""
    ahora = time.time()
    with _lock:
        while _envios and _envios[0] < ahora - 3600:
            _envios.popleft()
        hay = len(_envios) < MAX_AVISOS_POR_HORA
        if hay and consumir:
            _envios.append(ahora)
        return hay


def _enviar_correo(db: Session, asunto: str, texto: str) -> bool:
    """True si salió. Un rechazo de Resend pausa el correo varias horas (sin bucles de reintento)."""
    global _correo_pausado_hasta
    from app import crecimiento

    destino = _destino()
    if not destino or not settings.resend_api_key:
        return False
    if time.time() < _correo_pausado_hasta:
        return False
    try:
        crecimiento._enviar(destino, asunto, texto)
        return True
    except httpx.HTTPStatusError as e:
        codigo = e.response.status_code
        rechazo = codigo in (401, 403, 422)
        _correo_pausado_hasta = time.time() + (PAUSA_CORREO_RECHAZADO_S if rechazo else PAUSA_CORREO_FALLO_S)
        if rechazo:
            motivo = (f"Resend rechazó el correo (HTTP {codigo}). Con el remitente de pruebas (resend.dev) solo se "
                      "puede escribir al dueño de la cuenta de Resend: verifica un dominio en Resend y define "
                      "RESEND_FROM con ese dominio. Los avisos siguen llegando por push y en el panel.")
        else:
            motivo = f"Resend respondió HTTP {codigo}; se pausa el correo un rato."
        logger.warning("Avisos: %s", motivo)
        _guardar_error_correo(db, motivo)
    except Exception as e:  # noqa: BLE001
        _correo_pausado_hasta = time.time() + PAUSA_CORREO_FALLO_S
        logger.warning("Avisos: no se pudo enviar el correo (%s); se pausa un rato", type(e).__name__)
        _guardar_error_correo(db, f"No se pudo enviar el correo ({type(e).__name__}).")
    return False


def _guardar_error_correo(db: Session, motivo: str) -> None:
    try:
        fila = fila_admin(db)
        if fila is not None:
            fila.correo_error = motivo[:300]
            fila.correo_error_en = datetime.utcnow()
            db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()


def _limpiar_error_correo(db: Session) -> None:
    try:
        fila = fila_admin(db)
        if fila is not None and fila.correo_error:
            fila.correo_error = None
            fila.correo_error_en = None
            db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()


def notificar(db: Session, titulo: str, cuerpo: str, *, push: bool, correo: bool,
              fila: AjustesAvisos | None) -> dict:
    """Un aviso por los canales pedidos. Devuelve {"push": n, "correo": bool}."""
    n_push, ok_correo = 0, False
    if push and fila is not None:
        try:
            n_push = enviar_push(db, fila.usuario_id, titulo, cuerpo, "/salud-negocio")
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.warning("Avisos: falló el push", exc_info=True)
    if correo:
        texto = f"{cuerpo}\n\n—\nVer detalle: CuadraMe > Más > Salud del negocio > Actividad reciente."
        ok_correo = _enviar_correo(db, f"CuadraMe: {titulo}", texto)
        if ok_correo:
            _limpiar_error_correo(db)
    return {"push": n_push, "correo": ok_correo}


def _vaciar_agrupados(db: Session, fila: AjustesAvisos | None, prefs: dict) -> None:
    """Si había eventos agrupados por el tope y ya hay cupo, manda UN aviso «N eventos nuevos»."""
    pendientes = db.query(EventoActividad).filter(EventoActividad.aviso_estado == "agrupado").all()
    if not pendientes or not _cupo_hora(consumir=True):
        return
    n = len(pendientes)
    push = any(prefs[e.tipo]["push"] for e in pendientes if e.tipo in prefs)
    correo = any(prefs[e.tipo]["correo"] for e in pendientes if e.tipo in prefs)
    notificar(db, f"{n} eventos nuevos", "Hubo bastante actividad. Míralos en Actividad reciente.",
              push=push, correo=correo, fila=fila)
    for e in pendientes:
        e.aviso_estado = "resumido"
    db.commit()


def _despachar(db: Session, ev: EventoActividad, sin_correo: bool = False, sin_push: bool = False) -> None:
    fila = fila_admin(db)
    prefs = leer_preferencias(fila)
    p = prefs.get(ev.tipo, {"push": False, "correo": False})
    quiere_push = p["push"] and not sin_push
    quiere_correo = p["correo"] and not sin_correo
    if not quiere_push and not quiere_correo:
        ev.aviso_estado = "sin_canal"
        db.commit()
        return
    if fila is not None and fila.silenciado_hasta and fila.silenciado_hasta > datetime.utcnow():
        ev.aviso_estado = "silenciado"
        db.commit()
        return
    if fila is not None and fila.resumen_diario:
        ev.aviso_estado = "resumen"
        db.commit()
        return
    _vaciar_agrupados(db, fila, prefs)
    if not _cupo_hora(consumir=True):
        ev.aviso_estado = "agrupado"  # lo recoge el próximo «N eventos nuevos» o el resumen diario
        db.commit()
        return
    r = notificar(db, TIPOS[ev.tipo][0], ev.resumen, push=quiere_push, correo=quiere_correo, fila=fila)
    ev.aviso_estado = "enviado" if (r["push"] or r["correo"]) else "sin_canal"
    db.commit()


# ───────────────────────────── Registro de eventos ─────────────────────────────

def _email_de(db: Session, usuario_id: str | None) -> str | None:
    if not usuario_id:
        return None
    return db.query(EventoActividad.email).filter(
        EventoActividad.clave_unica == f"nuevo_registro:{usuario_id}").scalar()


def _procesar(tipo: str, usuario_id: str | None, email: str | None, meta: dict | None, clave_unica: str | None,
              sin_correo: bool, sin_push: bool, requiere_registro: bool, texto: str | None = None) -> None:
    """Hilo aparte, sesión propia. Nunca lanza."""
    db = SessionLocal()
    try:
        if requiere_registro and usuario_id:
            # Eventos de activación: solo de personas que llegaron desde que existen los avisos
            # (así un usuario antiguo no aparece como «primera cuenta» por hacer algo hoy).
            if not db.query(EventoActividad.id).filter(
                    EventoActividad.clave_unica == f"nuevo_registro:{usuario_id}").first():
                return
        if email is None:
            email = _email_de(db, usuario_id)
        ev = EventoActividad(tipo=tipo, usuario_id=usuario_id, clave_unica=clave_unica,
                             resumen=(texto or _resumen(tipo, email))[:200], email=(email or None), meta=_meta_json(meta))
        try:
            db.add(ev)
            db.commit()
        except IntegrityError:
            db.rollback()  # ya existía: idempotente
            return
        _despachar(db, ev, sin_correo=sin_correo, sin_push=sin_push)
    except Exception:  # noqa: BLE001 - un aviso jamás debe afectar a nadie
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        logger.warning("Avisos: no se pudo registrar el evento %s", tipo, exc_info=True)
    finally:
        db.close()


def registrar_evento(tipo: str, usuario_id: str | None = None, email: str | None = None, meta: dict | None = None,
                     clave_unica: str | None = None, sin_correo: bool = False, sin_push: bool = False,
                     requiere_registro: bool = False, texto: str | None = None) -> None:
    """Punto de entrada. No bloquea y no lanza. `clave_unica` evita repetir el evento.
    `texto` reemplaza la frase automática (debe ser genérico: sin datos de personas)."""
    try:
        if tipo not in TIPOS:
            logger.warning("Avisos: tipo desconocido %s", tipo)
            return
        _lanzar(_procesar, tipo, usuario_id, email, meta, clave_unica, sin_correo, sin_push, requiere_registro, texto)
    except Exception:  # noqa: BLE001
        logger.warning("Avisos: fallo al programar %s", tipo, exc_info=True)


# ── Primera vez que se ve a un usuario autenticado ──

def _revisar_usuario(usuario_id: str, email: str) -> None:
    from app.crecimiento import es_admin

    db = SessionLocal()
    try:
        if es_admin(email):
            asegurar_fila_admin(db, usuario_id)  # así el push sabe a qué celular ir
        if usuario_id in _ignorados:
            return
        if db.query(EventoActividad.id).filter(
                EventoActividad.clave_unica == f"nuevo_registro:{usuario_id}").first():
            return
        perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
        if perfil is not None:
            if perfil.creado_en is None or perfil.creado_en < datetime.utcnow() - timedelta(days=1):
                return  # usuario de antes de los avisos
        elif (db.query(Cuenta.id).filter(Cuenta.usuario_id == usuario_id).first()
              or db.query(Movimiento.id).filter(Movimiento.usuario_id == usuario_id).first()):
            return  # sin perfil pero con datos: ya usaba la app
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.warning("Avisos: no se pudo revisar al usuario", exc_info=True)
        return
    finally:
        db.close()
    _procesar("nuevo_registro", usuario_id, email or None, None, f"nuevo_registro:{usuario_id}", False, False, False)


def visto(usuario) -> None:
    """Se llama en cada petición autenticada; solo la PRIMERA vez por proceso hace algo (en un hilo)."""
    try:
        uid = getattr(usuario, "id", None)
        if not uid:
            return
        with _lock:
            if uid in _vistos:
                return
            if len(_vistos) > 100_000:
                _vistos.clear()
            _vistos.add(uid)
        _lanzar(_revisar_usuario, uid, getattr(usuario, "email", "") or "")
    except Exception:  # noqa: BLE001
        pass


def cuenta_eliminada(usuario_id: str) -> None:
    """Tras borrar la cuenta: se anota SIN datos (sin id ni correo)."""
    with _lock:
        _ignorados.add(usuario_id)
    registrar_evento("cuenta_eliminada")


def limite_alcanzado(usuario_id: str, accion: str, dia: str) -> None:
    registrar_evento("limite_alcanzado", usuario_id, meta={"accion": accion},
                     clave_unica=f"limite:{usuario_id}:{accion}:{dia}")


# ── Eventos de activación vía la base (Cuenta, Movimiento, Perfil) ──
# Se anotan al insertar y se disparan solo si la transacción SE CONFIRMÓ (after_commit).

_INFO = "avisos_pendientes"


def _anotar(target, tipo: str, meta: dict | None = None) -> None:
    uid = getattr(target, "usuario_id", None)
    if not uid:
        return
    with _lock:
        if (tipo, uid) in _marcados:
            return
    sesion = Session.object_session(target)
    if sesion is not None:
        sesion.info.setdefault(_INFO, []).append((tipo, uid, meta))


@event.listens_for(Cuenta, "after_insert")
def _cuenta_creada(_mapper, _conn, target):
    _anotar(target, "primera_cuenta")


@event.listens_for(Movimiento, "after_insert")
def _movimiento_creado(_mapper, _conn, target):
    origen = getattr(target, "origen", None)
    _anotar(target, "primer_movimiento", {"canal": origen or "manual"})
    if origen == "atajo":
        _anotar(target, "atajo_activado")


@event.listens_for(Perfil, "after_update")
def _perfil_actualizado(_mapper, _conn, target):
    try:
        h = get_history(target, "gmail_conectado")
        if h.added and h.added[0] is True:
            _anotar(target, "gmail_conectado")
    except Exception:  # noqa: BLE001
        pass


@event.listens_for(Session, "after_commit")
def _tras_commit(sesion):
    try:
        pendientes = sesion.info.pop(_INFO, None)
        if not pendientes:
            return
        for tipo, uid, meta in pendientes:
            with _lock:
                if (tipo, uid) in _marcados:
                    continue
                if len(_marcados) > 100_000:
                    _marcados.clear()
                _marcados.add((tipo, uid))
            registrar_evento(tipo, uid, meta=meta, clave_unica=f"{tipo}:{uid}", requiere_registro=True)
    except Exception:  # noqa: BLE001
        pass


@event.listens_for(Session, "after_rollback")
def _tras_rollback(sesion):
    sesion.info.pop(_INFO, None)


# ───────────────────────────── Resumen diario / pendientes ─────────────────────────────

def enviar_resumen(db: Session) -> dict:
    """Cron diario. Junta los eventos en espera (modo resumen o agrupados por el tope) en UN aviso."""
    from app.crecimiento import SISTEMA
    from app.crons import reclamar_marca

    fila = fila_admin(db)
    prefs = leer_preferencias(fila)
    pendientes = db.query(EventoActividad).filter(
        EventoActividad.aviso_estado.in_(("resumen", "agrupado"))).all()
    if not pendientes:
        return {"ok": True, "enviado": False, "eventos": 0}
    dia = ahora_co().strftime("%Y-%m-%d")
    if not reclamar_marca(db, SISTEMA, "avisos:resumen-diario", dia):
        return {"ok": True, "enviado": False, "eventos": len(pendientes), "ya_enviado": True}
    cuenta: dict[str, int] = {}
    for e in pendientes:
        cuenta[e.tipo] = cuenta.get(e.tipo, 0) + 1
    lineas = [f"{n} x {TIPOS[t][0].lower()}" for t, n in sorted(cuenta.items(), key=lambda kv: -kv[1]) if t in TIPOS]
    cuerpo = f"{len(pendientes)} eventos desde el último resumen: " + ", ".join(lineas) + "."
    push = any(prefs[t]["push"] for t in cuenta if t in prefs)
    correo = any(prefs[t]["correo"] for t in cuenta if t in prefs)
    r = notificar(db, f"Resumen: {len(pendientes)} eventos", cuerpo, push=push, correo=correo, fila=fila)
    salio = bool(r["push"] or r["correo"])
    for e in pendientes:
        e.aviso_estado = "resumido"
    db.commit()
    if not salio and (push or correo):
        # Sin canal disponible: queda en el panel; no se reintenta (evita bucles).
        logger.info("Avisos: el resumen diario no tuvo canal de salida; los eventos quedan en el panel")
    return {"ok": True, "enviado": salio, "eventos": len(pendientes)}


def tiene_push(db: Session, usuario_id: str) -> bool:
    return (db.query(func.count(PushSubscription.id)).filter(PushSubscription.usuario_id == usuario_id).scalar() or 0) > 0


def reiniciar_para_pruebas() -> None:
    global _correo_pausado_hasta
    with _lock:
        _envios.clear()
        _vistos.clear()
        _marcados.clear()
        _ignorados.clear()
    _correo_pausado_hasta = 0.0
