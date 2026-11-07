"""Reglas PERSONALES de notificaciones: «aprende cómo avisa TU banco».

Cuando el lector general no puede decidir algo, el atajo de iPhone se lo pregunta a la persona. Su respuesta se
guarda como una regla SUYA para que esa forma de aviso no vuelva a preguntarse.

Privacidad (Ley 1581): la regla guarda la app y el «esqueleto» del aviso (palabras fijas de un vocabulario
cerrado; montos, nombres y todo lo demás quedan como «*»). El texto del aviso NO se guarda. Vale solo para quien
la creó, se puede ver y borrar, y no se usa para entrenar nada compartido. Sin IA.
"""
import re

from sqlalchemy.orm import Session

from app.models import Cuenta, ReglaNotificacion
from app.notificaciones import banco_de_cuenta, _sin_tildes
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


PREFIJO_CUENTA = "pantalla:"  # regla «esta forma de pantallazo es de ESTA cuenta» (app = «pantalla:<cuenta>»)


def _posicion(clave: str, texto_plano: str) -> int | None:
    """Dónde aparece la palabra completa en el texto (None si no aparece)."""
    if not clave:
        return None
    m = re.search(rf"(?<![a-z0-9]){re.escape(clave)}(?![a-z0-9])", texto_plano)
    return m.start() if m else None


def inferir_cuenta(db: Session, usuario_id: str, titulo: str, texto: str, elegida: str | None = None) -> tuple[str | None, list[str]]:
    """Cuenta de un pantallazo sin preguntar, en este orden: la que la persona acaba de elegir, la que ya enseñó para esta
    forma de pantallazo, y la cuenta suya cuyo nombre o banco (Nu, Nequi...) aparece en el texto. Un comprobante nombra
    el banco de origen y el de destino: gana el que aparece PRIMERO (el encabezado es el origen); si se equivoca, la
    persona lo corrige una vez y se aprende. Devuelve
    (cuenta o None si no hay forma de saberlo, nombres de todas sus cuentas para preguntar sólo en ese caso)."""
    nombres = [c.nombre for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).order_by(Cuenta.nombre).all()]
    if elegida:
        return (next((n for n in nombres if n.lower() == elegida.strip().lower()), None), nombres)
    esq = esqueleto(titulo, texto)
    if esq:
        regla = (db.query(ReglaNotificacion)
                 .filter(ReglaNotificacion.usuario_id == usuario_id, ReglaNotificacion.esqueleto == esq,
                         ReglaNotificacion.app.like(PREFIJO_CUENTA + "%")).first())
        if regla is not None:
            nombre = regla.app[len(PREFIJO_CUENTA):]
            if nombre in nombres:
                return nombre, nombres
    plano = _sin_tildes(f"{titulo or ''} {texto or ''}")
    halladas = []  # (posición en el texto, nombre)
    for nombre in nombres:
        claves = {_sin_tildes(nombre).strip()}
        banco = banco_de_cuenta(nombre)
        if banco:
            claves.add(banco.lower())
        pos = [p for p in (_posicion(k, plano) for k in claves) if p is not None]
        if pos:
            halladas.append((min(pos), nombre))
    return (min(halladas)[1] if halladas else None), nombres


def significado(r: ReglaNotificacion) -> str:
    if (r.app or "").startswith(PREFIJO_CUENTA):
        return f"los pantallazos con esta forma son de {r.app[len(PREFIJO_CUENTA):]}"
    partes = []
    if r.sin_cifra:
        partes.append("el aviso no trae monto: te lo pregunto")
    if r.tipo:
        partes.append("es un " + ("ingreso" if r.tipo == "income" else "gasto"))
    return "; ".join(partes) or "sin efecto"
