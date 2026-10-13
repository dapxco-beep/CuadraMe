# Propuesta de texto: consentimiento `lectura_correo` (B4) — BORRADOR, NO APLICADO

Estado: solo propuesta. Aplicarla obliga a subir `VERSION_TEXTOS` y a que **todos** los usuarios acepten de nuevo. Decide Daniel (y el abogado). Los plazos (30 y 365 días) deben coincidir con lo que se active en Railway (`RETENCION_*`) y con la sección 9 de la política.

## Texto propuesto (lenguaje llano, 112 palabras)

> **Leer tu correo para encontrar tus movimientos**
> CuadraMe lee tu Gmail, solo para lectura, y busca avisos y extractos de bancos: por remitente y palabras clave, y también los que no tengan etiqueta. Guardamos remitente, asunto, vista previa y monto de los avisos para ofrecértelos como movimientos. Si no son un movimiento, borramos ese contenido a los 30 días; si ya son un movimiento, a los 365 días. De los extractos guardamos banco, periodo y nombre del archivo, no el PDF. No usamos tu correo con inteligencia artificial externa, no lo vendemos, no lo usamos para publicidad y ninguna persona lo lee. Puedes retirar el permiso cuando quieras en Perfil, «Desconectar Gmail», y dejamos de leer de inmediato.

## Archivos que habría que tocar al aprobarlo
1. `pwa/src/lib/consentimientos.js`: texto de la finalidad `lectura_correo` y subir `VERSION_TEXTOS`.
2. `backend/app/routers/consentimientos.py`: `VERSION_TEXTOS` debe coincidir con el de la PWA (y los tests de backend que fijen la versión).
3. Pantallas que muestran o piden el texto: `pwa/src/components/ConexionGmail.jsx`, `SeccionPrivacidad.jsx`, `ModalConsentimiento.jsx` (usa FINALIDADES) y `pwa/src/screens/AutorizacionTratamiento.jsx` (mencionar plazos). Tests: `pwa/src/test/privacidad_derechos.test.jsx` y `saldo_y_autorizacion.test.jsx`.
4. Fuentes de los textos legales (`docs/legal/POLITICA_DE_PRIVACIDAD.md`, `TERMINOS_Y_CONDICIONES.md`) y regenerar las páginas estáticas con `npm run legales` (en `pwa/`), revisando el diff de `pwa/public/` generado.
5. Pruebas de vitest que fijan el texto o la versión de consentimientos, y `docs/CHECKLIST_LANZAMIENTO.md` / `docs/salida/GOOGLE_VERIFICACION.md` (marcar B3 y B4 resueltas).
6. Variables en Railway: `RETENCION_CORREOS_IGNORADOS_DIAS=30`, `RETENCION_CORREOS_PROCESADOS_DIAS=365` y crear el cron `/correos/cron/purgar-retencion`.
