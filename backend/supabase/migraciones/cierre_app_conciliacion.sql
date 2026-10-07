-- Cruce de movimientos rápidos (Wallet / cierre de app) con el extracto del banco.
-- conciliado_en: cuándo se completó con el extracto (NULL = aún sin conciliar).
-- extracto_id:   historial_extractos.id del extracto que lo completó.
-- Idempotente. NO se ha ejecutado: main.py también lo aplica al arrancar en
-- Postgres, así que esto es solo para correrlo a mano en el SQL Editor si prefieres.
ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS conciliado_en TIMESTAMP NULL;
ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS extracto_id VARCHAR NULL;
