import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import importar_respaldo as respaldo
from app import punto_partida
from app.routers.cuentas import ajustar_saldo as ajustar_saldo_cuenta
from app.schemas import AjusteSaldoRequest

from app import avisos
from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.derechos_titular import armar_json, armar_zip, borrar_todo, recopilar
from app.limites import verificar_limite
from app.models import Cuenta, Perfil
from app.claves_api import asignar_clave_nueva, tiene_clave
from app.nombre import NombreInvalido, nombre_de_pila, nombre_para_mostrar, nombre_titular_limpio, validar_nombre
from app.utiles import ahora_co
from app.schemas import ConfianzaAutoimportUpdate, EliminarCuentaRequest

router = APIRouter(prefix="/perfil", tags=["perfil"])
logger = logging.getLogger(__name__)


def _get_or_create_perfil(db: Session, usuario_id: str) -> Perfil:
    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
    if not perfil:
        perfil = Perfil(usuario_id=usuario_id, plan="free")
        db.add(perfil)
        db.commit()
        db.refresh(perfil)
    return perfil


class NombreUpdate(BaseModel):
    nombre: str | None = Field(default=None, max_length=200)
    omitir: bool = False  # «Ahora no»: se queda con el nombre de pila automático y no se vuelve a preguntar


def _respuesta_nombre(perfil: Perfil, usuario: UsuarioActual) -> dict:
    sugerido = nombre_de_pila(usuario.nombre, getattr(usuario, "nombre_pila", ""))
    guardado = nombre_para_mostrar(perfil.nombre_preferido)
    return {
        "nombre": guardado or None,
        "sugerido": sugerido or None,
        "confirmado": bool(perfil.nombre_confirmado),
        "email": usuario.email,
    }


