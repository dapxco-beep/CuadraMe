# Rendimiento y fluidez de CuadraMe

Objetivo: que la app se sienta rápida en celulares modestos con datos móviles lentos (Colombia).
Este documento deja registrado cómo se midió, qué se encontró, qué se cambió y qué queda pendiente.

## Cómo se midió

- Chrome (Playwright), viewport 390x844, **red «Fast 3G»** (1,6 Mbps bajada, 750 kbps subida,
  150 ms de latencia por petición) y **CPU 4x más lenta** (CDP `Network.emulateNetworkConditions` y
  `Emulation.setCPUThrottlingRate`).
- Build de producción servido con gzip (como Vercel) + backend local (SQLite) con **datos sintéticos
  de 1.500 movimientos**, 4 cuentas, 5 presupuestos, metas, deudas y recurrentes (`backend/tools/prueba_carga.py`).
- «Inicio útil» = el texto «Hola, …» del Inicio ya visible y sin esqueletos de carga.
- «Carga fría» = primera apertura (sin caché ni service worker). «Recarga» = segunda apertura
  (service worker y caché HTTP calientes). Mediana de 3 corridas por escenario.
- Las cifras absolutas dependen de la máquina; lo útil es la comparación antes/después en la misma máquina.

## Resultados (antes -> después)

| Medida | Antes | Después |
|---|---|---|
| Inicio útil, carga fría (Fast 3G, CPU 4x) | 3,56 s | 2,98 s (-16 %) |
| Inicio útil, recarga (app ya instalada/abierta antes) | 1,12 s | 0,63 s (-44 %) |
| JavaScript de la carga inicial (sin comprimir) | ~860 KB | ~615 KB (+39 KB de animaciones que bajan después) |
| JavaScript de la carga inicial (gzip) | ~262 KB | ~190 KB (-27 %) |
| Bytes transferidos en la carga fría (todo) | 353 KB | 257 KB (-27 %) |
| Bytes de la API en el arranque (12 lecturas del Inicio) | 52 KB | 23 KB (-56 %, gzip) |
| Navegación entre pantallas ya visitadas (Inicio, Movimientos, Presupuesto, Metas…) | 36-300 ms | 40-100 ms |
| Peticiones de API al arrancar | 19 (ya estaban deduplicadas; 38 sin deduplicar según el REPORTE de QA) | 19, ahora **en paralelo con la descarga del JS** |

Backend con 1.500 movimientos (mediana de 4 llamadas ya calientes, SQLite local; sin cambios de
lógica): `cuentas` 17 ms, `movimientos?limit=50` 23 ms, `presupuestos/disponible-hoy` 86 ms,
`reportes/mensual` 122 ms, `reportes/tendencias` 134 ms, `consejos` 59 ms, `insights/alertas-proactivas`
77 ms, `punto-de-partida/cobertura` 6 ms. Consultas SQL por endpoint: máximo 9 salvo
`sincronizacion/estado` (17, constante, no crece con los datos): no hay N+1.

## Qué se cambió

### Carga inicial
- **`@supabase/auth-js` en vez de `@supabase/supabase-js`** (`pwa/src/lib/supabase.js`): la app solo
  usa autenticación; el paquete completo traía realtime, storage, postgrest y functions (~120 KB que
  nunca se ejecutaban). Misma llave de almacenamiento (`sb-<host>-auth-token`), mismas cabeceras y
  opciones por defecto: **no cierra la sesión de nadie**.
- **Animaciones lazy**: los componentes usan `m` + `LazyMotion` (el motor, ~39 KB, baja después del
  primer pintado) en vez de `motion` completo (~124 KB en el paquete principal).
- **Separación de librerías** (`vite.config.js`, `manualChunks`): `vendor-react` y `vendor-auth` son
  archivos estables; tras un despliegue el celular solo baja el código propio.
- **Menos peso en el paquete principal**: `AVISO_EDUCATIVO` salió de `aprende.js` (22 KB de
  lecciones que el Inicio cargaba por una frase); el Recorrido (15 KB) y las pantallas
  CrearCuenta / NuevaPassword / AutorizacionTratamiento se descargan al abrirse.
- **`preconnect` a la API** y **preload de las dos letras** que se ven primero (400 y 700) en `index.html`.
- **Vercel**: `/assets/*` con `Cache-Control: immutable` (1 año) y `/sw.js` siempre revalidado.
- **Recarga automática una vez** si tras un despliegue una pestaña vieja pide un archivo que ya no
  existe (`vite:preloadError` en `main.jsx`); antes salía «Algo salió mal».
- **Service worker**: si la red tarda más de 4 s al abrir, se muestra el último `index.html`
  guardado (abre al instante) en vez de esperar. Los archivos con hash siguen cache-first.

### Peticiones y cascadas
- **Arranque en paralelo** (`index.html` + `api.js`): si ya hay sesión vigente, las 13 lecturas del
  Inicio (autorización, cuentas, categorías, movimientos, reporte, disponible hoy…) salen
  **mientras todavía baja y se analiza el JS**; `api.js` las recoge una sola vez (misma sesión,
  menos de 15 s). Antes eran tres escalones en fila: autorización -> cuentas -> datos del Inicio.
  `lib/arranque.js` hace lo mismo desde React por si el script no corrió (y comparte las respuestas).
  Las rutas del script deben mantenerse alineadas con `lib/arranque.js`.
- **CORS `max_age=7200`**: el navegador recuerda el permiso (preflight) y no lo repite antes de
  cada lectura (cada preflight era un viaje de ida y vuelta extra).
