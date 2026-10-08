# Auditoría de seguridad, derechos del titular y carga — CuadraMe backend

Alcance: todo `backend/app` (35 routers, 196 endpoints), sin tocar producción ni leer secretos.
Método: lectura del código + pruebas automáticas con dos usuarios sintéticos + prueba de carga local.
Severidad: **Alta** = dinero, datos de terceros o caída total · **Media** = daño real pero acotado · **Baja** = endurecimiento.

## 1. Lo que se verificó y quedó bien

| Tema | Resultado |
|---|---|
| Autorización por usuario (IDOR) | **Sin fugas de lectura ni escritura entre usuarios** en los 196 endpoints. `tests/test_aislamiento_usuarios.py` siembra datos de A en todos los módulos y B los ataca por id (cuentas, movimientos, correos, extractos, historial de conciliación, reglas, metas, presupuestos, deudas, activos, planes de cuotas, gastos compartidos...): 4xx y la foto completa de las filas de A no cambia. |
| Cobertura futura | `test_todo_endpoint_esta_clasificado` **falla** si alguien agrega un endpoint sin clasificarlo en esa prueba. |
| Sin sesión | Los 150+ endpoints de usuario responden 401; los 13 crons exigen `X-Cron-Secret` (comparación en tiempo constante); `/movimientos/rapido*` rechazan clave falsa. |
| Roles de cuenta compartida | Lector solo lee; editor mueve movimientos pero no edita/borra la cuenta, no invita ni ve accesos (`tests/test_roles_cuenta_compartida.py`). |
| Tokens de Gmail y clave de PDF | Cifrados con Fernet; ningún esquema de respuesta los devuelve. La clave del Atajo se guarda como hash SHA-256. |
| OAuth de Gmail | `state` cifrado con caducidad de 10 min. |
| Inyección SQL | Todo va por ORM con parámetros; el único SQL en texto (`rls.py`, migraciones de arranque) no usa entradas de usuario. Los `ilike` escapan comodines. |
| Subida de archivos | PDF ≤ 15 MB y extracto ≤ 6 páginas en Gmail; imágenes ≤ 1,5 MB validadas por firma; Excel/CSV con tope de filas; PDFs protegidos piden clave y no la registran. |
| Logs | No se registran claves, tokens, montos ni cuerpos; los errores de cron registran solo el id de usuario. |
| Docs de la API | `/docs`, `/redoc` y `/openapi.json` apagados en producción. |

## 2. Defectos encontrados y CORREGIDOS (con prueba)

