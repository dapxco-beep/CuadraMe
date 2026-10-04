import base64
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
from app.conciliacion import detectar_banco
from app.extractos_gmail import (
    MAX_PDF_BYTES,
    abrir_pdf,
    banco_por_remitente,
    claves_candidatas,
    construir_query_extractos,
    construir_query_notificaciones,
    contiene_palabra_extracto,
    descargar_adjunto,
    detectar_periodo,
    detectar_ultimos4,
    encabezados,
    es_notificacion_transaccion,
    fecha_mensaje,
    listar_adjuntos_pdf,
    sugerir_cuenta,
)
from app.gmail_extract import detectar_tipo, extraer_comercio, extraer_moneda, extraer_monto
from app.gmail_oauth import (
    cifrar,
    cliente_gmail,
    crear_state,
    descifrar,
    intercambiar_code,
    leer_state,
    obtener_email,
    url_autorizacion,
)
from app.models import ClavePdf, Cuenta, CorreoGasto, ExtractoCorreo, Movimiento, Perfil
from app.routers.consentimientos import exigir_consentimiento, tiene_consentimiento
from app.routers.conciliacion import procesar_extracto
from app.schemas import (
    AprobarCorreoRequest,
    ClavePdfIn,
    ConciliarExtractoRequest,
    ExtractoCorreoOut,
    ProcesarExtractoRequest,
    ProcesarExtractoResponse,
    CorreoGastoOut,
    CorreoGastoUpdate,
    GmailEstado,
    SincronizarCorreosResponse,
)

router = APIRouter(prefix="/correos", tags=["correos"])
logger = logging.getLogger(__name__)

# Estados que se muestran en "Extractos encontrados" (los demás son marcas internas).
ESTADOS_VISIBLES = ("nuevo", "falta_clave", "procesado", "error")


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
        modo_pruebas=settings.gmail_modo_pruebas,
        soporte_email=settings.soporte_email,
        consentimiento=tiene_consentimiento(db, usuario.id, "lectura_correo") or not settings.exigir_consentimientos,
    )


