-- Motivo por el que un extracto no se pudo leer (lista «Todos los extractos»).
-- Idempotente. NO se ha ejecutado: main.py aplica estas columnas al arrancar en Postgres
-- (ALTER ... IF NOT EXISTS); esto es solo por si prefieres correrlo a mano en el SQL Editor.
-- Opcionales: sin ellas la app funciona (los errores antiguos dicen «motivo no guardado»).
-- Valores: clave_faltante | clave_incorrecta | formato_no_reconocido | pdf_escaneado | archivo_vacio | error_temporal

ALTER TABLE historial_extractos ADD COLUMN IF NOT EXISTS motivo_error VARCHAR NULL;
ALTER TABLE extractos_correo    ADD COLUMN IF NOT EXISTS motivo_error VARCHAR NULL;