@router.get("/nombre")
def obtener_nombre(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Cómo le decimos a ESTA persona (cada cuenta tiene el suyo). `sugerido` sale del nombre de Google."""
    perfil = _get_or_create_perfil(db, usuario.id)
    _recordar_nombre_titular(db, perfil, usuario)
    return _respuesta_nombre(perfil, usuario)


def _recordar_nombre_titular(db: Session, perfil: Perfil, usuario: UsuarioActual) -> None:
    """Guarda el nombre completo de Google SOLO para reconocer traslados propios (ver contabilidad.py).
    Mejor esfuerzo: si la columna aún no existe, no pasa nada."""
    try:
        completo = nombre_titular_limpio(usuario.nombre)
        if completo and perfil.nombre_titular != completo:
            perfil.nombre_titular = completo
            db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()


@router.put("/nombre")
def guardar_nombre(
    data: NombreUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Guarda el nombre que la persona escribió, o con `omitir` el nombre de pila automático."""
    perfil = _get_or_create_perfil(db, usuario.id)
    if data.omitir:
        auto = nombre_de_pila(usuario.nombre, getattr(usuario, "nombre_pila", ""))
        if auto and not perfil.nombre_preferido:
            perfil.nombre_preferido = auto
    else:
        try:
            perfil.nombre_preferido = validar_nombre(data.nombre)
        except NombreInvalido as e:
            raise HTTPException(status_code=422, detail=str(e))
    perfil.nombre_confirmado = True
    db.commit()
    return _respuesta_nombre(perfil, usuario)


@router.get("/api-key")
def obtener_api_key(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    if not tiene_clave(db, perfil):
        # Primera vez: se crea y se muestra completa (única ocasión, junto con regenerar).
        return {"api_key": asignar_clave_nueva(db, perfil), "tiene_clave": True, "nueva": True}
    if perfil.api_key:
        # Clave antigua aún en claro (se migra a hash la primera vez que el Atajo la use).
        return {"api_key": perfil.api_key, "tiene_clave": True, "nueva": False}
    # Ya guardada como hash: no se puede mostrar. Solo el prefijo para reconocerla.
    return {"api_key": None, "tiene_clave": True, "nueva": False, "prefijo": perfil.api_key_prefijo,
            "mensaje": "Por seguridad tu clave ya no se puede mostrar. Si la perdiste, genera una nueva."}


class RecordatorioUpdate(BaseModel):
    activo: bool


@router.get("/recordatorio-diario")
def obtener_recordatorio_diario(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    return {"activo": bool(perfil.recordatorio_diario)}


@router.put("/recordatorio-diario")
def actualizar_recordatorio_diario(
    data: RecordatorioUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Activa o apaga el aviso de las 8pm 'hoy no has registrado nada'."""
    perfil = _get_or_create_perfil(db, usuario.id)
    perfil.recordatorio_diario = data.activo
    db.commit()
    return {"activo": bool(perfil.recordatorio_diario)}


@router.post("/api-key/regenerar")
def regenerar_api_key(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    clave = asignar_clave_nueva(db, perfil)  # también reinicia api_key_ultimo_uso
    return {"api_key": clave, "tiene_clave": True, "nueva": True}


@router.get("/confianza-autoimport")
def obtener_confianza_autoimport(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    return {"confianza_autoimport": perfil.confianza_autoimport or 0.75}


@router.put("/confianza-autoimport")
def actualizar_confianza_autoimport(
    data: ConfianzaAutoimportUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    if not (0.5 <= data.confianza_autoimport <= 0.95):
        raise HTTPException(status_code=400, detail="El valor debe estar entre 0.5 y 0.95")
    perfil = _get_or_create_perfil(db, usuario.id)
    perfil.confianza_autoimport = data.confianza_autoimport
    db.commit()
    return {"confianza_autoimport": perfil.confianza_autoimport}


class AutoimportarExtractosUpdate(BaseModel):
    activo: bool


@router.get("/autoimportar-extractos")
def obtener_autoimportar_extractos(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    return {"activo": bool(perfil.autoimportar_extractos), "confianza_autoimport": perfil.confianza_autoimport or 0.75}


@router.put("/autoimportar-extractos")
def actualizar_autoimportar_extractos(
    data: AutoimportarExtractosUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Opcional y apagado por defecto: al subir un extracto, importa solo lo que la app
    reconoce con certeza (umbral = confianza-autoimport). Lo importado se puede deshacer."""
    perfil = _get_or_create_perfil(db, usuario.id)
    perfil.autoimportar_extractos = data.activo
    db.commit()
    return {"activo": bool(perfil.autoimportar_extractos)}




@router.get("/mis-datos")
def descargar_mis_datos(
    formato: Literal["zip", "json"] = "zip",
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Derecho de acceso y portabilidad (Ley 1581 de 2012): todo lo que CuadraMe guarda
    del usuario. ZIP con un JSON completo + un CSV por tabla (abren en Excel), o solo el
    JSON con ?formato=json. Se limita a 5 por hora: armar el archivo recorre todas las tablas."""
    verificar_limite(f"mis-datos:{usuario.id}", 5, 3600, "Ya descargaste tus datos varias veces. Intenta de nuevo en {espera}.")
    datos = recopilar(db, usuario.id, usuario.email)
    hoy = ahora_co().strftime("%Y-%m-%d")
    if formato == "json":
        return Response(
            content=armar_json(datos, usuario.email), media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=cuadrame_mis_datos_{hoy}.json"},
        )
    return Response(
        content=armar_zip(datos, usuario.email), media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=cuadrame_mis_datos_{hoy}.zip"},
    )


# ── Importar mi respaldo ─────────────────────────────────────────────────────────────
# Restaura el ZIP de «Descargar mis datos». La lógica (y todas las garantías) viven en
# app/importar_respaldo.py; aquí solo está la API: vista previa -> importar -> deshacer.

def _leer_subida(archivo: UploadFile) -> dict:
    crudo = archivo.file.read(respaldo.MAX_BYTES_ARCHIVO + 1)
    try:
        return respaldo.leer_datos(crudo)
    except respaldo.RespaldoInvalido as e:
        raise HTTPException(status_code=400, detail=str(e))


def _marcar_correo(resumen: dict, usuario: UsuarioActual) -> dict:
    otro = (resumen.get("correo_respaldo") or "").strip().lower()
    resumen["correo_distinto"] = bool(otro and usuario.email and otro != usuario.email.lower())
    resumen.pop("correo_respaldo", None)  # el correo de otra persona no se devuelve
    return resumen


@router.post("/importar-respaldo/vista-previa")
def vista_previa_respaldo(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Cuenta qué se crearía y qué ya existe (y se omitiría). No escribe nada."""
    verificar_limite(f"importar-respaldo:{usuario.id}", 20, 3600, "Ya probaste varios respaldos. Intenta de nuevo en {espera}.")
    datos = _leer_subida(archivo)
    r = respaldo.procesar(db, usuario.id, datos, aplicar=False)
    db.rollback()
    return {"vista_previa": True, **_marcar_correo(r["resumen"], usuario)}


@router.post("/importar-respaldo")
def importar_respaldo(
    archivo: UploadFile = File(...),
    confirmar: bool = Form(False),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Importa el respaldo en UNA transacción (si algo falla no queda nada a medias).
    Exige confirmar=true: la vista previa va primero. Repetirlo no duplica."""
    if not confirmar:
        raise HTTPException(status_code=400, detail="Confirma la importación después de ver la vista previa.")
    verificar_limite(f"importar-respaldo:{usuario.id}", 20, 3600, "Ya importaste varias veces. Intenta de nuevo en {espera}.")
    datos = _leer_subida(archivo)
    try:
        resumen = respaldo.importar(db, usuario.id, datos)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("importar-respaldo: falló la importación del usuario %s", usuario.id)
        raise HTTPException(status_code=500, detail="No pudimos importar tu respaldo y no se guardó nada. Intenta de nuevo.")
    return {"ok": True, **_marcar_correo(resumen, usuario)}


@router.get("/importar-respaldo/ultima")
def ultima_importacion(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """¿Hay una importación que se pueda deshacer? (para mostrar el botón)."""
    lote = respaldo.ultima_importacion(db, usuario.id)
    if not lote:
        return {"hay": False}
    import json as _json
    return {"hay": True, "creado_en": lote.creado_en.isoformat() if lote.creado_en else None,
            "resumen": {k: v for k, v in _json.loads(lote.resumen or "{}").items() if isinstance(v, dict)}}


@router.post("/importar-respaldo/deshacer")
def deshacer_importacion(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Revierte SOLO lo que creó la última importación (lo que ya tenías, no se toca)."""
    lote = respaldo.ultima_importacion(db, usuario.id)
    if not lote:
        raise HTTPException(status_code=404, detail="No hay ninguna importación para deshacer.")
    try:
        out = respaldo.deshacer(db, usuario.id, lote)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("importar-respaldo: falló el deshacer del usuario %s", usuario.id)
        raise HTTPException(status_code=500, detail="No pudimos deshacer la importación. No se cambió nada.")
    return {"ok": True, "revertido": out}


@router.post("/eliminar-cuenta")
def eliminar_cuenta(
    data: EliminarCuentaRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Derecho de supresión (Ley 1581 de 2012): borra TODOS los datos del usuario.
    Es irreversible. Se exige la palabra ELIMINAR para evitar llamadas accidentales.
    Solo actúa sobre la sesión de quien llama: nadie puede borrar la cuenta de otro.
    La lógica vive en app/derechos_titular.py (también revoca el permiso de Gmail)."""
    if data.confirmacion.strip().upper() != "ELIMINAR":
        raise HTTPException(status_code=400, detail='Para confirmar, envía confirmacion="ELIMINAR"')

    resultado = borrar_todo(db, usuario.id, usuario.email)
    avisos.cuenta_eliminada(usuario.id)  # se anota sin datos de la persona (ni id ni correo)
    respuesta = {"ok": True, "auth_eliminado": resultado["auth_eliminado"],
                 "gmail_revocado": resultado["gmail_revocado"]}
    if resultado["aviso"]:
        respuesta["aviso"] = resultado["aviso"]
    return respuesta


# ── Punto de partida ──────────────────────────────────────────────────────────
# «Empezar desde hoy» o «recrear mi histórico». La lógica y las reglas viven en
# app/punto_partida.py; aquí solo está la API. Nada de esto borra datos.

class SaldoPuntoPartida(BaseModel):
    inicial: float | None = None
    actual: float | None = None


class PuntoPartidaIn(BaseModel):
    modo: Literal["hoy", "historico"]
    fecha: date | None = None  # 'hoy': por defecto hoy. 'historico': obligatoria (o `meses`)
    meses: int | None = Field(default=None, ge=1, le=24)  # atajo: «los últimos N meses»
    saldos: dict[str, SaldoPuntoPartida] = {}  # cuenta_id -> saldo
    ajustar_saldos: bool = False  # llevar cada cuenta al saldo `actual` declarado (ajuste neutral)


class AjustarSaldosIn(BaseModel):
    cuenta_ids: list[str] = []  # vacío = todas las que tengan saldo declarado


@router.get("/punto-de-partida")
def obtener_punto_de_partida(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Elección actual y cuántos correos/extractos anteriores a esa fecha se están ignorando."""
    return punto_partida.resumen(db, usuario.id)


@router.put("/punto-de-partida")
def guardar_punto_de_partida(
    data: PuntoPartidaIn,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Elige el punto de partida. Hacia atrás: permite importar más. Hacia adelante: oculta lo
    anterior de informes y consejos (no borra nada)."""
    hoy = punto_partida.hoy_co()
    if data.modo == "hoy":
        fecha = data.fecha or hoy
    else:
        fecha = data.fecha or (punto_partida.sugerencia_fecha(data.meses) if data.meses else None)
        if fecha is None:
            raise HTTPException(status_code=400, detail="Elige desde cuándo quieres recrear tu histórico")
    if fecha > hoy:
        raise HTTPException(status_code=400, detail="La fecha de inicio no puede ser futura")
    if fecha < punto_partida.sugerencia_fecha(punto_partida.MAX_MESES_HISTORICO):
        raise HTTPException(status_code=400, detail="Elige una fecha de hasta 24 meses atrás")

    cuentas = {c.id: c for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all()}
    saldos: dict = {}
    for cuenta_id, s in data.saldos.items():
        if cuenta_id not in cuentas:
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        for v in (s.inicial, s.actual):
            if v is not None and abs(v) > 1e12:
                raise HTTPException(status_code=400, detail="Ese saldo no parece válido")
        # En «hoy» el saldo que la persona escribe es a la vez el inicial y el actual.
        inicial = s.inicial if s.inicial is not None else (s.actual if data.modo == "hoy" else None)
        saldos[cuenta_id] = {"inicial": inicial, "actual": s.actual if s.actual is not None else inicial}
    efecto = punto_partida.guardar(db, usuario.id, data.modo, fecha, saldos)
    db.commit()

    ajustados = 0
    if data.ajustar_saldos:
        # Fijar el saldo de partida no es un movimiento del histórico: la nota lo distingue del ajuste
        # posterior (ese sí cuenta al reconstruir el saldo).
        ajustados = _ajustar_a_declarados(
            db, usuario, [k for k, v in saldos.items() if v.get("actual") is not None], punto_partida.NOTA_SALDO_INICIAL)
    return {**punto_partida.resumen(db, usuario.id), "retrocedio": efecto["retrocedio"], "ajustados": ajustados}


def _ajustar_a_declarados(db: Session, usuario: UsuarioActual, cuenta_ids: list[str],
                          nota: str = punto_partida.NOTA_AJUSTE) -> int:
    """Lleva cada cuenta a su saldo declarado con el «Ajuste de saldo» de siempre (no es gasto ni ingreso)."""
    declarados = punto_partida.obtener(db, usuario.id)["saldos"]
    n = 0
    for cuenta_id in cuenta_ids:
        objetivo = (declarados.get(cuenta_id) or {}).get("actual")
        if objetivo is None:
            continue
        r = ajustar_saldo_cuenta(cuenta_id, AjusteSaldoRequest(saldo_real=objetivo, nota=nota),
                                 db=db, usuario=usuario)
        n += 1 if r.get("ajustado") else 0
    return n


@router.get("/punto-de-partida/cobertura")
def cobertura_punto_de_partida(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Modo histórico: por cuenta, qué meses ya tienen extracto conciliado y cuáles faltan."""
    return {**punto_partida.cobertura(db, usuario.id), "modo": punto_partida.obtener(db, usuario.id)["modo"]}


@router.get("/punto-de-partida/conciliacion")
def conciliacion_punto_de_partida(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Saldo reconstruido (inicial + movimientos desde la fecha) frente al saldo actual declarado."""
    filas = punto_partida.conciliacion(db, usuario.id)
    con_dato = [f for f in filas if f["coincide"] is not None]
    return {"cuentas": filas, "todo_coincide": bool(con_dato) and all(f["coincide"] for f in con_dato)}


@router.post("/punto-de-partida/ajustar-saldos")
def ajustar_saldos_punto_de_partida(
    data: AjustarSaldosIn,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Ofrece el «ajuste de saldo» neutral cuando lo reconstruido no coincide con lo declarado."""
    declarados = punto_partida.obtener(db, usuario.id)["saldos"]
    ids = data.cuenta_ids or list(declarados)
    return {"ok": True, "ajustados": _ajustar_a_declarados(db, usuario, ids)}


# ── País, moneda e idioma ───────────────────────────────────────────────────
class PaisUpdate(BaseModel):
    pais: str = Field(max_length=2)
    moneda_base: str | None = Field(default=None, max_length=3)
    idioma: str | None = Field(default=None, max_length=10)
    zona_horaria: str | None = Field(default=None, max_length=64)


def _respuesta_pais(db: Session, usuario_id: str) -> dict:
    from app import paises

    perfil = _get_or_create_perfil(db, usuario_id)
    try:
        guardado, base, idioma, zona, conf = (perfil.pais, perfil.moneda_base, perfil.idioma,
                                              perfil.zona_horaria, perfil.pais_confirmado)
    except Exception:  # columnas aún sin crear en la base: se comporta como Colombia
        db.rollback()
        guardado = base = idioma = zona = conf = None
    cod = guardado if paises.pais_valido(guardado) else paises.PAIS_POR_DEFECTO_LEGADO
    c = paises.PAISES[cod]
    return {
        "pais": cod,
        "confirmado": bool(conf),
        "moneda_base": base or c["moneda"],
        "idioma": idioma or c["idioma"],
        "zona_horaria": zona or c["zona_horaria"],
        "config": {k: c[k] for k in ("nombre", "estado", "moneda", "simbolo", "decimales", "locale",
                                     "tratamiento", "funciones_fiscales", "unidad_tributaria",
                                     "pago_inmediato", "banco_central", "ley_datos")},
    }


@router.get("/pais")
def obtener_pais(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """País, moneda e idioma de ESTA persona. Sin país guardado (perfiles anteriores) = Colombia."""
    return _respuesta_pais(db, usuario.id)


@router.put("/pais")
def guardar_pais(
    data: PaisUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """La persona elige (o confirma la sugerencia de) su país. La moneda base por defecto es la del país."""
    from app import paises

    cod = data.pais.upper()
    if not paises.pais_valido(cod):
        raise HTTPException(status_code=422, detail="Ese país todavía no está disponible.")
    c = paises.PAISES[cod]
    moneda = (data.moneda_base or c["moneda"]).upper()
    if not moneda.isalpha() or len(moneda) != 3:
        raise HTTPException(status_code=422, detail="Moneda no válida.")
    perfil = _get_or_create_perfil(db, usuario.id)
    try:
        perfil.pais = cod
        perfil.moneda_base = moneda
        perfil.idioma = data.idioma or c["idioma"]
        perfil.zona_horaria = data.zona_horaria or c["zona_horaria"]
        perfil.pais_confirmado = True
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=503, detail="No pudimos guardar tu país ahora. Inténtalo de nuevo en un momento.")
    return _respuesta_pais(db, usuario.id)


@router.get("/paises")
def listar_paises(usuario: UsuarioActual = Depends(get_current_user)):
    """Catálogo para el selector de país (solo los disponibles). No contiene datos de personas."""
    from app import paises

    return {"paises": paises.catalogo_publico()}
