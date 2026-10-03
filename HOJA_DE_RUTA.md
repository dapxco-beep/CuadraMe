# CuadraMe — Hoja de ruta

Última actualización: 2026-10-03. Estado: backend y frontend desplegados y estables en producción (Railway + Vercel). Todo lo marcado ✅ ya está en producción; lo marcado ⏳ necesita algo de ti antes de activarse; lo marcado 🔲 es trabajo pendiente de construir.

---

## 🆕 Revisión de salida a producción (2026-10-03) — lo que necesita tu mano

1. **Activar RLS en Supabase (5 min, importante).** Abre Supabase → SQL Editor y ejecuta `backend/supabase/habilitar_rls.sql`. Las tablas viven en el esquema público; sin RLS cualquiera con la clave `anon` (que va dentro del JS de la app) podría leerlas directo, saltándose el backend. El backend no se afecta. No pude verificar si ya estaba activado, así que ejecútalo igual: es idempotente.
2. **Arreglar los horarios en cron-job.org.** Los logs de Railway mostraban `aportes-automaticos` y `premiar-presupuestos-mes` corriendo **cada 15 minutos** y `revisar-presupuestos` cada hora. Deben ser: aportes-automaticos 1 vez al día; premiar-presupuestos-mes 1 vez al día (el código ya solo actúa el último día del mes); revisar-presupuestos 1 vez al día; resumen-semanal y revisar-uso-semanal 1 vez por semana; recordar-recurrentes 1 vez al día. El código ya está blindado contra repeticiones, pero los horarios correctos ahorran carga.
3. **Revisar vidas del árbol de octubre.** Por el cron cada 15 min, premiar-presupuestos-mes pudo otorgar la vida `presupuesto_cumplido_2026-10` el día 1 sin que se hubiera cumplido nada. Es un solo registro y solo afecta al ahorcado.
4. **(Opcional) `SUPABASE_SERVICE_ROLE_KEY` en Railway.** Con ella, "Eliminar mi cuenta" también borra el usuario de Supabase Auth. Sin ella se borran todos los datos pero el correo queda registrado en Supabase. Es una clave muy sensible: solo en Railway, nunca en Vercel ni en el repo.
5. **Región de Railway: `sfo` (California).** Tus usuarios están en Colombia; mover el servicio a `us-east` baja la latencia. Es un cambio de un clic en Railway → Settings → Region.

**Lo que se hizo en esta revisión:** edición de movimientos, transferencias entre cuentas, recuperar contraseña, eliminar cuenta y datos (Ley 1581), cuentas en USD/EUR, paginación, caché offline, límites de uso (IA, PDF, Gmail, API key), horas de Colombia en todo el backend, bloqueo de filas para saldos, 49 pruebas de backend y 33 de interfaz. Ver `backend/tests` y `pwa/src/test`.

**Cómo correr las pruebas:** `cd backend && venv/Scripts/python.exe -m pytest tests` y `cd pwa && npm test`.

---

## 🔴 Bloqueante — antes de invitar gente nueva

- 🔲 **Verificación OAuth de Google (Gmail)**: hoy solo funciona para correos agregados como "test user" en Google Cloud Console → OAuth consent screen. Cualquier persona nueva que quiera conectar su Gmail va a ver un error 403 si no la agregas primero ahí. Dos caminos:
  - Rápido: seguir agregando test users a mano (hasta 100), suficiente para la beta.
  - Definitivo: iniciar la verificación formal de Google para el scope `gmail.readonly` — puede pedir una auditoría CASA (potencialmente costosa, cientos-miles de USD). Investigar la probabilidad real antes de decidir.

---

## ⏳ Ya construido, esperando que actives las claves

Estas funciones ya están en el código y desplegadas, pero apagadas hasta que configures las variables de entorno correspondientes en Railway/Vercel:

- **Monitoreo de errores (Sentry)** — código listo en backend (`sentry-sdk`) y frontend (`@sentry/react` + Error Boundary). Falta:
  1. Crear cuenta gratis en sentry.io con dapxco@gmail.com
  2. Crear 2 proyectos: uno Python/FastAPI, uno React
  3. Pasar los 2 DSN → configurar `SENTRY_DSN` (Railway) y `VITE_SENTRY_DSN` (Vercel)

- **Backup diario por correo** — endpoint `/backup/cron/enviar` ya exporta las 17 tablas completas a JSON comprimido. Falta:
  1. Crear cuenta gratis en resend.com con dapxco@gmail.com
  2. Pasar la API key → configurar `RESEND_API_KEY` (Railway)
  3. Programar el endpoint en cron-job.org (diario, header `X-Cron-Secret`)

