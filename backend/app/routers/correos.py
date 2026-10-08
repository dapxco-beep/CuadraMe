import base64
import json
import logging
import time

from google.auth.exceptions import RefreshError
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, cron_autorizado, get_current_user
from app.crons import Corrida, MarcaCron, reclamar_marca
from app.push import enviar_push
from app.autocat import ClasificadorUsuario, aplicar_a_anteriores, guardar_regla_aprendida
from app.config import settings
from app.limites import verificar_limite
from app.limites_diarios import consumir_cupo_diario
from app.database import get_db
from app.conciliacion import detectar_banco
from app.contabilidad import con_marca_traslado
from app.extractos_conciliados import (
    ESTADO_YA_CONCILIADO,
    depurar_conciliados,
    evidencia_conciliado,
    mes_del_extracto,
    periodo_en_asunto,
)
from app.extractos_gmail import (
    MAX_PDF_BYTES,
    abrir_pdf,
    banco_por_remitente,
    claves_candidatas,
    construir_query_extractos,
    construir_query_notificaciones,
    contiene_palabra_extracto,
    cuentas_del_banco,
    descargar_adjunto,
    detectar_periodo,
    detectar_ultimos4,
    encabezados,
    es_notificacion_transaccion,
    fecha_mensaje,
    inferir_cuenta_por_remitente,
    listar_adjuntos_pdf,
    sugerir_cuenta,
)
from app.gmail_extract import detectar_tipo, es_posible_traslado_propio, extraer_comercio, extraer_moneda, extraer_monto
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
from app.models import Categoria, ClavePdf, Cuenta, CorreoGasto, ExtractoCorreo, HistorialExtracto, Movimiento, Perfil, SyncGmail
from app.routers.consentimientos import exigir_consentimiento, tiene_consentimiento
from app.routers.conciliacion import procesar_extracto
from app.utiles import utc_a_co
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

# Estados que devuelve "Extractos encontrados" (los demás son marcas internas).
# 'ya_conciliado' viaja aparte de lo pendiente: la pantalla lo muestra plegado.
ESTADOS_VISIBLES = ("nuevo", "falta_clave", "procesado", "error", ESTADO_YA_CONCILIADO)


MENSAJE_MONTO_INVALIDO = "El monto debe ser mayor que cero: escríbelo antes de aprobar"


def _get_or_create_perfil(db: Session, usuario_id: str) -> Perfil:
    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
    if not perfil:
        perfil = Perfil(usuario_id=usuario_id, plan="free")
        db.add(perfil)
        db.commit()
        db.refresh(perfil)
    return perfil


def _con_cuenta(db: Session, usuario_id: str, correos: list[CorreoGasto]) -> list[CorreoGastoOut]:
    """Agrega a cada correo el banco del remitente y la cuenta que le corresponde
    (o `falta_cuenta` si el usuario no tiene una de ese banco)."""
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).all()
    clasificador = ClasificadorUsuario(db, usuario_id) if any(c.estado == "pendiente" for c in correos) else None
    salida = []
    for c in correos:
        o = CorreoGastoOut.model_validate(c)
        o.banco_detectado, o.cuenta_sugerida_id, o.falta_cuenta = inferir_cuenta_por_remitente(c.remitente, cuentas)
        o.falta_monto = (c.monto or 0) <= 0
        if c.estado == "pendiente":
            o.preguntar_categoria = c.categoria_sugerida == "Otros"
            # La razón se recalcula: solo vale si la categoría sigue siendo la que sugirió el clasificador.
            r = clasificador.clasificar(c.comercio, f"{c.asunto} {c.snippet}") if clasificador else None
            o.razon_categoria = r.get("razon") if r and r["categoria"] == c.categoria_sugerida else None
        salida.append(o)
    return salida


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

    # El correo es solo informativo: si Google no lo entrega, la conexión sigue valiendo.
    try:
        email = obtener_email(tokens["access_token"])
    except Exception:
        logger.warning("No se pudo leer el correo de la cuenta de Gmail conectada")
        email = ""

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


def _crear_correo(msg: dict, usuario_id: str, modelo: ClasificadorUsuario) -> CorreoGasto:
    """Convierte un mensaje de Gmail en un CorreoGasto 'pendiente' (sugerencia
    que el usuario debe aprobar; nunca crea movimientos). La categoría la decide
    el clasificador del usuario (reglas -> aprendido -> diccionario -> 'Otros')."""
    h = encabezados(msg)
    remitente = h.get("From", "")
    asunto = h.get("Subject", "")
    snippet = msg.get("snippet", "")
    texto = f"{asunto} {snippet}"
    comercio = extraer_comercio(remitente, asunto, snippet)
    resultado = modelo.clasificar(comercio, texto)
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


