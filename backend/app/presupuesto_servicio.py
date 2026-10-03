"""Capa con base de datos de la proyección de presupuestos: arma los datos y
delega TODO el cálculo en las funciones puras de planificacion.py."""
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app import planificacion as plan
from app.compartidos import cuentas_ids_accesibles
from app.fx import convertir_a_cop
from app.models import Cuenta, Movimiento, Presupuesto
from app.models_planificacion import ConfigPlanificacion


def obtener_config(db: Session, uid: str) -> ConfigPlanificacion:
    """Config del usuario; si no existe devuelve una SIN guardar con los valores por defecto."""
    cfg = db.query(ConfigPlanificacion).filter(ConfigPlanificacion.usuario_id == uid).first()
    if cfg is None:
        cfg = ConfigPlanificacion(
            usuario_id=uid, dia_pago=None, periodo_defecto="monthly",
            regla_necesidades=50, regla_deseos=30, regla_ahorro=20,
            arrastre_ids="[]", alertas_proyeccion="{}",
        )
    return cfg


def guardar_config(db: Session, uid: str, **campos) -> ConfigPlanificacion:
    cfg = db.query(ConfigPlanificacion).filter(ConfigPlanificacion.usuario_id == uid).first()
    if cfg is None:
        cfg = obtener_config(db, uid)
        db.add(cfg)
    for k, v in campos.items():
        setattr(cfg, k, v)
    db.commit()
    db.refresh(cfg)
    return cfg


def json_lista(texto) -> list:
    try:
        v = json.loads(texto or "[]")
        return v if isinstance(v, list) else []
    except ValueError:
        return []


def json_dict(texto) -> dict:
    try:
        v = json.loads(texto or "{}")
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def _dt(d) -> datetime:
    return datetime(d.year, d.month, d.day)


class GastosPorRango:
    """Suma gastos por categoría y rango de fechas, convirtiendo a COP."""

    def __init__(self, db: Session, uid: str):
        self.db = db
        self.ids = cuentas_ids_accesibles(db, uid)
        self.monedas = {c.id: c.moneda for c in db.query(Cuenta).filter(Cuenta.id.in_(self.ids)).all()}

    def gastado(self, categoria: str, inicio, fin) -> float:
        filas = (
            self.db.query(Movimiento.monto, Movimiento.cuenta_id)
            .filter(
                Movimiento.cuenta_id.in_(self.ids),
                Movimiento.categoria == categoria,
                Movimiento.tipo == "expense",
                Movimiento.fecha >= _dt(inicio),
                Movimiento.fecha < _dt(fin),
            )
            .all()
        )
        return sum(convertir_a_cop(m, self.monedas.get(c, "COP")) for m, c in filas)


def proyectar_presupuesto(p: Presupuesto, cfg: ConfigPlanificacion, gastos: GastosPorRango,
                          hoy, n_historico: int = 3) -> dict:
    """Proyección de un presupuesto en SU periodo (mensual/quincenal/semanal),
    con límite efectivo = límite + sobre_ajuste + sobrante arrastrado (si lo pidió)."""
    periodo = plan.normalizar_periodo(p.periodo)
    rango = plan.rango_periodo(hoy, periodo, cfg.dia_pago)
    gastado = gastos.gastado(p.categoria, rango["inicio"], rango["fin"])

    historico = []
    ant = rango
    for _ in range(n_historico):
        ant = plan.periodo_anterior(ant["inicio"], periodo, cfg.dia_pago)
        historico.append(gastos.gastado(p.categoria, ant["inicio"], ant["fin"]))

    arrastre = 0.0
    if p.id in json_lista(cfg.arrastre_ids):
        arrastre = plan.sobrante_arrastrable(p.limite, historico[0])

    limite_efectivo = (p.limite or 0) + (p.sobre_ajuste or 0) + arrastre
    res = plan.proyectar_cierre(gastado, limite_efectivo, rango, historico, p.categoria)
    res.update({
        "presupuesto_id": p.id,
        "periodo": periodo,
        "inicio": rango["inicio"].isoformat(),
        "fin": rango["fin"].isoformat(),
        "dias_totales": rango["dias_totales"],
        "dias_transcurridos": rango["dias_transcurridos"],
        "arrastre": arrastre,
        "alerta_pct": p.alerta_pct,
        "clave_periodo": plan.clave_periodo(rango["inicio"], periodo),
    })
    return res
