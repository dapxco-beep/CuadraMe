-- Cómo le decimos a la persona. Idempotente. NO se ha ejecutado: main.py también lo aplica al
-- arrancar en Postgres, así que esto es solo para correrlo a mano si prefieres.
ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS nombre_preferido VARCHAR NULL;
ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS nombre_confirmado BOOLEAN DEFAULT FALSE;
