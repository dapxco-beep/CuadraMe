"""«Enséñale a leer este correo»: reglas PERSONALES de lectura (ver app/reglas_correo.py).

Todo está filtrado por el usuario de la sesión. El cuerpo del correo se baja de SU Gmail solo para mostrárselo y
para comprobar lo que marcó; nunca se guarda ni se comparte. No se usa IA ni se entrena nada con el contenido."""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from google.auth.exceptions import RefreshError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.autocat import ClasificadorUsuario
from app.database import get_db
from app.duplicados import absorber_correos
from app.formas_asunto import registrar_forma
from app.extractos_gmail import encabezados
from app.gmail_extract import texto_cuerpo
from app.limites import verificar_limite
from app.models import CorreoGasto, Cuenta, ReglaCorreo
from app import reglas_correo as rc
from app.routers.correos import _ID_GMAIL, _crear_correo, _gmail_del_usuario

router = APIRouter(prefix="/reglas-correo", tags=["reglas-correo"])
logger = logging.getLogger(__name__)

MAX_REGLAS = 100


class _Modelo:
    """Clasificador vacío: aquí solo interesa lo que lee el lector estándar, no la categoría."""

    def clasificar(self, comercio, texto):
        return None


class VistaIn(BaseModel):
    correo_id: str | None = Field(None, max_length=64)
    gmail_msg_id: str | None = Field(None, max_length=64)


class ReglaIn(VistaIn):
    monto_texto: str | None = Field(None, max_length=60)
    comercio_texto: str | None = Field(None, max_length=80)
    tipo: str = Field("expense", pattern="^(income|expense)$")


def _salida(r: ReglaCorreo) -> dict:
    return {
        "id": r.id, "remitente_dominio": r.remitente_dominio, "esqueleto_asunto": r.esqueleto_asunto,
        "tipo": r.tipo, "marca_monto": r.etiqueta_monto is not None, "marca_comercio": r.etiqueta_comercio is not None,
        "corrige": bool(r.corrige), "usos": r.usos or 0, "creado_en": r.creado_en.isoformat() if r.creado_en else None,
    }


def _id_de_gmail(db: Session, usuario_id: str, data: VistaIn) -> str:
    """El id del mensaje de Gmail: del correo de Por revisar (solo si es de esta persona) o el que viene de la búsqueda."""
    if data.correo_id:
        c = db.query(CorreoGasto).filter(CorreoGasto.id == data.correo_id, CorreoGasto.usuario_id == usuario_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="No encontramos ese correo.")
        return c.gmail_msg_id
    if data.gmail_msg_id and _ID_GMAIL.match(data.gmail_msg_id):
        return data.gmail_msg_id
    raise HTTPException(status_code=400, detail="Elige el correo que quieres enseñarle a leer.")


def _leer_mensaje(db: Session, usuario_id: str, gmail_id: str) -> dict:
    gmail = _gmail_del_usuario(db, usuario_id, "movimiento")
    try:
        return gmail.users().messages().get(userId="me", id=gmail_id, format="full").execute()
    except RefreshError:
        raise HTTPException(status_code=400, detail="Se perdió el acceso a Gmail. Conéctalo de nuevo.")
    except Exception:
        logger.exception("No se pudo leer el correo para enseñarle a leer (usuario %s)", usuario_id)
        raise HTTPException(status_code=502, detail="No pudimos abrir ese correo ahora. Intenta de nuevo.")


def _datos_del_mensaje(msg: dict) -> tuple[str, str, str]:
    h = encabezados(msg)
    asunto, remitente = h.get("Subject", ""), h.get("From", "")
    texto = rc.texto_del_mensaje(asunto, msg.get("snippet", ""), texto_cuerpo(msg, limite=3000))
    return remitente, asunto, texto


