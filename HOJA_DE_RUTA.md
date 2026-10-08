# CuadraMe — Hoja de ruta

Última actualización: 2026-10-03. Estado: backend y frontend desplegados y estables en producción (Railway + Vercel). Todo lo marcado ✅ ya está en producción; lo marcado ⏳ necesita algo de ti antes de activarse; lo marcado 🔲 es trabajo pendiente de construir.

---

## 🆕 CuadraMe educativo: consejos, «Aprende» y débito vs crédito (pendiente de tu aprobación)

- **Consejos personalizados sin IA externa:** `GET /consejos` (`backend/app/consejos.py`, reglas puras y probadas con casos sintéticos). Cada consejo trae `id` estable (con el periodo), prioridad, título, texto llano, cifra del usuario y acción a una pantalla; el cuerpo lleva el aviso «Orientación educativa, no es asesoría financiera». Reglas: categoría que sube >30 %, gastos hormiga, pago solo del mínimo, utilización de cupo >30 %, fondo de emergencia (3–6 meses de SUS gastos), ahorro sin meta, sin presupuesto, deudas (avalancha vs bola de nieve / deuda cara), suscripciones detectadas, ingreso sin repartir (50/30/20), movimientos sin categoría, débito vs crédito y fechas de corte/pago. Agregar una regla = una función en `REGLAS`. Sin cambios de base de datos.
- **PWA:** tarjeta «Consejo para ti» en Inicio (`ConsejoParaTi`, carrusel de hasta 3; lo descartado se guarda en el dispositivo por id), pantalla **Aprende** (`/aprende`, menú Más → Ajustes) con 11 microlecciones y glosario con buscador (todo el texto en `pwa/src/lib/aprende.js`), y `<Ayudita termino="cupo">` («¿qué es esto?») en Tarjetas, Cuentas y Presupuesto. Cuentas y detalle muestran «Débito / Ahorros» vs «Tarjeta de crédito» con lo que significa cada saldo, y al pagar una tarjeta (Agregar → Transferir, y en el detalle del movimiento) se avisa que no es un gasto nuevo.

---

## 🆕 Producto para salir a vender (2026-10-07) — pendiente de tu aprobación

- **Resumen semanal por correo (opt-in, apagado por defecto):** `GET/PUT /resumen/preferencias` (interruptor en Perfil → «Correo») y cron `POST /resumen/cron/semanal` (header `X-Cron-Secret`). Idempotente por usuario y semana ISO (`marcas_cron`, clave `resumen_correo_semanal`), un fallo no frena a los demás (la marca se libera para reintentar), sin gastos ni avisos no manda nada. **Cron NO creado**: domingo 18:00 hora Colombia. Columnas nuevas `ajustes_usuario.resumen_correo` y `.email_resumen` (las agrega `main.py`; SQL suelto en `backend/supabase/migraciones/resumen_semanal.sql`, NO ejecutado). Ojo: `RESEND_FROM` por defecto es el remitente de pruebas de Resend y solo escribe al dueño de la cuenta; para clientes hace falta dominio verificado.
- **Recordatorios en Inicio:** `GET /recordatorios` (pago de tarjeta en ≤5 días, presupuesto ≥80 %, extractos de Gmail por revisar). Tarjetas descartables; lo descartado se guarda en el dispositivo con una clave que cambia cuando hay una situación nueva.
- **Página pública** `pwa/public/bienvenida.html` (sin login, sin JS, con Open Graph). El `canonical`/`og:*` apuntan al dominio actual de Vercel: cambiarlos cuando haya dominio. De paso, `sw.js` ya no guarda en el caché del shell otras páginas que no sean `/`.
- **Legal:** borradores en `docs/legal/` (con lo que debes decidir en `PENDIENTES_DANIEL.md`) y pantallas de la app alineadas con el código (Gmail también busca sin etiqueta, Resend, Sentry, copias de seguridad, transferencia internacional). La versión de textos sigue en 1.1 a propósito.
- **Checklist final:** `docs/SALIDA_A_PRODUCCION.md`.

---

## 🆕 Traslados con dirección y saldo correcto (2026-10-06) — pendiente de tu aprobación

