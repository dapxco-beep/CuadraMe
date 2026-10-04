-- Sincronización de Gmail por lotes + tablero "Conexiones y estado".
-- NO ejecutado: revisar y correr una vez en Supabase -> SQL Editor. Es idempotente.
-- (main.py también agrega la columna de perfiles al arrancar y create_all crea la
-- tabla; este script deja el esquema explícito y activa RLS desde el primer momento.)

-- Último uso de la API key (Atajo de iPhone, Tasker...).
ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS api_key_ultimo_uso TIMESTAMP;

-- Estado y cursor de la sincronización de Gmail, por usuario.
CREATE TABLE IF NOT EXISTS public.sync_gmail (
    usuario_id              VARCHAR PRIMARY KEY,
    en_curso                BOOLEAN DEFAULT FALSE,
    fase                    VARCHAR DEFAULT 'etiqueta',  -- etiqueta | notificaciones | extractos
    fase_iniciada           BOOLEAN DEFAULT FALSE,
    cursor_token            VARCHAR,
    cursor_ids              VARCHAR DEFAULT '[]',
    reintento_clave_hecho   BOOLEAN DEFAULT FALSE,
    desde                   TIMESTAMP,
    iniciada_en             TIMESTAMP,
    leidos                  INTEGER DEFAULT 0,
    total_estimado          INTEGER DEFAULT 0,
    nuevos                  INTEGER DEFAULT 0,
    omitidos                INTEGER DEFAULT 0,
    extractos_nuevos        INTEGER DEFAULT 0,
    ultima_sync             TIMESTAMP,
    ultimo_leidos           INTEGER DEFAULT 0,
    ultimo_nuevos           INTEGER DEFAULT 0,
    ultimo_extractos        INTEGER DEFAULT 0,
    ultimo_error            VARCHAR,
    ultimo_error_en         TIMESTAMP
);

-- RLS sin políticas: la API REST de Supabase no ve nada; el backend (rol dueño) la ignora.
ALTER TABLE public.sync_gmail ENABLE ROW LEVEL SECURITY;