def _similares(db: Session, usuario_id: str, regla: ReglaCorreo, excepto_gmail: str | None = None) -> list[CorreoGasto]:
    """Correos YA leídos de esta persona con la misma forma y que la lectura estándar dejó de lado (ignorados con monto)."""
    filas = (db.query(CorreoGasto).filter(CorreoGasto.usuario_id == usuario_id, CorreoGasto.estado == "ignorado",
                                          CorreoGasto.monto > 0)
             .order_by(CorreoGasto.recibido_en.desc()).limit(500).all())
    return [c for c in filas if c.gmail_msg_id != excepto_gmail and rc.coincide(regla, c.remitente, c.asunto)]


@router.get("")
def listar_reglas(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    filas = db.query(ReglaCorreo).filter(ReglaCorreo.usuario_id == usuario.id).order_by(ReglaCorreo.creado_en.desc()).all()
    return [_salida(r) for r in filas]


@router.post("/vista")
def vista_del_correo(data: VistaIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """El texto del correo (solo para esta persona, no se guarda) y lo que el lector estándar entendió."""
    verificar_limite(f"regla-correo-vista:{usuario.id}", 60, 3600, "Abriste muchos correos seguidos. Intenta en unos minutos.")
    gmail_id = _id_de_gmail(db, usuario.id, data)
    msg = _leer_mensaje(db, usuario.id, gmail_id)
    remitente, asunto, texto = _datos_del_mensaje(msg)
    estandar = _crear_correo(msg, usuario.id, _Modelo(), [])
    return {
        "gmail_msg_id": gmail_id, "asunto": asunto, "remitente": remitente, "texto": texto,
        "monto_actual": estandar.monto or 0, "comercio_actual": estandar.comercio, "tipo_actual": estandar.tipo_sugerido,
    }


@router.post("")
def crear_regla(data: ReglaIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Guarda la regla con lo que la persona marcó, la aplica a ese correo y cuenta cuántos parecidos ya leídos podrían volver."""
    verificar_limite(f"regla-correo-crear:{usuario.id}", 30, 3600, "Creaste muchas reglas seguidas. Intenta en unos minutos.")
    gmail_id = _id_de_gmail(db, usuario.id, data)
    msg = _leer_mensaje(db, usuario.id, gmail_id)
    remitente, asunto, texto = _datos_del_mensaje(msg)
    esq = rc.esqueleto_asunto(asunto)
    if not esq:
        raise HTTPException(status_code=400, detail="El asunto de este correo no tiene suficiente texto fijo para aprender de él.")
    try:
        marcas = rc.derivar_regla(texto, data.monto_texto, data.comercio_texto)
    except rc.ErrorRegla as e:
        raise HTTPException(status_code=400, detail=str(e))

    estandar = _crear_correo(msg, usuario.id, _Modelo(), [])
    monto_marcado = rc.extraer_monto(data.monto_texto, sanear=False) if marcas["etiqueta_monto"] is not None else 0
    comercio_marcado = rc.leer_comercio(texto, marcas["etiqueta_comercio"]) if marcas["etiqueta_comercio"] is not None else ""
    # «Corrige»: el lector había leído algo bueno y la persona lo cambió a propósito.
    corrige = bool(
        (monto_marcado and (estandar.monto or 0) > 0 and estandar.monto != monto_marcado)
        or (comercio_marcado and not rc.es_comercio_generico(estandar.comercio) and estandar.comercio != comercio_marcado)
        or (data.tipo != estandar.tipo_sugerido and (estandar.monto or 0) > 0 and not rc.es_comercio_generico(estandar.comercio))
    )

    if (estandar.monto or 0) <= 0 or rc.es_comercio_generico(estandar.comercio):
        registrar_forma(db, usuario.id, remitente, asunto)  # solo cuenta si aceptó estadísticas anónimas; sin datos personales

    dominio = rc.dominio_remitente(remitente)
    regla = (db.query(ReglaCorreo).filter(ReglaCorreo.usuario_id == usuario.id, ReglaCorreo.remitente_dominio == dominio,
                                          ReglaCorreo.esqueleto_asunto == esq).first())
    if regla is None:
        if db.query(ReglaCorreo).filter(ReglaCorreo.usuario_id == usuario.id).count() >= MAX_REGLAS:
            raise HTTPException(status_code=400, detail="Ya tienes muchas reglas. Borra alguna que no uses para crear otra.")
        regla = ReglaCorreo(usuario_id=usuario.id, remitente_dominio=dominio, esqueleto_asunto=esq, usos=0)
        db.add(regla)
    regla.etiqueta_monto = marcas["etiqueta_monto"]
    regla.etiqueta_comercio = marcas["etiqueta_comercio"]
    regla.tipo = data.tipo
    regla.corrige = corrige
    regla.creado_en = datetime.utcnow()
    db.flush()
    db.info.pop("reglas_correo", None)

    # Este mismo correo: si ya está en la lista de la persona, queda leído con lo que marcó.
    propio = None
    for c in db.query(CorreoGasto).filter(CorreoGasto.usuario_id == usuario.id, CorreoGasto.gmail_msg_id == gmail_id).all():
        if c.estado in ("aprobado", "ya_registrado"):
            continue
        if monto_marcado:
            c.monto = monto_marcado
        if comercio_marcado:
            c.comercio = comercio_marcado
        c.tipo_sugerido = data.tipo
        if c.estado == "ignorado" and (c.monto or 0) > 0:
            c.estado = "pendiente"
        propio = {"id": c.id, "monto": c.monto, "comercio": c.comercio, "tipo": c.tipo_sugerido, "estado": c.estado}
    similares = len(_similares(db, usuario.id, regla, excepto_gmail=gmail_id))
    db.commit()
    return {"regla": _salida(regla), "correo": propio, "similares": similares}


@router.post("/{regla_id}/aplicar-anteriores")
def aplicar_a_anteriores(regla_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Los correos parecidos que ya se habían leído y quedaron de lado vuelven a «Por revisar»; los que siguen
    pendientes sin monto o sin nombre se releen con la regla (con el fragmento que ya tenemos)."""
    regla = db.query(ReglaCorreo).filter(ReglaCorreo.id == regla_id, ReglaCorreo.usuario_id == usuario.id).first()
    if not regla:
        raise HTTPException(status_code=404, detail="No encontramos esa regla.")
    recuperados = 0
    for c in _similares(db, usuario.id, regla):
        c.estado = "pendiente"
        recuperados += 1
    releidos = 0
    for c in db.query(CorreoGasto).filter(CorreoGasto.usuario_id == usuario.id, CorreoGasto.estado == "pendiente").limit(500).all():
        if not rc.coincide(regla, c.remitente, c.asunto):
            continue
        out = rc.aplicar_regla({"remitente": c.remitente, "asunto": c.asunto, "texto": rc.texto_del_mensaje(c.asunto, c.snippet, ""),
                                "monto": c.monto, "comercio": c.comercio, "tipo": c.tipo_sugerido}, [regla])
        if out:
            c.monto = out.get("monto", c.monto)
            c.comercio = out.get("comercio", c.comercio)
            c.tipo_sugerido = out.get("tipo", c.tipo_sugerido)
            releidos += 1
    if recuperados:
        regla.usos = (regla.usos or 0) + recuperados
        db.flush()
        # Los que ya tienen su movimiento no deben volver a la lista.
        absorber_correos(db, usuario.id, cuentas=db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all())
    db.commit()
    return {"ok": True, "recuperados": recuperados, "releidos": releidos}


@router.delete("/{regla_id}")
def borrar_regla(regla_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    regla = db.query(ReglaCorreo).filter(ReglaCorreo.id == regla_id, ReglaCorreo.usuario_id == usuario.id).first()
    if not regla:
        raise HTTPException(status_code=404, detail="No encontramos esa regla.")
    db.delete(regla)
    db.commit()
    return {"ok": True}
