r"""
Crea (o recrea) los 7 crons de CuadraMe en cron-job.org por su API, con los
horarios correctos y zona horaria de Colombia.

Uso (desde backend/):
  set CRONJOB_API_KEY=...   (cron-job.org -> Settings -> API -> Create API key)
  set CRON_SECRET=...       (el mismo valor que CRON_SECRET en Railway)
  venv\Scripts\python.exe cronjobs\crear_crons.py            # solo muestra qué haría
  venv\Scripts\python.exe cronjobs\crear_crons.py --aplicar  # crea los jobs

Antes de aplicar, borra o desactiva a mano los 3 jobs viejos que corren cada 15 minutos,
para no duplicar.
"""
import json
import os
import sys

import httpx

BASE = "https://backend-production-aeab.up.railway.app"
TZ = "America/Bogota"

# (título, ruta, horas, minutos, días-de-semana [-1 = todos; 0=domingo])
JOBS = [
    ("CuadraMe - aportes automaticos", "/push/cron/aportes-automaticos", [8], [0], [-1]),
    ("CuadraMe - revisar presupuestos", "/push/cron/revisar-presupuestos", [18], [0], [-1]),
    ("CuadraMe - premiar presupuestos (fin de mes)", "/push/cron/premiar-presupuestos-mes", [21], [0], [-1]),
    ("CuadraMe - recordar recurrentes", "/push/cron/recordar-recurrentes", [9], [0], [-1]),
    ("CuadraMe - resumen semanal (push, domingo en la tarde)", "/push/cron/resumen-semanal", [17], [0], [0]),
    ("CuadraMe - backup diario", "/backup/cron/enviar", [2], [0], [-1]),
    ("CuadraMe - uso semanal", "/metricas/cron/revisar-uso-semanal", [8], [0], [1]),
    # Minimización de datos de Gmail: sin efecto mientras RETENCION_* valgan 0 en Railway (decide Daniel).
    ("CuadraMe - purgar retencion de datos", "/correos/cron/purgar-retencion", [3], [30], [-1]),
    # Inversiones (opcional): precios por ticker cada 30 min en horario de mercado (L-V, 8 a 17 h)
    # y push semanal del portafolio solo para quien lo activó. Se crean SOLO si Daniel lo decide.
    ("CuadraMe - precios de inversiones", "/inversiones/cron/actualizar-precios", [8, 10, 12, 14, 16], [0, 30], [1, 2, 3, 4, 5]),
    ("CuadraMe - resumen semanal de inversiones", "/inversiones/cron/resumen-semanal", [18], [0], [0]),
    ("CuadraMe - resumen diario de avisos", "/avisos/cron/resumen-diario", [20], [0], [-1]),
    ("CuadraMe - avisar renta (push 14 y 3 dias antes)", "/impuestos/cron/avisar-renta", [9], [30], [-1]),
]


def construir(secreto: str) -> list[dict]:
    return [
        {
            "job": {
                "url": BASE + ruta,
                "title": titulo,
                "enabled": True,
                "saveResponses": False,
                "requestMethod": 1,  # 1 = POST
                "schedule": {
                    "timezone": TZ,
                    "expiresAt": 0,
                    "hours": horas,
                    "minutes": minutos,
                    "mdays": [-1],
                    "months": [-1],
                    "wdays": wdays,
                },
                "extendedData": {"headers": {"X-Cron-Secret": secreto}},
            }
        }
        for titulo, ruta, horas, minutos, wdays in JOBS
    ]


if __name__ == "__main__":
    secreto = os.environ.get("CRON_SECRET", "")
    api_key = os.environ.get("CRONJOB_API_KEY", "")
    aplicar = "--aplicar" in sys.argv
    if not secreto:
        sys.exit("Falta la variable CRON_SECRET")
    cuerpos = construir(secreto)
    for c in cuerpos:
        j = c["job"]
        print(f'{j["title"]:48} {j["schedule"]["hours"]}:{j["schedule"]["minutes"]} wdays={j["schedule"]["wdays"]}')
    if not aplicar:
        sys.exit("\n(simulación: agrega --aplicar para crearlos)")
    if not api_key:
        sys.exit("Falta la variable CRONJOB_API_KEY")
    for c in cuerpos:
        r = httpx.put("https://api.cron-job.org/jobs", json=c, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
        print(r.status_code, r.text[:120])
