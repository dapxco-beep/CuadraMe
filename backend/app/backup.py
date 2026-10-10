"""
Respaldo diario de la base de datos: JSON comprimido y CIFRADO (AES-256-GCM, clave derivada de
BACKUP_PASSPHRASE con PBKDF2) enviado por correo. Existe porque el plan Free de Supabase no
incluye backups automáticos.

Qué NO viaja nunca (ni siquiera cifrado), por la política de «Uso Limitado» de Google y la
Ley 1581:
- contenido leído de Gmail: asuntos, remitentes, fragmentos, adjuntos (tablas correos_gastos,
  extractos_correo, historial_extractos) y el estado de la sincronización (sync_gmail);
- credenciales: tokens de Gmail, claves de PDF, claves del Atajo (en claro, hash y prefijo)
  y suscripciones push.
Sin BACKUP_PASSPHRASE el respaldo NO se envía (ver enviar_backup_por_correo).
Cómo descifrarlo y restaurarlo: docs/RESTAURAR_RESPALDO.md y backend/tools/descifrar_respaldo.py.
"""
import base64
import gzip
import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import inspect

from app.config import settings
from app.database import Base, engine

logger = logging.getLogger(__name__)

# Formato del archivo cifrado: MAGIC | sal(16) | nonce(12) | AES-GCM(gzip(json)).
# MAGIC viaja como dato autenticado (AAD): si alguien lo cambia, no descifra.
MAGIC = b"CMBK1"
ITERACIONES = 600_000
EXTENSION = ".cmbk"

# Tablas completas que no se respaldan.
TABLAS_NO_RESPALDADAS = {
    "correos_gastos",       # asunto, remitente y fragmento de correos leídos
    "extractos_correo",     # asunto, remitente y nombre de adjuntos de Gmail
    "historial_extractos",  # foto de las líneas de extractos (pudieron venir de Gmail)
    "sync_gmail",           # estado/cursores de la lectura de Gmail
    "claves_pdf",           # claves de PDF (cifradas, pero nunca viajan)
    "push_subscriptions",   # endpoint y llaves de notificaciones push
}
# Columnas que se quitan de cualquier tabla.
COLUMNAS_NO_RESPALDADAS = {
    "api_key", "api_key_hash", "api_key_prefijo",   # claves del Atajo
    "gmail_refresh_token_enc", "gmail_email",       # acceso a Gmail
    "clave_enc",
    "asunto", "snippet", "remitente",               # texto de correos (por si aparece en otra tabla)
    "endpoint", "p256dh", "auth",                   # push
}
# Red de seguridad: una columna futura con estos fragmentos en el nombre tampoco viaja.
_FRAGMENTOS_PROHIBIDOS = ("token", "secret", "password", "api_key", "refresh", "cuerpo", "snippet")


def columna_respaldable(nombre: str) -> bool:
    n = nombre.lower()
    return n not in COLUMNAS_NO_RESPALDADAS and not any(f in n for f in _FRAGMENTOS_PROHIBIDOS)


def derivar_clave(frase: str, sal: bytes, iteraciones: int = ITERACIONES) -> bytes:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sal, iterations=iteraciones).derive(frase.encode("utf-8"))


def cifrar_respaldo(datos: bytes, frase: str) -> bytes:
    """AES-256-GCM con clave PBKDF2(frase, sal aleatoria). Sin frase no se cifra: se rechaza."""
    if not frase:
        raise ValueError("Falta la frase de cifrado")
    sal, nonce = os.urandom(16), os.urandom(12)
    cifrado = AESGCM(derivar_clave(frase, sal)).encrypt(nonce, datos, MAGIC)
    return MAGIC + sal + nonce + cifrado


def descifrar_respaldo(blob: bytes, frase: str) -> bytes:
    """Inversa de cifrar_respaldo. Lanza ValueError si la frase es incorrecta o el archivo se alteró."""
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 16 + 12 + 16:
        raise ValueError("No es un respaldo de CuadraMe (formato desconocido)")
    sal = blob[len(MAGIC):len(MAGIC) + 16]
    nonce = blob[len(MAGIC) + 16:len(MAGIC) + 28]
    cuerpo = blob[len(MAGIC) + 28:]
    try:
        return AESGCM(derivar_clave(frase, sal)).decrypt(nonce, cuerpo, MAGIC)
    except Exception as e:  # InvalidTag
        raise ValueError("Frase incorrecta o archivo alterado") from e


