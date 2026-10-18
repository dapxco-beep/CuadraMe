# Guía de textos de CuadraMe

Para quien escribe o cambia un texto de la app. Pensada para personas que **no** son técnicas ni financieras.
Regla de oro: si tu mamá no lo diría en voz alta, no va en la pantalla.

## Tono

- Español colombiano, de tú. Cercano y tranquilo, sin regaños ni alarmismo.
- Frases cortas: una idea por frase. Verbo primero cuando es una acción («Agrega tu primera cuenta»).
- Habla de **la plata de la persona**, no del sistema: «Lo que debes en la tarjeta», no «Saldo del pasivo».
- Cuadri (la mascota) acompaña en celebraciones, vacíos y consejos. No va en pantallas de trabajo ni en errores.

## Longitud

| Pieza | Máximo |
|---|---|
| Título de pantalla | 3 palabras |
| Botón | 3 palabras, empieza con verbo («Guardar movimiento») |
| Línea de apoyo bajo un título | 1 frase (~100 caracteres) |
| Estado vacío | título corto + 1 frase + **un** botón |
| Mensaje de error | qué pasó + qué hacer, en 2 frases |
| Toast | 1 frase; con «Deshacer» si se puede revertir |

## Palabras preferidas y prohibidas

| No uses | Usa | Notas |
|---|---|---|
| Conciliar / conciliación / conciliado | Revisar el extracto · «coincide con el banco» · «Revisado» | «Cuadre con el banco» como título de tarjeta |
| Sincronizar | Traer movimientos | El botón principal es «Traer todo ahora» |
| Cruzado / cruzar | Coincide con el banco | «12 movimientos coinciden con el banco» |
| Recurrente(s) | Pago fijo / Pagos fijos | Explica: «lo que pagas o recibes cada mes» |
| Traslado propio / transferencia interna | Pasar plata entre tus cuentas | Aclara siempre «no cuenta como gasto» |
| Pagar la tarjeta (como «transferencia») | Pagar la tarjeta | No es un gasto nuevo: dilo en el aviso |
| Huella (de comercio) | Nombre con el que lo reconozco | «Huella» solo para biometría del celular («huella o rostro») |
| Token / clave de API / hash | Clave · «se guarda solo en este celular» | Nunca muestres «hash» ni «token» |
| Patrimonio | Patrimonio, **con** glosa: «todo lo que tienes menos lo que debes» | La primera vez que aparece en cada pantalla |
| Flujo de caja / proyección de saldo | Cuánto tendrías en los próximos meses | |
| Categorizar / clasificación | Poner en una categoría · «¿En qué categoría va?» | «Sin categorizar» se puede usar como filtro |
| Entrenar / reglas de categorización | Enseñar categorías · Reglas automáticas | |
| Insights | Hallazgos | |
| Activo / pasivo | «algo tuyo que vale plata» / «lo que debes» | «Activo» solo en el botón «Agregar activo» con glosa al lado |
| Importar / procesar / parsear | Traer / leer | «Leyendo tu extracto...» |
| Error / falló / inválido | Qué pasó + qué hacer | Ver sección Errores |
| Periodo | «Cada cuánto» (mensual, quincenal, semanal) | |
| Límite | «Lo máximo que quieres gastar» | |

### «Traer movimientos» es un asistente: UNA cosa a la vez

La pantalla principal solo muestra (1) un estado calmado y (2) UN paso con su botón. Todo lo demás está detrás de una hoja.

