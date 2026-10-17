"""
Traslados entre cuentas propias: revisión y decisión de la persona.

La detección automática vive en app/contabilidad.py (`clasificar`). Aquí la persona:
  - ve sugerencias («Revisar posibles traslados»): pares sin pista y «posibles» sin la otra pata;
  - decide «Es un traslado entre mis cuentas» / «No es un traslado» (una o varias a la vez);
  - con `recordar`, deja una regla por huella que vale para movimientos futuros parecidos.
La decisión se guarda en `notas` del movimiento (marca) y, si se pide, en `reglas_traslado`;
`clasificar` la respeta en TODOS los cálculos (informes, presupuesto, cierre, correos...).
Solo se pueden decidir movimientos PROPIOS (de cuentas de la persona).
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.compartidos import cuentas_ids_accesibles
from app.contabilidad import (
    huella_traslado,
    notas_con_decision,
    sugerir_traslados,
    tipos_cuenta_de,
    _sin_acentos,
)
from app import punto_partida
from app.database import get_db
from app.contabilidad import ConvertidorBase
from app.models import Cuenta, Movimiento
from app.models_pendientes import ReglaTraslado
from app.utiles import ahora_co

router = APIRouter(prefix="/traslados", tags=["traslados"])

DIAS_REVISION = 180
MAX_SUGERENCIAS = 100
MAX_IDS = 200


def _resumen(m: Movimiento, cuentas: dict[str, Cuenta], conv: ConvertidorBase) -> dict:
    c = cuentas.get(m.cuenta_id)
    return {
        "id": m.id, "fecha": m.fecha.isoformat() if m.fecha else None, "descripcion": m.descripcion or "",
        "monto": round(conv.contar(m.monto, c.moneda if c else "COP")), "tipo": m.tipo,
        "cuenta_id": m.cuenta_id, "cuenta": c.nombre if c else "",
    }


@router.get("/sugerencias")
def sugerencias(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Pares que parecen un traslado entre tus cuentas y movimientos a los que les falta la otra pata."""
    ids = list(cuentas_ids_accesibles(db, usuario.id))
    if not ids:
        return {"sugerencias": [], "total": 0}
    desde = ahora_co() - timedelta(days=DIAS_REVISION)
    inicio_pp = punto_partida.fecha_inicio(db, usuario.id)
    if inicio_pp and desde < inicio_pp:
        desde = inicio_pp
    movs = db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids), Movimiento.fecha >= desde).all()
    cuentas = {c.id: c for c in db.query(Cuenta).filter(Cuenta.id.in_(ids)).all()}
    tc = tipos_cuenta_de(db, ids, [usuario.nombre] if usuario.nombre else None)
    por_id = {m.id: m for m in movs}
    # Solo movimientos propios: la decisión se guarda en la fila y en reglas de quien decide.
    propios = {m.id for m in movs if m.usuario_id == usuario.id}
    conv = ConvertidorBase.de_usuario(db, usuario.id)
    items = []
    for s in sugerir_traslados(movs, tc):
        if not all(i in propios for i in s["ids"]):
            continue
        filas = [_resumen(por_id[i], cuentas, conv) for i in s["ids"]]
        items.append({"tipo": s["tipo"], "ids": s["ids"], "diferencia": s["diferencia"], "movimientos": filas,
                      "fecha": max(f["fecha"] or "" for f in filas)})
    items.sort(key=lambda x: x["fecha"], reverse=True)
    return {"sugerencias": items[:MAX_SUGERENCIAS], "total": len(items)}


class DecisionTraslado(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=MAX_IDS)
    decision: str  # traslado | real
    recordar: bool = False


@router.post("/decidir")
def decidir(data: DecisionTraslado, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """«Es un traslado entre mis cuentas» (traslado) o «No es un traslado» (real) para uno o varios
    movimientos propios. Con `recordar`, también para los que se parezcan en el futuro."""
    if data.decision not in ("traslado", "real"):
        raise HTTPException(status_code=422, detail="La decisión debe ser 'traslado' o 'real'")
    movs = db.query(Movimiento).filter(Movimiento.id.in_(data.ids), Movimiento.usuario_id == usuario.id).all()
    if len(movs) != len(set(data.ids)):
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    reglas = 0
    for m in movs:
        m.notas = notas_con_decision(m.notas, data.decision)
        if data.decision == "real" and _sin_acentos(m.categoria or "").strip().lower() == "transferencia":
            m.categoria = "Otros"  # la categoría neutra heredada ya no aplica a un movimiento real
        if data.recordar:
            h = huella_traslado(m.descripcion)
            if not h:
                continue
            r = db.query(ReglaTraslado).filter(ReglaTraslado.usuario_id == usuario.id, ReglaTraslado.huella == h).first()
            if r:
                r.decision = data.decision
            else:
                db.add(ReglaTraslado(usuario_id=usuario.id, huella=h, decision=data.decision))
            reglas += 1
    db.commit()
    return {"ok": True, "aplicados": len(movs), "reglas_guardadas": reglas}


@router.get("/reglas")
def listar_reglas(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Lo que la persona pidió recordar (para poder deshacerlo)."""
    filas = db.query(ReglaTraslado).filter(ReglaTraslado.usuario_id == usuario.id).order_by(ReglaTraslado.creado_en.desc()).all()
    return [{"id": r.id, "huella": r.huella, "decision": r.decision} for r in filas]


@router.delete("/reglas/{regla_id}")
def borrar_regla(regla_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    r = db.query(ReglaTraslado).filter(ReglaTraslado.id == regla_id, ReglaTraslado.usuario_id == usuario.id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    db.delete(r)
    db.commit()
    return {"ok": True}
