# Verificación de Google para el permiso de Gmail (`gmail.readonly`)

**Objetivo:** que cualquier persona (no solo 100 «usuarios de prueba») pueda conectar su Gmail sin la pantalla roja «Google no ha verificado esta app».
**Tiempo estimado:** 1 día para preparar + 2 a 6 semanas de espera de Google + la evaluación de seguridad externa (CASA).
**Quién:** Daniel hace los clics y graba el video; Claude ya dejó los textos; el abogado revisa la política antes de enviar.

> Dato clave: `gmail.readonly` es un scope **restringido** (el nivel más alto). Exige (a) verificación OAuth de marca y scopes y (b) una **evaluación de seguridad anual (CASA)** hecha por un evaluador autorizado por Google. Sin ambas, la app se queda en modo Pruebas (tope de 100 usuarios; hoy `GMAIL_MODO_PRUEBAS=true`).

---

## 0. Qué hace realmente el código (base de todo lo que se declara)

| Hecho | Dónde |
|---|---|
| Único scope pedido: `https://www.googleapis.com/auth/gmail.readonly`. No se pide `email`, `profile` ni `openid` (el login va por Supabase). | `gmail_oauth.py` |
| Se pide `access_type=offline` y `prompt=consent`; se guarda solo el **refresh token**, cifrado con Fernet (`FERNET_KEY`, solo en Railway). Ningún esquema de respuesta lo devuelve. | `gmail_oauth.py`, `routers/correos.py` |
| `state` de OAuth cifrado, caduca en 10 min. | `gmail_oauth.py` |
| Antes de generar la URL de Google se exige el consentimiento específico `lectura_correo` (casilla; versión y fecha quedan registradas). | `routers/correos.py::conectar_gmail` |
| Qué se busca: (1) mensajes con la **etiqueta** que el usuario elige (por defecto `gastos`); (2) notificaciones de **dominios de bancos conocidos** sin adjunto; (3) correos de bancos con **adjunto PDF** y palabras de extracto. | `extractos_gmail.py::construir_query_*` |
| Qué se guarda de cada correo candidato: remitente, asunto, fragmento (`snippet`, máx. 400 caracteres), fecha y lo extraído (monto, moneda, comercio, categoría sugerida). **No se guarda el cuerpo completo.** | `routers/correos.py::_crear_correo` |
| PDF de extractos: se descarga **en memoria**, se lee el texto y **se descarta**; no se guarda el archivo. Tope 15 MB. Se guarda: banco, periodo, nombre del archivo, cuenta sugerida. | `_analizar_adjunto`, `MAX_PDF_BYTES` |
| La app **nunca crea movimientos sola** desde un correo: quedan como sugerencia que la persona aprueba o descarta. | `_crear_correo` (estado `pendiente`) |
| Nunca envía, borra ni modifica correos (solo `messages.list`, `messages.get`, `attachments.get`, `labels.list`, `users.getProfile`). | `correos.py`, `extractos_gmail.py` |
| Desconectar: revoca el token **en Google** (`oauth2.googleapis.com/revoke`) y borra token y correo de la fila. Borrar la cuenta también revoca. | `desconectar_gmail`, `revocar_token` |
| Topes: 80 sincronizaciones/hora, 300/día, 40 correos y 5 PDF por lote, 60 conciliaciones/día, PDF ≤ 15 MB, 100 usuarios con Gmail mientras `GMAIL_MODO_PRUEBAS`. | `correos.py`, `limites_diarios.py`, `config.py` |
| Sincronización automática cada 3 h por cron (`/correos/cron/sincronizar`, exige `X-Cron-Secret`). | `correos.py` |

---

## 1. BRECHAS A CERRAR ANTES DE ENVIAR (hoy NO se cumple)

Google revisa la política y el comportamiento. Estas cuatro brechas pueden causar rechazo o, peor, una declaración falsa. Resuélvelas antes de grabar el video.

