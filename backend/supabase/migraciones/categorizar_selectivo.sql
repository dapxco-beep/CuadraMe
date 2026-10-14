-- «Por categorizar» a elección (app/pendientes.py). NO ejecutado: correr UNA vez en
-- Supabase -> SQL Editor cuando se apruebe. Es idempotente.
--
-- El backend ya hace lo mismo solo al arrancar (ALTER ... IF NOT EXISTS + create_all + RLS
-- automático); este archivo existe para tenerlo documentado. Sin esto la app funciona igual:
-- una regla sin la columna `activa` cuenta como activa.

-- 1) Reglas «en pausa» (NULL = activa).
ALTER TABLE public.reglas_categoria ADD COLUMN IF NOT EXISTS activa BOOLEAN DEFAULT TRUE;

-- 2) Comercios que el usuario silenció. Solo guarda la huella del comercio, sin montos ni descripciones.
CREATE TABLE IF NOT EXISTS public.comercios_silenciados (
  id         VARCHAR PRIMARY KEY,
  usuario_id VARCHAR NOT NULL,
  huella     VARCHAR NOT NULL,
  tipo       VARCHAR NOT NULL DEFAULT 'no_preguntar',  -- no_preguntar | ocultar | regla_descartada
  creado_en  TIMESTAMP DEFAULT NOW(),
  CONSTRAINT uq_comercio_silenciado UNIQUE (usuario_id, huella, tipo)
);
CREATE INDEX IF NOT EXISTS ix_comercios_silenciados_usuario ON public.comercios_silenciados (usuario_id);
ALTER TABLE public.comercios_silenciados ENABLE ROW LEVEL SECURITY;
