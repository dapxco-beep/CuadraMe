-- País, moneda base, zona horaria e idioma del usuario (expansión LATAM). NO ejecutado:
-- correr UNA vez en Supabase -> SQL Editor cuando se apruebe. Es idempotente.
-- Mientras no existan, el backend trata a todos como Colombia (comportamiento de siempre).
ALTER TABLE public.perfiles ADD COLUMN IF NOT EXISTS pais VARCHAR;
ALTER TABLE public.perfiles ADD COLUMN IF NOT EXISTS moneda_base VARCHAR;
ALTER TABLE public.perfiles ADD COLUMN IF NOT EXISTS zona_horaria VARCHAR;
ALTER TABLE public.perfiles ADD COLUMN IF NOT EXISTS idioma VARCHAR;
ALTER TABLE public.perfiles ADD COLUMN IF NOT EXISTS pais_confirmado BOOLEAN;
