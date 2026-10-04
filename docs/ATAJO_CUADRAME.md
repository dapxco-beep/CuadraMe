# Atajos de CuadraMe para iPhone

Dos atajos pequeños, en lugar de uno grande, para que sean fáciles de armar en el celular. La versión paso a paso con maquetas está en `docs/crear-atajos-cuadrame.html`.

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
4. "Enviar un pago de prueba" en Conectar dispositivo prueba el servidor, no los atajos.

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

## Compartir con los clientes

1. Vacía el Texto de la clave en cada atajo y deja la pregunta de importación.
2. Mantén pulsado cada atajo → **Compartir → Copiar enlace de iCloud**.
3. Se revisan por dentro (clave vacía, propiedades elegidas, pregunta de importación) leyendo el enlace de iCloud.
4. Se pegan los dos enlaces en `pwa/src/screens/ConectarDispositivo.jsx` (hoy solo existe la constante `ATAJO_ICLOUD_URL`, para el de Apple Pay; falta añadir la del cierre).
5. Si cambias un atajo, el enlace nuevo es otro. Quien ya lo instaló conserva su versión.

## Lo que Apple no permite

- Leer las notificaciones de otras apps.
- Crear la automatización por el cliente: cada uno la crea en su Atajos.
- Saber qué app se cerró o si hubo un movimiento: por eso el Texto con el nombre de la cuenta y la pregunta.
