"""
Límite de peticiones por usuario (ventana deslizante en memoria).

Protege lo que cuesta dinero o recursos —preguntas a la IA (OpenRouter),
lectura de PDFs, sincronización de Gmail— y los endpoints que se autentican
solo con API key.

IMPORTANTE: el contador vive en la memoria de CADA proceso. Con N réplicas el
límite efectivo se multiplica por N (y se reinicia en cada despliegue). Por eso
Railway debe quedarse en 1 réplica mientras no exista un almacén compartido
(p. ej. Redis); al migrar, la interfaz `verificar_limite` no cambia.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

_lock = threading.Lock()
_eventos: dict[str, deque] = defaultdict(deque)


def _texto_espera(segundos: int) -> str:
    """'45 segundos', '1 minuto', '12 minutos': para decirle al usuario cuándo reintentar."""
    if segundos < 60:
        return f"{max(segundos, 1)} segundos"
    minutos = (segundos + 59) // 60
    return "1 minuto" if minutos == 1 else f"{minutos} minutos"


def verificar_limite(clave: str, maximo: int, ventana_segundos: int, mensaje: str | None = None) -> None:
    """Registra un uso de `clave` y lanza 429 si ya hubo `maximo` en la ventana.
    Si `mensaje` contiene "{espera}", se reemplaza por cuánto falta ('12 minutos')."""
    ahora = time.monotonic()
    with _lock:
        cola = _eventos[clave]
        while cola and ahora - cola[0] > ventana_segundos:
            cola.popleft()
        if len(cola) >= maximo:
            espera = int(ventana_segundos - (ahora - cola[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=(mensaje or "Demasiadas solicitudes. Intenta de nuevo en {espera}.").replace(
                    "{espera}", _texto_espera(espera)
                ),
                headers={"Retry-After": str(espera)},
            )
        cola.append(ahora)
        # Evita que el diccionario crezca sin límite con claves de usuarios inactivos.
        if len(_eventos) > 20000:
            for k in [k for k, v in _eventos.items() if not v or ahora - v[-1] > ventana_segundos]:
                _eventos.pop(k, None)


# --- Intentos fallidos de API key por IP ------------------------------------
# Frena el adivinado de claves: 30 intentos fallidos por IP cada 10 minutos.
# Solo cuentan los FALLOS; los aciertos no gastan cupo.
FALLOS_API_KEY_MAX = 30
FALLOS_API_KEY_VENTANA = 600
MENSAJE_FALLOS_API_KEY = "Demasiados intentos con una clave inválida. Intenta de nuevo en unos minutos."


def ip_cliente(request) -> str:
    """IP del cliente: primer valor de X-Forwarded-For (Railway va detrás de un
    proxy) con respaldo a la IP del socket."""
    reenviada = request.headers.get("x-forwarded-for", "")
    if reenviada.strip():
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


def _clave_fallos(ip: str) -> str:
    return f"apikey-invalida:{ip}"


def bloquear_si_demasiados_fallos(ip: str) -> None:
    """Lanza 429 si la IP ya agotó sus intentos fallidos (no registra nada)."""
    ahora = time.monotonic()
    with _lock:
        cola = _eventos.get(_clave_fallos(ip))
        if not cola:
            return
        while cola and ahora - cola[0] > FALLOS_API_KEY_VENTANA:
            cola.popleft()
        if len(cola) >= FALLOS_API_KEY_MAX:
            espera = int(FALLOS_API_KEY_VENTANA - (ahora - cola[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=MENSAJE_FALLOS_API_KEY,
                headers={"Retry-After": str(espera)},
            )


def registrar_fallo_api_key(ip: str) -> None:
    """Anota un intento fallido de la IP."""
    with _lock:
        _eventos[_clave_fallos(ip)].append(time.monotonic())
