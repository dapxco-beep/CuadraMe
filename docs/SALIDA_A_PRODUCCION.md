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
`OPENROUTER_API_KEY`, `OPENROUTER_MODEL_PRIVADO` (opcional; vacÃ­a = el contenido de Gmail nunca va a IA), `BACKUP_PASSPHRASE` (obligatoria para que el respaldo se envÃ­e; cifrado, ver `docs/RESTAURAR_RESPALDO.md`), `RESEND_API_KEY`, `RESEND_FROM`, `BACKUP_EMAIL`, `SOPORTE_EMAIL`,
`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY_PEM`, `VAPID_SUBJECT`, `SENTRY_DSN`, `ENVIRONMENT`,
`ADMIN_EMAIL` (tu correo: recibe los avisos y es el único que ve el panel), y opcionales con el valor del plan gratuito por defecto:
`RESEND_LIMITE_DIA` (100), `RESEND_LIMITE_MES` (3000), `SUPABASE_DB_LIMITE_MB` (500), `GMAIL_TOPE_USUARIOS` (100), `IA_PREGUNTAS_MES_AVISO` (3000), `ERRORES_5XX_AVISO` (20),
`GMAIL_MODO_PRUEBAS`, `EXIGIR_CONSENTIMIENTOS` (debe quedar en `true`), `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_LIFETIME_COP` (solo si se cobra).
**Vercel (PWA):** `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_SENTRY_DSN`, `VITE_ADMIN_EMAIL` (opcional: solo muestra el acceso «Salud del negocio» en el menú a ese correo; la seguridad la pone el backend con `ADMIN_EMAIL`).
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
| `/push/cron/resumen-semanal` | domingo 17:00 (push: «Esta semana gastaste $X, N % menos que la anterior. Lo que más pesó: ...»; ver 2b) |
| **`/resumen/cron/semanal`** (nuevo) | **domingo 18:00 (correo; solo a quien lo activó en Perfil)** |
| `/backup/cron/enviar` | diario 03:00 |
| `/metricas/cron/revisar-uso-semanal` | lunes 08:00 |
| `/cierre-mes/cron/cerrar-mes` | diario 07:00 |
| `/correos/cron/sincronizar` | cada 3 horas (`0 */3 * * *`) |
| `/patrimonio/cron/snapshot-mensual` | diario (opcional) |
| **`/metricas/cron/avisos-crecimiento`** (nuevo) | **diario 08:00 hora Bogotá** (`0 8 * * *`; monitor de capacidad, ver 3b) |

Las respuestas traen `{ok, procesados, fallidos, ...}`. El resumen por correo añade `enviados`, `ya_enviados` y `sin_datos`.
Aviso: `crear_crons.py` aún no incluye `/resumen/cron/semanal`; créalo a mano o agrégalo a la lista `JOBS` (no se hizo para no tocar horarios sin aprobación).

## 2b. Recordatorio semanal por push y «Importar mi respaldo»
**Push semanal** (`POST /push/cron/resumen-semanal`, ya estaba en `crear_crons.py`; ahora a las **17:00 del domingo**, hora Bogotá, y con el texto nuevo). El cron **aún NO está (re)creado en cron-job.org**: si ya existe el job de las 19:00, edítalo a mano o bórralo y corre `crear_crons.py --aplicar`.
- **Qué manda:** «Esta semana gastaste $X, 12 % menos que la anterior. Lo que más pesó: Comida.» con botón «Ver mis informes» (abre Informes). Solo a quien tiene push activo **y** movimientos en los últimos 7 días.
- **Reglas:** compara con la semana anterior (si la anterior queda antes del punto de partida, no compara); respeta el punto de partida; idempotente por usuario y semana ISO (`marcas_cron`, clave `resumen_semanal`; si el envío falla la marca se libera); un fallo con un usuario no frena a los demás.
- **Opt-out:** apagar «Notificaciones» en Perfil (quita la suscripción push). Con «Ocultar saldos» activado en la app el texto sale **sin montos** (la preferencia se copia a `ajustes_usuario.ocultar_montos`).
- **Columna nueva:** `ajustes_usuario.ocultar_montos` (la agrega `main.py` al arrancar; SQL suelto en `backend/supabase/migraciones/respaldo_y_push_semanal.sql`, sin ejecutar).

