-- Punto de partida («empezar desde hoy» o «recrear mi histórico») y resultado de la clave del PDF.
-- Idempotente. NO se ha ejecutado: main.py aplica estas columnas al arrancar en Postgres
-- (ALTER ... IF NOT EXISTS). Esto es solo para correrlo a mano en el SQL Editor si prefieres.
-- Todo es opcional: sin estos datos la app se comporta como siempre (sin fecha de inicio).

ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS punto_partida_modo   VARCHAR   NULL;  -- hoy | historico
ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS punto_partida_fecha  DATE      NULL;  -- primer día que cuenta
ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS punto_partida_saldos VARCHAR   NULL;  -- JSON {cuenta_id: {inicial, actual}}
ALTER TABLE ajustes_usuario ADD COLUMN IF NOT EXISTS punto_partida_en     TIMESTAMP NULL;

ALTER TABLE extractos_correo ADD COLUMN IF NOT EXISTS clave_resultado  VARCHAR   NULL;  -- ok | fallo (nunca la clave)
ALTER TABLE extractos_correo ADD COLUMN IF NOT EXISTS clave_probada_en TIMESTAMP NULL;
