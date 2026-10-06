import calendar

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import presupuesto_servicio as srv
from app.utiles import ahora_co
from app.auth import UsuarioActual, get_current_user
from app.compartidos import cuentas_ids_accesibles
from app.cuotas_servicio import comprometido_cuotas
from app.database import get_db
from app.fx import convertir_a_cop
from app.models import Cuenta, Meta, Presupuesto, Recurrente
from app.schemas import (
    DisponibleCategoria,
    DisponibleHoy,
    EnMiBolsillo,
    MoverSobreRequest,
    PresupuestoCreate,
    PresupuestoOut,
)

router = APIRouter(prefix="/presupuestos", tags=["presupuestos"])


@router.get("", response_model=list[PresupuestoOut])
def listar_presupuestos(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    return db.query(Presupuesto).filter(Presupuesto.usuario_id == usuario.id).all()


@router.post("", response_model=PresupuestoOut)
def crear_presupuesto(
    data: PresupuestoCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    presupuesto = Presupuesto(usuario_id=usuario.id, **data.model_dump())
    db.add(presupuesto)
    db.commit()
    db.refresh(presupuesto)
    return presupuesto


@router.get("/disponible-hoy", response_model=DisponibleHoy)
def disponible_hoy(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Cuánto queda disponible por gastar hoy y en lo que resta del periodo,
    por categoría con presupuesto activo y en total. Cada presupuesto se mide en
    SU periodo (mensual, quincenal o semanal); los antiguos son mensuales."""
    ahora = ahora_co()
    cfg = srv.obtener_config(db, usuario.id)
    gastos = srv.GastosPorRango(db, usuario.id)
    presupuestos = (
        db.query(Presupuesto)
        .filter(Presupuesto.usuario_id == usuario.id, Presupuesto.activo == True)  # noqa: E712
        .all()
    )

    categorias: list[DisponibleCategoria] = []
    disponible_total = 0.0
    disponible_hoy_total = 0.0

    for p in presupuestos:
        proy = srv.proyectar_presupuesto(p, cfg, gastos, ahora, n_historico=1)
        dias_restantes = proy["dias_restantes"] + 1  # hoy todavía se puede gastar
        limite_efectivo = proy["limite"]
        total_gastado = proy["gastado"]
        disponible = limite_efectivo - total_gastado
        disponible_total += disponible
        disponible_hoy_total += disponible / dias_restantes

        categorias.append(
            DisponibleCategoria(
                categoria=p.categoria,
                limite=limite_efectivo,
                gastado=total_gastado,
                disponible=disponible,
                disponible_por_dia=disponible / dias_restantes,
                pct_usado=round((total_gastado / limite_efectivo) * 100, 1) if limite_efectivo else 0,
                dias_restantes_mes=dias_restantes,
            )
        )

    ultimo_dia_mes = calendar.monthrange(ahora.year, ahora.month)[1]
    return DisponibleHoy(
        disponible_total_hoy=disponible_hoy_total,
        disponible_total_mes=disponible_total,
        dias_restantes_mes=max(ultimo_dia_mes - ahora.day + 1, 1),
        categorias=categorias,
    )


@router.get("/en-mi-bolsillo", response_model=EnMiBolsillo)
def en_mi_bolsillo(
    incluir_cuotas: bool = False,
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Estilo PocketGuard 'In My Pocket': el saldo de tus cuentas menos lo que
    ya sabes que se va a ir este mes (recurrentes de gasto pendientes) y lo
    que te comprometiste a aportar a tus metas — lo que queda es de verdad tuyo."""
    ahora = ahora_co()
    ultimo_dia_mes = calendar.monthrange(ahora.year, ahora.month)[1]
    dias_restantes = max(ultimo_dia_mes - ahora.day + 1, 1)

    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    cuentas = db.query(Cuenta).filter(Cuenta.id.in_(ids_accesibles)).all()
    saldo_total = sum(convertir_a_cop(c.saldo, c.moneda) for c in cuentas)

    recurrentes = (
        db.query(Recurrente)
        .filter(Recurrente.usuario_id == usuario.id, Recurrente.activo == True, Recurrente.tipo == "expense")  # noqa: E712
        .all()
    )
    recurrentes_pendientes = sum(
        r.monto
        for r in recurrentes
        if not (r.ultima_vez and r.ultima_vez.year == ahora.year and r.ultima_vez.month == ahora.month)
    )

    metas = db.query(Meta).filter(Meta.usuario_id == usuario.id, Meta.activa == True).all()  # noqa: E712
    aportes_comprometidos = 0.0
    for m in metas:
        if not m.fecha_objetivo:
            continue
        dias_para_meta = (m.fecha_objetivo - ahora).days
        if dias_para_meta <= 0:
            continue
        faltante = max(0, m.monto_objetivo - m.monto_actual)
        meses_para_meta = max(dias_para_meta / 30, 1 / 30)  # nunca diluir a menos de "1 día de plazo"
        aportes_comprometidos += faltante / meses_para_meta

    # Cuotas de compras diferidas con tarjeta que vencen este mes. El saldo de la tarjeta
    # ya refleja la deuda completa, así que por defecto solo se informan; con
    # ?incluir_cuotas=true también se restan del disponible (para quien prefiere verlo así).
    cuotas_tarjeta = comprometido_cuotas(db, usuario.id, ahora.year, ahora.month, ahora.date())
    disponible_real = saldo_total - recurrentes_pendientes - aportes_comprometidos
    if incluir_cuotas:
        disponible_real -= cuotas_tarjeta

    return EnMiBolsillo(
        saldo_total=saldo_total,
        recurrentes_pendientes_mes=recurrentes_pendientes,
        aportes_comprometidos_mes=round(aportes_comprometidos),
        cuotas_tarjeta_mes=cuotas_tarjeta,
        disponible_real=round(disponible_real),
        disponible_real_por_dia=round(disponible_real / dias_restantes),
        dias_restantes_mes=dias_restantes,
    )


@router.post("/mover-sobre")
def mover_sobre(
    data: MoverSobreRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Envelope budgeting: mueve plata del sobre (presupuesto) de una
    categoría al de otra — lo que sobró en Comida se puede pasar a
    Transporte, en vez de que el sobrante simplemente se pierda cada mes."""
    if data.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")

    origen = (
        db.query(Presupuesto)
        .filter(Presupuesto.id == data.presupuesto_origen_id, Presupuesto.usuario_id == usuario.id)
        .first()
    )
    destino = (
        db.query(Presupuesto)
        .filter(Presupuesto.id == data.presupuesto_destino_id, Presupuesto.usuario_id == usuario.id)
        .first()
    )
    if not origen or not destino:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    if origen.id == destino.id:
        raise HTTPException(status_code=400, detail="Elige dos categorías distintas")

    proy = srv.proyectar_presupuesto(
        origen, srv.obtener_config(db, usuario.id), srv.GastosPorRango(db, usuario.id), ahora_co(), n_historico=1
    )
    disponible_origen = proy["limite"] - proy["gastado"]
    if data.monto > disponible_origen:
        raise HTTPException(
            status_code=400,
            detail=f"Solo tienes {round(disponible_origen):,} COP disponibles en {origen.categoria} para mover".replace(",", "."),
        )

    origen.sobre_ajuste = (origen.sobre_ajuste or 0) - data.monto
    destino.sobre_ajuste = (destino.sobre_ajuste or 0) + data.monto
    db.commit()
    return {"ok": True}


@router.delete("/{presupuesto_id}")
def eliminar_presupuesto(
    presupuesto_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    p = (
        db.query(Presupuesto)
        .filter(Presupuesto.id == presupuesto_id, Presupuesto.usuario_id == usuario.id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    db.delete(p)
    db.commit()
    return {"ok": True}
