# Atajos de CuadraMe para iPhone

Dos atajos pequeños, en lugar de uno grande. Los clientes los instalan por enlace de iCloud (no los arman). La versión paso a paso con maquetas está en `docs/crear-atajos-cuadrame.html`.

| Atajo | Lo llama | Qué recibe | Qué hace |
|---|---|---|---|
| **CuadraMe Apple Pay** | Automatización **Transacción** | Comercio, importe y tarjeta | Registra el pago directo, sin preguntar |
| **CuadraMe Cierre** | Una automatización **App → Se cierra** por cada app | Nada | Pregunta "¿Hiciste algún movimiento?" y registra lo que el cliente conteste |

iOS no le dice al atajo qué app se cerró. Por eso el atajo de cierre le pregunta a CuadraMe qué cuentas tiene el cliente y se las muestra para elegir. Así el nombre de la cuenta nunca queda fijo dentro del atajo y no depende de ningún texto en la automatización.

En todos los casos el movimiento queda **por confirmar**. Al abrir la app, el cliente lo confirma, lo edita o lo descarta. Con el extracto, la conciliación lo cruza por fecha, hora y monto y lo completa con el destinatario real.

URL del servidor: `https://backend-production-aeab.up.railway.app/movimientos/rapido`

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

**Para que no pregunte en cada cierre (recomendado).** iOS dispara la automatización cada vez que se cierra la app, aunque solo hayas ido a mirar un saldo. Se arregla con cuatro pasos al INICIO del atajo, justo después del paso 1 (Texto con la clave):

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
| CuadraMe Apple Pay | `ATAJO_ICLOUD_URL` | https://www.icloud.com/shortcuts/8b2de178aff84465a938df4a5ef9c0dc |
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
