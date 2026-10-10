# Resend: verificar el dominio para enviar correos a clientes

**Objetivo:** que el resumen semanal, los avisos y los correos de CuadraMe lleguen a cualquier persona (hoy `RESEND_FROM=CuadraMe <backup@resend.dev>`, que **solo entrega al dueño de la cuenta de Resend**).
**Tiempo estimado:** 20 min de clics + de 10 min a 48 h de propagación DNS.
**Quién:** Daniel (Resend, Hostinger, Railway). Claude no toca DNS ni cuentas.

Qué dejaría de funcionar sin esto: resumen semanal a clientes, avisos al administrador si `ADMIN_EMAIL` no es el dueño de Resend, y cierre de mes por correo.

---

## 1. Añadir el dominio en Resend

1. Entra a `resend.com` → **Domains** → **Add Domain**.
2. **Name:** `cuadrame.dapx.shop` (subdominio dedicado: no choca con cualquier correo que tengas en `dapx.shop`).
3. **Region:** elige `São Paulo (sa-east-1)` si aparece (más cerca de Colombia); si no, `us-east-1`. No se cambia después.
4. Pulsa **Add**. Resend te muestra una tabla de registros DNS: **déjala abierta**, la vas a copiar.

## 2. Registros DNS que debes crear (genéricos)

Resend te dará exactamente estos tipos; **copia los valores de su pantalla**, no los de este documento (las claves DKIM son únicas):

| Tipo | Nombre / host (relativo a tu dominio) | Valor | Para qué |
|---|---|---|---|
| TXT | `resend._domainkey.cuadrame` | `p=MIGfMA0G...` (larga, la da Resend) | **DKIM**: firma que prueba que el correo es tuyo |
| MX | `send.cuadrame` | `feedback-smtp.<región>.amazonses.com` (prioridad 10) | Retorno de rebotes (el «Return-Path») |
| TXT | `send.cuadrame` | `v=spf1 include:amazonses.com ~all` | **SPF**: quién puede enviar por ti |
| TXT (tú lo añades) | `_dmarc.cuadrame` | `v=DMARC1; p=none; rua=mailto:dapxco@gmail.com` | **DMARC**: política y reportes |

Notas:
- Resend mostrará los nombres completos (`resend._domainkey.cuadrame.dapx.shop`). En Hostinger se escribe solo la parte relativa (sin `.dapx.shop`).
- DMARC empieza en `p=none` (solo observar). Cuando lleves 2 semanas sin problemas, sube a `p=quarantine`.
- **No borres ni cambies** otros registros MX/SPF que ya existan en `dapx.shop`: estos van en el subdominio `cuadrame`/`send.cuadrame` y no los afectan.

## 3. Dónde pegarlos en Hostinger

1. `hpanel.hostinger.com` → **Dominios** → `dapx.shop` → **Administrar**.
2. Menú izquierdo: **DNS / Servidores de nombres** → pestaña **Registros DNS** (Zona DNS).
3. Para cada fila de la tabla: elige **Tipo**, escribe **Nombre**, pega el **Valor**, TTL por defecto (14400 o 3600) → **Añadir registro**.
4. **Antes de empezar, comprueba** en esa misma pantalla que los *nameservers* del dominio sean los de Hostinger (`ns1.dns-parking.com` o similares). Si apuntan a otro servicio (Cloudflare, Vercel), los registros se crean **ahí**, no en Hostinger.
5. Vuelve a Resend → el dominio → **Verify DNS Records**. Estado esperado: `Verified` en DKIM, SPF y MX.

## 4. Cambiar la variable en Railway

1. `railway.app` → proyecto CuadraMe → servicio **backend** → pestaña **Variables**.
2. Edita (o crea) `RESEND_FROM` con este valor exacto, incluyendo el nombre:

```
CuadraMe <hola@cuadrame.dapx.shop>
```

