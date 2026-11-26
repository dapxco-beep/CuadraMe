import os

# Red de seguridad: si el entorno trae una DATABASE_URL que no es SQLite (p. ej. la de producción), las pruebas se niegan a
# correr. Las pruebas crean y borran datos; jamás deben tocar una base real.
_url = os.environ.get("DATABASE_URL", "")
if _url and not _url.lower().startswith("sqlite"):
    raise RuntimeError("DATABASE_URL apunta a una base que no es SQLite: las pruebas no se ejecutan contra bases reales.")

# Se fija antes de que cualquier prueba importe la app (config.py lee el entorno al importarse).
os.environ.setdefault("CRON_SECRET", "secreto-de-prueba")
# Las pruebas antiguas usan Gmail/IA sin pasar por la pantalla de autorización; la
# exigencia se prueba de forma explícita en test_consentimientos.py (la reactiva).
os.environ.setdefault("EXIGIR_CONSENTIMIENTOS", "false")
