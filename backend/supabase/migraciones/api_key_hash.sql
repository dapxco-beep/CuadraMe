-- Clave API del Atajo guardada como hash SHA-256. NO ejecutado: correr UNA vez en
-- Supabase -> SQL Editor cuando se apruebe. Es idempotente.
--
-- Las claves antiguas siguen en perfiles.api_key (en claro) y funcionan igual:
-- el backend las migra a hash solo, la primera vez que se usan, y deja api_key en NULL.
-- Mientras esta columna no exista, el backend se comporta como antes (todo en claro).
ALTER TABLE public.perfiles ADD COLUMN IF NOT EXISTS api_key_hash VARCHAR;
ALTER TABLE public.perfiles ADD COLUMN IF NOT EXISTS api_key_prefijo VARCHAR;
CREATE UNIQUE INDEX IF NOT EXISTS ix_perfiles_api_key_hash ON public.perfiles (api_key_hash);
