-- Monitor de crecimiento: fecha de alta del perfil. Idempotente. NO se ha ejecutado: main.py también
-- lo aplica al arrancar en Postgres, así que esto es solo para correrlo a mano si prefieres.
ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS creado_en TIMESTAMP;
