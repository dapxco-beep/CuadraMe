# Nombre propio de un movimiento («título»)

La persona puede ponerle SU nombre a un movimiento («Pago PSE ... 884221» pasa a «Recibo de la luz») para saber de qué es.

## Decisión de diseño
- **El texto del banco no se toca.** `Movimiento.descripcion` sigue siendo el original. El anti-duplicados (`duplicados.py`, huellas por canal), el cuadre con extractos, las reglas por comercio (`huella_de`, `reglas_categoria`, memoria/autocat) y el modelo leen siempre la descripción. Por eso el nombre va en una columna aparte: `movimientos.titulo` (VARCHAR NULL, máx. 80).
- **Se muestra `titulo || descripcion`** en lista, tabla, detalle, inicio, cuenta y exportación. Cuando hay título se ve «Banco: …» en pequeño. La búsqueda (`GET /movimientos?q=`) y el filtro local encuentran por ambos textos.
- **Exportar** (CSV/Excel): «Descripción» trae el nombre propio (o el del banco) y se agrega al final la columna «Texto del banco».
- **No afecta montos ni cuadre**: solo se guarda un texto.
- Limpieza (`app/titulo.py::limpiar`): sin etiquetas HTML, espacios colapsados, máximo 80. Vacío = sin título (vuelve el original).

## Dónde se pone
| Dónde | Cómo |
|---|---|
| Revisión de extractos (`SubidaMultiple`) | Lápiz junto a cada línea; campo con el original como pista. Viaja en `POST /conciliacion/historial/{id}/importar` (`titulos: {fingerprint: nombre}`, `recordar_titulo: [fingerprint]`) y queda en `review_json` (`titulo`). Si la línea completa un movimiento que ya existía, el nombre pasa a ese movimiento. El borrador de `lib/retomar.js` guarda también `titulos` y `recordarTitulo`. |
| Archivos CSV/Excel | `filas[].titulo` en `POST /importar/confirmar`. |
| Correos «Por revisar» | Lápiz en la tarjeta; viaja en `POST /correos/{id}/aprobar` (`titulo`, `recordar_titulo`). No hace falta columna en `CorreoGasto`: el nombre solo existe al aprobar. |
| Detalle | Lápiz junto al nombre (guarda al instante) y campo «Nombre (para ti)» en Editar. `PUT /movimientos/{id}` con `titulo` (`""` lo quita). |
| Lista | Lápiz en cada fila (se oculta en modo selección); abre una hoja con el editor. |
| Crear a mano | `POST /movimientos` acepta `titulo`. |

## «Recordar este nombre para este comercio»
- Tabla `reglas_titulo` (usuario, `huella`, `titulo`). La huella es `pendientes.huella_de(descripcion)`, la misma de las reglas de categoría. Huellas demasiado genéricas («pago») no se guardan.
- **Solo si la persona lo pide** (`recordar_titulo`). La casilla sale apagada, salvo que el comercio ya se repita ≥ 4 veces (`MIN_REPETICIONES`, igual a `pendientes.MIN_REPETICIONES_PENDIENTE`).
- Se aplica a movimientos NUEVOS: crear a mano, atajo, aprobar correo, importar extracto (incluye la auto-importación) y archivos. Los ya existentes no se renombran solos.
- Para olvidarlo: quitar el nombre con `recordar_titulo: true`.

## Migración
`0004_titulo_personalizado` (al final de `migraciones.py`; 0001-0003 no se tocan): `ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS titulo`, `CREATE TABLE IF NOT EXISTS reglas_titulo` e índice por usuario. La tabla nueva tiene `usuario_id`, así que entra sola al borrado/descarga de datos del titular.

## Límites conocidos
- Los informes que arman sus propias filas (p. ej. «qué pasó con tu dinero») siguen mostrando el texto del banco si el endpoint no trae `titulo`.
- Un nombre elegido para una línea que el servidor reconoce como duplicado ya registrado no se guarda (no se crea movimiento).