**Defecto corregido:** los renglones de transferencia de un extracto (Nequi "Transfer", Nu "Transferencia"…) se guardaban como `transfer` sin dirección: no movían el saldo y no se sabía si entraron o salieron. Regla nueva: **todo movimiento tiene dirección (income/expense) y siempre mueve el saldo**; que sea traslado propio (neutral) o gasto/ingreso real lo decide `contabilidad.tipos_efectivos`, no el tipo.

- **Lectores** (`conciliacion.py`, `importador_tabular.py`, prompt de IA en `pdf_extract.py`): nunca emiten `transfer`; la dirección sale del signo o de las columnas débito/crédito. Si la contraparte parece el titular dejan `pista: posible_traslado_propio`, que al importar queda en `notas`. Los extractos viejos guardados con `transfer` se resuelven por la descripción al importar; si no se puede, se omiten (`sin_direccion` en la respuesta) en vez de adivinar. Los pares TRF creados en la app siguen igual (`transfer` + `:out`/`:in` en notas, y `contabilidad.delta_saldo` es ahora la regla única de cuánto mueve el saldo).
- **Informes** (`contabilidad.tipos_efectivos`): son neutrales (a) las patas TRF, (b) los pagos de tarjeta y (c) los **pares detectados**: egreso en una cuenta + ingreso del mismo monto y moneda en otra cuenta del usuario, a ≤ 2 días, con descripción de traslado ("a tu cuenta", Bre-B, "Para…", Nequi…) o la pista; emparejados 1:1 con el mejor candidato (más pistas, luego fecha más cercana). Sin pareja = gasto/ingreso real (transferencia a un tercero). Marca `no_es_traslado` (la deja el usuario) lo excluye siempre.
- **PWA:** fila y detalle muestran "Traslado ↔" / "Posible traslado ↔" con el signo y color de su dirección; el detalle permite "Marcar como traslado entre mis cuentas", "Es un gasto/ingreso real" y "Vincular con su contraparte" (marca ambas patas con la categoría neutral `Transferencia`).
- **Datos existentes (NO ejecutado):** `backend/supabase/migraciones/retipar_transfers.sql`. Lectura contra producción el 2026-10-06: hay 189 `transfer` importados en 2 cuentas (cuenta A: 101 = 92 salen + 9 entran; cuenta B, la de Nequi: 88 = 3 salen + 85 entran, casi todos "Recibí por Bre-B"). **0 no deducibles** con las reglas finales (sin la regla "Recibí…" eran 85). En producción todos los `transfer` vienen de extractos (19 `conciliacion_auto` + 170 `conciliacion_extracto`); no hay pares TRF internos (esos nunca se tocan). Cada una de las dos cuentas tiene 1 `ajuste_saldo` (2026-07-31).
- **Orden recomendado:** (1) desplegar el backend nuevo (así los extractos nuevos ya entran con dirección y nadie crea más `transfer`); (2) respaldo de la base; (3) correr las dos consultas de lectura del encabezado del `.sql` y confirmar los conteos; (4) ejecutar el `.sql` (una transacción, aborta si algo no cuadra, idempotente); (5) revisar la verificación del final del archivo y los informes del mes.
- **Qué hace con el saldo:** en cuentas **sin** ajuste de saldo suma el efecto que faltaba; en cuentas **con** `ajuste_saldo` (las dos de hoy) el saldo NO cambia (ya era el real) y el último ajuste absorbe la diferencia. Previsto: cuenta A, entradas 6.350.000 − salidas 6.575.000 = −225.000, así que su ajuste sube de 267.726,23 a 492.726,23; cuenta Nequi, +5.489.000 − 1.280.000 = +4.209.000, así que su ajuste baja de 4.369.219,81 a 160.219,81.
- **¿Dejar o quitar los "ajuste de saldo"?** Dejarlos: son el saldo inicial/lo que el extracto no explica y siguen funcionando (neutrales en informes). Ya no hacen falta cuando el libro iguala al extracto: la consulta de verificación (saldo vs suma de movimientos) da diferencia ≈ 0 sin contar el ajuste, o el ajuste queda en 0 (la migración lo borra sola). Si tras la migración el ajuste de la cuenta Nequi sigue en ~160.000, es plata que ningún extracto explica: revísalo antes de borrarlo.

## 🆕 Centro «Traer movimientos» (pendiente de tu aprobación)