def _marcar_si_conciliado(db: Session, fila: ExtractoCorreo) -> bool:
    """Si el banco+cuenta+periodo de este extracto ya quedó conciliado (por Gmail
    o por subida manual) se guarda como 'ya_conciliado': no se muestra como
    pendiente ni cuenta en las tareas. Solo con periodo explícito (nunca se
    adivina por la fecha del correo) y cuenta conocida."""
    if not fila.periodo or not fila.cuenta_sugerida_id:
        return False
    ev = evidencia_conciliado(db, fila.usuario_id, fila.cuenta_sugerida_id, mes_del_extracto(fila.periodo, None))
    if not ev:
        return False
    fila.estado = ESTADO_YA_CONCILIADO
    fila.historial_id = fila.historial_id or ev["historial_id"]
    return True


def _analizar_adjunto(gmail, db: Session, fila: ExtractoCorreo, adjunto: dict, cuentas: list, clave: str | None) -> None:
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
        _marcar_si_conciliado(db, fila)
    else:
        # Sin texto no hay periodo ni cuenta; el banco sale del remitente.
        fila.periodo = detectar_periodo("", f"{fila.archivo} {fila.asunto}")
        fila.cuenta_sugerida_id = sugerir_cuenta(fila.banco, "", cuentas) if fila.banco else None
        fila.estado = estado  # falta_clave | error


# ── Sincronización por lotes ───────────────────────────────────────
# Cada request lee como mucho LOTE_CORREOS correos y descarga LOTE_PDFS PDF (para
# no pasar el timeout de Railway). El estado queda en `sync_gmail` y el cliente
# repite la llamada hasta que `completado` sea True. Lo ya visto (gmail_msg_id)
# se salta sin costo, así que repetir o reanudar nunca duplica.
LOTE_CORREOS = 40
LOTE_PDFS = 5
PAGINA_GMAIL = 100
DIAS_PRIMERA_SYNC = 90
SOLAPE_DIAS = 1
MAX_CORRIDA_HORAS = 6
FASES = ("etiqueta", "notificaciones", "extractos")


def _get_or_create_sync(db: Session, usuario_id: str) -> SyncGmail:
    sync = db.query(SyncGmail).filter(SyncGmail.usuario_id == usuario_id).first()
    if not sync:
        sync = SyncGmail(usuario_id=usuario_id)
        db.add(sync)
        db.flush()
    return sync


def _consulta_fase(fase: str, desde: datetime) -> dict:
    if fase == "notificaciones":
        return {"q": construir_query_notificaciones(desde=desde)}
    if fase == "extractos":
        return {"q": construir_query_extractos(desde=desde)}
    return {"q": f"after:{desde:%Y/%m/%d}"}


def _listar(gmail, fase: str, desde: datetime, label_id: str | None, token: str | None, max_results: int) -> dict:
    kw = _consulta_fase(fase, desde)
    if fase == "etiqueta":
        kw["labelIds"] = [label_id]
    if token:
        kw["pageToken"] = token
    return gmail.users().messages().list(userId="me", maxResults=max_results, **kw).execute()


def _iniciar_corrida(gmail, sync: SyncGmail, label_id: str | None, completa: bool, dias: int) -> None:
    ahora = datetime.utcnow()
    if completa or not sync.ultima_sync:
        desde = ahora - timedelta(days=dias)
    else:
        desde = sync.ultima_sync - timedelta(days=SOLAPE_DIAS)
    sync.en_curso = True
    sync.desde = desde
    sync.iniciada_en = ahora
    sync.fase = FASES[0] if label_id else FASES[1]
    sync.fase_iniciada = False
    sync.cursor_token = None
    sync.cursor_ids = "[]"
    sync.reintento_clave_hecho = False
    sync.leidos = sync.nuevos = sync.omitidos = sync.extractos_nuevos = 0
    # Estimación del total (una llamada barata por fase) para la barra de progreso.
    total = 0
    for fase in FASES:
        if fase == "etiqueta" and not label_id:
            continue
        r = _listar(gmail, fase, desde, label_id, None, 1)
        total += int(r.get("resultSizeEstimate", len(r.get("messages", []))) or 0)
    sync.total_estimado = total


