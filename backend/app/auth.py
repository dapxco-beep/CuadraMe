"""
Verifica tokens emitidos por Supabase Auth usando sus claves públicas (JWKS).
No emitimos JWT propios: Supabase maneja registro, login y OAuth (Google).
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="noop", auto_error=False)

_jwks_client = jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


class UsuarioActual:
    def __init__(self, id: str, email: str):
        self.id = id
        self.email = email


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
        )
    except jwt.PyJWTError:
        raise credentials_exception

    usuario_id = payload.get("sub")
    email = payload.get("email", "")
    if not usuario_id:
        raise credentials_exception

    return UsuarioActual(id=usuario_id, email=email)
