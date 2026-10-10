# Precios y planes de CuadraMe: propuesta basada en el costo real

**Objetivo:** que Daniel decida si cobra, cuánto, por qué funciones y por qué canal, sabiendo cuánto cuesta cada usuario.
**Tiempo estimado:** 25 min de lectura + decisión. Cobrar de verdad exige 2–4 días de desarrollo (sección 6).
**Aviso:** los precios de proveedores son de referencia (los cambian); **confirma cada uno** en su página antes de comprometer dinero. Tasa supuesta: 1 USD = 4.000 COP (ajusta con la del día). Nada aquí es asesoría tributaria ni legal.

---

## 1. Cuánto cuesta hoy y cuánto costará

### 1.1 Costos fijos por escalón

| Proveedor | Hoy (gratis) | Cuándo toca pagar | Plan de pago (ref.) | Aprox. USD/mes |
|---|---|---|---|---|
| Supabase (base + login) | 500 MB, **sin backups automáticos** | ~100–150 usuarios activos (ver 1.2) o cuando quieras backups reales | Pro | 25 |
| Railway (API) | uso bajo | ~300 usuarios activos o más memoria | Hobby/Pro por consumo | 5–20 |
| Vercel (web) | Hobby | **Hobby es para uso no comercial**: al cobrar, Pro | Pro por persona | 20 |
| Resend (correos) | 100/día y 3.000/mes | ~100 personas con resumen semanal (el cron los manda todos el mismo domingo y topa los 100/día) | Pro (50.000/mes) | 20 |
| OpenRouter (IA) | modelo `:free` | cuando el modelo gratis se agote o se cierre B1 de `GOOGLE_VERIFICACION.md` | prepago por uso | 3–15 |
| Sentry (errores) | Developer gratis | rara vez al inicio | Team | 0–26 |
| Dominio (`dapx.shop`) | pagado | n/a | anual | ~1–2 |
| Evaluación CASA de Google | n/a | para abrir Gmail a todos | anual, la fija el evaluador | **cotizar** (ver `GOOGLE_VERIFICACION.md`) |

**Escalón «ya cobro y quiero dormir tranquilo»** (Supabase Pro + Railway + Vercel Pro + Resend Pro + IA + Sentry gratis): **≈ USD 75–95/mes ≈ COP 300.000–380.000/mes**, más la evaluación anual de Google.

### 1.2 Costo variable por usuario activo (sale de los límites del código)

| Recurso | Límite en el código | Uso típico/mes | Uso máximo posible/mes | Costo típico | Costo en el peor caso |
|---|---|---|---|---|---|
| Base de datos | sin tope por usuario (**brecha**) | ~3–5 MB por usuario/año (movimientos, correos, extractos) | n/a | ~0 (ya incluido en Pro 8 GB) | un usuario abusivo puede llenar el disco |
| Preguntas a la IA | 40/día (`preguntar`) | ~20/mes | 1.200/mes | < COP 100 | ~COP 4.000–6.000 con un modelo barato de pago |
| Facturas escaneadas | 30/día | 3/mes | 900/mes | < COP 50 | ~COP 3.000 |
| Extractos procesados | 40/día; PDF ≤ 15 MB | 3/mes | 1.200/mes | ~COP 0 (regex) a 100 (IA) | ~COP 4.000 si todo va a IA |
| Gmail (sincronizaciones) | 300/día, 80/h, 40 correos por lote | 240 (cada 3 h) | 9.000 | ~COP 0 (API gratuita; costo de CPU) | CPU/tiempo de Railway |
| Correos salientes (Resend) | resumen semanal 1/semana, cierre de mes 1 | ~5–6 | ~10 | ~COP 5–10 con plan Pro | n/a |
| Peticiones a la API | 240/min por usuario | miles | ~10 millones | ~COP 0 | CPU de Railway |

**Lectura:** el costo **por usuario** es muy bajo (COP 100–500/mes típico). Lo que cuesta es el **escalón fijo** y la **verificación de Google**. Cobrar sirve sobre todo para cubrir esos fijos y el tiempo de soporte, no los usuarios individuales.

### 1.3 Punto de equilibrio

Costo fijo ≈ COP 340.000/mes (punto medio). Comisión de la pasarela ≈ 3–4 % + tarifa fija por transacción (**verifica con la pasarela**; supongamos 5 % efectivo en cobros pequeños).

| Precio mensual (COP) | Neto aprox. | Suscriptores para cubrir fijos |
|---|---|---|
| 7.900 | 7.500 | 45 |
| 9.900 | 9.400 | 37 |
| 14.900 | 14.100 | 25 |

