r"""
Cambia de servidor los crons de CuadraMe en cron-job.org y crea el que mantiene despierto el plan gratis de Render.

- Todo job cuya URL empiece por la base VIEJA pasa a la NUEVA (se conserva ruta, horario y cabecera X-Cron-Secret).
- Crea (si no existe) «CuadraMe - mantener despierto»: GET /health cada 10 minutos.

Uso (desde backend/):
  set CRONJOB_API_KEY=...                         (la de la cuenta dapx)
  set CUADRAME_API_BASE_NUEVA=https://api.cuadrame.dapx.shop
  set CUADRAME_API_BASE_VIEJA=https://backend-production-aeab.up.railway.app   (opcional)
  python cronjobs\repuntar_crons.py            # solo muestra qué haría
  python cronjobs\repuntar_crons.py --aplicar  # lo hace

Es seguro repetirlo: si todo ya apunta a la base nueva, no cambia nada.
"""
import os
import sys
import time

import httpx

API = "https://api.cron-job.org"
VIEJA = os.environ.get("CUADRAME_API_BASE_VIEJA", "https://backend-production-aeab.up.railway.app").rstrip("/")
TITULO_VIVO = "CuadraMe - mantener despierto"


def main() -> int:
    clave = os.environ.get("CRONJOB_API_KEY", "")
    nueva = os.environ.get("CUADRAME_API_BASE_NUEVA", "").rstrip("/")
    aplicar = "--aplicar" in sys.argv
    if not clave or not nueva:
        print("Faltan CRONJOB_API_KEY y/o CUADRAME_API_BASE_NUEVA")
        return 1
    h = {"Authorization": f"Bearer {clave}", "Content-Type": "application/json"}
    with httpx.Client(timeout=30, headers=h) as c:
        r = c.get(f"{API}/jobs")
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
        print(f"{len(jobs)} jobs en la cuenta ({'APLICANDO' if aplicar else 'solo simulación'})")
        mover = [j for j in jobs if j.get("url", "").startswith(VIEJA)]
        for j in mover:
            destino = nueva + j["url"][len(VIEJA):]
            print(f"  {j['title']}: {j['url'].replace(VIEJA, '<vieja>')} -> <nueva>{j['url'][len(VIEJA):]}")
            if aplicar:
                c.patch(f"{API}/jobs/{j['jobId']}", json={"job": {"url": destino}}).raise_for_status()
                time.sleep(0.4)  # el API de cron-job.org limita las peticiones por segundo
        if not mover:
            print("  ningún job apunta ya a la base vieja")
        if any(j.get("title") == TITULO_VIVO for j in jobs):
            print(f"  «{TITULO_VIVO}» ya existe")
        else:
            print(f"  crear «{TITULO_VIVO}» (GET {nueva}/health cada 10 min)")
            if aplicar:
                cuerpo = {
                    "job": {
                        "url": nueva + "/health",
                        "title": TITULO_VIVO,
                        "enabled": True,
                        "saveResponses": False,
                        "requestMethod": 0,  # 0 = GET
                        "schedule": {
                            "timezone": "America/Bogota",
                            "expiresAt": 0,
                            "hours": [-1],
                            "minutes": list(range(0, 60, 10)),
                            "mdays": [-1],
                            "months": [-1],
                            "wdays": [-1],
                        },
                    }
                }
                c.put(f"{API}/jobs", json=cuerpo).raise_for_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
