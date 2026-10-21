# Relectura de extractos de tarjeta

## Por qué existe
Los extractos de tarjeta procesados con un lector viejo quedan (a) en la cuenta de ahorros del mismo banco y/o
(b) con menos líneas de las que hoy se leen. Antes el arreglo eran dos pasos manuales por extracto.

## Política de relectura automática (`releer_extracto.releer_pendientes`)
Al abrir «Traer movimientos» (`POST /conciliacion/releer-pendientes`), una vez por `VERSION_LECTOR` y por extracto
(marca `releer_extracto:<id>`), máximo **3 por apertura en total**:
1. Los `pendiente_revision` con correo, como siempre (reemplazan las líneas sin resolver).
2. Los `conciliado` **de tarjeta que ya están en una cuenta de crédito**, en modo **«solo agregar lo que faltaba»**:
   nunca modifica, mueve ni quita lo ya importado; las líneas nuevas entran como `faltante` y el extracto vuelve
   a `pendiente_revision` («faltan importar N»). Si la lectura de la tarjeta (`lectura_completa`) no suma lo que
   dice el extracto, no se agrega nada.
3. Un conciliado de tarjeta que está en una cuenta que NO es de crédito no se relee solo (traería líneas a la
   cuenta equivocada): lo resuelve «Arreglar mis extractos de la tarjeta».
Los conciliados que no son de tarjeta no se tocan solos. Al mejorar el lector, sube `VERSION_LECTOR`.

## Cómo se sabe que es de tarjeta
La cuenta es de crédito, o la lectura guardada trae `resumen_tarjeta`, o el asunto/archivo del correo hablan de
tarjeta de crédito (`cuentas_banco.producto_de_texto`).

## «Arreglar mis extractos de la tarjeta» (`app/arreglar_tarjetas.py`)
- `GET /conciliacion/tarjetas/arreglar/previa`: sin cambios y sin Gmail. Por extracto: mes, cuenta actual -> destino,
  movimientos que se moverán, saldos antes/después (por cuenta y total; el total no cambia), si pide clave del PDF y
  si puede releerse.
- `POST /conciliacion/tarjetas/arreglar` `{confirmar: true}`: del más viejo al más nuevo, por extracto: (1) si está en una
  cuenta que no es de crédito y hay UNA tarjeta de crédito del mismo banco -> `reasignar_extracto.cambiar`;
  (2) releer en modo «solo agregar». Un extracto que falla (Gmail, PDF, clave) se salta y se informa; los demás siguen.
  Idempotente. Máximo 12 por llamada; la app lo hace de a uno (`maximo`, `excluir`, `continuar`) para mostrar el avance.
  El límite por hora (6) cuenta la tanda, no cada paso.
- Orden importa: primero mover, para que lo ya importado se empareje en la tarjeta.

## Sin duplicar
La huella de una línea (`compute_fingerprint`) incluye el id de la cuenta, así que al mover un extracto la huella
guardada ya no coincide con la que sale al releer. `releer_extracto.reconciliar` reconoce esas líneas conservadas
(mismo día, tipo, monto y comercio parecido, 1:1) y anota la huella nueva en `huellas_alt` de la línea conservada:
no se ofrece como «por importar» ni ahora ni en relecturas futuras. Sin columnas ni migraciones nuevas.

## Corregir el monto de una línea ya importada (`app/corregir_pago.py`)
Cuando un lector nuevo lee distinto el MONTO de algo que el lector viejo ya importó, no se ofrece una segunda línea:
- **Solo con regla explícita del lector.** La línea nueva trae `corrige_lectura` = {descripción que dejaba el lector
  anterior, tipo, montos con que la leía}. Hoy hay una: el pago de la tarjeta Nu («Pago $A -$B -$C», C = A−B, se
  importó como «Pago de tu tarjeta (factura anterior)» por B). **Nunca** por parecido de monto, día o comercio.
- **Corregir:** movimiento de la misma cuenta, ±3 días, descripción vieja y monto B o C -> la línea pasa a
  `corregir_monto` (encendida por defecto). Al importar se actualiza ese movimiento (mismo id, fecha, vínculos,
  categoría y marca de traslado propio), el saldo de la cuenta cambia en A−B (cuenta bloqueada) y nunca se crea otro.
  Su descripción pasa a la de hoy y las huellas toman el monto nuevo, así la misma línea no se vuelve a ofrecer.
- **Ya duplicado** (el viejo por B y el nuevo por A): la línea vieja pasa a `quitar_repetido`; al importar se borra con
  motivo «error» (sin fantasma que bloquee), se revierte su saldo y se recalcula el ajuste inicial.