@router.get("/gmail/conectar")
def conectar_gmail(
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Devuelve la URL a la que el frontend debe redirigir al usuario para
    autorizar el acceso de solo lectura a Gmail. Sin la autorización específica
    de lectura de correo (Ley 1581) no se genera la URL."""
    exigir_consentimiento(db, usuario.id, "lectura_correo")
    return {"url": url_autorizacion(crear_state(usuario.id))}


# Errores que Google devuelve al callback cuando el usuario no completa la autorización.
_ERRORES_SIN_ACCESO = {"access_denied", "admin_policy_enforced", "org_internal"}


@router.get("/oauth/callback")
def gmail_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    # Google devuelve ?error=access_denied (sin code) cuando el usuario cancela o,
    # con la app en modo Pruebas, cuando su correo no es 'test user'. En vez de una
    # pantalla de error, volvemos a la app con un mensaje claro: Correos lo muestra.
    if error:
        motivo = "sin_acceso" if error in _ERRORES_SIN_ACCESO else "error"
        return RedirectResponse(url=f"{settings.pwa_url}/#/correos?gmail={motivo}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Faltan datos de la autorización de Google")

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


MAX_EXTRACTOS_POR_SYNC = 8   # descargas de PDF por sincronización (cuida cuota y tiempo)
MAX_REINTENTOS_CLAVE = 5


def _clave_pdf(db: Session, usuario_id: str) -> str | None:
    fila = db.query(ClavePdf).filter(ClavePdf.usuario_id == usuario_id).first()
    if not fila:
        return None
    try:
        return descifrar(fila.clave_enc)
    except Exception:
        return None


def _crear_correo(msg: dict, usuario_id: str, modelo) -> CorreoGasto:
    """Convierte un mensaje de Gmail en un CorreoGasto 'pendiente' (sugerencia
    que el usuario debe aprobar; nunca crea movimientos)."""
    h = encabezados(msg)
    remitente = h.get("From", "")
    asunto = h.get("Subject", "")
    snippet = msg.get("snippet", "")
    texto = f"{asunto} {snippet}"
    comercio = extraer_comercio(remitente, asunto)
    resultado = classify(comercio, modelo) or clasificar_por_diccionario(f"{comercio} {texto}")
    return CorreoGasto(
        usuario_id=usuario_id,
        gmail_msg_id=msg["id"],
        remitente=remitente,
        asunto=asunto,
        snippet=snippet[:400],
        recibido_en=fecha_mensaje(msg),
        monto=extraer_monto(texto),
        moneda=extraer_moneda(texto),
        comercio=comercio,
        categoria_sugerida=resultado["categoria"] if resultado else "Otros",
        tipo_sugerido=detectar_tipo(texto),
        confianza=resultado["confianza"] if resultado else 0,
        estado="pendiente",
    )


def _sync_transacciones(gmail, db: Session, usuario_id: str, existentes: set, modelo, label_id: str | None) -> tuple[int, int]:
    """Correos con la etiqueta del usuario (si existe) + notificaciones de
    remitentes bancarios conocidos SIN etiqueta. Devuelve (nuevos, omitidos)."""
    refs: list[dict] = []
    if label_id:
        refs += gmail.users().messages().list(userId="me", labelIds=[label_id], maxResults=25).execute().get("messages", [])
    refs += gmail.users().messages().list(
        userId="me", q=construir_query_notificaciones(), maxResults=25
    ).execute().get("messages", [])

    nuevos = omitidos = 0
    vistos: set[str] = set()
    for ref in refs:
        if ref["id"] in existentes or ref["id"] in vistos:
            omitidos += 1
            continue
        vistos.add(ref["id"])
        msg = gmail.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        correo = _crear_correo(msg, usuario_id, modelo)
        con_etiqueta = bool(label_id) and label_id in (msg.get("labelIds") or [])
        # Los de la etiqueta los eligió el usuario: entran siempre. Los
        # detectados solos deben parecer una transacción real (con monto), para
        # no llenar la bandeja de publicidad del banco. Los descartados se
        # guardan como 'ignorado' para no volver a leerlos en cada sincronización.
        if not con_etiqueta and not (
            correo.monto > 0 and es_notificacion_transaccion(correo.asunto, correo.snippet)
        ):
            correo.estado = "ignorado"
        else:
            nuevos += 1
        db.add(correo)
    return nuevos, omitidos


def _analizar_adjunto(gmail, fila: ExtractoCorreo, adjunto: dict, cuentas: list, clave: str | None) -> None:
    """Descarga el PDF, intenta abrirlo y rellena banco/periodo/cuenta/estado.
    El PDF no se guarda en ningún lado."""
    try:
        pdf = descargar_adjunto(gmail, fila.gmail_msg_id, adjunto["attachment_id"])
    except Exception:
        logger.warning("No se pudo descargar un adjunto del mensaje %s", fila.gmail_msg_id)
        fila.estado = "error"
        return
    estado, texto, _ = abrir_pdf(pdf, claves_candidatas(clave))
    if estado == "ok":
        banco_texto = detectar_banco(texto)
        if banco_texto not in ("generico", "desconocido") and not fila.banco:
            fila.banco = banco_texto.capitalize()
        fila.periodo = detectar_periodo(texto, f"{fila.archivo} {fila.asunto}")
        fila.cuenta_sugerida_id = sugerir_cuenta(fila.banco, detectar_ultimos4(texto), cuentas)
        fila.estado = "nuevo"
    else:
        # Sin texto no hay periodo ni cuenta; el banco sale del remitente.
        fila.periodo = detectar_periodo("", f"{fila.archivo} {fila.asunto}")
        fila.cuenta_sugerida_id = sugerir_cuenta(fila.banco, "", cuentas) if fila.banco else None
        fila.estado = estado  # falta_clave | error


def _sync_extractos(gmail, db: Session, usuario_id: str, cuentas: list, clave: str | None) -> int:
    filas = db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == usuario_id).all()
    msgs_vistos = {f.gmail_msg_id for f in filas}

    # 1) Reintentar los que estaban esperando clave, si ahora hay una.
    if clave:
        pendientes_clave = [f for f in filas if f.estado == "falta_clave"][:MAX_REINTENTOS_CLAVE]
        for fila in pendientes_clave:
            try:
                msg = gmail.users().messages().get(userId="me", id=fila.gmail_msg_id, format="full").execute()
            except Exception:
                continue
            adj = next((a for a in listar_adjuntos_pdf(msg) if a["archivo"] == fila.archivo), None)
            if adj:
                _analizar_adjunto(gmail, fila, adj, cuentas, clave)

    # 2) Extractos nuevos.
    refs = gmail.users().messages().list(
        userId="me", q=construir_query_extractos(), maxResults=25
    ).execute().get("messages", [])
    nuevos = 0
    for ref in refs:
        if ref["id"] in msgs_vistos:
            continue
        if nuevos >= MAX_EXTRACTOS_POR_SYNC:
            break
        msg = gmail.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        h = encabezados(msg)
        remitente, asunto = h.get("From", ""), h.get("Subject", "")
        snippet = msg.get("snippet", "")
        banco = banco_por_remitente(remitente) or ""
        adjuntos = [
            a for a in listar_adjuntos_pdf(msg)
            if contiene_palabra_extracto(asunto, a["archivo"], snippet) and a["tamano"] <= MAX_PDF_BYTES
        ]
        if not adjuntos:
            # Marca para no volver a leer este correo en cada sincronización.
            db.add(ExtractoCorreo(
                usuario_id=usuario_id, gmail_msg_id=ref["id"], archivo="",
                remitente=remitente, asunto=asunto, estado="ignorado",
            ))
            continue
        for adj in adjuntos:
            fila = ExtractoCorreo(
                usuario_id=usuario_id, gmail_msg_id=ref["id"], archivo=adj["archivo"],
                remitente=remitente, asunto=asunto, banco=banco, recibido_en=fecha_mensaje(msg),
            )
            _analizar_adjunto(gmail, fila, adj, cuentas, clave)
            db.add(fila)
            nuevos += 1
    return nuevos


@router.post("/sincronizar", response_model=SincronizarCorreosResponse)
def sincronizar(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Busca en Gmail (solo lectura) sin exigir etiqueta: 1) notificaciones de
    transacciones de bancos conocidos y los correos con la etiqueta opcional
    (por defecto 'gastos'), que quedan como pendientes de revisión — nunca se
    crean movimientos solos — y 2) extractos bancarios en PDF, que quedan en
    'Extractos encontrados' listos para conciliar. Lo ya visto (gmail_msg_id)
    no se duplica."""
    verificar_limite(f"sync-gmail:{usuario.id}", 12, 3600, "Sincronizaste muchas veces seguidas. Intenta en unos minutos.")
    perfil = _get_or_create_perfil(db, usuario.id)
    if not perfil.gmail_conectado or not perfil.gmail_refresh_token_enc:
        raise HTTPException(status_code=400, detail="Gmail no está conectado")

    etiqueta = perfil.gmail_etiqueta or "gastos"

    try:
        gmail = cliente_gmail(perfil.gmail_refresh_token_enc)
        labels = gmail.users().labels().list(userId="me").execute().get("labels", [])
        label_id = next((l["id"] for l in labels if l["name"].lower() == etiqueta.lower()), None)

        existentes = {
            r[0]
            for r in db.query(CorreoGasto.gmail_msg_id).filter(CorreoGasto.usuario_id == usuario.id).all()
        }
        historial = (
            db.query(Movimiento)
            .filter(Movimiento.usuario_id == usuario.id, Movimiento.categoria != "Otros")
            .all()
        )
        modelo = build_model(
            [{"descripcion": m.descripcion, "categoria": m.categoria, "tipo": m.tipo} for m in historial]
        )

        nuevos, omitidos = _sync_transacciones(gmail, db, usuario.id, existentes, modelo, label_id)
        db.commit()

        cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all()
        extractos_nuevos = _sync_extractos(gmail, db, usuario.id, cuentas, _clave_pdf(db, usuario.id))
        db.commit()
        return SincronizarCorreosResponse(
            ok=True, nuevos=nuevos, omitidos=omitidos, extractos_nuevos=extractos_nuevos
        )

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


# ── Extractos encontrados ──────────────────────────────────────────

@router.get("/extractos", response_model=list[ExtractoCorreoOut])
def listar_extractos(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    return (
        db.query(ExtractoCorreo)
        .filter(ExtractoCorreo.usuario_id == usuario.id, ExtractoCorreo.estado.in_(ESTADOS_VISIBLES))
        .order_by(ExtractoCorreo.recibido_en.desc())
        .limit(50)
        .all()
    )


@router.post("/extractos/{extracto_id}/conciliar", response_model=ProcesarExtractoResponse)
def conciliar_extracto(
    extracto_id: str,
    data: ConciliarExtractoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Vuelve a descargar el PDF desde Gmail y lo pasa por la conciliación
    existente (/conciliacion/procesar). Devuelve la misma respuesta, con el
    historial_id para abrir la revisión."""
    verificar_limite(f"conciliar-gmail:{usuario.id}", 20, 3600, "Conciliaste muchos extractos seguidos. Intenta en un rato.")
    fila = (
        db.query(ExtractoCorreo)
        .filter(ExtractoCorreo.id == extracto_id, ExtractoCorreo.usuario_id == usuario.id)
        .first()
    )
    if not fila:
        raise HTTPException(status_code=404, detail="Extracto no encontrado")
    perfil = _get_or_create_perfil(db, usuario.id)
    if not perfil.gmail_conectado or not perfil.gmail_refresh_token_enc:
        raise HTTPException(status_code=400, detail="Gmail no está conectado")

    try:
        gmail = cliente_gmail(perfil.gmail_refresh_token_enc)
        msg = gmail.users().messages().get(userId="me", id=fila.gmail_msg_id, format="full").execute()
        adj = next((a for a in listar_adjuntos_pdf(msg) if a["archivo"] == fila.archivo), None)
        if not adj:
            return ProcesarExtractoResponse(ok=False, error="El adjunto ya no está en tu correo.")
        pdf = descargar_adjunto(gmail, fila.gmail_msg_id, adj["attachment_id"])
    except RefreshError:
        return ProcesarExtractoResponse(ok=False, error="Se perdió el acceso a Gmail. Conéctalo de nuevo.")
    except Exception:
        logger.exception("Error descargando extracto de %s", usuario.id)
        return ProcesarExtractoResponse(ok=False, error="No se pudo descargar el extracto. Intenta de nuevo.")

    estado, _texto, clave_usada = abrir_pdf(pdf, claves_candidatas(_clave_pdf(db, usuario.id)))
    if estado == "falta_clave":
        fila.estado = "falta_clave"
        db.commit()
        return ProcesarExtractoResponse(
            ok=False, error="Este extracto está cifrado: guarda la clave del PDF (normalmente tu cédula) en los ajustes."
        )
    if estado != "ok":
        fila.estado = "error"
        db.commit()
        return ProcesarExtractoResponse(ok=False, error="No se pudo leer este PDF.")

    resp = procesar_extracto(
        ProcesarExtractoRequest(
            pdf_base64=base64.b64encode(pdf).decode(), cuenta_id=data.cuenta_id, password=clave_usada or ""
        ),
        db=db,
        usuario=usuario,
    )
    if resp.ok:
        fila.estado = "procesado"
        fila.historial_id = resp.historial_id
        db.commit()
    return resp


@router.post("/extractos/{extracto_id}/descartar")
def descartar_extracto(
    extracto_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    fila = (
        db.query(ExtractoCorreo)
        .filter(ExtractoCorreo.id == extracto_id, ExtractoCorreo.usuario_id == usuario.id)
        .first()
    )
    if not fila:
        raise HTTPException(status_code=404, detail="Extracto no encontrado")
    fila.estado = "descartado"
    db.commit()
    return {"ok": True}


# ── Clave de los PDF ───────────────────────────────────────────────

@router.get("/clave-pdf")
def estado_clave_pdf(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Solo dice si hay una clave guardada; nunca la devuelve."""
    existe = db.query(ClavePdf).filter(ClavePdf.usuario_id == usuario.id).first() is not None
    return {"configurada": existe}


@router.put("/clave-pdf")
def guardar_clave_pdf(
    data: ClavePdfIn,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    verificar_limite(f"clave-pdf:{usuario.id}", 20, 3600, "Cambiaste la clave muchas veces. Intenta en un rato.")
    fila = db.query(ClavePdf).filter(ClavePdf.usuario_id == usuario.id).first()
    cifrada = cifrar(data.clave.strip())
    if fila:
        fila.clave_enc = cifrada
    else:
        db.add(ClavePdf(usuario_id=usuario.id, clave_enc=cifrada))
    db.commit()
    return {"ok": True, "configurada": True}


@router.delete("/clave-pdf")
def borrar_clave_pdf(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    db.query(ClavePdf).filter(ClavePdf.usuario_id == usuario.id).delete()
    db.commit()
    return {"ok": True, "configurada": False}


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
        # La categoría la sugirió la app al leer el correo: queda por revisar
        # salvo que sea 'Otros' (que ya aparece en la vista por revisar).
        cat_origen="sugerida" if correo.categoria_sugerida != "Otros" else None,
        cat_confirmada=correo.categoria_sugerida == "Otros",
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