- **Una sola pantalla** (`/sincronizacion`, `pwa/src/screens/Sincronizacion.jsx`) reemplaza a Correos, Conciliación, Importar archivo y el tablero de Conexiones. Arriba: estado y «Sincronizar todo»; luego tres bloques plegables con contador: **Desde tu correo** (Gmail, notificaciones por revisar, extractos), **Subir archivos** (zona única PDF/Excel/CSV, varios a la vez, cola con progreso, revisión consolidada por cuenta y archivo con «Seleccionar todo lo que falta», «Recordar», avisos de «periodo ya conciliado» y de líneas que no se pudieron leer) y **Por revisar** (por confirmar, por categorizar, bancos sin cuenta, cuadrícula cuenta × mes). Con cero pendientes cada bloque queda en «Todo al día». El total «por resolver» es el mismo de Inicio (`tareas.length` de `GET /sincronizacion/estado`).
- **Rutas viejas redirigen** (`RedirigirAlCentro`): `/correos`, `/conciliacion`, `/importar`, `/conexiones` abren el bloque que corresponde (conservan `?gmail=…`, `historialId`, cuenta y mes). Se borraron `Correos.jsx` y `Conciliacion.jsx`; `ImportarArchivo` queda solo para elegir columnas a mano (hoja dentro de «Subir archivos»); `Conexiones` es una hoja desde el botón «Conexiones».
- **Correos aprobados con nombre real:** `extraer_comercio` lee el concepto del asunto/cuerpo («Compra en Juan Valdez», «Envío a Ana», «Pago de servicios»); si un banco no dice más, «Gasto/Ingreso/Traslado sin detalle» (nunca el remitente). La descripción del movimiento ya no lleva « (correo)» (el origen sigue en `fuente="email"`). `POST /correos/{id}/aprobar` responde 400 si el monto es ≤ 0 y acepta `monto` opcional; `GET /correos/pendientes` marca `falta_monto`. Los correos sin monto siguen sin ofrecerse (el sync los ignora, a propósito); la tarjeta de la PWA pide el monto si alguna llega así.
- **API (solo campos nuevos):** `ProcesarExtractoResponse.cuenta_id` (al reabrir una revisión), `CorreoGastoOut.falta_monto`, `AprobarCorreoRequest.monto`.
- ⏳ El menú (BottomNav/BarraLateral) aún lista Correos y Conciliar extracto por separado: lo ajusta el agente de menú; mientras tanto esos enlaces redirigen al centro.

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

## 🆕 Tarjetas de crédito: captura, extracto, cuotas y lectura del extracto (pendiente de tu aprobación)

- **Crear tarjeta:** pide cupo total, «¿Cuánto debes hoy?» (se guarda como saldo negativo), día de corte, día de pago y tasa. Antes un valor positivo se leía como saldo a favor.
- **Pago para no pagar intereses = deuda al último corte** (`backend/app/tarjetas.py` `estado_extracto`): total del extracto, pagado desde el corte, falta, compras después del corte. El aviso push usa lo que FALTA y no avisa si ya está pagado.
- **Compras a cuotas:** vista de compromiso (no cambia saldos). `GET/POST/PUT/DELETE /cuotas-tarjeta`. «Comprometido en cuotas este mes» se informa en `/presupuestos/en-mi-bolsillo` y `/reportes/flujo-caja-futuro`; solo resta del disponible/flujo con `?incluir_cuotas=true` (la deuda de la tarjeta ya está restada en el saldo).
- **Leer el extracto:** `backend/app/extracto_tarjeta.py` propone (nunca aplica solo) actualizar cupo, corte, pago y tasa; en Conciliación aparece «Tu extracto dice… ¿Actualizar tu tarjeta?». Probado solo con textos inventados, no con extractos reales.
- ⏳ **SQL sin ejecutar:** `backend/supabase/migraciones/cuotas_tarjeta.sql` (tablas `cuotas_tarjeta` y `extractos_tarjeta` + RLS, idempotente). El arranque las crea y activa RLS en Postgres.
- ⏳ **Pendiente de montar:** el componente `PropuestaTarjeta` en `Sincronizacion.jsx`/`Correos.jsx` (otro frente de trabajo); la respuesta de `/conciliacion/procesar` ya trae `propuesta_tarjeta`.

---

