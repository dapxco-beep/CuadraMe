# Lo que debe decidir Daniel antes de publicar los textos legales

> Los borradores de esta carpeta están marcados «BORRADOR PARA REVISIÓN DE ABOGADO». Nada se publica como definitivo sin esa revisión.

## Datos que solo tú puedes dar
1. **Razón social / responsable.** Hoy los textos dicen «DAPX, persona natural en proceso de formalización». Define quién es el responsable del tratamiento (nombre o razón social, NIT o C.C., domicilio).
2. **Correo de contacto para Habeas Data y soporte.** Hoy es `dapxco@gmail.com` (también está en `SOPORTE_EMAIL`, `BACKUP_EMAIL` y `VAPID_SUBJECT`). Para clientes conviene un correo de dominio propio.
3. **Dominio.** La app vive en un subdominio de Vercel. Al tener dominio: actualizar `canonical` y `og:*` en `pwa/public/bienvenida.html`, `PWA_URL`, `API_BASE_URL` y los orígenes de CORS, y el remitente de Resend.
4. **Remitente de Resend con dominio verificado** (`RESEND_FROM`). Sin eso el resumen semanal no llega a clientes.
5. **¿Habrá cobro?** El código tiene Stripe (pago único), pero los textos dicen «gratis». Decide si se cobra y cuándo.
6. **Publicar la versión 1.2 de los textos.** Cambia lo que se autoriza (se declara el correo de copias de seguridad, Resend y Sentry, y que Gmail también busca notificaciones y extractos sin etiqueta). Publicarla obliga a subir `VERSION_TEXTOS` (`pwa/src/lib/consentimientos.js` y `backend/app/routers/consentimientos.py`) y a pedir de nuevo la autorización a todos los usuarios. Lo hice **sin** subir la versión para no cambiar el comportamiento en producción; es decisión tuya.

## Para el abogado
- Registro en el RNBD de la SIC (¿aplica por tamaño?).
- Transmisión/transferencia internacional: dónde están realmente Supabase, Railway, Vercel, OpenRouter, Resend y Sentry; contratos de encargado.
- Copias de seguridad que contienen datos de todos los usuarios y se envían por correo: retención y qué se responde cuando un usuario pide supresión.
- Permiso `gmail.readonly` frente a la política de datos de Google (uso limitado) y la verificación OAuth.
- Cláusula de responsabilidad vs. Estatuto del Consumidor (Ley 1480); jurisdicción; PQR.
- Estimaciones fiscales (4x1000, «posiblemente deducible») y aviso de que no son asesoría.

## Desalineaciones que encontré en las pantallas de la app (ya corregidas en el código)
- La política decía que solo se leen los correos con la etiqueta elegida; el código también busca notificaciones y extractos por remitente y palabras clave. Corregido en Política y Autorización.
- No se mencionaban Resend (resumen semanal, cierre de mes y backup), Sentry ni los servicios de push. Añadidos.
- No se declaraba que cada día se envía por correo una copia de la base de datos al administrador. Añadido (retención por validar).
- Se hablaba de eliminar la cuenta «escribiendo al correo», pero la app ya permite hacerlo en Perfil → Privacidad y datos. Corregido.
- Se añadió el resumen semanal por correo (opt-in) y la nota de transferencias internacionales.
