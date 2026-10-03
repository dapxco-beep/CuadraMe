import logging

from google.auth.exceptions import RefreshError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.classifier import build_model, classify
from app.comercios_conocidos import clasificar_por_diccionario
from app.config import settings
from app.limites import verificar_limite
from app.database import get_db
from app.gmail_extract import detectar_tipo, extraer_comercio, extraer_moneda, extraer_monto
from app.gmail_oauth import (
    cifrar,
    cliente_gmail,
    crear_state,
    intercambiar_code,
    leer_state,
    obtener_email,
    url_autorizacion,
)
from app.models import Cuenta, CorreoGasto, Movimiento, Perfil
from app.schemas import (
    AprobarCorreoRequest,
    CorreoGastoOut,
    CorreoGastoUpdate,
    GmailEstado,
    SincronizarCorreosResponse,
)

router = APIRouter(prefix="/correos", tags=["correos"])
logger = logging.getLogger(__name__)


def _get_or_create_perfil(db: Session, usuario_id: str) -> Perfil:
    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
    if not perfil:
        perfil = Perfil(usuario_id=usuario_id, plan="free")
        db.add(perfil)
        db.commit()
        db.refresh(perfil)
    return perfil


@router.get("/gmail/estado", response_model=GmailEstado)
def estado_gmail(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    return GmailEstado(
        conectado=bool(perfil.gmail_conectado),
        email=perfil.gmail_email,
        etiqueta=perfil.gmail_etiqueta or "gastos",
    )


@router.get("/gmail/conectar")
def conectar_gmail(
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Devuelve la URL a la que el frontend debe redirigir al usuario para
    autorizar el acceso de solo lectura a Gmail."""
    return {"url": url_autorizacion(crear_state(usuario.id))}


@router.get("/oauth/callback")
def gmail_callback(code: str, state: str, db: Session = Depends(get_db)):
    usuario_id = leer_state(state)
    if not usuario_id:
        raise HTTPException(status_code=400, detail="Estado OAuth inválido o expirado")

    tokens = intercambiar_code(code)
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        # Google no reenvía refresh_token si el usuario ya había autorizado antes
        # sin revocar acceso; pedimos que revoque y reintente.
        raise HTTPException(
            status_code=400,
            detail="Google no devolvió un refresh token. Revoca el acceso en "
            "myaccount.google.com/permissions y vuelve a intentar.",
        )

    email = obtener_email(tokens["access_token"])

    perfil = _get_or_create_perfil(db, usuario_id)
    perfil.gmail_conectado = True
    perfil.gmail_refresh_token_enc = cifrar(refresh_token)
    perfil.gmail_email = email
    db.commit()

    return RedirectResponse(url=f"{settings.pwa_url}/#/perfil?gmail=conectado")


@router.post("/gmail/desconectar")
def desconectar_gmail(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    perfil.gmail_conectado = False
    perfil.gmail_refresh_token_enc = None
    perfil.gmail_email = None
    db.commit()
    return {"ok": True}


@router.post("/gmail/etiqueta")
def actualizar_etiqueta(
    etiqueta: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    perfil = _get_or_create_perfil(db, usuario.id)
    perfil.gmail_etiqueta = etiqueta.strip() or "gastos"
    db.commit()
    return {"ok": True, "etiqueta": perfil.gmail_etiqueta}


@router.post("/sincronizar", response_model=SincronizarCorreosResponse)
def sincronizar(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Lee los correos con la etiqueta configurada (por defecto 'gastos') que
    aún no se han procesado, extrae monto/comercio y los deja como pendientes
    de revisión — nunca crea movimientos automáticamente."""
    verificar_limite(f"sync-gmail:{usuario.id}", 12, 3600, "Sincronizaste muchas veces seguidas. Intenta en unos minutos.")
    perfil = _get_or_create_perfil(db, usuario.id)
    if not perfil.gmail_conectado or not perfil.gmail_refresh_token_enc:
        raise HTTPException(status_code=400, detail="Gmail no está conectado")

    etiqueta = perfil.gmail_etiqueta or "gastos"

    try:
        gmail = cliente_gmail(perfil.gmail_refresh_token_enc)
        labels = gmail.users().labels().list(userId="me").execute().get("labels", [])
        label_id = next(
            (l["id"] for l in labels if l["name"].lower() == etiqueta.lower()), None
        )
        if not label_id:
            return SincronizarCorreosResponse(
                ok=False, nuevos=0, omitidos=0,
                error=f"Etiqueta '{etiqueta}' no encontrada en Gmail",
            )

        existentes = {
            r[0]
            for r in db.query(CorreoGasto.gmail_msg_id)
            .filter(CorreoGasto.usuario_id == usuario.id)
            .all()
        }

        resultado = (
            gmail.users()
            .messages()
            .list(userId="me", labelIds=[label_id], maxResults=25)
            .execute()
        )
        mensajes = resultado.get("messages", [])

        historial = (
            db.query(Movimiento)
            .filter(Movimiento.usuario_id == usuario.id, Movimiento.categoria != "Otros")
            .all()
        )
        modelo = build_model(
            [{"descripcion": m.descripcion, "categoria": m.categoria, "tipo": m.tipo} for m in historial]
        )

        nuevos = 0
        omitidos = 0

        for ref in mensajes:
            if ref["id"] in existentes:
                omitidos += 1
                continue

            msg = gmail.users().messages().get(userId="me", id=ref["id"], format="full").execute()
            headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
            remitente = headers.get("From", "")
            asunto = headers.get("Subject", "")
            snippet = msg.get("snippet", "")
            texto = f"{asunto} {snippet}"

            monto = extraer_monto(texto)
            moneda = extraer_moneda(texto)
            comercio = extraer_comercio(remitente, asunto)
            tipo = detectar_tipo(texto)

            resultado_clasif = classify(comercio, modelo) or clasificar_por_diccionario(f"{comercio} {texto}")
            categoria = resultado_clasif["categoria"] if resultado_clasif else "Otros"
            confianza = resultado_clasif["confianza"] if resultado_clasif else 0

            correo = CorreoGasto(
                usuario_id=usuario.id,
                gmail_msg_id=ref["id"],
                remitente=remitente,
                asunto=asunto,
                snippet=snippet[:400],
                monto=monto,
                moneda=moneda,
                comercio=comercio,
                categoria_sugerida=categoria,
                tipo_sugerido=tipo,
                confianza=confianza,
                estado="pendiente",
            )
            db.add(correo)
            nuevos += 1

        db.commit()
        return SincronizarCorreosResponse(ok=True, nuevos=nuevos, omitidos=omitidos)

    except HTTPException:
        raise
    except RefreshError:
        db.rollback()
        perfil.gmail_conectado = False
        perfil.gmail_refresh_token_enc = None
        db.commit()
        return SincronizarCorreosResponse(
            ok=False, nuevos=0, omitidos=0,
            error="Se perdió el acceso a Gmail (revocado o expirado). Conéctalo de nuevo.",
        )
    except Exception:
        db.rollback()
        # El detalle técnico va al log (y a Sentry), no al cliente.
        logger.exception("Error sincronizando correos de %s", usuario.id)
        return SincronizarCorreosResponse(
            ok=False, nuevos=0, omitidos=0,
            error="No se pudo sincronizar tus correos. Intenta de nuevo en un momento.",
        )


@router.get("/pendientes", response_model=list[CorreoGastoOut])
def listar_pendientes(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    return (
        db.query(CorreoGasto)
        .filter(CorreoGasto.usuario_id == usuario.id, CorreoGasto.estado == "pendiente")
        .order_by(CorreoGasto.creado_en.desc())
        .all()
    )


@router.patch("/{correo_id}", response_model=CorreoGastoOut)
def editar_correo(
    correo_id: str,
    data: CorreoGastoUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    correo = (
        db.query(CorreoGasto)
        .filter(CorreoGasto.id == correo_id, CorreoGasto.usuario_id == usuario.id)
        .first()
    )
    if not correo:
        raise HTTPException(status_code=404, detail="Correo no encontrado")

    if data.monto is not None:
        correo.monto = data.monto
    if data.comercio is not None:
        correo.comercio = data.comercio
    if data.categoria is not None:
        correo.categoria_sugerida = data.categoria
    if data.tipo is not None:
        correo.tipo_sugerido = data.tipo

    db.commit()
    db.refresh(correo)
    return correo


@router.post("/{correo_id}/aprobar", response_model=CorreoGastoOut)
def aprobar_correo(
    correo_id: str,
    data: AprobarCorreoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    correo = (
        db.query(CorreoGasto)
        .filter(CorreoGasto.id == correo_id, CorreoGasto.usuario_id == usuario.id)
        .first()
    )
    if not correo:
        raise HTTPException(status_code=404, detail="Correo no encontrado")
    if correo.estado != "pendiente":
        raise HTTPException(status_code=400, detail="Este correo ya fue procesado")

    cuenta = (
        db.query(Cuenta)
        .filter(Cuenta.id == data.cuenta_id, Cuenta.usuario_id == usuario.id)
        .first()
    )
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    movimiento = Movimiento(
        usuario_id=usuario.id,
        cuenta_id=cuenta.id,
        descripcion=f"{correo.comercio} (correo)",
        categoria=correo.categoria_sugerida,
        tipo=correo.tipo_sugerido,
        monto=correo.monto,
        fecha=correo.recibido_en or correo.creado_en,
        fuente="email",
    )
    db.add(movimiento)

    if correo.tipo_sugerido == "income":
        cuenta.saldo += correo.monto
    elif correo.tipo_sugerido == "expense":
        cuenta.saldo -= correo.monto

    correo.estado = "aprobado"
    db.commit()
    db.refresh(movimiento)
    correo.movimiento_id = movimiento.id
    db.commit()
    db.refresh(correo)
    return correo


@router.post("/{correo_id}/descartar", response_model=CorreoGastoOut)
def descartar_correo(
    correo_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    correo = (
        db.query(CorreoGasto)
        .filter(CorreoGasto.id == correo_id, CorreoGasto.usuario_id == usuario.id)
        .first()
    )
    if not correo:
        raise HTTPException(status_code=404, detail="Correo no encontrado")
    correo.estado = "descartado"
    db.commit()
    db.refresh(correo)
    return correo