| # | Sev. | Defecto | Corrección | Prueba |
|---|---|---|---|---|
| 1 | **Alta** | **Bloqueo total bajo carga.** Con 100 usuarios simultáneos el servidor se colgaba 30 s y respondía 500 al 100 % (1,7 req/s). Los endpoints síncronos esperaban una conexión del pool y las conexiones las retenían peticiones ya terminadas que esperaban un hilo para serializar/cerrar. En Railway pasaría con una ráfaga (p. ej. varios crons + usuarios a la vez). | `get_db` ahora es `async`, limita las sesiones abiertas a (conexiones − 2) esperando en el bucle de eventos (sin gastar hilos) y cierra la sesión en hilos propios. Tras el arreglo: 100 usuarios, 0 errores, ~38-50 req/s. | `tests/test_concurrencia.py` (100 peticiones simultáneas; sin el arreglo se cuelga) |
| 2 | **Alta** | **Webhook de Stripe con secreto vacío.** Si `STRIPE_WEBHOOK_SECRET` no está en Railway, la firma se calcula con clave vacía y cualquiera puede fabricar «pago completado» y volverse Pro gratis. | Sin secreto configurado responde 503. | `test_webhook_sin_secreto_configurado_no_acepta_firmas_forjadas` |
| 3 | Media | **Redirección abierta en el checkout**: `startswith(pwa_url)` aceptaba `https://pwa-seven-ecru.vercel.app.malo.com` y `http://localhost.malo.com`. | Se compara el origen real (esquema, host, puerto), sin credenciales en la URL. | `test_url_de_retorno_de_stripe` (11 casos) |
| 4 | Media | **IDOR de escritura**: `POST /recurrentes` y `POST /deudas` aceptaban el `cuenta_id` de otra persona y lo guardaban (el pago luego sí filtraba, pero el dato quedaba atado a una cuenta ajena). | `exigir_cuenta_propia` (404). | `test_aislamiento_usuarios.py`, `test_roles_cuenta_compartida.py` |
| 5 | Media | **Desconectar Gmail no revocaba el permiso en Google**; solo borraba el token local. | `revocar_token` (best-effort, nunca lanza); se usa al desconectar y al borrar la cuenta. | `test_revocar_token_*`, `test_desconectar_gmail_revoca_*` |
| 6 | Media | **Inyección de fórmulas en CSV/Excel**: una descripción de correo/PDF de un tercero como `=HYPERLINK(...)` se ejecuta al abrir la descarga. | `celda_segura` en exportaciones de movimientos, renta y «mis datos». | `test_csv_de_la_descarga_neutraliza_formulas` |
| 7 | Media | **Sin tope de tamaño de cuerpo** (cualquier usuario podía mandar cientos de MB) y **JSON con `NaN`/`Infinity`** (un saldo infinito rompía con 500 todas las respuestas de ese usuario). | Middleware: 2 MB por defecto, 25 MB solo en rutas de archivos; rechaza NaN/Infinity con 422. Topes de largo en textos libres (descripción, notas, nombres). | `test_cuerpo_grande_*`, `test_json_con_nan_o_infinity_*` |
| 8 | Baja | Sin cabeceras de seguridad. | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, HSTS, CSP restrictiva, `Cache-Control: no-store` en toda respuesta. | `test_toda_respuesta_lleva_cabeceras_de_seguridad` |
| 9 | Baja | Sentry podía recibir variables locales (tokens, claves de PDF, montos) y cabeceras. | `include_local_variables=False` + `before_send` que filtra Authorization, X-Api-Key, X-Cron-Secret, cuerpos y query string. | `test_sentry_no_recibe_cuerpos_ni_claves` |
| 10 | Baja | El JWT no exigía `exp`; no había tope general de peticiones por usuario. | `require: [exp, sub]`; 240 peticiones/min por usuario (429 con `Retry-After`). | `test_token_valido_entra_*`, `test_tope_general_por_usuario_*` |
| 11 | Baja | PDF subido sin tope de páginas, con base64 roto → 500. | Máx. 60 páginas, valida `%PDF-`, base64 inválido ya no da 500. | `test_pdf_con_base64_roto_*`, `test_solo_se_leen_las_primeras_paginas` |
| 12 | Baja | Callback de Gmail con código vencido → 500; etiqueta de Gmail sin tope de largo. | Redirige a la app con `gmail=error`; máx. 80 caracteres. | `test_callback_de_gmail_*`, `test_etiqueta_*` |
| 13 | Baja | El backup diario incluía la clave del Atajo antigua **en claro** (`perfiles.api_key`). | Se excluye del backup (el hash sí viaja). | — (cambio de 1 línea en `app/backup.py`) |

Rendimiento corregido (sección 4): consultas N+1 en presupuestos y en la cuadrícula de sincronización.

## 3. PENDIENTE — requiere decisión o acción de Daniel

