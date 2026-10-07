"""Row Level Security automático para las tablas del esquema public.

Por qué: `Base.metadata.create_all` crea tablas nuevas SIN RLS, y en Supabase el
esquema public queda legible por la API REST con la clave anon (pública). Esta
función repite, al arrancar, el equivalente a supabase/habilitar_rls.sql.
Es idempotente (solo toca tablas sin RLS) y tolerante a fallos: nunca tumba
el arranque.
"""
import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)

_LISTAR = "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity"


def _comillas(nombre: str) -> str:
    return '"' + nombre.replace('"', '""') + '"'


def asegurar_rls(engine) -> int:
    """Activa RLS en las tablas de public que no la tengan. Devuelve cuántas
    tablas se actualizaron (0 si no es Postgres o si algo falló)."""
    if engine.dialect.name != "postgresql":
        return 0
    try:
        with engine.begin() as conn:
            tablas = [fila[0] for fila in conn.execute(text(_LISTAR)).fetchall()]
            for t in tablas:
                conn.execute(text(f"ALTER TABLE public.{_comillas(t)} ENABLE ROW LEVEL SECURITY"))
        if tablas:
            logger.info("RLS activado en %d tabla(s) nueva(s): %s", len(tablas), ", ".join(tablas))
        return len(tablas)
    except Exception:
        logger.exception("No se pudo asegurar RLS (el arranque continúa)")
        return 0
