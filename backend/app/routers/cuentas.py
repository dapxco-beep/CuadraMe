from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.compartidos import bloquear_cuenta, cuenta_accesible, cuentas_ids_accesibles, puede_editar_cuenta
from app.contabilidad import CATEGORIA_AJUSTE, FUENTE_AJUSTE, tipos_cuenta_de, tipos_efectivos
from app.database import get_db
from app.fx import convertir_a_cop
from app.models import Cuenta, Movimiento
from app.schemas import AjusteSaldoRequest, CuentaCreate, CuentaOut, CuentaUpdate
from app.utiles import ahora_co
from app.tarjetas import calc_tarjeta, extractos_guardados, movimientos_tras_corte, sin_historial_al_corte

router = APIRouter(prefix="/cuentas", tags=["cuentas"])


def _serializar(cuenta: Cuenta, db: Session | None = None) -> dict:
    """Cuenta + (si es tarjeta de crédito) los cálculos de cupo y fechas. Con `db`
    también el extracto (total a pagar al corte, pagado, falta)."""
    tarjeta = None
    if cuenta.tipo == "credito":
        movs = movimientos_tras_corte(db, cuenta) if db is not None and cuenta.dia_corte else None
        guardado = extractos_guardados(db, [cuenta.id]).get(cuenta.id) if db is not None else None
        declarado = bool(movs is not None and sin_historial_al_corte(db, cuenta))
        tarjeta = calc_tarjeta(cuenta, None, movs, guardado, declarado)
    return {
        "id": cuenta.id,
        "nombre": cuenta.nombre,
        "tipo": cuenta.tipo,
        "saldo": cuenta.saldo,
        "moneda": cuenta.moneda,
        "icono": cuenta.icono,
        "cupo_total": cuenta.cupo_total,
        "dia_corte": cuenta.dia_corte,
        "dia_pago": cuenta.dia_pago,
        "tasa_ea": cuenta.tasa_ea,
        "alias_tarjeta": cuenta.alias_tarjeta,
        "tarjeta": tarjeta,
    }


