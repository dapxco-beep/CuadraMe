# Atajos de CuadraMe para iPhone

> **2026-11-07:** el atajo «CuadraMe Cierre» (App › Se cierra) ya NO se ofrece en la app. Se quitó del catálogo, del paso de Wallet y del panel
> avanzado. El servidor conserva `/movimientos/cierre-pregunta` y `/movimientos/cuentas-rapido` por si alguien ya lo tenía instalado.
> Hoy los atajos que se ofrecen son: CuadraMe Apple Pay, CuadraMe Notificaciones y CuadraMe Registrar (ver `pwa/src/components/CatalogoAtajos.jsx`).

## Atajos vigentes (noviembre de 2026)

| Atajo | Lo llama | Qué manda | Qué hace el servidor |
|---|---|---|---|
| **CuadraMe Apple Pay** | Automatización **Transacción** | Comercio, importe y tarjeta (`fuente=wallet`) a `/movimientos/rapido` | Registra el pago; la tarjeta decide la cuenta por su alias |
| **CuadraMe Notificaciones** | Una automatización **«Cuando recibo una notificación»** (iOS 27) por cada app de banco | El texto del aviso, `paquete=auto` a `/movimientos/rapido-notificacion` | Lee por verbos (no por banco), deduce la cuenta y registra; pregunta solo lo que no puede saber |
| **CuadraMe Registrar** | Un gesto que elige cada persona (Tocar atrás, Botón de acción, Siri) | El texto leído de un pantallazo (OCR en el iPhone; la imagen no sale del teléfono), `paquete=auto` | Igual que Notificaciones, con lector de comprobantes de Nu, Nequi y Bancolombia |

Cómo responde `/movimientos/rapido-notificacion` (campo `motivo`): sin motivo = registrado «por confirmar»; `pedir_monto` (salió plata y el aviso no trae cifra);
`pedir_tipo` (hay monto pero no se sabe si entró o salió); `confirmar_cuenta` (no se supo de qué cuenta era: YA se registró en la más probable y el atajo
pregunta «¿De qué cuenta es?» con `GET /movimientos/cuentas-rapido`; la respuesta vuelve con `movimiento_id` + `cuenta` y el servidor MUEVE ese movimiento con
`mover_masivo` —saldos ajustados— y aprende esa pantalla; solo mueve movimientos propios creados por un atajo); `no_parece_un_movimiento`.
Cada respuesta de la persona se aprende como regla personal (`reglas_notificacion`): plantilla anónima, sin texto, nombres ni montos; se ve y se borra en Conexiones.

**Cuenta de un pantallazo**, en orden: lo que la persona enseñó → últimos 4 dígitos («*8223») contra el alias de sus cuentas → huellas por banco
(`HUELLAS_BANCO` en `backend/app/reglas_notificacion.py`) → nombre del banco en el texto, SIN contar destinos («Entidad», «Producto destino»,
«a su cuenta de», «Institución de origen»). **Para enseñarle un banco nuevo** hace falta una captura real de su comprobante: se agrega su huella y su prueba
(con datos inventados: el repositorio es público).

### Cómo se (re)generan y se publican los atajos

Los archivos salen de `backend/tools/generar_atajo_notificaciones.py` (`--modo notificacion|pantalla|captura|wallet`). iOS exige que estén firmados, y eso se hace
en un Mac (basta el Apple ID gratis):

```
python3 backend/tools/generar_atajo_notificaciones.py --modo pantalla --salida sinfirmar.shortcut
shortcuts sign -m anyone -i sinfirmar.shortcut -o "CuadraMe Registrar.shortcut"
```