| Parte | Texto |
|---|---|
| Estado | «Todo al día» (con «Miré tu correo hace 2 h») SOLO si no queda nada: ni extractos a medias, ni errores o claves pendientes, ni correos por revisar, ni un extracto en otra cuenta. Si solo quedan cosas opcionales (categorizar, correos descartados): «Casi todo al día» + «Solo queda: mirar 16 correos descartados». Si no: «Tienes 3 cosas por hacer». «No hay nada nuevo en tu correo» habla solo del correo, nunca del estado general. |
| Avance | «Paso 1 de 3» con una barra fina; solo si hay más de un paso. Al resolver uno avanza («Paso 2 de 3»). |
| Paso principal | Título corto en imperativo + una frase + un botón con verbo. Orden: conectar (solo primer uso) → fecha de inicio (solo primer uso) → clave del PDF → crear cuenta → extractos a medias → importar faltantes → correos por revisar → lo demás → cuadre → categorizar (opcional). |
| Al terminar un paso | «Listo ✓ — siguiente:» y el nuevo paso. Sin nada más: «Listo ✓» y «Todo al día». |
| Búsqueda | Un solo botón secundario «Buscar ahora» (sin Gmail: «Conectar Gmail»). El progreso va en línea: «Leyendo tus extractos… 3 de 6», «Leyendo tus avisos del banco… 120 de 340», «Probando tu clave en los PDF…». |
| Errores y esperas | Una frase con su acción: «Falta la clave de tu PDF → Ponerla ahora»; «La clave de tu PDF no abrió tus extractos → Cambiar la clave». Nunca «carril» ni jerga. |

**Estado por cuenta y mes** (debajo del paso): una tarjeta por cuenta con su nombre completo y tipo («Nu Colombia · Ahorros», «Nu Colombia Crédito · Tarjeta») y «3 de 6 meses completos». Cada mes dice UN estado, con ícono y palabras: «Conciliado · 14 mov.», «Falta importar 2», «No se pudo leer · falta la clave», «Falta el extracto», «En otra cuenta · Está en Nu Colombia», «Mes en curso» (el mes que aún no termina no es «falta»).

**Nada sin nombre ni origen:** una fila de extracto o de error nunca dice solo «desconocido» ni «banco». Dice de qué banco o cuenta es, de dónde salió («Correo «Llegó el extracto…» · archivo X.pdf» o «Subido a mano el 14 oct») y a qué cuenta quedó. Los errores iguales se agrupan («10 extractos de Nu esperan la clave del PDF» con un solo botón «Poner la clave»). Sin banco identificado el botón dice «Decirme de qué banco es».

**Resumen de la factura anterior (extracto de tarjeta):** tarjeta informativa «Factura anterior: $A · Pagaste: $B · Quedó pendiente: $C»; la fila importable es el pago de lo que pagaste, «Pago de tu tarjeta (factura anterior)», que se cuenta como traslado, no como gasto. Si no coincide con una salida de tu cuenta de ahorros del mismo banco queda sin marcar, con el aviso «Parece el pago de tu tarjeta. Confirma el monto.»

**Línea con dos montos:** «Esta línea trae dos montos. Elige el correcto»; la línea queda apagada y no se importa hasta elegir un monto (botones con los montos de la línea o un campo para escribirlo). Un «Pago» de la tarjeta se sugiere como traslado: «Parece el pago de tu tarjeta desde otra cuenta tuya: se cuenta como traslado, no como gasto.»

Textos de los pasos (fijos): «Conecta tu Gmail», «¿Desde cuándo leo tu correo?», «Falta la clave de tu PDF», «Crea tu cuenta de <banco>», «Sigue con tu extracto de <mes>», «Revisa tu extracto» / «Revisa tus N extractos», «Revisa N movimientos», «Confirma si son tuyos», «Hay extractos que no se pudieron leer», «Un extracto está en otra cuenta», «Hay N correos descartados» (opcional), «Puede haber movimientos repetidos», «Un mes no cuadra con tu extracto», «Pon categoría a N comercios».

**Detrás (hojas):**
- **Ver todo** (pestañas **Extractos** · **Correos** · **Por mes**): extractos a medias («Seguir»), extractos para conciliar, todos los extractos por mes con su estado, ignorados; correos ya registrados e ignorados; cobertura por mes y cuadre.
- **Conexiones y claves**: Gmail, «Leer notificaciones» / «Leer extractos», última lectura, clave del PDF y, bajo «Otras formas de traer movimientos»: subir un archivo, buscar un extracto por su asunto, agregar uno a mano, fecha desde la que leo, estado de todas tus conexiones y «Mi banco no está».
- Hojas de un paso: clave del PDF, poner categorías, revisar un extracto o archivo.
- Automático al abrir (sin botón): leer el correo (si no se leyó hace menos de 15 min), probar la clave guardada y releer saldos. En escritorio, la columna derecha lo dice en «Lo que hago solo».