| # | Brecha | Por qué importa | Qué hacer | Responsable |
|---|---|---|---|---|
| B1 | **El texto de extractos que vienen de Gmail puede ir a un proveedor de IA externo.** Si los parsers regex no reconocen el banco, `conciliacion.py::procesar_extracto` llama a `extraer_via_ia` (OpenRouter, modelo `nvidia/nemotron-nano-12b-v2-vl:free`) con el texto del PDF. El flujo «conciliar desde Gmail» reutiliza ese camino. | Uso Limitado: los datos de Gmail solo pueden ir a terceros para dar la función visible al usuario y **no** para entrenar IA generalizada. Los modelos `:free` de OpenRouter pueden registrar o usar los prompts; la política dice «no entrenamos modelos». Contradicción posible. | Elegir UNA: (a) para PDFs que vienen de Gmail, **apagar** el camino IA (solo regex; si no reconoce, «súbelo manualmente»); o (b) usar un modelo de pago con la opción de OpenRouter de no almacenar/no entrenar, y declararlo en consentimiento y política. Recomendado: (a) hasta tener la verificación. | Claude (código) + Daniel (decide) |
| B2 | **El respaldo diario por correo incluye las tablas de correos leídos** (`correos_gasto`: remitente, asunto, snippet; y los extractos de correo) **sin cifrar**, enviadas por Resend a `dapxco@gmail.com`. | Datos de usuario de Google copiados a un tercero (Resend) y a una bandeja personal sin cifrar. También es el hallazgo ALTO de `docs/AUDITORIA_SEGURIDAD.md`. | Excluir esas tablas del backup (cambio pequeño, como ya se hizo con `claves_pdf`) **y** cifrar el adjunto o pasar a backups de Supabase. | Claude (código) |
| B3 | **No hay plazo de retención** de los correos leídos: se conservan mientras exista la cuenta. Además se guardan asunto y snippet de correos que luego quedan `ignorado` (no son movimientos). | Minimización: guardar solo lo necesario. Google pregunta por retención y borrado. | Decidir plazo (propuesta: 12 meses, o hasta aprobar/descartar + 90 días) y (a) vaciar `asunto`/`snippet` de los `ignorado`; (b) tarea de purga. Documentarlo en la política (sección 9). | Daniel decide, Claude código, abogado redacta |
| B4 | **El texto del consentimiento en la app** (`consentimientos.js`, `lectura_correo`) no dice que también busca notificaciones y extractos de bancos sin etiqueta, ni qué se guarda. La Autorización de datos (v1.1) sí lo menciona. | El consentimiento debe coincidir con lo que declaras ante Google. | Usar el texto de la sección 5. Cambiarlo obliga a subir `VERSION_TEXTOS` y pedir autorización de nuevo (decisión de Daniel; ver `CHECKLIST_LANZAMIENTO.md`). | Daniel aprueba, Claude edita |

Otros puntos a verificar (no son brechas de código):

- **URL de la política.** Hoy es `https://cuadrame.dapx.shop/#/legal/privacidad` (ruta con `#`, dentro de la app). Funciona sin sesión, pero el revisor de Google a veces no ejecuta apps de una sola página. **Recomendado:** publicar una copia estática (p. ej. `/privacidad.html`) y usar esa URL en el formulario. Claude puede generarla desde `docs/legal/POLITICA_DE_PRIVACIDAD.md`.
- **Comprobar en vivo** que la sección «Uso de la información recibida de las APIs de Google» (commit `5ebb1d3`) ya está desplegada. Ábrela en ventana de incógnito.
- **RLS en Supabase:** el backend ya la activa al arrancar (`rls.py::asegurar_rls`), pero la auditoría la daba por pendiente. Comprueba con una consulta anónima que devuelve 0 filas antes de contestar «sí» en el cuestionario (paso en `CHECKLIST_LANZAMIENTO.md`).
- **`FERNET_KEY` sin rotación:** respóndelo con honestidad (sección 6).

---

## 2. Requisitos previos (lista)

