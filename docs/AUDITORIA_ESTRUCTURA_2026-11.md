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
- **No se unió «Traer movimientos»** (extractos + correo + registro automático): existe una decisión previa de producto
  (commit fc66f31) que los separó a propósito (cierre mensual vs avisos del día). Se respetó.
