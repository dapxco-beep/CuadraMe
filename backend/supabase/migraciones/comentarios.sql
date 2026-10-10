-- Buzón de opinión («Tu opinión cuenta»): comentarios, ideas, problemas y dudas de los usuarios.
-- Idempotente. NO ejecutado: correr en Supabase -> SQL Editor (producción) solo con aprobación.
-- El backend también crea la tabla al arrancar (create_all), pero sin RLS; este script la deja con RLS.
-- Solo el backend (conexión directa) lee y escribe; la API REST pública no tiene políticas, así que no ve nada.

CREATE TABLE IF NOT EXISTS public.comentarios (
  id                 VARCHAR PRIMARY KEY,
  usuario_id         VARCHAR NOT NULL,
  email              VARCHAR,                       -- copia del correo para poder responder
  tipo               VARCHAR NOT NULL DEFAULT 'sugerencia',  -- sugerencia | problema | pregunta | elogio
  mensaje            TEXT NOT NULL,                 -- 1-2000 caracteres, sin HTML
  pantalla           VARCHAR,                       -- ruta donde estaba la persona (máx 120)
  version_app        VARCHAR,
  dispositivo        VARCHAR,                       -- resumen corto: móvil/escritorio, navegador
  puede_contactar    BOOLEAN DEFAULT TRUE,
  estado             VARCHAR NOT NULL DEFAULT 'nuevo',       -- nuevo | visto | en_curso | resuelto | descartado
  nota_admin         TEXT,                          -- interna: nunca se muestra a la persona
  respuesta_publica  TEXT,                          -- visible para quien escribió el comentario
  creado_en          TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
  actualizado_en     TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_comentarios_usuario_id ON public.comentarios (usuario_id);
CREATE INDEX IF NOT EXISTS ix_comentarios_estado_creado ON public.comentarios (estado, creado_en);

ALTER TABLE public.comentarios ENABLE ROW LEVEL SECURITY;