| Requisito | Estado esperado | Cómo se comprueba |
|---|---|---|
| Dominio propio verificado en **Google Search Console** (`cuadrame.dapx.shop` o `dapx.shop`), con la **misma cuenta de Google** que es propietaria/editora del proyecto de Google Cloud | Verificado | Search Console → propiedad → «Verificada» |
| Dominio autorizado en la pantalla de consentimiento: `dapx.shop` (dominio de nivel superior) | Agregado | Google Auth Platform → Branding → Authorized domains |
| Página de inicio pública que describa la app | `https://cuadrame.dapx.shop/bienvenida.html` | Abrir en incógnito; se ve sin iniciar sesión |
| Política de privacidad pública, en el **mismo dominio**, con sección de Uso Limitado | Ver brechas | Incógnito |
| Términos y condiciones públicos | `https://cuadrame.dapx.shop/#/legal/terminos` | Incógnito |
| Nombre de la app en el consentimiento = el de la web («CuadraMe»); logo 120×120 px | Cargado | Branding |
| Correo de soporte y de contacto del desarrollador (idealmente de dominio propio) | Definido | Branding |
| URI de redirección autorizada = `{API_BASE_URL}/correos/oauth/callback` (hoy `https://backend-production-aeab.up.railway.app/correos/oauth/callback`) | Igual al código | Credentials → cliente OAuth |
| El dominio del callback es de Railway, no tuyo: Google puede pedir dominio verificado. Mejor: apuntar `api.cuadrame.dapx.shop` a Railway y cambiar `API_BASE_URL` y el URI | Recomendado | n/a |
| Video de demostración en YouTube (**no listado**) | Pendiente | Sección 4 |
| Justificación del scope (en inglés) | Lista abajo | Sección 3 |
| Evaluación CASA contratada | Pendiente | Sección 6 |

---

## 3. Justificación del scope (pegar en el formulario, en inglés)

**Campo «How will you use this scope / Why do you need it?»** Copiar tal cual:

```
CuadraMe is a personal-finance app for users in Colombia. Users connect their own Gmail
account so the app can find the bank transaction notifications and PDF bank statements
they already receive, and turn them into SUGGESTED expense/income entries that the user
reviews and approves inside the app. Nothing is created without the user's approval.

Why gmail.readonly: the app must (1) search messages by the label the user chose and by
known bank sender domains / statement keywords, (2) read the subject, sender, date and
snippet of those messages to extract amount, currency and merchant, and (3) download PDF
statement attachments in memory to read the period and account and reconcile it with the
user's records. The Gmail "metadata" scope cannot read message bodies or attachments and
does not support the search query ("q") parameter, so it cannot do this. No narrower
scope provides message content or attachment access, and we do not need write access, so
gmail.readonly is the least-privileged scope that works. We never send, delete, modify or
label messages.

Data minimization: we only query (a) messages carrying the label the user chose,
(b) messages from a fixed list of Colombian bank/fintech sender domains, and (c) bank
messages with a PDF attachment whose name or subject contains statement keywords. We store
only sender, subject, a snippet of at most 400 characters, date and the extracted fields
(amount, currency, merchant). We do not store full message bodies and we do not store PDF
files; the PDF is read in memory and discarded.

User control: Gmail access is opt-in, requires a separate explicit consent checkbox, and
can be disconnected at any time from Profile > Privacy and data; disconnecting revokes the
token at Google and deletes it from our database. Users can also delete their whole account
and all their data.

Limited Use: our use of information received from Google APIs adheres to the Google API
Services User Data Policy, including the Limited Use requirements. We do not sell the data,
do not use it for advertising, do not use it to train generalized AI/ML models, and humans
do not read it except with the user's consent, for security/abuse, or to comply with law.
Refresh tokens are encrypted at rest and all traffic uses HTTPS.
```

> **No pegues el párrafo «Limited Use» hasta cerrar B1 y B2**: hoy no sería cierto.

**Otros campos**

| Campo | Qué poner |
|---|---|
| App name | CuadraMe |
| User type | External |
| Application home page | `https://cuadrame.dapx.shop/bienvenida.html` |
| Privacy policy link | URL estática de la política (ver «Otros puntos») |
| Terms of service link | `https://cuadrame.dapx.shop/#/legal/terminos` |
| Authorized domain | `dapx.shop` |
| Developer contact | correo de dominio propio (o `dapxco@gmail.com` mientras no haya) |
| Scopes | solo `.../auth/gmail.readonly` |
| Demo video | enlace de YouTube no listado |