def _reintentar_claves(gmail, db: Session, usuario_id: str, cuentas: list, clave: str | None) -> None:
    """Los extractos que esperaban clave se reintentan SOLO si el usuario guardó
    una clave nueva después del último intento (así una clave que no sirve no
    obliga a descargar los mismos PDF en cada sincronización). `creado_en` hace
    de marca del último intento: se actualiza si la clave volvió a fallar."""
    if not clave:
        return
    fila_clave = db.query(ClavePdf).filter(ClavePdf.usuario_id == usuario_id).first()
    if not fila_clave:
        return
    filas = (
        db.query(ExtractoCorreo)
        .filter(
            ExtractoCorreo.usuario_id == usuario_id,
            ExtractoCorreo.estado == "falta_clave",
            ExtractoCorreo.creado_en < (fila_clave.actualizado_en or datetime.min),
        )
        .limit(MAX_REINTENTOS_CLAVE)
        .all()
    )
    for fila in filas:
        try:
            msg = gmail.users().messages().get(userId="me", id=fila.gmail_msg_id, format="full").execute()
        except Exception:
            continue
        adj = next((a for a in listar_adjuntos_pdf(msg) if a["archivo"] == fila.archivo), None)
        if adj:
            _analizar_adjunto(gmail, db, fila, adj, cuentas, clave)
            if fila.estado == "falta_clave":
                fila.creado_en = datetime.utcnow()


def _procesar_transaccion(gmail, db, usuario_id, ref_id, modelo, label_id, existentes: set) -> bool:
    """Lee un correo y lo guarda. True si quedó como candidato (no ignorado)."""
    msg = gmail.users().messages().get(userId="me", id=ref_id, format="full").execute()
    correo = _crear_correo(msg, usuario_id, modelo)
    con_etiqueta = bool(label_id) and label_id in (msg.get("labelIds") or [])
    # Un correo sin monto no es un movimiento (publicidad, "tu pedido fue entregado",
    # "llegó tu extracto"): no se ofrece para revisar ni para conciliar, aunque lo
    # haya marcado la etiqueta del usuario. Con monto entran los de la etiqueta, y los
    # detectados solos solo si además parecen una transacción real. Los descartados se
    # guardan 'ignorado' y no se releen.
    tiene_monto = (correo.monto or 0) > 0
    candidato = tiene_monto and (con_etiqueta or es_notificacion_transaccion(correo.asunto, correo.snippet))
    if not candidato:
        correo.estado = "ignorado"
    db.add(correo)
    existentes.add(ref_id)
    return candidato


def _procesar_extracto(gmail, db, usuario_id, ref_id, cuentas, clave, vistos: set) -> tuple[int, int]:
    """Lee un correo con posible extracto. Devuelve (PDF descargados, extractos
    nuevos para el usuario). Si el asunto ya dice el periodo ('extracto de
    septiembre') y ese periodo de esa cuenta ya está conciliado, se guarda como
    'ya_conciliado' SIN descargar el PDF."""
    msg = gmail.users().messages().get(userId="me", id=ref_id, format="full").execute()
    h = encabezados(msg)
    remitente, asunto = h.get("From", ""), h.get("Subject", "")
    snippet = msg.get("snippet", "")
    banco = banco_por_remitente(remitente) or ""
    adjuntos = [
        a for a in listar_adjuntos_pdf(msg)
        if contiene_palabra_extracto(asunto, a["archivo"], snippet) and a["tamano"] <= MAX_PDF_BYTES
    ]
    vistos.add(ref_id)
    if not adjuntos:
        # Marca para no volver a leer este correo en cada sincronización.
        db.add(ExtractoCorreo(
            usuario_id=usuario_id, gmail_msg_id=ref_id, archivo="",
            remitente=remitente, asunto=asunto, estado="ignorado",
        ))
        return 0, 0
    recibido = fecha_mensaje(msg)
    # ¿Se puede saber el periodo y la cuenta sin abrir el PDF?
    cuenta_unica = cuentas_del_banco(banco, cuentas) if banco else []
    periodo_previo = periodo_en_asunto(asunto, recibido)
    ev = (
        evidencia_conciliado(db, usuario_id, cuenta_unica[0].id, mes_del_extracto(periodo_previo, None))
        if len(cuenta_unica) == 1 and periodo_previo else None
    )
    descargados = nuevos = 0
    for adj in adjuntos:
        fila = ExtractoCorreo(
            usuario_id=usuario_id, gmail_msg_id=ref_id, archivo=adj["archivo"],
            remitente=remitente, asunto=asunto, banco=banco, recibido_en=recibido,
        )
        if ev:
            fila.periodo, fila.cuenta_sugerida_id = periodo_previo, cuenta_unica[0].id
            fila.estado, fila.historial_id = ESTADO_YA_CONCILIADO, ev["historial_id"]
        else:
            _analizar_adjunto(gmail, db, fila, adj, cuentas, clave)
            descargados += 1
            nuevos += fila.estado != ESTADO_YA_CONCILIADO
        db.add(fila)
    return descargados, nuevos


