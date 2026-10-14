-- Fecha del movimiento leida del texto del correo del banco (UTC, opcional). Idempotente.
-- NO se ha ejecutado: main.py tambien la aplica al arrancar en Postgres.
ALTER TABLE correos_gastos ADD COLUMN IF NOT EXISTS fecha_movimiento TIMESTAMP;