- **Compresión gzip** en la API (`backend/app/compresion.py`): respuestas > 1 KB, nivel 5, excepto
  descargas (`/exportar`, `/backup`). Una lista de 50 movimientos baja de 17,5 KB a 2,1 KB.
- Ya existían y se conservan: deduplicación de GET idénticos en vuelo, caché de 5 s e
  invalidación total ante cualquier escritura (`api.js`).

### Percepción
- **Último visto (stale-while-revalidate)** (`lib/ultimoVisto.js`): Inicio y Presupuesto pintan al
  instante lo que se vio hace menos de 30 min mientras llega lo nuevo y se actualizan solos; sin
  copia, esqueleto como antes. Movimientos también muestra su lista en caché al entrar desde el menú.
- Presupuesto ya no vuelve a mostrar el esqueleto completo al recargar tras borrar o crear.
- **Sin parpadeos**: los esqueletos y la pantalla «Cargando» aparecen a los 250 ms (si los datos
  llegan antes, no se ve nada); la transición entre pantallas pasó de 320 a 200 ms; el splash de
  marca pasó de ~1,3 s a ~0,95 s.
- **Eliminar varios movimientos es optimista**: las filas salen al instante, se restauran si falla,
  y los saldos se refrescan en segundo plano en vez de bloquear la pantalla.
- Ya estaban: categorizar con actualización optimista y «Deshacer», scroll restaurado al volver
  (`useEstadoLista`), botones con «Guardando...».

### Mala señal / sin conexión
- **Leer sin red**: si una lectura falla por falta de conexión, se devuelve lo último visto
  (hasta 7 días) y aparece una franja «Sin conexión: ves lo último que cargó» (`AvisoSinConexion`).
- **Registrar un gasto sin señal** (`lib/colaOffline.js`): un movimiento nuevo (ingreso o gasto) se
  guarda en el celular con su hora real y se envía solo al volver la red, en orden. Un 409
  (duplicado: la respuesta se perdió pero sí se guardó) se descarta sin duplicar. Transferencias,
  ediciones y borrados siguen pidiendo conexión.

### Backend
- `backend/supabase/migraciones/indices_rendimiento.sql` (idempotente, **NO ejecutado**): se agregaron
  `ix_huellas_usuario_huella`, `ix_huellas_movimiento` y `ix_movimientos_huella` (deduplicación entre
  canales). El script lleva ahora 8 índices y su consulta de verificación.
- Sin N+1: ningún endpoint medido ejecuta más de 9 consultas (17 el estado de sincronización,
  constante). Todos responden en < 140 ms con 1.500 movimientos.

## Decisiones y por qué

- **No hay ETag ni caché HTTP de datos.** La política de seguridad (`docs/AUDITORIA_SEGURIDAD.md`,
  hallazgo 8) es `Cache-Control: no-store` en toda respuesta para que ningún navegador ni proxy
  guarde datos financieros; revalidar con ETag exigiría guardarlos. Se prefirió gzip + peticiones
  en paralelo, que no tocan esa política. Tampoco el service worker cachea la API.
- **«Último visto» en el celular**: guarda en `localStorage` solo unas pocas lecturas permitidas
  (cuentas, movimientos recientes, resumen, presupuestos, reporte y tendencias del mes, categorías,
  patrimonio, metas, deudas, recurrentes y estado de sincronización), por usuario, máximo ~180 KB, y
  se borra al cerrar sesión o al vencer la sesión. **Nunca** claves de API, correos ni conexiones.
  Es una decisión de privacidad que conviene que Daniel confirme: si prefiere que no quede nada
  en disco, basta poner `PERSISTIBLE` vacío (`lib/ultimoVisto.js`) y el «último visto» sigue
  funcionando solo mientras la app está abierta.
- **Reportes mensuales/tendencias siguen leyendo todo el historial** (O(N) en Python). Con 1.500
  movimientos tardan ~130 ms; con decenas de miles se notará. Acotar la consulta a una ventana
  cambiaría el emparejamiento de traslados entre cuentas propias (`tipos_efectivos`) en casos
  límite, así que no se tocó sin una revisión específica de cuentas.

## Pendiente / recomendaciones (requieren decisión o despliegue)

1. **Servir la API desde el mismo dominio de la PWA** (rewrite de Vercel `/api/*` -> Railway). Evita
   el preflight CORS y el saludo TLS extra a Estados Unidos desde Colombia (varios cientos de ms
   en la carga fría). Requiere cambiar `VITE_API_URL` y el destino del rewrite: es un cambio de
   producción, no se hizo.
2. **Ejecutar `indices_rendimiento.sql`** en Supabase (SQL Editor) cuando Daniel lo apruebe.
3. **Región del backend**: Railway en California agrega 150-250 ms por viaje desde Colombia.
   Una región más cercana (o el punto 1) pesa más que cualquier optimización de código.
4. Brotli en Vercel ya viene activado por defecto para los estáticos; no requiere acción.
5. Si el historial de un usuario crece (> 10 mil movimientos), pre-agregar por mes (tabla
   resumen) para `reportes/mensual` y `reportes/tendencias`.

## Versión de la app (1.0.0)

- La PWA pasó de `0.0.0` a `1.0.0` en `pwa/package.json`; ese número es el que se muestra. Súbelo en cada entrega visible.
- El build inyecta `__APP_VERSION__`, `__APP_BUILD__` y `__APP_COMMIT__` (Vite `define`) y publica `/version.json` (sin caché: cabecera en `vercel.json`, el service worker no lo toca).
- La app lo consulta al volver a primer plano y cada 30 min; si hay compilación más nueva muestra «Hay una versión nueva · Actualizar» (nunca recarga sola).
- Servidor: `GET /version` devuelve `{servicio, version, commit, arranque_en}`; `/health` no cambia.