| Sev. | Hallazgo | Recomendación |
|---|---|---|
| **Alta** | **El backup diario manda TODA la base (datos financieros de todos los clientes) por correo, sin cifrar**, a `dapxco@gmail.com` vía Resend. Con muchos clientes es una concentración de datos en una bandeja de correo, y el borrado por Ley 1581 no alcanza a copias ya enviadas. | Antes de vender a escala: pasar a plan Supabase con backups automáticos (PITR) y apagar el correo, o cifrar el adjunto (Fernet/age) y definir retención (p. ej. borrar copias > 30 días). Decidir y documentar en la política de privacidad el plazo en que un borrado llega a los respaldos. |
| **Alta** | **RLS de Supabase sin activar** (`backend/supabase/habilitar_rls.sql`, ya en el backlog). El backend usa conexión directa y no depende de RLS, pero sin RLS cualquiera con la `anon key` (pública en la PWA) puede leer tablas vía la API REST de Supabase. | Ejecutar `habilitar_rls.sql` en Supabase (acción de Daniel) y comprobar con una consulta anónima que devuelve 0 filas. |
| **Alta** | **«Confirmar correo» en Supabase Auth.** Las invitaciones a cuentas compartidas se aceptan por coincidencia de correo del JWT. Si el registro permite correos sin confirmar, alguien podría registrarse con el correo de otra persona y aceptar sus invitaciones. | Verificar en Supabase → Auth → Providers → Email que *Confirm email* esté **activado**. Si no lo está, activarlo (o exigir `email_verified` en el backend, lo que cerraría sesión a los usuarios sin confirmar: coordinar). |
| Media | `SUPABASE_SERVICE_ROLE_KEY` no configurada ⇒ «Borrar mi cuenta» borra todos los datos pero **deja el login (correo) en Supabase Auth**. | Ponerla solo en Railway (nunca en el repo ni en Vercel). La respuesta ya avisa `auth_eliminado: false`. |
| Media | Límites de uso **en memoria** (1 réplica). Con 2+ réplicas en Railway cada una cuenta aparte, y cada despliegue los reinicia. | Mantener 1 réplica o mover los contadores a Redis/base antes de escalar. La prueba de carga mostró que 1 réplica atiende ~40-50 req/s. |
| Media | Sin cuotas de almacenamiento por usuario (movimientos, cuentas, categorías ilimitadas). | Definir topes por plan (decisión de producto). |
| Media | Una sola `FERNET_KEY` sin rotación: si se pierde, se pierden todos los tokens de Gmail y claves de PDF. | Guardarla en el gestor de secretos y planear `MultiFernet` para rotarla. |
| Baja | `ip_cliente` toma el primer valor de `X-Forwarded-For`, que el cliente puede falsear (evade el tope de claves de Atajo inválidas; la fuerza bruta sigue siendo inviable: 192 bits). | Usar la IP que añade el proxy de Railway cuando se confirme cuántos proxies hay delante. |
| Baja | La PWA guarda la sesión en el navegador (`localStorage`): un XSS la expondría. La PWA no tenía NINGUNA cabecera de seguridad; se agregó `pwa/vercel.json` (nosniff, anti-iframe, HSTS, Referrer-Policy; se aplica en el próximo deploy). Falta una CSP: requiere probarla con Supabase, Sentry y las fuentes antes de activarla. | Armar una CSP en modo `Content-Security-Policy-Report-Only` primero, y revisar dependencias del frontend. |
| Baja | No se ejecutó `pip-audit`/`npm audit` en CI. | Agregarlo al workflow de CI. |
| Info | Los índices nuevos (`backend/supabase/migraciones/indices_rendimiento.sql`) **no se ejecutaron**. | Correr una vez en Supabase → SQL Editor cuando se apruebe (idempotente). |

## 4. Prueba de carga y rendimiento

Herramienta: `backend/tools/prueba_carga.py` (datos sintéticos, SQLite temporal, servidor en proceso aparte, autenticación de prueba solo dentro del script).

```
cd backend
python tools/prueba_carga.py                          # 100 usuarios, 30 s (pausa 1-3 s entre acciones)
python tools/prueba_carga.py --pausa 0.05 0.25        # saturación extrema
python tools/prueba_carga.py --modo consultas --movimientos 2000 --cuentas 12 --presupuestos 20
```

