# Lista maestra de lanzamiento de CuadraMe

**Objetivo:** una sola lista, en orden de urgencia, de todo lo que falta para abrir CuadraMe a clientes, con responsable y estado.
**Tiempo estimado:** bloqueantes: 1–2 días de trabajo propio + esperas (Google, abogado). Importantes: 1–2 semanas. El resto, después.
**Estado a 10 de octubre de 2026.** Responsables: **Daniel** (acciones en cuentas, decisiones), **Abogado**, **Claude** (código y documentos). Estado: `Pendiente`, `Por verificar` (no se pudo comprobar desde el código), `En código` (hecho en código, falta desplegar o decidir).

Documentos relacionados: [GOOGLE_VERIFICACION.md](GOOGLE_VERIFICACION.md) · [RESEND_DOMINIO.md](RESEND_DOMINIO.md) · [PRECIOS_Y_PLANES.md](PRECIOS_Y_PLANES.md) · [PRUEBA_CON_PERSONAS.md](PRUEBA_CON_PERSONAS.md) · `../SALIDA_A_PRODUCCION.md` · `../AUDITORIA_SEGURIDAD.md` · `../legal/PENDIENTES_DANIEL.md`

---

## BLOQUEANTE (no se abre a clientes sin esto)

| # | Tarea | Responsable | Estado | Dónde / cómo |
|---|---|---|---|---|
| B1 | **Rotar claves expuestas en el chat**: Hostinger, Sentry, Resend, cron-job.org y la **clave del PDF** (de los extractos). Nunca pegarlas de nuevo en un chat. | Daniel | Pendiente | Hostinger → Seguridad/contraseña; Sentry → Settings → Auth Tokens/DSN; Resend → API Keys (crear nueva, borrar vieja); cron-job.org → Settings → API; clave del PDF: cámbiala en el banco y guarda la nueva en Perfil → Clave de PDF. Después actualiza `RESEND_API_KEY`, `SENTRY_DSN`, `CRONJOB_API_KEY` en Railway/tu equipo. |
| B2 | **Respaldo diario por correo sin cifrar** (hallazgo ALTO de la auditoría): manda toda la base a `dapxco@gmail.com`. | Claude (código) + Daniel (decide) | Hecho (confirmar mañana) | Código cerrado: respaldo cifrado AES-256, sin correos/tokens/claves. `BACKUP_PASSPHRASE` puesta en Railway (12-oct-2026); Daniel debe guardar la frase en su gestor. Confirmar que mañana ~2:00 llega el adjunto `.cmbk` ([RESTAURAR_RESPALDO.md](../RESTAURAR_RESPALDO.md)). |
| B3 | **«Confirm email» activo en Supabase Auth** (evita que alguien acepte invitaciones con un correo ajeno). | Daniel | Por verificar | Supabase → Authentication → Providers → Email → *Confirm email* = ON. |
| B4 | **`SUPABASE_SERVICE_ROLE_KEY` solo en Railway** (nunca en Vercel ni en el repositorio) y comprobar que «Borrar mi cuenta» responde `auth_eliminado: true`. | Daniel | Por verificar | Railway → backend → Variables. Vercel NO debe tenerla. |
| B5 | **RLS comprobada en Supabase**: el backend la activa al arrancar (`rls.py`); verificar con la clave anónima que una consulta REST devuelve 0 filas y aplicar `backend/supabase/habilitar_rls.sql` si hay tablas sin RLS. Nada de SQL sin tu visto bueno. | Daniel | Por verificar | SQL Editor: `SELECT tablename FROM pg_tables WHERE schemaname='public' AND NOT rowsecurity;` debe dar 0 filas. |
| B6 | **Textos legales revisados por abogado** y datos propios definidos (razón social/NIT, correo de contacto de dominio propio, domicilio). | Abogado + Daniel | Pendiente | `../legal/PENDIENTES_DANIEL.md`, secciones 1–2 y «Para el abogado». |
| B7 | **Publicar versión 1.2 de los textos** (declara correo de respaldos, Resend, Sentry, búsqueda de Gmail sin etiqueta). Obliga a subir `VERSION_TEXTOS` en `pwa/src/lib/consentimientos.js` y en `backend/app/routers/consentimientos.py` y a pedir la autorización de nuevo. **Se sube con el texto del abogado, no antes.** | Daniel decide, Claude ejecuta | Pendiente | `../legal/PENDIENTES_DANIEL.md`, punto 6; texto de Gmail en [GOOGLE_VERIFICACION.md](GOOGLE_VERIFICACION.md) §5. |
| B8 | **Correo saliente con dominio verificado** (`RESEND_FROM`), o el resumen semanal no llega a clientes. | Daniel | Pendiente | [RESEND_DOMINIO.md](RESEND_DOMINIO.md). |
| B9 | **Cerrar las brechas de Gmail antes de pedir la verificación** (IA externa en PDFs de Gmail, respaldo con correos, retención, texto de consentimiento). | Claude (código) + Daniel (decide) | Parcial | B1 (IA externa) y B2 (respaldo) cerradas en código; quedan B3 y B4 de GOOGLE_VERIFICACION.md. |
| B10 | **Mientras Google no verifique Gmail**: dejar `GMAIL_MODO_PRUEBAS=true`, `EXIGIR_CONSENTIMIENTOS=true`; no invitar a más de 100 usuarios con Gmail. | Daniel | En código | Railway Variables. |

