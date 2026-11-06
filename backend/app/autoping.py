"""Mantiene despierto el servidor en el plan gratis de Render (se duerme tras 15 min sin tráfico y despertarlo tarda
30-60 s: quien abre la app espera y las tareas programadas se pierden).

Mientras el servidor esté despierto, un hilo se llama a sí mismo por su dirección PÚBLICA cada pocos minutos. Es un
seguro adicional a la tarea «mantener despierto» de cron-job.org, que se desactivó sola tras fallar y dejó el servidor
durmiendo días. Se activa solo si existe la variable AUTOPING_URL (p. ej. https://api.cuadrame.dapx.shop/health)."""
import os
import threading
import time
import urllib.request

INTERVALO_SEG = 8 * 60  # menos de los 15 min de inactividad que tolera Render


def _llamar(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "cuadrame-autoping"}), timeout=20) as r:
            return 200 <= r.status < 300
    except Exception:  # un fallo de red no debe tumbar nada: se reintenta en el siguiente turno
        return False


def _bucle(url: str, intervalo: float) -> None:
    while True:
        time.sleep(intervalo)
        _llamar(url)


def iniciar(url: str | None = None, intervalo: float = INTERVALO_SEG) -> threading.Thread | None:
    """Arranca el hilo (daemon) si hay URL; devuelve el hilo, o None si está apagado."""
    url = (url if url is not None else os.environ.get("AUTOPING_URL", "")).strip()
    if not url.startswith("http"):
        return None
    hilo = threading.Thread(target=_bucle, args=(url, intervalo), name="autoping", daemon=True)
    hilo.start()
    return hilo