Resultados (equipo de desarrollo, SQLite — una escritura a la vez, peor que Postgres):

| Escenario | Antes | Después |
|---|---|---|
| 100 usuarios simultáneos | 1,7 req/s, **100 % errores** (bloqueo del pool) | **~38 req/s, 0 errores**, p50 global 158 ms, p95 ≈ 2,4 s (casi todo el p95 es el arranque simultáneo de los 100) |
| Saturación (pausa 0,05-0,25 s) | igual de bloqueado | 51 req/s, 0 errores (se pone en cola, no se cae) |

Cuellos de botella y correcciones:

* **Pool de conexiones** (hallazgo 1): el más grave; resuelto.
* `GET /presupuestos/disponible-hoy` hacía **2 consultas por presupuesto × 4 periodos** (25 consultas con 5 presupuestos, ~100 con 20) y recalculaba el emparejamiento de traslados en cada una. Ahora: una consulta de movimientos para toda la ventana, una de cuentas, y el gasto por categoría se calcula una vez por periodo. 25 → 6 consultas; 317 → 90 ms con 20 presupuestos y 2000 movimientos. También acelera las alertas de presupuesto del cron.
* `GET /sincronizacion/estado` hacía **una consulta por mes** de la cuadrícula (hasta 24). Ahora una sola agrupada por cuenta y mes.
* Índices compuestos que faltaban: `movimientos (cuenta_id, fecha)`, `movimientos (usuario_id, fecha)`, parcial de «por confirmar», y `(usuario_id, estado)` en correos y extractos. Declarados en los modelos (bases nuevas) y en `backend/supabase/migraciones/indices_rendimiento.sql` (bases existentes; **no ejecutado**).
* Ya no crece el número de consultas con los datos: `tests/test_consultas_por_peticion.py` lo protege.

Lo que sigue mandando el rendimiento: los reportes pesados (`/informes/gasto`, `/insights/*`) leen y agregan en Python (~50-150 ms con 2000 movimientos). Si algún cliente acumula 50 000+ movimientos conviene pasar esas sumas a SQL (`GROUP BY`).

## 5. Derechos del titular (Ley 1581 de 2012)

* **Descargar mis datos**: `GET /perfil/mis-datos` (ZIP con `datos.json`, un CSV por tabla y un LEEME) o `?formato=json`. Recorre todas las tablas con `usuario_id` (una tabla nueva queda incluida sola), más lo escrito por otros en sus cuentas compartidas y las tablas hijas. **No incluye** claves/tokens (clave del Atajo, token de Gmail, clave de PDF, llaves push). Límite: 5 por hora.
* **Borrar mi cuenta y todos mis datos**: `POST /perfil/eliminar-cuenta` con `confirmacion="ELIMINAR"` (escrita por la persona; solo actúa sobre la sesión de quien llama). Revoca el permiso de Gmail en Google, deshace en el saldo del dueño lo que la persona registró en cuentas ajenas, borra todo lo de sus cuentas (incluido lo escrito por editores y las marcas fiscales de otros sobre esos movimientos), las tablas hijas sin `usuario_id` y, si hay `SUPABASE_SERVICE_ROLE_KEY`, el login. `test_borrar_cuenta_sin_huerfanos_*` recorre **todas las columnas de texto de todas las tablas** buscando ids de lo borrado y exige cero. `test_toda_tabla_sin_usuario_id_esta_clasificada` obliga a decidir el tratamiento de cualquier tabla hija nueva.
* **PWA**: Perfil → Privacidad y datos → «Descargar mis datos» y «Borrar mi cuenta y todos mis datos» (hoja con lenguaje simple, escribir ELIMINAR, opción de descargar antes). Nada se ejecutó contra datos reales; las pruebas usan usuarios sintéticos.
* Pendiente de política (ver sección 3): plazo en que un borrado alcanza a los respaldos ya enviados por correo.
