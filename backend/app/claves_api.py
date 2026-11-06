"""
Clave API del Atajo/dispositivo, guardada como hash SHA-256.

Decisiones:
- La clave nace con 24 bytes aleatorios (192 bits): con tanta entropía basta un
  SHA-256 simple (sin sal ni "stretching" lento, que sirven para contraseñas que
  una persona puede adivinar). Así además se puede buscar por el hash con índice.
- El acceso por API se verifica SIEMPRE con el hash. Además la clave se guarda cifrada (Fernet, `api_key_enc`)
  solo para que su dueño pueda volver a verla en la app con su sesión; las claves creadas antes de esa columna
  (solo hash) no se pueden mostrar: se genera una nueva una vez.
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


_columna_enc_ok: dict[int, bool] = {}


def hay_columna_enc(db: Session) -> bool:
    """True si perfiles ya tiene api_key_enc (la migración 0014 corre al arrancar). Solo cachea el «sí»."""
    motor = db.get_bind()
    if _columna_enc_ok.get(id(motor)):
        return True
    try:
        columnas = {c["name"] for c in inspect(motor).get_columns("perfiles")}
    except Exception:  # noqa: BLE001
        return False
    ok = "api_key_enc" in columnas
    if ok:
        _columna_enc_ok[id(motor)] = True
    return ok


def clave_visible(db: Session, perfil: Perfil) -> str | None:
    """La clave en claro para su dueño, si se guardó cifrada. None si no (clave anterior a esta función o
    cifrado ilegible): entonces solo se puede generar una nueva."""
    if not hay_columna_enc(db) or not perfil.api_key_enc:
        return None
    from app.gmail_oauth import descifrar

    try:
        return descifrar(perfil.api_key_enc)
    except Exception:  # noqa: BLE001 - p.ej. se rotó FERNET_KEY: no se puede leer, pero tampoco debe tumbar nada
        logger.warning("No se pudo descifrar api_key_enc", exc_info=True)
        return None


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
        if hay_columna_enc(db):
            from app.gmail_oauth import cifrar

            try:
                perfil.api_key_enc = cifrar(clave)
            except Exception:  # noqa: BLE001 - sin llave de cifrado válida igual se crea la clave (solo no se podrá ver luego)
                perfil.api_key_enc = None
                logger.warning("No se pudo cifrar la clave API", exc_info=True)
    else:
        perfil.api_key = clave
    perfil.api_key_ultimo_uso = None
    db.commit()
    return clave


def _recordar_cifrada(db: Session, perfil: Perfil, clave: str, confirmar: bool = True) -> None:
    """Quien usa la clave (el Atajo) la acaba de presentar completa: si aún no está guardada cifrada, se guarda para que
    su dueño pueda verla en la app SIN tener que generar otra. Mejor esfuerzo: nunca debe tumbar la autenticación."""
    try:
        if hay_columna_enc(db) and not perfil.api_key_enc:
            from app.gmail_oauth import cifrar

            perfil.api_key_enc = cifrar(clave)
            if confirmar:
                db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.warning("No se pudo guardar api_key_enc", exc_info=True)


def buscar_perfil_por_clave(db: Session, clave: str) -> Perfil | None:
    """Perfil dueño de la clave o None. Migra a hash las claves antiguas en claro."""
    if not clave:
        return None
    con_hash = hay_columna_hash(db)
    if con_hash:
        h = hash_clave(clave)
        perfil = db.query(Perfil).filter(Perfil.api_key_hash == h).first()
        if perfil and perfil.api_key_hash and hmac.compare_digest(perfil.api_key_hash, h):
            _recordar_cifrada(db, perfil, clave)
            return perfil
    # Camino antiguo: clave en claro.
    perfil = db.query(Perfil).filter(Perfil.api_key == clave).first()
    if perfil and perfil.api_key and hmac.compare_digest(perfil.api_key.encode(), clave.encode()):
        if con_hash:
            perfil.api_key_hash = hash_clave(clave)
            perfil.api_key_prefijo = prefijo_clave(clave)
            perfil.api_key = None
            _recordar_cifrada(db, perfil, clave, confirmar=False)
            db.commit()
        return perfil
    return None