## IMPORTANTE (antes o poco después del lanzamiento)

| # | Tarea | Responsable | Estado | Dónde / cómo |
|---|---|---|---|---|
| I1 | **Verificación de Google** (OAuth + CASA): dominio en Search Console, política estática pública, video, justificación, evaluación. Empezar ya: tarda semanas. | Daniel | Pendiente | [GOOGLE_VERIFICACION.md](GOOGLE_VERIFICACION.md). |
| I2 | **`VITE_ADMIN_EMAIL` en Vercel** (tu correo) para que veas «Salud del negocio» en el menú. La seguridad la pone el backend con `ADMIN_EMAIL`. | Daniel | Hecho | `VITE_ADMIN_EMAIL` puesta en Vercel y app redesplegada (12-oct-2026). |
| I3 | **`ADMIN_EMAIL` en Railway** (para avisos y panel). | Daniel | Hecho | `ADMIN_EMAIL` y `PWA_URL=https://cuadrame.dapx.shop` puestas en Railway. |
| I4 | **Crons por crear en cron-job.org** (POST con header `X-Cron-Secret`, hora Colombia). `crear_crons.py` ya incluye 8; **faltan**: `/correos/cron/sincronizar` (cada 3 h), `/resumen/cron/semanal` (dom 18:00), `/metricas/cron/avisos-crecimiento` (diario 08:00), `/cierre-mes/cron/cerrar-mes` (07:00), `/push/cron/recordar-registro` (20:00), opcional `/patrimonio/cron/snapshot-mensual`. Revisa en cron-job.org cuáles ya existen antes de crear (son idempotentes, pero evita duplicados). | Daniel (con Claude para agregarlos a `JOBS`) | Hecho | Los 13 crons existen y están activos en cron-job.org (incluye sincronizar Gmail, avisos de crecimiento, cierre de mes y resumen diario de avisos). Único pendiente: el cron del resumen semanal **por correo** (`/resumen/cron/semanal`), que se crea cuando Resend tenga dominio verificado (B8). |
| I5 | **Región de Railway más cercana a Colombia** (hoy `sfo`, California; agrega 150–250 ms por viaje): cambiar a `us-east`. | Daniel | Pendiente | Railway → servicio backend → Settings → Region. Probar después; el servicio se reinicia. Ver `../RENDIMIENTO.md` punto 3. |
| I6 | **Prueba con 5 personas** y arreglo de lo hallado. | Daniel (conduce) + Claude (tareas) | Pendiente | [PRUEBA_CON_PERSONAS.md](PRUEBA_CON_PERSONAS.md). |
| I7 | **`FERNET_KEY` guardada en un gestor de secretos** (si se pierde, se pierden los tokens de Gmail y las claves de PDF). | Daniel | Por verificar | Gestor de contraseñas; plan futuro `MultiFernet`. |
| I8 | **Índices de rendimiento** (`backend/supabase/migraciones/indices_rendimiento.sql`, idempotente) sin ejecutar. | Daniel aprueba | Pendiente | Supabase → SQL Editor. |
| I9 | **Contar con CSP en modo `Report-Only`** en la PWA (hoy solo cabeceras básicas). | Claude | Pendiente | `pwa/vercel.json`; probar con Supabase, Sentry y fuentes. |
| I10 | **`pip-audit`/`npm audit` en CI**. | Claude | Pendiente | Workflow de CI. |
| I11 | **Plan de incidentes de 1 página** (quién, qué, en cuánto tiempo; notificación a titulares y SIC). | Daniel + Abogado | Pendiente | Lo pide el cuestionario de seguridad de Google. |
| I12 | **Dominio de la API** (`api.cuadrame.dapx.shop` → Railway) para no depender de `railway.app` en el callback de Google. Cambia `API_BASE_URL` y el URI de redirección en Google Cloud. | Daniel | Pendiente | Hostinger (DNS) + Railway → Settings → Networking → Custom domain. |
| I13 | **DNS y sitio de `dapx.shop`** (pendientes de dominio y subdominio `cuadrame`). | Daniel | Hecho | `cuadrame.dapx.shop` sirve la app (HTTPS) y `dapx.shop` el sitio de DAPX. |
| I14 | **Política de privacidad estática** en `/privacidad.html` (copia de la actual) para el revisor de Google. | Claude | Pendiente | [GOOGLE_VERIFICACION.md](GOOGLE_VERIFICACION.md) §1. |
| I15 | **Definir retención** de correos leídos y de `eventos_actividad` (propuesta: 12 meses) y plazo de que un borrado alcance a los respaldos. | Daniel decide + Abogado redacta + Claude código | Pendiente | `../legal/PENDIENTES_DANIEL.md`. |

