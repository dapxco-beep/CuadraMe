-- CuadraMe AI (asistente financiero). NO ejecutado: correr UNA vez en
-- Supabase -> SQL Editor cuando se apruebe. Es idempotente.
--
-- El backend ya hace Base.metadata.create_all al arrancar, que crearía la
-- tabla solo; este archivo existe para tenerla con RLS desde el inicio
-- (el backend usa el rol dueño y no se afecta; la API REST de Supabase queda cerrada).
-- Solo guarda un contador diario por usuario: NO se almacenan conversaciones.

CREATE TABLE IF NOT EXISTS public.uso_asistente (
  id         VARCHAR PRIMARY KEY,
  usuario_id VARCHAR NOT NULL,
  dia        VARCHAR NOT NULL,
  cantidad   INTEGER DEFAULT 0,
  CONSTRAINT uq_uso_asistente_usuario_dia UNIQUE (usuario_id, dia)
);
CREATE INDEX IF NOT EXISTS ix_uso_asistente_usuario_id ON public.uso_asistente (usuario_id);

ALTER TABLE public.uso_asistente ENABLE ROW LEVEL SECURITY;