- Se marca al procesar y al releer (también en «solo agregar»: solo propone, no cambia nada hasta importar). Si el
  movimiento ya no existe al importar, la línea se importa como pago normal. Idempotente. Sin columnas ni migraciones.
- El pago de tarjeta sigue sin contar como ingreso ni gasto (regla única `contabilidad.py`, `MARCA_TRASLADO_PROPIO`).
- Para sumar otra corrección: que el lector declare `corrige_lectura` en esa línea y añadir su prueba sintética.

## Corregir el tipo: compras que se importaron como ingreso (`app/corregir_tipo.py`)
El lector viejo no veía el signo de la línea y guardó muchas COMPRAS de la tarjeta como `income`. Efecto: la tarjeta
sale con saldo positivo (a favor) en vez de una deuda, y los «ingresos» se inflan. El lector de hoy tipa bien:
compra, compra en cuotas, cuota de manejo y comisión = `expense`; solo el pago es `income` (traslado). Signos de la
cuenta de crédito (regla única `delta_saldo`): compra = `expense`, resta del saldo (la deuda es negativa); pago =
`income`, la reduce. Ni la regla única ni la paridad Python/JS cambian.

Regla de seguridad: solo cuando el lector de tarjeta lo DECLARA en la línea (`corrige_tipo: {de: income, a: expense}`
y `linea_tipo` de compra). Nunca por simple parecido; nunca toca movimientos hechos a mano, por atajo o por correo
(solo los que ese extracto importó: fuente `conciliacion_extracto/auto`, vinculados por `movimiento_id` o huella);
nunca toca pagos de tarjeta (categoría «Pago de tarjeta», marca de traslado o «Pago ...»).

Tres casos al releer (`marcar`, junto a `corregir_pago.marcar`):
1. Compra nueva (`faltante`) + ingreso ya importado que es la misma (misma cuenta, ±1 día, monto ±$1, comercio
   parecido, emparejamiento 1:1) -> la línea pasa a `corregir_tipo`. Al importar se ACTUALIZA el mismo movimiento a gasto
   (id, fecha, vínculos y huella se conservan; el saldo cambia en −2·monto; el ajuste inicial se recalcula). La
   categoría solo cambia si era de ingreso, «Otros» o la había puesto la app; una elegida por la persona no se pisa.
2. Ya están las dos (el ingreso viejo y la compra nueva importada como gasto) -> el ingreso viejo pasa a
   `quitar_repetido` con `quita_por = "tipo"`: se borra con motivo «error» (sin fantasma), se revierte su saldo, y solo si
   la compra buena sigue ahí.
3. Extractos ya releídos donde esas compras quedaron como `faltante`: la siguiente relectura las convierte a
   `corregir_tipo` (ya no se ofrecen como compras nuevas), porque `corregir_tipo` es reemplazable.
Idempotente: un movimiento corregido ya no es ingreso. Sin columnas nuevas (todo vive en la revisión guardada).

Dónde se aplica:
- «Arreglar mis extractos de la tarjeta»: la vista previa suma `movimientos_a_corregir` y `correcciones` (por tarjeta:
  cuántas y saldo antes/después, ya con lo que se mueve); es una estimación (ingresos importados por ese extracto que no
  son pagos). El POST, tras mover y releer, aplica las correcciones en el mismo paso (`aplicar_en_historial`) y las
  cuenta en `corregidos` / `repetidos_quitados`. También aplica las que una relectura automática ya había propuesto.
- «Releer este extracto» y la relectura automática (modo «solo agregar»): solo PROPONEN (`corregir_tipo` cuenta como
  corrección); la persona confirma en la hoja con «Revisar e importar». Si la lectura no suma el extracto, no se marca nada.
- Importar (`POST /conciliacion/historial/{id}/importar`): `corregidos` incluye estas; `tipos_corregidos` las separa.
Sube `VERSION_LECTOR` (v6) para que todos los extractos de tarjeta se relean una vez.

## Formatos que el lector reconoce (tarjeta Nu) y cómo pedir una muestra

El lector (`backend/app/extractos_tarjeta_nu.py`) no adivina: solo reconoce lo siguiente y, si aun así la suma no cuadra con el
resumen del extracto, deja la lectura como NO completa y no importa nada solo.

