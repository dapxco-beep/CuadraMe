"""Utilidades pequeñas compartidas."""
from datetime import datetime, timedelta, timezone

# Colombia no tiene horario de verano: es UTC-5 todo el año, así que un
# offset fijo es exacto y evita depender de la base de datos de zonas horarias
# (tzdata), que no siempre está instalada en el contenedor.
_ZONA_CO = timezone(timedelta(hours=-5))


def ahora_co() -> datetime:
    """Hora actual de Colombia como datetime 'naive' (sin tzinfo), para
    decidir cosas como 'qué día es hoy' o 'cuándo empezó el mes' desde el
    punto de vista del usuario. Con utcnow() las 7pm del último día del mes
    ya contarían como el mes siguiente."""
    return datetime.now(_ZONA_CO).replace(tzinfo=None)