1. El nombre del archivo firmado es el nombre con el que se comparte: debe ser EXACTAMENTE «CuadraMe Apple Pay», «CuadraMe Notificaciones» o «CuadraMe Registrar» (sin «firmado»).
2. Se importa en la app Atajos, y se usa Compartir › Copiar enlace de iCloud.
3. Se comprueba el nombre con `https://www.icloud.com/shortcuts/api/records/<id>` (campo `name`).
4. El enlace se pega en `pwa/src/lib/atajosEnlaces.js` y se despliega la web. Quien ya instaló un atajo conserva su versión: hay que avisarle si cambia.

### Cómo aprende la app de dónde viene cada pantalla

El atajo NO sabe qué app está abierta (iOS no se lo dice), así que el servidor lo deduce del texto. Y **aprende de lo que la persona hace**:
al crear un movimiento por pantallazo se anota, sin el texto, la «forma» de esa pantalla (`reglas_notificacion.forma_estable`: palabras fijas; nombres,
montos y bancos tapados) en una fila `mov:<id>` de `reglas_notificacion`. Si la persona **mueve ese movimiento a otra cuenta** (editar o mover varios)
o lo **confirma**, esa forma pasa a ser una regla `pantalla:<cuenta>`, y la próxima pantalla PARECIDA (`_parecida`: mismas palabras fijas) va directo a esa
cuenta sin adivinar. Si se corrige, gana lo último que enseñó (una sola regla por pantalla). Solo se guardan las últimas 100 formas pendientes por persona.
Orden de decisión de la cuenta: regla aprendida › últimos 4 dígitos › huella de banco › nombre del banco en el texto (sin contar destinos) › la cuenta que más usa.

### Quien ya tiene un atajo anterior

iOS NO actualiza los atajos instalados desde un enlace: cada persona guarda una copia. Por eso el aviso viaja dentro del propio atajo:
`backend/app/routers/movimientos.py` (`_aviso_atajo_viejo`) detecta los atajos anteriores (los nuevos mandan `paquete="auto"`; los anteriores mandaban el
nombre de un banco) y agrega a su `mensaje`, una vez al día por persona, cómo cambiarlo (Perfil › Registro automático › Instalar). Los atajos anteriores
siguen funcionando: el servidor conserva sus nombres de banco y respuestas. La app lo explica en el catálogo («¿Ya tenías un atajo instalado?» y «¿No funciona?»).

**Cuando una versión futura exija reinstalar:** hacer que el generador mande un campo `version` en el JSON, subir una constante en el servidor y comparar en
`_aviso_atajo_viejo` (hoy la heurística es solo «auto» o no). Cambiar el enlace de iCloud no avisa a nadie por sí solo.

La clave de cada persona NO va dentro del archivo: iOS la pide al instalar. «Registrar» ya se usó en un iPhone real y llega al servidor; «Notificaciones» y «Apple Pay» siguen pendientes de prueba en un iPhone real.

Dos atajos pequeños, en lugar de uno grande. Los clientes los instalan por enlace de iCloud (no los arman). La versión paso a paso con maquetas está en `docs/crear-atajos-cuadrame.html`.

| Atajo | Lo llama | Qué recibe | Qué hace |
|---|---|---|---|
| **CuadraMe Apple Pay** | Automatización **Transacción** | Comercio, importe y tarjeta | Registra el pago directo, sin preguntar |
| **CuadraMe Cierre** | Una automatización **App → Se cierra** por cada app | Nada | Pregunta "¿Hiciste algún movimiento?" y registra lo que el cliente conteste |

iOS no le dice al atajo qué app se cerró. Por eso el atajo de cierre le pregunta a CuadraMe qué cuentas tiene el cliente y se las muestra para elegir. Así el nombre de la cuenta nunca queda fijo dentro del atajo y no depende de ningún texto en la automatización.

En todos los casos el movimiento queda **por confirmar**. Al abrir la app, el cliente lo confirma, lo edita o lo descarta. Con el extracto, la conciliación lo cruza por fecha, hora y monto y lo completa con el destinatario real.

URL del servidor: `https://api.cuadrame.dapx.shop/movimientos/rapido`

## Atajo 1 · CuadraMe Apple Pay

