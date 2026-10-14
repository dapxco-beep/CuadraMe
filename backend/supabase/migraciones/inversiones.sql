-- Inversiones (opcional). NO ejecutado: correr UNA vez en Supabase -> SQL Editor cuando se apruebe.
-- Idempotente. El backend ya crea las tablas nuevas solo al arrancar (create_all); las COLUMNAS
-- nuevas de activos_patrimonio SI requieren este ALTER (create_all no altera tablas existentes).

ALTER TABLE public.activos_patrimonio ADD COLUMN IF NOT EXISTS arriendo_mensual DOUBLE PRECISION;
ALTER TABLE public.activos_patrimonio ADD COLUMN IF NOT EXISTS anio DOUBLE PRECISION;
ALTER TABLE public.activos_patrimonio ADD COLUMN IF NOT EXISTS depreciacion_pct DOUBLE PRECISION;
ALTER TABLE public.activos_patrimonio ADD COLUMN IF NOT EXISTS deuda_id VARCHAR;
ALTER TABLE public.activos_patrimonio ADD COLUMN IF NOT EXISTS broker VARCHAR;

CREATE TABLE IF NOT EXISTS public.brokers_inversion (
  id VARCHAR PRIMARY KEY, usuario_id VARCHAR NOT NULL, nombre VARCHAR NOT NULL, pais VARCHAR DEFAULT 'CO',
  tipo VARCHAR DEFAULT 'acciones', moneda VARCHAR DEFAULT 'COP', cuenta_id VARCHAR,
  activo BOOLEAN DEFAULT TRUE, creado_en TIMESTAMP DEFAULT now());
CREATE INDEX IF NOT EXISTS ix_brokers_inversion_usuario ON public.brokers_inversion (usuario_id);

CREATE TABLE IF NOT EXISTS public.posiciones_inversion (
  id VARCHAR PRIMARY KEY, usuario_id VARCHAR NOT NULL, broker_id VARCHAR, activo_id VARCHAR, ticker VARCHAR,
  mercado VARCHAR DEFAULT '', nombre VARCHAR NOT NULL, tipo VARCHAR DEFAULT 'accion', moneda VARCHAR DEFAULT 'COP',
  cantidad DOUBLE PRECISION DEFAULT 0, costo_promedio DOUBLE PRECISION DEFAULT 0,
  precio_manual DOUBLE PRECISION, precio_manual_fecha TIMESTAMP,
  activo BOOLEAN DEFAULT TRUE, creado_en TIMESTAMP DEFAULT now());
CREATE INDEX IF NOT EXISTS ix_posiciones_inversion_usuario ON public.posiciones_inversion (usuario_id);

CREATE TABLE IF NOT EXISTS public.transacciones_inversion (
  id VARCHAR PRIMARY KEY, usuario_id VARCHAR NOT NULL, posicion_id VARCHAR NOT NULL, tipo VARCHAR NOT NULL,
  fecha TIMESTAMP NOT NULL, cantidad DOUBLE PRECISION DEFAULT 0, precio DOUBLE PRECISION DEFAULT 0,
  comision DOUBLE PRECISION DEFAULT 0, monto DOUBLE PRECISION DEFAULT 0, moneda VARCHAR DEFAULT 'COP',
  tipo_cambio DOUBLE PRECISION, movimiento_id VARCHAR, nota VARCHAR DEFAULT '');
CREATE INDEX IF NOT EXISTS ix_transacciones_inversion_usuario ON public.transacciones_inversion (usuario_id);
CREATE INDEX IF NOT EXISTS ix_transacciones_inversion_pos ON public.transacciones_inversion (posicion_id);

CREATE TABLE IF NOT EXISTS public.cotizaciones_inversion (
  id VARCHAR PRIMARY KEY, ticker VARCHAR NOT NULL, mercado VARCHAR DEFAULT '', precio DOUBLE PRECISION,
  precio_anterior DOUBLE PRECISION, moneda VARCHAR DEFAULT '', fecha TIMESTAMP, consultada_en TIMESTAMP,
  fuente VARCHAR DEFAULT '', error VARCHAR DEFAULT '',
  CONSTRAINT uq_cotizacion_ticker_mercado UNIQUE (ticker, mercado));

CREATE TABLE IF NOT EXISTS public.consultas_precio (clave VARCHAR PRIMARY KEY, cantidad DOUBLE PRECISION DEFAULT 0);
CREATE TABLE IF NOT EXISTS public.pref_inversiones (usuario_id VARCHAR PRIMARY KEY, resumen_semanal BOOLEAN DEFAULT FALSE);
