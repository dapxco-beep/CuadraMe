import os

# Se fija antes de que cualquier prueba importe la app (config.py lee el entorno al importarse).
os.environ.setdefault("CRON_SECRET", "secreto-de-prueba")