def _correr_lote(gmail, db: Session, usuario_id: str, sync: SyncGmail, label_id: str | None, modelo, cuentas, clave) -> None:
    """Avanza la corrida hasta agotar el presupuesto del lote o terminar."""
    gets, pdfs = LOTE_CORREOS, LOTE_PDFS
    existentes = {r[0] for r in db.query(CorreoGasto.gmail_msg_id).filter(CorreoGasto.usuario_id == usuario_id).all()}
    vistos_ext = {r[0] for r in db.query(ExtractoCorreo.gmail_msg_id).filter(ExtractoCorreo.usuario_id == usuario_id).all()}

    while sync.en_curso:
        ids = json.loads(sync.cursor_ids or "[]")
        if not ids:
            if sync.fase_iniciada and not sync.cursor_token:
                # La fase terminó: siguiente, o fin de la corrida.
                i = FASES.index(sync.fase) + 1
                if i >= len(FASES):
                    sync.en_curso = False
                    sync.ultima_sync = datetime.utcnow()
                    sync.ultimo_leidos, sync.ultimo_nuevos = sync.leidos, sync.nuevos
                    sync.ultimo_extractos = sync.extractos_nuevos
                    sync.ultimo_error = None
                    sync.total_estimado = max(sync.total_estimado, sync.leidos)
                    return
                sync.fase, sync.fase_iniciada, sync.cursor_token = FASES[i], False, None
                continue
            if sync.fase == "extractos" and not sync.reintento_clave_hecho:
                _reintentar_claves(gmail, db, usuario_id, cuentas, clave)
                sync.reintento_clave_hecho = True
            r = _listar(gmail, sync.fase, sync.desde, label_id, sync.cursor_token, PAGINA_GMAIL)
            sync.cursor_token = r.get("nextPageToken")
            sync.fase_iniciada = True
            ids = [m["id"] for m in r.get("messages", [])]
            sync.cursor_ids = json.dumps(ids)
            continue

        ref_id = ids[0]
        if sync.fase == "extractos":
            conocido = ref_id in vistos_ext
        else:
            conocido = ref_id in existentes
        if not conocido:
            if gets <= 0 or (sync.fase == "extractos" and pdfs <= 0):
                return  # se acabó el presupuesto: el resto queda para el siguiente lote
            gets -= 1
            if sync.fase == "extractos":
                descargados, n_nuevos = _procesar_extracto(gmail, db, usuario_id, ref_id, cuentas, clave, vistos_ext)
                pdfs -= descargados
                sync.extractos_nuevos += n_nuevos
            elif _procesar_transaccion(gmail, db, usuario_id, ref_id, modelo, label_id, existentes):
                sync.nuevos += 1
        else:
            sync.omitidos += 1
        sync.leidos += 1
        sync.cursor_ids = json.dumps(ids[1:])


def _respuesta_sync(sync: SyncGmail) -> SincronizarCorreosResponse:
    completado = not sync.en_curso
    return SincronizarCorreosResponse(
        ok=True,
        nuevos=sync.nuevos if sync.en_curso else sync.ultimo_nuevos,
        omitidos=sync.omitidos,
        extractos_nuevos=sync.extractos_nuevos if sync.en_curso else sync.ultimo_extractos,
        leidos=sync.leidos if sync.en_curso else sync.ultimo_leidos,
        total_estimado=max(sync.total_estimado, sync.leidos),
        pendientes=0 if completado else max(sync.total_estimado - sync.leidos, 1),
        completado=completado,
        extractos_encontrados=sync.extractos_nuevos if sync.en_curso else sync.ultimo_extractos,
    )


