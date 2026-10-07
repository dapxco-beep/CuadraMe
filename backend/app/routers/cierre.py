"""Cierre de mes: informe mensual por usuario, guardado para verlo en la app.

El cron (POST /cierre-mes/cron/cerrar-mes, header X-Cron-Secret) genera el cierre
de TODOS los usuarios para el mes que acaba de terminar. Es idempotente por
(usuario, mes): correrlo varias veces no regenera informes ni repite notificaciones.
Este archivo NO crea ni cambia ningún cron; cómo programarlo está en HOJA_DE_RUTA.md."""
import json
import logging
import re
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, cron_autorizado, get_current_user
from app.cierre_mensual import generar_cierre
from app.compartidos import cuentas_ids_accesibles
from app.config import settings
from app.contabilidad import tipos_de_cuentas, tipos_efectivos
from app.database import get_db
from app.fx import convertir_a_cop
from app.models import Cuenta, Deuda, Movimiento
from app.models_fiscal import AjusteUsuario, CierreMes
from app.models_patrimonio import SnapshotPatrimonio
from app.push import enviar_push
from app.utiles import ahora_co

router = APIRouter(prefix="/cierre-mes", tags=["cierre-mes"])
logger = logging.getLogger(__name__)

_MES_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class PreferenciasCierre(BaseModel):
    correo: bool


def _mes_valido(mes: str) -> str:
    if not _MES_RE.match(mes or ""):
        raise HTTPException(status_code=422, detail="El mes debe tener formato AAAA-MM")
    return mes


def mes_anterior(mes: str) -> str:
    anio, num = (int(x) for x in mes.split("-"))
    return f"{anio - 1}-12" if num == 1 else f"{anio}-{num - 1:02d}"


def _inicio(mes: str) -> datetime:
    anio, num = (int(x) for x in mes.split("-"))
    return datetime(anio, num, 1)


def _siguiente(mes: str) -> str:
    anio, num = (int(x) for x in mes.split("-"))
    return f"{anio + 1}-01" if num == 12 else f"{anio}-{num + 1:02d}"


def construir_cierre(db: Session, usuario_id: str, mes: str) -> dict:
    """Junta los datos del usuario y delega el cálculo en la función pura."""
    ids = cuentas_ids_accesibles(db, usuario_id)
    cuentas = db.query(Cuenta).filter(Cuenta.id.in_(ids)).all()
    monedas = {c.id: c.moneda for c in cuentas}
    tipos = tipos_de_cuentas(cuentas)
    previo = mes_anterior(mes)
    movs = (
        db.query(Movimiento)
        .filter(Movimiento.cuenta_id.in_(ids), Movimiento.fecha >= _inicio(previo) - timedelta(days=3),
                Movimiento.fecha < _inicio(_siguiente(mes)) + timedelta(days=3))
        .all()
    )
    te = tipos_efectivos(movs, tipos)

    def fila(m):
        return {"tipo": te[m.id], "monto": convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP")),
                "categoria": m.categoria, "descripcion": m.descripcion}

    movs_mes = [fila(m) for m in movs if m.fecha.strftime("%Y-%m") == mes]
    movs_prev = [fila(m) for m in movs if m.fecha.strftime("%Y-%m") == previo]

    deudas = db.query(Deuda).filter(Deuda.usuario_id == usuario_id, Deuda.activa == True).all()  # noqa: E712
    interes_deudas = sum((d.saldo_actual or 0) * (d.tasa_mensual or 0) / 100 for d in deudas)

    snaps = {
        s.mes: s.patrimonio_neto
        for s in db.query(SnapshotPatrimonio)
        .filter(SnapshotPatrimonio.usuario_id == usuario_id, SnapshotPatrimonio.mes.in_([mes, previo])).all()
    }
    return generar_cierre(mes, movs_mes, movs_prev, interes_deudas, snaps.get(previo), snaps.get(mes))


def _guardar(db: Session, usuario_id: str, mes: str, informe: dict) -> CierreMes | None:
    fila = CierreMes(usuario_id=usuario_id, mes=mes, datos=json.dumps(informe, ensure_ascii=False))
    db.add(fila)
    try:
        db.commit()
    except IntegrityError:  # otro proceso lo guardó justo antes: idempotencia
        db.rollback()
        return None
    return fila


def _enviar_correo(destino: str, asunto: str, texto: str) -> bool:
    """Correo por Resend. Solo se llama si el usuario lo activó; sin clave configurada no hace nada."""
    if not settings.resend_api_key:
        return False
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": settings.resend_from, "to": [destino], "subject": asunto, "text": texto},
            timeout=20,
        )
        r.raise_for_status()
        return True
    except Exception:
        logger.warning("cierre: no se pudo enviar el correo", exc_info=True)
        return False


def texto_correo(informe: dict) -> str:
    lineas = [informe["titulo"], "", informe["resumen_corto"], ""]
    if informe.get("categoria_que_mas_subio"):
        c = informe["categoria_que_mas_subio"]
        lineas.append(f"Lo que más subió: {c['categoria']} (+${c['aumento']:,.0f})".replace(",", "."))
    if informe.get("intereses_pagados"):
        lineas.append(f"Intereses pagados: ${informe['intereses_pagados']:,.0f}".replace(",", "."))
    lineas += ["", "Para el próximo mes:"] + [f"- {a}" for a in informe["acciones"]]
    lineas += ["", "Míralo completo en CuadraMe > Más > Cierre de mes."]
    return "\n".join(lineas)


