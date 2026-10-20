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
