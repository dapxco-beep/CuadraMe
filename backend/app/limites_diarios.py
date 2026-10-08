"""
Topes DIARIOS por usuario para lo que cuesta dinero o recursos.

Complementa a limites.py (ventana por hora, en memoria): ese se reinicia con cada
despliegue y no se comparte entre réplicas; este vive en la base (tabla `uso_diario`,
un contador por usuario, acción y día) y por eso aguanta ambas cosas. Solo guarda
CONTADORES, nunca contenido.

Diseño:
- El incremento es atómico (UPDATE ... WHERE cantidad < tope): dos peticiones
  simultáneas no pueden pasarse del tope.
- Falla ABIERTO: si la base del contador falla, se deja pasar (el límite por hora
  sigue activo). Preferimos no bloquear a un usuario por un fallo nuestro.
- El día es el de Colombia; el cupo se reinicia a medianoche.
"""
import logging

from fastapi import HTTPException
from sqlalchemy import Column, Integer, String, UniqueConstraint, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import gen_uuid
from app.utiles import ahora_co

logger = logging.getLogger(__name__)


class UsoDiario(Base):
    __tablename__ = "uso_diario"
    __table_args__ = (UniqueConstraint("usuario_id", "accion", "dia", name="uq_uso_diario_usuario_accion_dia"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    accion = Column(String, nullable=False)
    dia = Column(String, nullable=False)  # YYYY-MM-DD en hora Colombia
    cantidad = Column(Integer, default=0)


# accion -> (tope por día, cómo se nombra en el mensaje amable)
LIMITES_DIARIOS: dict[str, tuple[int, str]] = {
    "preguntar": (40, "preguntas al asistente"),
    "factura": (30, "facturas escaneadas"),
    "extracto": (40, "extractos procesados"),
    "conciliar-gmail": (60, "extractos conciliados desde tu correo"),
    "sync-gmail": (300, "sincronizaciones de tu correo"),
    "importar": (40, "archivos importados"),
}


def mensaje_limite(accion: str) -> str:
    tope, nombre = LIMITES_DIARIOS[accion]
    return (f"Hoy ya usaste tus {tope} {nombre} del día. Es un tope para cuidar el servicio de todos; "
            "se reinicia mañana. Si lo necesitas con urgencia, escríbenos.")


def consumir_cupo_diario(db: Session, usuario_id: str, accion: str) -> None:
    """Gasta 1 del cupo diario de `accion`; lanza 429 amable si ya se agotó."""
    tope, _nombre = LIMITES_DIARIOS[accion]
    agotado = False
    dia = ahora_co().strftime("%Y-%m-%d")
    try:
        for _ in range(2):  # 2.º intento: otra petición creó la fila justo antes que nosotros
            r = db.execute(
                update(UsoDiario)
                .where(UsoDiario.usuario_id == usuario_id, UsoDiario.accion == accion,
                       UsoDiario.dia == dia, UsoDiario.cantidad < tope)
                .values(cantidad=UsoDiario.cantidad + 1)
            )
            if r.rowcount:
                db.commit()
                return
            existe = db.query(UsoDiario.id).filter(
                UsoDiario.usuario_id == usuario_id, UsoDiario.accion == accion, UsoDiario.dia == dia
            ).first()
            if existe:
                db.rollback()
                agotado = True
                break
            try:
                db.add(UsoDiario(usuario_id=usuario_id, accion=accion, dia=dia, cantidad=1))
                db.commit()
                return
            except IntegrityError:
                db.rollback()
        else:
            return  # carrera repetida: se deja pasar
    except Exception:  # noqa: BLE001 - fallar abierto (ver docstring del módulo)
        db.rollback()
        logger.warning("No se pudo consultar el cupo diario (%s); se deja pasar", accion, exc_info=True)
        return
    if agotado:
        raise HTTPException(status_code=429, detail=mensaje_limite(accion))
