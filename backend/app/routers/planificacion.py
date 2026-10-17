"""Planificación: proyección de presupuestos, periodos, reparto de ingresos,
metas inteligentes y descomposición del patrimonio. Toda la matemática vive en
app/planificacion.py (pura); aquí solo se leen datos y se expone la API.
Nada de esto mueve plata: son sugerencias que el usuario confirma."""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import planificacion as plan
from app import presupuesto_servicio as srv
from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.contabilidad import ConvertidorBase
from app.models import Meta, Presupuesto, Recurrente
from app.models_patrimonio import ActivoPatrimonio, FlujoActivo, SnapshotPatrimonio
from app.utiles import ahora_co

router = APIRouter(prefix="/planificacion", tags=["planificacion"])


class ConfigIn(BaseModel):
    dia_pago: Optional[int] = Field(default=None, ge=1, le=31)
    periodo_defecto: Optional[str] = None
    regla_necesidades: Optional[float] = Field(default=None, ge=0, le=100)
    regla_deseos: Optional[float] = Field(default=None, ge=0, le=100)
    regla_ahorro: Optional[float] = Field(default=None, ge=0, le=100)
    arrastre_ids: Optional[list[str]] = None
    sin_dia_pago: bool = False  # true => borrar el día de pago


class DistribuirIn(BaseModel):
    monto: float = Field(gt=0)


class PlanMetaIn(BaseModel):
    objetivo: float = Field(gt=0)
    fecha_objetivo: Optional[datetime] = None
    saldo_actual: float = Field(default=0, ge=0)
    tasa_ea: float = Field(default=0, ge=0, le=100)


def _config_out(cfg) -> dict:
    return {
        "dia_pago": cfg.dia_pago,
        "periodo_defecto": plan.normalizar_periodo(cfg.periodo_defecto),
        "regla": {"necesidades": cfg.regla_necesidades, "deseos": cfg.regla_deseos, "ahorro": cfg.regla_ahorro},
        "arrastre_ids": srv.json_lista(cfg.arrastre_ids),
    }


