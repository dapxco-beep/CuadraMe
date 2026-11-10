"""Reglas PERSONALES de notificaciones: «aprende cómo avisa TU banco».

Cuando el lector general no puede decidir algo, el atajo de iPhone se lo pregunta a la persona. Su respuesta se
guarda como una regla SUYA para que esa forma de aviso no vuelva a preguntarse.

Privacidad (Ley 1581): la regla guarda la app y el «esqueleto» del aviso (palabras fijas de un vocabulario
cerrado; montos, nombres y todo lo demás quedan como «*»). El texto del aviso NO se guarda. Vale solo para quien
la creó, se puede ver y borrar, y no se usa para entrenar nada compartido. Sin IA.
"""
import re

from sqlalchemy.orm import Session

from sqlalchemy import func

from app.models import Cuenta, Movimiento, ReglaNotificacion
from app.notificaciones import banco_de_cuenta, _sin_tildes
from app.wallet import alias_de
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


# Frases que SOLO salen en la pantalla de ese banco (vistas en capturas reales; sin tildes, minúsculas). El logo no se lee
# como texto, por eso no basta con buscar el nombre del banco.
HUELLAS_BANCO = {
    "nequi": ("escanea este qr con nequi", "numero nequi", "de donde salio la plata"),
    "nu": ("abrir comprobante", "id mol", "reportar un problema", "reportar problema"),
    # «Producto origen / Producto destino / Datos de la transferencia» (comprobante de transferencia de Bancolombia)
    "bancolombia": ("producto origen", "producto destino", "datos de la transferencia"),
}
# «Entidad Nequi S.A.», «a su cuenta de Bancolombia», «Banco Nequi»: ahí el banco es el DESTINO; «Institución de origen Nu» es
# el banco de quien TE ENVIÓ. En ningún caso es la cuenta de la persona.
_DESTINO = re.compile(r"\b(?:entidad|banco|cuenta de|a su cuenta de|destino|institucion de origen)\s+[a-z0-9.]+(?:\s+[a-z0-9.]+){0,2}")

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
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).order_by(Cuenta.nombre).all()
    nombres = [c.nombre for c in cuentas]
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
    # Últimos 4 dígitos de la cuenta de origen («*8223»): si coinciden con el alias de UNA cuenta suya, esa es
    ultimos = set(re.findall(r"[*•·]\s*(\d{4})\b", f"{titulo or ''} {texto or ''}"))
    if ultimos:
        con_alias = [c.nombre for c in cuentas if any(d in a for d in ultimos for a in alias_de(c))]
        if len(con_alias) == 1:
            return con_alias[0], nombres
    plano = _sin_tildes(f"{titulo or ''} {texto or ''}")
    # Huella de pantalla: si la forma de la pantalla es inconfundible de un banco, es una cuenta de ese banco; si la persona
    # tiene varias (ahorros y tarjeta de Nu, por ejemplo), se elige la que corresponde al tipo de movimiento.
    for banco, frases in HUELLAS_BANCO.items():
        if any(f in plano for f in frases):
            suyas = [c for c in cuentas if (banco_de_cuenta(c.nombre) or "").lower() == banco]
            if not suyas:
                # Ninguna cuenta se llama como el banco («Ahorros», «Mi cuenta»...): la pantalla es de ESTE banco, así que es una de las
                # cuentas que no se llaman como OTRO banco ni son efectivo o inversión. Nunca la de Nequi, Bancolombia, etc.
                suyas = [c for c in cuentas if banco_de_cuenta(c.nombre) is None and (c.tipo or "ahorro") not in ("efectivo", "inversion")]
            if suyas:
                return _elegir_de_un_banco(db, usuario_id, suyas, plano), nombres
    plano = _DESTINO.sub(" ", plano)
    # Todas las pistas del texto, por su posición: gana la que aparece PRIMERO (el encabezado es el origen). Si empatan, el nombre
    # completo de la cuenta pesa más que solo el banco.
    pistas = []  # (posición, 0 = nombre de la cuenta / 1 = solo el banco, nombre de cuenta o banco)
    for c in cuentas:
        pos = _posicion(_sin_tildes(c.nombre).strip(), plano)
        if pos is not None:
            pistas.append((pos, 0, c.nombre))
        banco = banco_de_cuenta(c.nombre)
        pos_b = _posicion(banco.lower(), plano) if banco else None
        if pos_b is not None:
            pistas.append((pos_b, 1, banco))
    if pistas:
        _pos, clase, valor = min(pistas)
        if clase == 0:
            return valor, nombres
        mismas = [c for c in cuentas if banco_de_cuenta(c.nombre) == valor]
        return _elegir_de_un_banco(db, usuario_id, mismas, plano), nombres
    return None, nombres


def _mas_reciente(db: Session, usuario_id: str, cuentas: list) -> str:
    """De estas cuentas, la del movimiento más reciente (si ninguna tiene, la primera por nombre)."""
    ultimos = dict(
        db.query(Movimiento.cuenta_id, func.max(Movimiento.fecha))
        .filter(Movimiento.usuario_id == usuario_id)
        .group_by(Movimiento.cuenta_id)
        .all()
    )
    con_uso = [(ultimos[c.id], c.nombre) for c in cuentas if ultimos.get(c.id) is not None]
    return max(con_uso)[1] if con_uso else sorted(cuentas, key=lambda c: c.nombre)[0].nombre


def _elegir_de_un_banco(db: Session, usuario_id: str, cuentas_banco: list, plano: str) -> str:
    """Ya se sabe el BANCO pero la persona tiene varias cuentas ahí (ahorros y tarjeta de crédito, por ejemplo). Una transferencia,
    un envío o un pago por llave no sale de una tarjeta de crédito: se prefiere la que no es de crédito; entre las que quedan,
    la que se usó más recientemente."""
    if len(cuentas_banco) == 1:
        return cuentas_banco[0].nombre
    es_transferencia = re.search(r"transferencia|enviaste|enviado a|bre ?-?b|llave|envio realizado", plano) is not None
    candidatas = cuentas_banco
    if es_transferencia:
        candidatas = [c for c in cuentas_banco if (c.tipo or "ahorro") != "credito"] or cuentas_banco
    return _mas_reciente(db, usuario_id, candidatas)


def cuenta_mas_reciente(db: Session, usuario_id: str) -> str | None:
    """Cuenta con el movimiento más reciente (si ninguna tiene, la primera por nombre): la apuesta cuando un comprobante no
    deja saber de qué banco es. Es la misma regla que ya usa el Wallet para desempatar entre cuentas del mismo banco."""
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).order_by(Cuenta.nombre).all()
    if not cuentas:
        return None
    return _mas_reciente(db, usuario_id, cuentas)


def significado(r: ReglaNotificacion) -> str:
    if (r.app or "").startswith(PREFIJO_CUENTA):
        return f"los pantallazos con esta forma son de {r.app[len(PREFIJO_CUENTA):]}"
    partes = []
    if r.sin_cifra:
        partes.append("el aviso no trae monto: te lo pregunto")
    if r.tipo:
        partes.append("es un " + ("ingreso" if r.tipo == "income" else "gasto"))
    return "; ".join(partes) or "sin efecto"
