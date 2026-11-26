# Auditoría y rediseño UX/UI integral — 2026-11-26

Rama `ux/rediseno-integral` (worktree `wt-rediseno`), base `9bdf1a6` = producción web. API en producción `0c1cc78`.
Sin push, sin deploy, sin cambios en backend, `models.py`, migraciones ni dependencias.

## Método
- Recorrido automatizado en Chrome de **35 pantallas × 8 anchos** (360, 390, 430, 768, 1024, 1280, 1440, 1920) con datos de demostración y otro con **usuario nuevo** (una cuenta, sin movimientos) para los estados vacíos. Capturas en 390, 768, 1280 y 1440.
- Medición objetiva por pantalla: desbordes, errores de consola/5xx, áreas táctiles (sondeadas con `elementFromPoint`, que cuenta rellenos invisibles), texto menor de 12 px, nombres accesibles.
- Revisión visual de hojas de contacto antes/después; contraste WCAG de los componentes cambiados en **56 combinaciones** (8 temas × sin acento + 6 acentos).
- Revisión del código: uso del sistema de componentes (`Boton`, `Chip`, `Tarjeta`, `Campo`) contra elementos sueltos.

## Lo que la auditoría desmintió (para no repetirlo)
La primera pasada del medidor dio 340 «áreas táctiles pequeñas», 72 «controles sin nombre» y 2 `h1` en Impuestos. **Eran falsas alarmas**: (1) el medidor no veía los rellenos táctiles invisibles ni medía lo que estaba fuera de pantalla; (2) los campos de búsqueda y casillas sí tienen `<label>`; (3) el segundo `h1` de Impuestos es solo para impresión (`hidden print-only`). Con la sonda corregida, lo único real era el calendario de gasto por día (38 px). El trabajo previo de accesibilidad de la otra sesión estaba bien hecho.

## Hallazgos
Severidad: **P0** impide usar / rompe función · **P1** jerarquía, consistencia, responsive · **P2** refinamiento.

| # | Pantalla | Hallazgo (evidencia) | Sev. | Estado |
|---|---|---|---|---|
| 1 | Todas | **Sin P0**: 0 desbordes horizontales, 0 errores de consola, 0 respuestas 5xx en 348 mediciones | — | verificado |
| 2 | Presupuesto, Pagos fijos, Metas, Inversiones, Cuentas, Deudas | Los botones de acción («+», pasar plata, ayuda) caían en una **fila propia y sola** bajo las pestañas (~64 px muertos en 6 pantallas) | P1 | **hecho** |
| 3 | Inicio | «Pon CuadraMe en tu celular» y «¿Cómo quieres usar CuadraMe?» (~350 px) iban **antes del saldo**; en 390 px el saldo quedaba en la parte baja de la primera pantalla | P1 | **hecho** |
| 4 | Toda la app | **Botones principales con 7 recetas** (radio xl/2xl, altura por relleno, texto 12/14/15 px) en 146 sitios, frente a 87 `<Boton>` y 807 `<button>` sueltos en total | P1 | **hecho** (146 botones; candado en pruebas) |
| 5 | Pagos fijos | 9 botones «Agregar» idénticos y principales: ruido que compite con «Agregar todos» | P1 | **hecho** |
| 6 | Presupuesto, Metas (768–1023 px) | Tableta = columna de móvil estirada a ~700 px, líneas de texto muy largas | P1 | **hecho** (2 columnas desde 768 px) |
| 7 | Barra lateral (escritorio) | Cada sección con descripción de 4–5 líneas: muro de texto | P1 | **hecho** (solo en la activa; tooltip y lectores en las demás) |
| 8 | Informes > Gastos | Calendario de gasto: celdas de 38 px | P2 | **hecho** (44 px) |
| 9 | Toda la app | Rótulos en mayúsculas de 11 px | P2 | **hecho** (12 px) |
| 10 | Registrar movimiento | «Frecuentes» corta el nombre («Corral hambur…») | P2 | **hecho** (2 líneas) |
| 11 | Movimientos | Encabezado con 6 grupos de controles antes de la primera fila; filas de ~95 px (categoría y lápiz en una tercera línea) | P1 | **pendiente** (filas con deslizar, virtualización y áreas táctiles delicadas: requiere diseño propio) |
| 12 | Presupuesto | Tarjeta por categoría de ~180 px con frase larga y «✕» de borrado siempre visible | P1 | **pendiente** (quitar el ✕ cambia un comportamiento) |
| 13 | Metas | Cada meta con 4 párrafos; el progreso debería dominar | P2 | pendiente |
| 14 | Cuentas | 3 enlaces secundarios repetidos por cada cuenta | P2 | pendiente |
| 15 | Informes > Gastos (cuenta vacía) | Tres bloques vacíos apilados (resumen, calendario de ceros, costos) | P2 | pendiente |
| 16 | Estados vacíos | **Fortaleza**: ilustración, mensaje y acción propios por módulo | — | conservar |
| 17 | Temas | Contraste del botón principal ≥ **5,93:1** y del secundario ≥ 13,8:1 en las 56 combinaciones | — | verificado |

