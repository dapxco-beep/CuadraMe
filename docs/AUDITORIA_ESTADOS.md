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

## «Todos los extractos»: de qué mes es cada uno y que ninguno quede invisible

Hallazgo con datos reales (usuario con más actividad): la pantalla solo listaba los «ya revisados» (6 filas casi idénticas «Nu Colombia / 0 movimientos coinciden con el banco») y los demás extractos quedaban invisibles o dispersos: sin procesar (4), con clave (3), con error (3 intentos fallidos sin motivo), por revisar (2) y 8 correos sin PDF.

| Dónde | Problema | Arreglo |
|---|---|---|
| Filas de extracto | No decían mes, ni tipo (cuenta/tarjeta), y «0 movimientos coinciden con el banco» parecía «no hizo nada». | Banco + tipo + mes en grande, estado con ícono y frase honesta (`estado_traer.lista_extractos` + `extractos_vista.frase_resultado`). |
| Mes del extracto | Se tomaba el periodo guardado o, si no, el mes anterior a la fecha del correo. | `extractos_vista.deducir_periodo`: periodo guardado, asunto, nombre del archivo, líneas leídas, fecha de recepción; si nada sirve, «Mes por confirmar» + selector (`PUT /sincronizacion/extractos/{id}/mes`). Las fuentes seguras se guardan en `extractos_correo.periodo` (`persistir_periodos`). |
| Regla de Nu | `Nu_2026-08-04.pdf` es la FECHA DE PAGO, no el periodo. | Para Nu, una fecha en el nombre del archivo vale el MES ANTERIOR (el corte anterior). Otros bancos: la fecha vale su propio mes. |
| Lista | Solo se veían los revisados; el resto, disperso. | `GET /sincronizacion/extractos` (y `todos_extractos` en `/sincronizacion/estado`): todos los estados, por mes, con contadores, filtros, buscador y los correos sin PDF plegados. |
| Duplicados | El mismo extracto en dos correos, o varios intentos fallidos, eran filas casi idénticas. | Una fila por (cuenta, mes), o (banco, tipo, mes) si no hay cuenta; «x2 correos» / «x3 intentos». |
| Errores | Un extracto con error no decía por qué. | `historial_extractos.motivo_error` y `extractos_correo.motivo_error` (opcionales); `POST /correos/extractos/{id}/reintentar` («Intentar de nuevo»). Los errores antiguos dicen «No se pudo leer (motivo no guardado)». |
| Cobertura | Sus textos («Al día», «Falta algo») no coincidían con la lista y un extracto con error era «Sin datos». | Mismos nombres de estado, estado «No se pudo leer» y, por celda, `lista` con los extractos de ese mes; tocar una celda abre la lista filtrada por mes y cuenta. |

Pendiente: un extracto SUBIDO A MANO y roto no tiene correo detrás, así que no se le puede fijar el mes con el selector (solo «Subir de nuevo»).

## El correo en dos usos independientes (movimientos / extractos)

Antes el correo traía notificaciones y extractos mezclados: una sola sincronización, un solo bloque y contadores revueltos. Feedback de un usuario: los EXTRACTOS son para CONCILIAR; los MOVIMIENTOS (notificaciones) son para tener el dato REAL del día a día.

