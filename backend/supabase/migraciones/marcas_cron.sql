-- Marcas de idempotencia de los crons (resumen semanal, backup diario, aviso de
-- aporte sin saldo). Idempotente. NO se ha ejecutado: create_all la crea al arrancar;
-- esto es solo por si prefieres correrlo a mano en el SQL Editor.
CREATE TABLE IF NOT EXISTS marcas_cron (
    id VARCHAR PRIMARY KEY,
    usuario_id VARCHAR NOT NULL,
    clave VARCHAR NOT NULL,
    valor VARCHAR NOT NULL,
    actualizado_en TIMESTAMP,
    CONSTRAINT uq_marca_cron_usuario_clave UNIQUE (usuario_id, clave)
);
CREATE INDEX IF NOT EXISTS ix_marcas_cron_usuario_id ON marcas_cron (usuario_id);
ALTER TABLE marcas_cron ENABLE ROW LEVEL SECURITY;
