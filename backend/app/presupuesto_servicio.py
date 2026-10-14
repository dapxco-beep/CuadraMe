"""Capa con base de datos de la proyección de presupuestos: arma los datos y
delega TODO el cálculo en las funciones puras de planificacion.py."""
import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import planificacion as plan
from app.compartidos import cuentas_ids_accesibles
from app.contabilidad import tipos_de_cuentas, tipos_efectivos
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

    # Ventana que se trae de la base de una sola vez. Cada presupuesto pide su periodo
    # actual y 1-3 anteriores; antes eso eran 2 consultas por cada pedido (5 presupuestos =
    # 20+ consultas, 80 con 20 presupuestos). Ahora: una consulta de movimientos para toda
    # la ventana y se filtra en memoria. Cubre hasta ~4 meses atrás y 1 mes adelante.
    ATRAS_DIAS = 130
    ADELANTE_DIAS = 35

    def __init__(self, db: Session, uid: str):
        self.db = db
        self.ids = cuentas_ids_accesibles(db, uid)
        self._tipos = None
        self.monedas = {}
        if self.ids:
            cuentas = db.query(Cuenta).filter(Cuenta.id.in_(self.ids)).all()
            self.monedas = {c.id: c.moneda for c in cuentas}
            # Mismo contenido que tipos_cuenta_de(), sin repetir la consulta de cuentas.
            self._tipos = tipos_de_cuentas(cuentas, db)
        self._ventana = None  # (desde, hasta, [movimientos])
        self._por_rango = {}  # (desde, hasta) -> {categoría: gasto}

    def _movimientos(self, desde: datetime, hasta: datetime) -> list:
        """Movimientos con fecha en [desde, hasta), tomados de la ventana en memoria
        (que se amplía si el pedido cae fuera de ella)."""
        v = self._ventana
        if v is None or desde < v[0] or hasta > v[1]:
            ini = desde - timedelta(days=self.ATRAS_DIAS)
            fin = hasta + timedelta(days=self.ADELANTE_DIAS)
            if v is not None:
                ini, fin = min(ini, v[0]), max(fin, v[1])
            movs = (
                self.db.query(Movimiento)
                .filter(Movimiento.cuenta_id.in_(self.ids), Movimiento.fecha >= ini, Movimiento.fecha < fin)
                .all()
            )
            self._ventana = v = (ini, fin, movs)
        return [m for m in v[2] if desde <= m.fecha < hasta]

    def gastado(self, categoria: str, inicio, fin) -> float:
        # Regla contable (contabilidad.py): no cuentan los pagos de tarjeta ni los
        # traslados entre cuentas propias. Se leen 3 días antes del rango solo para
        # poder emparejar traslados que caen en el borde.
        if not self.ids:
            return 0.0
        return self._gasto_por_categoria(_dt(inicio), _dt(fin)).get(categoria, 0.0)

    def _gasto_por_categoria(self, desde: datetime, hasta: datetime) -> dict[str, float]:
        """{categoría: gasto en COP} del rango. Se calcula UNA vez por rango: varios
        presupuestos comparten el mismo periodo, y emparejar traslados (tipos_efectivos)
        es lo más caro; con 20 presupuestos se repetía 80 veces."""
        clave = (desde, hasta)
        hecho = self._por_rango.get(clave)
        if hecho is None:
            movs = self._movimientos(desde - timedelta(days=3), hasta + timedelta(days=3))
            te = tipos_efectivos(movs, self._tipos)
            hecho = {}
            for m in movs:
                if desde <= m.fecha < hasta and te[m.id] == "expense":
                    hecho[m.categoria] = hecho.get(m.categoria, 0.0) + convertir_a_cop(
                        m.monto, self.monedas.get(m.cuenta_id, "COP"))
            self._por_rango[clave] = hecho
        return hecho


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
