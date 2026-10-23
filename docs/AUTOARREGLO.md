# Autoarreglo: la app ordena sola las cuentas

Hasta ahora cada reparación pedía que la persona tocara un botón y confirmara (arreglar tarjetas, completar
rendimientos, releer, reintentar errores...). El **autoarreglo** (`backend/app/autoarreglo.py`) las ejecuta solas,
para cualquier cliente, de forma **segura, visible y reversible**. Los botones manuales siguen existiendo como respaldo.

## Qué es automático

`correr` hace, en este orden e idempotente, 6 pasos (cada uno devuelve qué hizo):

| # | Paso | Qué hace | Condición para actuar |
|---|---|---|---|
| 1 | `errores` | Reintenta los extractos que fallaron por la clave del PDF | Ya hay una clave guardada |
| 2 | `tarjetas` | Pasa el extracto de tarjeta a la cuenta de crédito del mismo banco, lo relee con el lector de hoy, corrige pagos (`corregir_monto`) y tipos (`corregir_tipo`: compras guardadas como ingreso) y quita repetidos | Hay **UNA** sola tarjeta candidata **y** la lectura está verificada (`lectura_completa`: suma lo que dice el resumen del extracto) |
| 3 | `ajustes` | Registra rendimientos, 4x1000 y costos por retiro de extractos de ahorro | La lectura del resumen cuadra (lo que no cuadra queda apagado) |
| 4 | `importar` | Importa las líneas `faltante` de extractos con lectura verificada | `lectura_completa` o las líneas explican el cambio de saldo del extracto; la línea no es dudosa; el extracto no tiene correcciones pendientes |
| 5 | `inicial` | Recalcula el ajuste inicial por cuenta | Reglas de siempre: no toca tarjetas, ni saldo fijado a mano, ni el modo «hoy» |
| 6 | `cuadre` | Solo lee: por cuenta, «Cuadra todos los meses» o el primer mes que no cuadra con su causa | Siempre (`cierre_extractos.cuadre_por_cuenta`, que reutiliza `cuadre_encadenado.calcular`) |

## Qué es sugerido (queda para la persona)

El aviso lo dice con una acción de un toque; nada de esto se decide solo:

- **Líneas dudosas** (`lectura_dudosa`, varios montos, `pago_detalle`, línea apagada por no cuadrar): `dudosas`.
- **Varias tarjetas del mismo banco**: no se mueve nada, `varias_tarjetas`.
- **Falta la clave del PDF**: `clave_pdf`.
- **Extractos de tarjeta que no se pudieron comprobar** contra su resumen: no se tocan, `tarjeta_sin_verificar`
  (no se vuelven a descargar hasta que mejore `VERSION_LECTOR`).
- Correcciones (`corregir_*`) que quedan pendientes en un extracto: ese extracto no se importa solo.

## Qué NUNCA se toca

Movimientos manuales, de correo o de atajo; inventar saldos; mover dinero entre cuentas sin certeza; una tarjeta sin lector
verificado; el modo «hoy» del punto de partida (lo anterior al inicio no se importa); un extracto que la persona deshizo.

## Cómo se ve (PWA)

Aviso discreto en **Inicio** y **Traer movimientos** (`AvisoAutoarreglo.jsx`): mientras trabaja «Estoy ordenando tus
cuentas… (2 de 6)»; al terminar «Listo, ordené tus cuentas: moví 4 extractos a tu tarjeta, corregí 31 compras,
registré 12 rendimientos e impuestos» con **Ver qué hice** (cuenta por cuenta, saldos de antes y después, cada cambio) y
**Deshacer**. Corre una vez por sesión y como mucho una vez por hora (`lib/autoarreglo.js`), sin bloquear la pantalla.

## Snapshot y cómo deshacer

Cada fase (mover, releer, corregir, importar...) compara una **foto** de movimientos, extractos y saldos antes y después
y guarda las diferencias en la tabla **`arreglos_auto`** (migración `0010_arreglos_auto`), agrupadas por `lote_id`:

| Tipo | Qué guarda |
|---|---|
| `mover_cuenta`, `corregir_tipo`, `corregir_monto` | antes/después de cuenta, tipo, monto, fecha, descripción |
| `quitar_repetido` | el registro completo del movimiento borrado (para volver a crearlo) |
| `crear_linea`, `ajuste_inicial` | lo creado/cambiado (el ajuste inicial se recalcula solo y también se deshace) |
| `historial` | el extracto antes (cuenta, estado, revisión) y una huella del después |
| `saldo` | saldo de cada cuenta antes y después (para «Ver qué hice») |

