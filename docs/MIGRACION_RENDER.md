# Pasar el servidor de Railway a Render (plan gratis)

Cuenta: **dapxco@gmail.com**. La base de datos y el login siguen en Supabase: solo se mueve el servidor.

## Qué hay listo
- `render.yaml` (raíz): describe el servicio. Usa `backend/Dockerfile`, región Virginia, plan gratis, `/health` como chequeo.
- `backend/cronjobs/repuntar_crons.py`: pasa las 19 tareas de cron-job.org a la URL nueva y crea «mantener despierto» (cada 10 min).
- `pwa/vercel.json`: la política de seguridad ya deja conectar con `*.onrender.com` y `api.cuadrame.dapx.shop`.

## Por qué un dominio propio (`api.cuadrame.dapx.shop`)
Así la app, las tareas y el Android no dependen de quién aloja el servidor: si algún día se cambia de proveedor,
solo se cambia el DNS. El dominio está en Hostinger (cuenta dapx).

## Orden del traslado (cada paso es reversible hasta el 7)
1. Subir la rama `infra/render` a GitHub (la hace Daniel; el repo `dapxco-beep/CuadraMe`).
2. En Render (cuenta dapx): New → Blueprint → elegir el repo y la rama `infra/render`. Crea `cuadrame-api`.
3. Cargar las variables secretas (nombres en `render.yaml`) con los mismos valores de Railway.
4. Probar `https://cuadrame-api.onrender.com/health` → `{"ok": true}`. Railway sigue sirviendo a todos.
5. En Render → Settings → Custom Domains: agregar `api.cuadrame.dapx.shop`; en Hostinger crear el CNAME que Render indique.
6. Probar `https://api.cuadrame.dapx.shop/health` y un inicio de sesión real contra esa URL.
7. **Corte:** en Vercel poner `VITE_API_URL=https://api.cuadrame.dapx.shop` y desplegar; correr
   `repuntar_crons.py --aplicar`; actualizar el webhook de Stripe y la URL de redirección de Google si apuntan a Railway.
8. Dejar Railway 2–3 días como respaldo y luego apagarlo.

## Lo que NO se mueve solo
- **App Android:** trae la URL de Railway dentro (`Config.kt`). Hay que recompilarla con la nueva (o cambiarla en sus ajustes si los tiene).
- **Atajos viejos** (Tasker/Scriptable) que usan la URL de Railway: pedir que la cambien.
- Estado en memoria del proceso (contadores de errores 5xx de 24 h) se reinicia con cada reposo del servicio; es solo informativo.

## Límites del plan gratis
- Se duerme tras 15 min sin visitas y tarda ~50 s en despertar. La tarea «mantener despierto» evita casi todos los reposos.
- 750 h/mes = justo un servicio encendido todo el mes.
- Si Render prohíbe ese truco o cambia las reglas: plan B Google Cloud Run (pide tarjeta, tiene capa gratis).
- Con clientes de pago, pasar a un plan de pago.
