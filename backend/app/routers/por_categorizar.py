"""«Por categorizar» a elección del usuario.

Nada es obligatorio: la lista de pendientes (definición única en app/pendientes.py) se
puede ignorar. Aquí el usuario ELIGE: pone categoría a lo que seleccione, lo deja como está,
deja de recibir preguntas de un comercio u oculta un comercio de la lista. Todo se puede
deshacer. Las reglas automáticas solo se crean si pide «recordar» de forma explícita.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import pendientes
from app.auth import UsuarioActual, get_current_user
from app.autocat import aplicar_a_anteriores, guardar_regla_aprendida
from app.clave_comercio import clave_comercio
from app.compartidos import cuentas_ids_accesibles, puede_editar_cuenta
from app.database import get_db
from app.models import Categoria, Cuenta, Movimiento, ReglaCategoria
from app.models_pendientes import ComercioSilenciado

router = APIRouter(prefix="/por-categorizar", tags=["por-categorizar"])

MAX_ELEMENTOS = 500


class AccionRequest(BaseModel):
    accion: Literal["categoria", "dejar", "marcar", "no_preguntar", "ocultar"]
    movimiento_ids: list[str] = Field(default_factory=list, max_length=MAX_ELEMENTOS)
    huellas: list[str] = Field(default_factory=list, max_length=MAX_ELEMENTOS)
    categoria: Optional[str] = Field(default=None, max_length=60)
    recordar: bool = False  # crear la regla del comercio (opcional, nunca automático)
    aplicar_anteriores: bool = False
    confirmar_peligrosa: bool = False


class Previo(BaseModel):
    id: str
    categoria: Optional[str] = None
    cat_confirmada: Optional[bool] = True
    cat_origen: Optional[str] = None


class DeshacerRequest(BaseModel):
    previos: list[Previo] = Field(default_factory=list, max_length=MAX_ELEMENTOS * 4)
    huellas: list[str] = Field(default_factory=list, max_length=MAX_ELEMENTOS)
    tipo_silencio: Optional[Literal["no_preguntar", "ocultar"]] = None
    reglas_creadas: list[str] = Field(default_factory=list, max_length=MAX_ELEMENTOS)


class QuitarSilenciosRequest(BaseModel):
    huellas: list[str] = Field(min_length=1, max_length=MAX_ELEMENTOS)


@router.get("")
def resumen(
    limite: int = Query(10, ge=1, le=50),
    todos: bool = False,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Los comercios pendientes, agrupados y ordenados por impacto (lo que más pesa primero).
    Por defecto solo los `limite` primeros; `todos=true` trae todos."""
    ids = cuentas_ids_accesibles(db, usuario.id)
    return pendientes.resumen(db, usuario.id, ids, limite=limite, todos=todos)


