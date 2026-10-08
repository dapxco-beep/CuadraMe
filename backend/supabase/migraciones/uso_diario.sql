-- Topes diarios por usuario (app/limites_diarios.py). NO ejecutado: correr UNA vez en
-- Supabase -> SQL Editor cuando se apruebe. Es idempotente.
--
-- El backend ya crea la tabla solo al arrancar (create_all + RLS automático); este archivo
-- existe para tenerla documentada. Solo guarda CONTADORES por usuario/acción/día, sin contenido.
-- Si la tabla no existe o falla, el backend deja pasar (el límite por hora sigue activo).

CREATE TABLE IF NOT EXISTS public.uso_diario (
  id         VARCHAR PRIMARY KEY,
  usuario_id VARCHAR NOT NULL,
  accion     VARCHAR NOT NULL,
  dia        VARCHAR NOT NULL,
  cantidad   INTEGER DEFAULT 0,
  CONSTRAINT uq_uso_diario_usuario_accion_dia UNIQUE (usuario_id, accion, dia)
);
CREATE INDEX IF NOT EXISTS ix_uso_diario_usuario_id ON public.uso_diario (usuario_id);

ALTER TABLE public.uso_diario ENABLE ROW LEVEL SECURITY;
