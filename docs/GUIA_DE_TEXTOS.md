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