| Qué | Cómo lo reconoce |
|---|---|
| Pago o abono | La descripción empieza por «Pago» o «Abono», o la fila está bajo un título «Abonos». Nunca se tipa como compra; entra como pago (traslado propio, jamás ingreso). |
| Cuota de manejo | «Cobro por cuota» (con o sin «de manejo» en la línea siguiente), «Cuota de manejo», «Cargo por cuota», con uno o varios importes en columnas distintas. |
| Intereses del mes | Si el resumen trae «Intereses» y no hay una fila de intereses, se agrega una línea de gasto «Intereses de tu tarjeta» fechada el día del corte. |
| Deuda al corte | `usado` del resumen (cupo − disponible). Si no se lee, se estima con deuda a pagar + deuda restante + cuota de manejo + cargos por conversión + intereses y queda marcada «estimado». |

Cadena que debe cuadrar: deuda al corte = deuda del corte anterior + compras (por su valor completo el día de la compra) + cuotas de
manejo + comisiones + intereses − pagos.

### Si un extracto no se reconoce

La app lo avisa en la salud de datos («extracto de tarjeta con formato no reconocido») con la acción «Mándame este extracto (sin datos
personales) para aprender su formato». No se envía nada solo. Para la muestra: tapa nombre, cédula, dirección y los últimos dígitos de la
tarjeta (los importes y las fechas sí sirven), y pásala al equipo; con ella se agrega el formato y una prueba con cifras inventadas.

## Formatos viejos de la tarjeta Nu (may–ago) y la fórmula del resumen

Además de lo anterior, el lector reconoce (probado con 4 extractos sintéticos en `backend/tests/fixtures/extracto_tarjeta_nu_viejo_*.txt`):

| Línea | Qué es |
|---|---|
| «Gracias por tu pago $A -$A $0,00» (o «$A $0,00 $0,00») + sub-líneas capital / intereses / cargos | Un PAGO por A (primer importe), igual que «Pago». Lo que el lector anterior guardó como «Gracias por tu pago» se reconoce por su huella y no se duplica. |
| «Cuota por avance a cuenta $V 1 de 1 $V 2.07% $I $T $0» + «↪ Comisión por servicio $C» (T = V + C + I) | Tres gastos en la tarjeta: el avance por V (marcado como posible traslado propio: el dinero llegó a tu cuenta de ahorros), la «Comisión por servicio de avance» C y «Intereses de tu tarjeta» I. |
| Fila sin descripción «15 JUL 2026 $0,00 $0,00 2.07% $I $I $0,00» | El cobro de intereses del periodo (gasto «Intereses de tu tarjeta», fecha del corte). |
| Cuota de manejo, intereses o comisión por servicio que el RESUMEN trae y la tabla no lista | Se agrega UNA línea por la diferencia, fechada el corte y marcada `desde_resumen`. Solo agrega; si las líneas ya suman más que el resumen, la lectura queda incompleta. |
| Compra en cuotas «2 de 6», «3 de 6»… con fecha anterior al periodo | Cuota de compra anterior: no es un movimiento nuevo, solo cuenta en la verificación. La compra cuenta completa el día de la compra. |

### Verificación (lectura completa)

1. `deuda_a_pagar` = suma del «total a pagar» de las líneas que NO son cuota de manejo, intereses ni comisiones (un avance cuenta por V; también se acepta por T, si cuadra exacto).
2. Restante, cuota de manejo y pagos (capital + intereses + cargos = A), como antes.
3. Fórmula maestra: `usado = deuda a pagar + deuda restante + cuota de manejo + cargos por conversión + intereses + comisiones de servicio y de avance − abonaste`. Se exige solo cuando el propio resumen la cumple; entonces cada término se rearma desde las líneas.
4. Cadena entre extractos: `usado(k) = usado(k−1) + compras completas + avances + comisiones + intereses + manejo − pagos`.

Si algo no cuadra, la lectura queda NO completa, no se importa nada solo y salud de datos ofrece «Mándame este extracto (sin datos personales)…».

### Autoarreglo y lecturas de Gmail

- La verificación de cada extracto se guarda por (extracto, versión del lector) en `marcas_cron` (`autoarreglo_sv:<id>` = `<versión>|falso|<fecha>` o `|nulo|`): «no suma» no se vuelve a descargar con la misma versión; «no pude medirlo» se reintenta tras 6 horas.
- Una lectura marcada incompleta por un lector anterior se vuelve a medir UNA vez con el de hoy.
- Las tarjetas dejan siempre una lectura de cada llamada a los ajustes de ahorros (4x1000, rendimientos, costos por retiro), y un extracto que no verifica no frena a los demás: queda como decisión «extractos de tarjeta que no pude comprobar».
- El cuadre por cuenta de tarjeta trae `cortes` (cada corte: «debo al corte» = `usado` o no, y por cuánto) y `desde`.