**Enseñarle a leer un correo** (cuando el lector no entiende un correo del banco, la billetera o un comercio): botón «Enseñarle a leer este correo» en un correo de «Por revisar» sin monto o «Gasto sin detalle», y en cada resultado de «Buscar un movimiento por su asunto». La hoja «Enseñar a leer» son tres toques, uno por paso: «¿Cuál es el monto?» (toca el número), «¿A quién o dónde fue?» (toca la primera y la última palabra del nombre) y «¿Fue un gasto o un ingreso?». Siempre se dice que es privado: «Guardo solo dónde está cada dato en este tipo de correo, no el correo. Es solo para ti.» Si hay correos parecidos que se habían dejado de lado se pregunta antes: «Encontré 3 correos parecidos que había dejado de lado. ¿Los paso a «Por revisar» con lo que me enseñaste?» → «Pasar a Por revisar» / «Ahora no». Cierre: «Listo. Cuando llegue un correo así, lo leo solo.» En «Conexiones y claves» la lista se llama «Mis reglas de correo» (borrar pide confirmar: «Sí, borrar» / «Conservar»). No se dice «regla» en los pasos ni «entrenar»: es enseñar. Nada de lo que se aprende sale de la cuenta de la persona.

Lo que sigue describe los nombres de las secciones antes del asistente; hoy esos contenidos viven en «Ver todo» y «Conexiones y claves».

### El correo tiene DOS usos y la pantalla «Traer movimientos» tiene TRES secciones (nombres fijos)

| Nombre | Qué es | Texto de apoyo |
|---|---|---|
| **Movimientos** | Las notificaciones del banco por correo (compra, transferencia, retiro, pago) + «Agregar uno a mano». Se revisan en la pantalla **Movimientos** («Por revisar · N del correo») y pasan a la lista como provisionales. | «Las notificaciones de tu banco: así ves en el momento lo que gastas.» |
| **Extractos** | TODOS los extractos para conciliar: los que llegan al correo y los que subes tú (PDF, Excel o CSV), con la cobertura por mes y cuenta. | «El extracto mensual del banco: sirve para confirmar y cuadrar el mes.» |
| **Conexión de Gmail** | Conectar o desconectar, interruptores «Leer notificaciones» y «Leer extractos», última vez, errores y desde qué fecha leo. Plegada por defecto. | «Solo tengo permiso de lectura…» |

- Aquí «conciliar» SÍ se usa (botón «Conciliar», «extractos por conciliar»); en el resto de la app sigue valiendo «Revisar el extracto».
- Cada sección tiene su «Por hacer» y su contador propio. Lo que no es del correo va en «Otras cosas por hacer».
- La tarjeta de Movimientos NO repite la lista: dice el estado de la lectura y ofrece «Ver los N por revisar» (lleva a Movimientos).
- En Movimientos: chip «Del correo por revisar (N)» y sección «Por revisar · N del correo». Cada tarjeta muestra primero la fecha y hora del movimiento («Jue 8 oct 2026 · 4:30 pm»); si el banco la escribió distinta a cuando llegó el correo: «Fecha del movimiento (la que usaré) · Llegó el correo el …». Botones: «Aprobar», «Editar» (fecha, monto), «Descartar»; en bloque: «Aprobar los N que parecen correctos». Encabezados por día: Hoy, Ayer, 8 oct.
- Apagado: «no leo ni guardo notificaciones/extractos de tu correo» + «Encenderlo en «Conexión de Gmail»».
- Etiqueta de un movimiento que aún no respalda un extracto: «Falta confirmar con el extracto»; cuando llega: «confirmado por extracto».
- Contadores sin mezclar: «3 movimientos por revisar · 1 extracto por conciliar».
- Ayuda «¿Cuál es la diferencia?» (dentro de «Conexión de Gmail»): un ejemplo de una línea por uso. Nunca decir «carril» al usuario (es un término interno).
- Si falla uno, se nombra cuál: «Extractos: No pudimos…», y el otro sigue funcionando.

### «Todos los extractos» (lista dentro de la sección Extractos)