@router.get("/silencios")
def listar_silencios(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    filas = (
        db.query(ComercioSilenciado)
        .filter(ComercioSilenciado.usuario_id == usuario.id, ComercioSilenciado.tipo.in_(pendientes.SILENCIOS_QUE_OCULTAN))
        .order_by(ComercioSilenciado.creado_en.desc())
        .all()
    )
    return {"silencios": [{"huella": f.huella, "tipo": f.tipo, "creado_en": f.creado_en.isoformat()} for f in filas]}


@router.post("/silencios/quitar")
def quitar_silencios(
    data: QuitarSilenciosRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Vuelve a preguntar por estos comercios (deshace «no volver a preguntar» y «ocultar»)."""
    n = pendientes.quitar_silencios(db, usuario.id, data.huellas, pendientes.SILENCIOS_QUE_OCULTAN)
    db.commit()
    return {"ok": True, "quitados": n}


def _estado(m: Movimiento) -> dict:
    return {"id": m.id, "categoria": m.categoria, "cat_confirmada": m.cat_confirmada is not False, "cat_origen": m.cat_origen}


@router.post("/accion")
def accion(
    data: AccionRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    ids_cuentas = cuentas_ids_accesibles(db, usuario.id)
    ids_mov = set(data.movimiento_ids)
    huellas = {h for h in data.huellas if h}

    # Silencios: trabajan por comercio. Un movimiento suelto aporta su huella.
    if data.accion in ("no_preguntar", "ocultar"):
        if ids_mov:
            for i, d in db.query(Movimiento.id, Movimiento.descripcion).filter(
                Movimiento.id.in_(ids_mov), Movimiento.cuenta_id.in_(ids_cuentas)
            ).all():
                huellas.add(pendientes.huella_de(d))
        if not huellas:
            raise HTTPException(status_code=400, detail="Elige al menos un comercio")
        nuevas = [h for h in huellas if h not in pendientes.silencios(db, usuario.id, (data.accion,))]
        pendientes.silenciar(db, usuario.id, huellas, data.accion)
        db.commit()
        return {"ok": True, "accion": data.accion, "huellas": sorted(huellas), "huellas_nuevas": sorted(nuevas),
                "movimientos": 0, "previos": []}

    # Acciones sobre movimientos: los sueltos más todos los pendientes de los comercios elegidos.
    if huellas:
        for m, _ in pendientes.pendientes(db, usuario.id, ids_cuentas):
            if pendientes.huella_de(m.descripcion) in huellas:
                ids_mov.add(m.id)
    if not ids_mov:
        raise HTTPException(status_code=400, detail="Elige al menos un movimiento o comercio")
    if len(ids_mov) > MAX_ELEMENTOS * 4:
        raise HTTPException(status_code=400, detail="Elegiste demasiados a la vez: hazlo por partes")

    categoria = (data.categoria or "").strip()
    if data.accion == "categoria":
        if not categoria:
            raise HTTPException(status_code=400, detail="Elige una categoría")
        hay_lista = db.query(Categoria.id).filter(Categoria.usuario_id == usuario.id).first()
        if hay_lista and not db.query(Categoria.id).filter(
            Categoria.usuario_id == usuario.id, Categoria.nombre == categoria
        ).first():
            raise HTTPException(status_code=400, detail="Esa categoría no existe en tu lista")

    movs = db.query(Movimiento).filter(Movimiento.id.in_(ids_mov), Movimiento.cuenta_id.in_(ids_cuentas)).all()
    editables: dict[str, bool] = {}
    for cid in {m.cuenta_id for m in movs}:
        c = db.query(Cuenta).filter(Cuenta.id == cid).first()
        editables[cid] = bool(c and puede_editar_cuenta(db, usuario.id, c))
    movs = [m for m in movs if editables.get(m.cuenta_id)]
    if not movs:
        raise HTTPException(status_code=400, detail="No encontré esos movimientos o no puedes editarlos")

    previos = {m.id: _estado(m) for m in movs}
    for m in movs:
        if data.accion == "categoria":
            m.categoria, m.cat_confirmada, m.cat_origen = categoria, True, None
        elif data.accion == "dejar":
            # Se queda como está: confirmada, y si era «Otros» deja de contar como pendiente.
            m.cat_confirmada = True
            m.cat_origen = pendientes.ORIGEN_DEJADA if (m.categoria or "Otros").strip().lower() in pendientes.CATEGORIAS_SIN_DEFINIR else None
        elif data.accion == "marcar":
            m.cat_origen = pendientes.ORIGEN_MARCADA

    reglas_creadas: list[str] = []
    reglas_omitidas: list[dict] = []
    anteriores = 0
    if data.accion == "categoria" and data.recordar:
        por_huella: dict[str, Movimiento] = {}
        for m in movs:
            por_huella.setdefault(clave_comercio(m.descripcion), m)
        # Foto del estado de los anteriores para poder deshacer también lo que cambie la regla.
        antes = {m.id: _estado(m) for m in db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids_cuentas)).all()}
        for h, ejemplo in por_huella.items():
            if not h:
                continue
            r = guardar_regla_aprendida(db, usuario.id, ejemplo.descripcion, categoria,
                                        confirmar_peligrosa=data.confirmar_peligrosa)
            if not r["guardada"]:
                reglas_omitidas.append({"huella": h, "motivo": r["motivo"]})
                continue
            db.flush()
            if not r["actualizada"]:
                regla = next((x for x in db.query(ReglaCategoria).filter(ReglaCategoria.usuario_id == usuario.id).all()
                              if clave_comercio(x.patron) == r["huella"]), None)
                if regla:
                    reglas_creadas.append(regla.id)
            if data.aplicar_anteriores:
                anteriores += aplicar_a_anteriores(db, usuario.id, r["huella"], categoria, {m.id for m in movs})
        if data.aplicar_anteriores:
            for m in db.query(Movimiento).filter(Movimiento.id.in_(list(antes))).all():
                if m.id not in previos and _estado(m) != antes[m.id]:
                    previos[m.id] = antes[m.id]

    db.commit()
    return {"ok": True, "accion": data.accion, "movimientos": len(movs), "previos": list(previos.values()),
            "reglas_creadas": reglas_creadas, "reglas_omitidas": reglas_omitidas, "anteriores": anteriores}


@router.post("/deshacer")
def deshacer(
    data: DeshacerRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Revierte la última acción: restaura el estado anterior de los movimientos, quita los
    silencios nuevos y borra las reglas que esa acción creó (las que ya existían no se tocan)."""
    ids_cuentas = cuentas_ids_accesibles(db, usuario.id)
    por_id = {p.id: p for p in data.previos}
    restaurados = 0
    if por_id:
        for m in db.query(Movimiento).filter(Movimiento.id.in_(list(por_id)), Movimiento.cuenta_id.in_(ids_cuentas)).all():
            p = por_id[m.id]
            m.categoria = p.categoria or m.categoria
            m.cat_confirmada = p.cat_confirmada is not False
            m.cat_origen = p.cat_origen
            restaurados += 1
    quitados = 0
    if data.huellas:
        tipos = (data.tipo_silencio,) if data.tipo_silencio else pendientes.SILENCIOS_QUE_OCULTAN
        quitados = pendientes.quitar_silencios(db, usuario.id, data.huellas, tipos)
    borradas = 0
    if data.reglas_creadas:
        borradas = (
            db.query(ReglaCategoria)
            .filter(ReglaCategoria.usuario_id == usuario.id, ReglaCategoria.id.in_(data.reglas_creadas))
            .delete(synchronize_session=False)
        )
    db.commit()
    return {"ok": True, "restaurados": restaurados, "silencios_quitados": quitados, "reglas_borradas": borradas}
