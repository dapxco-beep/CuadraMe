# Atajo de CuadraMe para iPhone

Un solo atajo, llamado desde dos automatizaciones. Esta guía sirve para armarlo una vez (tú) y para entender qué ve el cliente.

## Cómo funciona

| Quién lo llama | Qué recibe el atajo | Qué hace |
|---|---|---|
| Automatización **Transacción** (Apple Pay) | Comercio, importe y tarjeta | Registra el pago directo, sin preguntar |
| Automatización **App → Se cierra** (Nequi, Daviplata, un banco) | Nada | Pregunta "¿Hiciste algún movimiento?" y registra lo que el cliente conteste |

En los dos casos el movimiento queda **por confirmar** en CuadraMe. Al abrir la app, el cliente lo confirma, lo edita o lo descarta. Cuando llega el extracto del banco, la conciliación lo cruza por fecha, hora y monto, y lo completa con el destinatario real.

## Estructura del atajo

Nombre: `CuadraMe – registrar pago`

```
1. Texto                          → tu clave de CuadraMe (queda VACÍO al compartir)
2. Texto                          → nombre de la cuenta para el cierre de app (por defecto: Nequi)
3. Si  [Entrada del atajo]  tiene algún valor
   │
   │  ── Camino A: Apple Pay ──
   ├─ 4. Obtener contenido de URL      POST …/movimientos/rapido
   │      Encabezado   X-Api-Key = Texto (paso 1)
   │      Cuerpo JSON  comercio = Entrada del atajo › Comercio
   │                   monto    = Entrada del atajo › Importe
   │                   tarjeta  = Entrada del atajo › Tarjeta o pase
   │                   fuente   = wallet
   ├─ 5. Obtener valor del diccionario  clave: mensaje
   ├─ 6. Mostrar notificación           (valor del paso 5)
   │
   │  ── Camino B: cierre de la app ──
   └─ Si no
        7. Elegir del menú  "¿Hiciste algún movimiento?"
           ├─ Gasto
           │    8. Pedir entrada  (Número)  "¿Cuánto fue?"
           │    9. Pedir entrada  (Texto)   "¿En qué? (opcional)"
           │   10. Obtener contenido de URL   POST …/movimientos/rapido
           │         Encabezado  X-Api-Key = Texto (paso 1)
           │         Cuerpo JSON tipo = gasto, monto = (paso 8),
           │                     descripcion = (paso 9), cuenta = Texto (paso 2),
           │                     fuente = cierre_app
           │   11. Obtener valor del diccionario  clave: mensaje
           │   12. Mostrar notificación
           ├─ Ingreso   (igual que Gasto, con tipo = ingreso)
           └─ No        13. Detener este atajo
   Fin Si
```

URL del servidor: `https://backend-production-aeab.up.railway.app/movimientos/rapido`

## Cómo armarlo en el iPhone

1. App **Atajos → Atajos → +**. Nómbralo `CuadraMe – registrar pago`.
2. Añade **Texto** (paso 1) y pega tu clave (Perfil → Conectar dispositivo → Copiar clave).
3. Añade otro **Texto** (paso 2) con `Nequi`.
4. Añade **Si**. En la condición elige **Entrada del atajo** y **tiene algún valor**.
5. Dentro del "Si", crea el Camino A:
   - **Obtener contenido de URL**, método POST, encabezado `X-Api-Key`.
   - Cuerpo **JSON** con los cuatro campos. Para cada valor toca **Seleccionar variable → Entrada del atajo**, vuelve a tocar la burbuja azul y elige la propiedad (Comercio, Importe, Tarjeta o pase).
   - Si la lista de propiedades no se abre, crea primero la automatización de Transacción y vuelve.
   - **Obtener valor del diccionario** (clave `mensaje`) y **Mostrar notificación**.
6. En el "Si no", crea el Camino B con **Elegir del menú** y las tres opciones. Dentro de Gasto e Ingreso usa **Pedir entrada**, tipo Número y tipo Texto.
7. En cada **Obtener contenido de URL** del Camino B, el campo `monto` debe usar la burbuja del resultado de **Pedir entrada**, no una "Entrada del atajo".
8. Pregunta de importación para la clave: **⋯ → Configuración → Añadir pregunta de importación**, ligada al texto del paso 1. Pregunta sugerida: `Pega tu clave de CuadraMe (la app ya la copió)`.
9. Opcional: otra pregunta de importación para el paso 2 (`¿Cómo se llama tu cuenta de Nequi en CuadraMe?`).

## Las dos automatizaciones

**Apple Pay.** Atajos → Automatización → **+** → **Transacción** → elige tus tarjetas → **Siguiente** → ejecuta `CuadraMe – registrar pago` → desactiva "Preguntar antes de ejecutar" → **Ejecutar inmediatamente**.

**Cierre de Nequi.** Atajos → Automatización → **+** → **App** → elige Nequi → marca **Se cierra** (desmarca "Se abre") → **Siguiente** → ejecuta el mismo atajo → **Ejecutar inmediatamente**.

Para otra app (Daviplata, tu banco), crea otra automatización igual. Si esa app va a una cuenta distinta de Nequi, duplica el atajo y cambia el texto del paso 2.

## Cómo probarlo

1. **Conexión.** Ejecuta el atajo a mano con el botón de play. Sin datos, entra por el Camino B y te muestra el menú. Elige Gasto, escribe `1000` y una nota. Debe aparecer la notificación de CuadraMe y, en la app, "Detectamos 1 movimiento".
2. **Camino A.** Pulsa "Enviar un pago de prueba" en Perfil → Conectar dispositivo. Eso prueba el servidor, no el atajo.
3. **Real.** Haz una compra pequeña con Apple Pay y mira que llegue el aviso en unos 5 segundos.
4. **Cierre de app.** Abre Nequi y ciérrala: debe salir el menú de "¿Hiciste algún movimiento?".

## Errores frecuentes

| Síntoma | Causa | Arreglo |
|---|---|---|
| Error 401 | Clave vacía o con espacios | Pégala de nuevo en el paso 1 |
| Error 422, "monto" | El campo recibió la "Entrada del atajo" completa | Toca la burbuja y elige la propiedad (Importe) |
| La automatización no corre sola | Quedó con "Preguntar antes de ejecutar" | Cámbiala a "Ejecutar inmediatamente" |
| Se ejecutó sin pedir nada | Entró por el Camino A con datos vacíos | Revisa que la condición sea "tiene algún valor" |
| Pregunta cada vez que miras el saldo | El disparador salta al cerrar la app | Toca "No": es un toque |

## Compartirlo con los clientes

1. Vacía el texto de la clave (paso 1).
2. Mantén pulsado el atajo → **Compartir → Copiar enlace de iCloud**.
3. Pega el enlace en `ATAJO_ICLOUD_URL` de `pwa/src/screens/ConectarDispositivo.jsx`.
4. Si cambias el atajo después, el enlace nuevo es otro. Los clientes que ya lo instalaron conservan su versión.

## Lo que Apple no permite

- Leer las notificaciones de otras apps.
- Crear la automatización por el cliente: cada uno la crea en su Atajos, una vez.
- Saber si hubo un movimiento al cerrar la app: por eso el atajo pregunta.
