"""
Backup diario de la base de datos completa a un archivo JSON comprimido,
enviado por correo a dapxco@gmail.com. Existe porque el plan Free de
Supabase no incluye backups automáticos — este es el respaldo propio
mínimo mientras el proyecto no pase a un plan con backups nativos.
"""
import base64
import gzip
import json
import logging
from datetime import date, datetime
from decimal import Decimal

import httpx
from sqlalchemy import inspect

from app.config import settings
from app.database import Base, engine

logger = logging.getLogger(__name__)


# La clave del Atajo antigua estaba en claro: no debe viajar por correo (el hash sí; sirve para restaurar).
COLUMNAS_NO_RESPALDADAS = {"api_key"}


def _serializable(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def exportar_base_de_datos() -> bytes:
    """Recorre TODAS las tablas registradas en los modelos (Base.metadata),
    no una lista fija — así una tabla nueva que se agregue después queda
    incluida en el backup sin tener que acordarse de actualizar este archivo."""
    inspector = inspect(engine)
    tablas_en_bd = set(inspector.get_table_names())
    data: dict[str, list[dict]] = {}

    with engine.connect() as conn:
        for nombre_tabla, tabla in Base.metadata.tables.items():
            if nombre_tabla not in tablas_en_bd or nombre_tabla == "claves_pdf":  # las claves nunca viajan por correo
                continue
            filas = conn.execute(tabla.select()).mappings().all()
            data[nombre_tabla] = [
                {k: _serializable(v) for k, v in dict(fila).items() if k not in COLUMNAS_NO_RESPALDADAS}
                for fila in filas
            ]

    payload = json.dumps(
        {"exportado_en": datetime.utcnow().isoformat(), "tablas": data},
        ensure_ascii=False,
    ).encode("utf-8")
    return gzip.compress(payload)


def enviar_backup_por_correo() -> dict:
    if not settings.resend_api_key:
        logger.warning("backup: RESEND_API_KEY no configurada, no se pudo enviar el backup")
        return {"ok": False, "error": "Resend no configurado"}

    contenido_gz = exportar_base_de_datos()
    fecha_hoy = datetime.utcnow().strftime("%Y-%m-%d")
    nombre_archivo = f"cuadrame_backup_{fecha_hoy}.json.gz"

    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": settings.resend_from,
            "to": [settings.backup_email],
            "subject": f"CuadraMe — backup del {fecha_hoy}",
            "text": (
                f"Backup automático de la base de datos de CuadraMe, generado el {fecha_hoy}.\n\n"
                "Es un archivo JSON comprimido (.json.gz) con todas las tablas. "
                "Guárdalo en un lugar seguro; no hace falta abrirlo salvo que necesites "
                "restaurar datos."
            ),
            "attachments": [
                {
                    "filename": nombre_archivo,
                    "content": base64.b64encode(contenido_gz).decode("ascii"),
                }
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return {"ok": True, "bytes": len(contenido_gz)}
