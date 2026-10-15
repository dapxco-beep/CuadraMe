-- Nombre completo del titular (el de su cuenta de Google), SOLO para reconocer traslados propios
-- en extractos y correos («Enviaste a DANIEL ALFONSO PARRADO»). No se muestra ni sale del servidor.
-- Idempotente. Sin esta columna todo funciona: se usa solo el nombre preferido.
ALTER TABLE perfiles ADD COLUMN IF NOT EXISTS nombre_titular VARCHAR NULL;