@router.get("", response_model=list[CuentaOut])
def listar_cuentas(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    ids = cuentas_ids_accesibles(db, usuario.id)
    return [_serializar(c, db) for c in db.query(Cuenta).filter(Cuenta.id.in_(ids)).all()]


@router.post("", response_model=CuentaOut)
def crear_cuenta(
    data: CuentaCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = Cuenta(usuario_id=usuario.id, **data.model_dump())
    db.add(cuenta)
    db.commit()
    db.refresh(cuenta)
    return _serializar(cuenta, db)


@router.put("/{cuenta_id}", response_model=CuentaOut)
def editar_cuenta(
    cuenta_id: str,
    data: CuentaUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = (
        db.query(Cuenta)
        .filter(Cuenta.id == cuenta_id, Cuenta.usuario_id == usuario.id)
        .first()
    )
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(cuenta, campo, valor)

    db.commit()
    db.refresh(cuenta)
    return _serializar(cuenta, db)


@router.delete("/{cuenta_id}")
def eliminar_cuenta(
    cuenta_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = (
        db.query(Cuenta)
        .filter(Cuenta.id == cuenta_id, Cuenta.usuario_id == usuario.id)
        .first()
    )
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    tiene_movimientos = (
        db.query(Movimiento.id).filter(Movimiento.cuenta_id == cuenta_id).first()
        is not None
    )
    if tiene_movimientos:
        raise HTTPException(
            status_code=400,
            detail="Esta cuenta tiene movimientos registrados y no se puede eliminar. Puedes dejarla en $0 en vez de borrarla.",
        )

    from app.models_rendimientos import Cajita

    db.query(Cajita).filter(Cajita.cuenta_id == cuenta_id).delete()  # sus cajitas no sobreviven a la cuenta
    db.delete(cuenta)
    db.commit()
    return {"ok": True}


# ── Saldo claro: resumen, detalle y ajuste ─────────────────────────

def _ultimos_movs(db: Session, cuenta_ids: list[str]) -> dict[str, datetime]:
    """{cuenta_id: fecha del último movimiento} (para el 'actualizado el...')."""
    filas = (
        db.query(Movimiento.cuenta_id, func.max(Movimiento.fecha))
        .filter(Movimiento.cuenta_id.in_(cuenta_ids))
        .group_by(Movimiento.cuenta_id)
        .all()
    )
    return {cid: f for cid, f in filas}


@router.get("/resumen")
def resumen_saldos(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Todo lo que hace falta para explicar el 'Saldo actual': el total en COP, cuánto
    es plata disponible hoy (cuentas que no son tarjeta) y cuánto es deuda de tarjetas,
    más los totales por moneda y por tipo de cuenta."""
    ids = cuentas_ids_accesibles(db, usuario.id)
    cuentas = db.query(Cuenta).filter(Cuenta.id.in_(ids)).all() if ids else []
    ultimos = _ultimos_movs(db, ids) if ids else {}

    total = disponible = deudas = 0.0
    por_moneda: dict[str, float] = {}
    por_tipo: dict[str, float] = {}
    for c in cuentas:
        moneda = c.moneda or "COP"
        cop = convertir_a_cop(c.saldo or 0, moneda)
        total += cop
        if c.tipo == "credito":
            deudas += max(0.0, -cop)
        else:
            disponible += cop
        por_moneda[moneda] = por_moneda.get(moneda, 0.0) + (c.saldo or 0)
        por_tipo[c.tipo] = por_tipo.get(c.tipo, 0.0) + cop
    ultimo = max(ultimos.values()) if ultimos else None
    return {
        "total_cop": round(total, 2),
        "disponible_cop": round(disponible, 2),
        "deudas_tarjeta_cop": round(deudas, 2),
        "por_moneda": {k: round(v, 2) for k, v in por_moneda.items()},
        "por_tipo": {k: round(v, 2) for k, v in por_tipo.items()},
        "ultimo_movimiento": ultimo.isoformat() if ultimo else None,
        "ultimo_por_cuenta": {k: v.isoformat() for k, v in ultimos.items()},
        "hay_movimientos": bool(ultimos),
    }


@router.get("/{cuenta_id}/detalle")
def detalle_cuenta(
    cuenta_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Saldo actual de UNA cuenta + ingresos/gastos reales del mes (con la regla
    contable: sin pagos de tarjeta, traslados ni ajustes) + últimos movimientos."""
    cuenta = cuenta_accesible(db, usuario.id, cuenta_id)
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    inicio_mes = ahora_co().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # 3 días antes del mes: solo para emparejar traslados del borde (igual que gastos_por_categoria).
    # Se leen los movimientos de TODAS tus cuentas: la otra pata de un traslado vive en otra cuenta,
    # y sin ella (ni tu nombre ni tus reglas) el traslado se vería como ingreso o gasto de ésta.
    ids = cuentas_ids_accesibles(db, usuario.id)
    movs_mes = (
        db.query(Movimiento)
        .filter(Movimiento.cuenta_id.in_(ids), Movimiento.fecha >= inicio_mes - timedelta(days=3))
        .all()
    )
    te = tipos_efectivos(movs_mes, tipos_cuenta_de(db, ids))
    ingresos = sum(m.monto for m in movs_mes if m.cuenta_id == cuenta.id and m.fecha >= inicio_mes and te[m.id] == "income")
    gastos = sum(m.monto for m in movs_mes if m.cuenta_id == cuenta.id and m.fecha >= inicio_mes and te[m.id] == "expense")
    ultimos = (
        db.query(Movimiento)
        .filter(Movimiento.cuenta_id == cuenta.id)
        .order_by(Movimiento.fecha.desc())
        .limit(8)
        .all()
    )
    return {
        "cuenta": _serializar(cuenta, db),
        "saldo_actual": cuenta.saldo,
        "ingresos_mes": round(ingresos, 2),
        "gastos_mes": round(gastos, 2),
        "ultimo_movimiento": ultimos[0].fecha.isoformat() if ultimos else None,
        "movimientos": [
            {
                "id": m.id, "fecha": m.fecha.isoformat(), "descripcion": m.titulo or m.descripcion, "titulo": m.titulo,
                "categoria": m.categoria, "tipo": m.tipo, "monto": m.monto, "fuente": m.fuente,
            }
            for m in ultimos
        ],
    }


@router.post("/{cuenta_id}/ajustar-saldo")
def ajustar_saldo(
    cuenta_id: str,
    data: AjusteSaldoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """El usuario escribe el saldo REAL (el que ve en su banco) y la app crea un
    movimiento 'Ajuste de saldo' por la diferencia. Ese movimiento mueve el saldo
    pero NO cuenta como gasto ni ingreso (ver contabilidad.FUENTE_AJUSTE).
    Para una tarjeta, el saldo es negativo cuando debes (-800.000 = debes 800.000)."""
    cuenta = cuenta_accesible(db, usuario.id, cuenta_id)
    if not cuenta or not puede_editar_cuenta(db, usuario.id, cuenta):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    if abs(data.saldo_real) > 1e12:
        raise HTTPException(status_code=400, detail="Ese saldo no parece válido")
    cuenta = bloquear_cuenta(db, cuenta_id)  # evita carreras con otro movimiento simultáneo
    anterior = cuenta.saldo or 0.0
    diferencia = round(data.saldo_real - anterior, 2)
    if abs(diferencia) < 0.005:
        return {"ok": True, "ajustado": False, "saldo": anterior, "diferencia": 0.0, "movimiento_id": None}

    mov = Movimiento(
        usuario_id=usuario.id,
        cuenta_id=cuenta.id,
        fecha=ahora_co(),
        descripcion="Ajuste de saldo",
        categoria=CATEGORIA_AJUSTE,
        tipo="income" if diferencia > 0 else "expense",
        monto=abs(diferencia),
        fuente=FUENTE_AJUSTE,
        notas=(data.nota or f"Saldo anterior {anterior:,.2f}")[:200],
    )
    cuenta.saldo = anterior + diferencia
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return {"ok": True, "ajustado": True, "saldo": cuenta.saldo, "diferencia": diferencia, "movimiento_id": mov.id}
