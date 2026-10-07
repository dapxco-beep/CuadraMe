-- OPCIONAL. NO se ejecuta automáticamente; correr a mano en Supabase -> SQL Editor
-- solo si se quiere una segunda red de seguridad además de app/rls.py.
--
-- Activa RLS en cualquier tabla nueva creada en el esquema public (por la app,
-- por el SQL Editor o por una migración), sin esperar al próximo arranque.
-- Requiere un rol con permiso para crear event triggers (en Supabase: postgres).

CREATE OR REPLACE FUNCTION public.rls_automatico()
RETURNS event_trigger
LANGUAGE plpgsql
AS $$
DECLARE obj record;
BEGIN
  FOR obj IN SELECT * FROM pg_event_trigger_ddl_commands() WHERE command_tag = 'CREATE TABLE' LOOP
    IF obj.schema_name = 'public' THEN
      EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', obj.object_identity);
    END IF;
  END LOOP;
END $$;

DROP EVENT TRIGGER IF EXISTS rls_en_tablas_nuevas;
CREATE EVENT TRIGGER rls_en_tablas_nuevas
  ON ddl_command_end
  WHEN TAG IN ('CREATE TABLE')
  EXECUTE FUNCTION public.rls_automatico();

-- Para quitarlo:  DROP EVENT TRIGGER rls_en_tablas_nuevas;
