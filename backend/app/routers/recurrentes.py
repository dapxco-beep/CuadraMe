
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.utiles import ahora_co
from app.auth import UsuarioActual, get_current_user
from app.conciliacion import normalize_texto
from app.database import get_db
from app.compartidos import cuentas_ids_accesibles
from app.contabilidad import tipos_cuenta_de, tipos_efectivos
from app.deteccion import detectar_recurrentes
from app.finanzas import calc_estado_recurrente
from app.models import Cuenta, Movimiento, Recurrente
from app.schemas import MarcarPagadoRequest, RecurrenteCreate, RecurrenteOut, RecurrenteSugerido

router = APIRouter(prefix="/recurrentes", tags=["recurrentes"])


def _serializar(rec: Recurrente) -> dict:
    return {
        "id": rec.id,
        "nombre": rec.nombre,
        "monto": rec.monto,
        "tipo": rec.tipo,
        "categoria": rec.categoria,
        "cuenta_id": rec.cuenta_id,
        "dia_del_mes": rec.dia_del_mes,
        "alerta_dias_antes": rec.alerta_dias_antes,
        "ultima_vez": rec.ultima_vez,
        "notas": rec.notas,
        "activo": rec.activo,
        **calc_estado_recurrente(rec),
    }


@router.get("", response_model=list[RecurrenteOut])
def listar_recurrentes(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    recs = (
        db.query(Recurrente)
        .filter(Recurrente.usuario_id == usuario.id, Recurrente.activo.is_(True))
        .all()
    )
    serializados = [_serializar(r) for r in recs]
    return sorted(serializados, key=lambda r: r["dia_del_mes"])


@router.post("", response_model=RecurrenteOut)
def crear_recurrente(
    data: RecurrenteCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    rec = Recurrente(usuario_id=usuario.id, **data.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _serializar(rec)


@router.get("/sugerencias", response_model=list[RecurrenteSugerido])
def sugerir_recurrentes(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Analiza el historial de movimientos y sugiere posibles suscripciones/pagos
    fijos que aún no están registrados como recurrentes. No los crea, solo sugiere."""
    movimientos = (
        db.query(Movimiento)
        .filter(Movimiento.usuario_id == usuario.id)
        .order_by(Movimiento.fecha.asc())
        .all()
    )
    # El pago de la tarjeta no es una suscripción: se sugiere con el tipo efectivo.
    te = tipos_efectivos(movimientos, tipos_cuenta_de(db, cuentas_ids_accesibles(db, usuario.id)))
    data = [
        {
            "id": m.id,
            "descripcion": m.descripcion,
            "categoria": m.categoria,
            "tipo": te.get(m.id, m.tipo),
            "monto": m.monto,
            "fecha": m.fecha,
            "cuenta_id": m.cuenta_id,
        }
        for m in movimientos
    ]
    sugerencias = detectar_recurrentes(data)

    existentes = {
        normalize_texto(r.nombre)
        for r in db.query(Recurrente).filter(Recurrente.usuario_id == usuario.id).all()
    }
    return [s for s in sugerencias if normalize_texto(s["descripcion"]) not in existentes]


@router.post("/{rec_id}/marcar_pagado", response_model=RecurrenteOut)
def marcar_pagado(
    rec_id: str,
    data: MarcarPagadoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    rec = (
        db.query(Recurrente)
        .filter(Recurrente.id == rec_id, Recurrente.usuario_id == usuario.id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Recurrente no encontrado")

    rec.ultima_vez = ahora_co()

    if data.crear_movimiento and rec.cuenta_id:
        cuenta = (
            db.query(Cuenta)
            .filter(Cuenta.id == rec.cuenta_id, Cuenta.usuario_id == usuario.id)
            .first()
        )
        if cuenta:
            movimiento = Movimiento(
                usuario_id=usuario.id,
                cuenta_id=cuenta.id,
                descripcion=f"{rec.nombre} (recurrente)",
                categoria=rec.categoria,
                tipo=rec.tipo,
                monto=rec.monto,
                fuente="recurrente",
                notas="Registrado automáticamente",
            )
            db.add(movimiento)
            if rec.tipo == "income":
                cuenta.saldo += rec.monto
            elif rec.tipo == "expense":
                cuenta.saldo -= rec.monto

    db.commit()
    db.refresh(rec)
    return _serializar(rec)


@router.delete("/{rec_id}")
def eliminar_recurrente(
    rec_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    rec = (
        db.query(Recurrente)
        .filter(Recurrente.id == rec_id, Recurrente.usuario_id == usuario.id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Recurrente no encontrado")
    rec.activo = False
    db.commit()
    return {"ok": True}
