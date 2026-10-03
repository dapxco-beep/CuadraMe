-- Ejecutar UNA vez en Supabase → SQL Editor (proyecto de producción).
--
-- Por qué: las tablas de CuadraMe viven en el esquema "public", y Supabase
-- expone ese esquema por una API REST (PostgREST) accesible con la clave
-- "anon" que va dentro del JavaScript de la PWA (es pública por diseño).
-- Sin Row Level Security (RLS), cualquiera con esa clave podría leer o editar
-- las tablas directamente, saltándose el backend.
--
-- Con RLS activado y SIN políticas, la API REST de Supabase no devuelve ni
-- permite nada a anon/authenticated. El backend NO se afecta: se conecta con
-- el rol dueño de las tablas (DATABASE_URL), que ignora RLS.
-- La PWA solo usa Supabase para autenticarse (auth.*), no lee estas tablas.

DO $$
DECLARE t record;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
  END LOOP;
END $$;

-- Verificación: todas deben salir con rls_activo = true
SELECT tablename, rowsecurity AS rls_activo
FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
