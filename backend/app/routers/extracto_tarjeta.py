"""Aplicar a una tarjeta lo que dice su extracto real. SOLO se llama cuando el cliente
pulsa 'Aplicar' en la propuesta ('Tu extracto dice...'): nada se actualiza solo."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.compartidos import bloquear_cuenta, cuenta_accesible, puede_editar_cuenta
from app.database import get_db
from app.models_cuotas import ExtractoTarjeta

router = APIRouter(prefix="/tarjetas", tags=["tarjetas"])

_FECHA = r"^\d{4}-\d{2}-\d{2}$"


class AplicarExtractoRequest(BaseModel):
    # Datos de la cuenta que la propuesta puede cambiar
    cupo_total: Optional[float] = Field(default=None, gt=0, le=1e12)
    dia_corte: Optional[int] = Field(default=None, ge=1, le=31)
    dia_pago: Optional[int] = Field(default=None, ge=1, le=31)
    tasa_ea: Optional[float] = Field(default=None, gt=0, le=100)
    # Lo que dice el extracto (se guarda para el pago mínimo y el total a pagar reales)
    cupo_disponible: Optional[float] = Field(default=None, ge=0, le=1e12)
    pago_total: Optional[float] = Field(default=None, ge=0, le=1e12)
    pago_minimo: Optional[float] = Field(default=None, ge=0, le=1e12)
    fecha_limite_pago: Optional[str] = Field(default=None, pattern=_FECHA)
    fecha_corte: Optional[str] = Field(default=None, pattern=_FECHA)


@router.post("/{cuenta_id}/aplicar-extracto")
def aplicar_extracto(
    cuenta_id: str,
    data: AplicarExtractoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = cuenta_accesible(db, usuario.id, cuenta_id)
    if not cuenta or not puede_editar_cuenta(db, usuario.id, cuenta) or cuenta.tipo != "credito":
        raise HTTPException(status_code=404, detail="Tarjeta de crédito no encontrada")
    cuenta = bloquear_cuenta(db, cuenta_id)

    cambiadas = []
    for campo in ("cupo_total", "dia_corte", "dia_pago", "tasa_ea"):
        valor = getattr(data, campo)
        if valor is not None and valor != getattr(cuenta, campo):
            setattr(cuenta, campo, valor)
            cambiadas.append(campo)

    extracto_dado = any(
        getattr(data, c) is not None
        for c in ("pago_total", "pago_minimo", "fecha_limite_pago", "fecha_corte", "cupo_disponible")
    )
    if extracto_dado:
        fila = db.query(ExtractoTarjeta).filter(ExtractoTarjeta.cuenta_id == cuenta.id).first()
        if not fila:
            fila = ExtractoTarjeta(usuario_id=cuenta.usuario_id, cuenta_id=cuenta.id)
            db.add(fila)
        for campo in ("cupo_disponible", "pago_total", "pago_minimo", "fecha_limite_pago", "fecha_corte"):
            setattr(fila, campo, getattr(data, campo))
        fila.actualizado_en = datetime.utcnow()
    db.commit()
    return {"ok": True, "cambiadas": cambiadas, "extracto_guardado": extracto_dado}
