import base64
import json
import logging
import time
from typing import Optional

import re

from pydantic import BaseModel, Field
from google.auth.exceptions import RefreshError
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, cron_autorizado, get_current_user
from app.crons import Corrida, MarcaCron, reclamar_marca
from app.push import enviar_push
from app.autocat import ClasificadorUsuario, aplicar_a_anteriores, guardar_regla_aprendida
from app.config import settings
from app.limites import verificar_limite
from app.limites_diarios import consumir_cupo_diario
from app.database import get_db
from app import titulo as tit
from app import punto_partida
from app.extractos_vista import clasificar_motivo, frase_error
from app.conciliacion import detectar_banco
from app.contabilidad import con_marca_traslado
from app.extractos_conciliados import (
    ESTADO_YA_CONCILIADO,
    depurar_conciliados,
    evidencia_conciliado,
    mes_del_extracto,
    periodo_en_asunto,
)
from app.cuentas_banco import pregunta_de_cuentas, producto_de_cuenta, producto_de_texto
from app.extractos_gmail import (
    MAX_PDF_BYTES,
    abrir_pdf,
    asunto_para_gmail,
    construir_query_asunto,
    datos_cuerpo_tarjeta,
    texto_cuerpo,
    banco_por_remitente,
    claves_candidatas,
    construir_query_extractos,
    construir_query_notificaciones,
    contiene_palabra_extracto,
    candidatas_banco,
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
from app import reevaluar_ignorados
from app import releer_saldos
from app.gmail_extract import (
    buscar_fecha_en_texto,
    detectar_tipo,
    es_posible_traslado_propio,
    extraer_comercio,
    extraer_moneda,
    extraer_monto,
    fecha_movimiento_info,
    texto_cuerpo,
)
from app.gmail_oauth import (
    cifrar,
    cliente_gmail,
    crear_state,
    descifrar,
    intercambiar_code,
    leer_state,
    obtener_email,
    revocar_token,
    url_autorizacion,
)
from app import carriles_correo as carriles
from app.models import Categoria, ClavePdf, Cuenta, CorreoGasto, ExtractoCorreo, HistorialExtracto, Movimiento, Perfil, SyncGmail
from app.routers.consentimientos import exigir_consentimiento, tiene_consentimiento
from app.routers.conciliacion import procesar_extracto_de_gmail as procesar_extracto
from app.utiles import ahora_co, utc_a_co
from app.duplicados import absorber_correos
from app import duplicados as dup
from app.schemas import (
    AprobarCorreoRequest,
    LecturaCorreoRequest,
    ClavePdfIn,
    ProbarClaveIn,
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
    registrados = {}
    ids_reg = [c.movimiento_id for c in correos if c.estado == "ya_registrado" and c.movimiento_id]
    if ids_reg:
        movs = dup.anotar_canales(db, db.query(Movimiento).filter(Movimiento.id.in_(ids_reg)).all())
        registrados = {m.id: {"descripcion": m.descripcion, "monto": m.monto, "fecha": m.fecha.isoformat() if m.fecha else None,
                              "tipo": m.tipo, "canales": m.canales} for m in movs}
    salida = []
    for c in correos:
        o = CorreoGastoOut.model_validate(c)
        info = fecha_movimiento_info(c)
        o.fecha_movimiento, o.fecha_movimiento_con_hora, o.fecha_del_texto = info["fecha"], info["con_hora"], info["del_texto"]
        o.recibido_en_co = utc_a_co(c.recibido_en or c.creado_en)
        if c.estado == "ya_registrado":
            o.registrado_como = registrados.get(c.movimiento_id)
        o.banco_detectado, o.cuenta_sugerida_id, o.falta_cuenta = inferir_cuenta_por_remitente(c.remitente, cuentas, f"{c.asunto} {c.snippet}")
        o.falta_monto = (c.monto or 0) <= 0
        if o.banco_detectado and not o.falta_cuenta and not o.cuenta_sugerida_id:
            # Banco con varias cuentas y sin ganador claro: la app pregunta en vez de adivinar.
            cands, o.producto_detectado = candidatas_banco(
                o.banco_detectado, detectar_ultimos4(f"{c.asunto} {c.snippet}"), cuentas, f"{c.asunto} {c.snippet}"
            )
            if len(cands) > 1:
                o.cuentas_candidatas = [x.id for x in cands]
                o.pregunta_cuenta = pregunta_de_cuentas(cands)
        elif o.cuenta_sugerida_id:
            o.producto_detectado = producto_de_texto(f"{c.asunto} {c.snippet}")
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
        leer_movimientos=perfil.gmail_leer_movimientos is not False,
        leer_extractos=perfil.gmail_leer_extractos is not False,
    )


@router.put("/gmail/lectura")
def guardar_lectura(
    data: LecturaCorreoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Enciende o apaga cada uso del correo por separado: `leer_movimientos` (notificaciones del
    banco) y `leer_extractos` (PDF para conciliar). Lo que no se mande no cambia. Apagar un uso no
    borra lo ya guardado; solo deja de leer y de guardar cosas nuevas de ese carril."""
    perfil = _get_or_create_perfil(db, usuario.id)
    if data.leer_movimientos is not None:
        perfil.gmail_leer_movimientos = data.leer_movimientos
    if data.leer_extractos is not None:
        perfil.gmail_leer_extractos = data.leer_extractos
    db.commit()
    return {
        "ok": True,
        "leer_movimientos": perfil.gmail_leer_movimientos is not False,
        "leer_extractos": perfil.gmail_leer_extractos is not False,
    }


@router.get("/carriles")
def carriles_correo(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Estado de los dos usos del correo por separado: interruptor, última vez y contadores
    (movimientos: leídos/nuevos/por revisar/ya registrados; extractos: encontrados/leídos/
    con clave pendiente/al día). Solo lee la base; no toca Gmail."""
    absorber_correos(db, usuario.id)  # lo que ya tiene su movimiento no cuenta como «por revisar»
    _get_or_create_perfil(db, usuario.id)
    db.commit()
    return carriles.resumen(db, usuario.id)


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

    try:
        tokens = intercambiar_code(code)
    except Exception:  # noqa: BLE001 - código vencido/reusado: volver a la app, no mostrar un 500
        logger.warning("Google rechazó el código de autorización de Gmail")
        return RedirectResponse(url=f"{settings.pwa_url}/#/correos?gmail=error")
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
    revocar_token(perfil.gmail_refresh_token_enc)  # que Google también invalide el acceso
    perfil.gmail_conectado = False
    perfil.gmail_refresh_token_enc = None
    perfil.gmail_email = None
    db.commit()
    return {"ok": True}


@router.post("/gmail/etiqueta")
def actualizar_etiqueta(
    etiqueta: str = Query(max_length=80),
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


def _fecha_del_texto_utc(texto: str, recibido):
    co = buscar_fecha_en_texto(texto, recibido)
    return co + timedelta(hours=5) if co else None


def _crear_correo(msg: dict, usuario_id: str, modelo: ClasificadorUsuario) -> CorreoGasto:
    """Convierte un mensaje de Gmail en un CorreoGasto 'pendiente' (sugerencia
    que el usuario debe aprobar; nunca crea movimientos). La categoría la decide
    el clasificador del usuario (reglas -> aprendido -> diccionario -> 'Otros')."""
    h = encabezados(msg)
    remitente = h.get("From", "")
    asunto = h.get("Subject", "")
    snippet = msg.get("snippet", "")
    texto = f"{asunto} {snippet}"
    # El fragmento de Gmail son ~200 caracteres: a veces el monto queda fuera (p. ej. «Ya entró tu pago»).
    # Solo para notificaciones de TRANSACCIÓN de un banco conocido se lee el cuerpo; no se guarda.
    if not extraer_monto(texto) and banco_por_remitente(remitente) and es_notificacion_transaccion(asunto, snippet):
        cuerpo = texto_cuerpo(msg)
        if cuerpo and extraer_monto(f"{asunto} {cuerpo}", estricto=True):
            texto = f"{asunto} {snippet} {cuerpo}"
    comercio = extraer_comercio(remitente, asunto, snippet if texto == f"{asunto} {snippet}" else texto)
    resultado = modelo.clasificar(comercio, texto)
    recibido = fecha_mensaje(msg)
    return CorreoGasto(
        usuario_id=usuario_id,
        gmail_msg_id=msg["id"],
        remitente=remitente,
        asunto=asunto,
        snippet=snippet[:400],
        recibido_en=recibido,
        # La fecha que el banco escribió en el texto («el 3 de julio de 2026 a las 11:05 am»); None si no la trae.
        fecha_movimiento=_fecha_del_texto_utc(texto, recibido),
        monto=extraer_monto(texto, estricto=(texto != f"{asunto} {snippet}")),
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
    fila.motivo_error = None
    try:
        pdf = descargar_adjunto(gmail, fila.gmail_msg_id, adjunto["attachment_id"])
    except Exception:
        logger.warning("No se pudo descargar un adjunto del mensaje %s", fila.gmail_msg_id)
        fila.estado = "error"
        fila.motivo_error = "error_temporal"
        return
    estado, texto, clave_usada = abrir_pdf(pdf, claves_candidatas(clave))
    # Resultado de la clave en ESTE extracto (nunca la clave): solo cuenta si había una guardada
    # y el PDF la necesitaba (si abrió sin clave no dice nada de ella).
    if clave and estado == "ok" and clave_usada:
        fila.clave_resultado, fila.clave_probada_en = "ok", datetime.utcnow()
    elif clave and estado == "falta_clave":
        fila.clave_resultado, fila.clave_probada_en = "fallo", datetime.utcnow()
    if estado == "ok":
        banco_texto = detectar_banco(texto)
        if banco_texto not in ("generico", "desconocido") and not fila.banco:
            fila.banco = banco_texto.capitalize()
        fila.periodo = detectar_periodo(texto, f"{fila.archivo} {fila.asunto}")
        fila.cuenta_sugerida_id = sugerir_cuenta(fila.banco, detectar_ultimos4(texto), cuentas, texto[:6000])
        fila.estado = "nuevo"
        if not (texto or "").strip():
            fila.motivo_error = "pdf_escaneado"  # abre, pero es una imagen: no hay texto que leer
        _marcar_si_conciliado(db, fila)
    else:
        # Sin texto no hay periodo ni cuenta; el banco sale del remitente.
        fila.periodo = detectar_periodo("", f"{fila.archivo} {fila.asunto}")
        fila.cuenta_sugerida_id = sugerir_cuenta(fila.banco, "", cuentas) if fila.banco else None
        fila.estado = estado  # falta_clave | error
        if estado == "error":
            fila.motivo_error = clasificar_motivo(pdf_vacio=not pdf)
        elif estado == "falta_clave":
            fila.motivo_error = clasificar_motivo(pide_clave=True, clave_dada=bool(clave))


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
# Los extractos llegan una vez al mes y lo ya visto se salta sin costo: su fase mira un año atrás (no solo los
# 90 días de los gastos), si no, los meses viejos y los que se atrasaron nunca aparecen. Respeta el punto de partida.
DIAS_EXTRACTOS = 365


def desde_de_fase(fase: str, desde: datetime, inicio: datetime | None = None, modo: str | None = None,
                  ref: datetime | None = None) -> datetime:
    if fase != "extractos":
        return desde
    amplio = (ref or datetime.utcnow()) - timedelta(days=DIAS_EXTRACTOS)
    if inicio:
        amplio = inicio if modo == "historico" else max(amplio, inicio)
    r = min(desde, amplio)
    return max(r, inicio) if inicio else r


MAX_CORRIDA_HORAS = 6
FASES = ("etiqueta", "notificaciones", "extractos")

# Dos «carriles» independientes del correo. MOVIMIENTOS: notificaciones del banco (el dato real del
# día a día: fases etiqueta + notificaciones). EXTRACTOS: PDF del estado de cuenta (para conciliar).
TIPOS = ("todo", "movimientos", "extractos")
FASES_DEL_TIPO = {
    "movimientos": ("etiqueta", "notificaciones"),
    "extractos": ("extractos",),
    "todo": FASES,
}


def tipo_efectivo(perfil: Perfil, pedido: str = "todo") -> str | None:
    """Carril(es) que SÍ se leen: lo pedido ∩ lo que el usuario dejó activo. None = nada (ambos
    apagados o el pedido está apagado): en ese caso no se toca Gmail ni se guarda nada."""
    mov = pedido in ("todo", "movimientos") and perfil.gmail_leer_movimientos is not False
    ext = pedido in ("todo", "extractos") and perfil.gmail_leer_extractos is not False
    if mov and ext:
        return "todo"
    return "movimientos" if mov else ("extractos" if ext else None)


def _fases_de(tipo: str | None) -> tuple:
    return FASES_DEL_TIPO.get(tipo or "todo", FASES)


def _ultima_del_tipo(sync: SyncGmail, tipo: str) -> datetime | None:
    """Desde cuándo leer: la sincronización más ANTIGUA de los carriles que se van a leer
    (un carril nunca leído obliga a la ventana larga). Sin marcas por carril (datos de antes)
    vale la última sincronización general."""
    marcas = []
    if tipo in ("todo", "movimientos"):
        marcas.append(sync.ultima_sync_mov or sync.ultima_sync)
    if tipo in ("todo", "extractos"):
        marcas.append(sync.ultima_sync_ext or sync.ultima_sync)
    if any(m is None for m in marcas):
        return None
    return min(marcas)


def _exigir_extractos_activos(perfil: Perfil) -> None:
    """Con «Extractos» apagado no se descargan adjuntos del correo, ni a pedido."""
    if perfil.gmail_leer_extractos is False:
        raise HTTPException(
            status_code=400,
            detail="Tienes apagada la lectura de «Extractos». Enciéndela para leer extractos de tu correo.",
        )


def _get_or_create_sync(db: Session, usuario_id: str) -> SyncGmail:
    sync = db.query(SyncGmail).filter(SyncGmail.usuario_id == usuario_id).first()
    if not sync:
        sync = SyncGmail(usuario_id=usuario_id)
        db.add(sync)
        db.flush()
    return sync


def _pais_de(sync) -> str:
    """País del dueño de la corrida (para elegir los remitentes de su banco). Nunca rompe la sincronización."""
    try:
        from app import paises
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            return paises.pais_de_usuario(db, sync.usuario_id)
        finally:
            db.close()
    except Exception:
        return "CO"


def _consulta_fase(fase: str, desde: datetime, pais: str = "CO") -> dict:
    if fase == "notificaciones":
        return {"q": construir_query_notificaciones(desde=desde, pais=pais)}
    if fase == "extractos":
        return {"q": construir_query_extractos(desde=desde, pais=pais)}
    return {"q": f"after:{desde:%Y/%m/%d}"}


def _listar(gmail, fase: str, desde: datetime, label_id: str | None, token: str | None, max_results: int,
            pais: str = "CO", inicio: datetime | None = None, modo: str | None = None,
            ref: datetime | None = None) -> dict:
    kw = _consulta_fase(fase, desde_de_fase(fase, desde, inicio, modo, ref), pais)
    if fase == "etiqueta":
        kw["labelIds"] = [label_id]
    if token:
        kw["pageToken"] = token
    return gmail.users().messages().list(userId="me", maxResults=max_results, **kw).execute()


def _iniciar_corrida(gmail, sync: SyncGmail, label_id: str | None, completa: bool, dias: int,
                     inicio: datetime | None = None, modo: str | None = None, tipo: str = "todo") -> None:
    """`inicio`/`modo`: punto de partida del usuario. Nunca se lee antes del inicio; en modo
    «histórico» la primera lectura llega hasta esa fecha (no solo los últimos `dias`)."""
    ahora = datetime.utcnow()
    ultima = _ultima_del_tipo(sync, tipo)
    if completa or not ultima:
        desde = ahora - timedelta(days=dias)
        if inicio and modo == "historico":
            desde = inicio
    else:
        desde = ultima - timedelta(days=SOLAPE_DIAS)
    if inicio and desde < inicio:
        desde = inicio
    sync.en_curso = True
    sync.desde = desde
    sync.iniciada_en = ahora
    fases = [f for f in _fases_de(tipo) if f != "etiqueta" or label_id]
    sync.tipo = tipo
    sync.fase = fases[0]
    sync.fase_iniciada = False
    sync.cursor_token = None
    sync.cursor_ids = "[]"
    sync.reintento_clave_hecho = False
    sync.leidos = sync.nuevos = sync.omitidos = sync.extractos_nuevos = 0
    sync.leidos_mov = sync.leidos_ext = sync.omitidos_mov = 0
    # Estimación del total (una llamada barata por fase) para la barra de progreso.
    total = 0
    for fase in fases:
        r = _listar(gmail, fase, desde, label_id, None, 1, _pais_de(sync), inicio, modo, ahora)
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


def _procesar_extracto(gmail, db, usuario_id, ref_id, cuentas, clave, vistos: set,
                       forzar: bool = False) -> tuple[int, int]:
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
        # `forzar`: la persona eligió este correo a mano (búsqueda por asunto), no hace falta la palabra «extracto».
        if (forzar or contiene_palabra_extracto(asunto, a["archivo"], snippet)) and a["tamano"] <= MAX_PDF_BYTES
    ]
    try:  # solo 4 datos del aviso de la tarjeta; el cuerpo en sí no se guarda
        cuerpo = datos_cuerpo_tarjeta(f"{asunto}\n{texto_cuerpo(msg)}\n{snippet}") if adjuntos else None
    except Exception:  # noqa: BLE001 - leer de más nunca rompe la sincronización
        cuerpo = None
    cuerpo_json = json.dumps(cuerpo, ensure_ascii=False) if cuerpo else None
    vistos.add(ref_id)
    if not adjuntos:
        # Marca para no volver a leer este correo en cada sincronización.
        db.add(ExtractoCorreo(
            usuario_id=usuario_id, gmail_msg_id=ref_id, archivo="",
            remitente=remitente, asunto=asunto, estado="ignorado", recibido_en=fecha_mensaje(msg),
        ))
        return 0, 0
    recibido = fecha_mensaje(msg)
    # ¿Se puede saber el periodo y la cuenta sin abrir el PDF?
    cuenta_unica = cuentas_del_banco(banco, cuentas) if banco else []
    # El atajo es solo para el MISMO producto: «extracto de tu tarjeta Nu» no es el de la cuenta Nu.
    prod_asunto = producto_de_texto(f"{asunto} {' '.join(a['archivo'] for a in adjuntos)}")
    if len(cuenta_unica) == 1 and prod_asunto and producto_de_cuenta(cuenta_unica[0]) not in (prod_asunto, None):
        cuenta_unica = []
    periodo_previo = periodo_en_asunto(asunto, recibido)
    ev = (
        evidencia_conciliado(db, usuario_id, cuenta_unica[0].id, mes_del_extracto(periodo_previo, None))
        if len(cuenta_unica) == 1 and periodo_previo else None
    )
    descargados = nuevos = 0
    for adj in adjuntos:
        fila = ExtractoCorreo(
            usuario_id=usuario_id, gmail_msg_id=ref_id, archivo=adj["archivo"],
            remitente=remitente, asunto=asunto, banco=banco, recibido_en=recibido, datos_cuerpo=cuerpo_json,
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


def _cerrar_corrida(sync: SyncGmail) -> None:
    """Fin de la corrida: solo se actualiza el «última vez» y los contadores de los carriles que
    se leyeron (leer solo movimientos no debe borrar lo último que se supo de los extractos)."""
    ahora = datetime.utcnow()
    tipo = sync.tipo or "todo"
    # Datos de antes de los carriles: la marca general vale para ambos hasta la primera corrida parcial.
    if sync.ultima_sync:
        sync.ultima_sync_mov = sync.ultima_sync_mov or sync.ultima_sync
        sync.ultima_sync_ext = sync.ultima_sync_ext or sync.ultima_sync
    sync.en_curso = False
    if tipo in ("todo", "movimientos"):
        sync.ultima_sync_mov = ahora
        sync.ultimo_nuevos = sync.nuevos
        sync.ultimo_leidos_mov = sync.leidos_mov or 0
        sync.ultimo_ya_registrados = sync.omitidos_mov or 0
    if tipo in ("todo", "extractos"):
        sync.ultima_sync_ext = ahora
        sync.ultimo_extractos = sync.extractos_nuevos
        sync.ultimo_leidos_ext = sync.leidos_ext or 0
    sync.ultima_sync = max(m for m in (sync.ultima_sync_mov, sync.ultima_sync_ext) if m)  # lo más reciente
    sync.ultimo_leidos = sync.leidos
    sync.ultimo_error = None
    sync.total_estimado = max(sync.total_estimado, sync.leidos)


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
                activas = [f for f in _fases_de(sync.tipo) if f != "etiqueta" or label_id]
                siguientes = [f for f in activas if FASES.index(f) > FASES.index(sync.fase)]
                if not siguientes:
                    _cerrar_corrida(sync)
                    return
                sync.fase, sync.fase_iniciada, sync.cursor_token = siguientes[0], False, None
                continue
            if sync.fase == "extractos" and not sync.reintento_clave_hecho:
                _reintentar_claves(gmail, db, usuario_id, cuentas, clave)
                sync.reintento_clave_hecho = True
            from app import paises as _paises
            pais_corrida = _paises.pais_de_usuario(db, usuario_id)
            inicio_pp, modo_pp = punto_partida.desde_para_sync(db, usuario_id)
            r = _listar(gmail, sync.fase, sync.desde, label_id, sync.cursor_token, PAGINA_GMAIL,
                        pais_corrida, inicio_pp, modo_pp, sync.iniciada_en)
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
            if sync.fase != "extractos":
                sync.omitidos_mov = (sync.omitidos_mov or 0) + 1
        sync.leidos += 1
        if sync.fase == "extractos":
            sync.leidos_ext = (sync.leidos_ext or 0) + 1
        else:
            sync.leidos_mov = (sync.leidos_mov or 0) + 1
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
        tipo=sync.tipo or "todo",
        movimientos_leidos=(sync.leidos_mov if sync.en_curso else sync.ultimo_leidos_mov) or 0,
        movimientos_ya_registrados=(sync.omitidos_mov if sync.en_curso else sync.ultimo_ya_registrados) or 0,
        extractos_leidos=(sync.leidos_ext if sync.en_curso else sync.ultimo_leidos_ext) or 0,
    )


def _lote_de_sincronizacion(db: Session, usuario_id: str, perfil: Perfil, completa: bool = False,
                            dias: int = DIAS_PRIMERA_SYNC, tipo: str = "todo") -> tuple[SyncGmail, int, int]:
    """UN lote de la sincronización de Gmail (sin sesión HTTP): lo usan el botón del usuario
    y el cron. Inicia o retoma la corrida, lee un lote y hace commit. Devuelve (sync, novedades
    de ESTE lote: correos por revisar, extractos nuevos). Puede lanzar RefreshError y errores
    de Gmail: quien llama decide qué hacer. `tipo` ya debe ser el efectivo (movimientos | extractos |
    todo): un carril apagado nunca llega hasta aquí."""
    etiqueta = perfil.gmail_etiqueta or "gastos"
    gmail = cliente_gmail(perfil.gmail_refresh_token_enc)
    labels = gmail.users().labels().list(userId="me").execute().get("labels", [])
    label_id = next((l["id"] for l in labels if l["name"].lower() == etiqueta.lower()), None)

    reevaluar_ignorados.preparar(db, usuario_id)  # una sola vez por usuario: relee correos de bancos sin monto
    # Extractos ya procesados que quedaron sin saldos (lector viejo): se vuelven a traer de Gmail y se completan.
    releer_saldos.releer(db, usuario_id, gmail, _clave_pdf(db, usuario_id))
    sync = _get_or_create_sync(db, usuario_id)
    vencida = bool(sync.iniciada_en) and datetime.utcnow() - sync.iniciada_en > timedelta(hours=MAX_CORRIDA_HORAS)
    # Una corrida a medias de otro carril no se mezcla: se arranca la de este (lo ya visto se salta).
    cambio_tipo = bool(sync.en_curso) and (sync.tipo or "todo") != tipo
    if completa or not sync.en_curso or vencida or cambio_tipo:
        inicio_pp, modo_pp = punto_partida.desde_para_sync(db, usuario_id)
        _iniciar_corrida(gmail, sync, label_id, completa, dias, inicio_pp, modo_pp, tipo)
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
    # Los correos de gastos que YA tienen su movimiento (atajo, a mano, extracto...) no son novedad:
    # se enlazan a él y no salen en «Por revisar». Lo que el usuario borró tampoco resucita.
    # (Solo aplica al carril de movimientos: leer solo extractos no toca los correos de gastos.)
    quitar = 0
    if tipo in ("todo", "movimientos"):
        absorbidos = absorber_correos(db, usuario_id, cuentas=cuentas)
        quitar = absorbidos["ya_registrados"] + absorbidos["descartados"]
    if quitar:
        if sync.en_curso:
            sync.nuevos = max(0, (sync.nuevos or 0) - quitar)
            sync.omitidos_mov = (sync.omitidos_mov or 0) + absorbidos["ya_registrados"]
        else:
            sync.ultimo_nuevos = max(0, (sync.ultimo_nuevos or 0) - quitar)
            sync.ultimo_ya_registrados = (sync.ultimo_ya_registrados or 0) + absorbidos["ya_registrados"]
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
    tipo: str = Query("todo", pattern="^(movimientos|extractos|todo)$"),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Sincroniza Gmail (solo lectura) POR LOTES: 1) notificaciones de bancos
    conocidos y correos con la etiqueta opcional, que quedan pendientes de
    revisión — nunca se crean movimientos solos — y 2) extractos en PDF.
    Primera vez: últimos `dias` (90). Luego: incremental desde la última
    sincronización completa, con 1 día de solape. `completa=true` fuerza la
    ventana larga. Cada llamada hace un lote y devuelve el progreso; repetirla
    hasta `completado` (reanuda donde quedó, sin duplicar).

    `tipo` elige el carril: `movimientos` (notificaciones del banco), `extractos` (PDF para
    conciliar) o `todo` (por defecto, igual que siempre). Un carril que el usuario apagó en sus
    ajustes NO se lee ni se guarda nada de él; si no queda ninguno, responde sin tocar Gmail."""
    verificar_limite(f"sync-gmail:{usuario.id}", 80, 3600, "Sincronizaste muchas veces seguidas. Intenta en unos minutos.")
    consumir_cupo_diario(db, usuario.id, "sync-gmail")
    perfil = _get_or_create_perfil(db, usuario.id)
    if not perfil.gmail_conectado or not perfil.gmail_refresh_token_enc:
        raise HTTPException(status_code=400, detail="Gmail no está conectado")

    efectivo = tipo_efectivo(perfil, tipo)
    if efectivo is None:
        nombre = {"movimientos": "Los movimientos del día a día", "extractos": "Los extractos para conciliar"}.get(tipo, "La lectura del correo")
        return SincronizarCorreosResponse(
            ok=True, nuevos=0, omitidos=0, tipo=tipo,
            aviso=f"{nombre} están apagados: no leí nada de tu correo. Puedes activarlos cuando quieras.",
        )
    try:
        sync, _movs, _exts = _lote_de_sincronizacion(db, usuario.id, perfil, completa, dias, efectivo)
        return _respuesta_sync(sync)

    except HTTPException:
        raise
    except RefreshError:
        db.rollback()
        perfil.gmail_conectado = False
        perfil.gmail_refresh_token_enc = None
        db.commit()
        return SincronizarCorreosResponse(
            ok=False, nuevos=0, omitidos=0, tipo=tipo,
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
            ok=False, nuevos=0, omitidos=0, tipo=tipo,
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
    nuevos = sin_consentimiento = desconectados = avisados = apagados = 0
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
            efectivo = tipo_efectivo(perfil, "todo")
            if efectivo is None:  # el usuario apagó los dos usos: no se lee nada
                apagados += 1
                continue
            try:
                _sync, movs, exts = _lote_de_sincronizacion(db, uid, perfil, tipo=efectivo)
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
        "sin_consentimiento": sin_consentimiento, "desconectados": desconectados, "apagados": apagados,
        "pendientes_por_tiempo": pendientes_por_tiempo,
    }


@router.post("/cron/purgar-retencion")
def cron_purgar_retencion(db: Session = Depends(get_db), x_cron_secret: str = Header(default="")):
    """Minimización de datos de Gmail (cron externo, X-Cron-Secret; sugerido 1 vez al día, de madrugada).
    Aplica los plazos RETENCION_* (todos en 0 = apagado: no toca nada). Idempotente, por lotes con
    tope de tiempo, tolerante a fallos. Devuelve solo conteos, nunca contenido. Ver app/retencion.py."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    from app import retencion

    r = retencion.purgar(db)
    return {"ok": r["fallidos"] == 0, "procesados": sum(r[k] for k in retencion._CLAVES), **r}


# ── Lista completa de correos (con filtros y paginación) ───────────

@router.get("/lista", response_model=list[CorreoGastoOut])
def listar_correos(
    filtro: str = Query("nuevos", pattern="^(nuevos|aprobados|ignorados|descartados|ya_registrados|todos)$"),
    limite: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Correos leídos por estado, de a `limite` ('cargar más' con `offset`)."""
    estados = {"nuevos": "pendiente", "aprobados": "aprobado", "ignorados": "ignorado", "descartados": "descartado",
               "ya_registrados": "ya_registrado"}
    q = db.query(CorreoGasto).filter(CorreoGasto.usuario_id == usuario.id)
    if filtro != "todos":
        q = q.filter(CorreoGasto.estado == estados[filtro])
    inicio_pp = punto_partida.fecha_inicio(db, usuario.id)
    if inicio_pp and filtro == "nuevos":
        q = q.filter(or_(CorreoGasto.recibido_en.is_(None), CorreoGasto.recibido_en >= inicio_pp - timedelta(days=60)))
        # Margen de 60 dias en SQL; el corte exacto usa la fecha del movimiento (puede ser anterior a la de recepcion).
        filas = [c for c in q.order_by(CorreoGasto.creado_en.desc(), CorreoGasto.id).all()
                 if not punto_partida.es_anterior(fecha_movimiento_info(c)["fecha"], inicio_pp)]
        return _con_cuenta(db, usuario.id, filas[offset:offset + limite])
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
    cuentas_usuario = db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all()
    inicio_pp = punto_partida.fecha_inicio(db, usuario.id)
    fila_clave = db.query(ClavePdf).filter(ClavePdf.usuario_id == usuario.id).first()
    salida = []
    for f in filas:
        # Antes del punto de partida: no se ofrece (ni se concilia) lo que la persona dejó fuera.
        if f.estado in ("nuevo", "falta_clave", "error") and punto_partida.extracto_es_anterior(f.periodo, f.recibido_en, inicio_pp):
            continue
        o = ExtractoCorreoOut.model_validate(f)
        if f.estado == "falta_clave" or f.clave_resultado == "ok":
            o.clave_estado = _resultado_clave(f, fila_clave)
        # Extractos viejos pueden no traer el banco guardado: se deduce del remitente.
        o.banco = o.banco or banco_por_remitente(f.remitente) or ""
        o.cruzados = cruzados.get(f.historial_id)
        if o.banco and not o.cuenta_sugerida_id and f.estado in ("nuevo", "falta_clave", "error"):
            cands = cuentas_del_banco(o.banco, cuentas_usuario)
            if len(cands) > 1:
                o.cuentas_candidatas = [x.id for x in cands]
                o.pregunta_cuenta = pregunta_de_cuentas(cands)
        if f.estado == ESTADO_YA_CONCILIADO and o.cruzados is None:
            ev = evidencia_conciliado(db, usuario.id, f.cuenta_sugerida_id, mes_del_extracto(f.periodo, None))
            o.cruzados = ev["cruzados"] if ev else None
        salida.append(o)
    return salida


# ── Búsqueda manual por asunto ───────────────────────────────────────
MAX_RESULTADOS_ASUNTO = 15
DIAS_BUSQUEDA_ASUNTO = 365
_ID_GMAIL = re.compile(r"^[A-Za-z0-9_-]{2,64}$")


class BuscarAsuntoIn(BaseModel):
    asunto: str = Field(min_length=1, max_length=200)


class ProcesarAsuntoIn(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=MAX_RESULTADOS_ASUNTO)


class CorreoEncontradoOut(BaseModel):
    gmail_msg_id: str
    remitente: str
    asunto: str
    fecha: Optional[datetime] = None
    archivos: list[str] = []
    ya_en_lista: bool = False


def _gmail_del_usuario(db: Session, usuario_id: str):
    perfil = _get_or_create_perfil(db, usuario_id)
    if not perfil.gmail_conectado or not perfil.gmail_refresh_token_enc:
        raise HTTPException(status_code=400, detail="Gmail no está conectado")
    _exigir_extractos_activos(perfil)
    return cliente_gmail(perfil.gmail_refresh_token_enc)


@router.post("/extractos/buscar-asunto", response_model=list[CorreoEncontradoOut])
def buscar_extractos_por_asunto(
    data: BuscarAsuntoIn,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«¿No ves un extracto?»: busca en TU Gmail (solo lectura) correos con PDF adjunto de los últimos 365
    días cuyo asunto contenga el texto. El texto va solo como `subject:"…"` (sin operadores libres). No guarda
    nada: devuelve remitente, fecha y asunto para que la persona elija cuáles procesar."""
    verificar_limite(f"buscar-asunto:{usuario.id}", 20, 3600, "Buscaste muchas veces seguidas. Intenta en unos minutos.")
    frase = asunto_para_gmail(data.asunto)
    if not frase:
        raise HTTPException(status_code=400, detail="Escribe al menos 3 letras del asunto del correo.")
    gmail = _gmail_del_usuario(db, usuario.id)
    try:
        r = gmail.users().messages().list(
            userId="me", q=construir_query_asunto(frase, DIAS_BUSQUEDA_ASUNTO), maxResults=MAX_RESULTADOS_ASUNTO,
        ).execute()
        ids = [m["id"] for m in r.get("messages", [])][:MAX_RESULTADOS_ASUNTO]
        conocidos = {x[0] for x in db.query(ExtractoCorreo.gmail_msg_id).filter(
            ExtractoCorreo.usuario_id == usuario.id, ExtractoCorreo.estado != "ignorado").all()}
        salida = []
        for i in ids:
            msg = gmail.users().messages().get(userId="me", id=i, format="full").execute()
            adjuntos = listar_adjuntos_pdf(msg)
            if not adjuntos:
                continue
            h = encabezados(msg)
            salida.append(CorreoEncontradoOut(
                gmail_msg_id=i, remitente=h.get("From", "")[:200], asunto=h.get("Subject", "")[:200],
                fecha=fecha_mensaje(msg), archivos=[a["archivo"] for a in adjuntos][:5], ya_en_lista=i in conocidos,
            ))
        return salida
    except RefreshError:
        raise HTTPException(status_code=400, detail="Se perdió el acceso a Gmail. Conéctalo de nuevo.")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error buscando por asunto (usuario %s)", usuario.id)
        raise HTTPException(status_code=502, detail="No pudimos consultar tu correo ahora. Intenta de nuevo.")


@router.post("/extractos/buscar-asunto/procesar")
def procesar_extractos_por_asunto(
    data: ProcesarAsuntoIn,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Mete a la lista de extractos los correos que la persona eligió (misma tubería que la sincronización:
    clave del PDF, cuenta/producto, ya conciliado). Un correo ya listado no se duplica."""
    verificar_limite(f"buscar-asunto-procesar:{usuario.id}", 20, 3600, "Procesaste muchos correos seguidos. Intenta en unos minutos.")
    ids = []
    for i in data.ids:
        if not _ID_GMAIL.match(i):
            raise HTTPException(status_code=400, detail="Correo no válido.")
        if i not in ids:
            ids.append(i)
    gmail = _gmail_del_usuario(db, usuario.id)
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all()
    clave = _clave_pdf(db, usuario.id)
    agregados = 0
    try:
        for i in ids:
            previas = db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == usuario.id, ExtractoCorreo.gmail_msg_id == i).all()
            if any(p.estado != "ignorado" for p in previas):
                continue  # ya está en la lista: no se duplica
            for p in previas:  # lo había descartado el filtro automático: la persona lo pide a propósito
                db.delete(p)
            db.flush()
            _d, nuevos = _procesar_extracto(gmail, db, usuario.id, i, cuentas, clave, set(), forzar=True)
            agregados += nuevos
        db.commit()
    except RefreshError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Se perdió el acceso a Gmail. Conéctalo de nuevo.")
    except Exception:
        db.rollback()
        logger.exception("Error procesando por asunto (usuario %s)", usuario.id)
        raise HTTPException(status_code=502, detail="No pudimos leer ese correo ahora. Intenta de nuevo.")
    return {"ok": True, "extractos_nuevos": agregados}


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
    _exigir_extractos_activos(perfil)

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
        fila.motivo_error = "error_temporal"
        db.commit()
        return ProcesarExtractoResponse(ok=False, error="No se pudo descargar el extracto. Intenta de nuevo.",
                                        motivo_error="error_temporal")

    estado, _texto, clave_usada = abrir_pdf(pdf, claves_candidatas(_clave_pdf(db, usuario.id)))
    if estado == "falta_clave":
        fila.estado = "falta_clave"
        fila.motivo_error = clasificar_motivo(pide_clave=True, clave_dada=bool(_clave_pdf(db, usuario.id)))
        db.commit()
        return ProcesarExtractoResponse(
            ok=False, error="Este extracto está cifrado: guarda la clave del PDF (normalmente tu cédula) en los ajustes.",
            motivo_error=fila.motivo_error,
        )
    if estado != "ok":
        fila.estado = "error"
        fila.motivo_error = clasificar_motivo(pdf_vacio=not pdf)
        db.commit()
        return ProcesarExtractoResponse(ok=False, error="No se pudo leer este PDF.", motivo_error=fila.motivo_error)

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
        fila.motivo_error = None
        db.commit()
    elif resp.motivo_error:
        # No salieron movimientos: se guarda el motivo para decírselo en la lista (el extracto sigue ahí).
        fila.motivo_error = resp.motivo_error
        db.commit()
    return resp


class ReintentoOut(BaseModel):
    ok: bool
    estado: str
    motivo_error: Optional[str] = None
    mensaje: str = ""


@router.post("/extractos/{extracto_id}/reintentar", response_model=ReintentoOut)
def reintentar_extracto(
    extracto_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«Intentar de nuevo»: vuelve a descargar el PDF y a abrirlo con la clave guardada, y rellena banco, periodo,
    cuenta y estado como la primera vez. No importa movimientos (eso es «Revisar»)."""
    verificar_limite(f"reintentar-extracto:{usuario.id}", 30, 3600, "Reintentaste muchos extractos seguidos. Podrás seguir en {espera}.")
    fila = (
        db.query(ExtractoCorreo)
        .filter(ExtractoCorreo.id == extracto_id, ExtractoCorreo.usuario_id == usuario.id)
        .first()
    )
    if not fila:
        raise HTTPException(status_code=404, detail="Extracto no encontrado")
    if not fila.archivo:
        raise HTTPException(status_code=400, detail="Este correo no trae un archivo para reintentar.")
    perfil = _get_or_create_perfil(db, usuario.id)
    if not perfil.gmail_conectado or not perfil.gmail_refresh_token_enc:
        raise HTTPException(status_code=400, detail="Gmail no está conectado")
    _exigir_extractos_activos(perfil)
    try:
        gmail = cliente_gmail(perfil.gmail_refresh_token_enc)
        msg = gmail.users().messages().get(userId="me", id=fila.gmail_msg_id, format="full").execute()
    except RefreshError:
        return ReintentoOut(ok=False, estado=fila.estado, mensaje="Se perdió el acceso a Gmail. Conéctalo de nuevo.")
    except Exception:
        logger.exception("Error reintentando extracto de %s", usuario.id)
        return ReintentoOut(ok=False, estado=fila.estado, motivo_error="error_temporal",
                            mensaje="No pudimos conectarnos con Gmail ahora. Intenta de nuevo en un rato.")
    adj = next((a for a in listar_adjuntos_pdf(msg) if a["archivo"] == fila.archivo), None)
    if not adj:
        return ReintentoOut(ok=False, estado=fila.estado, mensaje="El archivo ya no está en tu correo.")
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all()
    _analizar_adjunto(gmail, db, fila, adj, cuentas, _clave_pdf(db, usuario.id))
    db.commit()
    if fila.estado == "error" or (fila.estado == "nuevo" and fila.motivo_error):
        return ReintentoOut(ok=False, estado=fila.estado, motivo_error=fila.motivo_error,
                            mensaje=frase_error(fila.motivo_error))
    if fila.estado == "falta_clave":
        return ReintentoOut(ok=False, estado=fila.estado, motivo_error=fila.motivo_error,
                            mensaje="Sigue pidiendo clave. Revisa la clave del PDF.")
    return ReintentoOut(ok=True, estado=fila.estado, mensaje="Listo: ya lo podemos revisar.")


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

def _nombre_extracto(f: ExtractoCorreo) -> str:
    """Cómo lo reconoce la persona: banco y periodo («Davivienda agosto 2026»)."""
    return " ".join(x for x in (f.banco or banco_por_remitente(f.remitente) or "", f.periodo or "") if x).strip() \
        or f.archivo or f.asunto or "sin nombre"


def _resultado_clave(f: ExtractoCorreo, fila_clave: ClavePdf | None) -> str:
    """'abrio' | 'no_abrio' | 'por_probar' | 'sin_clave' para un extracto que pide clave o que ya se abrió con ella."""
    if f.clave_resultado == "ok" and f.estado != "falta_clave":
        return "abrio"
    if not fila_clave:
        return "sin_clave"
    vigente = f.clave_probada_en and f.clave_probada_en >= (fila_clave.actualizado_en or datetime.min)
    if f.clave_resultado == "fallo" and vigente:
        return "no_abrio"  # esa clave ya se probó y no sirvió; hay que cambiarla
    return "por_probar"


@router.get("/clave-pdf")
def estado_clave_pdf(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Estado de la clave de los PDF, sin revelarla nunca: si hay una guardada, cuántas, y por
    extracto/banco cuáles abrió, cuáles no y cuáles están por probar."""
    fila_clave = db.query(ClavePdf).filter(ClavePdf.usuario_id == usuario.id).first()
    guardada = _clave_pdf(db, usuario.id) if fila_clave else None
    inicio_pp = punto_partida.fecha_inicio(db, usuario.id)
    filas = (
        db.query(ExtractoCorreo)
        .filter(
            ExtractoCorreo.usuario_id == usuario.id,
            or_(ExtractoCorreo.estado == "falta_clave", ExtractoCorreo.clave_resultado == "ok"),
            ExtractoCorreo.estado != "descartado",
        )
        .order_by(ExtractoCorreo.recibido_en.desc(), ExtractoCorreo.id)
        .limit(100)
        .all()
    )
    items, por_banco = [], {}
    for f in filas:
        if f.estado == "falta_clave" and punto_partida.extracto_es_anterior(f.periodo, f.recibido_en, inicio_pp):
            continue
        r = _resultado_clave(f, fila_clave)
        banco = f.banco or banco_por_remitente(f.remitente) or "Sin identificar"
        items.append({"id": f.id, "nombre": _nombre_extracto(f), "banco": banco, "periodo": f.periodo or "",
                      "resultado": r, "estado": f.estado})
        d = por_banco.setdefault(banco, {"banco": banco, "protegidos": 0, "abrieron": 0, "no_abrieron": 0, "por_probar": 0})
        d["protegidos"] += 1
        clave_d = {"abrio": "abrieron", "no_abrio": "no_abrieron"}.get(r, "por_probar")
        d[clave_d] += 1
    return {
        "configurada": fila_clave is not None,
        "cantidad_claves": len(claves_candidatas(guardada)) - 1 if guardada else 0,
        "actualizada_en": fila_clave.actualizado_en.isoformat() if fila_clave and fila_clave.actualizado_en else None,
        "protegidos": len(items),
        "abrieron": sum(1 for i in items if i["resultado"] == "abrio"),
        "no_abrieron": sum(1 for i in items if i["resultado"] == "no_abrio"),
        "por_probar": sum(1 for i in items if i["resultado"] in ("por_probar", "sin_clave")),
        "por_banco": sorted(por_banco.values(), key=lambda d: d["banco"]),
        "extractos": items,
    }


MAX_PRUEBAS_CLAVE = 8  # extractos que se prueban por llamada (cada uno descarga un PDF de Gmail)


def _plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


def _mensaje_prueba(abrieron: int, fallidos: list[str], ilegibles: int, restantes: int) -> str:
    partes = []
    if abrieron:
        partes.append(f"La clave funcionó en {_plural(abrieron, 'extracto', 'extractos')}.")
    if len(fallidos) == 1:
        partes.append(f"Esta clave no abrió el extracto {fallidos[0]}: revísala.")
    elif fallidos:
        partes.append(f"Esta clave no abrió {len(fallidos)} extractos ({', '.join(fallidos[:3])}"
                      f"{'…' if len(fallidos) > 3 else ''}): revísala.")
    if ilegibles:
        partes.append(f"{_plural(ilegibles, 'extracto no se pudo', 'extractos no se pudieron')} descargar; intenta de nuevo.")
    if restantes:
        partes.append(f"Quedan {_plural(restantes, 'extracto', 'extractos')} por probar: vuelve a tocar «Probar la clave ahora».")
    return " ".join(partes) or "No hay extractos protegidos por probar."


@router.post("/clave-pdf/probar")
def probar_clave_pdf(
    data: ProbarClaveIn,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Prueba la clave guardada ahora mismo: en UN extracto (`extracto_id`) o en todos los que piden
    clave. Descarga el PDF desde Gmail, intenta abrirlo, y si abre lo deja listo para conciliar.
    Responde con el resultado explícito por extracto. No muestra ni registra la clave."""
    fila_unica = None
    if data.extracto_id:
        fila_unica = (
            db.query(ExtractoCorreo)
            .filter(ExtractoCorreo.id == data.extracto_id, ExtractoCorreo.usuario_id == usuario.id)
            .first()
        )
        if not fila_unica:
            raise HTTPException(status_code=404, detail="Extracto no encontrado")
    verificar_limite(f"probar-clave:{usuario.id}", 30, 3600, "Probaste la clave muchas veces seguidas. Podrás seguir en {espera}.")
    perfil = _get_or_create_perfil(db, usuario.id)
    if not perfil.gmail_conectado or not perfil.gmail_refresh_token_enc:
        raise HTTPException(status_code=400, detail="Gmail no está conectado")
    _exigir_extractos_activos(perfil)
    clave = _clave_pdf(db, usuario.id)
    if not clave:
        return {"ok": False, "abrieron": 0, "no_abrieron": 0, "restantes": 0, "resultados": [],
                "mensaje": "Todavía no hay una clave guardada. Escríbela arriba y toca Guardar."}

    if fila_unica is not None:
        objetivos, restantes = [fila_unica], 0
    else:
        todos = (
            db.query(ExtractoCorreo)
            .filter(ExtractoCorreo.usuario_id == usuario.id, ExtractoCorreo.estado == "falta_clave")
            .order_by(ExtractoCorreo.recibido_en.desc(), ExtractoCorreo.id)
            .all()
        )
        inicio_pp = punto_partida.fecha_inicio(db, usuario.id)
        todos = [f for f in todos if not punto_partida.extracto_es_anterior(f.periodo, f.recibido_en, inicio_pp)]
        objetivos, restantes = todos[:MAX_PRUEBAS_CLAVE], max(0, len(todos) - MAX_PRUEBAS_CLAVE)

    try:
        gmail = cliente_gmail(perfil.gmail_refresh_token_enc)
    except Exception:
        raise HTTPException(status_code=400, detail="Se perdió el acceso a Gmail. Conéctalo de nuevo.")
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all()
    resultados, abrieron, fallidos, ilegibles = [], 0, [], 0
    for f in objetivos:
        nombre = _nombre_extracto(f)
        try:
            msg = gmail.users().messages().get(userId="me", id=f.gmail_msg_id, format="full").execute()
            adj = next((a for a in listar_adjuntos_pdf(msg) if a["archivo"] == f.archivo), None)
        except RefreshError:
            raise HTTPException(status_code=400, detail="Se perdió el acceso a Gmail. Conéctalo de nuevo.")
        except Exception:
            adj = None
        if not adj:
            ilegibles += 1
            resultados.append({"id": f.id, "nombre": nombre, "resultado": "no_descargo"})
            continue
        estado_antes = f.estado
        _analizar_adjunto(gmail, db, f, adj, cuentas, clave)
        if f.estado == "falta_clave":
            fallidos.append(nombre)
            resultados.append({"id": f.id, "nombre": _nombre_extracto(f), "resultado": "no_abrio"})
        elif f.estado == "error":
            f.estado = estado_antes  # el PDF no se pudo leer por otra razón: no se cambia lo que había
            ilegibles += 1
            resultados.append({"id": f.id, "nombre": nombre, "resultado": "no_descargo"})
        else:
            abrieron += 1
            resultados.append({"id": f.id, "nombre": _nombre_extracto(f), "resultado": "abrio"})
    db.commit()
    return {
        "ok": True, "abrieron": abrieron, "no_abrieron": len(fallidos), "restantes": restantes,
        "resultados": resultados, "mensaje": _mensaje_prueba(abrieron, fallidos, ilegibles, restantes),
    }


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
    # Autocuración: lo que ya tiene su movimiento (llegó antes por otro canal) no se ofrece para revisar.
    absorber_correos(db, usuario.id)
    q = db.query(CorreoGasto).filter(
        CorreoGasto.usuario_id == usuario.id,
        CorreoGasto.estado == "pendiente",
        CorreoGasto.monto > 0,  # sin monto no hay nada que registrar ni conciliar
    )
    inicio_pp = punto_partida.fecha_inicio(db, usuario.id)
    if inicio_pp:  # los correos anteriores al punto de partida no se muestran (tampoco se borran)
        # Margen de 60 dias en SQL; el corte exacto usa la fecha del MOVIMIENTO (que puede ser anterior a la de recepcion).
        q = q.filter(or_(CorreoGasto.recibido_en.is_(None), CorreoGasto.recibido_en >= inicio_pp - timedelta(days=60)))
    filas = [c for c in q.order_by(CorreoGasto.creado_en.desc()).all()
             if not punto_partida.es_anterior(fecha_movimiento_info(c)["fecha"], inicio_pp)]
    # Lo mas reciente primero, segun la fecha del movimiento (no la de lectura).
    filas.sort(key=lambda c: fecha_movimiento_info(c)["fecha"] or datetime.min, reverse=True)
    return _con_cuenta(db, usuario.id, filas)


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

    # La fecha del movimiento: la que corrigió la persona o, si no, la leída del correo (nunca la de lectura).
    info_fecha = fecha_movimiento_info(correo)
    fecha_mov = info_fecha["fecha"]
    if data.fecha is not None:
        ahora = ahora_co()
        if data.fecha > ahora + timedelta(days=1):
            raise HTTPException(status_code=400, detail="La fecha del movimiento no puede ser futura")
        if data.fecha < ahora - timedelta(days=5 * 365):
            raise HTTPException(status_code=400, detail="La fecha del movimiento es demasiado antigua")
        fecha_mov = data.fecha.replace(tzinfo=None)
        correo.fecha_movimiento = fecha_mov + timedelta(hours=5)

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
        banco, _sug, falta = inferir_cuenta_por_remitente(correo.remitente, cuentas, f"{correo.asunto} {correo.snippet}")
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
        titulo=tit.titulo_para_nuevo(db, usuario.id, correo.comercio, data.titulo),
        categoria=correo.categoria_sugerida,
        tipo=tipo,
        monto=correo.monto,
        # recibido_en y creado_en están en UTC: el movimiento va en hora Colombia.
        fecha=fecha_mov or utc_a_co(correo.recibido_en or correo.creado_en),
        fuente="email",
        # La categoría la sugirió la app al leer el correo: queda por revisar
        # salvo que sea 'Otros' (que ya aparece en la vista por revisar).
        cat_origen="sugerida" if correo.categoria_sugerida != "Otros" and not data.categoria else None,
        cat_confirmada=correo.categoria_sugerida == "Otros" or bool(data.categoria),
    )
    db.add(movimiento)
    dup.nuevo_movimiento(db, movimiento, dup.ORIGEN_CORREO, dup.huella_correo(correo.gmail_msg_id))
    if data.recordar_titulo and tit.limpiar(data.titulo):
        tit.guardar_regla(db, usuario.id, correo.comercio, data.titulo)

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


@router.post("/{correo_id}/no-es-duplicado", response_model=CorreoGastoOut)
def correo_no_es_duplicado(
    correo_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«Mostrar de todos modos / No es duplicado»: un correo que se dio por ya registrado era OTRO
    gasto igual. Vuelve a «Por revisar» y no se vuelve a esconder (ni al sincronizar de nuevo)."""
    correo = (
        db.query(CorreoGasto)
        .filter(CorreoGasto.id == correo_id, CorreoGasto.usuario_id == usuario.id)
        .first()
    )
    if not correo:
        raise HTTPException(status_code=404, detail="Correo no encontrado")
    if correo.estado != "ya_registrado":
        raise HTTPException(status_code=400, detail="Este correo no estaba marcado como ya registrado")
    dup.mostrar_de_todos_modos(db, usuario.id, correo)
    db.commit()
    db.refresh(correo)
    return _con_cuenta(db, usuario.id, [correo])[0]