---

## 4. Guion del video de demostración (4 a 5 min, narración en inglés)

**Reglas de Google:** (1) narración o subtítulos **en inglés**; (2) mostrar el **client_id de OAuth** en la barra de direcciones durante la pantalla de consentimiento; (3) mostrar la pantalla de consentimiento completa con el permiso; (4) mostrar **dónde se usa cada dato** en la app; (5) mostrar cómo se revoca. Grábalo con la app **en producción** y una cuenta de Gmail de prueba con 2 o 3 correos bancarios de ejemplo (sin datos reales de nadie). Sube a YouTube como «No listado».

Antes de grabar: en Gmail crea la etiqueta `gastos` y ponla a un correo de prueba; ten otro correo con un PDF de extracto de ejemplo (sin datos reales); inicia sesión en la app.

| # | Qué mostrar (acción) | Narración en inglés (leer tal cual) |
|---|---|---|
| 1 | Abrir `cuadrame.dapx.shop/bienvenida.html` y bajar | "This is CuadraMe, a personal finance app for people in Colombia. It helps users register and understand their spending." |
| 2 | Mostrar la política de privacidad hasta la sección de APIs de Google | "Our public privacy policy explains how we use information received from Google APIs, including the Limited Use requirements." |
| 3 | Iniciar sesión; ir a Correos / Perfil | "The user signs in with their CuadraMe account. Gmail access is optional and off by default." |
| 4 | Tocar «Conectar Gmail»; aparece el modal; marcar la casilla | "Before connecting, the app asks for a separate, explicit consent that explains what will be read. The checkbox is unchecked by default." |
| 5 | Pulsar «Autorizo». En Google: mostrar **la barra con `client_id=`** y elegir la cuenta | "Now Google's OAuth screen opens. Note the client ID in the address bar." |
| 6 | Mostrar la pantalla de consentimiento con el permiso de ver mensajes (solo lectura); pulsar Permitir | "The only permission requested is read-only access to Gmail. The app cannot send, delete or modify email." |
| 7 | Volver a la app: estado «Conectado» con el correo | "The connection is established. We store only an encrypted refresh token." |
| 8 | Pulsar «Sincronizar»; mostrar el progreso | "The app searches only messages with the label the user chose, plus notifications and statements from known bank senders." |
| 9 | Mostrar la lista de correos sugeridos (monto, comercio, categoría) y abrir uno | "For each detected message we show amount, merchant and a suggested category. Nothing becomes a transaction until the user approves it." |
| 10 | Aprobar uno (aparece en Movimientos) y descartar otro | "When the user approves, a transaction is created. When the user discards, it is not." |
| 11 | Mostrar los extractos encontrados y conciliar uno | "Bank statements in PDF are read in memory to find the period and account and compare them with the user's records. The PDF file is not stored." |
| 12 | Perfil → Privacidad y datos → «Desconectar Gmail» | "The user can disconnect at any time. This revokes the token at Google and deletes it from our database." |
| 13 | Otra pestaña: `myaccount.google.com/permissions`; CuadraMe ya no aparece | "The app no longer appears in the Google account's third-party access list." |
| 14 | Mostrar «Descargar mis datos» y «Borrar mi cuenta» | "Users can also download all their data or delete their account and all data." |
| 15 | Cierre | "This is how CuadraMe uses the gmail.readonly scope: only to help users turn their own bank emails into transactions they approve." |

> Si en el paso 11 el extracto pasara por IA externa, resuelve B1 antes (o usa un banco que el regex reconozca).

---

## 5. Texto del consentimiento en la app (propuesta, español)

Reemplaza `lectura_correo.texto` en `pwa/src/lib/consentimientos.js`. **No publicado:** requiere subir `VERSION_TEXTOS`.