Con conversión freemium de 3–5 %: 37 suscriptores = **750–1.250 usuarios registrados**. Antes de eso el negocio está subsidiado: es normal; decide cuánto tiempo y cuánto dinero pones.

---

## 2. Qué funciones son de pago y cuáles NUNCA

**Siempre gratis (dan confianza y seguridad; cobrarlas contradice la promesa de privacidad):**
- Registrar movimientos a mano, cuentas, categorías, presupuestos y metas básicas.
- Acceso protegido: PIN, biometría, cifrado, cabeceras de seguridad.
- Descargar mis datos, borrar mi cuenta, desconectar Gmail, revocar autorizaciones.
- Política y autorización claras, avisos de seguridad.
- Atajo de registro rápido (es el hábito que retiene a la gente).
- Recordatorios de presupuesto y vencimientos (push).
- Exportar mis movimientos (CSV).

**Candidatas a pago (cuestan dinero real o requieren soporte):**

| Función | Por qué | Costo que cubre |
|---|---|---|
| Registro automático desde Gmail (más de 1 banco o sincronización frecuente) | Verificación/CASA anual, CPU, soporte | Evaluación Google + Railway |
| Asistente de IA más allá de ~10 preguntas/mes | Paga tokens | OpenRouter |
| Escaneo de facturas y extractos con IA | Paga tokens | OpenRouter |
| Conciliación de extractos | Valor alto para quien lo usa; consumo de CPU | Railway |
| Resumen semanal por correo y cierre de mes | Correos de Resend | Resend |
| Cuentas compartidas con más de 2 personas | Aumenta carga y soporte | Soporte |
| Informes avanzados, renta/impuestos, patrimonio | Valor percibido alto | Desarrollo |
| Historial de más de 12 meses en informes | Almacenamiento | Supabase |

Regla de diseño: **lo que el usuario necesita para no perder su plata ni su privacidad es gratis; lo que le ahorra tiempo y nos cuesta, es de pago.**

---

## 3. Tres estructuras posibles

### A. Gratis + Pro por suscripción mensual (la más común)
- **Gratis:** todo lo básico + 1 banco por Gmail + 10 preguntas de IA/mes.
- **Pro (COP 9.900/mes o COP 89.000/año):** Gmail ilimitado y frecuente, IA ampliada, extractos, resumen semanal, informes.
- Ventaja: ingreso recurrente y predecible. Riesgo: hay que justificar el pago cada mes.

### B. «Gratis con funciones avanzadas de pago» por paquetes
- **Gratis:** casi todo, con tope de uso (ya existen: `limites_diarios.py`).
- **Paquete «Automático» (COP 6.900/mes):** Gmail + extractos.
- **Paquete «Asesor» (COP 6.900/mes):** IA + informes + renta.
- Ventaja: se paga solo por lo que se usa. Riesgo: más complejidad de cobro y de mensajes.

### C. Pago anual simple, con oferta de fundadores
- **Fundadores (primeros 100):** COP 59.000/año, precio congelado.
- **Después:** COP 89.000/año.
- Sin plan gratis ilimitado: prueba de 30 días con todo.
- Ventaja: menos transacciones, menos comisión por unidad, flujo de caja al inicio. Riesgo: menos registros porque hay que pagar.

**Sobre el pago único «de por vida» que ya existe en el código (COP 20.000, `STRIPE_PRICE_LIFETIME_COP`):** no lo recomiendo como plan permanente: hay costos fijos anuales (evaluación de Google, Supabase) y un cliente de «por vida» no los cubre. Útil solo como oferta limitada de fundadores.

---

## 4. Cómo cobrar en Colombia

| Opción | Métodos | Suscripción recurrente | Lo bueno | Lo malo |
|---|---|---|---|---|
| **Wompi** (Bancolombia) | Tarjetas, PSE, Nequi, botón Bancolombia | Cobros con tarjeta tokenizada: **la programación la haces tú** | PSE y Nequi (muy usados); cuenta en pesos | Más código para renovar/cancelar |
| **Mercado Pago** | Tarjetas, PSE, efectivo, saldo | Suscripciones nativas (`preapproval`) | Menos código de renovación | Comisiones y retención de saldo; revisar |
| **Stripe** (ya está en el código) | Tarjetas internacionales | Suscripciones nativas muy buenas | Mejor API y documentación | **Verifica si puedes abrir una cuenta como persona o empresa colombiana**; menos métodos locales (sin PSE/Nequi) |
| ePayco / PayU | Tarjetas, PSE, efectivo | Según producto | Muy conocidos localmente | Interfaz y comisiones variables |

**Recomendación:** **Wompi** para el primer cobro (PSE + Nequi + tarjeta) con **plan anual o cobro mensual manual con recordatorio**; Stripe solo si abres cuenta y vendes a tarjetas internacionales.