**Importar mi respaldo** (Perfil → Privacidad y datos): `POST /perfil/importar-respaldo/vista-previa` (no escribe), `POST /perfil/importar-respaldo` (exige `confirmar=true`), `GET /perfil/importar-respaldo/ultima` y `POST /perfil/importar-respaldo/deshacer`.
- Lee solo `datos.json` del ZIP (máx. 15 MB comprimido / 60 MB descomprimido), ignora campos desconocidos y secretos, valida `formato`/`version`. Importa cuentas, movimientos, presupuestos, metas y reglas con ids nuevos, en una sola transacción, siempre a nombre de quien importa.
- Idempotente: lo que ya existe se omite (cuentas por nombre+tipo+moneda; movimientos por huella cuenta+día+tipo+monto+descripción, contando repetidos). Respeta el punto de partida.
- Tabla nueva `importaciones_respaldo` (lote para deshacer; la crea `create_all`; SQL en el mismo archivo de migración, sin ejecutar). No aparece en «Descargar mis datos» pero sí se borra con «Borrar mi cuenta».
- Deshacer revierte solo lo importado (y los saldos de cuentas que ya tenías). Se conserva una cuenta o meta importada si después le registraste movimientos o aportes.

## 3b. Monitor de capacidad y crecimiento (te avisa antes de que algo se llene)
`POST /metricas/cron/avisos-crecimiento` (header `X-Cron-Secret`) corre **a diario a las 08:00 hora Bogotá**. El cron **aún NO está creado en cron-job.org** (no se tocan horarios sin tu aprobación): créalo a mano o agrégalo a `JOBS` de `crear_crons.py`.
- **Idempotente por umbral:** cada umbral se avisa una sola vez (marca en `marcas_cron`, usuario `sistema`, clave `crec:<recurso>:<umbral>`). Si en una corrida se cruzan varios, solo se manda el más alto. Los recursos que se reinician (Resend del día / del mes, IA del mes) se vuelven a armar al cambiar de día o mes. Si el correo falla, las marcas se liberan y se reintenta en la próxima corrida. Cada medición es tolerante: si una falla, queda «sin dato» y el resto sigue.
- **Destino:** `ADMIN_EMAIL` por Resend. Sin esa variable (o sin `RESEND_API_KEY`) los avisos solo quedan en el log de Railway. Cada aviso también va a Sentry (nivel info/warning, texto genérico sin datos personales).
- **Resumen semanal:** los lunes (hora Colombia) llega «CuadraMe: resumen semanal de crecimiento» (nuevos, activos, base %, Gmail, IA).
- **Panel:** `GET /metricas/panel` (solo `ADMIN_EMAIL`; cualquier otro usuario recibe 404) y la pantalla «Salud del negocio» (Más > Administración, ruta `#/salud-negocio`).
- **Aproximaciones a tener presentes:** el contador de errores 5xx vive en memoria del proceso (se reinicia en cada despliegue; la verdad está en Sentry). El tamaño de la base es `pg_database_size` (incluye índices y tablas del sistema, parecido a lo que mide Supabase). Los correos salidos se cuentan en `uso_diario` (usuario `sistema`) desde que se despliega esto. La fecha de alta de usuarios es `perfiles.creado_en` (columna nueva, la agrega `main.py` al arrancar; `backend/supabase/migraciones/perfil_creado_en.sql`); los perfiles anteriores se estiman con su primer movimiento.