> **Leer mi Gmail, solo lectura.** Autorizo a CuadraMe a leer en mi Gmail, únicamente: los correos con la etiqueta que yo elija, las notificaciones de bancos conocidos y los extractos en PDF de mis bancos. De cada uno guarda remitente, asunto, un fragmento corto y los datos extraídos (monto, comercio, fecha); el PDF no se guarda. Solo se usa para sugerirme movimientos que yo apruebo. No envía, borra ni modifica correos, no se usa para publicidad ni para entrenar inteligencia artificial, y no se vende. Puedo desconectarlo cuando quiera en Perfil → Privacidad y datos y eso revoca el permiso en Google.

Debe ser coherente con `docs/legal/POLITICA_DE_PRIVACIDAD.md` (secciones 3, 5, 9) y con `pwa/src/screens/legal/AutorizacionDatos.jsx` (sección 2). La frase «ni para entrenar IA» solo es cierta cuando B1 esté cerrada.

---

## 6. Cuestionario de seguridad (CASA / evaluación de seguridad): qué responder

CASA (Cloud Application Security Assessment) la hace un evaluador autorizado por Google; Google envía la lista de evaluadores al iniciar la verificación. Para una app pequeña suele ser **Tier 2** (escaneo + cuestionario) y se repite cada año. El costo lo fija el evaluador: **cotiza con 2 o 3 y confirma el precio vigente** antes de comprometerte.

Responde solo lo que el código cumple:

| Pregunta típica | Respuesta honesta | Evidencia |
|---|---|---|
| ¿Cifrado en tránsito? | Sí. HTTPS en PWA (Vercel) y API (Railway); HSTS en ambos; conexión a Postgres de Supabase con TLS. | `pwa/vercel.json`, cabeceras en `main.py` |
| ¿Cifrado en reposo? | Base de datos: cifrado en reposo del proveedor (Supabase). Tokens de Gmail y clave de PDF: cifrado adicional de aplicación (Fernet). | `gmail_oauth.py` |
| ¿Dónde están las claves? | Variables de entorno en Railway; no están en el repositorio. | `config.py` |
| ¿Rotación de claves? | **No hay rotación automática de `FERNET_KEY`** (pendiente `MultiFernet`). Decirlo. | `AUDITORIA_SEGURIDAD.md` §3 |
| ¿Autenticación y autorización? | Supabase Auth (JWT con `exp` y `sub`); toda consulta filtra por `usuario_id`; 196 endpoints probados contra acceso cruzado; roles en cuentas compartidas. | `tests/test_aislamiento_usuarios.py` |
| ¿Aislamiento / RLS? | RLS activada en las tablas públicas al arrancar el backend; el backend usa conexión directa. **Verifica antes de afirmarlo.** | `rls.py`, `habilitar_rls.sql` |
| ¿Límites de uso / abuso? | 240 peticiones/min por usuario; Gmail 80 sync/h y 300/día; cuerpo máx. 2 MB; PDF ≤ 15 MB; crons con secreto en tiempo constante. | `limites.py`, `limites_diarios.py` |
| ¿Registros (logs)? | No se registran tokens, claves, montos ni cuerpos; Sentry filtra cabeceras, cuerpos y variables locales. | `AUDITORIA_SEGURIDAD.md` §1 y #9 |
| ¿Pruebas de seguridad? | Auditoría interna con pruebas automáticas; sin pentest externo; `pip-audit`/`npm audit` aún no están en CI (**pendiente**). | `AUDITORIA_SEGURIDAD.md` |
| ¿Retención de datos de Gmail? | Hoy: mientras exista la cuenta (**B3**). Meta: plazo definido y purga. | n/a |
| ¿Borrado? | Desconectar revoca y borra el token. «Borrar mi cuenta» borra todos los datos y, con `SUPABASE_SERVICE_ROLE_KEY`, el login. Copias de respaldo: ver B2. | `AUDITORIA_SEGURIDAD.md` §5 |
| ¿Quién accede a los datos? | Una persona (el dueño) con acceso administrativo; no se leen correos de usuarios salvo soporte con consentimiento, seguridad o ley. | Política §5 |
| ¿Subprocesadores? | Supabase, Railway, Vercel, Resend, Sentry; OpenRouter (IA, solo si el usuario usa esas funciones). | Autorización de datos §5 |
| ¿Respuesta a incidentes? | Informal (Sentry + avisos al administrador); la política promete notificar. **Redacta 1 página**: quién, qué, en cuánto tiempo. | n/a |
| ¿Copias de seguridad? | Diaria por correo, sin cifrar (**hallazgo ALTO**, B2). Aceptable solo tras cifrar o pasar a backups de Supabase. | `backup.py` |

