-- «Lo que te cuesta tu plata»: columnas y tabla NUEVAS y opcionales. Idempotente.
-- NO se ha ejecutado: main.py también aplica los ALTER al arrancar en Postgres y create_all crea la tabla
-- (con RLS); esto es solo por si prefieres correrlo a mano en el SQL Editor de Supabase.

-- Categorías creadas por la app (Rendimientos, Intereses de tarjeta, Cuota de manejo, Comisiones y seguros,
-- 4x1000): no salen en presupuestos por defecto, sí en informes.
ALTER TABLE categorias ADD COLUMN IF NOT EXISTS es_sistema BOOLEAN DEFAULT FALSE;

-- Lo que cobró el banco en cada extracto de tarjeta (una fila por tarjeta y periodo AAAA-MM).
CREATE TABLE IF NOT EXISTS desgloses_extracto_tarjeta (
    id VARCHAR PRIMARY KEY,
    usuario_id VARCHAR NOT NULL,
    cuenta_id VARCHAR NOT NULL,
    periodo VARCHAR NOT NULL,
    intereses_corrientes FLOAT,
    intereses_mora FLOAT,
    cuota_manejo FLOAT,
    comisiones FLOAT,
    seguros FLOAT,
    tasa_ea FLOAT,
    tasa_mv FLOAT,
    pago_total FLOAT,
    pago_minimo FLOAT,
    fecha_corte VARCHAR,
    fecha_limite_pago VARCHAR,
    actualizado_en TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_desgloses_extracto_tarjeta_usuario_id ON desgloses_extracto_tarjeta (usuario_id);
CREATE INDEX IF NOT EXISTS ix_desgloses_extracto_tarjeta_cuenta_id ON desgloses_extracto_tarjeta (cuenta_id);
ALTER TABLE desgloses_extracto_tarjeta ENABLE ROW LEVEL SECURITY;
