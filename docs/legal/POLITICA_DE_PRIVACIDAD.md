# Política de Tratamiento de Datos Personales — CuadraMe

> **BORRADOR PARA REVISIÓN DE ABOGADO.** No publicar como definitivo sin revisión jurídica. Los textos entre `[CORCHETES]` los debe decidir Daniel (ver `PENDIENTES_DANIEL.md`). Este borrador describe lo que la aplicación hace hoy según el código; si el producto cambia, hay que actualizarlo.

Versión del borrador: 1.2 · Fecha: [FECHA DE PUBLICACIÓN]
(La versión que ve el usuario en la app y que se registra al autorizar sigue siendo la 1.1 hasta que se decida publicar esta; al cambiarla hay que subir `VERSION_TEXTOS` en `pwa/src/lib/consentimientos.js` y `backend/app/routers/consentimientos.py`.)

## 1. Responsable del tratamiento
[RAZÓN SOCIAL / NOMBRE DE LA PERSONA NATURAL], NIT/C.C. [NÚMERO], domicilio en [CIUDAD], Colombia (en adelante, "CuadraMe", "nosotros"), es responsable del tratamiento de tus datos personales conforme a la Ley 1581 de 2012, el Decreto 1377 de 2013 (compilado en el Decreto 1074 de 2015) y demás normas aplicables.
Contacto para consultas, reclamos y ejercicio de derechos: dapxco@gmail.com. Sitio: https://cuadrame.dapx.shop.

## 2. Qué datos tratamos
| Dato | De dónde viene | Obligatorio |
|---|---|---|
| Nombre y correo | Registro (o cuenta de Google si inicias sesión así) | Sí |
| Información financiera: cuentas, saldos, movimientos, categorías, presupuestos, metas, deudas, recurrentes, patrimonio | La que tú ingresas o importas | Sí (es el servicio) |
| Correos de Gmail: remitente, asunto, fragmento y datos extraídos (monto, comercio, fecha) de los que se detectan como movimientos; metadatos de extractos (banco, periodo, nombre del archivo) | Tu Gmail, con permiso de **solo lectura** (`gmail.readonly`), si lo conectas | No |
| Extractos PDF, CSV, Excel, fotos de facturas | Los que subes | No. El archivo se procesa y no se almacena |
| Clave del PDF de tus extractos | La que decides guardar. Se almacena cifrada y no va a copias de seguridad ni correos | No |
| Tokens de acceso a Gmail | Google, al conectar. Se almacenan cifrados | No |
| Datos de terceros: nombres de contactos en gastos compartidos | Los que tú registras | No |
| Datos técnicos: dirección IP, dispositivo, uso básico, errores | Automático | Sí |
| Autorizaciones otorgadas y su historial (finalidad, versión, fecha) | Pantalla de autorización | Sí |

No tratamos datos sensibles ni de menores de edad de forma intencional. CuadraMe es solo para mayores de 18 años. Si en un movimiento o nota escribes algo sensible (por ejemplo, un gasto médico), es tu decisión y se trata como parte de tu información financiera.

## 3. Finalidades
1. Prestarte el servicio: registrar y mostrar movimientos, presupuestos, proyecciones, informes y cierres de mes.
2. Sugerir movimientos y categorías desde tus correos y extractos, y comparar extractos con tu historial.
3. Responder consultas con el asistente de inteligencia artificial y leer facturas, solo si usas esas funciones.
4. Enviarte notificaciones y correos **que tú actives**: alertas de presupuesto, recordatorios, resumen semanal por correo, cierre de mes por correo.
5. Seguridad, prevención de abuso (topes de uso), soporte técnico, copias de seguridad y continuidad del servicio.
6. Cumplir obligaciones legales y atender requerimientos de autoridades.
No vendemos tus datos ni los usamos para publicidad de terceros.

## 4. Autorización
Tratamos tus datos con tu autorización previa, expresa e informada. La app la pide al registrarte (tratamiento básico) y de forma **separada y opcional** para: lectura de correo, inteligencia artificial y notificaciones. Cada autorización queda registrada con fecha y versión del texto, y puedes revocarla en Perfil → Privacidad y datos. Revocar la lectura de correo desconecta Gmail; revocar notificaciones desactiva los avisos.

## 5. Encargados y terceros que reciben datos
| Proveedor | Para qué | Qué recibe |
|---|---|---|
| Supabase | Base de datos y autenticación | Todos los datos de tu cuenta |
| Railway | Servidor del backend | Los datos que procesa la API |
| Vercel | Hospedaje de la aplicación web | Datos técnicos de conexión |
| Google (API de Gmail y OAuth) | Leer tu correo si lo conectas | Se conecta con tu autorización de solo lectura |
| OpenRouter y los modelos de IA que opera | Asistente, facturas, lectura de extractos | Solo lo necesario: tu pregunta y un resumen de tus datos recientes, o el contenido del documento. Nunca claves ni PIN. No guardamos las conversaciones |
| Resend | Envío de correos | Tu correo y el contenido del correo: resumen semanal, cierre de mes (si los activas) y copias de seguridad al administrador |
| Sentry | Registro de errores técnicos | Datos técnicos del error; configurado para no enviar datos personales |
| Servicios de notificaciones push de Apple, Google o Mozilla | Entregar avisos | El texto de la notificación, solo si las activas |
| Stripe | Pagos | Solo si en el futuro se cobra por el servicio. Hoy no hay cobros |
| Autoridades | Requerimiento legal válido | Lo que la ley exija |

