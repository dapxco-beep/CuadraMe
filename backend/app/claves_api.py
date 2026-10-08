"""
Clave API del Atajo/dispositivo, guardada como hash SHA-256.

Decisiones:
- La clave nace con 24 bytes aleatorios (192 bits): con tanta entropía basta un
  SHA-256 simple (sin sal ni "stretching" lento, que sirven para contraseñas que
  una persona puede adivinar). Así además se puede buscar por el hash con índice.
- Se muestra completa SOLO al crearla o regenerarla. Después solo queda el
  hash y un prefijo corto ("cdm_ab12…") para que el usuario reconozca cuál es.
- La comparación final usa hmac.compare_digest (tiempo constante).
- Compatibilidad: las claves antiguas siguen en claro en `perfiles.api_key`.
  Siguen funcionando y, al usarse por primera vez, se migran solas a hash
  (se borra el texto en claro). No hay migración manual.
- Tolerancia: si la columna `api_key_hash` aún no existe en la base (el script
  supabase/migraciones/api_key_hash.sql no se ha corrido), todo funciona como
  antes, en claro. `hay_columna_hash` lo detecta sin romper el arranque.
"""
import hashlib
import hmac
import logging

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models import Perfil, gen_api_key

logger = logging.getLogger(__name__)

PREFIJO_LARGO = 8  # "cdm_" + 4 caracteres

_columna_ok: dict[int, bool] = {}


def hash_clave(clave: str) -> str:
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()


def prefijo_clave(clave: str) -> str:
    return clave[:PREFIJO_LARGO] + "…"


def hay_columna_hash(db: Session) -> bool:
    """True si la tabla perfiles ya tiene api_key_hash. Solo cachea el "sí"
    (si falta, se vuelve a mirar, porque el script puede correrse en caliente)."""
    motor = db.get_bind()
    if _columna_ok.get(id(motor)):
        return True
    try:
        columnas = {c["name"] for c in inspect(motor).get_columns("perfiles")}
    except Exception:  # noqa: BLE001 - mejor degradar a modo antiguo que tumbar la petición
        logger.warning("No se pudo inspeccionar perfiles; se asume sin api_key_hash", exc_info=True)
        return False
    ok = "api_key_hash" in columnas
    if ok:
        _columna_ok[id(motor)] = True
    return ok


def tiene_clave(db: Session, perfil: Perfil) -> bool:
    if perfil.api_key:
        return True
    return hay_columna_hash(db) and bool(perfil.api_key_hash)


def asignar_clave_nueva(db: Session, perfil: Perfil) -> str:
    """Crea una clave nueva, la guarda (hash si se puede) y devuelve el texto
    completo: es la única vez que existe fuera del dispositivo del usuario."""
    clave = gen_api_key()
    if hay_columna_hash(db):
        perfil.api_key = None
        perfil.api_key_hash = hash_clave(clave)
        perfil.api_key_prefijo = prefijo_clave(clave)
    else:
        perfil.api_key = clave
    perfil.api_key_ultimo_uso = None
    db.commit()
    return clave


def buscar_perfil_por_clave(db: Session, clave: str) -> Perfil | None:
    """Perfil dueño de la clave o None. Migra a hash las claves antiguas en claro."""
    if not clave:
        return None
    con_hash = hay_columna_hash(db)
    if con_hash:
        h = hash_clave(clave)
        perfil = db.query(Perfil).filter(Perfil.api_key_hash == h).first()
        if perfil and perfil.api_key_hash and hmac.compare_digest(perfil.api_key_hash, h):
            return perfil
    # Camino antiguo: clave en claro.
    perfil = db.query(Perfil).filter(Perfil.api_key == clave).first()
    if perfil and perfil.api_key and hmac.compare_digest(perfil.api_key.encode(), clave.encode()):
        if con_hash:
            perfil.api_key_hash = hash_clave(clave)
            perfil.api_key_prefijo = prefijo_clave(clave)
            perfil.api_key = None
            db.commit()
        return perfil
    return None
