-- Índices de rendimiento (hallazgos de tools/prueba_carga.py). NO ejecutado: correr UNA vez en
-- Supabase -> SQL Editor cuando Daniel lo apruebe. Es IDEMPOTENTE (IF NOT EXISTS) y no borra ni
-- cambia datos: solo agrega índices. Los modelos (app/models.py) ya los declaran, así que una
-- base NUEVA los trae sola; las bases existentes necesitan este script porque create_all no
-- agrega índices a tablas que ya existen.
--
-- Por qué estos:
--  * movimientos (cuenta_id, fecha): casi toda pantalla pide "movimientos de estas cuentas en un
--    rango de fechas" (reportes, presupuestos, cuadrícula de sincronización, informes).
--  * movimientos (usuario_id, fecha): detección de recurrentes, wrapped, racha, insights y
--    sugerencias filtran por usuario + fecha. Con solo índices sueltos, Postgres elige uno y
--    filtra el resto fila por fila: con cientos de miles de movimientos se nota.
--  * correos_gastos / extractos_correo (usuario_id, estado): "pendientes de revisar" y los
--    contadores de la pantalla Sincronizar se consultan en cada apertura de la app.
--  * movimientos parcial por confirmar: la bandeja "¿son tuyos?" y el contador de movimientos
--    por revisar solo miran las filas con cat_confirmada = false (muy pocas); un índice parcial
--    las encuentra sin recorrer el historial completo y casi no ocupa espacio.
--
-- Nota: en una tabla muy grande, CREATE INDEX bloquea las ESCRITURAS mientras se construye.
-- Hoy las tablas son pequeñas (segundos). Si algún día pesan mucho, correr cada línea por
-- separado cambiando "CREATE INDEX" por "CREATE INDEX CONCURRENTLY" (no puede ir dentro de una
-- transacción: ejecutar de una en una en el SQL Editor).

CREATE INDEX IF NOT EXISTS ix_movimientos_cuenta_fecha
  ON public.movimientos (cuenta_id, fecha DESC);

CREATE INDEX IF NOT EXISTS ix_movimientos_usuario_fecha
  ON public.movimientos (usuario_id, fecha DESC);

CREATE INDEX IF NOT EXISTS ix_movimientos_por_confirmar
  ON public.movimientos (cuenta_id, fecha DESC)
  WHERE cat_confirmada IS FALSE;

CREATE INDEX IF NOT EXISTS ix_correos_gastos_usuario_estado
  ON public.correos_gastos (usuario_id, estado);

CREATE INDEX IF NOT EXISTS ix_extractos_correo_usuario_estado
  ON public.extractos_correo (usuario_id, estado);

-- Deduplicación entre canales (atajo, correo, extracto, importación): cada movimiento nuevo busca su
-- huella entre las del usuario y, al borrar/mover, sus huellas por movimiento. Sin estos índices
-- esas búsquedas recorren toda la tabla de huellas. (main.py ya crea ix_movimientos_huella al
-- arrancar; aquí queda por si se corre el script antes del primer despliegue.)
CREATE INDEX IF NOT EXISTS ix_huellas_usuario_huella
  ON public.huellas_origen (usuario_id, huella);

CREATE INDEX IF NOT EXISTS ix_huellas_movimiento
  ON public.huellas_origen (movimiento_id);

CREATE INDEX IF NOT EXISTS ix_movimientos_huella
  ON public.movimientos (usuario_id, huella_externa);

-- Verificación (solo lectura): debe listar los 8 índices.
-- SELECT indexname FROM pg_indexes WHERE schemaname = 'public'
--   AND indexname IN ('ix_movimientos_cuenta_fecha', 'ix_movimientos_usuario_fecha', 'ix_movimientos_por_confirmar',
--                     'ix_correos_gastos_usuario_estado', 'ix_extractos_correo_usuario_estado',
--                     'ix_huellas_usuario_huella', 'ix_huellas_movimiento', 'ix_movimientos_huella');
