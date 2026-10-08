"""
Monitor de capacidad y crecimiento de CuadraMe.

Objetivo: que el sistema AVISE a Daniel (correo + Sentry) cuando algo se acerca a su límite, con
tiempo para subir de plan, y que el panel «Salud del negocio» lo muestre en barras.

Piezas:
  - `recopilar(db)`: mide todo (cada medición es tolerante: si una falla queda en None).
  - `capacidades(m)`: convierte las mediciones en «cuánto de su límite llevamos» + qué hacer.
  - `procesar_avisos(db)`: lo que corre el cron diario; idempotente por umbral (marcas_cron).
  - `armar_panel(db)`: lo que lee el panel (solo admin).

Privacidad: aquí solo hay CONTEOS. Ni correos, ni nombres, ni ids de usuarios salen hacia el correo
de aviso ni hacia Sentry.
"""
import logging
from datetime import datetime, timedelta

import httpx
import sentry_sdk
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.config import settings
from app.crons import Corrida, liberar_marca, reclamar_marca
from app.database import SessionLocal
from app.limites_diarios import LIMITES_DIARIOS, UsoDiario
from app.models import CorreoGasto, ExtractoCorreo, HistorialExtracto, Movimiento, Perfil
from app.models_asistente import UsoAsistente
from app.monitor import contar_5xx
from app.utiles import ahora_co

logger = logging.getLogger("app.crecimiento")

SISTEMA = "sistema"  # usuario_id de las marcas y contadores globales
ACCION_CORREO = "correo-enviado"  # contador diario de correos salidos (UsoDiario, usuario 'sistema')

# Referencias aproximadas (la cifra real siempre se confirma en el panel del proveedor).
MOVIMIENTOS_REFERENCIA = 200_000  # a este volumen Supabase Free (500 MB) empieza a apretar
ACTIVOS_7D_RAILWAY_HOBBY = 300  # usuarios activos/semana en que Railway Hobby empieza a quedarse corto

# Cada capacidad: id -> (umbrales en %, periodo de la marca). Periodo 'unico' = se avisa una sola vez
# por umbral; 'dia'/'mes' = el aviso se vuelve a armar al cambiar el día/mes (cuota que se reinicia).
UMBRALES = {
    "gmail": ([60, 80, 90, 100], "unico"),
    "base": ([60, 80, 90], "unico"),
    "resend_dia": ([80, 90, 100], "dia"),
    "resend_mes": ([60, 80, 90, 100], "mes"),
    "ia_mes": ([80, 100], "mes"),
    "movimientos": ([60, 80, 100], "unico"),
    "activos_7d": ([60, 80, 100], "unico"),
}