## 🆕 Registro con Apple Wallet, bandeja "¿son tuyos?" y recordatorio nocturno (pendiente de tu aprobación)

- **Cómo funciona:** el disparador personal «Transacción» de Atajos de iOS hace POST a `/movimientos/rapido` (header `X-Api-Key`) con comercio, monto, tarjeta, fecha y moneda. El movimiento se crea al instante (los saldos quedan bien) pero marcado «por confirmar» (`cat_confirmada=false`, `cat_origen='wallet'`), así sale en «Por revisar» y en la bandeja. Acepta montos colombianos (`45.000,00`), mapea la tarjeta a la cuenta por **alias de tarjeta** (editable en cada cuenta) o por nombre, y ignora duplicados (mismo comercio+monto+cuenta en ±2 min, responde 200 con el existente).
- **PWA:** hoja «Detectamos N movimientos: ¿son tuyos?» al abrir y al volver a primer plano (no repite en 1 h salvo nuevos); pregunta «¿Hiciste algún movimiento?» en Inicio; asistente «Conectar tu celular» (`/conectar-dispositivo`) con guía iPhone/Android y botón de prueba. Scriptable ya no es parte de la guía (`scriptable_registro_rapido.js` queda como alternativa legada).
- ✅ **Atajos por enlace de iCloud:** el cliente ya no arma nada; instala `ATAJO_ICLOUD_URL` (pagos) y `ATAJO_CIERRE_URL` (cierre) desde `ConectarDispositivo.jsx` y pega su clave cuando iOS la pida. Armarlos a mano queda como «Avanzado» plegado. Ver `docs/ATAJO_CUADRAME.md`.
- ⏳ **SQL sin ejecutar:** `backend/supabase/migraciones/wallet_recordatorio.sql` (3 columnas, idempotente: `cuentas.alias_tarjeta`, `perfiles.recordatorio_diario`, `perfiles.ultimo_recordatorio`). `main.py` también las agrega al arrancar en Postgres.
- ⏳ **Cron del recordatorio nocturno (NO creado):** `POST /push/cron/recordar-registro` con header `X-Cron-Secret`. Programarlo en cron-job.org **1 vez al día a las 20:00 hora Colombia** (mismo método de `backend/cronjobs/crear_crons.py`). Solo avisa a quien activó «Recordatorio diario» en Perfil y hoy no registró nada; antes de las 8 p. m. (hora Colombia) no hace nada y no repite el mismo día, así que un horario mal puesto no genera spam. `?forzar=true` salta la comprobación de hora (para probar).

---

## 🆕 Importar Excel/CSV, regla contable, Impuestos y Cierre de mes (pendiente de tu aprobación)

- ⏳ **SQL sin ejecutar:** `backend/supabase/migraciones/impuestos_cierre_mes.sql` (3 tablas + RLS, idempotente). Correrlo en Supabase antes de desplegar; si no, el backend las crea al arrancar pero sin RLS. Importar CSV/Excel no necesita SQL.
- **Regla contable:** el pago de una tarjeta y los traslados entre cuentas propias no cuentan como gasto ni ingreso (`backend/app/contabilidad.py`; lo usan reportes, presupuestos, insights, salud, wrapped, push, exportar y cierre). Los saldos no cambian.
- **Importar:** Movimientos/Conciliación/Perfil -> "Importar Excel o CSV" (`/importar`). `.xls` antiguo requiere `xlrd` (agregado a requirements; sin él se pide guardar como .xlsx).
- **Impuestos:** `/impuestos` (4x1000 estimado, cuenta exenta, posibles deducibles con nota de soporte, Excel y PDF por impresión). UVT por año en `app/impuestos.py`: actualizar cada diciembre.
- ⏳ **Cron de cierre de mes (NO creado):** `POST /cierre-mes/cron/cerrar-mes` con header `X-Cron-Secret`. Programarlo en cron-job.org **1 vez al día** (p. ej. 07:00 hora Colombia, mismo método de `backend/cronjobs/crear_crons.py`); solo actúa sobre el mes ya terminado y es idempotente por usuario/mes (no repite informes, push ni correos). Parámetro opcional `?mes=AAAA-MM` para regenerar. El correo (Resend) solo se envía a quien lo active en la pantalla "Cierre de mes".
- **Legal:** Términos, Privacidad y Autorización actualizados (v1.1, 3-oct-2026) y siguen marcados como borrador pendiente de abogado colombiano.

