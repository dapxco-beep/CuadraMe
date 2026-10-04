-- Categorías libres (color y tipo) y categorización automática transparente.
-- Idempotente. NO se ha ejecutado: main.py también lo aplica al arrancar en
-- Postgres, así que esto es solo para correrlo a mano en el SQL Editor si prefieres.
ALTER TABLE categorias ADD COLUMN IF NOT EXISTS color VARCHAR;
ALTER TABLE categorias ADD COLUMN IF NOT EXISTS tipo VARCHAR DEFAULT 'ambos';
-- Con DEFAULT TRUE todos los movimientos que ya existen quedan como "confirmados".
ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS cat_origen VARCHAR;
ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS cat_confirmada BOOLEAN DEFAULT TRUE;
