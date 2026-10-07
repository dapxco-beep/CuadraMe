-- Registro con Apple Wallet (alias de tarjeta por cuenta) y recordatorio nocturno opcional.
-- Idempotente. NO se ha ejecutado: main.py también lo aplica al arrancar en
-- Postgres, así que esto es solo para correrlo a mano en el SQL Editor si prefieres.
ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS alias_tarjeta VARCHAR;
ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS recordatorio_diario BOOLEAN DEFAULT FALSE;
ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS ultimo_recordatorio VARCHAR;
