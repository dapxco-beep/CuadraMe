-- Resumen semanal por correo (opt-in). Idempotente. NO se ha ejecutado: main.py también lo
-- aplica al arrancar en Postgres, así que esto es solo para correrlo a mano si prefieres.
ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS resumen_correo BOOLEAN DEFAULT FALSE;
ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS email_resumen VARCHAR;