## PUEDE ESPERAR

| # | Tarea | Responsable | Estado | Dónde / cómo |
|---|---|---|---|---|
| E1 | **Cobro y planes**: estructura, pasarela, ciclo de suscripción, textos. | Daniel decide, Claude construye | Pendiente | [PRECIOS_Y_PLANES.md](PRECIOS_Y_PLANES.md). |
| E2 | **Registro en el RNBD de la SIC** (¿aplica por tamaño?). | Abogado | Pendiente | `../legal/PENDIENTES_DANIEL.md`. |
| E3 | **Contratos de encargado** con proveedores y confirmar dónde están realmente. | Abogado | Pendiente | Idem. |
| E4 | **Más de 1 réplica en Railway**: mover los límites en memoria a base/Redis antes de escalar. | Claude | Pendiente | `AUDITORIA_SEGURIDAD.md` §3. |
| E5 | **Cuotas de almacenamiento por usuario** (según plan). | Claude | Pendiente | Idem. |
| E6 | **Rotación de `FERNET_KEY` (`MultiFernet`)**. | Claude | Pendiente | Idem. |
| E7 | **`ip_cliente` con la IP real del proxy de Railway**. | Claude | Pendiente | Idem. |
| E8 | **Pasar reportes pesados a SQL (`GROUP BY`)** si algún cliente supera ~50.000 movimientos. | Claude | Pendiente | `../RENDIMIENTO.md`. |
| E9 | **Subir a Supabase Pro / Resend Pro / Vercel Pro** cuando el monitor avise o al cobrar. | Daniel | Pendiente | `../SALIDA_A_PRODUCCION.md` §3b; costos en [PRECIOS_Y_PLANES.md](PRECIOS_Y_PLANES.md). |

---

## Orden recomendado de las próximas 2 semanas

1. **Hoy:** B1 (rotar claves) y B3/B4/B5 (verificaciones de 10 min cada una).
2. **Esta semana:** B2 y B9 con Claude; B8 (Resend); I2 (`VITE_ADMIN_EMAIL`); I4 (crons).
3. **Semana 2:** I6 (5 personas), I1 (enviar verificación a Google), B6/B7 con el abogado.
4. **Después:** E1 (cobro) cuando haya ~100 usuarios activos o lo decidas.

Cuando completes un ítem, cambia su estado aquí y en `../SALIDA_A_PRODUCCION.md` §1.
