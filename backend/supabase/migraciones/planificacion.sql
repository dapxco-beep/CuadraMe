-- Planificación: periodos de presupuesto, reparto de ingresos y arrastre de sobrantes.
-- Idempotente: se puede ejecutar varias veces.
-- NO ejecutado: correr en Supabase -> SQL Editor (producción) solo con aprobación.
-- (El backend también crea la tabla al arrancar con create_all; este script existe
-- para dejarla lista con RLS activado desde el primer momento.)
-- No se tocan columnas de tablas existentes: presupuestos.periodo ya existía
-- ('monthly' por defecto; ahora también 'biweekly' y 'weekly').

CREATE TABLE IF NOT EXISTS config_planificacion (
    usuario_id          VARCHAR PRIMARY KEY,
    dia_pago            INTEGER,                         -- 1-31, ancla de la quincena
    periodo_defecto     VARCHAR DEFAULT 'monthly',       -- monthly | biweekly | weekly
    regla_necesidades   DOUBLE PRECISION DEFAULT 50,
    regla_deseos        DOUBLE PRECISION DEFAULT 30,
    regla_ahorro        DOUBLE PRECISION DEFAULT 20,
    arrastre_ids        VARCHAR DEFAULT '[]',            -- JSON: presupuestos que arrastran sobrante
    alertas_proyeccion  VARCHAR DEFAULT '{}',            -- JSON: {presupuesto_id: periodo ya avisado}
    actualizado_en      TIMESTAMP DEFAULT (now() AT TIME ZONE 'utc')
);

-- RLS: sin políticas, la API REST pública de Supabase (clave anon) no ve nada;
-- el backend (conexión directa) no se afecta.
ALTER TABLE config_planificacion ENABLE ROW LEVEL SECURITY;
