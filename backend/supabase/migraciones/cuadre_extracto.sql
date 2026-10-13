-- Cuadre con el extracto: saldos que dice el banco, guardados en el historial de extractos.
-- Idempotente. NO se ha ejecutado: main.py aplica estas columnas al arrancar en Postgres
-- (ALTER ... IF NOT EXISTS). Esto es solo para correrlo a mano en el SQL Editor si prefieres.
-- Todo es opcional: sin estos datos la app se comporta como siempre.
-- Los saldos van en la convencion de la cuenta: en una tarjeta de credito la deuda es NEGATIVA.

ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS saldo_inicial_extracto FLOAT     NULL;
ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS saldo_final_extracto   FLOAT     NULL;
ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS fecha_corte            VARCHAR   NULL;  -- AAAA-MM-DD
ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS periodo_inicio         VARCHAR   NULL;  -- AAAA-MM-DD
ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS moneda                 VARCHAR   NULL;
ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS saldos_origen          VARCHAR   NULL;  -- extracto | tabla | manual
ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS cuadre_estado          VARCHAR   NULL;  -- cuadra | diferencia
ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS cuadre_diferencia      FLOAT     NULL;
ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS cuadre_en              TIMESTAMP NULL;
