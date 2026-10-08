"""«Buscar duplicados»: sugiere (nunca borra solo) los movimientos que parecen el mismo gasto
llegado por canales distintos, y deja unirlos conservando el que la persona elija.

La regla que decide qué es «el mismo gasto» vive en app/duplicados.py (la usan todos los canales)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import duplicados as dup
from app.auth import UsuarioActual, get_current_user
from app.compartidos import cuentas_ids_accesibles
from app.database import get_db
from app.models import Movimiento
from app.routers.movimientos import _borrar_normal

router = APIRouter(prefix="/duplicados", tags=["duplicados"])


class UnirRequest(BaseModel):
    conservar_id: str
    unir_ids: list[str] = Field(min_length=1, max_length=20)


class NoDuplicadoRequest(BaseModel):
    movimiento_ids: list[str] = Field(min_length=2, max_length=20)


@router.get("/buscar")
def buscar_duplicados(
    dias: int = 120,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Grupos de posibles duplicados de los últimos `dias` días. Solo sugiere: cada grupo trae el
    movimiento que conviene conservar (`sugerido_conservar`), pero la persona elige."""
    dias = max(7, min(dias, 365))
    grupos = dup.grupos_posibles_duplicados(db, usuario.id, dias=dias)
    return {"grupos": grupos, "total": len(grupos)}


@router.post("/unir")
def unir_duplicados(
    data: UnirRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Une los movimientos de `unir_ids` en `conservar_id`: el que se conserva recibe los canales
    (atajo, correo, extracto...) de los demás y los demás se eliminan devolviendo su saldo. No se
    borra nada que no se haya pedido; los traslados, aportes a metas y ajustes no se pueden unir."""
    ids = [data.conservar_id, *data.unir_ids]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail="Elige movimientos distintos")
    accesibles = cuentas_ids_accesibles(db, usuario.id)
    movs = {m.id: m for m in db.query(Movimiento).filter(Movimiento.id.in_(ids), Movimiento.cuenta_id.in_(accesibles)).all()}
    if len(movs) != len(ids):
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if not all(dup.es_emparejable(m) for m in movs.values()):
        raise HTTPException(status_code=400, detail="Los traslados, aportes a metas y ajustes de saldo no se pueden unir")
    if len({m.tipo for m in movs.values()}) != 1:
        raise HTTPException(status_code=400, detail="Solo se pueden unir gastos con gastos o ingresos con ingresos")
    guardado = movs[data.conservar_id]
    for otro_id in data.unir_ids:
        otro = movs[otro_id]
        dup.reasignar_canales(db, otro, guardado)
        dup.enriquecer(guardado, descripcion=otro.descripcion)
        if (guardado.categoria or "Otros") == "Otros" and (otro.categoria or "Otros") != "Otros":
            guardado.categoria, guardado.cat_confirmada = otro.categoria, otro.cat_confirmada
        db.flush()
        _borrar_normal(db, usuario, otro)
    db.commit()
    db.refresh(guardado)
    dup.anotar_canales(db, [guardado])
    return {"ok": True, "unidos": len(data.unir_ids), "conservado": {
        "id": guardado.id, "descripcion": guardado.descripcion, "monto": guardado.monto, "canales": guardado.canales}}


@router.post("/no-es-duplicado")
def no_es_duplicado(
    data: NoDuplicadoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«No es duplicado»: ese grupo (eran compras iguales de verdad) no se vuelve a sugerir."""
    accesibles = cuentas_ids_accesibles(db, usuario.id)
    n = db.query(Movimiento).filter(Movimiento.id.in_(data.movimiento_ids), Movimiento.cuenta_id.in_(accesibles)).count()
    if n != len(set(data.movimiento_ids)):
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    marcados = dup.marcar_no_duplicados(db, usuario.id, data.movimiento_ids)
    db.commit()
    return {"ok": True, "marcados": marcados}
