"""
Carga de movimientos "efectivos" para informes y asistente: aplica la regla
contable (contabilidad.py) y convierte a COP. Es el único punto donde estas
pantallas leen movimientos, para que todas cuenten igual.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.compartidos import cuentas_ids_accesibles
from app.contabilidad import tipos_cuenta_de, tipos_efectivos
from app.fx import convertir_a_cop
from app import punto_partida
from app.models import Cuenta, Movimiento

# Se leen unos días de más en los bordes solo para poder emparejar traslados
# entre cuentas (mismo monto, <= 2 días); quien consume filtra por su rango.
MARGEN_EMPAREJAR = timedelta(days=3)


def cargar_movs_efectivos(
    db: Session,
    usuario_id: str,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    limite: int | None = None,
) -> list[dict]:
    """[{id, fecha, tipo('income'|'expense'|'transfer'), monto(COP), categoria,
    descripcion, cuenta_id}] de las cuentas accesibles, más recientes primero."""
    ids = list(cuentas_ids_accesibles(db, usuario_id))
    if not ids:
        return []
    monedas = {c.id: c.moneda for c in db.query(Cuenta).filter(Cuenta.id.in_(ids)).all()}
    q = db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids))
    # Punto de partida: informes y asistente arrancan en esa fecha (lo anterior se oculta, no se borra).
    inicio_pp = punto_partida.fecha_inicio(db, usuario_id)
    if inicio_pp:
        q = q.filter(Movimiento.fecha >= inicio_pp)
    if desde:
        q = q.filter(Movimiento.fecha >= desde - MARGEN_EMPAREJAR)
    if hasta:
        q = q.filter(Movimiento.fecha < hasta + MARGEN_EMPAREJAR)
    q = q.order_by(Movimiento.fecha.desc())
    if limite:
        q = q.limit(limite)
    movs = q.all()
    te = tipos_efectivos(movs, tipos_cuenta_de(db, ids))
    return [
        {
            "id": m.id,
            "cuenta_id": m.cuenta_id,
            "fecha": m.fecha,
            "tipo": te[m.id],
            "monto": convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP")),
            "categoria": m.categoria or "Otros",
            "descripcion": m.descripcion or "",
            "fuente": m.fuente or "manual",
        }
        for m in movs
    ]
