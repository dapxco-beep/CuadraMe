-- Registro auditable de autorizaciones de tratamiento de datos (Ley 1581 de 2012).
-- Idempotente. NO ejecutado: correr en Supabase -> SQL Editor (producción) solo con aprobación.
-- El backend también crea la tabla al arrancar (create_all), pero sin RLS; este script la deja con RLS.
-- La tabla es de SOLO INSERCIÓN desde el backend: revocar = nueva fila con aceptado = false.

CREATE TABLE IF NOT EXISTS public.consentimientos (
  id             VARCHAR PRIMARY KEY,
  usuario_id     VARCHAR NOT NULL,
  version        VARCHAR NOT NULL,            -- versión de los textos legales aceptada (ej. '1.1')
  finalidad      VARCHAR NOT NULL,            -- tratamiento_basico | lectura_correo | ia | notificaciones
  aceptado       BOOLEAN NOT NULL,
  creado_en_utc  TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
  creado_en_co   TIMESTAMP NOT NULL,          -- misma fecha en hora Colombia (UTC-5)
  ip             VARCHAR,                     -- opcional
  origen         VARCHAR DEFAULT 'app'
);
CREATE INDEX IF NOT EXISTS ix_consentimientos_usuario_id ON public.consentimientos (usuario_id);

ALTER TABLE public.consentimientos ENABLE ROW LEVEL SECURITY;