def _serializable(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def exportar_base_de_datos() -> bytes:
    """Recorre TODAS las tablas registradas en los modelos (Base.metadata), no una lista fija:
    una tabla nueva queda incluida sin acordarse de actualizar este archivo. Lo sensible se quita
    por TABLAS_NO_RESPALDADAS / columna_respaldable. Devuelve JSON comprimido (gzip), SIN cifrar:
    quien lo envíe debe pasarlo por cifrar_respaldo."""
    inspector = inspect(engine)
    tablas_en_bd = set(inspector.get_table_names())
    data: dict[str, list[dict]] = {}

    with engine.connect() as conn:
        for nombre_tabla, tabla in Base.metadata.tables.items():
            if nombre_tabla not in tablas_en_bd or nombre_tabla in TABLAS_NO_RESPALDADAS:
                continue
            filas = conn.execute(tabla.select()).mappings().all()
            data[nombre_tabla] = [
                {k: _serializable(v) for k, v in dict(fila).items() if columna_respaldable(k)}
                for fila in filas
            ]

    payload = json.dumps(
        {"exportado_en": datetime.utcnow().isoformat(), "tablas": data},
        ensure_ascii=False,
    ).encode("utf-8")
    return gzip.compress(payload)


def _avisar_falta_frase() -> None:
    """Deja constancia visible para el administrador (una vez al día) de qué hacer."""
    try:
        from app import avisos
        from app.utiles import ahora_co

        avisos.registrar_evento(
            "respaldo_sin_cifrar", clave_unica=f"respaldo_sin_clave:{ahora_co().strftime('%Y-%m-%d')}",
            texto="El respaldo diario NO se envió: define BACKUP_PASSPHRASE en Railway")
    except Exception:  # noqa: BLE001
        logger.warning("backup: no se pudo registrar el aviso al administrador", exc_info=True)


def enviar_backup_por_correo() -> dict:
    if not settings.resend_api_key:
        logger.warning("backup: RESEND_API_KEY no configurada, no se pudo enviar el backup")
        return {"ok": False, "error": "Resend no configurado"}
    if not settings.backup_passphrase:
        # Nunca se manda la base sin cifrar por correo.
        logger.warning(
            "backup: BACKUP_PASSPHRASE no está definida; el respaldo diario NO se envía. "
            "Acción: define BACKUP_PASSPHRASE (una frase larga y única) en las variables de Railway.")
        _avisar_falta_frase()
        return {"ok": False, "sin_frase": True,
                "error": "Falta BACKUP_PASSPHRASE: el respaldo no se envía sin cifrar"}

    contenido = cifrar_respaldo(exportar_base_de_datos(), settings.backup_passphrase)
    fecha_hoy = datetime.utcnow().strftime("%Y-%m-%d")
    nombre_archivo = f"cuadrame_backup_{fecha_hoy}{EXTENSION}"

    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": settings.resend_from,
            "to": [settings.backup_email],
            "subject": f"CuadraMe — backup del {fecha_hoy}",
            "text": (
                f"Backup automático de la base de datos de CuadraMe, generado el {fecha_hoy}.\n\n"
                "Está CIFRADO (AES-256-GCM): sin la frase BACKUP_PASSPHRASE no se puede abrir. "
                "No incluye correos leídos, tokens, claves de PDF ni claves del Atajo. "
                "Para restaurar sigue docs/RESTAURAR_RESPALDO.md."
            ),
            "attachments": [
                {
                    "filename": nombre_archivo,
                    "content": base64.b64encode(contenido).decode("ascii"),
                }
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    from app.crecimiento import registrar_correo_enviado  # cuenta el envío para el monitor de Resend
    registrar_correo_enviado()
    return {"ok": True, "bytes": len(contenido), "cifrado": True}
