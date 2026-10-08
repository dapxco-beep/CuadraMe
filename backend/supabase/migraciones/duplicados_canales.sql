-- Deduplicación entre canales (app / atajo / correo / extracto / archivo).
-- Idempotente. NO se ha ejecutado: main.py aplica las columnas al arrancar en Postgres
-- (ALTER ... IF NOT EXISTS) y create_all crea la tabla; esto es solo para correrlo a mano
-- en el SQL Editor si prefieres. Todo es opcional: sin estos datos la app sigue igual.

-- 1) Columnas nuevas (opcionales) en movimientos.
ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS origen VARCHAR NULL;          -- manual | atajo | correo | extracto | importacion
ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS huella_externa VARCHAR NULL;  -- id del canal de origen
CREATE INDEX IF NOT EXISTS ix_movimientos_huella ON movimientos (usuario_id, huella_externa);

-- 2) Tabla nueva: qué canales confirmaron cada movimiento (y qué se borró, para que no resucite).
CREATE TABLE IF NOT EXISTS huellas_origen (
    id            VARCHAR PRIMARY KEY,
    usuario_id    VARCHAR NOT NULL,
    movimiento_id VARCHAR NULL,
    huella        VARCHAR NOT NULL,
    origen        VARCHAR NOT NULL,
    estado        VARCHAR DEFAULT 'vigente',   -- vigente | descartado | no_duplicado
    cuenta_id     VARCHAR NULL,
    tipo          VARCHAR NULL,
    monto         DOUBLE PRECISION NULL,
    fecha         TIMESTAMP NULL,
    clave         VARCHAR NULL,
    creado_en     TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_huellas_origen_usuario_id ON huellas_origen (usuario_id);
CREATE INDEX IF NOT EXISTS ix_huellas_usuario_huella ON huellas_origen (usuario_id, huella);
CREATE INDEX IF NOT EXISTS ix_huellas_movimiento ON huellas_origen (movimiento_id);
-- Como el resto de tablas, con RLS activado (el backend usa el rol dueño y la salta).
ALTER TABLE huellas_origen ENABLE ROW LEVEL SECURITY;

-- 3) Datos viejos: origen según la fuente de cada movimiento (solo donde aún está vacío).
UPDATE movimientos SET origen = CASE
    WHEN fuente IN ('wallet','apple_pay','google_pay','shortcut','sms','cierre_app','voz') THEN 'atajo'
    WHEN fuente = 'email' THEN 'correo'
    WHEN fuente IN ('conciliacion_auto','conciliacion_extracto') THEN 'extracto'
    WHEN fuente IN ('importacion_archivo','importado_sin_saldo','csv_import') THEN 'importacion'
    ELSE 'manual' END
WHERE origen IS NULL;
-- Las huellas de los correos ya aprobados se calculan con la herramienta de Python
-- (backend/tools/calcular_huellas.py), que también lo hace sin tocar nada con --simular.