| Dónde | Qué quedó |
|---|---|
| Backend `POST /correos/sincronizar?tipo=movimientos\|extractos\|todo` | `todo` (por defecto) = comportamiento de siempre. `movimientos` = fases etiqueta + notificaciones; `extractos` = fase extractos. Una corrida a medias de otro tipo se reinicia (lo ya visto se salta, nunca duplica). |
| Preferencias `perfiles.gmail_leer_movimientos / gmail_leer_extractos` | Por defecto TRUE. `PUT /correos/gmail/lectura` (parcial) y `GET /correos/gmail/estado` las devuelve. Un uso apagado: no se llama a Gmail para él, no se guardan notificaciones ni adjuntos/extractos, y `conciliar` / `clave-pdf/probar` responden 400 con mensaje claro. Ambos apagados: no se toca Gmail (respuesta con `aviso`). El cron respeta las preferencias de cada usuario (`apagados` en su respuesta). |
| «Última vez» y contadores por uso | `sync_gmail.ultima_sync_mov / _ext` y contadores por uso; leer solo un uso NO marca el otro como al día (si luego se enciende, lee la ventana larga) ni borra sus contadores. `GET /correos/carriles` y `carriles` dentro de `GET /sincronizacion/estado`: movimientos (leídos, nuevos, por revisar, ya registrados, provisionales) y extractos (encontrados, leídos, con clave pendiente, no se pudo leer, por conciliar, al día). La respuesta de sincronizar solo AÑADE campos (`tipo`, `aviso`, `movimientos_leidos`, `movimientos_ya_registrados`, `extractos_leidos`). |
| Provisional / confirmado | Sin modelo nuevo: un movimiento del correo es provisional mientras tenga el canal `correo` y no el `extracto` (tabla de huellas de origen); al conciliar el extracto lo confirma sin duplicarlo (regla de `duplicados.py`, probada en ambos órdenes de llegada). |
| Traer movimientos (UI) | Tres secciones hermanas, cada una con su «Por hacer» y su contador: **Movimientos** (estado de la lectura de notificaciones + «Ver los N por revisar» + «Agregar uno a mano»; NO repite la lista), **Extractos** (los del correo con su estado, clave y «Conciliar», los que se suben como archivo, «Al día» y cobertura por mes) y **Conexión de Gmail** (conectar, interruptores, última vez, errores, punto de partida; plegada). «Traer todo ahora» corre los dos usos en secuencia y, si uno falla, dice cuál. Rutas viejas: `/correos` abre Movimientos (y la conexión si vuelve de Google con `?gmail=`), `/conciliacion` e `/importar` abren Extractos, `/conexiones` la hoja de conexiones. Inicio y el resumen dicen «3 movimientos por revisar · 1 extracto por conciliar». |
| Movimientos del correo en Movimientos | Los correos pendientes se aprueban en `/movimientos` (chip «Del correo por revisar», sección «Por revisar · N del correo», `?filtro=por-revisar`). La tarea «Movimientos del correo por revisar» lleva allí. Al aprobar, el movimiento aparece en la lista sin recargar. |
| Fecha del movimiento (correo) | El banco escribe la fecha dentro del texto («el 3 de julio de 2026 a las 11:05 am», «08/10/2026», «8-oct-2026»; am/pm o 24 h; hora Colombia). `extraer_fecha_movimiento` la lee y se guarda en `correos_gastos.fecha_movimiento` (UTC, opcional); sin ella o si es ambigua/futura/de hace más de 5 años vale la de recepción. Correos viejos: se calcula al vuelo al listar. Antes el movimiento nacía con la fecha de recepción: ahora usa la del movimiento, o la que la persona corrija al aprobar (`fecha` opcional en `aprobar`, 400 si es futura o muy antigua). El punto de partida, el orden de la lista y la comparación anti-duplicados usan esa fecha (la huella sigue siendo el id del mensaje). |

## Revisado sin hallazgos
- Pagos de tarjeta, traslados propios y ajustes de saldo ya son neutrales en informes, presupuesto, resumen del mes y cierre (`app/contabilidad.py`, probado en `test_traslados_neutralidad.py` y `test_contabilidad.py`). Los únicos `tipo == "expense"` sueltos son de pagos fijos (recurrentes), que no suman gasto real.
- «Por revisar» (`/movimientos/por-revisar/conteo`) y «Por categorizar»/«Por confirmar» del centro son conjuntos que no se pisan: la cola de categorizar excluye lo que ya está en la bandeja.

## Queda pendiente
- (Resuelto en la auditoría final) Inicio mostraba el recordatorio de extractos y la insignia «N por resolver»: ahora queda solo el número en el botón Traer movimientos. Ver AUDITORIA_FINAL.md.
- El mismo PDF en dos correos distintos se detecta por cuenta + mes. Un hash del contenido (columna nueva en `extractos_correo`) lo haría exacto también cuando el periodo no se pudo leer; no se agregó para no tocar la base.
- Saldos y cupos de tarjetas, Presupuesto y Cierre de mes: no se encontraron dobles conteos con las pruebas actuales, pero no se revisaron con datos reales.
- Correos aprobados: la tarjeta no muestra aún «esto es lo que va a pasar» (los que coinciden con algo ya no aparecen en «Por revisar»; los demás siempre se agregan como nuevos).