```
1  Texto                           tu clave (queda VACÍA al compartir; pregunta de importación)
2  Obtener contenido de URL        POST …/movimientos/rapido
                                   Encabezado  X-Api-Key = Texto (paso 1)
                                   Cuerpo JSON comercio = Entrada del atajo › Comercio
                                               monto    = Entrada del atajo › Importe
                                               tarjeta  = Entrada del atajo › Tarjeta o pase
                                               fuente   = wallet
3  Obtener valor del diccionario   mensaje
4  Mostrar notificación
```

## Atajo 2 · CuadraMe Cierre

```
1  Texto                           tu clave (queda VACÍA al compartir; pregunta de importación)
1b Obtener contenido de URL        GET …/movimientos/cierre-pregunta?horas=3   (X-Api-Key = Texto del paso 1)
1c Obtener valor del diccionario   preguntar
1d Si  (Valor del diccionario)  no es  "si"   →   Detener este atajo      (así no pregunta en cada cierre)
2  Elegir del menú                 "¿Hiciste algún movimiento?"  →  Gasto · Ingreso · No
   │  Gasto:   Texto  gasto
   │  Ingreso: Texto  ingreso
   │  No:      Detener este atajo
3  Obtener contenido de URL        GET …/movimientos/cuentas-rapido
                                   Encabezado  X-Api-Key = Texto (paso 1)
4  Elegir de la lista              "¿En qué cuenta?"  (lista = Contenido de la URL del paso 3)
5  Pedir entrada (Número)          "¿Cuánto fue?"      →  Establecer variable  monto
6  Pedir entrada (Texto)           "¿En qué? (opcional)" →  Establecer variable  nota
7  Obtener contenido de URL        POST …/movimientos/rapido
                                   Encabezado  X-Api-Key = Texto (paso 1)
                                   Cuerpo JSON tipo        = Resultado del menú
                                               monto       = monto
                                               descripcion = nota
                                               cuenta      = Elemento elegido (paso 4)
                                               fuente      = cierre_app
8  Obtener valor del diccionario   mensaje
9  Mostrar notificación
```

**Por qué están los pasos 1b–1d (ya incluidos arriba).** iOS dispara la automatización cada vez que se cierra la app, aunque solo hayas ido a mirar un saldo. Se arregla con cuatro pasos al INICIO del atajo, justo después del paso 1 (Texto con la clave):

```
1b  Obtener contenido de URL        GET …/movimientos/cierre-pregunta?horas=3
                                    Encabezado  X-Api-Key = Texto (paso 1)
1c  Obtener valor del diccionario   preguntar
1d  Si  (Valor del diccionario)  no es  "si"   →   Detener este atajo
```

El servidor responde "si" como máximo una vez cada 3 horas (cambia `horas`, de 1 a 12) y "no" en los demás cierres. Quien salta de un banco a otro solo ve la pregunta en el primero. No requiere migración: usa la tabla `marcas_cron`.

**Importante:** "Resultado del menú" no es el nombre de la opción tocada, sino lo que devuelve la última acción dentro de esa opción. Por eso Gasto e Ingreso llevan cada una un **Texto** (`gasto` / `ingreso`). Si quedan vacías, el atajo envía otro valor como `tipo` y el servidor responde "falta o no se entiende el tipo".

`GET /movimientos/cuentas-rapido` (autenticado por `X-Api-Key`) responde una lista simple de nombres, por ejemplo `["Bancolombia","Nequi"]`, que Atajos entiende directo como lista. Así la cuenta ya no va fija ni depende de un texto en la automatización.

## Las automatizaciones

**Apple Pay (una).** Atajos → Automatización → **+** → **Transacción** → tarjetas → **Siguiente** → **Ejecutar atajo** `CuadraMe Apple Pay` → desactiva "Preguntar antes de ejecutar".

