"""
Límite de peticiones por usuario (ventana deslizante en memoria).

Protege lo que cuesta dinero o recursos —preguntas a la IA (OpenRouter),
lectura de PDFs, sincronización de Gmail— y los endpoints que se autentican
solo con API key. Es por proceso: con una sola instancia de Railway funciona
tal cual; si algún día se escala a varias réplicas, pasar este contador a
Redis (la interfaz `verificar_limite` no cambia).
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

_lock = threading.Lock()
_eventos: dict[str, deque] = defaultdict(deque)


def verificar_limite(clave: str, maximo: int, ventana_segundos: int, mensaje: str | None = None) -> None:
    """Registra un uso de `clave` y lanza 429 si ya hubo `maximo` en la ventana."""
    ahora = time.monotonic()
    with _lock:
        cola = _eventos[clave]
        while cola and ahora - cola[0] > ventana_segundos:
            cola.popleft()
        if len(cola) >= maximo:
            espera = int(ventana_segundos - (ahora - cola[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=mensaje or f"Demasiadas solicitudes. Intenta de nuevo en {espera} segundos.",
                headers={"Retry-After": str(espera)},
            )
        cola.append(ahora)
        # Evita que el diccionario crezca sin límite con claves de usuarios inactivos.
        if len(_eventos) > 20000:
            for k in [k for k, v in _eventos.items() if not v or ahora - v[-1] > ventana_segundos]:
                _eventos.pop(k, None)
