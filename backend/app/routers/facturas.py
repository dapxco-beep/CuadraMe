from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.factura import FacturaError, analizar_factura, validar_imagen
from app.limites import verificar_limite
from app.routers.categorias import _asegurar_categorias_base
from app.routers.consentimientos import exigir_consentimiento
from app.routers.movimientos import _clasificar

router = APIRouter(prefix="/facturas", tags=["facturas"])


class EscanearRequest(BaseModel):
    imagen_base64: str  # sin el prefijo "data:...;base64,"
    mime: str = "image/jpeg"


@router.post("/escanear")
def escanear(
    data: EscanearRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Lee una foto de factura y devuelve campos SUGERIDOS. No guarda nada:
    el usuario los revisa en el formulario y decide si registra el movimiento.
    La imagen se procesa en memoria y se descarta."""
    exigir_consentimiento(db, usuario.id, "ia")  # Ley 1581: la foto va a un proveedor de IA
    # Cada lectura es una llamada a un modelo de visión: tope por usuario, como la IA de chat.
    verificar_limite(f"factura:{usuario.id}", 10, 3600, "Llegaste al límite de facturas por hora. Intenta más tarde.")
    try:
        datos = validar_imagen(data.imagen_base64, data.mime)
        categorias = [c.nombre for c in _asegurar_categorias_base(db, usuario.id) if c.activa]
        r = analizar_factura(datos, data.mime, categorias)
    except FacturaError as e:
        raise HTTPException(status_code=e.status, detail=e.mensaje)

    # La categoría de la IA se usa si existe entre las del usuario; si no, el
    # clasificador de siempre (reglas del usuario, aprendido, diccionario).
    categoria = r.pop("categoria_ia")
    if not categoria and r["comercio"]:
        sugerida = _clasificar(db, usuario.id, r["comercio"])
        categoria = sugerida["categoria"] if sugerida else None
    r["categoria"] = categoria or "Otros"
    return r