| Recurso | Límite de referencia | Avisa a | Qué hacer |
|---|---|---|---|
| Usuarios con Gmail | 100 (`GMAIL_TOPE_USUARIOS`, sin verificación de Google) | 60 / 80 / 90 / 100 | Iniciar YA la verificación de la app en Google Cloud (tarda semanas). Al aprobarse: `GMAIL_MODO_PRUEBAS=false`. |
| Tamaño de la base | 500 MB (`SUPABASE_DB_LIMITE_MB`, plan gratuito) | 60 / 80 / 90 % | Subir a Supabase Pro (Billing) y ajustar `SUPABASE_DB_LIMITE_MB`. |
| Correos del día (Resend) | 100 (`RESEND_LIMITE_DIA`) | 80 / 90 / 100 % | Plan de pago de Resend o reducir envíos; actualizar las variables. |
| Correos del mes (Resend) | 3000 (`RESEND_LIMITE_MES`) | 60 / 80 / 90 / 100 % | Igual que arriba. |
| Preguntas a la IA del mes | 3000 (`IA_PREGUNTAS_MES_AVISO`, referencia) | 80 / 100 % | Revisar saldo en OpenRouter; subir la referencia o bajar topes de `limites_diarios.py`. |
| Movimientos guardados | 200 000 (referencia) | 60 / 80 / 100 % | Mirar tamaño real en Supabase; planear Supabase Pro. |
| Usuarios activos (7 días) | 300 (referencia de Railway Hobby) | 60 / 80 / 100 % | Pasar Railway a plan de pago / más recursos. **Ojo con varias réplicas:** los límites por hora (`limites.py`) y el chat viven en memoria de cada réplica; hay que moverlos a la base antes de escalar a más de una. |
| Errores 5xx (24 h) | 20 (`ERRORES_5XX_AVISO`) | al superarlo (1 vez al día) | Revisar Sentry y logs de Railway; si es memoria/CPU, subir el plan. |
| Usuarios que tocaron un tope diario | 3 en 7 días | al superarlo (1 vez a la semana) | Ver si es abuso o un cliente que necesita un plan mayor (`limites_diarios.py`). |

## 3c. Avisos de actividad (te avisan cuando alguien se registra y demás)
Eventos que quedan en la tabla `eventos_actividad` y se muestran en **Más > Salud del negocio > Actividad reciente** (funciona aunque no llegue ni push ni correo): `nuevo_registro`, `primera_cuenta`, `primer_movimiento`, `gmail_conectado`, `atajo_activado`, `cuenta_eliminada`, `comentario_problema` (y `comentarios_pendientes` al juntarse 5 sin revisar), `limite_alcanzado`, `umbral_capacidad`, `errores_5xx_picos`.
- **Canales:** (a) push al celular del administrador, con la misma infraestructura de notificaciones (hay que **activarlas una vez en tu celular**: Salud del negocio > Qué te avisa y cuándo > «Activar en este celular»); (b) correo por Resend a `ADMIN_EMAIL`; (c) el panel.
- **IMPORTANTE, remitente de Resend:** `RESEND_FROM` por defecto es `backup@resend.dev` (remitente de pruebas). Ese remitente **solo entrega al correo dueño de la cuenta de Resend**. Si `ADMIN_EMAIL` es otro correo, Resend responde 403 y los avisos por correo no llegan. Para recibirlos en otro correo: en Resend > Domains verifica un dominio (registros DNS) y define en Railway `RESEND_FROM="CuadraMe <avisos@tu-dominio>"`. Si el envío falla por eso, el backend deja un warning claro en el log, **no reintenta en bucle** (pausa de 6 horas), muestra el motivo en el panel y los avisos siguen llegando por push y en la lista.
- **Quién avisa a quién:** solo `ADMIN_EMAIL`. El backend aprende tu id de usuario la primera vez que abres la app con ese correo (fila en `ajustes_avisos`). Sin suscripción push o sin `RESEND_API_KEY` el canal se omite sin error.
- **Control de ruido:** máximo 20 avisos por hora (`MAX_AVISOS_POR_HORA` en `app/avisos.py`); lo que pase se agrupa en un solo «N eventos nuevos». En el panel eliges qué tipos avisan por push y por correo, silencias por horas y activas el «resumen diario».
- **Privacidad:** el aviso muestra el correo enmascarado (`d***@gmail.com`), nunca nombres, montos ni descripciones de movimientos. El correo completo solo aparece en el panel del administrador. Al eliminar su cuenta una persona, sus eventos se borran y queda solo «Una persona eliminó su cuenta».
- **Idempotencia:** `nuevo_registro` y las activaciones llevan una clave única por usuario (restricción de la base): dos peticiones simultáneas no duplican. Los usuarios que ya existían antes de estos avisos no se cuentan como «nuevos» (se detecta por `perfiles.creado_en`).
- **Cron nuevo (no creado):** `POST /avisos/cron/resumen-diario`, diario 20:00 hora Bogotá (ya está en `JOBS` de `crear_crons.py`; créalo en cron-job.org con tu aprobación). Solo hace falta si usas «resumen diario» o para recoger lo agrupado por el tope.
- **Base de datos:** tablas `eventos_actividad` y `ajustes_avisos`; el backend las crea al arrancar. Script con RLS, idempotente y **sin ejecutar**: `backend/supabase/migraciones/avisos_actividad.sql`.
- **Aproximación:** el tope por hora y la pausa del correo viven en memoria del proceso (con varias réplicas, cada una cuenta lo suyo).