# Texto en lenguaje simple: qué es, qué significa pasarse y QUÉ HACER.
FICHAS = {
    "gmail": {
        "nombre": "usuarios con Gmail conectado",
        "unidad": "usuarios",
        "significa": ("Mientras Google no verifique la app, solo 100 personas pueden conectar su Gmail. "
                      "Al llegar al tope, nadie más podrá conectar su correo (lo demás de la app sigue igual)."),
        "accion": ("Inicia YA la verificación de la app en Google Cloud (Pantalla de consentimiento OAuth > "
                   "Publicar app > Enviar a verificación). Tarda semanas, por eso se avisa desde el 60 %. "
                   "Cuando Google la apruebe, pon GMAIL_MODO_PRUEBAS=false en Railway."),
    },
    "base": {
        "nombre": "la base de datos",
        "unidad": "MB",
        "significa": ("Es el espacio que ocupan todos los datos. Si se llena, Supabase deja la base en solo "
                      "lectura: nadie podría guardar movimientos."),
        "accion": ("Sube a Supabase Pro (Supabase > Settings > Billing; unos 25 USD/mes, 8 GB). Antes revisa si "
                   "alguna tabla crece de más. Después ajusta SUPABASE_DB_LIMITE_MB en Railway a 8192."),
    },
    "resend_dia": {
        "nombre": "los correos de hoy (Resend)",
        "unidad": "correos",
        "significa": ("Resend gratis deja enviar 100 correos al día. Pasado el tope, los correos del día "
                      "(resúmenes, backup, avisos) no salen hasta mañana."),
        "accion": ("Sube Resend a un plan de pago (resend.com > Billing) o reduce envíos. Si subes de plan, "
                   "actualiza RESEND_LIMITE_DIA y RESEND_LIMITE_MES en Railway."),
    },
    "resend_mes": {
        "nombre": "los correos de este mes (Resend)",
        "unidad": "correos",
        "significa": "Resend gratis deja enviar 3.000 correos al mes. Pasado el tope no salen más hasta el mes siguiente.",
        "accion": ("Sube Resend a un plan de pago (resend.com > Billing). Si subes de plan, actualiza "
                   "RESEND_LIMITE_DIA y RESEND_LIMITE_MES en Railway."),
    },
    "ia_mes": {
        "nombre": "las preguntas a la IA de este mes",
        "unidad": "preguntas",
        "significa": ("Cada pregunta al asistente cuesta dinero (OpenRouter). Es una referencia para que mires "
                      "el gasto antes de que te sorprenda."),
        "accion": ("Revisa saldo y gasto en openrouter.ai. Si el uso es sano, recarga o sube "
                   "IA_PREGUNTAS_MES_AVISO; si no, baja los topes diarios en backend/app/limites_diarios.py."),
    },
    "movimientos": {
        "nombre": "los movimientos guardados",
        "unidad": "filas",
        "significa": "Es la tabla que más crece; a este volumen la base gratuita de Supabase empieza a apretar.",
        "accion": "Mira el tamaño real en Supabase (Reports > Database) y planea subir a Supabase Pro.",
    },
    "activos_7d": {
        "nombre": "los usuarios activos esta semana",
        "unidad": "usuarios",
        "significa": "Con tantos usuarios activos, el servidor de Railway Hobby empieza a quedarse corto.",
        "accion": ("Pasa Railway a un plan de pago o más recursos. CUIDADO con más de una réplica: los límites "
                   "por hora (limites.py) y el chat viven en la memoria de cada réplica, así que cada una "
                   "contaría por su lado y los topes valdrían N veces más. Antes de escalar, hay que mover "
                   "esos contadores a la base (los topes diarios ya viven ahí)."),
    },
}


# ───────────────────────────── Mediciones ─────────────────────────────

