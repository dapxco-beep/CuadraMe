# Salud de datos y autocuración

Nació de seis fallas reales que apareció al probar con datos de verdad: el extracto de la TARJETA quedó en la cuenta de AHORROS del mismo banco; no existía la cuenta de la tarjeta; correos de transacciones reales quedaron «descartados» en silencio; la lectura de correos dio 0 durante días sin que nadie lo notara; extractos en error acumulados sin acción; un error de servidor se mostró como «sin conexión». La capa existe para que eso no vuelva a pasar con ningún cliente, de forma estándar y automática.

Regla de oro: **nunca se mueve dinero sin que la persona lo vea.** Lo automático no toca saldos; lo que sí los toca solo se sugiere, con vista previa.

## 1. Diagnóstico (`app/salud_datos.py`, `GET /salud`)

`diagnosticar(db, usuario_id)` solo LEE y devuelve hallazgos `{codigo, severidad, titulo, texto, accion, datos}`. `datos` lleva solo ids y conteos: nunca montos, descripciones ni contenido de correos. El endpoint es de la persona que pregunta (aislado por usuario).

| Código | Cuándo | Acción de un toque |
|---|---|---|
| `extracto_producto_distinto` | El asunto/archivo dice tarjeta (o ahorros) y la cuenta es del otro producto (`producto_de_texto` vs `producto_de_cuenta`) | Revisar → «Cambiar cuenta de extracto» con vista previa |
| `tarjeta_sin_cuenta` | Hay extractos de tarjeta de un banco y ninguna cuenta de crédito de ese banco | «Crear tarjeta <Banco>» |
| `extracto_en_error_recuperable` | Extracto en error que viene de un correo (y, si era por clave, ya hay clave guardada) | Reintentar |
| `correos_descartados_con_monto` | Correos `descartado` con monto | Ver correos (Descartados) |
| `lectura_correo_en_cero` | Gmail conectado, lectura de movimientos activa y ≥3 corridas completas seguidas con 0 correos | Revisar conexión |
| `clave_pdf_faltante` | Extractos esperando clave y no hay clave guardada | Guardar clave |
| `movimientos_en_cuenta_incoherente` | Movimientos importados de un extracto que viven en una cuenta distinta a la del extracto | Revisar → «Cambiar cuenta de extracto» |
| `sin_sincronizar` | Gmail conectado y sin sincronizar hace más de 48 h | Traer ahora |

## 2. Autocuración: automático vs sugerido

| Qué | Cómo | Tipo |
|---|---|---|
| Extracto NUEVO de tarjeta y UNA sola cuenta de crédito del banco | `extractos_gmail.sugerir_cuenta` (general por banco: Nu, Bancolombia, Davivienda, Falabella, Bogotá… probado). Si el banco solo tiene ahorros no lo asigna allí (no tapa el extracto de los ahorros); con dos tarjetas no adivina | **Automático** |
| Banco con extractos de tarjeta y sin cuenta de crédito | Banner → «Crear tarjeta <Banco>» (`POST /salud/crear-tarjeta`): crea `<Banco> Tarjeta`, tipo crédito, saldo 0, y reasigna los extractos de ese banco que **aún no se importaron**. No importa movimientos. Idempotente. Solo funciona si de verdad hay extractos de tarjeta del banco | **Un toque** de la persona |
| Ya importado en la cuenta equivocada | Solo se sugiere: «Cambiar cuenta de extracto» con vista previa y confirmación | **Sugerido** |
| Errores de clave | Se reintentan al guardar la clave y, una vez al día por persona, desde el cron de correos (`salud_autocuracion.reintento_diario`, marca `salud_reintento_errores` en `marcas_cron`) si la clave existe | **Automático** |
| Lo descartado | Política nueva, ver abajo | **Pregunta una vez** |

### Política de borrado: «lo que se borra no resucita… si tú lo dices»

Antes, borrar cualquier movimiento dejaba un «fantasma» que bloqueaba para siempre el correo o la línea del extracto equivalente, sin avisar. Ahora, al borrar algo que vino de un correo o de un extracto, la misma hoja de confirmación pregunta **«¿Qué pasó?»**:

| Respuesta (`motivo`) | Fantasma | Qué pasa con el correo / extracto |
|---|---|---|
| «Era duplicado» (`duplicado`) | Sí | Queda descartado (no vuelve) |
| «No va en mi cuenta» (`no_va`) | Sí | Queda descartado (no vuelve) |
| «Lo borré por error» (`error`) | **No** | El correo vuelve a «Por revisar»; la línea del extracto puede volver a importarse |

- Hecho a mano (sin correo ni extracto): la confirmación de siempre, sin pregunta extra.
- Borrado de varios: se pregunta UNA vez para todos («Eran duplicados» / «Los borré por error» / «No van en mi cuenta»).
- API: `DELETE /movimientos/{id}?motivo=…` y `POST /movimientos/eliminar-masivo` con `motivo`. Sin `motivo` el servidor usa `duplicado` (compatibilidad con clientes antiguos y el atajo). Lógica: `duplicados.registrar_borrado`. «Deshacer lo importado» sigue sin dejar fantasma.
- Siempre se puede recuperar un correo descartado desde Ver todo → Correos → Descartados.

## 3. Aviso en la app

Un banner discreto en Inicio y en Traer movimientos: «Revisé tu cuenta y encontré N cosas». Abre la lista de hallazgos, cada uno con su botón. Un solo banner; se oculta con N = 0 y si la consulta falla. Textos en `docs/GUIA_DE_TEXTOS.md`. Componente: `pwa/src/components/AvisoSalud.jsx`.

## 4. Monitor para el dueño (`POST /salud/cron/resumen`)

Protegido por `X-Cron-Secret`. Calcula contadores **agregados y anónimos** (cuántas personas, nunca cuáles):

| Contador | Umbral para avisar |
|---|---|
| `lectura_en_cero` (≥3 corridas en 0, Gmail conectado y lectura activa) | 1 |
| `extractos_en_error` | 3 |
| `descartados_altos` (≥5 correos descartados con monto) | 3 |
| `sin_sync_48h` | 2 |

Si alguno se supera, registra UN evento `salud_datos_alerta` por día (clave única `salud_datos:<fecha>`) en «Actividad reciente»: el mismo mecanismo de avisos (`app/avisos.py`, push + correo por Resend al administrador) que usan los picos de errores 5xx y la capacidad. Umbrales en `app/salud_monitor.py`.

**Cron (lo crea el dueño, NO está aplicado):** entrada en `backend/cronjobs/crear_crons.py`, «CuadraMe - monitor de salud de datos», diario 7:30 (Bogotá). Se aplica con `crear_crons.py --aplicar` cuando el dueño decida (recrea todos los jobs: revisar antes el aviso del script).

## Migraciones

Ninguna. Se usan columnas existentes (`sync_gmail.ceros_seguidos_mov`, `huellas_origen.estado`, `marcas_cron`).