def _lote_de_sincronizacion(db: Session, usuario_id: str, perfil: Perfil, completa: bool = False,
                            dias: int = DIAS_PRIMERA_SYNC) -> tuple[SyncGmail, int, int]:
    """UN lote de la sincronización de Gmail (sin sesión HTTP): lo usan el botón del usuario
    y el cron. Inicia o retoma la corrida, lee un lote y hace commit. Devuelve (sync, novedades
    de ESTE lote: correos por revisar, extractos nuevos). Puede lanzar RefreshError y errores
    de Gmail: quien llama decide qué hacer."""
    etiqueta = perfil.gmail_etiqueta or "gastos"
    gmail = cliente_gmail(perfil.gmail_refresh_token_enc)
    labels = gmail.users().labels().list(userId="me").execute().get("labels", [])
    label_id = next((l["id"] for l in labels if l["name"].lower() == etiqueta.lower()), None)

    sync = _get_or_create_sync(db, usuario_id)
    vencida = bool(sync.iniciada_en) and datetime.utcnow() - sync.iniciada_en > timedelta(hours=MAX_CORRIDA_HORAS)
    if completa or not sync.en_curso or vencida:
        _iniciar_corrida(gmail, sync, label_id, completa, dias)
    # Si la etiqueta desapareció a mitad de corrida, se salta esa fase.
    if sync.fase == "etiqueta" and not label_id:
        sync.fase, sync.fase_iniciada, sync.cursor_token, sync.cursor_ids = "notificaciones", False, None, "[]"

    # Los contadores de la corrida son acumulados: lo nuevo de este lote es la diferencia.
    antes_n, antes_e = (sync.nuevos or 0), (sync.extractos_nuevos or 0)
    # Mismo clasificador que la conciliación: reglas del usuario, lo que aprendió
    # de sus movimientos confirmados, diccionario y, si nada sirve, 'Otros'.
    modelo = ClasificadorUsuario(db, usuario_id)
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).all()
    _correr_lote(gmail, db, usuario_id, sync, label_id, modelo, cuentas, _clave_pdf(db, usuario_id))
    if sync.en_curso:
        despues_n, despues_e = (sync.nuevos or 0), (sync.extractos_nuevos or 0)
    else:
        despues_n, despues_e = (sync.ultimo_nuevos or 0), (sync.ultimo_extractos or 0)
    db.commit()
    return sync, max(0, despues_n - antes_n), max(0, despues_e - antes_e)


