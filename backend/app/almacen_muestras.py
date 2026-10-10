"""Almacenamiento PRIVADO de archivos de muestra («Mi banco no aparece»).

Los archivos van a un bucket PRIVADO de Supabase Storage (sin URL pública: ni siquiera con el enlace
se puede abrir). Solo el servidor los toca, con la llave de servicio, y solo para tres cosas: guardar lo
que sube la persona, entregárselo a la administración y borrarlo (la persona puede borrarlo cuando quiera).

Si no hay llave de servicio configurada, `disponible()` es False y el buzón guarda solo el nombre del banco.
Las pruebas reemplazan `_cliente_http` o las funciones públicas: nunca se llama a la red real."""
import logging
import re
import unicodedata

import httpx

from app.config import settings

logger = logging.getLogger("app.almacen_muestras")

BUCKET = "muestras-bancos"
MAX_BYTES = 5 * 1024 * 1024
EXTENSIONES = {"pdf", "xls", "xlsx", "csv"}
TIMEOUT = 20.0


class AlmacenNoDisponible(Exception):
    """No hay almacenamiento configurado o respondió con error."""


def disponible() -> bool:
    return bool(settings.supabase_service_role_key and settings.supabase_url)


def extension_de(nombre: str) -> str:
    return nombre.rsplit(".", 1)[-1].lower() if "." in (nombre or "") else ""


def nombre_seguro(nombre: str) -> str:
    """Solo letras, números, punto, guion y guion bajo; sin rutas; máximo 80 caracteres; conserva la extensión."""
    base = unicodedata.normalize("NFKD", str(nombre or "")).encode("ascii", "ignore").decode()
    base = base.replace("\\", "/").split("/")[-1]
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "muestra"
    if len(base) > 80:
        ext = extension_de(base)
        base = base[: 80 - len(ext) - 1] + "." + ext if ext else base[:80]
    return base


def contenido_valido(extension: str, datos: bytes) -> bool:
    """Revisa que el contenido corresponda a la extensión (el tipo que declara el navegador no es de fiar)."""
    if not datos:
        return False
    if extension == "pdf":
        return datos[:5] == b"%PDF-"
    if extension == "xlsx":
        return datos[:4] == b"PK\x03\x04"
    if extension == "xls":
        return datos[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    if extension == "csv":
        if b"\x00" in datos[:4096]:
            return False
        try:
            datos[:65536].decode("utf-8")
        except UnicodeDecodeError:
            try:
                datos[:65536].decode("latin-1")
            except UnicodeDecodeError:
                return False
        return True
    return False


def _cabeceras() -> dict:
    llave = settings.supabase_service_role_key
    return {"Authorization": f"Bearer {llave}", "apikey": llave}


def _url(ruta: str = "") -> str:
    return f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{BUCKET}/{ruta}".rstrip("/")


def _asegurar_bucket(cliente: httpx.Client) -> None:
    """Crea el bucket PRIVADO si no existe (idempotente: si ya existe responde 4xx y se ignora)."""
    cliente.post(
        f"{settings.supabase_url.rstrip('/')}/storage/v1/bucket",
        headers=_cabeceras(), json={"id": BUCKET, "name": BUCKET, "public": False},
    )


def guardar(ruta: str, datos: bytes, tipo_mime: str = "application/octet-stream") -> None:
    if not disponible():
        raise AlmacenNoDisponible("sin almacenamiento configurado")
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            cab = {**_cabeceras(), "Content-Type": tipo_mime, "x-upsert": "true"}
            r = c.post(_url(ruta), headers=cab, content=datos)
            if r.status_code in (400, 404):  # el bucket aún no existe
                _asegurar_bucket(c)
                r = c.post(_url(ruta), headers=cab, content=datos)
            if r.status_code >= 300:
                raise AlmacenNoDisponible(f"almacenamiento respondió {r.status_code}")
    except httpx.HTTPError as e:
        raise AlmacenNoDisponible(str(e)) from e


def leer(ruta: str) -> bytes:
    if not disponible():
        raise AlmacenNoDisponible("sin almacenamiento configurado")
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(_url(ruta), headers=_cabeceras())
    except httpx.HTTPError as e:
        raise AlmacenNoDisponible(str(e)) from e
    if r.status_code >= 300:
        raise AlmacenNoDisponible(f"almacenamiento respondió {r.status_code}")
    return r.content


def borrar(ruta: str) -> bool:
    """Borra un archivo. True si quedó borrado (o ya no existía). Nunca lanza."""
    if not ruta or not disponible():
        return False
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.delete(_url(ruta), headers=_cabeceras())
        return r.status_code < 300 or r.status_code == 404
    except httpx.HTTPError:
        logger.warning("Almacén de muestras: no se pudo borrar un archivo", exc_info=True)
        return False
