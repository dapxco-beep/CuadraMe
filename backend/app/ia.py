"""Un solo lugar para hablar con la IA de texto. Proveedores GRATUITOS, en orden de preferencia:

1. Groq (modelos abiertos, rápido; se activa con GROQ_API_KEY).
2. OpenRouter (modelo `:free`; se activa con OPENROUTER_API_KEY). Es el respaldo si Groq falla o se agota.

Los dos hablan el mismo formato (chat/completions), por eso comparten código. Si uno responde con error se
prueba el siguiente; si todos fallan se lanza el último error y cada llamador usa su texto determinista.
Lo que NO pasa por aquí: contenido de Gmail (solo con modelo privado, ver pdf_extract) ni la lectura de
facturas (necesita visión: sigue directo en OpenRouter, ver factura.py)."""
import logging

import httpx

from .config import settings

logger = logging.getLogger("cuadrame.ia")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Modelo gratuito de respaldo en OpenRouter. Los `:free` cambian con el tiempo: si deja de existir el log
# dirá «HTTP 404» y se cambia aquí.
OPENROUTER_MODEL = "google/gemma-4-31b-it:free"


def hay_ia() -> bool:
    return bool(settings.groq_api_key or settings.openrouter_api_key)


def _proveedores() -> list[tuple[str, str, str, str]]:
    """(nombre, url, clave, modelo) de los proveedores con clave, en orden de preferencia."""
    lista = []
    if settings.groq_api_key:
        lista.append(("groq", GROQ_URL, settings.groq_api_key, settings.groq_model))
    if settings.openrouter_api_key:
        lista.append(("openrouter", OPENROUTER_URL, settings.openrouter_api_key, OPENROUTER_MODEL))
    return lista


def completar(mensajes: list[dict], *, temperatura: float = 0.3, max_tokens: int | None = None,
              timeout: float = 20) -> str:
    """Devuelve el texto de la respuesta o lanza la excepción del último proveedor intentado.
    No registra el contenido (solo proveedor y código HTTP)."""
    ultimo: Exception = RuntimeError("sin proveedor de IA configurado")
    for nombre, url, clave, modelo in _proveedores():
        cuerpo: dict = {"model": modelo, "messages": mensajes, "temperature": temperatura}
        if max_tokens:
            cuerpo["max_tokens"] = max_tokens
        if nombre == "groq":
            # gpt-oss «piensa» antes de responder y esos tokens cuentan: esfuerzo bajo y holgura para el tope.
            cuerpo["reasoning_effort"] = "low"
            if max_tokens:
                cuerpo["max_tokens"] = max_tokens + 1000
        try:
            resp = httpx.post(url, headers={"Authorization": f"Bearer {clave}"}, json=cuerpo, timeout=timeout)
            resp.raise_for_status()
            texto = (resp.json()["choices"][0]["message"]["content"] or "").strip()
            if not texto:
                raise ValueError("respuesta vacía")
            return texto
        except Exception as e:  # noqa: BLE001
            estado = getattr(getattr(e, "response", None), "status_code", None)
            logger.warning("ia: %s falló (%s%s)", nombre, type(e).__name__, f" HTTP {estado}" if estado else "")
            ultimo = e
    raise ultimo
