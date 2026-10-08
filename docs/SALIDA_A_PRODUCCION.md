# CuadraMe — Salida a producción (checklist final)

Una página. Para el detalle de cada cosa, mira `HOJA_DE_RUTA.md`. Aquí solo hay **nombres** de variables, nunca valores.

## 1. Antes de desplegar
- [ ] CI en verde en el commit a desplegar. Local: `pytest tests -q` (backend) y `npx vitest run && npm run build` (PWA).
- [ ] SQL pendiente aprobado por Daniel: `habilitar_rls.sql` (RLS en Supabase). Nada de SQL a producción sin su visto bueno.
      Las columnas nuevas (`ajustes_usuario.resumen_correo`, `.email_resumen`) las agrega `main.py` al arrancar (aditivas); el SQL suelto está en `backend/supabase/migraciones/resumen_semanal.sql`.
- [ ] Textos legales revisados por un abogado (`docs/legal/`) y datos pendientes resueltos (razón social, correo de contacto, dominio).
- [ ] Verificación de Google para el permiso de Gmail (`gmail.readonly` es sensible). Mientras no esté aprobada: `GMAIL_MODO_PRUEBAS=true` y solo entran usuarios de prueba.
- [ ] Remitente de Resend con dominio verificado (ver `RESEND_FROM`). Con el remitente de pruebas de Resend solo se puede escribir al dueño de la cuenta: **el resumen semanal no llegaría a clientes**.

## 2. Variables de entorno (solo nombres)
**Railway (backend):** `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (opcional, muy sensible: solo aquí), `CRON_SECRET`, `FERNET_KEY`,
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `API_BASE_URL`, `PWA_URL`, `CORS_ORIGINS_EXTRA`, `CORS_ORIGIN_REGEX`,
`OPENROUTER_API_KEY`, `RESEND_API_KEY`, `RESEND_FROM`, `BACKUP_EMAIL`, `SOPORTE_EMAIL`,
`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY_PEM`, `VAPID_SUBJECT`, `SENTRY_DSN`, `ENVIRONMENT`,
`GMAIL_MODO_PRUEBAS`, `EXIGIR_CONSENTIMIENTOS` (debe quedar en `true`), `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_LIFETIME_COP` (solo si se cobra).
**Vercel (PWA):** `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_SENTRY_DSN`.
Una variable nueva en el código debe existir en Railway/Vercel **antes** del deploy.

## 3. Crons (cron-job.org, `POST` con header `X-Cron-Secret`, hora Colombia)
Los 7 base se crean con `backend/cronjobs/crear_crons.py`. Los demás se agregan a mano. Todos son idempotentes: ejecutar dos veces no duplica nada.

| Endpoint | Cuándo |
|---|---|
| `/push/cron/revisar-presupuestos` | diario 08:00 |
| `/push/cron/aportes-automaticos` | diario 06:00 |
| `/push/cron/premiar-presupuestos-mes` | diario 21:00 |
| `/push/cron/recordar-recurrentes` | diario 08:30 (incluye tarjetas) |
| `/push/cron/recordar-registro` | diario 20:00 |
| `/push/cron/resumen-semanal` | domingo 19:00 (push) |
| **`/resumen/cron/semanal`** (nuevo) | **domingo 18:00 (correo; solo a quien lo activó en Perfil)** |
| `/backup/cron/enviar` | diario 03:00 |
| `/metricas/cron/revisar-uso-semanal` | lunes 08:00 |
| `/cierre-mes/cron/cerrar-mes` | diario 07:00 |
| `/correos/cron/sincronizar` | cada 3 horas (`0 */3 * * *`) |
| `/patrimonio/cron/snapshot-mensual` | diario (opcional) |

Las respuestas traen `{ok, procesados, fallidos, ...}`. El resumen por correo añade `enviados`, `ya_enviados` y `sin_datos`.
Aviso: `crear_crons.py` aún no incluye `/resumen/cron/semanal`; créalo a mano o agrégalo a la lista `JOBS` (no se hizo para no tocar horarios sin aprobación).

## 4. Verificación después del despliegue (10 minutos)
1. `GET /health` responde `{"ok": true}`.
2. Entra a la app con una cuenta de prueba, registra un movimiento y revisa que aparezca en Inicio.
3. Perfil → «Resumen semanal por correo»: actívalo. Corre el cron a mano con el secreto: `POST /resumen/cron/semanal` debe responder `ok: true` y, si hay gastos de la semana, `enviados: 1`. Llega el correo; repetir la llamada da `ya_enviados: 1`.
4. Inicio muestra los recordatorios (si hay una tarjeta con pago cercano o un presupuesto al 80 % o más) y se pueden descartar.
5. Abre `/bienvenida.html` sin sesión: carga, el botón «Empezar» lleva al login.
6. Sentry: sin errores nuevos tras 15 minutos de uso. Logs de Railway sin trazas repetidas.
7. Un cron de prueba (p. ej. `/backup/cron/enviar`) responde 200 y el correo de respaldo llega.

## 5. Si algo falla
- **El deploy rompe la app:** vuelve al despliegue anterior (`railway redeploy` del anterior / «Promote» el deploy previo en Vercel). No hace falta tocar la base: los cambios de columnas son aditivos.
- **Un cron responde 401:** `CRON_SECRET` distinto entre cron-job.org y Railway. **Responde 500:** mira los logs de Railway; los fallos por usuario no frenan a los demás y salen en `fallidos`.
- **El resumen semanal no llega:** revisa `RESEND_API_KEY` y `RESEND_FROM` (dominio verificado). Si Resend falla, la marca de la semana se libera y la siguiente corrida reintenta. Resend apagado = `enviados: 0` sin error.
- **Un usuario recibe el correo dos veces:** no debería (marca única por usuario y semana en `marcas_cron`). Si pasa, revisa que no haya dos servicios de Railway corriendo el mismo cron.
- **Gmail «Acceso bloqueado»:** la app de Google sigue en modo Pruebas; agrega al usuario como tester o termina la verificación.
- **Cuentas con datos raros:** nada de borrar datos de usuarios sin aprobación (Ley 1581).
- **Pérdida de datos:** restaurar desde el último correo de `/backup/cron/enviar` (JSON comprimido); antes consultar con Daniel.
