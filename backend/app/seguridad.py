"""
Defensas generales de la API (middleware ASGI puro, sin dependencias nuevas).

1. Tamaño de cuerpo: cada petición tiene un tope. Solo las rutas que reciben
   archivos (PDF, imagen, Excel) admiten cuerpos grandes; el resto, 2 MB. Sin esto
   cualquiera con sesión puede mandar cientos de MB y tumbar la memoria del servidor.
2. JSON sin NaN / Infinity: Python acepta esos literales aunque no son JSON válido.
   Un `saldo: Infinity` quedaría guardado y luego rompería (500) toda respuesta que
   lo incluya, para siempre. Se rechazan antes de llegar a los modelos.
3. Cabeceras de seguridad en TODA respuesta, incluidos los errores.

Decisión: se bufferiza el cuerpo dentro del tope porque FastAPI igual lo lee entero
para validar el JSON; así el costo extra es casi nulo y el código sigue siendo simple.
"""
import json

# Rutas que reciben archivos en base64 (hasta ~15 MB de archivo -> ~20 MB de texto).
RUTAS_CON_ARCHIVOS = (
    "/conciliacion/procesar",
    "/facturas/escanear",
    "/importar/vista-previa",
)
LIMITE_GRANDE = 25 * 1024 * 1024
LIMITE_NORMAL = 2 * 1024 * 1024

CABECERAS_SEGURIDAD = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
]


def limite_de(ruta: str) -> int:
    return LIMITE_GRANDE if ruta.startswith(RUTAS_CON_ARCHIVOS) else LIMITE_NORMAL


def _rechazar_constante(nombre: str):
    raise ValueError(f"valor no permitido: {nombre}")


def json_es_finito(cuerpo: bytes) -> bool:
    """False si el JSON trae NaN, Infinity o -Infinity (o no se puede leer).
    Búsqueda rápida primero: lo normal es que ni aparezcan esas palabras."""
    if b"NaN" not in cuerpo and b"Infinity" not in cuerpo:
        return True
    try:
        json.loads(cuerpo, parse_constant=_rechazar_constante)
    except ValueError:
        # Puede ser JSON roto (lo dirá la validación normal) o una constante no finita.
        try:
            json.loads(cuerpo)
        except ValueError:
            return True  # JSON inválido: que responda el 422 de siempre
        return False
    return True


class SeguridadMiddleware:
    def __init__(self, app, con_csp: bool = True):
        self.app = app
        self.cabeceras = [h for h in CABECERAS_SEGURIDAD if con_csp or h[0] != b"content-security-policy"]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_seguro(mensaje):
            if mensaje["type"] == "http.response.start":
                existentes = {k.lower() for k, _ in mensaje.get("headers", [])}
                extra = [h for h in self.cabeceras if h[0] not in existentes]
                if b"cache-control" not in existentes:
                    # Respuestas con datos financieros: que ningún proxy ni navegador las guarde.
                    extra.append((b"cache-control", b"no-store"))
                mensaje = {**mensaje, "headers": [*mensaje.get("headers", []), *extra]}
            await send(mensaje)

        if scope["method"] in ("POST", "PUT", "PATCH", "DELETE"):
            limite = limite_de(scope["path"])
            cabeceras = {k.lower(): v for k, v in scope.get("headers", [])}
            try:
                declarado = int(cabeceras.get(b"content-length", b"0") or 0)
            except ValueError:
                declarado = 0
            if declarado > limite:
                return await self._responder(send_seguro, 413, "El archivo o los datos enviados son demasiado grandes.")

            partes: list[bytes] = []
            total = 0
            while True:
                mensaje = await receive()
                if mensaje["type"] == "http.disconnect":
                    return
                trozo = mensaje.get("body", b"")
                total += len(trozo)
                if total > limite:
                    return await self._responder(send_seguro, 413, "El archivo o los datos enviados son demasiado grandes.")
                partes.append(trozo)
                if not mensaje.get("more_body"):
                    break
            cuerpo = b"".join(partes)

            if b"json" in cabeceras.get(b"content-type", b"") and not json_es_finito(cuerpo):
                return await self._responder(send_seguro, 422, "Los números deben ser finitos (sin NaN ni Infinity).")

            enviado = False

            async def receive_repetido():
                nonlocal enviado
                if not enviado:
                    enviado = True
                    return {"type": "http.request", "body": cuerpo, "more_body": False}
                return await receive()

            return await self.app(scope, receive_repetido, send_seguro)

        return await self.app(scope, receive, send_seguro)

    @staticmethod
    async def _responder(send, estado: int, detalle: str):
        cuerpo = json.dumps({"detail": detalle}, ensure_ascii=False).encode()
        await send({"type": "http.response.start", "status": estado,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(cuerpo)).encode())]})
        await send({"type": "http.response.body", "body": cuerpo})


def limpiar_evento_sentry(evento, pista):
    """Quita de los eventos de Sentry lo que nunca debe salir del servidor: sesiones,
    claves de API, secretos de cron y cuerpos de petición (movimientos, PDFs, claves)."""
    peticion = evento.get("request")
    if peticion:
        peticion.pop("data", None)
        peticion.pop("cookies", None)
        peticion.pop("query_string", None)
        cab = peticion.get("headers")
        if isinstance(cab, dict):
            for k in list(cab):
                if k.lower() in ("authorization", "x-api-key", "x-cron-secret", "cookie", "stripe-signature"):
                    cab[k] = "[filtrado]"
    return evento