**Copias de seguridad.** Cada día se exporta la base de datos y se envía por correo, mediante Resend, al administrador del servicio (hoy [CORREO DE BACKUP]). Excluye la clave de los PDF. Incluye datos de cuentas de usuarios. Las copias ya enviadas no se pueden recuperar ni editar individualmente; al eliminar tu cuenta, tus datos salen de la base de datos de inmediato y de las copias a medida que estas se reemplazan. [El abogado debe validar el plazo de retención de copias y su redacción.]

**Uso de la información recibida de las APIs de Google.** El uso que CuadraMe hace de la información recibida de las APIs de Google cumple con la Política de Datos de Usuario de los Servicios de API de Google, incluidos los requisitos de Uso Limitado. Solo pedimos lectura de Gmail (`gmail.readonly`) si conectas tu cuenta, y la usamos únicamente para detectar notificaciones y extractos bancarios y registrarte movimientos en CuadraMe. No vendemos estos datos, no los usamos para publicidad ni para entrenar modelos de IA generalizados, y no permitimos que personas los lean salvo con tu consentimiento expreso, por seguridad o abuso, o por obligación legal.

## 6. Transferencias y transmisiones internacionales
Varios proveedores (Supabase, Railway, Vercel, Google, OpenRouter, Resend, Sentry) pueden procesar datos en servidores fuera de Colombia. Actuamos con proveedores que ofrecen medidas de seguridad razonables y los tratamos como encargados bajo nuestras instrucciones. [El abogado debe confirmar si aplican contratos de transmisión de datos (Art. 25 Decreto 1377) y si algún país receptor no ofrece nivel adecuado de protección (Art. 26 Ley 1581), y registrar las ubicaciones reales de cada proveedor.]

## 7. Seguridad
Conexiones cifradas (HTTPS); tokens de Gmail y clave de PDF cifrados en la base; las contraseñas las gestiona Supabase Auth; el PIN y la biometría se verifican en tu dispositivo y no llegan a nuestros servidores; la clave personal de la API (atajos) se guarda como huella (hash) y solo se muestra completa al crearla; los datos están separados por usuario. Ningún sistema es infalible: ante un incidente que afecte tus datos, te lo informaremos y lo reportaremos a la autoridad cuando corresponda.

## 8. Tus derechos
Como titular puedes: conocer, actualizar y rectificar tus datos; pedir prueba de la autorización; ser informado del uso que se les da; presentar quejas ante la Superintendencia de Industria y Comercio (SIC); revocar la autorización y/o pedir la supresión cuando no haya un deber legal o contractual de conservar; y acceder gratuitamente a tus datos.
**Cómo ejercerlos:** desde la app, en Perfil → Privacidad y datos (ver y revocar autorizaciones, descargar tus datos, eliminar tu cuenta), o escribiendo a [CORREO DE CONTACTO]. Consultas: respuesta en máximo 10 días hábiles (prorrogables 5). Reclamos: máximo 15 días hábiles (prorrogables 8), según los artículos 14 y 15 de la Ley 1581.

## 9. Conservación
Mientras tu cuenta esté activa. Si la eliminas, borramos tus datos personales de la base de datos, salvo lo que debamos conservar por obligación legal. Los registros de autorizaciones pueden conservarse como prueba. Ver lo dicho de las copias de seguridad en la sección 5.

Del contenido de los correos de Gmail que lees con tu autorización (remitente, asunto y fragmento) borramos el de los correos que descartas o ignoras a los 30 días, y el de los que se convierten en movimiento a los 12 meses. Conservamos solo lo mínimo para no volver a leer el mismo correo (identificador, fecha, monto y estado). Si desconectas Gmail, revocamos el permiso en Google y borramos el token de inmediato.

## 10. Cookies y almacenamiento local
La app usa almacenamiento del navegador para mantener tu sesión, tus preferencias (tema, secciones abiertas) y avisos descartados. No usamos cookies de publicidad. [Confirmar con el abogado si se añaden analíticas.]

## 11. Cambios
Si cambiamos esta política de forma sustancial, te lo avisaremos en la app y, cuando corresponda, te pediremos una nueva autorización.

## 12. Registro Nacional de Bases de Datos
[El abogado debe confirmar si CuadraMe está obligada a inscribir la base en el RNBD de la SIC (depende de los activos totales de la empresa) y, de ser así, el plazo.]
