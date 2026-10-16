# Subcategorías

Un nivel opcional de detalle DENTRO de una categoría: Transporte → Gasolina, Uber, Peajes.

## Modelo (lo menos invasivo)

La app referencia las categorías por **nombre** (movimientos, reglas, presupuestos, recurrentes). Las
subcategorías siguen la misma convención, así nada existente cambia:

| Dónde | Qué | Migración `0003_subcategorias` |
|---|---|---|
| tabla `subcategorias` | `id, usuario_id, categoria_padre (nombre), nombre, orden, creado_en` | `CREATE TABLE IF NOT EXISTS` + índice por usuario |
| `movimientos.subcategoria` | VARCHAR NULL | `ADD COLUMN IF NOT EXISTS` |
| `reglas_categoria.subcategoria` | VARCHAR NULL | `ADD COLUMN IF NOT EXISTS` |

NULL = «solo categoría» (todo lo anterior queda igual). No se tocaron 0001 ni 0002 ni `contabilidad.py`.

**La categoría padre sigue siendo la que agrega**: informes, presupuestos, gráficas, asistente y la regla
contable única leen `movimientos.categoria`. La subcategoría solo desglosa; ninguna cifra cambia por tenerlas.

## Reglas de integridad

- Un solo nivel: el padre de una subcategoría siempre es una categoría (no hay sub-subcategorías).
- Nombre único por (usuario, padre), sin distinguir mayúsculas. El mismo nombre puede existir en otro padre.
- Categorías de sistema (`es_sistema`, Transferencias, pago de tarjeta, 4x1000, intereses…) no admiten
  subcategorías: no se podrían usar sin riesgo para la regla contable.
- **Renombrar** una categoría renombra el padre de sus subcategorías (si el nombre nuevo ya tenía una igual, se fusionan).
- **Eliminar** una categoría: sin uso, sus subcategorías se borran con ella; con uso (`mover_a`), las subcategorías
  y los movimientos pasan al destino (fusión por nombre). Si el destino es de sistema, los movimientos pierden la subcategoría.
- **Renombrar** una subcategoría la renombra en sus movimientos y reglas. **Borrarla** NO borra movimientos: quedan
  solo con su categoría.
- Cambiar la categoría de un movimiento (o de una regla) sin indicar subcategoría limpia la anterior. Pedir una
  subcategoría que no es de esa categoría responde 400.
- Una subcategoría de un movimiento se valida contra las del usuario (aislado por `usuario_id`).

## Endpoints

- `GET /subcategorias[?categoria=]`, `POST /subcategorias {categoria, nombre}`, `PUT /subcategorias/{id} {nombre}`,
  `DELETE /subcategorias/{id}`. Cada fila trae `movimientos` (cuántos la usan).
- `subcategoria` opcional en: `POST/PUT /movimientos` (`""` la quita), `recategorizar-comercio`, `recategorizar-masivo`,
  `reglas-categoria` y `reglas-categoria/aprender`. `MovimientoOut` y `ReglaCategoriaOut` la devuelven.
- `GET /informes/gasto/subcategorias?categoria=&periodo=` → desglose de UNA categoría (incluye «Sin subcategoría», al final).
  La suma es exactamente el total de la categoría. `informes/gasto/movimientos` también trae la subcategoría de cada fila.

## Aprendizaje (nada de inventar)

- Una regla de comercio puede guardar categoría + subcategoría; al categorizar un movimiento nuevo con esa regla se
  asigna también la subcategoría (si todavía existe).
- La memoria del usuario (`memoria_usuario`) solo propone subcategoría si el usuario YA la usó con ese comercio y
  domina (más de la mitad de las veces que lo puso en esa categoría). El diccionario y el modelo de palabras nunca la proponen.

## Pantallas (móvil, 390 px; modo simple: no estorba)

1. **Categorías**: cada categoría tiene un `›` (con el número de subcategorías); al abrirla, lista + «Agregar subcategoría»
   (nombre y un toque), editar y borrar (la confirmación dice que los movimientos siguen en la categoría).
2. **Selector de categoría** (`SelectorCategoria`): tocar una categoría sin subcategorías guarda de una, como siempre.
   Si tiene, se abre un 2.º paso: chips de subcategorías, «+ Nueva subcategoría» (crea y asigna en un toque) y
   «Solo {categoría}» para saltarlo. «Con subcategoría» (al pie) permite crear la primera en una categoría que no tiene.
   `PorCategorizar` usa `conSubcategorias={false}` (sigue en un paso).
3. **Movimientos / detalle**: «Transporte · Gasolina». Al editar un movimiento, el selector de subcategoría aparece
   solo si la categoría tiene.
4. **Informe**: al tocar la categoría, arriba del listado va el desglose por subcategoría. **Presupuestos**: cada
   presupuesto con subcategorías muestra «Ver por subcategoría» (mes actual). El límite sigue siendo de la categoría.

Textos según `docs/GUIA_DE_TEXTOS.md` (tú, frases cortas, botón con verbo, error = qué pasó + qué hacer).

## Pendiente / decisiones abiertas

- El CSV/Excel de `exportar` no incluye aún la columna subcategoría (no se tocó el formato).
- Deshacer una recategorización que solo agregó subcategoría (misma categoría) restaura la categoría pero no limpia la subcategoría.
- Presupuestos por subcategoría no existen a propósito: el límite es de la categoría.