---

## 7. Paso a paso en Google Cloud (clics)

1. `console.cloud.google.com` → proyecto de CuadraMe → menú ☰ → **APIs y servicios → Pantalla de consentimiento de OAuth** (o «Google Auth Platform»).
2. **Branding:** nombre, correo de soporte, logo, página de inicio, política, términos, dominio autorizado `dapx.shop`, correo del desarrollador. Guardar.
3. **Audience:** tipo **External**. Para enviar la verificación se pasa de «Testing» a **In production** («Publish app»).
4. **Data Access:** «Add or remove scopes» → buscar `gmail.readonly` → marcar → pegar la justificación de la sección 3 → guardar.
5. **Verification Center:** «Prepare for verification» → pegar el enlace del video → confirmar dominios → **Submit**.
6. Google responde por correo al contacto del desarrollador (revisa spam). Responde **en el mismo hilo**, en inglés, en menos de 7 días: si no, la solicitud se cierra.
7. Cuando Google lo indique, contrata la evaluación CASA, completa el cuestionario y sube la **Carta de Validación (LOA)**.
8. Con la aprobación: en Railway `GMAIL_MODO_PRUEBAS=false` y sube o quita `GMAIL_TOPE_USUARIOS`.

---

## 8. Lista de verificación previa al envío

- [ ] B1, B2, B3 y B4 resueltas (o decididas y anotadas).
- [ ] Política estática pública, con Uso Limitado, abierta en incógnito.
- [ ] Dominio verificado en Search Console con la cuenta correcta.
- [ ] `dapx.shop` en Authorized domains; nombre y logo coinciden con la web.
- [ ] El URI de redirección del cliente OAuth es **idéntico** al `REDIRECT_URI` del backend.
- [ ] Solo `gmail.readonly` en Data Access.
- [ ] Video en inglés, con `client_id`, consentimiento, uso del dato y revocación; sin datos reales de terceros.
- [ ] La app está en producción y funciona sin pedir tarjeta.
- [ ] Cuenta de prueba para el revisor con datos de ejemplo; se entrega por el formulario, **nunca** en el repositorio.
- [ ] Cada respuesta del cuestionario revisada contra el código (sección 6).
- [ ] Alguien atento al correo para contestar a Google en menos de 7 días.

## 9. Errores típicos de rechazo

| Rechazo | Causa | Solución |
|---|---|---|
| «Homepage doesn't describe the app» | La home es un login o solo muestra la app | Usar `bienvenida.html` con descripción visible |
| «Privacy policy missing Limited Use disclosure» | Falta la frase de Uso Limitado | Ya está en la política; verificar que esté publicada |
| «Domain not verified / does not match» | Search Console con otra cuenta, o redirección en dominio ajeno (Railway) | Verificar con la misma cuenta; usar `api.cuadrame.dapx.shop` |
| «Video doesn't show the OAuth flow» | Falta el `client_id` o el consentimiento recortado | Grabar el navegador completo, 1080p |
| «Scope not justified / unnecessary» | Justificación vaga o scopes de más | Texto de la sección 3; un solo scope |
| «App uses data beyond disclosed» | Se detecta IA externa o respaldos con datos de Gmail | Cerrar B1 y B2 |
| «App name mismatch» | Nombre en Cloud distinto al de la web/app | «CuadraMe» en los tres |
| Solicitud cerrada por falta de respuesta | Correo de Google perdido | Revisar spam; responder rápido |