@router.post("/sincronizar", response_model=SincronizarCorreosResponse)
def sincronizar(
    completa: bool = False,
    dias: int = Query(DIAS_PRIMERA_SYNC, ge=7, le=365),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Sincroniza Gmail (solo lectura) POR LOTES: 1) notificaciones de bancos
    conocidos y correos con la etiqueta opcional, que quedan pendientes de
    revisión — nunca se crean movimientos solos — y 2) extractos en PDF.
    Primera vez: últimos `dias` (90). Luego: incremental desde la última
    sincronización completa, con 1 día de solape. `completa=true` fuerza la
    ventana larga. Cada llamada hace un lote y devuelve el progreso; repetirla
    hasta `completado` (reanuda donde quedó, sin duplicar)."""
    verificar_limite(f"sync-gmail:{usuario.id}", 80, 3600, "Sincronizaste muchas veces seguidas. Intenta en unos minutos.")
    consumir_cupo_diario(db, usuario.id, "sync-gmail")
    perfil = _get_or_create_perfil(db, usuario.id)
    if not perfil.gmail_conectado or not perfil.gmail_refresh_token_enc:
        raise HTTPException(status_code=400, detail="Gmail no está conectado")

    try:
        sync, _movs, _exts = _lote_de_sincronizacion(db, usuario.id, perfil, completa, dias)
        return _respuesta_sync(sync)

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
        try:
            sync = _get_or_create_sync(db, usuario.id)
            sync.ultimo_error = "No se pudo sincronizar tus correos."
            sync.ultimo_error_en = datetime.utcnow()
            db.commit()
        except Exception:
            db.rollback()
        return SincronizarCorreosResponse(
            ok=False, nuevos=0, omitidos=0,
            error="No se pudo sincronizar tus correos. Intenta de nuevo en un momento.",
        )


# ── Cron: sincronización periódica ─────────────────────────────────

PRESUPUESTO_CRON_SEGUNDOS = 45  # tiempo total por llamada; lo que falte sigue en la próxima (cursor)
MAX_USUARIOS_POR_CRON = 40  # tope de usuarios por llamada (con 100+ usuarios se reparte en varias)
CLAVE_INTENTO_CRON = "gmail_cron_intento"  # marca por usuario con el último intento del cron
_reloj = time.monotonic  # se puede sustituir en pruebas


def _aviso_correos_nuevos(movimientos: int, extractos: int) -> tuple[str, str]:
    """(título, cuerpo) del push resumen. `movimientos` y `extractos` ya son lo nuevo del lote."""
    if movimientos and extractos:
        cuerpo = (f"Encontré {movimientos} movimiento{'s' if movimientos != 1 else ''} nuevo{'s' if movimientos != 1 else ''} "
                  f"y {extractos} extracto{'s' if extractos != 1 else ''} en tu correo")
    elif movimientos:
        cuerpo = f"Encontré {movimientos} movimiento{'s' if movimientos != 1 else ''} nuevo{'s' if movimientos != 1 else ''} en tu correo"
    else:
        cuerpo = f"Encontré {extractos} extracto{'s' if extractos != 1 else ''} nuevo{'s' if extractos != 1 else ''} en tu correo para conciliar"
    return "Novedades en tu correo", cuerpo


@router.post("/cron/sincronizar")
def cron_sincronizar(db: Session = Depends(get_db), x_cron_secret: str = Header(default="")):
    """Sincronización periódica de Gmail (cron externo, header X-Cron-Secret; recomendado cada
    3 horas, hora Colombia). Para cada usuario con Gmail conectado Y con la autorización vigente
    de lectura de correo corre UN lote incremental de la misma sincronización del botón. Tiene
    presupuesto de tiempo (~45 s): si se acaba, corta y la siguiente ejecución continúa desde
    el cursor de cada usuario (quien lleva más tiempo sin sincronizar va primero). Un fallo de un
    usuario no detiene a los demás. Es idempotente: sin correos nuevos no cambia nada ni avisa.
    Si el lote encontró movimientos o extractos nuevos, manda UN push resumen a ese usuario."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")

    inicio = _reloj()
    perfiles = (
        db.query(Perfil)
        .filter(Perfil.gmail_conectado.is_(True), Perfil.gmail_refresh_token_enc.isnot(None))
        .all()
    )
    ultimas = {s.usuario_id: s.ultima_sync for s in db.query(SyncGmail).all()}
    # Justicia con 100+ usuarios: va primero a quien lleva MÁS tiempo sin que el cron lo
    # intente (nunca intentado = primero). Se ordena por el último INTENTO, no por la última
    # sincronización completa: así quien tiene una corrida larga en curso, o falla siempre,
    # no se queda al frente acaparando el presupuesto de tiempo. ISO en UTC ordena como texto.
    intentos = {m.usuario_id: m.valor for m in db.query(MarcaCron).filter(MarcaCron.clave == CLAVE_INTENTO_CRON)}
    perfiles.sort(key=lambda p: (intentos.get(p.usuario_id, ""), ultimas.get(p.usuario_id) or datetime.min, p.usuario_id))

    corrida = Corrida(db)
    nuevos = sin_consentimiento = desconectados = avisados = 0
    pendientes_por_tiempo = 0
    for i, perfil in enumerate(perfiles):
        # Dos topes: tiempo total y usuarios por llamada. Lo que falte sigue en la próxima
        # ejecución (el cursor de cada usuario y el orden por último intento lo retoman).
        if _reloj() - inicio >= PRESUPUESTO_CRON_SEGUNDOS or i >= MAX_USUARIOS_POR_CRON:
            pendientes_por_tiempo = len(perfiles) - i
            break
        uid = perfil.usuario_id
        # Se anota el intento ANTES de trabajar: si el usuario falla o se corta el proceso,
        # igual pasa al final de la fila en lugar de bloquear a los demás.
        reclamar_marca(db, uid, CLAVE_INTENTO_CRON, datetime.utcnow().isoformat())
        with corrida.aislar(uid):
            if not tiene_consentimiento(db, uid, "lectura_correo"):
                sin_consentimiento += 1
                continue
            try:
                _sync, movs, exts = _lote_de_sincronizacion(db, uid, perfil)
            except RefreshError:
                db.rollback()
                perfil.gmail_conectado = False
                perfil.gmail_refresh_token_enc = None
                db.commit()
                desconectados += 1
                continue
            if movs or exts:
                nuevos += movs + exts
                try:
                    titulo, cuerpo = _aviso_correos_nuevos(movs, exts)
                    if enviar_push(db, uid, titulo, cuerpo, "/correos"):
                        avisados += 1
                except Exception:
                    logger.exception("Cron correos: no se pudo avisar al usuario %s", uid)
    return {
        "ok": True, **corrida.resumen(), "nuevos": nuevos, "avisados": avisados,
        "sin_consentimiento": sin_consentimiento, "desconectados": desconectados,
        "pendientes_por_tiempo": pendientes_por_tiempo,
    }


# ── Lista completa de correos (con filtros y paginación) ───────────