## 4. Verificación después del despliegue (10 minutos)
1. `GET /health` responde `{"ok": true}`.
2. Entra a la app con una cuenta de prueba, registra un movimiento y revisa que aparezca en Inicio.
3. Perfil → «Resumen semanal por correo»: actívalo. Corre el cron a mano con el secreto: `POST /resumen/cron/semanal` debe responder `ok: true` y, si hay gastos de la semana, `enviados: 1`. Llega el correo; repetir la llamada da `ya_enviados: 1`.
4. Inicio muestra los recordatorios (si hay una tarjeta con pago cercano o un presupuesto al 80 % o más) y se pueden descartar.
5. Abre `/bienvenida.html` sin sesión: carga, el botón «Empezar» lleva al login.
6. Sentry: sin errores nuevos tras 15 minutos de uso. Logs de Railway sin trazas repetidas.
7. Un cron de prueba (p. ej. `/backup/cron/enviar`) responde 200 y el correo de respaldo llega.

## 5. Si algo falla
- **Los avisos de actividad no llegan al correo:** casi siempre es `RESEND_FROM=backup@resend.dev` con un `ADMIN_EMAIL` distinto del dueño de la cuenta de Resend (ver 3c). Mira el aviso rojo en Salud del negocio > Qué te avisa y cuándo, o el warning `Resend rechazó el correo` en los logs.
- **El deploy rompe la app:** vuelve al despliegue anterior (`railway redeploy` del anterior / «Promote» el deploy previo en Vercel). No hace falta tocar la base: los cambios de columnas son aditivos.
- **Un cron responde 401:** `CRON_SECRET` distinto entre cron-job.org y Railway. **Responde 500:** mira los logs de Railway; los fallos por usuario no frenan a los demás y salen en `fallidos`.
- **El resumen semanal no llega:** revisa `RESEND_API_KEY` y `RESEND_FROM` (dominio verificado). Si Resend falla, la marca de la semana se libera y la siguiente corrida reintenta. Resend apagado = `enviados: 0` sin error.
- **Un usuario recibe el correo dos veces:** no debería (marca única por usuario y semana en `marcas_cron`). Si pasa, revisa que no haya dos servicios de Railway corriendo el mismo cron.
- **Gmail «Acceso bloqueado»:** la app de Google sigue en modo Pruebas; agrega al usuario como tester o termina la verificación.
- **Cuentas con datos raros:** nada de borrar datos de usuarios sin aprobación (Ley 1581).
- **Pérdida de datos:** restaurar desde el último correo de `/backup/cron/enviar` (archivo `.cmbk` cifrado; descifrar segÃºn `docs/RESTAURAR_RESPALDO.md`); antes consultar con Daniel.