**Impuestos y retenciones, a muy alto nivel (confirma con un contador):**
- Tu régimen (persona natural o empresa, responsable de IVA o no) decide si el precio lleva IVA y si debes facturar electrónicamente.
- Los servicios digitales prestados a personas en Colombia pueden causar IVA; define si el precio publicado **incluye** IVA.
- Las pasarelas suelen practicar retenciones y comisiones que ven tu contador y tu declaración.
- La venta por internet a consumidores trae obligaciones del Estatuto del Consumidor (derecho de retracto, política de cancelación y reembolso, términos claros). Va al abogado junto con los T&C, que hoy dicen «gratis».

**Preguntas para el contador** (llévalas escritas): ¿persona natural o SAS?, ¿IVA sobre este servicio?, ¿factura electrónica obligatoria desde el primer peso?, ¿cómo se registra el ingreso de la pasarela?

---

## 5. Qué ya existe en el backend y qué falta

**Existe** (`backend/app/routers/pagos.py`):
- `GET /pagos/plan` devuelve `free` o `pro` del perfil.
- `POST /pagos/checkout` crea una sesión de Stripe de **pago único** (COP, `STRIPE_PRICE_LIFETIME_COP`), con URL de retorno validada (arreglo de la auditoría).
- `POST /pagos/webhook` verifica firma y marca `plan = "pro"` en `checkout.session.completed`; sin `STRIPE_WEBHOOK_SECRET` responde 503.
- Variables: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_LIFETIME_COP`.

**Falta:**
1. **Ninguna función está bloqueada por plan hoy**: el backend y la PWA no consultan `plan == pro` en ninguna parte. Hay que decidir qué se bloquea y aplicar el control en el **backend** (no solo ocultar botones).
2. **Suscripción:** pasar de `mode="payment"` a `mode="subscription"` (Stripe) o a cobros recurrentes (Wompi/Mercado Pago).
3. **Ciclo de vida:** renovación, fallo de pago, cancelación, vencimiento. Campos nuevos: `plan_vence_en`, `proveedor`, `suscripcion_id`; manejar los eventos `invoice.paid`, `invoice.payment_failed`, `customer.subscription.deleted`.
4. **Pantalla de planes** en la PWA, con comparación gratis/Pro y botón de cancelar.
5. **Gestión de suscripción** (portal de cliente de Stripe o pantalla propia) y comprobante/recibo por correo.
6. **Textos legales:** T&C y política dicen «gratis»; añadir precios, renovación, cancelación, reembolso (abogado), y subir `VERSION_TEXTOS`.
7. **Prueba con tarjetas de prueba** y un cron que degrade a `free` los vencidos.
8. **Topes por plan** en `limites_diarios.py` (hoy son iguales para todos) y cuota de almacenamiento por usuario.
9. **Facturación/contabilidad** según tu contador.

---

## 6. Preguntas de decisión para Daniel (con mi recomendación)

| # | Pregunta | Recomendación |
|---|---|---|
| 1 | ¿Cobrar ya o primero ganar usuarios y verificar Gmail? | **Primero** validar con 5 personas (`PRUEBA_CON_PERSONAS.md`) y cerrar la verificación de Google; cobrar desde ~100 usuarios activos o cuando el escalón fijo supere lo que quieres subsidiar. |
| 2 | ¿Qué estructura: A, B o C? | **A (gratis + Pro mensual/anual)**, con oferta de fundadores a COP 59.000/año para los primeros 100. |
| 3 | ¿Qué precio? | **COP 9.900/mes o COP 89.000/año**; prueba de 14 días con todo. |
| 4 | ¿Qué es de pago? | Gmail multibanco, extractos con IA, IA ampliada, resumen semanal, informes avanzados. Lo de seguridad/privacidad, siempre gratis. |
| 5 | ¿Qué pasarela? | **Wompi** primero; Stripe si te dan cuenta y quieres tarjetas internacionales. |
| 6 | ¿Qué hacer con el «de por vida» a COP 20.000 del código? | Quitarlo como plan; usarlo como oferta limitada o retirarlo. |
| 7 | ¿Persona natural o formalizarte? | Habla con un contador **antes** del primer cobro. |
| 8 | ¿Quién atiende reclamos y cancelaciones? | Tú, con un correo de dominio (`hola@cuadrame.dapx.shop`) y plazo de respuesta publicado. |

**Orden sugerido:** (1) cerrar B1/B2 de Google y verificar dominio de correo; (2) prueba con 5 personas; (3) contador + abogado; (4) construir cobro (2–4 días); (5) lanzar con fundadores.