## Antes / después (mismo auditor, 35 pantallas)
| Medida | Antes | Después |
|---|---|---|
| P0 (desbordes, errores) | 0 | 0 |
| Celdas del calendario < 44 px (360 y 390) | 21–28 | **0** |
| Elementos con texto < 12 px, 390 px | 56 | **24** |
| Elementos con texto < 12 px, 1280 px | 446 | **199** (restan atajos de teclado decorativos «N», «G I») |
| Botones principales armados a mano | 146 | **0** (candado en pruebas) |
| Filas de acciones solas bajo pestañas | 6 pantallas | **0** |

## Cambios (4 commits sobre `9bdf1a6`)
1. `789d3c2` Composición: acciones en la línea del título (`AccionesPantallaContext` + `EncabezadoPantalla`) y dos columnas en tableta.
2. `bbec7d4` Jerarquía: Inicio muestra primero el saldo; barra lateral sin muro de texto.
3. `4282920` Consistencia: botón principal único (`.btn .btn-primario`, `.btn-grande`, `.btn-sm`), calendario táctil, Pagos fijos más sereno, rótulos de 12 px, frecuentes en 2 líneas.
4. `a642fee` Pruebas (13 nuevas) y candado contra botones principales sueltos.

No se cambió ningún color, tipografía, token ni logo: los botones usan el mismo `--color-accent`/`--color-paper-raised`.

## No abordado en esta entrega (alcance del encargo que queda abierto)
Movimientos (11), tarjetas de Presupuesto (12), Metas (13), Cuentas (14), unificación de modales/drawers, revisión de microinteracciones y `prefers-reduced-motion`, formularios por pasos, estados de carga y error pantalla por pantalla, y la auditoría de código de los 807 `<button>` restantes que no son principales (secundarios, chips, iconos). La auditoría de dispositivos reales (zoom ampliado, teclado móvil) tampoco se hizo: solo Chrome emulado.

## Riesgos
- La otra sesión (autor DANIEL, `wt-ux-ui`) toca los mismos archivos (Inicio, Movimientos, Cuentas, Perfil). Mi rama toca 94 archivos, la mayoría con un cambio de una línea (botones). **Antes de integrar: `git fetch` y reubicar la rama**; si hay choques, el candado de botones y `EncabezadoPantalla` se reaplican sin esfuerzo.
- El botón principal pasa de rectángulo redondeado a **píldora** (la forma que el sistema ya definía en `.btn`): es el cambio visual más notorio y conviene aprobarlo.
- Fechas de los datos de demostración antiguas: los estados «sin gastos esta semana» de las capturas no reflejan una cuenta activa.

---

# Bloque 2 (2026-11-26): Movimientos, Presupuesto, Metas y Cuentas
Base `9bdf1a6` (producción web). Sin push, merge ni deploy. Backend, API, modelos, migraciones, autenticación y dependencias sin tocar (`git diff 9bdf1a6 -- backend pwa/package*.json` vacío).

