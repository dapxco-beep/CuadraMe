-- Detección automática de extractos bancarios en Gmail.
-- NO ejecutado: revisar y correr una vez en Supabase -> SQL Editor. Es idempotente.
-- (El backend también crea estas tablas al arrancar con create_all; este script
-- existe para dejar el esquema explícito y activar RLS desde el primer momento.)

CREATE TABLE IF NOT EXISTS public.extractos_correo (
    id                  VARCHAR PRIMARY KEY,
    usuario_id          VARCHAR NOT NULL,
    gmail_msg_id        VARCHAR NOT NULL,
    archivo             VARCHAR DEFAULT '',
    remitente           VARCHAR DEFAULT '',
    asunto              VARCHAR DEFAULT '',
    banco               VARCHAR DEFAULT '',
    periodo             VARCHAR DEFAULT '',
    cuenta_sugerida_id  VARCHAR,
    estado              VARCHAR DEFAULT 'nuevo',  -- nuevo | falta_clave | procesado | descartado | error | ignorado
    historial_id        VARCHAR,
    recibido_en         TIMESTAMP,
    creado_en           TIMESTAMP DEFAULT now(),
    CONSTRAINT uq_extracto_correo UNIQUE (usuario_id, gmail_msg_id, archivo)
);
CREATE INDEX IF NOT EXISTS ix_extractos_correo_usuario_id ON public.extractos_correo (usuario_id);

-- Clave de los PDF cifrados (normalmente la cédula). Se guarda cifrada con
-- Fernet desde el backend; la base solo ve texto cifrado.
CREATE TABLE IF NOT EXISTS public.claves_pdf (
    usuario_id      VARCHAR PRIMARY KEY,
    clave_enc       VARCHAR NOT NULL,
    actualizado_en  TIMESTAMP DEFAULT now()
);

-- RLS sin políticas: la API REST de Supabase (anon/authenticated) no ve nada;
-- el backend se conecta con el rol dueño y la ignora (igual que habilitar_rls.sql).
ALTER TABLE public.extractos_correo ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claves_pdf       ENABLE ROW LEVEL SECURITY;
