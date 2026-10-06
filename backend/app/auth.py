"""
Verifica tokens emitidos por Supabase Auth usando sus claves públicas (JWKS).
No emitimos JWT propios: Supabase maneja registro, login y OAuth (Google).

Para clientes que no pueden hacer login interactivo (Atajos de iOS, Scriptable,
Tasker, reglas de correo) hay una segunda vía: una API key propia por usuario
(ver get_current_user_by_api_key), pensada solo para registrar movimientos.
"""
import hmac
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.limites import bloquear_si_demasiados_fallos, ip_cliente, registrar_fallo_api_key

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="noop", auto_error=False)

_jwks_client = jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


class UsuarioActual:
    def __init__(self, id: str, email: str, nombre: str = ""):
        self.id = id
        self.email = email
        self.nombre = nombre


def cron_autorizado(secreto_recibido: str) -> bool:
    """Compara el secreto de los crons en tiempo constante (hmac.compare_digest)
    para que no se pueda adivinar byte a byte midiendo tiempos de respuesta.
    Si CRON_SECRET no está configurado, ningún cron queda autorizado."""
    if not settings.cron_secret:
        return False
    return hmac.compare_digest(secreto_recibido.encode(), settings.cron_secret.encode())


def get_current_user(token: str = Depends(oauth2_scheme)) -> UsuarioActual:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            leeway=30,  # tolera pequeño desfase de reloj entre máquinas
        )
    except jwt.PyJWTError:
        raise credentials_exception

    usuario_id = payload.get("sub")
    email = payload.get("email", "")
    if not usuario_id:
        raise credentials_exception

    meta = payload.get("user_metadata") or {}
    nombre = meta.get("nombre") or meta.get("full_name") or meta.get("name") or ""
    return UsuarioActual(id=usuario_id, email=email, nombre=nombre)


def get_current_user_by_api_key(
    request: Request, x_api_key: str = Header(...), db: Session = Depends(get_db)
) -> UsuarioActual:
    from app.models import Perfil

    # Tope de intentos con clave inválida por IP (ver limites.py): 30 cada 10 min.
    ip = ip_cliente(request)
    bloquear_si_demasiados_fallos(ip)
    perfil = db.query(Perfil).filter(Perfil.api_key == x_api_key).first()
    if not perfil:
        registrar_fallo_api_key(ip)
        raise HTTPException(status_code=401, detail="API key inválida")
    # Guarda cuándo se usó por última vez (alimenta el semáforo de "Conexiones").
    # Se escribe como mucho una vez por minuto para no sumar una escritura a
    # cada reintento de un Atajo; con eso la precisión sobra.
    ahora = datetime.utcnow()
    if not perfil.api_key_ultimo_uso or ahora - perfil.api_key_ultimo_uso > timedelta(seconds=60):
        perfil.api_key_ultimo_uso = ahora
        db.commit()
    return UsuarioActual(id=perfil.usuario_id, email="", nombre="")