**Cierre de una app (una por app).** Atajos → Automatización → **+** → **App** → la app → marca **Se cierra**, desmarca **Se abre** → **Siguiente** → una sola acción: **Ejecutar atajo** `CuadraMe Cierre`. Desactiva "Preguntar antes de ejecutar". El atajo pregunta la cuenta en el momento.

Si en CuadraMe no existe la cuenta que el cliente elige, no aparece en la lista: se crea en Cuentas → Nueva cuenta.

## Si el servidor tarda o falla

El servidor gratis puede tardar unos segundos si estuvo dormido. En los pasos "Obtener contenido de URL" deja el tiempo de espera largo y, después del POST final, el paso 8 (`mensaje`) ya muestra el aviso del servidor. Si la respuesta no trae `mensaje` (error de red o clave mala), agrega al final:

```
9b Si  (Valor del diccionario)  no tiene valor  →  Mostrar notificación "CuadraMe no respondió; abre la app y registra a mano"
```

Así nunca falla en silencio.

## Cómo probarlo

1. **Cierre de app.** Abre y cierra la app configurada: sale el menú. Elige Gasto, `1000` y una nota. Llega la notificación de CuadraMe.
2. **En CuadraMe.** Aparece "Detectamos 1 movimiento". En **Perfil → Conexiones** el atajo muestra "último uso hace 1 min".
3. **Apple Pay.** Compra pequeña con Apple Pay: aviso en unos 5 segundos.
4. «Probar ahora» prueba el servidor y la cuenta, no los atajos; la señal real es que el paso se marque solo cuando llega el primer pago del iPhone.

## Errores frecuentes

| Síntoma | Causa | Arreglo |
|---|---|---|
| 401 | Clave vacía o con espacios | Pégala de nuevo en el Texto |
| 422 en `monto` | El campo recibió la entrada completa | Toca la burbuja y elige la propiedad (Importe) |
| "falta o no se entiende el tipo" | Gasto/Ingreso del menú están vacías | Pon un Texto `gasto` / `ingreso` dentro de cada opción |
| No sale mi cuenta en la lista | La cuenta no existe en CuadraMe | Créala en Cuentas → Nueva cuenta |
| La lista sale rara o vacía | El GET devolvió un error (clave mala) | Revisa la clave y que la URL termine en `/cuentas-rapido` |
| No corre sola | Quedó con "Preguntar antes de ejecutar" | Desactívalo |
| Pregunta cada vez que miras el saldo | El disparador salta al cerrar la app | Toca "No" |

## Cómo lo ve el cliente: «Registro automático al pagar con el iPhone»

Pantalla `pwa/src/screens/ConectarDispositivo.jsx` (ruta `/conectar-dispositivo`). De cara al cliente ya no se llama «atajo» ni «Conectar dispositivo». Un solo flujo, una cosa por pantalla:

| Pantalla | Qué hace |
|---|---|
| Intro | «Cada vez que pagas con Apple Pay, CuadraMe lo anota solo». Etiqueta «Funciona en iPhone». En Android/PC explica que use correo o extractos y enlaza a Sincronización (no queda vacía) |
| Paso 1 de 3 · Copia tu clave | Botón grande «Copiar mi clave» que confirma. La clave completa solo se ve al crearla |
| Paso 2 de 3 · Instala el atajo | Abre `ATAJO_ICLOUD_URL`. «Cuando te lo pida, pega la clave» |
| Paso 3 de 3 · Actívalo en Wallet | Automatización «Transacción» en 4 pasos numerados con ilustración. Dentro, plegado y opcional, el segundo atajo «Para registrar pagos en efectivo o en cuentas sin Apple Pay» (`ATAJO_CIERRE_URL` + automatización App → Se cierra) |
| Probar | Botón «Probar ahora» (ver abajo) |
| Listo | Se muestra solo cuando el atajo real ya envió algo |

