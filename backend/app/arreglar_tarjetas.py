"""«Arreglar mis extractos de la tarjeta»: UN solo paso para dejar bien los extractos de tarjeta de crédito.

Problema: extractos de la tarjeta procesados con un lector viejo quedaron (a) en la cuenta de ahorros del mismo banco
y/o (b) con menos líneas de las que hoy se leen. Arreglarlo a mano son dos pasos por extracto («Cambiar la cuenta
de este extracto» y «Releer este extracto»). Aquí se hace todo junto, genérico para cualquier banco con tarjeta.

Para cada extracto de TARJETA con correo, del más viejo al más nuevo y en ESTE ORDEN:
  1. Si está en una cuenta que no es de crédito y hay UNA tarjeta de crédito del mismo banco: se pasa el extracto y
     lo que importó (reasignar_extracto.cambiar: movimientos, huellas y saldos de ambas cuentas). Va primero para
     que lo ya importado se empareje en la tarjeta y la relectura no lo duplique.
  2. Se relee con el lector de hoy en modo «solo agregar» (releer_extracto.releer_historial): lo ya importado queda
     intacto y las líneas que antes no se leían entran como «por importar» (el extracto pasa a «por revisar»).
     Si la lectura no suma lo que dice el extracto, no se agrega nada y se avisa.

Reglas: nada se importa solo; una transacción por extracto (cada paso hace su commit); si uno falla (Gmail, PDF,
clave) se salta, se informa y se sigue con el resto; idempotente (la 2.ª vez no hay nada que hacer: la marca
`releer_extracto:<id>` ya guarda la versión del lector); máximo 12 extractos por llamada y la llamada cuenta como
UNA frente al límite de relecturas por hora. Sin columnas nuevas."""
from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import reasignar_extracto
from app import releer_extracto as rx
from app.crons import MarcaCron
from app.cuentas_banco import CREDITO, producto_de_cuenta
from app.models import ClavePdf, Cuenta, HistorialExtracto, Perfil

logger = logging.getLogger(__name__)

MAXIMO_POR_LLAMADA = 12


def _pesos(v: float) -> str:
    return "$" + f"{abs(round(v or 0)):,}".replace(",", ".")


def _ultima_linea(h: HistorialExtracto) -> str:
    """Fecha (AAAA-MM-DD) de la última línea leída: el mes del corte de un extracto viejo que no guardó su fecha de corte."""
    try:
        fechas = [str(i.get("fecha"))[:10] for i in json.loads(h.review_json or "[]")
                  if isinstance(i, dict) and i.get("estado") != "sobrante" and i.get("fecha")]
    except ValueError:
        return ""
    fechas = [f for f in fechas if len(f) == 10 and f[4] == "-"]
    return max(fechas) if fechas else ""


def _mes(h: HistorialExtracto, fila) -> str:
    for f in (h.fecha_corte, getattr(fila, "periodo", None), _ultima_linea(h)):
        if f and len(str(f)) >= 7 and str(f)[4] == "-":
            return str(f)[:7]
    cuando = getattr(fila, "recibido_en", None) or h.creado_en
    return cuando.strftime("%Y-%m") if cuando else ""


def _orden(h: HistorialExtracto, fila) -> str:
    """Más viejo primero: por el corte del extracto; si no lo dice, por cuándo llegó el correo."""
    if h.fecha_corte:
        return str(h.fecha_corte)[:10]
    if _ultima_linea(h):
        return _ultima_linea(h)
    cuando = getattr(fila, "recibido_en", None) or h.creado_en
    return cuando.strftime("%Y-%m-%d") if cuando else ""


def _destino(h: HistorialExtracto, cuenta: Cuenta, cuentas: list[Cuenta], fila) -> Cuenta | None:
    """La tarjeta de crédito del mismo banco a la que debería pasar (solo si está en otra clase de cuenta y hay UNA)."""
    if producto_de_cuenta(cuenta) == CREDITO:
        return None
    texto = f"{getattr(fila, 'asunto', '') or ''} {getattr(fila, 'archivo', '') or ''} tarjeta de credito"
    s = reasignar_extracto.sugerir_cuenta_credito(h, cuenta, cuentas, texto)
    return next((c for c in cuentas if s and c.id == s["cuenta_id"]), None)


