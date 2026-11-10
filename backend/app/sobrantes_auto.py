"""Sobrantes que la app pasa SOLA a la cuenta correcta (parte del autoarreglo, deshacible por lote).

Caso típico: un pago de Apple Pay quedó guardado en la cuenta equivocada. El extracto de esa cuenta no lo trae («sobrante»)
y el extracto de OTRA cuenta tuya trae justo esa línea sin cruzar («faltante»). Si es UNA sola pareja posible (mismo tipo,
mismo monto a $1, <= 2 días, misma moneda) y nada la vuelve ambigua, el movimiento pasa a esa cuenta.

Nunca: tocar un movimiento ya conciliado con un extracto, uno que vino de un extracto, ni mover si hay dos pagos idénticos
(en el extracto, en la cuenta o en el destino): ahí no se hace nada y la persona decide con los botones de siempre."""
from __future__ import annotations

import json
import logging
from datetime import timedelta

from app import duplicados as dup
from app import estado_traer, saldo_inicial_auto
from app.compartidos import bloquear_cuenta
from app.conciliacion import parse_bank_date
from app.contabilidad import delta_saldo
from app.models import Cuenta, HistorialExtracto, HuellaOrigen, Movimiento
from app.utiles import ahora_co

logger = logging.getLogger(__name__)

VENTANA = timedelta(days=2)
MAX_POR_CORRIDA = 20


def _review(h: HistorialExtracto) -> list[dict]:
    try:
        r = json.loads(h.review_json or "[]")
    except ValueError:
        return []
    return r if isinstance(r, list) else []


def _parecido(monto_a, monto_b) -> bool:
    return abs(float(monto_a or 0) - float(monto_b or 0)) < 1


def _fecha_item(item: dict):
    return parse_bank_date(item.get("fecha"))


def _cerca(a, b) -> bool:
    return a is not None and b is not None and abs(a - b) <= VENTANA


def _destino_unico(db, uid: str, mov: Movimiento, x: HistorialExtracto, review_x: list[dict], cuentas: dict[str, Cuenta],
                   historiales: list[HistorialExtracto]):
    """(historial destino, línea) si hay UNA sola pareja posible para `mov` en el extracto de otra cuenta tuya; si no, None."""
    origen = cuentas[x.cuenta_id]
    # 1) Nada del lado de origen debe ser ambiguo: otro sobrante, otra línea o otro movimiento idénticos.
    for i in review_x:
        if i.get("match_id") == mov.id or i.get("tipo") != mov.tipo or not _parecido(i.get("monto"), mov.monto):
            continue
        if i.get("estado") in ("sobrante", "faltante", "dudoso") and _cerca(_fecha_item(i), mov.fecha):
            return None
    gemelos = db.query(Movimiento.id).filter(
        Movimiento.cuenta_id == origen.id, Movimiento.id != mov.id, Movimiento.tipo == mov.tipo,
        Movimiento.fecha >= mov.fecha - VENTANA, Movimiento.fecha <= mov.fecha + VENTANA).all()
    if any(_parecido(db.get(Movimiento, g[0]).monto, mov.monto) for g in gemelos):
        return None
    # 2) Exactamente UNA línea sin cruzar, en el extracto de OTRA cuenta de la misma moneda.
    hallazgos = []
    for h in historiales:
        c = cuentas.get(h.cuenta_id)
        if h.id == x.id or c is None or c.id == origen.id or (c.moneda or "COP") != (origen.moneda or "COP"):
            continue
        for i in _review(h):
            if i.get("tipo") == mov.tipo and _parecido(i.get("monto"), mov.monto) and _cerca(_fecha_item(i), mov.fecha):
                hallazgos.append((h, i))
    if len(hallazgos) != 1 or hallazgos[0][1].get("estado") != "faltante":
        return None
    h, linea = hallazgos[0]
    # 3) En la cuenta destino no puede haber ya un movimiento igual (sería un repetido, no un movimiento mal puesto).
    ya = db.query(Movimiento).filter(
        Movimiento.cuenta_id == h.cuenta_id, Movimiento.tipo == mov.tipo,
        Movimiento.fecha >= mov.fecha - VENTANA, Movimiento.fecha <= mov.fecha + VENTANA).all()
    if any(_parecido(m.monto, mov.monto) for m in ya):
        return None
    return h, linea


