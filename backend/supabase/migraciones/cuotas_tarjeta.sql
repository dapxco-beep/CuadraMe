-- Compras a cuotas de una tarjeta de credito (vista de compromiso: no mueve saldos).
-- Idempotente. NO se ha ejecutado: el backend crea la tabla (create_all) y activa RLS
-- al arrancar; esto es solo por si prefieres correrlo a mano en el SQL Editor de Supabase.
CREATE TABLE IF NOT EXISTS cuotas_tarjeta (
    id VARCHAR PRIMARY KEY,
    usuario_id VARCHAR NOT NULL,
    cuenta_id VARCHAR NOT NULL,
    movimiento_id VARCHAR,
    descripcion VARCHAR NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    num_cuotas INTEGER NOT NULL,
    cuota_mensual DOUBLE PRECISION NOT NULL,
    tasa_mensual DOUBLE PRECISION DEFAULT 0,
    cuotas_pagadas INTEGER DEFAULT 0,
    primera_fecha TIMESTAMP NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    creado_en TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_cuotas_tarjeta_usuario_id ON cuotas_tarjeta (usuario_id);
CREATE INDEX IF NOT EXISTS ix_cuotas_tarjeta_cuenta_id ON cuotas_tarjeta (cuenta_id);
ALTER TABLE cuotas_tarjeta ENABLE ROW LEVEL SECURITY;