def _plan(db: Session, usuario) -> dict:
    """Qué hay que hacer con cada extracto de tarjeta (solo lectura). Los que ya están bien no salen."""
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all()
    por_id = {c.id: c for c in cuentas}
    hechas = {m.clave for m in db.query(MarcaCron).filter(
        MarcaCron.usuario_id == usuario.id, MarcaCron.valor == rx.VERSION_LECTOR,
        MarcaCron.clave.like(rx.PREFIJO + "%")).all()}
    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario.id).first()
    gmail = bool(perfil and perfil.gmail_conectado and perfil.gmail_refresh_token_enc)
    clave_guardada = db.query(ClavePdf).filter(ClavePdf.usuario_id == usuario.id).first() is not None

    todos = (db.query(HistorialExtracto)
             .filter(HistorialExtracto.usuario_id == usuario.id, HistorialExtracto.estado != "error").all())
    candidatos = []
    for h in todos:
        cuenta = por_id.get(h.cuenta_id)
        fila = rx.correo_de(db, h)
        if cuenta is None or fila is None or not rx.es_de_tarjeta(h, cuenta, fila):
            continue
        candidatos.append((h, cuenta, fila))
    candidatos.sort(key=lambda t: (_orden(t[0], t[2]), t[0].creado_en or datetime.min))

    filas = []
    for h, cuenta, fila in candidatos:
        destino = _destino(h, cuenta, cuentas, fila)
        mover = None
        if destino is not None:
            try:
                mover = reasignar_extracto.previa(db, usuario.id, h.id, destino.id)
            except HTTPException:
                destino, mover = None, None  # monedas distintas o cuenta sin permiso: no se mueve
        en_otra_cuenta = producto_de_cuenta(cuenta) != CREDITO
        # Releer en una cuenta que no es de crédito (y sin tarjeta a donde pasarlo) traería líneas a la cuenta equivocada.
        releer = (rx.PREFIJO + h.id) not in hechas and (not en_otra_cuenta or destino is not None)
        if destino is None and not releer:
            continue
        requiere_clave = fila.clave_resultado == "fallo" or (fila.estado == "falta_clave" and not clave_guardada)
        filas.append({
            "historial_id": h.id, "mes": _mes(h, fila), "corte": h.fecha_corte, "estado": h.estado,
            "cuenta_actual": {"id": cuenta.id, "nombre": cuenta.nombre},
            "cuenta_destino": {"id": destino.id, "nombre": destino.nombre} if destino else None,
            "movera": mover["movera"] if mover else 0,
            "duplicados": mover["duplicados"] if mover else 0,
            "releera": releer, "puede_releerse": gmail, "requiere_clave": requiere_clave,
            "_origen": mover["origen"] if mover else None, "_destino": mover["destino"] if mover else None,
            "_h": h, "_cuenta": cuenta, "_destino_obj": destino,
        })
    return {"filas": filas, "cuentas": por_id, "total_tarjeta": len(candidatos)}


def _saldos(plan: dict) -> dict:
    """Saldos antes/después por cuenta y en total (el total no cambia: solo se pasan movimientos entre cuentas)."""
    cambio: dict[str, float] = {}
    for f in plan["filas"]:
        if f["_origen"]:
            cambio[f["_origen"]["id"]] = cambio.get(f["_origen"]["id"], 0) + f["_origen"]["saldo_despues"] - f["_origen"]["saldo_antes"]
            cambio[f["_destino"]["id"]] = cambio.get(f["_destino"]["id"], 0) + f["_destino"]["saldo_despues"] - f["_destino"]["saldo_antes"]
    cuentas = [{"id": cid, "nombre": plan["cuentas"][cid].nombre, "saldo_antes": plan["cuentas"][cid].saldo or 0,
                "saldo_despues": (plan["cuentas"][cid].saldo or 0) + d} for cid, d in cambio.items()]
    antes, despues = sum(c["saldo_antes"] for c in cuentas), sum(c["saldo_despues"] for c in cuentas)
    return {"por_cuenta": cuentas, "total_antes": antes, "total_despues": despues}


def previa(db: Session, usuario) -> dict:
    """Vista previa SIN cambios (no toca Gmail): qué se haría con cada extracto y cómo quedarían los saldos."""
    plan = _plan(db, usuario)
    filas = plan["filas"]
    visibles = [{k: v for k, v in f.items() if not k.startswith("_")} for f in filas]
    return {
        "total": len(filas), "total_tarjeta": plan["total_tarjeta"], "maximo_por_llamada": MAXIMO_POR_LLAMADA,
        "se_arreglan_ahora": min(len(filas), MAXIMO_POR_LLAMADA),
        "movimientos_a_mover": sum(f["movera"] for f in filas),
        "extractos": visibles, "saldos": _saldos(plan),
    }


def _linea_lectura(r: dict) -> str:
    """Frase honesta de la lectura: dice si lo leído suma lo que dice el extracto."""
    n = r.get("lineas_leidas") or 0
    uno = "línea" if n == 1 else "líneas"
    if r.get("lectura_completa") is True:
        return f"Leí {n} {uno} y suman lo que dice tu extracto ✓"
    return r.get("mensaje_lectura") or f"Leí {n} {uno}, pero no pude compararlas con el resumen de tu extracto."