---

## 🆕 Módulo Patrimonio e inversiones (pendiente de tu aprobación)

- ⏳ **SQL sin ejecutar:** `backend/supabase/migraciones/patrimonio.sql` (4 tablas + RLS, idempotente). Córrelo en Supabase ANTES de desplegar: si no, el backend las crea solo al arrancar (`create_all`) pero sin RLS.
- ⏳ **Cron opcional (no creado):** `POST /patrimonio/cron/snapshot-mensual` con header `X-Cron-Secret`, 1 vez al día, guarda la foto mensual de todos los usuarios. Sin él la serie igual se llena sola cuando alguien abre la pestaña Patrimonio.
- 🔲 **Precios automáticos:** interfaz lista en `backend/app/precios.py` (registrar un proveedor y poner su nombre en `fuente_precio`); hoy los precios son manuales.
- Cambio de navegación: la barra inferior ahora es Inicio · Presupuesto · (+) · Patrimonio · Perfil; "Movimientos" pasó a Perfil ("Todos mis movimientos") y sigue en "Ver todos" de Inicio.

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

**Límites de uso en memoria — Railway debe quedarse en 1 réplica.** El contador de `backend/app/limites.py` (IA, PDF, Gmail, API key y el tope de 30 intentos fallidos de API key por IP cada 10 min) vive en la memoria de cada proceso. Con 2 o más réplicas cada una cuenta aparte (el límite real se multiplica) y se reinicia en cada despliegue. Mientras no haya un almacén compartido (Redis), no escalar a más de 1 réplica.

**Crons que YA deberían estar programados en cron-job.org** (revisar si faltan). Todos van por `POST` con header `X-Cron-Secret`, devuelven `{ok, procesados, fallidos, ...}`, aíslan los fallos por usuario (`app/crons.py` `Corrida`) y son idempotentes (ejecutarlos dos veces no duplica nada). Horarios en hora Colombia:

| Endpoint | Horario recomendado | Idempotencia |
|---|---|---|
| `/push/cron/revisar-presupuestos` | 1 vez al día, 08:00 | marca por presupuesto y periodo |
| `/push/cron/aportes-automaticos` | 1 vez al día, 06:00 | `ultimo_aporte_automatico` + bloqueo de fila; si el cron falla un día, el siguiente recupera (dispara si ya llegó el día del aporte y no se aportó este mes) |
| `/push/cron/premiar-presupuestos-mes` | 1 vez al día, 21:00 (solo actúa el último día del mes) | vida única por mes |
| `/push/cron/resumen-semanal` | 1 vez por semana, domingo 19:00 | marca `resumen_semanal` por usuario y semana ISO (tabla `marcas_cron`) |
| `/push/cron/recordar-recurrentes` | 1 vez al día, 08:30 (también avisa tarjetas) | una vez por ocurrencia (ventana vencimiento − `alerta_dias_antes`) |
| `/push/cron/recordar-registro` | 1 vez al día, 20:00 | `perfiles.ultimo_recordatorio` |
| `/backup/cron/enviar` | 1 vez al día, 03:00 | marca `backup_diario` por día; si ya se envió responde `enviado=false` |
| `/metricas/cron/revisar-uso-semanal` | 1 vez por semana, lunes 08:00 | solo manda correo si hay alerta |
| `/cierre-mes/cron/cerrar-mes` | 1 vez al día, 07:00 | una fila por usuario y mes |
| `/patrimonio/cron/snapshot-mensual` | 1 vez al día (opcional) | sobrescribe la foto del mes |
| `/correos/cron/sincronizar` ⏳ (NO creado) | **cada 3 horas: `0 */3 * * *`, hora Colombia** | cursor por usuario (`sync_gmail`): sin correos nuevos no cambia nada ni avisa |

