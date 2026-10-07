import os

# Se fija antes de que cualquier prueba importe la app (config.py lee el entorno al importarse).
os.environ.setdefault("CRON_SECRET", "secreto-de-prueba")
# Las pruebas antiguas usan Gmail/IA sin pasar por la pantalla de autorización; la
# exigencia se prueba de forma explícita en test_consentimientos.py (la reactiva).
os.environ.setdefault("EXIGIR_CONSENTIMIENTOS", "false")