def _arreglar_uno(db: Session, usuario, f: dict) -> dict:
    h = f["_h"]
    out = {"historial_id": h.id, "mes": f["mes"], "movidos": 0, "nuevas": 0, "lineas_leidas": None,
           "lectura_completa": None, "mensaje_lectura": None, "estado": "sin_cambios", "motivo": None}
    if f["_destino_obj"] is not None:
        r = reasignar_extracto.cambiar(db, usuario.id, h.id, f["_destino_obj"].id)
        out["movidos"] = r["movidos"]
        out["estado"] = "arreglado" if r["movidos"] or not r["sin_cambios"] else "sin_cambios"
        db.refresh(h)
    if f["releera"]:
        try:
            r = rx.releer_historial(db, usuario, h, solo_agregar=True)
        except rx.ReleerError as e:
            if out["movidos"] or out["estado"] == "arreglado":
                out["estado"] = "parcial"  # ya pasó a su tarjeta; falta leerlo otra vez
            else:
                out["estado"] = "saltado"
            out["motivo"] = e.mensaje
            return out
        out.update(nuevas=r.get("por_importar", 0), lineas_leidas=r.get("lineas_leidas"),
                   lectura_completa=r.get("lectura_completa"), mensaje_lectura=_linea_lectura(r))
        if r["agregadas"] or out["estado"] == "arreglado":
            out["estado"] = "arreglado"
    return out


def arreglar(db: Session, usuario, maximo: int = MAXIMO_POR_LLAMADA) -> dict:
    """Aplica el arreglo a hasta `maximo` extractos (del más viejo al más nuevo). Un fallo no detiene al resto."""
    plan = _plan(db, usuario)
    filas = plan["filas"]
    lote, restantes = filas[:maximo], max(0, len(filas) - maximo)
    resultados = []
    for f in lote:
        try:
            r = _arreglar_uno(db, usuario, f)
        except HTTPException as e:
            db.rollback()
            r = {"historial_id": f["historial_id"], "mes": f["mes"], "movidos": 0, "nuevas": 0, "estado": "saltado",
                 "motivo": str(e.detail), "lineas_leidas": None, "lectura_completa": None, "mensaje_lectura": None}
        except Exception as e:  # noqa: BLE001 - un extracto roto no frena a los demás
            db.rollback()
            logger.warning("Arreglar tarjeta falló (usuario %s): %s", usuario.id[:8], type(e).__name__)
            r = {"historial_id": f["historial_id"], "mes": f["mes"], "movidos": 0, "nuevas": 0, "estado": "saltado",
                 "motivo": rx.MSG_FALLA, "lineas_leidas": None, "lectura_completa": None, "mensaje_lectura": None}
        r["cuenta_destino"] = f["cuenta_destino"] or f["cuenta_actual"]
        resultados.append(r)
    arreglados = [r for r in resultados if r["estado"] in ("arreglado", "parcial")]
    movidos = sum(r["movidos"] for r in resultados)
    nuevas = sum(r["nuevas"] for r in resultados)
    saltados = [r for r in resultados if r["estado"] in ("saltado", "parcial")]
    return {
        "ok": True, "arreglados": len(arreglados), "saltados": len(saltados), "movidos": movidos,
        "por_importar": nuevas, "restantes": restantes, "resultados": resultados,
        "resumen": resumen(len(arreglados), movidos, nuevas, len(saltados), restantes),
        "sin_cambios": not arreglados and not saltados,
    }


def resumen(arreglados: int, movidos: int, nuevas: int, saltados: int, restantes: int) -> str:
    """«Arreglé 6 extractos: moví 36 movimientos a tu tarjeta, encontré 41 compras por importar»."""
    if not arreglados and not saltados:
        return "Tus extractos de la tarjeta ya estaban bien. No cambié nada."
    def n(c, uno, varios):
        return f"{c} {uno if c == 1 else varios}"
    partes = []
    if movidos:
        partes.append(f"moví {n(movidos, 'movimiento', 'movimientos')} a tu tarjeta")
    if nuevas:
        partes.append(f"encontré {n(nuevas, 'compra', 'compras')} por importar")
    if not partes:
        partes.append("no encontré nada nuevo por importar")
    frase = (f"Arreglé {n(arreglados, 'extracto', 'extractos')}: " + ", ".join(partes)) if arreglados else "No pude arreglar nada ahora"
    if saltados:
        frase += f". {n(saltados, 'extracto quedó', 'extractos quedaron')} para después (te digo por qué abajo)"
    if restantes:
        frase += f". Quedan {restantes} por arreglar: vuelve a tocar el botón"
    return frase + "."
