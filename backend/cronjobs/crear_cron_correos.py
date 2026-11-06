r"""
Crea SOLO el cron que lee los correos de los bancos (cada hora de 6 a 23 h, hora Colombia).
No toca los otros jobs de cron-job.org y no duplica: si ya existe uno con el mismo título, no hace nada.

Uso (desde backend/), en tu terminal de Windows (las llaves no se guardan en ningún archivo):
  set CRONJOB_API_KEY=...   (cron-job.org -> Settings -> API -> Create API key)
  set CRON_SECRET=...       (el mismo valor que CRON_SECRET en Railway)
  venv\Scripts\python.exe cronjobs\crear_cron_correos.py            # solo muestra qué haría
  venv\Scripts\python.exe cronjobs\crear_cron_correos.py --aplicar  # lo crea
"""
import os
import sys

import httpx

API = "https://api.cron-job.org"
URL = os.environ.get("CUADRAME_API_BASE", "https://backend-production-aeab.up.railway.app").rstrip("/") + "/correos/cron/sincronizar"
TITULO = "CuadraMe - leer correos de los bancos"


def cuerpo(secreto: str) -> dict:
    return {
        "job": {
            "url": URL,
            "title": TITULO,
            "enabled": True,
            "saveResponses": False,
            "requestMethod": 1,  # 1 = POST
            "schedule": {
                "timezone": "America/Bogota",
                "expiresAt": 0,
                "hours": list(range(6, 24)),
                "minutes": [0],
                "mdays": [-1],
                "months": [-1],
                "wdays": [-1],
            },
            "extendedData": {"headers": {"X-Cron-Secret": secreto}},
        }
    }


if __name__ == "__main__":
    secreto = os.environ.get("CRON_SECRET", "")
    api_key = os.environ.get("CRONJOB_API_KEY", "")
    aplicar = "--aplicar" in sys.argv
    if not secreto:
        sys.exit("Falta la variable CRON_SECRET")
    print(f"Crearía: {TITULO}\n  POST {URL}\n  cada hora en punto, de 6:00 a 23:00 (America/Bogota), todos los días")
    if not aplicar:
        sys.exit("\n(simulación: agrega --aplicar para crearlo)")
    if not api_key:
        sys.exit("Falta la variable CRONJOB_API_KEY")
    h = {"Authorization": f"Bearer {api_key}"}
    existentes = httpx.get(f"{API}/jobs", headers=h, timeout=30)
    existentes.raise_for_status()
    if any(j.get("title") == TITULO for j in existentes.json().get("jobs", [])):
        sys.exit("Ya existe un job con ese título: no hago nada.")
    r = httpx.put(f"{API}/jobs", json=cuerpo(secreto), headers=h, timeout=30)
    print(r.status_code, r.text[:200])
    sys.exit(0 if r.status_code == 200 else 1)
