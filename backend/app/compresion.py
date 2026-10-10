"""Compresión gzip de las respuestas JSON (rendimiento en datos móviles).

Una lista de 50 movimientos pesa ~20 KB en JSON y comprime ~85 %; el Inicio junta ~12 lecturas.
Con datos móviles lentos (Colombia) eso son varios cientos de milisegundos menos por pantalla.

Decisiones:
  * Solo si el cliente manda `Accept-Encoding: gzip` (todos los navegadores) y la respuesta pasa
    de 1 KB: lo pequeño no compensa el costo de CPU.
  * Nivel 5 (el predeterminado, 9, gasta mucha CPU por muy poca ganancia extra).
  * Se excluyen las descargas (/exportar, /backup): un .xlsx ya viene comprimido.
  * NO se agregan ETag ni `Cache-Control: private`: la política de seguridad (ver
    docs/AUDITORIA_SEGURIDAD.md, hallazgo 8) es `no-store` en toda respuesta para que ningún
    navegador ni proxy guarde datos financieros. Revalidar con ETag exigiría guardarlos.
"""
from starlette.middleware.gzip import GZipMiddleware

_SIN_COMPRIMIR = ("/exportar", "/backup")


class GZipSelectivo(GZipMiddleware):
    def __init__(self, app, minimum_size: int = 1024, compresslevel: int = 5):
        super().__init__(app, minimum_size=minimum_size, compresslevel=compresslevel)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").startswith(_SIN_COMPRIMIR):
            return await self.app(scope, receive, send)
        return await super().__call__(scope, receive, send)