def _notificar(db: Session, fila: CierreMes, informe: dict) -> dict:
    """Push siempre (si tiene dispositivos); correo solo si lo activó. Cada canal una sola vez."""
    r = {"push": 0, "correo": 0}
    if not fila.notificado_push:
        enviar_push(db, fila.usuario_id, informe["titulo"], informe["resumen_corto"], "/cierre-mes")
        fila.notificado_push = True
        r["push"] = 1
    if not fila.notificado_correo:
        aj = db.query(AjusteUsuario).filter(AjusteUsuario.usuario_id == fila.usuario_id).first()
        if aj and aj.cierre_correo and aj.email_cierre:
            if _enviar_correo(aj.email_cierre, f"CuadraMe — {informe['titulo']}", texto_correo(informe)):
                fila.notificado_correo = True
                r["correo"] = 1
    db.commit()
    return r


@router.post("/cron/cerrar-mes")
def cron_cerrar_mes(
    mes: str | None = None,
    x_cron_secret: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Genera el cierre de todos los usuarios (por defecto del mes anterior). Idempotente."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    hoy_mes = ahora_co().strftime("%Y-%m")
    mes = _mes_valido(mes) if mes else mes_anterior(hoy_mes)
    if mes >= hoy_mes:
        raise HTTPException(status_code=400, detail="Solo se puede cerrar un mes que ya terminó")

    usuarios = [r[0] for r in db.query(Cuenta.usuario_id).distinct().all()]
    res = {"ok": True, "mes": mes, "usuarios": len(usuarios), "generados": 0, "ya_existian": 0,
           "sin_movimientos": 0, "push": 0, "correos": 0, "errores": 0}
    for uid in usuarios:
        try:
            fila = db.query(CierreMes).filter(CierreMes.usuario_id == uid, CierreMes.mes == mes).first()
            if fila:
                res["ya_existian"] += 1
            else:
                informe = construir_cierre(db, uid, mes)
                if informe["sin_datos"]:
                    res["sin_movimientos"] += 1
                    continue
                fila = _guardar(db, uid, mes, informe)
                if fila is None:
                    res["ya_existian"] += 1
                    continue
                res["generados"] += 1
            n = _notificar(db, fila, json.loads(fila.datos))
            res["push"] += n["push"]
            res["correos"] += n["correo"]
        except Exception:
            db.rollback()
            res["errores"] += 1
            logger.exception("cierre: falló para el usuario %s", uid)
    res["fallidos"] = res["errores"]
    res["procesados"] = len(usuarios) - res["errores"]
    return res


# ---------------------------------------------------------------- usuario

@router.get("")
def listar(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    filas = db.query(CierreMes).filter(CierreMes.usuario_id == usuario.id).order_by(CierreMes.mes.desc()).all()
    out = []
    for f in filas:
        d = json.loads(f.datos or "{}")
        out.append({"mes": f.mes, "titulo": d.get("titulo"), "resumen_corto": d.get("resumen_corto"),
                    "ahorro": d.get("ahorro"), "visto": bool(f.visto)})
    return out


@router.get("/preferencias")
def obtener_preferencias(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    aj = db.query(AjusteUsuario).filter(AjusteUsuario.usuario_id == usuario.id).first()
    return {"correo": bool(aj and aj.cierre_correo), "email": usuario.email}


@router.put("/preferencias")
def guardar_preferencias(
    data: PreferenciasCierre,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """El correo es opt-in. Se guarda el email actual porque el cron no tiene el token del usuario."""
    aj = db.query(AjusteUsuario).filter(AjusteUsuario.usuario_id == usuario.id).first()
    if not aj:
        aj = AjusteUsuario(usuario_id=usuario.id)
        db.add(aj)
    aj.cierre_correo = data.correo
    aj.email_cierre = usuario.email if data.correo else None
    db.commit()
    return {"ok": True, "correo": aj.cierre_correo}


@router.get("/{mes}")
def obtener(mes: str, silencioso: bool = False, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """El cierre del mes. Sin cierre: 404 (contrato actual de la PWA) o, con ?silencioso=true,
    200 {"existe": false} para no ensuciar la consola del cliente."""
    _mes_valido(mes)
    fila = db.query(CierreMes).filter(CierreMes.usuario_id == usuario.id, CierreMes.mes == mes).first()
    if not fila:
        if silencioso:
            return {"existe": False, "mes": mes}
        raise HTTPException(status_code=404, detail="Aún no hay cierre de ese mes")
    if not fila.visto:
        fila.visto = True
        db.commit()
    return json.loads(fila.datos)


@router.post("/{mes}/generar")
def generar(mes: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Genera el cierre de un mes ya terminado si aún no existe (idempotente). Para el mes
    en curso devuelve una vista parcial SIN guardarla."""
    _mes_valido(mes)
    hoy_mes = ahora_co().strftime("%Y-%m")
    if mes > hoy_mes:
        raise HTTPException(status_code=400, detail="Ese mes todavía no llega")
    if mes == hoy_mes:
        return {**construir_cierre(db, usuario.id, mes), "parcial": True}
    fila = db.query(CierreMes).filter(CierreMes.usuario_id == usuario.id, CierreMes.mes == mes).first()
    if fila:
        return json.loads(fila.datos)
    informe = construir_cierre(db, usuario.id, mes)
    if informe["sin_datos"]:
        raise HTTPException(status_code=404, detail="No hay movimientos en ese mes")
    fila = _guardar(db, usuario.id, mes, informe)
    if fila is None:
        fila = db.query(CierreMes).filter(CierreMes.usuario_id == usuario.id, CierreMes.mes == mes).first()
    else:
        fila.notificado_push = True  # lo generó el propio usuario: ya lo está viendo
        db.commit()
    return json.loads(fila.datos)
