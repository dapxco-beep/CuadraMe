"""Ajuste inicial RECALCULABLE: con cuánto empezó una cuenta, leído de su extracto más antiguo.

El problema: la app calcula el saldo de una cuenta sumando SOLO los movimientos importados. Si nadie registró con
cuánto empezó la cuenta, el saldo sale desfasado para siempre (la cuenta «siempre sale descuadrada»), aunque los
extractos digan el saldo exacto.

La regla (genérica, para cualquier usuario; la tarjeta de crédito tiene su variante al final):
  E0 = el extracto MÁS ANTIGUO de la cuenta con `saldo_inicial_extracto` confiable (origen «extracto» o «manual»).
  P0 = su primer día, S0 = su saldo inicial.
  M  = suma (regla única `delta_saldo`) de TODOS los movimientos de la cuenta anteriores a P0, SIN el propio ajuste.
  A  = S0 - M   → el libro de la cuenta vale S0 justo al empezar P0.
  El ajuste es un movimiento NEUTRO (fuente `ajuste_saldo`: ni ingreso ni gasto, regla única en contabilidad.py),
  fechado el día anterior a min(P0, primer movimiento registrado). Se reconoce por su nota: «Saldo inicial al …
  · automático» (sin columnas nuevas). Con |A| < $1 no hay movimiento (y si existía, se quita).

`recalcular` es idempotente: busca E0, calcula A y crea / actualiza / elimina el movimiento, dejando
`cuentas.saldo` = suma de TODOS los movimientos (incluido el ajuste). Se dispara cuando llega, cambia o se borra un
extracto, cuando se tocan movimientos de la cuenta, cuando cambia el punto de partida y al abrir «Traer movimientos».

Se respeta (no se recalcula, y `estado` dice por qué):
  - «desactivado»: la persona deshizo el ajuste (marca `ajuste_inicial_off:<cuenta>`); solo «Volver a calcular» lo reactiva.
  - «manual»: la persona registró a mano su saldo inicial (o lo fijó el punto de partida).
  - «saldo_fijado»: el saldo de la cuenta no es la suma de sus movimientos (lo fijó a mano).
  - «punto_partida»: el extracto queda antes del punto de partida elegido (no se inventa el pasado).
TARJETA DE CRÉDITO (deuda, no saldo; ver deuda_tarjeta.py): el ajuste se llama «Deuda inicial» y vale
  A = (− usado del extracto MÁS ANTIGUO) − Σ movimientos de la cuenta con fecha ≤ su corte (sin el propio ajuste),
con las mismas reglas (neutro, recalculable, deshacible, idempotente, respeta modo «hoy», saldo fijado y saldo inicial
a mano). Solo se crea si ese extracto se leyó completo y verificado (`lectura_completa`) y sin líneas por importar; si
no, no se inventa y `texto` dice qué falta.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app import cuadre_extracto as cx
from app import deuda_tarjeta as dt
from app import punto_partida
from app.compartidos import bloquear_cuenta
from app.contabilidad import FUENTE_AJUSTE, delta_saldo
from app.crons import MarcaCron
from app.models import Cuenta, HistorialExtracto, Movimiento

ORIGENES_VALIDOS = ("extracto", "manual")
SUFIJO_AUTOMATICO = " · automático"
EXPLICACION = "Es lo que tenías antes de tu primer extracto. No cuenta como ingreso ni gasto."
EXPLICACION_TARJETA = "Es lo que ya debías en tu tarjeta antes de tu primer extracto. No cuenta como ingreso ni gasto."


# En Postgres el bloqueo de la fila de la cuenta (FOR UPDATE) serializa a los procesos. SQLite lo ignora: dentro de este
# proceso un candado por cuenta cubre ese hueco (desarrollo y pruebas).
_CANDADOS: dict[str, threading.Lock] = defaultdict(threading.Lock)


# ── Marcas (sin commit: viajan con la transacción de quien llama) ───────────────────────────────
def clave_marca(cuenta_id: str) -> str:
    """Marca heredada de la versión «una sola vez» (quedó reclamada si ya se creó alguna vez)."""
    return f"saldo_inicial_auto:{cuenta_id}"


def clave_desactivado(cuenta_id: str) -> str:
    return f"ajuste_inicial_off:{cuenta_id}"


def clave_v2(cuenta_id: str) -> str:
    return f"ajuste_inicial_v2:{cuenta_id}"


def _hay_marca(db: Session, usuario_id: str, clave: str) -> bool:
    return db.query(MarcaCron.id).filter(MarcaCron.usuario_id == usuario_id, MarcaCron.clave == clave).first() is not None


def _poner_marca(db: Session, usuario_id: str, clave: str, valor: str = "1") -> None:
    if not _hay_marca(db, usuario_id, clave):
        db.add(MarcaCron(usuario_id=usuario_id, clave=clave, valor=valor))
        db.flush()


def _quitar_marca(db: Session, usuario_id: str, clave: str) -> None:
    db.query(MarcaCron).filter(MarcaCron.usuario_id == usuario_id, MarcaCron.clave == clave).delete(synchronize_session=False)
    db.flush()


def desactivado(db: Session, cuenta: Cuenta) -> bool:
    """¿La persona deshizo el ajuste? También cuenta la versión «una sola vez»: marca reclamada y ya sin movimiento."""
    uid = cuenta.usuario_id
    if _hay_marca(db, uid, clave_desactivado(cuenta.id)):
        return True
    return _hay_marca(db, uid, clave_marca(cuenta.id)) and not _hay_marca(db, uid, clave_v2(cuenta.id))


def desactivar(db: Session, cuenta: Cuenta) -> None:
    """La persona deshizo el ajuste: no se vuelve a crear solo. Sin commit."""
    _poner_marca(db, cuenta.usuario_id, clave_desactivado(cuenta.id))


# ── Reconocer el movimiento ────────────────────────────────────────────────────────────────────
def es_automatico(m) -> bool:
    g = (lambda k: m.get(k)) if isinstance(m, dict) else (lambda k: getattr(m, k, None))
    n = g("notas") or ""
    return g("fuente") == FUENTE_AJUSTE and n.startswith(cx.PREFIJO_INICIAL) and n.endswith(SUFIJO_AUTOMATICO)


def _es_saldo_inicial_propio(f: dict) -> bool:
    """Saldo inicial NO automático (a mano o del punto de partida): la persona ya dijo con cuánto empezó."""
    n = f.get("notas") or ""
    return f.get("fuente") == FUENTE_AJUSTE and n.startswith("Saldo inicial") and not es_automatico(f)


def _inicio_del_periodo(h: HistorialExtracto):
    """Primer día que cubre el extracto (si no lo trae, el día 1 del mes de su corte)."""
    d = cx.a_fecha(h.periodo_inicio)
    if d:
        return d
    corte = cx.a_fecha(h.fecha_corte)
    return corte.replace(day=1) if corte else None


def _extracto_mas_antiguo(db: Session, cuenta: Cuenta):
    """(inicio, historial) del extracto más antiguo con saldo inicial confiable en la moneda de la cuenta, o None."""
    mon = (cuenta.moneda or "").upper()
    cand = []
    for h in db.query(HistorialExtracto).filter(HistorialExtracto.cuenta_id == cuenta.id, HistorialExtracto.estado != "error"):
        if h.saldo_inicial_extracto is None or h.saldos_origen not in ORIGENES_VALIDOS:
            continue
        if mon and h.moneda and h.moneda.upper() != mon:
            continue  # el extracto está en otra moneda: no se mezcla
        inicio = _inicio_del_periodo(h)
        if inicio:
            cand.append((inicio, h))
    if not cand:
        return None
    cand.sort(key=lambda x: x[1].creado_en or datetime.min, reverse=True)  # empate de fechas: gana el más reciente
    return min(cand, key=lambda x: x[0])


def texto_aviso(monto: float, fecha, antes: float | None = None, tarjeta: bool = False) -> str:
    if tarjeta:
        if antes is None:
            return f"Registré con cuánto empezó tu tarjeta: debías {cx.pesos(monto)} al {cx.fecha_texto(fecha)}."
        return f"Actualicé con cuánto empezó tu tarjeta: debías {cx.pesos(monto)} al {cx.fecha_texto(fecha)} (antes {cx.pesos(antes)})."
    if antes is None:
        return f"Registré con cuánto empezó tu cuenta: {cx.pesos(monto)} al {cx.fecha_texto(fecha)}."
    return f"Actualicé con cuánto empezó tu cuenta: {cx.pesos(monto)} al {cx.fecha_texto(fecha)} (antes {cx.pesos(antes)})."


# ── Cálculo puro ───────────────────────────────────────────────────────────────────────────────
def deseado(filas: list[dict], inicio: date, saldo_inicial: float) -> tuple[float, date]:
    """(A, fecha) del ajuste: A = S0 - M, con M = suma de lo anterior a P0 sin el propio ajuste automático."""
    corte = datetime.combine(inicio, time.min)
    propias = [f for f in filas if not es_automatico(f)]
    m = sum(delta_saldo(f) for f in propias if f["fecha"] is None or f["fecha"] < corte)
    fechas = [f["fecha"].date() for f in propias if f["fecha"] is not None]
    ancla = min(inicio, min(fechas)) if fechas else inicio
    return round(float(saldo_inicial) - m, 2), ancla - timedelta(days=1)


def _res(cuenta: Cuenta, estado: str, **kw) -> dict:
    return {"estado": estado, "cambio": None, "cuenta_id": cuenta.id, "cuenta": cuenta.nombre,
            "saldo_cuenta": cuenta.saldo, **kw}


def proponer(db: Session, cuenta: Cuenta, inicio_pp: datetime | None = None) -> dict | None:
    """Qué ajuste inicial correspondería hoy a la cuenta (sin tocar nada), o None si no corresponde."""
    _, _, filas = cx._serie(db, cuenta.id)
    if (cuenta.tipo or "") == "credito":
        o = dt.objetivo_deuda_inicial(db, cuenta, filas, es_automatico)
        if o["estado"] != "ok" or (inicio_pp is not None and punto_partida.es_anterior(o["inicio"], inicio_pp)):
            return None
        monto, fecha, h, inicio = o["monto"], o["fecha"], o["h"], o["inicio"]
        if abs(monto) < cx.TOLERANCIA:
            return None
        return {"cuenta_id": cuenta.id, "cuenta": cuenta.nombre, "historial_id": h.id, "monto": monto, "fecha": fecha,
                "periodo_inicio": inicio}
    e0 = _extracto_mas_antiguo(db, cuenta)
    if not e0:
        return None
    inicio, h = e0
    if inicio_pp is not None and punto_partida.es_anterior(inicio, inicio_pp):
        return None
    monto, fecha = deseado(filas, inicio, h.saldo_inicial_extracto)
    if abs(monto) < cx.TOLERANCIA:
        return None
    return {"cuenta_id": cuenta.id, "cuenta": cuenta.nombre, "historial_id": h.id, "monto": monto, "fecha": fecha,
            "periodo_inicio": inicio}


def recalcular(db: Session, cuenta: Cuenta, inicio_pp: datetime | None = None, *, forzar: bool = False) -> dict:
    """Crea, actualiza o elimina el ajuste inicial automático de UNA cuenta. Idempotente. SIN commit (flush).

    `forzar` (el botón «Volver a calcular») levanta la marca de «desactivado». Bloquea la fila de la cuenta como el
    resto de operaciones de saldo, así dos procesos no se pisan. El dict devuelto trae `cambio`:
    «creado» | «actualizado» | «eliminado» | None (sin cambios) y un `texto` listo para mostrar."""
    cuenta = bloquear_cuenta(db, cuenta.id) or cuenta
    tarjeta = (cuenta.tipo or "") == "credito"
    uid = cuenta.usuario_id
    if tarjeta:
        dt.anclar_cuenta(db, cuenta)  # primero las anclas de deuda de cada extracto (la cadena); sin commit
        db.flush()
    if forzar:
        _quitar_marca(db, uid, clave_desactivado(cuenta.id))
        _quitar_marca(db, uid, clave_marca(cuenta.id))
    _, _, filas = cx._serie(db, cuenta.id)
    autos = [f for f in filas if es_automatico(f)]
    if desactivado(db, cuenta) and not forzar and (not autos or _hay_marca(db, uid, clave_desactivado(cuenta.id))):
        return _res(cuenta, "desactivado")
    if any(_es_saldo_inicial_propio(f) for f in filas):
        if autos:  # la persona dijo con cuánto empezó: lo suyo manda y el automático sobra
            for f in autos:
                sobra = db.get(Movimiento, f["id"])
                if sobra:
                    cuenta.saldo = round((cuenta.saldo or 0.0) - delta_saldo(sobra), 2)
                    db.delete(sobra)
            db.flush()
        return _res(cuenta, "manual")
    suma = sum(delta_saldo(f) for f in filas)
    if abs((cuenta.saldo or 0.0) - suma) >= cx.TOLERANCIA:
        return _res(cuenta, "saldo_fijado", texto="Tu saldo está fijado a mano: no lo cambio solo.")
    if tarjeta:
        o = dt.objetivo_deuda_inicial(db, cuenta, filas, es_automatico)
        e0 = (o["inicio"], o["h"]) if o["estado"] in ("ok", "incompleto") else None
    else:
        o = None
        e0 = _extracto_mas_antiguo(db, cuenta)
    if not e0:
        if autos:  # ya no queda ningún extracto que respalde el ajuste (se borró o se pasó a otra cuenta)
            antes = round(sum(delta_saldo(f) for f in autos), 2)
            for f in autos:
                sobra = db.get(Movimiento, f["id"])
                if sobra:
                    cuenta.saldo = round((cuenta.saldo or 0.0) - delta_saldo(sobra), 2)
                    db.delete(sobra)
            db.flush()
            return _res(cuenta, "sin_extracto", cambio="eliminado", monto=0.0, monto_antes=antes,
                        texto="Quité el saldo inicial automático: la cuenta ya no tiene extractos que lo respalden.")
        return _res(cuenta, "sin_extracto")
    inicio, h = e0
    if inicio_pp is not None and punto_partida.es_anterior(inicio, inicio_pp):
        return _res(cuenta, "punto_partida")
    if o is not None and o["estado"] == "incompleto":
        # La tarjeta no se inventa: sin el primer extracto leído completo no se sabe con cuánto empezó. Un ajuste que ya
        # existía se queda tal cual (no se mueve con datos a medias).
        return _res(cuenta, "sin_lectura", texto=o["texto"])

    monto, fecha = (o["monto"], o["fecha"]) if o is not None else deseado(filas, inicio, h.saldo_inicial_extracto)
    viejo = db.get(Movimiento, autos[0]["id"]) if autos else None
    for extra in autos[1:]:  # nunca debería haber dos; si los hay, queda uno
        sobra = db.get(Movimiento, extra["id"])
        if sobra:
            cuenta.saldo = round((cuenta.saldo or 0.0) - delta_saldo(sobra), 2)
            db.delete(sobra)
    antes = round(delta_saldo(viejo), 2) if viejo else None

    if abs(monto) < cx.TOLERANCIA:
        if not viejo:
            return _res(cuenta, "ok")
        cuenta.saldo = round((cuenta.saldo or 0.0) - delta_saldo(viejo), 2)
        db.delete(viejo)
        db.flush()
        return _res(cuenta, "ok", cambio="eliminado", monto=0.0, monto_antes=antes,
                    texto="Quité el saldo inicial automático: ya no hace falta.")

    nota = (f"{cx.PREFIJO_INICIAL} {cx.fecha_texto(fecha)} (según tu extracto)")[: 200 - len(SUFIJO_AUTOMATICO)] + SUFIJO_AUTOMATICO
    desc = dt.DESC_DEUDA_INICIAL if tarjeta else "Saldo inicial"
    cuando = datetime.combine(fecha, time.min)
    if viejo is None:
        mov = cx._nuevo_mov(cuenta, uid, cuando, desc, monto, nota)
        cuenta.saldo = round((cuenta.saldo or 0.0) + monto, 2)
        db.add(mov)
        cambio = "creado"
    else:
        if abs(antes - monto) < 0.005 and viejo.fecha == cuando and viejo.notas == nota:
            _poner_marca(db, uid, clave_v2(cuenta.id))
            return _res(cuenta, "ok", movimiento_id=viejo.id, monto=monto, fecha=fecha.isoformat())
        mov = viejo
        mov.tipo, mov.monto, mov.fecha, mov.notas = ("income" if monto > 0 else "expense"), round(abs(monto), 2), cuando, nota
        cuenta.saldo = round((cuenta.saldo or 0.0) - antes + monto, 2)
        cambio = "actualizado"
    db.flush()
    _poner_marca(db, uid, clave_v2(cuenta.id))
    cx.registrar_cuadre(db, cuenta, h)
    return _res(cuenta, "ok", cambio=cambio, movimiento_id=mov.id, monto=monto, monto_antes=antes, fecha=fecha.isoformat(),
                texto=texto_aviso(monto, fecha, antes if cambio == "actualizado" else None, tarjeta))


# ── Envoltorios con commit (los que llaman los endpoints) ───────────────────────────────────────
def refrescar(db: Session, cuenta_ids, inicio_pp: datetime | None = None, *, forzar: bool = False) -> list[dict]:
    """Recalcula el ajuste de varias cuentas (sin repetir), un commit por cuenta. Nunca estorba a quien llama: si
    algo falla, deshace solo esto. Devuelve solo las cuentas donde algo cambió."""
    out = []
    for cid in dict.fromkeys(c for c in cuenta_ids if c):
        try:
            c = db.get(Cuenta, cid)
            if not c:
                continue
            with _CANDADOS[cid]:
                db.expire_all()  # que lo que otro hilo acaba de guardar se vea antes de decidir
                r = recalcular(db, c, inicio_pp, forzar=forzar)
                db.commit()
            if r.get("cambio"):
                out.append(r)
        except Exception:  # noqa: BLE001
            db.rollback()
    return out


def refrescar_de_usuario(db: Session, usuario_id: str, cuenta_ids) -> list[dict]:
    """Igual que `refrescar`, leyendo el punto de partida de la persona."""
    return refrescar(db, cuenta_ids, punto_partida.fecha_inicio(db, usuario_id))


def registrar(db: Session, cuenta: Cuenta, inicio_pp: datetime | None = None) -> dict | None:
    """Recalcula UNA cuenta y devuelve el aviso si hubo cambio (None si no)."""
    r = refrescar(db, [cuenta.id], inicio_pp)
    return r[0] if r else None


def registrar_todas(db: Session, usuario_id: str, inicio_pp: datetime | None = None) -> list[dict]:
    """Pasa por las cuentas PROPIAS del usuario (no las compartidas). Idempotente: solo informa lo que cambió."""
    ids = [c.id for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).order_by(Cuenta.nombre).all()]
    return refrescar(db, ids, inicio_pp)


def estado_de_cuenta(db: Session, cuenta: Cuenta, inicio_pp: datetime | None = None) -> dict:
    """Lectura para la PWA: ¿hay ajuste automático?, ¿qué haría «Volver a calcular»? No cambia nada."""
    _, _, filas = cx._serie(db, cuenta.id)
    auto = next((f for f in filas if es_automatico(f)), None)
    p = proponer(db, cuenta, inicio_pp)
    falta = None
    if (cuenta.tipo or "") == "credito" and not auto:
        o = dt.objetivo_deuda_inicial(db, cuenta, filas, es_automatico)
        falta = o.get("texto") if o["estado"] == "incompleto" else None
    return {
        "cuenta_id": cuenta.id, "tarjeta": (cuenta.tipo or "") == "credito", "automatico": bool(auto),
        "movimiento_id": auto["id"] if auto else None, "monto": round(delta_saldo(auto), 2) if auto else None,
        "fecha": auto["fecha"].date().isoformat() if auto and auto["fecha"] else None,
        "desactivado": desactivado(db, cuenta), "propuesto": ({"monto": p["monto"], "fecha": p["fecha"].isoformat()} if p else None),
        "explicacion": EXPLICACION_TARJETA if (cuenta.tipo or "") == "credito" else EXPLICACION, "falta": falta,
    }
