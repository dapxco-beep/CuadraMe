import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
