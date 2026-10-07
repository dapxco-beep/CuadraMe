-- Ajuste 'importar solo lo que reconozco con certeza' al subir un extracto (apagado por defecto).
-- Idempotente. NO se ha ejecutado: main.py también lo aplica al arrancar en Postgres.
ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS autoimportar_extractos BOOLEAN DEFAULT FALSE;