Cada fila dice, en este orden: **banco + tipo + mes en grande** («Nu Colombia · Cuenta · Julio 2026»; tarjeta con corte conocido: «Tarjeta Nu · corte 14 jul 2026»), el **estado** con ícono y texto, y **una frase de lo que pasó**.

| Estado | Ícono | Frase de resultado |
|---|---|---|
| Revisado | check (verde) | «Leímos 37 movimientos: 37 ya estaban registrados, 0 nuevos.» · «…5 nuevos agregados, 32 ya estaban.» · «No encontramos movimientos en este extracto.» |
| Por revisar | lupa sobre archivo | «Leímos N movimientos: X ya estaban y Y faltan por registrar.» |
| Sin procesar | bandeja | «Llegó a tu correo y aún no lo hemos leído.» |
| Necesita clave | llave | «Está protegido con clave. Guarda la clave del PDF para poder leerlo.» |
| No se pudo leer | triángulo (rojo) | «No pudimos leer este extracto: <motivo>. <siguiente paso>» · antiguos: «No se pudo leer (motivo no guardado).» |
| Anterior a tu fecha de inicio | calendario tachado | «Es anterior a tu fecha de inicio, así que no se trae.» |

- **Prohibido** «0 movimientos coinciden con el banco»: con cero no se cuenta, se dice qué pasó (la frase de arriba).
- Motivos de error (columna `motivo_error`): clave faltante, clave incorrecta, formato no reconocido, PDF escaneado (sin texto), archivo vacío o dañado, problema momentáneo. Cada uno trae su siguiente paso concreto (ver `MOTIVOS` en `backend/app/extractos_vista.py`).
- Mismo extracto en varios correos (o en varios intentos): UNA fila con «x2 correos» / «x3 intentos».
- Sin mes claro: «Mes por confirmar» con un selector «¿De qué mes es este extracto?». Un mes deducido solo de la fecha del correo dice «Mes deducido de la fecha del correo» y deja «Cambiar mes».
- Contador arriba de la lista: «6 revisados · 3 con clave pendiente · 4 sin procesar · 3 con error» (solo lo que no es cero).
- Los correos que hablan de un extracto pero no traen el PDF van plegados: «Correos sin archivo adjunto (N)», con la razón.
- La cobertura por mes usa los MISMOS nombres de estado (Revisado, Por revisar, Sin procesar, Necesita clave, No se pudo leer) y, al tocar una celda, lista los extractos de ese mes con su título.

Palabras que sí puedes usar tal cual: cuenta, saldo, gasto, ingreso, tarjeta, cupo, corte, extracto, presupuesto, meta, deuda, categoría.
Si es la primera vez que aparece una (cupo, corte), usa la **Ayudita** (`<Ayudita termino="...">`) o una frase de apoyo.

## Reglas por tipo de texto

**Botones.** Una sola acción principal por pantalla (botón relleno). El resto, secundarios o enlaces. Nada de «Aceptar» ni «OK» sueltos: di qué pasa («Crear mi cuenta», «Guardar presupuesto»). Los íconos sin texto llevan `aria-label` con la acción **y** el objeto («Quitar el presupuesto de Comida»).

**Formularios.** Etiqueta visible arriba de cada campo (`CampoTexto`), no solo *placeholder*. Pregunta en vez de rótulo técnico («¿De cuánto es?», no «Monto»). Pon el ejemplo en el *placeholder* («Ej. 45000»). Valores por defecto inteligentes: país Colombia, moneda COP, cuenta la última usada, día 1. Lo opcional se dice: «(opcional)».

**Confirmaciones.** Solo para lo que no se puede deshacer o borra datos de verdad. Si se puede revertir: guarda y muestra un toast con «Deshacer», no preguntes antes.

**Retroalimentación.** Todo guardado responde con un toast: `Listo: …` o `Guardado: …`, con el nombre y el monto. Si algo cambió en otro sitio, dilo («ya está en tus movimientos»).

**Estados vacíos.** Tres partes: qué es esto, por qué importa, qué hacer ahora (un botón). Ejemplo: «Aún no tienes metas de ahorro · Una meta es algo que quieres comprar o lograr… · [Crear mi primera meta]».