3. Guarda. Railway vuelve a desplegar solo (~1 min). El dominio de la dirección **debe ser** el verificado (`cuadrame.dapx.shop`); el usuario antes de la `@` puede ser cualquiera (`hola`, `avisos`, `no-responder`).
4. Revisa que `RESEND_API_KEY` exista y sea de **esa misma cuenta** de Resend. Si rotaste la clave (ver `CHECKLIST_LANZAMIENTO.md`), pon aquí la nueva.
5. Variables relacionadas: `ADMIN_EMAIL` (quien recibe los avisos) y `BACKUP_EMAIL`.

## 5. Probar que llega

**A. Aviso de prueba (más fácil, sin comandos)**
1. Abre la app con la cuenta que coincide con `ADMIN_EMAIL`.
2. Más → **Salud del negocio** → «Qué te avisa y cuándo» → botón **Enviar aviso de prueba**.
3. Respuesta esperada: `correo: true`. Si falla, el panel muestra el motivo (`correo_error`). Es el endpoint `POST /avisos/probar` (solo el administrador; no usa el secreto de cron).
4. Revisa la bandeja **y spam**. Abre el correo → «Mostrar original» y confirma `SPF: PASS`, `DKIM: PASS`, `DMARC: PASS`.

**B. Resumen semanal**
1. En la app, con una cuenta de prueba: Perfil → «Resumen semanal por correo» → activar (con el correo donde lo quieres).
2. Registra un gasto en los últimos 7 días (sin datos no se envía).
3. Ejecuta el cron a mano (en PowerShell, con el secreto en una variable de entorno de tu equipo, no pegado en chat):

```
curl.exe -X POST https://backend-production-aeab.up.railway.app/resumen/cron/semanal -H "X-Cron-Secret: $env:CRON_SECRET"
```

4. Respuesta esperada: `{"ok": true, "enviados": 1, ...}`. Repetirlo da `ya_enviados: 1` (no duplica). Llega «Tu semana en CuadraMe».
5. Para volverlo a probar la misma semana hay que borrar la marca; no lo hagas en producción sin consultar.

**C. Probar con otro proveedor:** envía a una cuenta Gmail y a una Outlook. Que lleguen a **bandeja de entrada**, no a spam.

## 6. Si no verifica

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Sigue en `Pending` tras 1 h | Propagación o nombre mal escrito | Espera hasta 24–48 h; compara cada nombre y valor con Resend; en Hostinger sin `.dapx.shop` al final |
| DKIM `Failed` | Valor truncado o con comillas/espacios | Vuelve a copiar entero con el botón copiar de Resend; sin comillas ni saltos de línea |
| SPF/MX `Failed` | Registro puesto en el host equivocado, o ya existe un MX en ese nombre | El host es `send.cuadrame`, no `cuadrame`; borra duplicados |
| Todo bien pero 403 al enviar | `RESEND_FROM` usa otro dominio | Alinéalo con el verificado |
| Llega a spam | DMARC ausente, dominio nuevo, remitente sin nombre | Añade DMARC, deja de enviar pruebas repetidas, usa `CuadraMe <...>` |
| Resend dice «domain already registered» | El dominio está en otra cuenta de Resend | Entra con la otra cuenta o elimínalo allí |
| Nameservers no son los de Hostinger | El DNS lo gestiona otro servicio | Pon los registros en ese servicio; ver el pendiente de DNS de dapx.shop |

Si tras 48 h sigue sin verificar: copia el estado de cada fila de Resend y el pantallazo de la zona DNS y consúltalo con Claude (sin pegar claves).

## 7. Después

- Límites del plan gratuito de Resend que el monitor ya vigila: 100 correos/día y 3000/mes (`RESEND_LIMITE_DIA`, `RESEND_LIMITE_MES`). Con más de ~100 usuarios activos con resumen semanal, sube de plan (ver `PRECIOS_Y_PLANES.md`).
- Actualiza `docs/SALIDA_A_PRODUCCION.md` §1 y marca el ítem en `CHECKLIST_LANZAMIENTO.md`.
