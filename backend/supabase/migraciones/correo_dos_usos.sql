-- Correo en dos usos independientes: «Movimientos del día a día» y «Extractos para conciliar».
-- NO ejecutado: revisar y correr una vez en Supabase -> SQL Editor. Es idempotente.
-- (main.py también agrega estas columnas al arrancar.) Los valores por defecto dejan el
-- comportamiento actual intacto: ambos usos activos y la corrida lee todo.

ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS gmail_leer_movimientos BOOLEAN DEFAULT TRUE;
ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS gmail_leer_extractos   BOOLEAN DEFAULT TRUE;

ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS tipo                  VARCHAR DEFAULT 'todo';
ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS leidos_mov            INTEGER DEFAULT 0;
ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS leidos_ext            INTEGER DEFAULT 0;
ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS omitidos_mov          INTEGER DEFAULT 0;
ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS ultima_sync_mov       TIMESTAMP;
ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS ultima_sync_ext       TIMESTAMP;
ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS ultimo_leidos_mov     INTEGER DEFAULT 0;
ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS ultimo_leidos_ext     INTEGER DEFAULT 0;
ALTER TABLE sync_gmail ADD COLUMN IF NOT EXISTS ultimo_ya_registrados INTEGER DEFAULT 0;