**Errores.** Nunca «Error» a secas ni el mensaje del servidor crudo. Formato: *qué pasó* + *qué hacer*.
- Validación: «Escribe cuánto fue, solo números. Por ejemplo 25000.»
- Red/servidor: «No pudimos guardarlo. Revisa tu conexión e intenta de nuevo.»
- Sin culpar a la persona: «No pudimos…», no «Ingresaste mal…».
Los errores usan `role="alert"` y salen pegados al campo o al botón.

**Pantallas con mucho contenido.** Lo principal arriba (lo que la persona vino a hacer), el resto detrás de «Ver más» o de una sección plegable (`SeccionPlegable`). Máximo una tarjeta destacada por pantalla.

## Accesibilidad de texto

- Todo control tiene nombre accesible; los íconos solos llevan `aria-label`.
- No dependas del color: «Vencido» además del rojo.
- Toques de mínimo 44 px (`min-h-11`).
- Mensajes dinámicos en `role="status"` (avisos) o `role="alert"` (errores).
- Los números siempre con formato de pesos colombianos (`formatCOP`).

## Antes de publicar un texto: prueba de los 5 segundos

Enséñale la pantalla a alguien 5 segundos. ¿Sabe **para qué sirve** y **cuál es la acción principal**? Si no, sobra información o falta una frase.

## Nombre de la persona

- Se usa poco y solo donde ayuda: saludo de Inicio, algunas frases de Cuadri, resumen semanal y push semanal.
- En `lib/cuadri.js` el marcador es `{nombre}` y va siempre precedido de coma («¡Hola, {nombre}!»): sin nombre se quita con su coma. Nunca escribas un texto que dependa del nombre para entenderse.
- Nunca en lugares públicos ni en el panel de administración.

## Ingresos, gastos y traslados (nombres únicos)

| Concepto | Nombre en la app | Cómo se ve |
|---|---|---|
| Plata que entra de verdad | **Ingresos** | Acento positivo (`text-accent`), con «+» en listas |
| Plata que sale de verdad | **Gastos** | Tinta normal (`text-ink`), con «-» en listas |
| Ingresos − gastos | **Balance** | Con signo: positivo en acento, negativo en `text-danger` |
| Balance / ingresos | **Tasa de ahorro** | Solo si hay ingresos; si no, «—» |
| Plata entre tus cuentas | **Traslado** («Traslado entre tus cuentas») | Neutral: no suma ni resta. Decisión: «Es un traslado entre mis cuentas» / «No es un traslado» |
| Sin la otra pata todavía | **Posible traslado** | «¿Fue entre tus cuentas?» |
| Pagar la tarjeta | **Pago de tarjeta** | Neutral; el gasto ya se contó en la compra |
| Corrección de saldo | **Ajuste de saldo** | Neutral |

Dinero siempre con `formatCOP` / `fmt` (lib/format, respeta «ocultar saldos»). La regla vive en `backend/app/contabilidad.py` y su espejo `pwa/src/lib/contabilidad.js` (casos compartidos en `backend/tests/fixtures/contabilidad_casos.json`). La pantalla «¿En qué gasto mi plata?» lleva la nota «No incluye traslados entre tus cuentas ni pagos de tarjeta» y «Ver lo que no se cuenta».

## Cuadre mes a mes

Lenguaje llano, sin «libro» ni «conciliado»: «el banco dice» / «tu app dice», «No cuadra · $X», «Cuadra ✓», «Arrastra $X de junio», «Falta el extracto de junio», «Hueco o extracto faltante entre X y Y», «Solo falta el saldo inicial». Frase modelo: «Junio no cuadra: el banco registró $800.000 más que tu app. Falta importar 1 línea del extracto.» Toda reparación pide un «Sí, hacerlo» explícito y se puede deshacer; el ajuste de saldo es el último recurso y exige marcar que se entiende el riesgo. Los saldos salen solos: si un extracto quedó sin ellos, la app lo vuelve a leer del correo («Leyendo los saldos de tus extractos…»). Solo si de verdad no hay saldo legible se dice «No pude leer el saldo de este extracto. Escríbelo una vez y listo.» (origen «manual»); nunca «no lo invento». Lógica en `backend/app/cuadre_encadenado.py`.