## Problemas encontrados
| # | Pantalla | Problema | Cambio |
|---|---|---|---|
| 1 | Movimientos | Encabezado con 6 grupos de controles; fila de ~95 px; muchas acciones compitiendo | 2 filas de encabezado, filtros con etiqueta, fila de ~58 px con icono de categoría, día fijo (h2) al desplazar, barra de selección clara, tabla por defecto en escritorio ≥1280 (la vista elegida se recuerda en `cuadrame:mov-vista`) |
| 2 | Movimientos | Error de carga y «sin resultados» poco distinguibles | Estados propios con acción (Reintentar / Quitar los filtros) |
| 3 | Presupuesto | Tarjeta sin cifras claras; botón de borrar siempre a un toque | Siempre Llevas · Límite · Te queda, barra con %, estado con icono y palabra; «Quitar presupuesto» solo dentro de «Ver detalle» (terciario destructivo, con Deshacer) |
| 4 | Presupuesto | **Un fallo de carga se mostraba como «Aún no tienes presupuestos»** (el `catch` se tragaba el error) | Mensaje de error real con Reintentar; no pisa datos ya cargados |
| 5 | Metas | 4 párrafos redundantes; progreso poco protagonista | Porcentaje grande, fecha y días que faltan, Llevas · Objetivo · Te falta; se quita el «Si sigues así…» cuando ya hay mensaje de ritmo y el duplicado de «Meta completada» |
| 6 | Cuentas | Etiqueta de tipo suelta junto al lápiz; una sola columna de 670 px en escritorio; error sin acción | Tipo dentro de la tarjeta (sin repetirlo si es igual al nombre), dos columnas desde 1024, Reintentar |
| 7 | Barra lateral | El CTA «Agregar movimiento» se partía en dos líneas | `whitespace-nowrap`, padding ajustado |

## Jerarquía de botones (aprobada)
Principal = píldora (`.btn-primario`). Secundario = `.btn-secundario`. Terciario = texto con color de acento. Destructivo = texto/icono `text-danger`, nunca el principal. No se convirtió ningún otro control en píldora.

## Verificación
- Pruebas: 186 archivos / 1622 pruebas en verde (nuevas: `rediseno_bloque2.test.jsx` 7, `movimientos_bloque2.test.jsx` 4; ajustada `claridad.test.jsx`). En una corrida con la máquina cargada fallaron dos pruebas ya existentes (`movimientos_rapido`, `volumen`) y en la siguiente pasaron: intermitencia por carga, no relacionada con el cambio.
- Build de producción: OK. oxlint: solo avisos ya existentes de dependencias de efectos.
- Responsive: 360, 390, 430, 768, 1024, 1280 y 1440 en las 4 pantallas: sin desborde de página y sin errores de consola. En Movimientos lo que sobresale son carriles con scroll horizontal (intencional).
- Contraste: 96 combinaciones (8 temas × 3 acentos × 4 pantallas): 0 fallos. La tarjeta «En qué gasto mi plata» (Presupuesto e Informes) daba 3,85:1 en dark/azul por usar `text-ink-soft` sobre `bg-accent-soft`; ahora usa `text-ink`.
- Estados capturados (390 y 1440): cargando, vacío, error, detalle expandido, hoja de aporte, hoja de editar cuenta y foco por teclado. Hover y disabled revisados en código (clases del sistema).

## Evidencia
`docs/rediseno-ux-capturas/bloque2/`: `CMP_movil_*` y `CMP_escritorio_*` (antes | después), `EST_390_*` (estados) y capturas sueltas. No se versiona.

## Commits
`cb27d28` Movimientos · `6f0aa54` Presupuesto/Metas/Cuentas · `93d7115` Cuentas en dos columnas · (este) error de Presupuesto, pruebas y documentación.

## Riesgos y pendientes
- La tabla por defecto en escritorio cambia un hábito; se vuelve a la lista con el selector de vista.
- Mis cuentas pasa a ancho de pantalla grande, lo que también ensancha Deudas.

- Hover/disabled sin captura; revisar en dispositivo real.
