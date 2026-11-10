"""Traslados entre tus cuentas que la app marca SOLA cuando no hay duda (parte del autoarreglo, deshacible por lote).

Solo pares exactos 1:1: un egreso y un ingreso del mismo monto (a $1), cuentas PROPIAS distintas, misma moneda, a <= 2 días,
y que NINGUNO tenga otro candidato del mismo monto en esa ventana (dos pagos reales idénticos = ambiguo = no se hace nada).
Los pares con comisión (diferencia) o ambiguos siguen preguntándose en «Revisar posibles traslados».
Marcar = poner la marca en `notas` (la misma que «Es un traslado entre mis cuentas»); el dinero y los saldos no se mueven."""
from __future__ import annotations

from datetime import timedelta

from app import punto_partida
from app.contabilidad import (VENTANA_EMPAREJAR_SEG, notas_con_decision, sugerir_traslados, tipos_cuenta_de)
from app.models import Cuenta, Movimiento
from app.utiles import ahora_co

DIAS_REVISION = 180
MAX_POR_CORRIDA = 50


def _moneda(m: Movimiento, monedas: dict) -> str | None:
    return monedas.get(m.cuenta_id) or getattr(m, "moneda", None)


def _hay_otro(m: Movimiento, par: Movimiento, todos: list[Movimiento], monedas: dict) -> bool:
    """¿Hay, además de `par`, otro movimiento del sentido contrario con el mismo monto en la ventana de `m`?"""
    tipo_contrario = par.tipo
    for o in todos:
        if o.id in (m.id, par.id) or o.tipo != tipo_contrario or o.cuenta_id == m.cuenta_id or not o.fecha:
            continue
        if abs((o.monto or 0) - (m.monto or 0)) >= 1 or abs((o.fecha - m.fecha).total_seconds()) > VENTANA_EMPAREJAR_SEG:
            continue
        mo, mm = _moneda(o, monedas), _moneda(m, monedas)
        if mo and mm and mo != mm:
            continue
        return True
    return False


def pares_seguros(db, uid: str) -> list[tuple[Movimiento, Movimiento]]:
    """[(egreso, ingreso)] de pares exactos y únicos, ambos movimientos y cuentas del usuario. Solo lee."""
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == uid).all()
    ids = [c.id for c in cuentas]
    if len(ids) < 2:
        return []
    desde = ahora_co() - timedelta(days=DIAS_REVISION)
    inicio = punto_partida.fecha_inicio(db, uid)
    if inicio and desde < inicio:
        desde = inicio
    movs = db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids), Movimiento.fecha >= desde).all()
    por_id = {m.id: m for m in movs}
    tc = tipos_cuenta_de(db, ids, None)
    monedas = getattr(tc, "monedas", None) or {}
    out = []
    for s in sugerir_traslados(movs, tc):
        if s["tipo"] != "par" or s["diferencia"] != 0:
            continue
        g, i = por_id[s["ids"][0]], por_id[s["ids"][1]]
        if g.usuario_id != uid or i.usuario_id != uid or abs((g.monto or 0) - (i.monto or 0)) >= 1:
            continue
        if _hay_otro(g, i, movs, monedas) or _hay_otro(i, g, movs, monedas):
            continue
        out.append((g, i))
    return out[:MAX_POR_CORRIDA]


def marcar_seguros(db, uid: str) -> int:
    """Marca como traslado los pares seguros. Devuelve cuántos pares marcó."""
    pares = pares_seguros(db, uid)
    for g, i in pares:
        g.notas = notas_con_decision(g.notas, "traslado")
        i.notas = notas_con_decision(i.notas, "traslado")
    if pares:
        db.commit()
    return len(pares)
