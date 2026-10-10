-- Metas con sugerencia automática + «Mi banco no aparece». NO ejecutado: correr UNA vez en
-- Supabase -> SQL Editor cuando se apruebe. Es idempotente (IF NOT EXISTS).
--
-- El backend ya agrega estas columnas solo al arrancar (bloque de ALTER en app/main.py); este archivo
-- existe para tenerlas documentadas y poder aplicarlas a mano si hiciera falta.

-- Fecha del último aporte hecho a mano a una meta (regla de consejo «meta sin aporte este mes»).
ALTER TABLE public.metas ADD COLUMN IF NOT EXISTS ultimo_aporte TIMESTAMP NULL;

-- Buzón de opinión, tipo «banco»: nombre del banco y, opcional, el archivo de muestra.
-- El archivo vive en el bucket PRIVADO «muestras-bancos» de Supabase Storage (sin URL pública);
-- aquí solo queda su ruta interna, el nombre y el tamaño. El backend crea el bucket si no existe.
ALTER TABLE public.comentarios ADD COLUMN IF NOT EXISTS banco VARCHAR NULL;
ALTER TABLE public.comentarios ADD COLUMN IF NOT EXISTS adjunto_ruta VARCHAR NULL;
ALTER TABLE public.comentarios ADD COLUMN IF NOT EXISTS adjunto_nombre VARCHAR NULL;
ALTER TABLE public.comentarios ADD COLUMN IF NOT EXISTS adjunto_bytes INTEGER NULL;
