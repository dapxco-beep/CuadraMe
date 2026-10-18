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
