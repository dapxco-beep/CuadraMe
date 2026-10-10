-- Avisos de actividad para la administración («avísame cuando alguien se registra y demás»).
-- Idempotente. NO ejecutado: correr en Supabase -> SQL Editor (producción) solo con aprobación.
-- El backend también crea las tablas al arrancar (create_all) y activa RLS; este script las deja listas
-- con RLS igualmente. Solo el backend (conexión directa) lee y escribe; la API REST pública no ve nada.
-- Sin datos financieros: un evento guarda el hecho (tipo, quién = id/correo, frase corta), nunca montos
-- ni descripciones. Finalidad: administración y soporte del servicio (ver docs/legal/PENDIENTES_DANIEL.md).

CREATE TABLE IF NOT EXISTS public.eventos_actividad (
  id            VARCHAR PRIMARY KEY,
  tipo          VARCHAR NOT NULL,   -- nuevo_registro | primera_cuenta | primer_movimiento | gmail_conectado | atajo_activado | cuenta_eliminada | comentario_problema | comentarios_pendientes | limite_alcanzado | umbral_capacidad | errores_5xx_picos
  usuario_id    VARCHAR,            -- NULL en cuenta_eliminada y eventos del sistema; se borra con la cuenta
  clave_unica   VARCHAR UNIQUE,     -- evita duplicados (nuevo_registro:<usuario>, limite:<usuario>:<accion>:<dia>...)
  resumen       VARCHAR NOT NULL,   -- frase corta con el correo enmascarado
  email         VARCHAR,            -- correo completo: solo lo muestra el panel del administrador
  meta          TEXT,               -- JSON pequeño (canal, acción, recurso...)
  aviso_estado  VARCHAR NOT NULL DEFAULT 'pendiente',  -- pendiente | enviado | sin_canal | silenciado | resumen | agrupado | resumido
  creado_en     TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_eventos_actividad_usuario_id ON public.eventos_actividad (usuario_id);
CREATE INDEX IF NOT EXISTS ix_eventos_actividad_creado_en ON public.eventos_actividad (creado_en);
CREATE INDEX IF NOT EXISTS ix_eventos_actividad_tipo_creado ON public.eventos_actividad (tipo, creado_en);

CREATE TABLE IF NOT EXISTS public.ajustes_avisos (
  usuario_id        VARCHAR PRIMARY KEY,   -- el administrador (ADMIN_EMAIL)
  tipos             TEXT,                  -- JSON {tipo: {"push": bool, "correo": bool}}
  silenciado_hasta  TIMESTAMP,
  resumen_diario    BOOLEAN DEFAULT FALSE,
  correo_error      VARCHAR,               -- último motivo por el que Resend rechazó un aviso
  correo_error_en   TIMESTAMP,
  actualizado_en    TIMESTAMP DEFAULT (now() AT TIME ZONE 'utc')
);

ALTER TABLE public.eventos_actividad ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ajustes_avisos ENABLE ROW LEVEL SECURITY;
