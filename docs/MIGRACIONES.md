# Migraciones del esquema

`create_all` solo crea tablas nuevas; no altera tablas que ya existen en producción.
Para columnas o índices nuevos en tablas existentes usa `backend/app/migraciones.py`.

## Cómo funciona

- `MIGRACIONES` es una lista ordenada de `(id, [sentencias SQL])`.
- Al arrancar (solo PostgreSQL) `migraciones.aplicar(engine)` ejecuta las que no estén en la
  tabla `schema_migrations (id, aplicada_en)`. Cada una corre en su propia transacción junto
  con su registro: o queda completa y anotada, o no deja nada (si falla, el arranque falla).
- Varias instancias a la vez: un `pg_advisory_xact_lock` las serializa; la segunda ve la
  migración ya anotada y la salta.
- SQLite (tests) no ejecuta migraciones: ahí la tabla sale completa de `create_all`.

## Cómo añadir una

1. Agrega la columna al modelo.
2. Al FINAL de `MIGRACIONES` añade una tupla nueva con el id siguiente:

```python
("0002_alias_tarjeta", [
    "ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS alias_tarjeta VARCHAR NULL",
    "CREATE INDEX IF NOT EXISTS ix_x ON cuentas (alias_tarjeta)",
]),
```

3. Reglas: sentencias idempotentes (`IF NOT EXISTS`); nunca edites ni reordenes una migración
   ya desplegada; nada de `DROP` ni borrado de datos sin aprobación; si hay SQL suelto en
   `supabase/migraciones/`, mantén ambos iguales.
4. `pytest tests/test_columnas_de_arranque.py` verifica que las columnas del modelo estén cubiertas.

Nota: `0001_columnas_historicas` agrupa todos los ALTER que antes estaban en `main.py`;
en producción se ejecutará una vez (no-op, porque son idempotentes) y quedará anotada.
