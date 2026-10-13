# Auditoría de estados y conteos (Traer movimientos y vecinos)

Qué se revisó: números que no cuentan la historia completa, estados poco claros, dobles conteos y contadores que no se actualizan tras una acción.

## Encontrado y corregido

| Dónde | Problema | Arreglo |
|---|---|---|
| Traer movimientos | «0 movimientos»: la pantalla mostraba solo `importados`; si todo ya estaba registrado se importaba 0. «Revisado · N» contaba exactos + aproximados y dejaba fuera los completados. | Modelo único `app/estado_traer.py` (leídas = ya estaban + nuevas + por revisar + descartadas + anteriores). Frase humana por extracto («37 leídos, 37 ya estaban, 0 nuevos»). |
| Historial de extractos | `faltantes`/`importados` quedaban viejos tras importar o completar: un extracto resuelto seguía diciendo «faltan N». | `sincronizar_contadores` tras procesar, importar y resolver dudosos; la cuenta sale de la revisión guardada. |
| Extractos que «quedan» | Carrera: si registrabas a mano/atajo/correo una línea DESPUÉS de leer el extracto, seguía como pendiente. | `reconciliar_pendientes` (al abrir el centro y en Inicio) junta esas líneas con lo existente, sin duplicar. |
| Extractos que «quedan» | El mismo extracto en dos correos, o subido a mano y por Gmail, contaba dos veces como pendiente. | Un renglón por (cuenta, mes); `copias` dice cuántos eran. Tareas e Inicio usan ese mismo conteo. |
| Extractos que «quedan» | Un par de movimientos conciliados de un periodo que se solapa daban por revisado todo el mes siguiente. | `evidencia_conciliado` exige que al menos la mitad de los movimientos del mes estén conciliados. |
| Extractos que «quedan» | Borrar la revisión dejaba el extracto de Gmail «procesado» sin respaldo. | Vuelve a «nuevo». |
| Extractos aproximados | Una línea «casi igual» se daba por registrada sin preguntar (y sin dejar rastro). | Vista previa con las dos filas lado a lado: «Sí, es el mismo» (se junta) / «No, es otro» (se agrega); en bloque. Excel/CSV: `conciliar_con`. |
| Inicio | El recordatorio «extractos por revisar» contaba extractos crudos (copias incluidas) y no coincidía con el centro. | Usa el mismo modelo. |
| Cobertura | Un mes con extracto leído pero con líneas por registrar salía «revisado». | Estado «Falta algo» (amarillo); «anterior a tu fecha de inicio» tachado. |

## El correo en dos usos independientes (movimientos / extractos)

Antes el correo traía notificaciones y extractos mezclados: una sola sincronización, un solo bloque y contadores revueltos. Feedback de un usuario: los EXTRACTOS son para CONCILIAR; los MOVIMIENTOS (notificaciones) son para tener el dato REAL del día a día.

| Dónde | Qué quedó |
|---|---|
| Backend `POST /correos/sincronizar?tipo=movimientos\|extractos\|todo` | `todo` (por defecto) = comportamiento de siempre. `movimientos` = fases etiqueta + notificaciones; `extractos` = fase extractos. Una corrida a medias de otro tipo se reinicia (lo ya visto se salta, nunca duplica). |
| Preferencias `perfiles.gmail_leer_movimientos / gmail_leer_extractos` | Por defecto TRUE. `PUT /correos/gmail/lectura` (parcial) y `GET /correos/gmail/estado` las devuelve. Un uso apagado: no se llama a Gmail para él, no se guardan notificaciones ni adjuntos/extractos, y `conciliar` / `clave-pdf/probar` responden 400 con mensaje claro. Ambos apagados: no se toca Gmail (respuesta con `aviso`). El cron respeta las preferencias de cada usuario (`apagados` en su respuesta). |
| «Última vez» y contadores por uso | `sync_gmail.ultima_sync_mov / _ext` y contadores por uso; leer solo un uso NO marca el otro como al día (si luego se enciende, lee la ventana larga) ni borra sus contadores. `GET /correos/carriles` y `carriles` dentro de `GET /sincronizacion/estado`: movimientos (leídos, nuevos, por revisar, ya registrados, provisionales) y extractos (encontrados, leídos, con clave pendiente, no se pudo leer, por conciliar, al día). La respuesta de sincronizar solo AÑADE campos (`tipo`, `aviso`, `movimientos_leidos`, `movimientos_ya_registrados`, `extractos_leidos`). |
| Provisional / confirmado | Sin modelo nuevo: un movimiento del correo es provisional mientras tenga el canal `correo` y no el `extracto` (tabla de huellas de origen); al conciliar el extracto lo confirma sin duplicarlo (regla de `duplicados.py`, probada en ambos órdenes de llegada). |
| Traer movimientos (UI) | Dentro de «Desde tu correo» hay DOS tarjetas con su interruptor, botón, última vez, contadores y error propios; «Traer todo ahora» las corre una tras otra y, si una falla, dice cuál y la otra sigue. «Por hacer» sale agrupado por uso con su nombre; Inicio y el resumen dicen «3 movimientos por aprobar · 1 extracto por conciliar». |

## Revisado sin hallazgos
- Pagos de tarjeta, traslados propios y ajustes de saldo ya son neutrales en informes, presupuesto, resumen del mes y cierre (`app/contabilidad.py`, probado en `test_traslados_neutralidad.py` y `test_contabilidad.py`). Los únicos `tipo == "expense"` sueltos son de pagos fijos (recurrentes), que no suman gasto real.
- «Por revisar» (`/movimientos/por-revisar/conteo`) y «Por categorizar»/«Por confirmar» del centro son conjuntos que no se pisan: la cola de categorizar excluye lo que ya está en la bandeja.

## Queda pendiente
- (Resuelto en la auditoría final) Inicio mostraba el recordatorio de extractos y la insignia «N por resolver»: ahora queda solo el número en el botón Traer movimientos. Ver AUDITORIA_FINAL.md.
- El mismo PDF en dos correos distintos se detecta por cuenta + mes. Un hash del contenido (columna nueva en `extractos_correo`) lo haría exacto también cuando el periodo no se pudo leer; no se agregó para no tocar la base.
- Saldos y cupos de tarjetas, Presupuesto y Cierre de mes: no se encontraron dobles conteos con las pruebas actuales, pero no se revisaron con datos reales.
- Correos aprobados: la tarjeta no muestra aún «esto es lo que va a pasar» (los que coinciden con algo ya no aparecen en «Por revisar»; los demás siempre se agregan como nuevos).
