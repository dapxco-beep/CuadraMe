"""
Conexión de Gmail por usuario, independiente del login (que va por Supabase Auth
y no expone scopes de Gmail). Cada usuario autoriza su propio Gmail una vez;
guardamos el refresh token cifrado y lo usamos para leer solo los correos con
la etiqueta que el usuario elija (por defecto "gastos").
"""
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_SCOPE ="https://www.googleapis.com/auth/gmail.readonly"
REDIRECT_URI = f"{settings.api_base_url}/correos/oauth/callback"


def _fernet() -> Fernet:
    return Fernet(settings.fernet_key.encode())


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def descifrar(texto: str) -> str:
    return _fernet().decrypt(texto.encode()).decode()


def crear_state(usuario_id: str) -> str:
    """El 'state' del flujo OAuth lleva el usuario cifrado y con marca de
    tiempo (Fernet). Así no hace falta guardarlo en memoria del servidor:
    sobrevive reinicios y funciona con varias instancias."""
    return cifrar(usuario_id)


def leer_state(state: str, max_segundos: int = 600) -> str | None:
    """Devuelve el usuario_id si el state es válido y tiene menos de 10 min."""
    try:
        return _fernet().decrypt(state.encode(), ttl=max_segundos).decode()
    except Exception:
        return None


def url_autorizacion(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": GMAIL_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def intercambiar_code(code: str) -> dict:
    resp = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def obtener_email(access_token: str) -> str:
    # El perfil de Gmail responde con el permiso gmail.readonly que ya pedimos.
    # (El endpoint oauth2/v2/userinfo exigiría además el scope userinfo.email.)
    resp = httpx.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("emailAddress", "")


def revocar_token(refresh_token_enc: str | None) -> bool:
    """Le pide a Google que invalide el refresh token (que el acceso a Gmail muera de
    verdad, no solo en nuestra base). Devuelve True si Google lo confirmó. Nunca lanza:
    desconectar o borrar la cuenta debe funcionar aunque Google esté caído o el token
    ya estuviera revocado; en ese caso el usuario puede quitarlo en
    myaccount.google.com/permissions."""
    if not refresh_token_enc:
        return False
    try:
        token = descifrar(refresh_token_enc)
        resp = httpx.post(GOOGLE_REVOKE_URL, params={"token": token}, timeout=10)
        return resp.status_code == 200
    except Exception:  # noqa: BLE001 - best effort; sin registrar el token
        return False


def cliente_gmail(refresh_token_enc: str):
    creds = Credentials(
        token=None,
        refresh_token=descifrar(refresh_token_enc),
        token_uri=GOOGLE_TOKEN_URL,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=[GMAIL_SCOPE],
    )
    return build("gmail", "v1", credentials=creds)