**Sincronización periódica de Gmail (`POST /correos/cron/sincronizar`, header `X-Cron-Secret`):** para cada usuario con Gmail conectado Y autorización vigente `lectura_correo` corre UN lote incremental de la misma sincronización del botón (`_lote_de_sincronizacion` en `routers/correos.py`). Presupuesto de ~45 s por llamada (`PRESUPUESTO_CRON_SEGUNDOS`): al agotarse corta y la siguiente ejecución sigue desde el cursor (va primero quien lleva más tiempo sin sincronizar). Un fallo de un usuario no detiene a los demás; si Google revoca el acceso (`RefreshError`) se desconecta Gmail de ese usuario. Responde `{ok, procesados, fallidos, nuevos, avisados, sin_consentimiento, desconectados, pendientes_por_tiempo}`. Si el lote encontró movimientos o extractos nuevos manda UN push resumen («Encontré 3 movimientos nuevos en tu correo») solo a quien tenga push activo. Crearlo en cron-job.org lo hace el dueño después del despliegue (no hay SQL ni variables nuevas).

**Extractos (revisión E2E de 2026-10-06):**
- **No es un extracto → se rechaza.** `/conciliacion/procesar` responde `ok:false, parece_extracto:false, motivo_rechazo` («Este archivo no parece un extracto bancario») cuando el banco no se reconoce y el texto no tiene señales de extracto + una tabla coherente (≥3 líneas con fecha válida, monto y descripción, rango ≤15 meses); tampoco se manda a la IA. La PWA ya lo muestra como error de ese archivo (usa `ok`/`error`). Bancos reconocidos no se cuestionan. El lector genérico ahora lee por renglón y respeta el signo `-` (antes todo salía como ingreso).
- **Procesar ya NO importa nada.** Antes el backend auto-importaba lo que categorizaba con certeza y «Cancelar» no lo deshacía. Ahora procesar solo lee y propone (cada línea trae `categoria_sugerida` y `razon_categoria`); se importa al confirmar. La auto-importación quedó como ajuste opcional **apagado por defecto** («importar solo lo que reconozco con certeza»): `GET/PUT /perfil/autoimportar-extractos {activo}` (usa el umbral `confianza-autoimport`). Con el ajuste activo los movimientos entran marcados `auto:true` + `movimiento_id` y se deshacen con `POST /conciliacion/historial/{id}/deshacer-auto` (revierte saldo; respeta los que el usuario ya confirmó). El resumen suma: `ya_registrados + faltantes + auto_importados = total_movimientos`. ⏳ **SQL sin ejecutar:** `backend/supabase/migraciones/autoimportar_extractos.sql` (columna `perfiles.autoimportar_extractos`, idempotente; `main.py` también la agrega al arrancar). ⏳ PWA: mostrar el interruptor en Perfil y el botón «Deshacer» cuando `auto_importados > 0` (campos nuevos, ningún nombre existente cambió).
- **Nequi:** lector por registro (líneas partidas en varios renglones, `$-8,200.00` / `-$8.200` / `($8,200)`, miles con coma o punto, movimientos consecutivos idénticos). Lo que parece movimiento y no se puede leer cuenta en `descartados` (aviso visible) y también si `saldo anterior + abonos − cargos ≠ saldo actual`.
- **`GET /cierre-mes/{mes}`:** sigue devolviendo 404 si no hay cierre (la PWA actual lo usa para mostrar «Generar cierre»); con `?silencioso=true` devuelve 200 `{existe:false, mes}`. ⏳ PWA: llamar con `?silencioso=true` y tratar `existe===false` como «no hay cierre» para limpiar la consola.
- **`GET /sincronizacion/estado`:** los meses con movimientos importados por conciliación cuentan como `conciliado` (mismo criterio de `extractos_conciliados.FUENTES_CONCILIACION`) y acepta `?meses=6..24` (por defecto 6) y `?hasta=AAAA-MM`.

**Aportes automáticos a metas:** cada aporte crea un movimiento «Aporte a meta «X»» (`fuente='aporte_meta'`, categoría «Aporte a meta», `notas='META:<id>'`) que el saldo sí refleja pero que `contabilidad.tipos_efectivos` trata como neutro (ni gasto ni ingreso, igual que traslados y ajustes). Si la cuenta no tiene saldo suficiente no se aporta parcialmente: se avisa por push una sola vez al mes por meta y se reintenta cada día. El movimiento no se edita (400); borrarlo devuelve el dinero a la cuenta y lo descuenta de la meta. Tabla nueva `marcas_cron` (la crea `create_all`; SQL opcional en `backend/supabase/migraciones/marcas_cron.sql`, NO ejecutado).

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