def mover_sobrantes(db, usuario, excluidos: set[str] | None = None) -> int:
    """Pasa cada sobrante seguro a la cuenta de su pareja. Devuelve cuántos movió (con commit)."""
    uid = usuario.id
    excluidos = excluidos or set()
    cuentas = {c.id: c for c in db.query(Cuenta).filter(Cuenta.usuario_id == uid).all()}
    if len(cuentas) < 2:
        return 0
    historiales = [h for h in db.query(HistorialExtracto).filter(
        HistorialExtracto.usuario_id == uid, HistorialExtracto.estado == "pendiente_revision").all()
        if h.cuenta_id in cuentas and h.id not in excluidos]
    movidos = 0
    for x in historiales:
        review_x = _review(x)
        for item in review_x:
            if movidos >= MAX_POR_CORRIDA:
                return movidos
            if item.get("estado") != "sobrante" or not item.get("match_id"):
                continue
            mov = db.get(Movimiento, item["match_id"])
            if (mov is None or mov.usuario_id != uid or mov.cuenta_id != x.cuenta_id or mov.conciliado_en is not None
                    or mov.fecha is None or mov.tipo not in ("income", "expense")
                    or dup.origen_de_movimiento(mov) == dup.ORIGEN_EXTRACTO):
                continue
            par = _destino_unico(db, uid, mov, x, review_x, cuentas, historiales)
            if par is None:
                continue
            if _mover(db, usuario, mov, x, item, review_x, par[0], par[1], cuentas):
                movidos += 1
    return movidos


def _mover(db, usuario, mov: Movimiento, x: HistorialExtracto, item: dict, review_x: list[dict],
           y: HistorialExtracto, linea: dict, cuentas: dict[str, Cuenta]) -> bool:
    review_y = _review(y)
    linea_y = next((i for i in review_y if i.get("fingerprint") == linea.get("fingerprint") and i.get("estado") == "faltante"), None)
    if linea_y is None:
        return False
    try:
        origen_id, destino_id = x.cuenta_id, y.cuenta_id
        bloq = {cid: bloquear_cuenta(db, cid) for cid in sorted((origen_id, destino_id))}
        origen, destino = bloq[origen_id], bloq[destino_id]
        if origen is None or destino is None or db.get(Movimiento, mov.id).cuenta_id != origen_id:
            db.rollback()
            return False
        origen.saldo = round((origen.saldo or 0) - delta_saldo(mov), 2)
        destino.saldo = round((destino.saldo or 0) + delta_saldo(mov), 2)
        mov.cuenta_id = destino_id
        mov.conciliado_en, mov.extracto_id = ahora_co(), y.id  # ahora lo respalda el extracto de su cuenta
        db.query(HuellaOrigen).filter(HuellaOrigen.movimiento_id == mov.id).update(
            {HuellaOrigen.cuenta_id: destino_id}, synchronize_session=False)
        # Revisión de ambos extractos.
        item["estado"], item["resuelto"] = "sobrante_resuelto", "movido"
        item["movido_a"] = destino.nombre
        linea_y["estado"], linea_y["match_id"] = "completado", mov.id
        linea_y["movido_desde"] = origen.nombre
        x.review_json = json.dumps(review_x, default=str)
        y.review_json = json.dumps(review_y, default=str)
        estado_traer.sincronizar_contadores(y, review_y)
        db.commit()
        saldo_inicial_auto.refrescar_de_usuario(db, usuario.id, [origen_id, destino_id])
        return True
    except Exception as e:  # noqa: BLE001 - un sobrante raro no frena a los demás
        db.rollback()
        logger.warning("Autoarreglo sobrantes falló (usuario %s): %s", usuario.id[:8], type(e).__name__)
        return False