@router.get("/config")
def leer_config(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    return _config_out(srv.obtener_config(db, usuario.id))


@router.put("/config")
def guardar_config(data: ConfigIn, db: Session = Depends(get_db),
                   usuario: UsuarioActual = Depends(get_current_user)):
    actual = srv.obtener_config(db, usuario.id)
    campos = {}
    if data.sin_dia_pago:
        campos["dia_pago"] = None
    elif data.dia_pago is not None:
        campos["dia_pago"] = data.dia_pago
    if data.periodo_defecto is not None:
        campos["periodo_defecto"] = plan.normalizar_periodo(data.periodo_defecto)
    if data.arrastre_ids is not None:
        campos["arrastre_ids"] = json.dumps(data.arrastre_ids)
    partes = (data.regla_necesidades, data.regla_deseos, data.regla_ahorro)
    if any(p is not None for p in partes):
        n = data.regla_necesidades if data.regla_necesidades is not None else actual.regla_necesidades
        d = data.regla_deseos if data.regla_deseos is not None else actual.regla_deseos
        a = data.regla_ahorro if data.regla_ahorro is not None else actual.regla_ahorro
        if abs(n + d + a - 100) > 0.01:
            raise HTTPException(status_code=422, detail="La regla debe sumar 100%")
        campos.update(regla_necesidades=n, regla_deseos=d, regla_ahorro=a)
    return _config_out(srv.guardar_config(db, usuario.id, **campos))


def proyecciones_de_usuario(db: Session, uid: str, hoy=None) -> list:
    hoy = hoy or ahora_co()
    cfg = srv.obtener_config(db, uid)
    gastos = srv.GastosPorRango(db, uid)
    presupuestos = (
        db.query(Presupuesto)
        .filter(Presupuesto.usuario_id == uid, Presupuesto.activo == True)  # noqa: E712
        .all()
    )
    return [srv.proyectar_presupuesto(p, cfg, gastos, hoy) for p in presupuestos]


@router.get("/proyeccion")
def proyeccion(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    items = proyecciones_de_usuario(db, usuario.id)
    cfg = srv.obtener_config(db, usuario.id)
    # El total solo suma presupuestos del mismo periodo (mezclar semana y mes no tiene sentido).
    por_periodo = {}
    for i in items:
        por_periodo.setdefault(i["periodo"], []).append(i)
    totales = {per: plan.proyectar_total(lst) for per, lst in por_periodo.items()}
    return {"items": items, "totales": totales, "config": _config_out(cfg)}


def _promedios_historicos(db: Session, uid: str, hoy, meses: int = 3) -> dict:
    """Ingreso y gasto promedio mensual de los últimos `meses` meses COMPLETOS."""
    from app.informe_datos import cargar_movs_efectivos

    fin = datetime(hoy.year, hoy.month, 1)
    ini_y, ini_m = hoy.year, hoy.month
    for _ in range(meses):
        ini_y, ini_m = plan._mes_anterior(ini_y, ini_m)
    inicio = datetime(ini_y, ini_m, 1)
    # Regla contable central: pagos de tarjeta, traslados propios y ajustes de saldo no cuentan.
    filas = [m for m in cargar_movs_efectivos(db, uid, inicio, fin)
             if inicio <= m["fecha"] < fin and m["tipo"] in ("income", "expense")]
    ingresos = gastos = 0.0
    meses_con_datos = set()
    for m in filas:
        meses_con_datos.add(m["fecha"].strftime("%Y-%m"))
        if m["tipo"] == "income":
            ingresos += m["monto"]
        else:
            gastos += m["monto"]
    n = max(1, len(meses_con_datos))
    return {"ingreso": ingresos / n, "gasto": gastos / n, "ahorro": (ingresos - gastos) / n,
            "meses_con_datos": len(meses_con_datos)}


def _necesidad_meta(m: Meta, hoy) -> float:
    """Aporte mensual que pide una meta: el automático si lo tiene; si no, lo que falta / meses."""
    if m.aporte_automatico:
        return float(m.aporte_automatico)
    faltante = max(0.0, (m.monto_objetivo or 0) - (m.monto_actual or 0))
    if m.fecha_objetivo and faltante > 0:
        meses = plan.meses_hasta(hoy, m.fecha_objetivo)
        if meses:
            return faltante / meses
    return 0.0


@router.post("/distribuir-ingreso")
def distribuir_ingreso(data: DistribuirIn, db: Session = Depends(get_db),
                       usuario: UsuarioActual = Depends(get_current_user)):
    """SUGERENCIA de reparto de un ingreso. No registra ni mueve nada."""
    hoy = ahora_co()
    cfg = srv.obtener_config(db, usuario.id)
    fijos = sum(
        r.monto for r in db.query(Recurrente).filter(
            Recurrente.usuario_id == usuario.id, Recurrente.activo == True, Recurrente.tipo == "expense")  # noqa: E712
    )
    metas = [
        {"id": m.id, "nombre": m.nombre, "aporte_mensual": _necesidad_meta(m, hoy)}
        for m in db.query(Meta).filter(Meta.usuario_id == usuario.id, Meta.activa.is_(True)).all()
        if (m.monto_actual or 0) < (m.monto_objetivo or 0)
    ]
    sobres = [
        {"categoria": p.categoria, "limite": p.limite}
        for p in db.query(Presupuesto).filter(Presupuesto.usuario_id == usuario.id, Presupuesto.activo == True).all()  # noqa: E712
    ]
    regla = {"necesidades": cfg.regla_necesidades, "deseos": cfg.regla_deseos, "ahorro": cfg.regla_ahorro}
    return plan.sugerir_distribucion(data.monto, regla, fijos or None, metas, sobres)


@router.post("/plan-meta")
def plan_de_meta(data: PlanMetaIn, db: Session = Depends(get_db),
                 usuario: UsuarioActual = Depends(get_current_user)):
    hoy = ahora_co()
    h = _promedios_historicos(db, usuario.id, hoy)
    res = plan.plan_meta(
        data.objetivo, data.saldo_actual, data.fecha_objetivo, hoy,
        ahorro_real_mensual=h["ahorro"], ingreso_mensual=h["ingreso"],
        gasto_mensual=h["gasto"], tasa_ea=data.tasa_ea,
    )
    res["historico"] = h
    return res


@router.get("/patrimonio-descomposicion")
def patrimonio_descomposicion(db: Session = Depends(get_db),
                              usuario: UsuarioActual = Depends(get_current_user)):
    """De dónde viene el crecimiento mensual del patrimonio: ahorro, valorización
    y reducción de deuda. Usa los snapshots y los flujos de activos existentes."""
    snaps = (db.query(SnapshotPatrimonio).filter(SnapshotPatrimonio.usuario_id == usuario.id)
             .order_by(SnapshotPatrimonio.mes).all())
    snaps_d = [
        {"mes": s.mes, "total_activos": s.total_activos or 0, "total_cuentas": s.total_cuentas or 0,
         "total_deudas": s.total_deudas or 0, "patrimonio_neto": s.patrimonio_neto or 0}
        for s in snaps
    ]
    monedas = {a.id: a.moneda or "COP" for a in
               db.query(ActivoPatrimonio).filter(ActivoPatrimonio.usuario_id == usuario.id).all()}
    conv = ConvertidorBase.de_usuario(db, usuario.id)
    aportes: dict = {}
    for f in db.query(FlujoActivo).filter(FlujoActivo.usuario_id == usuario.id).all():
        mes = f.fecha.strftime("%Y-%m")
        # flujo negativo = aporte (sale de tu bolsillo); positivo = retiro/dividendo.
        aportes[mes] = aportes.get(mes, 0.0) - conv.contar(f.monto, monedas.get(f.activo_id, "COP"))
    return {"meses": plan.serie_descomposicion(snaps_d, aportes)}
