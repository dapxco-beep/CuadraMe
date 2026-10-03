"""
Rachas de constancia (días consecutivos registrando movimientos) y el
otorgamiento de vidas del ahorcado que se derivan de ellas y de otros hitos.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models import Meta, Presupuesto, RachaUsuario, VidaAhorcado

# Todas las fechas se guardan en UTC, pero el "día" de una racha debe
# calcularse en hora de Colombia: un movimiento registrado a las 7pm-11:59pm
# COT ya cae en el día siguiente en UTC, lo que rompía rachas o las contaba
# de más si se comparaba directo con datetime.utcnow().date().
_TZ_COLOMBIA = ZoneInfo("America/Bogota")


def _dia_colombia(momento_utc: datetime) -> date:
    return momento_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(_TZ_COLOMBIA).date()


def registrar_actividad_hoy(db: Session, usuario_id: str) -> dict:
    """Llamar cada vez que el usuario crea un movimiento. Actualiza la racha
    y otorga vidas en los hitos 7 y 30 días (una sola vez por hito, hasta que
    la racha se rompe y vuelve a alcanzarlo)."""
    hoy = _dia_colombia(datetime.utcnow())
    racha = db.query(RachaUsuario).filter(RachaUsuario.usuario_id == usuario_id).first()
    if not racha:
        racha = RachaUsuario(usuario_id=usuario_id, dias_consecutivos=0, mejor_racha=0)
        db.add(racha)

    ultimo = _dia_colombia(racha.ultimo_dia_activo) if racha.ultimo_dia_activo else None

    if ultimo == hoy:
        return {"dias_consecutivos": racha.dias_consecutivos, "vida_otorgada": None}

    if ultimo == hoy - timedelta(days=1):
        racha.dias_consecutivos += 1
    else:
        racha.dias_consecutivos = 1

    racha.ultimo_dia_activo = datetime.utcnow()
    racha.mejor_racha = max(racha.mejor_racha, racha.dias_consecutivos)

    vida_otorgada = None
    if racha.dias_consecutivos == 7:
        vida_otorgada = "racha_7"
    elif racha.dias_consecutivos == 30:
        vida_otorgada = "racha_30"

    if vida_otorgada:
        db.add(VidaAhorcado(usuario_id=usuario_id, origen=vida_otorgada))

    db.commit()
    return {"dias_consecutivos": racha.dias_consecutivos, "vida_otorgada": vida_otorgada}


def otorgar_vida_si_nueva(db: Session, usuario_id: str, origen: str) -> bool:
    """Otorga una vida por un hito puntual (meta cumplida, presupuesto del mes
    cumplido) solo si no se ha otorgado ya una vida con ese mismo origen hoy
    (evita duplicar si se llama varias veces)."""
    # Mismo criterio de "día" que las rachas: medianoche en Colombia, no en
    # UTC, convertida de vuelta a UTC (naive, como se guarda creado_en) para
    # poder compararla contra la columna en la consulta.
    hoy_colombia = _dia_colombia(datetime.utcnow())
    hoy_inicio_local = datetime(hoy_colombia.year, hoy_colombia.month, hoy_colombia.day, tzinfo=_TZ_COLOMBIA)
    hoy_inicio = hoy_inicio_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    ya_otorgada = (
        db.query(VidaAhorcado)
        .filter(
            VidaAhorcado.usuario_id == usuario_id,
            VidaAhorcado.origen == origen,
            VidaAhorcado.creado_en >= hoy_inicio,
        )
        .first()
    )
    if ya_otorgada:
        return False
    db.add(VidaAhorcado(usuario_id=usuario_id, origen=origen))
    db.commit()
    return True


def vidas_disponibles(db: Session, usuario_id: str) -> int:
    return (
        db.query(VidaAhorcado)
        .filter(VidaAhorcado.usuario_id == usuario_id, VidaAhorcado.usada == False)  # noqa: E712
        .count()
    )
