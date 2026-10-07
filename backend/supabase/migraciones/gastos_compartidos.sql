-- Gastos compartidos (estilo Splitwise). NO ejecutado: correr UNA vez en
-- Supabase -> SQL Editor cuando se apruebe. Es idempotente (IF NOT EXISTS).
--
-- Nota: el backend ya hace Base.metadata.create_all al arrancar, que crearía
-- estas tablas solo; este archivo existe para tenerlas con RLS desde el inicio
-- (el backend usa el rol dueño y no se afecta; la API REST de Supabase queda cerrada).

CREATE TABLE IF NOT EXISTS public.contactos_gasto (
  id         VARCHAR PRIMARY KEY,
  usuario_id VARCHAR NOT NULL,
  nombre     VARCHAR NOT NULL,
  telefono   VARCHAR DEFAULT '',
  creado_en  TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_contactos_gasto_usuario ON public.contactos_gasto (usuario_id);

CREATE TABLE IF NOT EXISTS public.grupos_gasto (
  id         VARCHAR PRIMARY KEY,
  usuario_id VARCHAR NOT NULL,
  nombre     VARCHAR NOT NULL,
  creado_en  TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_grupos_gasto_usuario ON public.grupos_gasto (usuario_id);

CREATE TABLE IF NOT EXISTS public.miembros_grupo_gasto (
  id          VARCHAR PRIMARY KEY,
  grupo_id    VARCHAR NOT NULL REFERENCES public.grupos_gasto (id) ON DELETE CASCADE,
  contacto_id VARCHAR NOT NULL REFERENCES public.contactos_gasto (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_miembros_grupo_gasto_grupo ON public.miembros_grupo_gasto (grupo_id);

CREATE TABLE IF NOT EXISTS public.gastos_compartidos (
  id            VARCHAR PRIMARY KEY,
  usuario_id    VARCHAR NOT NULL,
  grupo_id      VARCHAR,
  movimiento_id VARCHAR,
  descripcion   VARCHAR NOT NULL,
  total         DOUBLE PRECISION NOT NULL,
  moneda        VARCHAR DEFAULT 'COP',
  pagador_id    VARCHAR NOT NULL,
  modo          VARCHAR DEFAULT 'iguales',
  fecha         TIMESTAMP DEFAULT now(),
  creado_en     TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_gastos_compartidos_usuario ON public.gastos_compartidos (usuario_id);
CREATE INDEX IF NOT EXISTS ix_gastos_compartidos_grupo ON public.gastos_compartidos (grupo_id);

CREATE TABLE IF NOT EXISTS public.partes_gasto (
  id              VARCHAR PRIMARY KEY,
  gasto_id        VARCHAR NOT NULL REFERENCES public.gastos_compartidos (id) ON DELETE CASCADE,
  participante_id VARCHAR NOT NULL,
  monto           DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_partes_gasto_gasto ON public.partes_gasto (gasto_id);

CREATE TABLE IF NOT EXISTS public.liquidaciones_gasto (
  id         VARCHAR PRIMARY KEY,
  usuario_id VARCHAR NOT NULL,
  grupo_id   VARCHAR,
  de_id      VARCHAR NOT NULL,
  a_id       VARCHAR NOT NULL,
  monto      DOUBLE PRECISION NOT NULL,
  moneda     VARCHAR DEFAULT 'COP',
  nota       VARCHAR DEFAULT '',
  fecha      TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_liquidaciones_gasto_usuario ON public.liquidaciones_gasto (usuario_id);

ALTER TABLE public.contactos_gasto       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.grupos_gasto          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.miembros_grupo_gasto  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gastos_compartidos    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.partes_gasto          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.liquidaciones_gasto   ENABLE ROW LEVEL SECURITY;