- `GET /autoarreglo/lotes`: lo hecho por lote (conteos, texto, saldos antes/después por cuenta, detalle, `deshacible`).
- `POST /autoarreglo/lotes/{lote}/deshacer`: revierte el lote **completo, en orden inverso**, con bloqueo de las cuentas
  (siempre por id). **Idempotente** (`ya_deshecho`). Si algo posterior cambió una de las cosas del lote (por ejemplo la
  persona editó a mano una compra corregida) responde **409 y no cambia nada**.
- Tras deshacer: esos extractos no se vuelven a ordenar solos (`autoarreglo_no:<id>` en `marcas_cron`) y el orden
  automático se **pausa 24 horas** (`autoarreglo_pausa`).
- Límite conocido: al recrear un movimiento borrado no se restauran sus huellas de origen (canales de duplicados).
- `arreglos_auto` guarda montos, ids y descripciones cortas; en `antes` de las filas `historial` va la revisión del
  extracto, que salió de un correo: por eso la tabla **no viaja en los respaldos** (`backup.TABLAS_NO_RESPALDADAS`) y sí
  se exporta y se borra con los derechos del titular (tiene `usuario_id`).

## Límites y concurrencia

- **Candado por usuario** (`autoarreglo_candado` en `marcas_cron`, atómico por la restricción única): un lote a la vez; una
  segunda llamada responde `ocupado` sin hacer nada. Un candado de más de 10 minutos (proceso caído) se reemplaza.
- **Por llamada**: `MAX_PASOS_POR_LLAMADA = 3` lecturas de PDF/Gmail y 25 s de tiempo. Lo que falte sigue en la siguiente
  llamada (una cuenta grande converge en varias aperturas). `estado: 'trabajando'` = queda trabajo y esta llamada avanzó.
- **Por hora**: `LIMITE_RELECTURAS_HORA = 24` lecturas por persona (`autoarreglo-relectura:<id>`) y 60 llamadas
  (`autoarreglo:<id>`, 429 con mensaje amable). Si se acaba el cupo la respuesta es `limite_alcanzado` y sigue después.
- **Tolerante a fallos**: un paso que falla queda como `fallo` en `pasos` y los demás siguen; `correr` nunca lanza.
- Un lote se mantiene abierto entre llamadas hasta que no queda trabajo (máx. 6 h); así el aviso final cuenta TODO.

## Cómo se dispara

1. **Al abrir la app** (Inicio y Traer movimientos): `POST /autoarreglo/correr`, una vez por sesión y por hora; la PWA
   repite mientras diga `trabajando` (máx. 12 rondas, con pausa corta). En el servidor, si la última corrida fue hace menos
   de 5 minutos y nada la reclamó, responde `omitido`.
2. **Cron diario de correos** (`/correos/cron/sincronizar`): tras leer los correos, a cada usuario con Gmail y lectura de
   extractos activada (máximo `MAX_AUTOARREGLO_POR_CRON = 10` por corrida). La respuesta trae `ordenados`.
3. **Tras subir o releer un extracto**: `autoarreglo.pedir` deja una marca (`autoarreglo_pedido`) y la próxima apertura corre
   sin esperar el intervalo.

La respuesta de `correr` trae además `decisiones` y `cuadre` (por cuenta: `cuadra` / `no_cuadra`, con el primer mes
y su causa).


## Guardia de coherencia (`backend/app/guardia_coherencia.py`)

Las reglas sueltas de `ingresos_sueltos.py` arreglan cada forma del problema; la **guardia** mira lo que QUEDA con una sola
pregunta y **nunca escribe**: «¿todo lo importado de un extracto tiene respaldo en ese extracto?». Solo mira extractos leídos
**completos** (el más reciente de cada corte; misma regla que `_verificada`).

`revisar(db, usuario_id, cuenta)` devuelve hallazgos `{movimiento_id, motivo, texto, severidad}` (`revisar_usuario` los trae de
todas las cuentas, con `cuenta_id` y `cuenta`). Motivos estables:

| Motivo | Severidad | Qué significa |
|---|---|---|
| `sin_respaldo_en_extracto` | alta | Movimiento importado, dentro del periodo, que ninguna línea del extracto trae (residuos) |
| `tipo_distinto_al_extracto` | alta | Hay una línea de ese valor pero con otra dirección (ingreso falso con su compra buena) |
| `repetido_frente_al_extracto` | alta | El extracto trae un solo movimiento igual y aquí hay dos (pago repetido) |
| `pareja_inexistente` | media | Línea «completada/aproximada» cuyo movimiento ya no existe (o no tiene) |
| `pareja_en_otra_cuenta` | media | Su movimiento vive en otra cuenta |
| `pareja_de_otro_comercio` | media | Línea aproximada emparejada con un movimiento de otro comercio con el mismo valor |

