"""Reglas PERSONALES de notificaciones: «aprende cómo avisa TU banco».

Cuando el lector general no puede decidir algo, el atajo de iPhone se lo pregunta a la persona. Su respuesta se
guarda como una regla SUYA para que esa forma de aviso no vuelva a preguntarse.

Privacidad (Ley 1581): la regla guarda la app y el «esqueleto» del aviso (palabras fijas de un vocabulario
cerrado; montos, nombres y todo lo demás quedan como «*»). El texto del aviso NO se guarda. Vale solo para quien
la creó, se puede ver y borrar, y no se usa para entrenar nada compartido. Sin IA.
"""
from sqlalchemy.orm import Session

from app.models import ReglaNotificacion
from app.reglas_correo import esqueleto_anonimo

MAX_REGLAS = 200


def tipo_normal(valor: str | None) -> str | None:
    v = (valor or "").strip().lower()
    return {"gasto": "expense", "egreso": "expense", "expense": "expense",
            "ingreso": "income", "income": "income"}.get(v)


def esqueleto(titulo: str, texto: str) -> str:
    """'' si el aviso no tiene suficientes palabras fijas para reconocerlo después (entonces no se aprende)."""
    return esqueleto_anonimo(f"{titulo or ''}. {texto or ''}")


def buscar(db: Session, usuario_id: str, app: str, esq: str) -> ReglaNotificacion | None:
    if not esq:
        return None
    return (db.query(ReglaNotificacion)
            .filter(ReglaNotificacion.usuario_id == usuario_id, ReglaNotificacion.app == app,
                    ReglaNotificacion.esqueleto == esq).first())


def aprender(db: Session, usuario_id: str, app: str, esq: str, *, tipo: str | None, sin_cifra: bool) -> bool:
    """Crea o actualiza la regla. False si no se pudo aprender (aviso sin forma reconocible o tope de reglas)."""
    if not esq:
        return False
    regla = buscar(db, usuario_id, app, esq)
    if regla is None:
        if db.query(ReglaNotificacion).filter(ReglaNotificacion.usuario_id == usuario_id).count() >= MAX_REGLAS:
            return False
        regla = ReglaNotificacion(usuario_id=usuario_id, app=app, esqueleto=esq, usos=0)
        db.add(regla)
    if tipo:
        regla.tipo = tipo
    if sin_cifra:
        regla.sin_cifra = True
    db.commit()
    return True


def significado(r: ReglaNotificacion) -> str:
    partes = []
    if r.sin_cifra:
        partes.append("el aviso no trae monto: te lo pregunto")
    if r.tipo:
        partes.append("es un " + ("ingreso" if r.tipo == "income" else "gasto"))
    return "; ".join(partes) or "sin efecto"
