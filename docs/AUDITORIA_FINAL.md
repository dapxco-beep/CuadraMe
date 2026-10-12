# Auditoría final de diseño, flujos y tarjetas

Hecha mirando la app como una persona que no es técnica: navegador real (Chrome) contra el backend local (SQLite) con datos **solo sintéticos**, no el sitio desplegado. Cada captura citada se abrió y se miró. Las capturas no están en el repo.

## Cómo se probó (y qué limita)

| Cosa | Detalle |
|---|---|
| Navegador | Chromium con emulación de iPhone 13 (390x664 útil, táctil, puntero «grueso»), 360x740 (Android), 375x667 (SE), horizontal 844x390, escritorio 1280 y 1920. |
| Temas | Claro y oscuro (axe en ambos). |
| Datos | Cuenta nueva · cuenta con 3 cuentas y ~45 movimientos · cuenta con 1.500 movimientos · cuenta con correos, extractos con clave y un correo igual a un gasto manual. |
| Accesibilidad | axe-core 4 con Playwright, instalado **fuera del repo** (no entra al bundle ni a `package.json`). |
| **WebKit/Safari real** | **No se pudo.** El WebKit de Playwright instalado en esta máquina no arranca (falta `libpng16.dll`; se intentó con una copia, sigue sin abrir). Todo lo «de iPhone» es emulación en Chromium: tamaño, táctil, `pointer: coarse`. No prueba el motor de Safari, la barra inferior real, el notch, el teclado real ni el pellizco real. |

## Qué se revisó (pantalla, tamaño, tema)

- **Inicio**: cuenta nueva (360, claro), con datos (360, 390, 1280 claro), con 1.500 movimientos (360). Simple y completo.
- **Movimientos**: 390 y 1280 (lista y tabla), 1.500 filas: carga ~1,8 s local, sin errores. Hoja de categoría.
- **Presupuesto, En qué gasto (Informe), Perfil, Cuentas, Patrimonio, Metas, Deudas, Pagos fijos, Categorías, Hallazgos, Ayuda, Sincronización, Impuestos, Cierre de mes, Resumen, Aprende, Asistente, Nuevo movimiento**: 390 claro con axe y medición de toques; 1280 claro de Inicio, Movimientos, Informe, Presupuesto, Perfil, Cuentas y Patrimonio.
- **Axe en oscuro**: 390, todas las rutas anteriores. Sin violaciones de contraste.
- **Traer movimientos**: 390 y 1280, con un correo igual a un gasto manual, un extracto con clave, un extracto pendiente y tres bancos sin cuenta.
- **Hojas y diálogos**: Esc y «atrás» cierran (Patrimonio, categoría en Movimientos, Ajustes de Presupuesto, Metas, detalle de cuenta): 10 de 10 bien, y «atrás» no saca de la pantalla.
- **Teclado en pantalla** (simulado con 330 px de alto): el campo enfocado de una hoja queda visible con el aro de foco.
- **Horizontal** (844x390): sin scroll horizontal; las hojas hacen scroll interno.
- **Movimiento reducido**: ninguna animación infinita ni activa tras 2,5 s en Inicio, Movimientos, Presupuesto, Informe y Perfil.
- **Impresión**: emulada en Informe y Movimientos (ver pendientes).

## Qué se corrigió

