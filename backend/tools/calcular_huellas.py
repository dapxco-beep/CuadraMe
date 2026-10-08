"""Calcula `origen` y las huellas de canal de los movimientos que ya existían antes de la regla
central de duplicados (app/duplicados.py). NO se ha ejecutado en producción.

Uso (desde backend/, con DATABASE_URL apuntando a la base):
    python tools/calcular_huellas.py            # solo cuenta lo que haría (no escribe nada)
    python tools/calcular_huellas.py --aplicar  # lo escribe

Es idempotente: correrlo otra vez no duplica ni cambia nada. Requiere que las columnas nuevas
(`movimientos.origen`, `movimientos.huella_externa`) y la tabla `huellas_origen` ya existan; el
backend las crea al arrancar (o con supabase/migraciones/duplicados_canales.sql)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.database import SessionLocal  # noqa: E402
from app.duplicados import calcular_huellas_viejas  # noqa: E402


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    db = SessionLocal()
    try:
        r = calcular_huellas_viejas(db, aplicar=aplicar)
    finally:
        db.close()
    print(("APLICADO: " if aplicar else "SIMULACIÓN (usa --aplicar para escribir): ") + str(r))


if __name__ == "__main__":
    main()
