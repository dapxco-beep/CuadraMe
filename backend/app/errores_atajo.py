"""Errores legibles para los Atajos de iPhone (/movimientos/rapido*).

Un Atajo lee el campo "mensaje" de la respuesta y lo muestra como notificación.
Con un error normal de FastAPI ese campo no existe y la notificación sale vacía,
sin decir si se registró o no. Aquí los errores de esas rutas traen un "mensaje"
en español que explica qué pasó. Nunca se incluyen los valores enviados (solo
el nombre del campo), porque pueden ser datos personales."""
import logging

from fastapi import HTTPException, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

RUTAS = ("/movimientos/rapido", "/movimientos/cuentas-rapido")

# Nombre del campo tal como lo ve el usuario al armar el Atajo.
_CAMPOS = {
    "monto": "el monto",
    "tipo": "el tipo (gasto o ingreso)",
    "comercio": "el comercio",
    "descripcion": "la nota",
    "tarjeta": "la tarjeta",
    "cuenta": "la cuenta",
    "x_api_key": "la clave (X-Api-Key)",
}


def _es_ruta_atajo(request: Request) -> bool:
    return request.url.path.startswith(RUTAS)


def _mensaje_validacion(errores: list[dict]) -> str:
    """Resume qué campos fallaron sin repetir los valores recibidos."""
    for e in errores:
        loc = [str(x) for x in e.get("loc", ()) if x not in ("body", "header", "query")]
        campo = loc[-1].lower().replace("-", "_") if loc else ""
        if campo == "x_api_key":
            return (
                "No se registró: el atajo no envió tu clave. Pégala en el primer Texto del atajo "
                "(CuadraMe → Perfil → Conectar dispositivo → Copiar mi clave)."
            )
        detalle = str(e.get("msg", "")).replace("Value error, ", "")
        if campo == "monto" or "monto" in detalle.lower():
            return "No se registró: no entendí el monto. Escribe solo números."
        if campo in _CAMPOS:
            return f"No se registró: falta o no se entiende {_CAMPOS[campo]}."
        if detalle:
            return f"No se registró: {detalle}."
    return "No se registró: faltan datos en el atajo."


async def validacion_atajo(request: Request, exc: RequestValidationError):
    if not _es_ruta_atajo(request):
        return await request_validation_exception_handler(request, exc)
    errores = exc.errors()
    # Solo nombres de campo y tipo de error en el log: nada de valores.
    logger.warning(
        "Atajo rechazado (422): %s",
        [(".".join(str(x) for x in e.get("loc", ())), e.get("type")) for e in errores],
    )
    cuerpo = {
        "ok": False,
        "mensaje": _mensaje_validacion(errores),
        "detail": [{"loc": list(e.get("loc", ())), "msg": e.get("msg"), "type": e.get("type")} for e in errores],
    }
    return JSONResponse(status_code=422, content=cuerpo)


async def http_atajo(request: Request, exc: HTTPException):
    if not _es_ruta_atajo(request):
        return await http_exception_handler(request, exc)
    detalle = exc.detail if isinstance(exc.detail, str) else "error"
    if exc.status_code == 401:
        mensaje = (
            "No se registró: la clave del atajo no es válida. Cópiala de nuevo en CuadraMe "
            "(Perfil → Conectar dispositivo) y pégala en el atajo."
        )
    elif exc.status_code == 404:
        mensaje = "No se registró: no encontré ninguna cuenta en CuadraMe. Crea una primero."
    elif exc.status_code == 429:
        mensaje = "No se registró: hiciste muchos registros seguidos. Intenta en un rato."
    else:
        mensaje = f"No se registró: {detalle}"
    cuerpo = {"ok": False, "mensaje": mensaje, "detail": exc.detail}
    return JSONResponse(status_code=exc.status_code, content=cuerpo, headers=getattr(exc, "headers", None))


def registrar(app) -> None:
    app.add_exception_handler(RequestValidationError, validacion_atajo)
    app.add_exception_handler(HTTPException, http_atajo)
