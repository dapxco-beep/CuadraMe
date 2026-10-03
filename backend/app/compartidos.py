"""
Acceso compartido a cuentas (uso familiar/pareja): un usuario puede invitar
a otro por email a ver o editar una cuenta específica. El resto del sistema
sigue funcionando en base a `usuario_id` (movimientos, presupuestos, etc. no
se comparten, solo la cuenta y sus movimientos asociados vía cuenta_id).
"""
from sqlalchemy.orm import Session

from app.models import Cuenta, CuentaCompartida


def cuentas_ids_accesibles(db: Session, usuario_id: str) -> list[str]:
    """IDs de cuentas propias + cuentas compartidas con este usuario."""
    propias = db.query(Cuenta.id).filter(Cuenta.usuario_id == usuario_id).all()
    compartidas = (
        db.query(CuentaCompartida.cuenta_id)
        .filter(CuentaCompartida.usuario_id == usuario_id)
        .all()
    )
    return [r[0] for r in propias] + [r[0] for r in compartidas]


def puede_editar_cuenta(db: Session, usuario_id: str, cuenta: Cuenta) -> bool:
    if cuenta.usuario_id == usuario_id:
        return True
    compartida = (
        db.query(CuentaCompartida)
        .filter(CuentaCompartida.cuenta_id == cuenta.id, CuentaCompartida.usuario_id == usuario_id)
        .first()
    )
    return bool(compartida and compartida.rol == "editor")


def bloquear_cuenta(db: Session, cuenta_id: str) -> Cuenta | None:
    """Trae la cuenta bloqueando su fila (SELECT ... FOR UPDATE) hasta el
    commit. Los saldos se actualizan con 'leer, sumar, escribir'; sin el
    bloqueo, dos movimientos simultáneos sobre la misma cuenta leen el mismo
    saldo y uno de los dos se pierde. populate_existing fuerza a releer el
    valor actual aunque la sesión ya tuviera el objeto cargado. En SQLite
    (desarrollo local) el FOR UPDATE se ignora sin problema."""
    return (
        db.query(Cuenta)
        .filter(Cuenta.id == cuenta_id)
        .with_for_update()
        .populate_existing()
        .first()
    )


def cuenta_accesible(db: Session, usuario_id: str, cuenta_id: str) -> Cuenta | None:
    cuenta = db.query(Cuenta).filter(Cuenta.id == cuenta_id).first()
    if not cuenta:
        return None
    if cuenta.usuario_id == usuario_id:
        return cuenta
    compartida = (
        db.query(CuentaCompartida)
        .filter(CuentaCompartida.cuenta_id == cuenta_id, CuentaCompartida.usuario_id == usuario_id)
        .first()
    )
    return cuenta if compartida else None