| Dónde | Problema | Arreglo |
|---|---|---|
| Toda la app | No había `<main>` ni `<h1>` en Inicio (lectores de pantalla). | `ShellApp` usa `<main>`; el saludo de Inicio es `<h1>`. |
| Toda la app | Chips y botones pequeños medían 36-38 px con el dedo. | `.btn-sm` y `.chip` miden 44 px con puntero táctil (en escritorio siguen compactos). Selector de periodo (Informe, Hallazgos) migrado a `<Chip>`. Impuestos migrado a `<Boton>`. Categorías (subir/bajar), chip de categoría y casilla de selección en Movimientos, «Agregar activo», «Política de privacidad» y «Volver» del asistente con zona de toque de 44 px. |
| Inicio, modo simple | Los últimos movimientos pegaban el texto y la cifra al borde de la tarjeta (sin margen). | Margen interno de 16 px. |
| Inicio | «Presupuesto del mes» salía como «Presup…». | Se llama «Presupuesto» y el resumen «Libre $ …». |
| Inicio | Lo mismo («N por resolver») salía en 4 sitios: botón, sección «Por resolver», aviso de extractos y aviso de conexión. | Queda UNA: el número en el botón «Traer movimientos» (y el aviso rojo solo si una conexión falla). Se quitó la sección «Por resolver» y el recordatorio de extractos cuando ya hay número. |
| Inicio, cuenta nueva | Tres cosas pedían lo mismo: el paso 2 del camino, la tarjeta «Aún no tienes movimientos» y «Crear una meta». | Con el camino a la vista solo queda el camino (y el saldo). |
| Perfil | Pared de ~15 secciones. | Cuatro grupos plegables con encabezado y una línea de apoyo: Atajos a tus pantallas, Avisos y correo, Seguridad y ajustes, Privacidad y legal. Un enlace con `#punto-de-partida` abre su grupo solo. |
| Nombres | «En qué gasto mi plata» (título) vs «En qué gasto» (menú). | Un solo nombre: «En qué gasto». |
| Nuevo movimiento | El monto se veía de 16 px (la regla anti-zoom de iOS le ganaba al tamaño grande). | 44 px en móvil (sigue siendo mayor de 16: iOS tampoco hace zoom). Sin barra inferior en esta pantalla (el «+» ya es esta pantalla y tapaba el formulario). Tarjetas de cuenta con aro de selección, `aria-pressed` y contraste AA. Botones Gasto/Ingreso/Dividir de 44 px. |
| Tarjetas de cuenta | Una cifra larga se cortaba con «…» (engaña). | La letra baja de tamaño, nunca se corta. |
| Traer movimientos | La insignia de «Por revisar» decía «1» con el bloque vacío («Nada por…»): era «Bancos sin cuenta». | El bloque muestra «Bancos sin cuenta» con un botón por banco. Prueba nueva. |
| En qué gasto | Colores de la dona fijos, ilegibles en oscuro (verde sobre carbón). | Tokens `--c-serie-1..6` con versión clara y oscura. (Ojo: `var()` en `stroke` solo funciona si la variable no es del `@theme` de Tailwind; por eso es `--c-serie-*`.) |
| Inversiones | Costo promedio y precio sin miles. | Usan `<InputMonto>` (1.250.000) con ejemplo en el campo. |
| Hallazgos | Botón de enviar sin nombre. | `aria-label="Enviar pregunta"`. |
| Cuentas | Título «Compras a cuotas» saltaba de nivel. | `h2`. |

## Descartado (no se reprodujo)

- «Errores de Patrimonio y Perfil»: con el backend local real (no simulado) se agregó un activo y se accionaron todos los interruptores y el control de confianza: sin errores en consola ni respuestas 4xx/5xx. Falta confirmarlo contra el sitio desplegado, que no se tocó.
- Cuadri: tamaño y posición correctos en el consejo de Inicio (único sitio donde se miró); con «reducir movimiento» no hay animaciones activas. La celebración se lee en el código (sin toques, sobre la barra inferior), no se vio en pantalla.

## Qué NO se pudo verificar

- Safari/iPhone real: pellizco y zoom (hoy bloqueado a propósito, ver decisiones), muescas y zonas seguras con valores reales (el CSS usa `env(safe-area-inset-*)` en barra inferior, hojas y arriba; no se vio con una muesca real), teclado real, inercia del scroll, orientación al girar el aparato.
- 1920 px: se cubrió 1280; el contenido ya tiene ancho máximo, pero no se revisó pantalla por pantalla a 1920.
- Modo oscuro: solo se vio con ojos Perfil (grupo Avisos) e Informe; el resto, solo con axe.
- Los estados «extracto todo registrado» y «parcial» de Traer movimientos necesitan leer un PDF real de banco: no se armaron. Sí se vieron: con clave, pendiente, bancos sin cuenta y correo repetido (el correo repetido solo se sembró directo en la base, no entró por el canal real; su aviso «ya lo anotaste» no se pudo ver).
- Sitio desplegado: no se tocó.

## Decisiones para Daniel

1. **Zoom bloqueado** (`user-scalable=no` + bloqueo de pellizco, con prueba): da sensación de app, pero axe lo marca (WCAG 1.4.4) y quien ve poco no puede ampliar. Se dejó como estaba porque es una decisión de diseño anterior. Si quieres cumplir AA a rajatabla: quitar `maximum-scale`/`user-scalable` y `estabilidadVista.js`.
2. **Impresión**: imprimir Movimientos saca también botones y casillas. Hay exportar a Excel; no se hizo hoja de impresión.
3. **«Bancos sin cuenta»** sale ahora en 4 sitios de Traer movimientos (tarea, bloque Por revisar, franja de cobertura, tarjeta de correo). Propuesta: dejar tarea + franja.
4. **Sincronización**: las casillas mes x cuenta miden 36x40 (se dejaron por ancho); un cambio a 44 las haría deslizar de lado.
5. Etiquetas accesibles de «Ver detalle de …» y «Editar …» no incluyen el texto visible completo (avisos menores de axe).
6. Colores de la lista de Categorías (la persona los elige) y las banderas/Google se dejaron fijos a propósito.
7. Axe marca `region` en casi todas las pantallas: ruido de contenedores, no se tocó.