El paso se recuerda en el celular (`localStorage`, clave `cuadrame:atajo-paso`) y hay botón Atrás. Todo lo técnico (armar a mano, Android con Tasker, Siri por voz) vive plegado bajo «Avanzado» (`components/AtajoAvanzado.jsx`) y no se pinta hasta abrirlo.

| Atajo | Constante | Enlace |
|---|---|---|
| CuadraMe Apple Pay | `ATAJO_ICLOUD_URL` | https://www.icloud.com/shortcuts/002171858328481ab9b3d58718192c73 |
| CuadraMe Cierre | `ATAJO_CIERRE_URL` | https://www.icloud.com/shortcuts/d34fa153ac844631baf36d8e158f7bf4 |

## Verificación en vivo

- **Detección automática (sin marcar a mano):** la pantalla consulta `GET /conexiones/estado` y mira `atajo.ultimo_uso` (último uso real de la clave API). Mientras espera repite cada 6 s. Si aparece, muestra «¡Listo! Tu primer pago de prueba llegó». El mismo dato marca el paso «atajo» del asistente de primer uso.
- **«Probar ahora»:** usa `POST /movimientos/rapido-prueba` con la SESIÓN (no con la clave), así NO altera el «último uso de la clave», que queda reservado para el atajo real. Comprueba que el pago aparece en «por confirmar». Prueba el servidor y la cuenta, no el iPhone.
- **Errores en lenguaje simple** (`pwa/src/lib/atajoPrueba.js`): 404 → «Aún no tienes dónde anotar el pago» con botón a Cuentas (Nu, Nequi…); 401 → sesión cerrada; 429 → espera; sin red → sin conexión; no apareció en «por confirmar» → repite. Si la prueba sale bien pero el iPhone no envía nada, se listan las 3 causas típicas: clave mal pegada, atajo no instalado, automatización que pregunta antes de correr.
- Sin cambios de backend: se reutilizan `rapido-prueba`, `conexiones/estado` y los mensajes de `errores_atajo.py`.

Para actualizar un atajo:
1. Vacía el Texto de la clave y deja la pregunta de importación «Pega tu clave de Cuádrame».
2. Mantén pulsado el atajo → **Compartir → Copiar enlace de iCloud**.
3. Revisa por dentro el enlace (clave vacía, propiedades elegidas, pregunta de importación).
4. Pega el enlace nuevo en la constante correspondiente. Quien ya instaló el atajo conserva su versión: avísale que lo vuelva a instalar.

## Lo que Apple no permite

- Leer las notificaciones de otras apps.
- Crear la automatización por el cliente: cada uno la crea en su Atajos.
- Saber qué app se cerró o si hubo un movimiento: por eso el Texto con el nombre de la cuenta y la pregunta.

## La clave del Atajo (guardada como hash)

- CuadraMe ya no guarda tu clave en claro: guarda solo una "huella" (SHA-256) y las primeras letras (`cdm_ab12…`).
- La clave completa se muestra **una sola vez**, al crearla o al pulsar «Crear una clave nueva». Aparece un aviso: «Cópiala ahora, no se vuelve a mostrar». Pégala enseguida en el Atajo.
- Si ya existe una clave guardada, la app dice «Tu clave empieza por cdm_ab12…». Si la perdiste, crea una nueva; el Atajo del iPhone dejará de funcionar hasta que pegues la nueva.
- Las claves antiguas siguen funcionando sin que hagas nada: al usarse por primera vez el servidor las convierte a huella solo.
- «Probar ahora» ya no necesita leer la clave guardada: usa tu sesión (`POST /movimientos/rapido-prueba`, mismo registro que `/rapido`). Si acabas de crear la clave, la prueba usa esa clave y revisa el camino real del Atajo.
- Para el equipo: las columnas `api_key_hash` y `api_key_prefijo` se crean con `backend/supabase/migraciones/api_key_hash.sql` (idempotente, pendiente de aprobar). Mientras no existan, todo sigue en claro como antes y la app muestra la clave como siempre.
