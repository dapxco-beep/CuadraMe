"""Errores inesperados como respuesta 500 con cabeceras CORS (ver el comentario en main.py).

ASGI puro a propósito: no envuelve ni reconstruye las respuestas normales (compresión, streaming);
solo actúa si la app lanza una excepción antes de empezar a responder."""
import json
import logging

log = logging.getLogger(__name__)

_CUERPO = json.dumps({"detail": "Algo falló de nuestro lado. Intenta de nuevo en un momento."}).encode()


class Errores500Middleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        empezo = False

        async def _send(mensaje):
            nonlocal empezo
            if mensaje["type"] == "http.response.start":
                empezo = True
            await send(mensaje)

        try:
            await self.app(scope, receive, _send)
        except Exception as e:  # noqa: BLE001
            log.exception("Error inesperado en %s %s", scope.get("method"), scope.get("path"))
            try:
                import sentry_sdk

                sentry_sdk.capture_exception(e)
            except Exception:  # noqa: BLE001
                pass
            if empezo:
                raise
            await send({"type": "http.response.start", "status": 500,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(_CUERPO)).encode())]})
            await send({"type": "http.response.body", "body": _CUERPO})
