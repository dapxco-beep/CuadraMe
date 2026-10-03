-- Tarjetas de crédito reales: datos propios de las cuentas de tipo "credito".
-- Idempotente. NO se ha ejecutado: main.py también lo aplica al arrancar en
-- Postgres, así que esto es solo para correrlo a mano en el SQL Editor si prefieres.
ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS cupo_total FLOAT;
ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS dia_corte INTEGER;
ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS dia_pago INTEGER;
ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS tasa_ea FLOAT;
ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS ultima_alerta_pago VARCHAR;