def _seguro(db: Session, nombre: str, fn, defecto=None):
    """Una medición que falla no tumba el monitor: queda en `defecto` y se registra el tipo de error."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 - tolerante a propósito
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        logger.warning("Monitor: no se pudo medir %s (%s)", nombre, type(e).__name__)
        return defecto


def tamano_base_bytes(db: Session) -> int | None:
    """Tamaño de la base en Postgres (pg_database_size). En SQLite (local/pruebas) no aplica."""
    if db.bind.dialect.name != "postgresql":
        return None
    return int(db.execute(text("SELECT pg_database_size(current_database())")).scalar() or 0)


def registrar_correo_enviado() -> None:
    """Suma 1 al contador diario de correos salidos (para compararlo con el límite de Resend).
    Usa su propia sesión y nunca lanza: contar no puede romper un envío."""
    db = SessionLocal()
    try:
        dia = ahora_co().strftime("%Y-%m-%d")
        for _ in range(2):
            n = db.query(UsoDiario).filter(UsoDiario.usuario_id == SISTEMA, UsoDiario.accion == ACCION_CORREO,
                                           UsoDiario.dia == dia).update({UsoDiario.cantidad: UsoDiario.cantidad + 1})
            if n:
                db.commit()
                return
            try:
                db.add(UsoDiario(usuario_id=SISTEMA, accion=ACCION_CORREO, dia=dia, cantidad=1))
                db.commit()
                return
            except Exception:  # noqa: BLE001 - carrera: otra petición creó la fila; reintenta
                db.rollback()
    except Exception:  # noqa: BLE001
        logger.warning("Monitor: no se pudo contar el correo enviado", exc_info=True)
    finally:
        db.close()


def _tendencia(db: Session, ahora: datetime, dias: int = 30) -> list[dict]:
    """Usuarios nuevos por día y total acumulado en los últimos `dias`. La fecha de alta es
    `creado_en`; en perfiles antiguos (sin ella) se estima con su primer movimiento."""
    primero = dict(db.query(Movimiento.usuario_id, func.min(Movimiento.fecha)).group_by(Movimiento.usuario_id).all())
    alta: list[datetime | None] = []
    for uid, creado in db.query(Perfil.usuario_id, Perfil.creado_en).all():
        alta.append(creado or primero.get(uid))  # None = sin fecha conocida: cuenta como «de antes»
    inicio = (ahora - timedelta(days=dias - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    antes = sum(1 for a in alta if a is None or a < inicio)
    por_dia: dict[str, int] = {}
    for a in alta:
        if a is not None and a >= inicio:
            k = a.strftime("%Y-%m-%d")
            por_dia[k] = por_dia.get(k, 0) + 1
    serie, total = [], antes
    for i in range(dias):
        k = (inicio + timedelta(days=i)).strftime("%Y-%m-%d")
        total += por_dia.get(k, 0)
        serie.append({"dia": k, "nuevos": por_dia.get(k, 0), "total": total})
    return serie


def recopilar(db: Session, ahora: datetime | None = None) -> dict:
    ahora = ahora or ahora_co()
    hoy = ahora.strftime("%Y-%m-%d")
    mes = ahora.strftime("%Y-%m")
    d7 = (ahora - timedelta(days=7)).strftime("%Y-%m-%d")
    d30 = (ahora - timedelta(days=30)).strftime("%Y-%m-%d")

    def activos(desde: datetime, desde_txt: str) -> int:
        con_mov = {u for (u,) in db.query(Movimiento.usuario_id).filter(Movimiento.fecha >= desde).distinct()}
        con_uso = {u for (u,) in db.query(UsoDiario.usuario_id).filter(
            UsoDiario.dia >= desde_txt, UsoDiario.usuario_id != SISTEMA, UsoDiario.accion != ACCION_CORREO).distinct()}
        return len(con_mov | con_uso)

    def correos_hoy() -> int:
        return db.query(func.coalesce(func.sum(UsoDiario.cantidad), 0)).filter(
            UsoDiario.usuario_id == SISTEMA, UsoDiario.accion == ACCION_CORREO, UsoDiario.dia == hoy).scalar() or 0

    def correos_mes() -> int:
        return db.query(func.coalesce(func.sum(UsoDiario.cantidad), 0)).filter(
            UsoDiario.usuario_id == SISTEMA, UsoDiario.accion == ACCION_CORREO,
            UsoDiario.dia >= f"{mes}-01").scalar() or 0

    def ia_mes() -> int:
        a = db.query(func.coalesce(func.sum(UsoAsistente.cantidad), 0)).filter(UsoAsistente.dia >= f"{mes}-01").scalar() or 0
        b = db.query(func.coalesce(func.sum(UsoDiario.cantidad), 0)).filter(
            UsoDiario.accion == "preguntar", UsoDiario.dia >= f"{mes}-01").scalar() or 0
        return int(a) + int(b)

    def usuarios_en_tope() -> int:
        """Usuarios que agotaron algún tope diario en los últimos 7 días."""
        n = set()
        for accion, (tope, _nombre) in LIMITES_DIARIOS.items():
            n |= {u for (u,) in db.query(UsoDiario.usuario_id).filter(
                UsoDiario.accion == accion, UsoDiario.dia >= d7, UsoDiario.cantidad >= tope).distinct()}
        return len(n)

    db_bytes = _seguro(db, "tamaño de la base", lambda: tamano_base_bytes(db))
    limite_mb = max(1, settings.supabase_db_limite_mb)
    return {
        "generado_en": ahora.isoformat(timespec="seconds"),
        "usuarios_total": _seguro(db, "usuarios", lambda: db.query(func.count(Perfil.usuario_id)).scalar() or 0),
        "activos_7d": _seguro(db, "activos 7d", lambda: activos(ahora - timedelta(days=7), d7)),
        "activos_30d": _seguro(db, "activos 30d", lambda: activos(ahora - timedelta(days=30), d30)),
        "nuevos_7d": _seguro(db, "nuevos 7d", lambda: sum(p["nuevos"] for p in _tendencia(db, ahora)[-7:])),
        "nuevos_30d": _seguro(db, "nuevos 30d", lambda: sum(p["nuevos"] for p in _tendencia(db, ahora))),
        "gmail": _seguro(db, "gmail", lambda: db.query(func.count(Perfil.usuario_id)).filter(Perfil.gmail_conectado.is_(True)).scalar() or 0),
        "base_mb": None if db_bytes is None else round(db_bytes / 1_048_576, 1),
        "base_limite_mb": limite_mb,
        "movimientos": _seguro(db, "movimientos", lambda: db.query(func.count(Movimiento.id)).scalar() or 0),
        "correos_procesados": _seguro(db, "correos", lambda: db.query(func.count(CorreoGasto.id)).scalar() or 0),
        "extractos_procesados": _seguro(db, "extractos", lambda: (
            (db.query(func.count(ExtractoCorreo.id)).filter(ExtractoCorreo.estado == "procesado").scalar() or 0)
            + (db.query(func.count(HistorialExtracto.id)).scalar() or 0))),
        "ia_mes": _seguro(db, "IA", ia_mes),
        "resend_dia": _seguro(db, "correos de hoy", correos_hoy),
        "resend_mes": _seguro(db, "correos del mes", correos_mes),
        "errores_5xx_24h": contar_5xx(24),
        "usuarios_en_tope_7d": _seguro(db, "topes diarios", usuarios_en_tope),
        "tendencia": _seguro(db, "tendencia", lambda: _tendencia(db, ahora), []),
        "dia": hoy,
        "mes": mes,
        "semana": f"{ahora.isocalendar()[0]}-W{ahora.isocalendar()[1]:02d}",
    }


def nivel_de(pct: float | None) -> str:
    if pct is None:
        return "sin_dato"
    if pct >= 90:
        return "critico"
    if pct >= 80:
        return "alto"
    if pct >= 60:
        return "atencion"
    return "ok"


def capacidades(m: dict) -> list[dict]:
    """Cada recurso con límite: cuánto llevamos, qué % es y qué hacer."""
    pares = [
        ("gmail", m["gmail"], settings.gmail_tope_usuarios),
        ("base", m["base_mb"], m["base_limite_mb"]),
        ("resend_dia", m["resend_dia"], settings.resend_limite_dia),
        ("resend_mes", m["resend_mes"], settings.resend_limite_mes),
        ("ia_mes", m["ia_mes"], settings.ia_preguntas_mes_aviso),
        ("movimientos", m["movimientos"], MOVIMIENTOS_REFERENCIA),
        ("activos_7d", m["activos_7d"], ACTIVOS_7D_RAILWAY_HOBBY),
    ]
    salida = []
    for cid, actual, limite in pares:
        ficha = FICHAS[cid]
        pct = None if actual is None or not limite else round(actual * 100 / limite, 1)
        salida.append({
            "id": cid, "nombre": ficha["nombre"], "unidad": ficha["unidad"], "actual": actual, "limite": limite,
            "pct": pct, "nivel": nivel_de(pct), "significa": ficha["significa"], "accion": ficha["accion"],
            "umbrales": UMBRALES[cid][0],
        })
    return salida


def senales(m: dict) -> list[dict]:
    """Señales sin barra de capacidad: errores del servidor y usuarios que tocan los topes diarios."""
    errores, tope = m["errores_5xx_24h"], settings.errores_5xx_aviso
    en_tope = m["usuarios_en_tope_7d"]
    return [
        {"id": "errores_5xx", "nombre": "errores del servidor (últimas 24 h)", "actual": errores,
         "alerta": errores >= tope,
         "significa": "Respuestas 5xx contadas en este servidor (se reinicia en cada despliegue).",
         "accion": "Abre Sentry y los logs de Railway para ver qué falla; si es falta de memoria o CPU, sube el plan de Railway."},
        {"id": "topes_diarios", "nombre": "usuarios que tocaron un tope diario (7 días)", "actual": en_tope,
         "alerta": bool(en_tope and en_tope >= 3),
         "significa": "Alguien gastó todo su cupo diario (IA, extractos, facturas...). Puede ser abuso o que necesita un plan mayor.",
         "accion": "Revisa si es un usuario real que necesita más (¿plan de pago?) o un abuso; los topes están en backend/app/limites_diarios.py."},
    ]


# ───────────────────────────── Avisos ─────────────────────────────

def _periodo(tipo: str, m: dict) -> str:
    return {"unico": "unico", "dia": m["dia"], "mes": m["mes"]}[tipo]


def umbrales_cruzados(c: dict) -> list[int]:
    if c["pct"] is None:
        return []
    return [u for u in c["umbrales"] if c["pct"] >= u]


def _texto_aviso(c: dict, umbral: int) -> tuple[str, str]:
    asunto = f"CuadraMe: llegaste al {umbral} % de {c['nombre']}"
    actual = c["actual"]
    actual_txt = f"{actual:g}" if isinstance(actual, float) else f"{actual}"
    cuerpo = (f"Llevas {actual_txt} de {c['limite']} {c['unidad']} ({c['pct']:g} %).\n\n"
              f"QUÉ SIGNIFICA\n{c['significa']}\n\nQUÉ HACER\n{c['accion']}")
    return asunto, cuerpo


def destino_admin() -> str:
    """ADMIN_EMAIL. Sin él, los avisos solo quedan en el log (no se adivina un destinatario)."""
    return (settings.admin_email or "").strip()


def _enviar(destino: str, asunto: str, texto: str) -> None:
    """Resend. Lanza si falla (para que el cron libere las marcas y reintente mañana)."""
    r = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={"from": settings.resend_from, "to": [destino], "subject": asunto, "text": texto},
        timeout=20,
    )
    r.raise_for_status()
    registrar_correo_enviado()


def _a_sentry(mensaje: str, nivel: str) -> None:
    """Mensaje genérico, sin datos personales. Sin SENTRY_DSN el SDK no hace nada."""
    try:
        sentry_sdk.capture_message(mensaje, level=nivel)
    except Exception:  # noqa: BLE001
        logger.warning("Monitor: no se pudo registrar en Sentry", exc_info=True)


def procesar_avisos(db: Session, ahora: datetime | None = None) -> dict:
    """Cron diario. Por cada recurso, avisa UNA vez cada umbral (60/80/90/100...); si en una corrida
    se cruzan varios, solo se manda el más alto. Todo va en un solo correo."""
    ahora = ahora or ahora_co()
    m = recopilar(db, ahora)
    corrida = Corrida(db)
    pendientes: list[tuple[dict, int, str]] = []  # (capacidad, umbral, clave)

    for c in capacidades(m):
        with corrida.aislar(c["id"]):
            nuevos = []
            for u in umbrales_cruzados(c):
                clave = f"crec:{c['id']}:{u}"
                if reclamar_marca(db, SISTEMA, clave, _periodo(UMBRALES[c["id"]][1], m)):
                    nuevos.append((u, clave))
            if nuevos:
                # Se reclaman todos los cruzados (para no mandar el 60 mañana si hoy ya se mandó el 80),
                # pero solo se avisa el más alto.
                pendientes.append((c, nuevos[-1][0], [k for _, k in nuevos]))

    señales_nuevas = []
    for s in senales(m):
        with corrida.aislar(s["id"]):
            if s["alerta"] and reclamar_marca(db, SISTEMA, f"crec:senal:{s['id']}", m["dia"] if s["id"] == "errores_5xx" else m["semana"]):
                señales_nuevas.append(s)

    avisos = [{"id": c["id"], "umbral": u, "pct": c["pct"]} for c, u, _ in pendientes]
    avisos += [{"id": s["id"], "actual": s["actual"]} for s in señales_nuevas]

    enviado = False
    error = None
    if avisos:
        cuerpos, asuntos = [], []
        for c, u, _claves in pendientes:
            a, cu = _texto_aviso(c, u)
            asuntos.append(a)
            cuerpos.append(cu)
            _a_sentry(f"Capacidad: {c['id']} alcanzó el {u} % del límite", "warning" if u >= 80 else "info")
        for s in señales_nuevas:
            asuntos.append(f"CuadraMe: {s['nombre']}")
            cuerpos.append(f"{s['nombre'].capitalize()}: {s['actual']}.\n\nQUÉ SIGNIFICA\n{s['significa']}\n\nQUÉ HACER\n{s['accion']}")
            _a_sentry(f"Señal de uso: {s['id']} = {s['actual']}", "warning")
        asunto = asuntos[0] if len(asuntos) == 1 else f"CuadraMe: {len(asuntos)} avisos de capacidad ({asuntos[0].removeprefix('CuadraMe: ')}, ...)"
        texto = "\n\n────────────\n\n".join(cuerpos) + "\n\n—\nPanel: CuadraMe > Más > Salud del negocio."
        destino = destino_admin()
        if not destino:
            logger.warning("Monitor: hay avisos de capacidad pero ADMIN_EMAIL no está configurado. %s", asuntos)
        elif not settings.resend_api_key:
            logger.warning("Monitor: hay avisos de capacidad pero RESEND_API_KEY no está configurada. %s", asuntos)
        else:
            try:
                _enviar(destino, asunto, texto)
                enviado = True
            except Exception as e:  # noqa: BLE001 - se libera para reintentar en la próxima corrida
                error = type(e).__name__
                logger.warning("Monitor: no se pudo enviar el aviso (%s); se reintentará", error)
                for _c, _u, claves in pendientes:
                    for k in claves:
                        liberar_marca(db, SISTEMA, k)
                for s in señales_nuevas:
                    liberar_marca(db, SISTEMA, f"crec:senal:{s['id']}")
                corrida.fallidos += 1

    resumen = _resumen_semanal(db, m, ahora)
    return {"ok": error is None, "enviado": enviado, "avisos": avisos, "resumen_semanal": resumen,
            "error": error, **corrida.resumen()}


def _resumen_semanal(db: Session, m: dict, ahora: datetime) -> str:
    """Los lunes (hora Colombia) manda el resumen de crecimiento. Devuelve: 'enviado', 'no_toca',
    'ya_enviado', 'sin_destino' o 'error'."""
    if ahora.weekday() != 0:
        return "no_toca"
    if not destino_admin() or not settings.resend_api_key:
        logger.warning("Monitor: resumen semanal no enviado (falta ADMIN_EMAIL o RESEND_API_KEY)")
        return "sin_destino"
    clave = "crec:resumen-semanal"
    if not reclamar_marca(db, SISTEMA, clave, m["semana"]):
        return "ya_enviado"
    caps = {c["id"]: c for c in capacidades(m)}
    base = caps["base"]
    base_txt = "sin dato" if base["pct"] is None else f"{base['pct']:g} % ({base['actual']:g} de {base['limite']} MB)"
    texto = (
        "Resumen semanal de crecimiento de CuadraMe\n\n"
        f"Usuarios registrados: {m['usuarios_total']}\n"
        f"Nuevos esta semana: {m['nuevos_7d']}  (últimos 30 días: {m['nuevos_30d']})\n"
        f"Activos 7 días: {m['activos_7d']}  |  30 días: {m['activos_30d']}\n"
        f"Gmail conectado: {m['gmail']} de {settings.gmail_tope_usuarios}\n"
        f"Base de datos: {base_txt}\n"
        f"Movimientos: {m['movimientos']}\n"
        f"Preguntas a la IA este mes: {m['ia_mes']}\n\n"
        "Detalle y barras: CuadraMe > Más > Salud del negocio."
    )
    try:
        _enviar(destino_admin(), "CuadraMe: resumen semanal de crecimiento", texto)
    except Exception as e:  # noqa: BLE001
        logger.warning("Monitor: no se pudo enviar el resumen semanal (%s)", type(e).__name__)
        liberar_marca(db, SISTEMA, clave)
        return "error"
    _a_sentry(f"Resumen semanal: {m['usuarios_total']} usuarios, {m['nuevos_7d']} nuevos", "info")
    return "enviado"


# ───────────────────────────── Panel ─────────────────────────────

def es_admin(email: str | None) -> bool:
    admin = destino_admin().lower()
    return bool(admin) and (email or "").strip().lower() == admin


def armar_panel(db: Session) -> dict:
    m = recopilar(db)
    return {
        "generado_en": m["generado_en"],
        "usuarios": {k: m[k] for k in ("usuarios_total", "activos_7d", "activos_30d", "nuevos_7d", "nuevos_30d")},
        "capacidades": capacidades(m),
        "senales": senales(m),
        "volumen": {k: m[k] for k in ("movimientos", "correos_procesados", "extractos_procesados", "ia_mes")},
        "tendencia": m["tendencia"],
    }
