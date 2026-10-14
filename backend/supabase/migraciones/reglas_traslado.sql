-- Reglas de traslado entre cuentas propias (lo que la persona decidió y pidió recordar).
-- Idempotente y OPCIONAL: sin esta tabla la app funciona igual (solo no recuerda decisiones por regla;
-- la decisión sobre cada movimiento se guarda en movimientos.notas, que ya existe).
-- Solo guarda la huella de la descripción, sin montos ni fechas.
CREATE TABLE IF NOT EXISTS public.reglas_traslado (
  id         VARCHAR PRIMARY KEY,
  usuario_id VARCHAR NOT NULL,
  huella     VARCHAR NOT NULL,
  decision   VARCHAR NOT NULL,  -- traslado | real
  creado_en  TIMESTAMP DEFAULT NOW(),
  CONSTRAINT uq_regla_traslado UNIQUE (usuario_id, huella)
);
CREATE INDEX IF NOT EXISTS ix_reglas_traslado_usuario ON public.reglas_traslado (usuario_id);
ALTER TABLE public.reglas_traslado ENABLE ROW LEVEL SECURITY;