Dónde sale: `autoarreglo.correr` → `coherencia: [...]` (al final, después de los pasos; vacío si todo está bien) y
`GET /conciliacion/cuadre/encadenado?cuenta_id=…` → campo nuevo **opcional** `coherencia` (lista de la cuenta). Ambos son campos
añadidos: el front que no los conoce no se rompe.

## Registro por movimiento

`autoarreglo.historia_de_movimiento(db, usuario_id, movimiento_id)` y `GET /autoarreglo/movimientos/{id}/historia` cuentan, con
la tabla `arreglos_auto`, qué se le hizo a UN movimiento: `{movimiento_id, existe, historia: [{fecha, texto, lote_id, tipo,
deshecho}]}` (de lo más viejo a lo más nuevo), con frases como «El 23 de octubre quité este movimiento porque era repetido de
otro.» y, si se deshizo, «El 24 de octubre deshiciste ese arreglo…». Aislado por usuario: un movimiento ajeno responde 404; uno
propio sin arreglos, `historia: []`. Un movimiento ya borrado conserva su historia (`existe: false`).

## Alerta de mes que deja de cuadrar

Tras `cierre_extractos.cuadre_por_cuenta` (paso `cuadre`), `avisar_cuadre_roto` compara con la marca `cuadre_estado:<cuenta_id>`
de `marcas_cron` (`cuadra` o `no_cuadra|<mes>`). Si una cuenta que **cuadraba** pasa a no cuadrar, registra el evento interno
`cuadre_dejo_de_cuadrar` en `eventos_actividad` (sin push ni correo, sin montos; `clave_unica = cuadre_roto:<usuario>:<cuenta>:<mes>`,
así no se repite para el mismo mes aunque vuelva a cuadrar y a romperse). La primera lectura de una cuenta solo se anota. El
paso informa `alertas: n`. El administrador ve el evento en «Actividad reciente» y puede activar push/correo para ese tipo.

## Formato de banco desconocido: «aprendiendo»

Aprender un formato es trabajo nuestro, no de la persona. Un extracto **no se pudo leer por formato**
(`motivo_error == 'formato_no_reconocido'`) o su lector midió que lo leído **no suma** el resumen (`lectura_completa == false`)
está en estado `aprendiendo` (`backend/app/estado_aprendizaje.py`). Nada se toca ni se pide.

Campos nuevos (todos aditivos; `null` cuando no aplica):

- `autoarreglo.correr` → `aprendizaje: {estado_aprendizaje: 'aprendiendo', texto_aprendizaje, cantidad, historial_ids}` o `null`.
- Cada renglón de **estado de extractos** (`estado_traer`): `estado_aprendizaje` y `texto_aprendizaje`.
- Acciones y causas del **cuadre encadenado** (`lectura_incompleta` / `pedir_extracto`) y hallazgo `tarjeta_formato_no_reconocido`
  de **salud de datos** (`datos.estado_aprendizaje`).
- Texto fijo: «Estamos aprendiendo el formato de tu banco; no tienes que hacer nada.»

**Qué cambia en el front (para otro agente; `pwa/` NO se tocó):** hoy los textos «Mándame el extracto para aprender su formato»
(`cuadre_encadenado.py`, `deuda_tarjeta.py`) y el botón `pedir_muestra_extracto` (`salud_datos.py`, ruta en `AvisoSalud.jsx`)
siguen llegando sin cambio. El front debe: (1) si `estado_aprendizaje === 'aprendiendo'`, mostrar `texto_aprendizaje` como estado
informativo **sin botón** y **ocultar** la acción `pedir_extracto` / `pedir_muestra_extracto`; (2) en `AvisoAutoarreglo.jsx`,
mostrar `aprendizaje.texto_aprendizaje` (sin acción) cuando `aprendizaje` no sea `null`; (3) opcional: mostrar `coherencia` y la
historia por movimiento («Ver qué hice» por movimiento).

## Fixtures multi-banco

`backend/tests/fixtures_bancos.py` trae extractos inventados de «Banco Ejemplo A» (una línea por movimiento con valor con signo),
«B» (columnas Débito/Crédito/Saldo) y «C» (formato sin tabla que ningún lector conoce). `tests/test_bancos_genericos.py`
comprueba que el flujo genérico no asume Nu: A se lee, se importa y cuadra; B se lee mal (con la celda de Débito/Crédito vacía el
lector de columnas corre el valor a Débito) y la red de seguridad lo frena porque no suma el saldo; C queda `aprendiendo` y sin
tocar. **Hallazgo abierto:** el lector de columnas (`_parse_bancolombia`, también usado por el genérico) confunde Débito y Crédito
cuando una celda queda vacía; hoy no daña nada (no suma ⇒ no se importa solo) pero conviene un lector verificado para ese formato.
