"""Contador en memoria de errores 5xx recientes (solo cuenta; no guarda rutas, usuarios ni cuerpos).

Vive en el proceso: se reinicia con cada despliegue y, con varias réplicas, cada una cuenta lo suyo.
Es una señal temprana barata; la fuente de verdad de los errores sigue siendo Sentry.
"""
import threading
import time
from collections import deque

_lock = threading.Lock()
_marcas: deque = deque(maxlen=5000)


def registrar_5xx() -> None:
    with _lock:
        _marcas.append(time.time())


def contar_5xx(horas: float = 24) -> int:
    corte = time.time() - horas * 3600
    with _lock:
        return sum(1 for t in _marcas if t >= corte)


def reiniciar() -> None:  # para pruebas
    with _lock:
        _marcas.clear()
