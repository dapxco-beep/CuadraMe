# Atajos de CuadraMe para iPhone

Dos atajos pequeños, en lugar de uno grande, para que sean fáciles de armar en el celular. La versión paso a paso con maquetas está en `docs/crear-atajos-cuadrame.html`.

| Atajo | Lo llama | Qué recibe | Qué hace |
|---|---|---|---|
| **CuadraMe Apple Pay** | Automatización **Transacción** | Comercio, importe y tarjeta | Registra el pago directo, sin preguntar |
| **CuadraMe Cierre** | Una automatización **App → Se cierra** por cada app | El nombre de la cuenta, como texto | Pregunta "¿Hiciste algún movimiento?" y registra lo que el cliente conteste |

iOS no le dice al atajo qué app se cerró. Por eso cada automatización de cierre de app lleva dos acciones: un **Texto** con el nombre de la cuenta (`Nequi`) y **Ejecutar atajo** `CuadraMe Cierre` con ese texto como entrada. El nombre de la cuenta nunca queda fijo dentro del atajo.

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
   │  No: Detener este atajo       (Gasto e Ingreso no llevan acciones dentro)
3  Pedir entrada (Número)          "¿Cuánto fue?"      →  Establecer variable  monto
4  Pedir entrada (Texto)           "¿En qué? (opcional)" →  Establecer variable  nota
5  Obtener contenido de URL        POST …/movimientos/rapido
                                   Encabezado  X-Api-Key = Texto (paso 1)
                                   Cuerpo JSON tipo        = Resultado del menú
                                               monto       = monto
                                               descripcion = nota
                                               cuenta      = Entrada del atajo
                                               fuente      = cierre_app
6  Obtener valor del diccionario   mensaje
7  Mostrar notificación
```

El backend entiende `Gasto`/`Ingreso` en cualquier mayúscula, así que "Resultado del menú" se usa tal cual.

## Las automatizaciones

**Apple Pay (una).** Atajos → Automatización → **+** → **Transacción** → tarjetas → **Siguiente** → **Ejecutar atajo** `CuadraMe Apple Pay` → desactiva "Preguntar antes de ejecutar".

**Cierre de una app (una por app).** Atajos → Automatización → **+** → **App** → la app → marca **Se cierra**, desmarca **Se abre** → **Siguiente** y añade dos acciones:
1. **Texto**: `Nequi` (o `Daviplata`, `Bancolombia`…).
2. **Ejecutar atajo** `CuadraMe Cierre`, con ese **Texto** como **Entrada**.
Luego desactiva "Preguntar antes de ejecutar".

El texto se busca entre las cuentas del cliente por nombre parcial. Si no coincide ninguna, cae en la primera cuenta.

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
| Cae en la cuenta equivocada | El texto no se parece al nombre de la cuenta | Cambia el Texto de la automatización |
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
