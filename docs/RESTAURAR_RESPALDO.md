# Restaurar el respaldo diario

El cron `POST /backup/cron/enviar` (03:00) manda por correo `cuadrame_backup_AAAA-MM-DD.cmbk`, **cifrado** con AES-256-GCM. La clave sale de la variable `BACKUP_PASSPHRASE` (Railway) con PBKDF2-SHA256 (600 000 iteraciones). Sin esa variable el respaldo **no se envía**: el cron responde 503, hay un warning en el log y un aviso al administrador («Respaldo diario sin enviar»).

## Qué contiene y qué no
- Sí: todas las tablas de datos financieros y de configuración.
- No (nunca): `correos_gastos`, `extractos_correo`, `historial_extractos`, `sync_gmail` (contenido leído de Gmail), `claves_pdf`, `push_subscriptions`, y las columnas de tokens de Gmail, correo de Gmail y claves del Atajo (`api_key`, `api_key_hash`, `api_key_prefijo`). Tras restaurar, cada persona debe reconectar Gmail y regenerar su clave del Atajo.

## Descifrar
1. Guarda la frase `BACKUP_PASSPHRASE` en tu gestor de contraseñas (si la pierdes, los respaldos no se pueden abrir).
2. `pip install cryptography`
3. `python backend/tools/descifrar_respaldo.py cuadrame_backup_2026-10-10.cmbk respaldo.json` (pide la frase, o usa la variable de entorno `BACKUP_PASSPHRASE`).
   El resultado es JSON `{"exportado_en": ..., "tablas": {"cuentas": [...], ...}}`.
4. `respaldo.json` contiene datos personales: bórralo al terminar.

## Restaurar
1. Crea la base vacía con el esquema actual (arranca el backend contra ella o usa `supabase/`).
2. Inserta cada tabla de `tablas` en orden (primero las que no dependen de otras: `perfiles`, `cuentas`, luego `movimientos`, etc.) con `INSERT` o `pandas.to_sql(..., if_exists="append")`.
3. Verifica conteos por tabla contra el JSON. Consulta con Daniel antes de tocar producción.

## Cambiar la frase
Cambiar `BACKUP_PASSPHRASE` no afecta respaldos viejos: se abren con la frase vigente cuando se generaron. Anota la fecha de cada cambio.
