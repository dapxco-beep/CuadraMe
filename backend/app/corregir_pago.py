"""Corregir el monto de un movimiento YA importado cuando el lector de extractos cambió de criterio.

Caso de origen (tarjeta Nu): el lector viejo leyó «Pago $A -$B -$C» como un pago de B; el lector de hoy sabe que
A es lo que pagaste y que B y C son cómo se aplicó. Sin esto, al importar la tarjeta recibiría DOS pagos del
mismo día (el viejo por B y el nuevo por A).

Política (docs/RELECTURA_DE_TARJETAS.md):
  · Solo corrige cuando el LECTOR lo declara con una regla explícita en la línea (`corrige_lectura`:
    descripción que dejaba el lector anterior + montos con que la leyó). NUNCA por parecido de monto.
  · Línea nueva + movimiento viejo (misma cuenta, ±3 días, descripción vieja, monto en la regla)
        -> la línea pasa a `corregir_monto`; al importar se ACTUALIZA el movimiento (mismo id, fecha, vínculos,
           categoría y marca de traslado), el saldo de la cuenta cambia en A−B y no se crea otro movimiento.
  · Si ya están los dos (el viejo por B y el nuevo por A), la línea vieja pasa a `quitar_repetido`; al importar se
    borra con motivo «error» (sin fantasma que bloquee), se revierte su saldo y se recalcula el ajuste inicial.
  · Idempotente: un movimiento ya corregido no coincide con la regla (su monto es A), así que no vuelve a salir.
Sin columnas nuevas: todo vive en la revisión guardada (review_json) y en el movimiento."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app import duplicados as dup
from app.compartidos import bloquear_cuenta
from app.conciliacion import normalize_texto, parse_bank_date
from app.contabilidad import delta_saldo
from app.models import HuellaOrigen, Movimiento
from app.utiles import ahora_co

CORREGIR = "corregir_monto"
QUITAR = "quitar_repetido"
ESTADOS_CORRECCION = (CORREGIR, QUITAR)
VENTANA_DIAS = 3
TOL_MONTO = 0.5
_CON_MOVIMIENTO = ("importado", "exacto", "aproximado", "completado")


def _igual(a, b) -> bool:
    return abs(float(a or 0) - float(b or 0)) <= TOL_MONTO


def _en(monto, montos) -> bool:
    return any(_igual(monto, m) for m in montos)


def regla_de(item: dict) -> dict | None:
    """La regla explícita del lector, bien formada; sin ella no hay corrección posible."""
    r = item.get("corrige_lectura")
    if not isinstance(r, dict) or not r.get("descripcion") or not r.get("tipo"):
        return None
    montos = [float(m) for m in (r.get("montos") or []) if isinstance(m, (int, float))]
    return {"descripcion": r["descripcion"], "tipo": r["tipo"], "montos": montos} if montos else None


def _cerca(f1, f2) -> bool:
    return bool(f1 and f2 and abs((f1.date() - f2.date()).days) <= VENTANA_DIAS)


def _candidatos(db: Session, usuario_id: str, cuenta_id: str, fecha, regla: dict) -> list[Movimiento]:
    """Movimientos de la cuenta con la descripción vieja del lector, en la ventana de días (cualquier monto)."""
    if not fecha:
        return []
    filas = (db.query(Movimiento)
             .filter(Movimiento.usuario_id == usuario_id, Movimiento.cuenta_id == cuenta_id,
                     Movimiento.tipo == regla["tipo"],
                     Movimiento.fecha >= fecha - timedelta(days=VENTANA_DIAS),
                     Movimiento.fecha < fecha + timedelta(days=VENTANA_DIAS + 1))
             .order_by(Movimiento.fecha, Movimiento.id).all())
    clave = normalize_texto(regla["descripcion"])
    return [m for m in filas if normalize_texto(m.descripcion or "") == clave]


def _movimiento_valido(db: Session, usuario_id: str, cuenta_id: str, mov_id, regla: dict) -> Movimiento | None:
    """El movimiento que dice la revisión, solo si SIGUE siendo de esta persona, de esta cuenta y de la lectura vieja."""
    if not mov_id:
        return None
    m = db.get(Movimiento, mov_id)
    if (m is None or m.usuario_id != usuario_id or m.cuenta_id != cuenta_id or m.tipo != regla["tipo"]
            or normalize_texto(m.descripcion or "") != normalize_texto(regla["descripcion"])
            or not _en(m.monto, regla["montos"])):
        return None
    return m


# ── Marcar la revisión (relectura y procesar) ─────────────────────────────────────────────────────
def marcar(db: Session, usuario_id: str, cuenta_id: str, review: list[dict]) -> int:
    """Pone `corregir_monto` / `quitar_repetido` donde una regla del lector lo pide. Devuelve cuántas líneas cambió
    (para que quien llama guarde la revisión). No toca la base de datos."""
    cambios = 0
    reclamados: set[str] = set()

    # 1) Línea nueva por A + movimiento viejo por B (o C): corregir el monto, no crear otro pago.
    for it in review:
        regla = regla_de(it)
        if not regla or it.get("estado") not in ("faltante", CORREGIR):
            continue
        fecha = parse_bank_date(it.get("fecha"))
        mov = next((m for m in _candidatos(db, usuario_id, cuenta_id, fecha, regla)
                    if m.id not in reclamados and _en(m.monto, regla["montos"]) and not _igual(m.monto, it["monto"])), None)
        if mov is not None:
            reclamados.add(mov.id)
            if it.get("estado") != CORREGIR or it.get("corrige_movimiento_id") != mov.id:
                cambios += 1
            it.update({"estado": CORREGIR, "corrige_movimiento_id": mov.id, "monto_anterior": float(mov.monto),
                       "marcar_por_defecto": True, "aviso_linea": None})
        elif it.get("estado") == CORREGIR:  # el movimiento ya no está (o ya se corrigió): vuelve a ser un pago normal
            for k in ("corrige_movimiento_id", "monto_anterior"):
                it.pop(k, None)
            it["estado"] = "faltante"
            cambios += 1

    # 2) Ya están los dos (el viejo por B y el nuevo por A): ofrecer quitar el repetido.
    confirmados: set[int] = set()
    for nuevo in review:
        regla = regla_de(nuevo)
        if not regla or nuevo.get("estado") not in _CON_MOVIMIENTO:
            continue
        f_nuevo = parse_bank_date(nuevo.get("fecha"))
        clave = normalize_texto(regla["descripcion"])
        for viejo in review:
            if (viejo is nuevo or id(viejo) in confirmados or viejo.get("estado") not in ("importado", QUITAR)
                    or normalize_texto(viejo.get("descripcion") or "") != clave or viejo.get("tipo") != regla["tipo"]
                    or not _en(viejo.get("monto"), regla["montos"]) or _igual(viejo.get("monto"), nuevo.get("monto"))
                    or not _cerca(parse_bank_date(viejo.get("fecha")), f_nuevo)):
                continue
            mov = _movimiento_valido(db, usuario_id, cuenta_id, viejo.get("movimiento_id"), regla)
            if mov is None:
                mov = next((m for m in _candidatos(db, usuario_id, cuenta_id, f_nuevo, regla)
                            if m.id not in reclamados and _igual(m.monto, viejo.get("monto"))), None)
            if mov is None:
                continue
            reclamados.add(mov.id)
            confirmados.add(id(viejo))
            if viejo.get("estado") != QUITAR:
                cambios += 1
            viejo.update({"estado": QUITAR, "movimiento_id": mov.id, "monto_correcto": float(nuevo["monto"]),
                          "marcar_por_defecto": True, "corrige_lectura": regla})
            break
    for viejo in review:
        if viejo.get("estado") == QUITAR and id(viejo) not in confirmados:
            for k in ("monto_correcto", "corrige_lectura"):
                viejo.pop(k, None)
            viejo["estado"] = "importado"
            cambios += 1
    return cambios


# ── Aplicar al importar ───────────────────────────────────────────────────────────────────────────
def _refrescar_canales(db: Session, mov: Movimiento, huella: str | None) -> None:
    """Las huellas del movimiento llevan la «foto» (monto, clave): se actualizan para que un fantasma o un
    emparejamiento futuro lo vea con el monto de hoy. El canal «extracto» queda con la huella de la línea nueva."""
    db.flush()
    foto = dup._foto(mov)
    for f in db.query(HuellaOrigen).filter(HuellaOrigen.usuario_id == mov.usuario_id,
                                           HuellaOrigen.movimiento_id == mov.id).all():
        for k, v in foto.items():
            setattr(f, k, v)
        if huella and f.origen == dup.ORIGEN_EXTRACTO and f.estado == dup.ESTADO_VIGENTE:
            f.huella = huella
    dup.registrar_canal(db, mov, dup.ORIGEN_EXTRACTO, huella)


def corregir(db: Session, usuario_id: str, cuenta, historial_id: str, item: dict, huella: str | None) -> dict | None:
    """Actualiza el monto del movimiento viejo al de la línea nueva. None si ya no se puede (el movimiento no está,
    cambió o no es de esta cuenta): quien llama entonces trata la línea como un pago normal. Sin commit."""
    regla = regla_de(item)
    if not regla:
        return None
    mov = _movimiento_valido(db, usuario_id, cuenta.id, item.get("corrige_movimiento_id"), regla)
    if mov is None:
        mov = next((m for m in _candidatos(db, usuario_id, cuenta.id, parse_bank_date(item.get("fecha")), regla)
                    if _en(m.monto, regla["montos"]) and not _igual(m.monto, item["monto"])), None)
    if mov is None:
        return None
    cuenta = bloquear_cuenta(db, cuenta.id) or cuenta
    anterior, antes = float(mov.monto), delta_saldo(mov)
    mov.monto = round(float(item["monto"]), 2)
    mov.descripcion = item["descripcion"]  # el texto de hoy: así la línea coincide con el movimiento (sin duplicar luego)
    cuenta.saldo += delta_saldo(mov) - antes
    mov.conciliado_en = ahora_co()
    mov.extracto_id = historial_id
    _refrescar_canales(db, mov, huella)
    return {"movimiento_id": mov.id, "monto_anterior": anterior}


def quitar(db: Session, usuario_id: str, cuenta, item: dict) -> bool:
    """Borra el pago viejo repetido (motivo «error»: sin fantasma) y revierte su efecto en la cuenta. Sin commit."""
    regla = regla_de(item)
    if not regla:
        return False
    mov = _movimiento_valido(db, usuario_id, cuenta.id, item.get("movimiento_id"), regla)
    if mov is None:
        return False
    cuenta = bloquear_cuenta(db, cuenta.id) or cuenta
    cuenta.saldo -= delta_saldo(mov)
    dup.registrar_borrado(db, mov, dup.MOTIVO_ERROR)
    db.flush()
    db.delete(mov)
    return True