@router.get("/lista", response_model=list[CorreoGastoOut])
def listar_correos(
    filtro: str = Query("nuevos", pattern="^(nuevos|aprobados|ignorados|descartados|todos)$"),
    limite: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Correos leídos por estado, de a `limite` ('cargar más' con `offset`)."""
    estados = {"nuevos": "pendiente", "aprobados": "aprobado", "ignorados": "ignorado", "descartados": "descartado"}
    q = db.query(CorreoGasto).filter(CorreoGasto.usuario_id == usuario.id)
    if filtro != "todos":
        q = q.filter(CorreoGasto.estado == estados[filtro])
    return _con_cuenta(db, usuario.id, q.order_by(CorreoGasto.creado_en.desc(), CorreoGasto.id).offset(offset).limit(limite).all())


# ── Extractos encontrados ──────────────────────────────────────────

@router.get("/extractos", response_model=list[ExtractoCorreoOut])
def listar_extractos(
    estado: str | None = Query(None, pattern="^(nuevo|falta_clave|procesado|error|descartado|ya_conciliado)$"),
    limite: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Extractos encontrados; `estado` filtra y `limite`/`offset` paginan. Los de
    un periodo que ya se concilió salen como 'ya_conciliado' (con sus movimientos
    cruzados) y nunca como 'nuevo'."""
    depurar_conciliados(db, usuario.id)
    q = db.query(ExtractoCorreo).filter(
        ExtractoCorreo.usuario_id == usuario.id,
        ExtractoCorreo.estado == estado if estado else ExtractoCorreo.estado.in_(ESTADOS_VISIBLES),
    )
    filas = q.order_by(ExtractoCorreo.recibido_en.desc(), ExtractoCorreo.id).offset(offset).limit(limite).all()
    cruzados = {
        h.id: (h.exactos or 0) + (h.aproximados or 0)
        for h in db.query(HistorialExtracto).filter(
            HistorialExtracto.usuario_id == usuario.id,
            HistorialExtracto.id.in_([f.historial_id for f in filas if f.historial_id] or [""]),
        )
    }
    salida = []
    for f in filas:
        o = ExtractoCorreoOut.model_validate(f)
        # Extractos viejos pueden no traer el banco guardado: se deduce del remitente.
        o.banco = o.banco or banco_por_remitente(f.remitente) or ""
        o.cruzados = cruzados.get(f.historial_id)
        if f.estado == ESTADO_YA_CONCILIADO and o.cruzados is None:
            ev = evidencia_conciliado(db, usuario.id, f.cuenta_sugerida_id, mes_del_extracto(f.periodo, None))
            o.cruzados = ev["cruzados"] if ev else None
        salida.append(o)
    return salida


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
    verificar_limite(f"conciliar-gmail:{usuario.id}", 60, 3600, "Conciliaste muchos extractos seguidos. Podrás seguir en {espera}.")
    consumir_cupo_diario(db, usuario.id, "conciliar-gmail")
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
    return _con_cuenta(db, usuario.id, (
        db.query(CorreoGasto)
        .filter(
            CorreoGasto.usuario_id == usuario.id,
            CorreoGasto.estado == "pendiente",
            CorreoGasto.monto > 0,  # sin monto no hay nada que registrar ni conciliar
        )
        .order_by(CorreoGasto.creado_en.desc())
        .all()
    ))


def _validar_categoria(db: Session, usuario_id: str, categoria: str) -> None:
    """La categoría elegida tiene que estar en la lista del usuario (si ya tiene una)."""
    hay_lista = db.query(Categoria.id).filter(Categoria.usuario_id == usuario_id).first()
    if hay_lista and not db.query(Categoria.id).filter(
        Categoria.usuario_id == usuario_id, Categoria.nombre == categoria
    ).first():
        raise HTTPException(status_code=400, detail="Esa categoría no existe en tu lista")


def _aprender_de_correo(db: Session, usuario_id: str, correo: CorreoGasto, categoria: str, anteriores: bool) -> dict:
    """Guarda la regla del comercio del correo (misma huella que en la conciliación:
    una por comercio, si ya hay se actualiza) y, si se pide, recategoriza los
    movimientos anteriores. Sin commit. 'Otros' nunca se aprende."""
    if not categoria or categoria == "Otros":
        return {}
    r = guardar_regla_aprendida(db, usuario_id, correo.comercio, categoria, tipo=correo.tipo_sugerido)
    n = aplicar_a_anteriores(db, usuario_id, r["huella"], categoria) if r["guardada"] and anteriores else 0
    return {"regla_guardada": r["guardada"], "regla_omitida": r.get("motivo"), "anteriores_actualizados": n}


def _con_aprendizaje(o: CorreoGastoOut, aprendido: dict) -> CorreoGastoOut:
    for k, v in aprendido.items():
        setattr(o, k, v)
    return o


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
        if data.monto <= 0:
            raise HTTPException(status_code=400, detail=MENSAJE_MONTO_INVALIDO)
        correo.monto = data.monto
    if data.comercio is not None:
        correo.comercio = data.comercio
    if data.tipo is not None:
        correo.tipo_sugerido = data.tipo
    aprendido: dict = {}
    if data.categoria is not None:
        _validar_categoria(db, usuario.id, data.categoria)
        cambio = data.categoria != correo.categoria_sugerida
        correo.categoria_sugerida = data.categoria
        if cambio and data.recordar:
            aprendido = _aprender_de_correo(db, usuario.id, correo, data.categoria, data.aplicar_anteriores)

    db.commit()
    db.refresh(correo)
    return _con_aprendizaje(_con_cuenta(db, usuario.id, [correo])[0], aprendido)


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

    # Un movimiento de 0 (o negativo) no existe: si el correo no trajo el monto, hay que escribirlo.
    if data.monto is not None:
        if data.monto <= 0:
            raise HTTPException(status_code=400, detail=MENSAJE_MONTO_INVALIDO)
        correo.monto = data.monto
    if (correo.monto or 0) <= 0:
        raise HTTPException(status_code=400, detail=MENSAJE_MONTO_INVALIDO)

    cuenta = (
        db.query(Cuenta)
        .filter(Cuenta.id == data.cuenta_id, Cuenta.usuario_id == usuario.id)
        .first()
        if data.cuenta_id else None
    )
    if not cuenta:
        # Nunca se asume una cuenta: si el correo es de un banco que el usuario
        # no tiene como cuenta, se le dice cuál crear.
        cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all()
        banco, _sug, falta = inferir_cuenta_por_remitente(correo.remitente, cuentas)
        if falta:
            raise HTTPException(status_code=400, detail=f"No tienes una cuenta {banco}: créala o elige otra")
        raise HTTPException(status_code=400, detail="Elige la cuenta a la que pertenece este movimiento")

    # Si el usuario eligió otra categoría al aprobar, esa manda (y queda confirmada).
    eligio = data.categoria is not None and data.categoria != correo.categoria_sugerida
    aprendido: dict = {}
    if data.categoria is not None:
        _validar_categoria(db, usuario.id, data.categoria)
        correo.categoria_sugerida = data.categoria
        if eligio and data.recordar:
            aprendido = _aprender_de_correo(db, usuario.id, correo, data.categoria, data.aplicar_anteriores)

    # Correos viejos pudieron quedar como 'transfer' (sin dirección): se leen de nuevo del texto.
    tipo = correo.tipo_sugerido
    if tipo not in ("income", "expense"):
        tipo = detectar_tipo(f"{correo.asunto} {correo.snippet}")
    notas = con_marca_traslado("") if es_posible_traslado_propio(f"{correo.asunto} {correo.snippet}") else ""

    movimiento = Movimiento(
        usuario_id=usuario.id,
        cuenta_id=cuenta.id,
        notas=notas,
        # El comercio o concepto que dice el correo ('Compra en Juan Valdez'), no quién lo envió.
        # El origen queda en `fuente="email"`.
        descripcion=correo.comercio,
        categoria=correo.categoria_sugerida,
        tipo=tipo,
        monto=correo.monto,
        # recibido_en y creado_en están en UTC: el movimiento va en hora Colombia.
        fecha=utc_a_co(correo.recibido_en or correo.creado_en),
        fuente="email",
        # La categoría la sugirió la app al leer el correo: queda por revisar
        # salvo que sea 'Otros' (que ya aparece en la vista por revisar).
        cat_origen="sugerida" if correo.categoria_sugerida != "Otros" and not data.categoria else None,
        cat_confirmada=correo.categoria_sugerida == "Otros" or bool(data.categoria),
    )
    db.add(movimiento)

    if tipo == "income":
        cuenta.saldo += correo.monto
    else:
        cuenta.saldo -= correo.monto

    correo.estado = "aprobado"
    db.commit()
    db.refresh(movimiento)
    correo.movimiento_id = movimiento.id
    db.commit()
    db.refresh(correo)
    return _con_aprendizaje(_con_cuenta(db, usuario.id, [correo])[0], aprendido)


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