- **Alerta semanal de uso/límites de plan** — endpoint `/metricas/cron/revisar-uso-semanal` ya cuenta usuarios y movimientos, y solo manda correo si algo se acerca al límite de un plan gratuito. Falta:
  1. Depende de la misma `RESEND_API_KEY` de arriba
  2. Programar el endpoint en cron-job.org (semanal, header `X-Cron-Secret`)

**Crons que YA deberían estar programados en cron-job.org** (revisar si faltan):
- `/push/cron/revisar-presupuestos` (diario)
- `/push/cron/aportes-automaticos` (diario)
- `/push/cron/premiar-presupuestos-mes` (mensual, último día)
- `/push/cron/resumen-semanal` (semanal)
- `/push/cron/recordar-recurrentes` (diario)
- `/backup/cron/enviar` (diario) — nuevo
- `/metricas/cron/revisar-uso-semanal` (semanal) — nuevo

---

## 🟠 Importante, no bloqueante para una beta con gente de confianza

- 🔲 **Revisión legal real**: Términos, Privacidad y Autorización de Datos ya están escritos (Ley 1581/2012) pero son un borrador. Antes de abrir a público desconocido, un abogado colombiano debe revisarlos — especialmente responsabilidad por categorización automática/proyecciones, y actualización con NIT cuando se constituya la empresa.
- 🔲 **Confirmar plan de Supabase**: hoy en Free, sin backups nativos (por eso se construyó el backup por correo como mitigación). Si el volumen de usuarios crece, pasar a Pro ($25/mes) da backups automáticos de verdad además de más storage.
- 🔲 **Dominio propio** (ej. cuadrame.com) en vez de depender de `vercel.app`/`railway.app` — más profesional, ~$12-15/año.

---

## 🟡 Pulido de producto (con margen para esperar)

- 🔲 **framer-motion está instalado pero sin usar** — hoy las animaciones son CSS puro (que funciona bien), pero si se quiere algo más elaborado (gestos, drag, animaciones de layout) ya está la librería disponible sin instalar nada nuevo.
- 🔲 **Presupuesto Pro reactivado con gating real**: hoy TODO es gratis a propósito (decisión tomada en esta sesión). Si se quiere monetizar más adelante, hay que decidir qué funciones quedan detrás del pago y aplicar el chequeo en el backend (el código de Stripe sigue ahí, solo desconectado de la UI).
- 🔲 **Condición de carrera en aportar_meta** (`metas.py`): dos aportes concurrentes a la misma meta el mismo día podrían generar un read-then-write no serializado. Riesgo bajo pero real; arreglarlo requiere locking a nivel de fila.
- 🔲 **Envelope budgeting**: hoy solo se puede "mover plata" entre presupuestos existentes. Podría faltar una vista consolidada de "sobres" tipo YNAB más visual.
- 🔲 **Code splitting del bundle**: el build avisa que el JS principal pasa los 500KB — no es urgente a esta escala de usuarios, pero eventualmente vale la pena separar rutas con `dynamic import()`.

---

## ✅ Completado en esta sesión (para contexto, no acción)

- Categorías 100% personalizables (crear, renombrar, ícono, ocultar) — antes estaban fijas en el código
- Diccionario de categorización automática expandido a ~280 patrones (bancarios + comercios CO)
- 5 bugs reales arreglados: aportes a metas ya cumplidas, rachas rotas por zona horaria, invitaciones duplicadas al compartir cuenta, alertas sin convertir moneda, reintentos sin backoff en tasas de cambio
- Selector de fecha y carrusel animado de cuentas en "Agregar movimiento"
- Carrusel rotativo de funciones a descubrir en Inicio (antes solo mostraba el aviso de Gmail)
- Animaciones consistentes en toda la app (entrada de pantallas, listas en cascada, modales tipo hoja, barras que "suben" al cargar)
- Identidad visual completa: mazo de cuentas con colores reales por banco, timeline, termómetro de presupuesto, mapa de calor de gastos, árbol financiero (reemplazo del "Ahorcado")
- Legal: Términos, Privacidad, Autorización de Datos + checkbox obligatorio en registro
- Onboarding: pantalla de bienvenida explicando las 3 funciones clave antes de crear la primera cuenta
- Conciliación de extractos: categoría visible y editable antes de importar, aviso post-importación si algo quedó en "Otros"
- Registro por voz/Siri (con parser propio de montos en español colombiano)
- Sentry + backup diario por correo + alerta semanal de uso (código listo, pendiente activar claves)

---

## Cómo retomar mañana

Decir algo como: *"sigamos con la hoja de ruta, empecemos por [sección]"* — por ejemplo "empecemos por lo de Sentry" o "revisemos el tema legal con el abogado". Este archivo vive en la raíz del proyecto (`HOJA_DE_RUTA.md`) y se puede actualizar a medida que se completen ítems.
