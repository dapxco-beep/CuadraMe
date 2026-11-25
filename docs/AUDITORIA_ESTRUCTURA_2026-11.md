# Auditoría de diseño y estructura (noviembre 2026)

Revisión pantalla por pantalla (41 pantallas, celular 390 px y computador 1536 px, con los datos de demostración; ver
`docs/AUDITORIA_VISUAL.md`) y evaluación de qué secciones se pueden unir, simplificar o conectar.

## Hallazgos visuales
- Ninguna pantalla se desborda de lado. Estilo coherente (crema, naranja, tarjetas).
- Corregido: botón «+» solo en una fila vacía (Categorías, Reglas, Patrimonio); «Ver las N categorías» escondido;
  mayúsculas en cada palabra en el selector de «Mi mes»; «sin base para comparar» que sacaba el monto de la fila.
- Pendiente (decisión de diseño): botones de agregar de dos colores (naranja y negro), encabezados con flecha redonda o suelta,
  tarjetas de Cuentas con etiqueta lateral, gráfica «Cómo ha cambiado» de Patrimonio vacía con datos de demostración.

## Qué se unió (2026-11-24)
| Antes (pantallas sueltas) | Ahora |
|---|---|
| Presupuesto + Pagos fijos | `/presupuesto` con pestañas «Presupuesto» y «Pagos fijos» |
| Metas + Inversiones | `/metas` con pestañas «Metas» e «Inversiones» |
| Cuentas + Deudas | `/cuentas` con pestañas «Cuentas» y «Deudas» |
| Ayuda + Aprende | `/ayuda` con pestañas «Ayuda» y «Aprende» |
| Impuestos | pestaña «Impuestos» dentro de `/informes` |

Las rutas viejas (`/recurrentes`, `/inversiones`, `/deudas`, `/aprende`, `/impuestos`) redirigen a su pestaña y conservan la
consulta. El buscador del menú las sigue encontrando (`EXTRA_BUSQUEDA` en `lib/navegacion.js`). El menú «Más» tiene 5 entradas
menos. Cada pantalla se muestra sin su encabezado propio dentro de la pestaña (`useEmbebido`).

## Por qué no se unió más (pendiente, en orden de valor)
1. **Traer movimientos**: `/sincronizacion` ya reúne extractos, correo y conexiones; falta sumar «Registro automático»
   (`/conectar-dispositivo`, atajos) como pestaña. Es la pantalla más grande (1.768 líneas): conviene partirla antes.
2. **Revisar movimientos** (traslados y repetidos) podría vivir dentro de Movimientos («Más acciones»).
3. **Informes**: Mi mes, Días, Patrimonio y Cierre mantienen su diseño anterior; rediseñarlas con el mismo lenguaje que
   Gastos (resumen, hallazgos, paneles personalizables). «Cierre» y «Mi cuenta cuadra» se solapan.
4. **Costos** («Lo que te cuesta tu plata») hoy es un enlace desde Gastos; podría ser un panel de Gastos.
5. **Asistente**: es una función aparte; valorar que «Ayuda» lo sugiera como primera opción.
6. Preguntar el perfil de uso al entrar a una cuenta nueva (hoy está en Perfil).

## Cosas que están y casi no se usan (por confirmar con datos de uso)
No hay analítica de uso por pantalla. Antes de quitar nada, medir (de forma anónima y con consentimiento) qué pantallas se
abren: candidatas a revisar son Ahorcado/juego, Costos, Enseñar categorías y Impuestos.

## Segunda tanda (2026-11-24)
- **Botones y encabezados unificados**: la acción principal es naranja en toda la app (97 botones; quedan oscuros solo los avisos
  flotantes, tooltips y burbujas de chat) y todas las flechas de volver son redondas (20).
- **Costos** ya es un panel de Gastos («Lo que te cuesta tu plata»); `/costos` lleva a ese panel.
- **Revisar traslados y repetidos** se abre desde «Más acciones» de Movimientos (sigue en el buscador; salió del menú).
- **Cierre / «Mi cuenta cuadra»**: ya eran la misma pestaña (`/mi-cuenta-cuadra` redirige a Cierre). Sin cambios.
- **Días**: dentro de Informes ya no repite el enlace a Gastos ni el chat (que duplicaba al Asistente: ahora es un acceso al
  Asistente); gráfica nueva «¿Qué día gastas más?» (promedio por día de la semana, con 2 semanas o más de datos).
- **Patrimonio**: con un solo punto de historia explica por qué falta la gráfica en vez de dibujar un punto suelto.
- **Medición anónima de uso** (opt-in «estadísticas anónimas», sin migración): se cuenta qué pantallas se abren (solo la ruta,
  sin usuario). Lectura interna: `GET /formas-asunto/cron/pantallas` con el secreto de los crons. Con unas semanas de datos se
  decide qué sobra (candidatas: Ahorcado/juego, Enseñar categorías).
- **«Traer movimientos» unido** (por pedido de Daniel, 2026-11-25): una sola entrada del menú y una pantalla con pestañas
  «Extractos», «Correo» y «Automático» (registro automático/atajos). Antes (commit fc66f31) extractos y correo estaban separados
  a propósito; `/movimientos-correo`, `/conectar-dispositivo` y `/sincronizacion` siguen funcionando (redirigen a su pestaña y
  conservan el estado de navegación).
- **Tarjetas de Cuentas** a ancho completo (antes una columna lateral las dejaba de distinto ancho); «Ver sus movimientos» a la
  izquierda y tipo + editar a la derecha, en una sola fila.
- **Invitación «¿Cómo quieres usar CuadraMe?»** en el Inicio (una vez, solo si ya hay 3+ movimientos y no se ha elegido perfil).

## Tercera tanda (2026-11-25)
- **Perfil** reordenado: «Cómo uso CuadraMe» (abierta), «Apariencia y letra» y «Punto de partida» son secciones separadas (antes todo
  iba en una sola sección plegada).
- **Mi mes**: ya era una historia de 5 tarjetas; ahora Cuadri reacciona en cada una (radiante si ahorraste, preocupado si el gasto
  subió, celebra una buena racha). Si se apaga «Mostrar a Cuadri» vuelve el emoji. La imagen que se comparte no cambia.
- **Cierre**: barra de avance «N de 3 revisiones listas» con Cuadri que se anima (`avanceCierre` en `lib/cierreAsistente.js`).
- **Agregar**: muestra el nombre de la cuenta elegida y las tarjetas de cuenta son compactas.
- Pendiente: Wallet del iPhone (necesita la captura de la notificación de Nu al pagar con Wallet).
