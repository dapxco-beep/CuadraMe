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
