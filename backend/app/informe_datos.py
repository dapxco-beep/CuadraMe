"""
Carga de movimientos "efectivos" para informes y asistente: aplica la regla
contable (contabilidad.py) y convierte a la moneda base del perfil (COP por defecto). Es el único punto donde estas
pantallas leen movimientos, para que todas cuenten igual.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.compartidos import cuentas_ids_accesibles
from app.contabilidad import ConvertidorBase, clasificar, moneda_base_de, tipos_cuenta_de
from app import punto_partida
from app.models import Cuenta, Movimiento


class MovsEfectivos(list):
    """Lista de movimientos + la moneda base y las monedas SIN tasa (su monto vale 0: no se suma a ciegas;
    el original queda en monto_original). Los endpoints la copian a su respuesta como monedas_sin_tasa."""

    base = "COP"
    sin_tasa: tuple = ()


# Se leen unos días de más en los bordes solo para poder emparejar traslados
# entre cuentas (mismo monto, <= 2 días); quien consume filtra por su rango.
MARGEN_EMPAREJAR = timedelta(days=3)

# Solo las columnas que la regla contable y los informes leen: traerlas como filas sueltas (en vez de objetos ORM
# completos) ahorra cerca de la mitad del tiempo con miles de movimientos.
_COLUMNAS = ("id", "cuenta_id", "fecha", "tipo", "monto", "categoria", "subcategoria", "descripcion", "fuente", "notas")


def cargar_movs_efectivos(
    db: Session,
    usuario_id: str,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    limite: int | None = None,
) -> list[dict]:
    """[{id, fecha, tipo(income|expense|transfer), monto(moneda base del perfil), sin_tasa, categoria,
    descripcion, cuenta_id, razon, par}] de las cuentas accesibles, más recientes primero."""
    ids = list(cuentas_ids_accesibles(db, usuario_id))
    if not ids:
        return MovsEfectivos()
    monedas = {c.id: c.moneda for c in db.query(Cuenta).filter(Cuenta.id.in_(ids)).all()}
    conv = ConvertidorBase.de_usuario(db, usuario_id)
    q = db.query(*(getattr(Movimiento, c) for c in _COLUMNAS)).filter(Movimiento.cuenta_id.in_(ids))
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
    movs = [dict(zip(_COLUMNAS, fila)) for fila in q.all()]
    te = clasificar(movs, tipos_cuenta_de(db, ids))
    salida = MovsEfectivos(
        {
            "id": m["id"],
            "cuenta_id": m["cuenta_id"],
            "fecha": m["fecha"],
            "tipo": te[m["id"]]["tipo"],
            "razon": te[m["id"]]["razon"],
            "par": te[m["id"]]["par"],
            "monto": conv.contar(m["monto"], monedas.get(m["cuenta_id"], "COP")),
            "monto_original": m["monto"],
            "sin_tasa": (monedas.get(m["cuenta_id"]) or "COP").upper() in conv.sin_tasa,
            "categoria": m["categoria"] or "Otros",
            "subcategoria": m["subcategoria"],
            "descripcion": m["descripcion"] or "",
            "fuente": m["fuente"] or "manual",
        }
        for m in movs
    )
    salida.base = conv.base
    salida.sin_tasa = tuple(sorted(conv.sin_tasa))
    return salida
