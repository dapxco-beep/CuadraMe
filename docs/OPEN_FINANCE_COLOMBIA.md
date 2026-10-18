# Finanzas abiertas en Colombia: viabilidad para CuadraMe

Fecha de consulta de todas las fuentes: 12-oct-2026. Es investigación, no asesoría legal. Lo que no se pudo verificar en el texto oficial está marcado "no confirmado".

## 1. Resumen y recomendación

- El Decreto 368 de 2026 hace obligatorio el sistema, pero **obliga a los bancos a abrir datos solo a terceros vigilados**. Para un tercero **no vigilado** (CuadraMe hoy) el acceso es **voluntario y por acuerdo bilateral** con cada banco. El banco no está obligado a aceptarlo.
- El estándar oficial no estará operativo pronto. El directorio de participantes se espera para abril de 2027 y el acceso de datos por categoría llega hasta 12 meses después de publicados los estándares (más una prórroga posible de 6). Hay además un borrador de decreto (22-sep-2026) que ajusta esos plazos.
- Recomendación: **no integrar directo ahora. Seguir con Gmail/PDF/Excel/atajo, pilotar un agregador con licencia (Belvo o Finerio) solo si hay demanda comprobable, y revisar el estándar oficial en 12 meses.** Detalle de fases en la sección 7.

## 2. Decreto 368 de 2026 (7-abr-2026)

Fuente: texto en normograma y CER (enlaces al final). Resumen verificado en un resumen del texto; **los números de artículo no se confirmaron** (no se pudo leer el decreto completo).

- Modifica el Decreto 2555 de 2010 e incorpora un sistema de finanzas abiertas **obligatorio** para entidades vigiladas. Regula acceso, suministro, tratamiento y circulación de datos personales y financieros con autorización del titular.
- Figuras: **proveedor de datos** (entidad vigilada obligada), **tercero receptor vigilado** y **tercero receptor no vigilado** (esquemas voluntarios).
- Obligados: bancos, establecimientos de crédito, aseguradoras, administradoras de pensiones, comisionistas/valores. Deben dar acceso a terceros vigilados; **no tienen obligación frente a no vigilados**.
- Datos cubiertos: información de productos activos, de vinculación del cliente y características generales de productos.
- Consentimiento "previo, expreso e informado" del titular, autenticación fuerte y ciberseguridad. El receptor no puede condicionar su servicio a que el cliente consienta datos que no necesita.
- Los proveedores pueden recuperar costos directos de infraestructura según volumen de uso, con criterios objetivos. **No confirmado:** montos o tarifas.
- Calendario: 6 meses para que la SFC publique el cronograma de estándares (vence 7-oct-2026; **no confirmado** si ya se publicó); 12 meses para el directorio operativo (7-abr-2027); hasta 12 meses por categoría tras publicar estándares, prorrogables 6 meses una vez.
- Ajuste en curso: la URF publicó el 22-sep-2026 un borrador de decreto que cambia plazos de publicación de estándares y operación del directorio; comentarios hasta el 27-sep. **Contenido exacto no confirmado** (el PDF técnico no pudo leerse). El sector pide acelerar.

## 3. Proyecto de Circular Externa 10 de 2026 (SFC, julio de 2026)

Fuente: página de la SFC y análisis de Holland & Knight (30-jul-2026). Comentarios cerraron el 10-ago-2026. **No se leyó el texto íntegro** de la circular ni su anexo; lo siguiente viene del resumen.

- Estructura: disposiciones generales, tratamiento de datos y directorio de participantes. El detalle del tratamiento de datos personales se desarrollará en otra circular posterior.
- Participantes: proveedores de datos (vigilados); receptores **vigilados** (requieren autorización de la SFC y registro en el directorio); receptores **no vigilados** (operan por acuerdos bilaterales y solo con clientes que consienten).
- Lo que el proveedor debe verificar de un receptor no vigilado, periódicamente y de forma documentada: registro de bases de datos o política adecuada de gobierno de datos; procedimiento de atención de consultas de titulares; certificaciones (PCI-DSS si hay datos de tarjeta); gestión de riesgos de seguridad y reporte de incidentes; cifrado en tránsito y reposo con estándares reconocidos.
- Intercambio por APIs automáticas, con segmentación, monitoreo y disponibilidad. Los vigilados no pueden poner trabas que desalienten el intercambio.
- Plazos: quienes ya tienen esquemas de finanzas abiertas tienen hasta el 7-abr-2027 para cumplir; directorio operativo en abril de 2027.
- Falta saber si la versión final cambia estos puntos: **no confirmado** (hasta la fecha de consulta no encontré la circular definitiva).

Contexto previo: CE 004 de 2024 (estándares, ISO 27001 para agregadores según prensa) y CE 001 de 2026 (3-feb-2026: transición de 30 meses desde la CE 004 para entidades con estándares distintos).

## 4. Qué papel puede tener CuadraMe

- Hoy CuadraMe sería **receptor no vigilado**. No hay, por lo que encontré, una licencia ni registro obligatorio para serlo; **la barrera es contractual y de seguridad**: cada banco decide si firma y debe verificar los requisitos de la sección 3.
- Ser receptor vigilado exigiría ser entidad supervisada por la SFC (y su autorización): no es realista para CuadraMe.
- Certificaciones probables: política de datos y registro RNBD (Ley 1581), cifrado, gestión de incidentes. ISO 27001 se menciona para agregadores; para un tercero final **no confirmado**. PCI-DSS solo si maneja datos de tarjeta (no es el caso si solo lee movimientos).
- Camino práctico: **usar un agregador** que ya tenga los acuerdos y certificaciones, y CuadraMe queda como cliente del agregador.

## 5. Quiénes operan hoy (cobertura, precio, tiempo)

| Actor | Qué hace | Cobertura Colombia | Precio |
|---|---|---|---|
| Belvo | API de agregación y pagos | Más de 10 entidades, ~90 % de cuentas: Bancolombia, Davivienda, Banco de Bogotá, Occidente, Scotiabank, Falabella, AV Villas, Daviplata, Nequi (acuerdo bilateral regulado con Nequi) | Por ventas; la información pública habla de cuota fija con mínimo 12 meses más uso. **Valores no confirmados** |
| Finerio Connect | PFM y open banking; alianza con Bancolombia | Lista completa **no confirmada** | "Pay as you go" sin mínimos, o cuota fija más variable por usuario. **Valores no confirmados** |
| Prometeo | Información y pagos por API | Dice cubrir bancos con ~80 % de mercado en CO/PE/EC; bancos específicos **no confirmados** | Modelo por banco; valores **no confirmados** |
| Bancolombia / Davivienda (portales de APIs propios) | APIs directas | Solo su propio banco | No confirmado |

Cobertura por banco que pidió Daniel: Nequi, Bancolombia, Davivienda, Daviplata (Belvo, confirmado por prensa de Belvo); BBVA no apareció en la lista de Belvo (**no confirmado**); **Nu y Lulo: no encontré evidencia de cobertura** en ningún agregador. Son justo bancos digitales donde hoy CuadraMe ya depende del correo/atajo.

Tiempo de integración: no hay cifras publicadas. Estimación mía: 3 a 6 semanas para un piloto con sandbox de agregador, más el tiempo comercial de contrato (sin confirmar). Costos de ventas/contrato son el cuello de botella, no el código.

## 6. Consentimiento, seguridad, datos y diferencias con lo de hoy

| Tema | Hoy (gmail.readonly) | Con banco/agregador |
|---|---|---|
| Consentimiento | OAuth de Google sobre el buzón; el usuario ve que da acceso a correo | Autorización previa, expresa e informada **por finalidad y por datos** (Decreto 368); revocable; el banco confirma la autorización |
| Alcance | Se lee todo el correo accesible y se filtra por banco | Solo cuentas y datos autorizados; mucho más limpio |
| Verificación | Alcance restringido de Google: verificación anual con evaluación de seguridad (CASA); prensa especializada reporta de cientos de USD a cifras altas, **sin cifra oficial confirmada** | Verificación del banco o del agregador sobre CuadraMe (cifrado, incidentes, política) |
| Ley 1581 de 2012 | Aplica: política de tratamiento, autorización, derechos ARCO, registro RNBD según corresponda | Igual y más estricta: finalidad específica, no condicionar el servicio, atender consultas, reporte de incidentes |
| Credenciales | No toca claves bancarias | Con agregador por OAuth/API no se guardan claves; evitar flujos que pidan usuario y clave del banco (scraping) |
| Confiabilidad | Frágil ante cambios de formato de correo | Datos estructurados, pero dependes del uptime del agregador |

Impacto para CuadraMe si integra: política de tratamiento actualizada, pantalla de consentimiento propia, registro de autorizaciones, revocación, cifrado de tokens, plan de respuesta a incidentes y contrato de encargado de tratamiento con el agregador.

## 7. Alternativas y plan por fases

Alternativa A: agregador con licencia (Belvo/Finerio/Prometeo). Pros: ya existe, cobertura de Nequi/Bancolombia/Davivienda. Contras: costo mínimo probable alto para una app pequeña, dependencia, Nu/Lulo sin confirmar.
Alternativa B: esperar el estándar oficial. Pros: costo bajo de acceso, un solo estándar. Contras: beneficia primero a receptores vigilados, plazos inciertos y un no vigilado igual necesita acuerdo bilateral.
Alternativa C: seguir como hoy. Pros: sin costo ni riesgo regulatorio nuevo. Contras: fragilidad y fricción de usuario.

| Fase | Qué hacer | Costo estimado | Riesgo |
|---|---|---|---|
| Ahora (0-3 meses) | Mantener el canal actual. Pedir cotización y términos a Belvo y Finerio (cobertura Nu/Lulo/BBVA, mínimo mensual, precio por usuario/enlace, requisitos de certificación). Revisar política de datos y RNBD. | Casi cero (horas) | Pérdida de tiempo si no hay demanda |
| 6 meses | Piloto con un agregador solo con Nequi, Bancolombia y Davivienda y un grupo pequeño. Medir cuántos usuarios conectan y cuánto reduce errores. Seguir la circular definitiva y el decreto de plazos. | Estimado: del orden de cientos a pocos miles de USD si hay mínimo de cuota; **no confirmado** | Mínimo contractual de 12 meses sin usuarios |
| 12 meses | Con el directorio (abril 2027) y estándares, decidir si migrar a conexión directa o mantener agregador. Evaluar acuerdos con bancos ya publicados. | Depende de tarifas de los bancos (**no confirmado**) | Plazos que se corren (hay borrador de ajuste) |

Riesgos transversales: cambio de reglas, costo mínimo del agregador, responsabilidad legal por datos financieros (más grave que correo), y que Nu/Lulo queden fuera.

## 8. Decisiones para Daniel

1. ¿Autoriza pedir cotización a Belvo y Finerio (sin comprometerse) para tener precios reales?
2. ¿Hay suficiente demanda de usuarios para pagar un mínimo mensual de agregador en 6 meses, o se espera al estándar oficial?
3. ¿Qué bancos son imprescindibles (si Nu y Lulo lo son, el agregador hoy no los garantiza)?

## 9. Enlaces (consultados el 12-oct-2026)

- Decreto 368 de 2026, texto: https://normograma.com/keralty/compilacion/docs/decreto_0368_2026.htm
- Función Pública, Decreto 368: https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=275576
- CER, Decreto 368: https://www.cerlatam.com/normatividad/minhacienda-decreto-368-de-2026-07-abr-26/
- URF, finanzas abiertas obligatorias: https://www.urf.gov.co/w/colombia-avanza-hacia-las-finanzas-abiertas-obligatorias-un-paso-clave-para-la-inclusi%C3%B3n-financiera-y-la-transformaci%C3%B3n-digital-del-pa%C3%ADs
- URF, ajuste de plazos (PDF técnico, no legible en la consulta): https://www.urf.gov.co/documents/283253/3555757/003_Documento_Tecnico.pdf/de7566c4-26f4-9efe-d5b6-a410a8eaef8f?t=1790109497026
- SFC, Proyecto de Circular Externa 10 de 2026: https://www.superfinanciera.gov.co/publicaciones/10116197/proyecto-de-circular-externa-10-2026/
- Holland & Knight, análisis (30-jul-2026): https://www.hklaw.com/en/insights/publications/2026/07/sfc-propone-nuevas-reglas-para-implementar-el-sistema-de-finanzas
- CER, proyecto de circular 27-jul-2026: https://www.cerlatam.com/normatividad/sfc-proyecto-de-circular-externa27-julio-de-2026/
- Pérez-Llorca, CE 001 de 2026: https://www.perezllorca.com/es-co/actualidad/boletin/regimen-de-transicion-a-modelo-de-finanzas-abiertas-circular-externa-001-de-2026-de-la-superfinanciera-de-colombia/
- Forbes Colombia, ajuste de tiempos: https://forbes.co/economia-y-finanzas/colombia-ajusta-los-tiempos-del-open-finance-el-sector-pide-acelerar-su-implementacion
- AFIC, ampliación de plazos: https://afic.com.co/finanzas-abiertas-proyecto-propone-ampliar-los-plazos-de-implementacion/
- Belvo y Nequi: https://belvo.com/es/blog/belvo-nequi-lideran-camino-primer-acuerdo-open-finance/
- Belvo, Nequi (LatamFintech): https://www.latamfintech.co/articles/fintechs-belvo-y-nequi-realizan-el-primer-acuerdo-de-open-finance-en-colombia
- Belvo, precios (tercero): https://www.xpay.sh/saas-pricing/belvo/
- Finerio Connect y Bancolombia: https://www.semana.com/economia/capsulas/articulo/finerio-se-alia-con-bancolombia-para-hacer-open-banking-en-colombia/202248/
- Finerio, agregación bancaria: https://finerioconnect.com/products/bank-aggregation
- Prometeo, API: https://www.enter.co/startups/innovacion/prometeo-api-para-pagos-interbancarios/
- Agregadores en Colombia (Open Banking Tracker): https://openbankingtracker.com/country/co/aggregators
- Google, verificación de alcances restringidos: https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification
- GMass, costo de la evaluación de seguridad (tercero): https://www.gmass.co/blog/google-oauth-verification-security-assessment/

## 8. Actualización del 18-oct-2026: qué dice Nequi y qué cambió

Es investigación, no asesoría legal. Lo no verificado está marcado "no confirmado".

- **Portal de APIs de Nequi:** es para **comercios** (cobros por QR, notificaciones push, suscripciones, consulta de pagos). No ofrece el historial de movimientos de una persona a una app de finanzas. Para usarlo hay que registrarse como comercio o aliado. Fuente: nequi.com.co/negocios/apis.
- **Acuerdo Nequi–Belvo (Open Finance):** existió un anuncio de un acuerdo bilateral (≈2 años atrás, bajo la Circular 004 de 2024). Pero un agregador de terceros (Fintable) lista la conexión de Nequi en Belvo como **inactiva o sin soporte**. **No confirmado** que hoy funcione. Esto matiza la fila de Belvo de la sección 5: antes de contar con Nequi vía Belvo hay que pedir confirmación escrita.
- **Comunidad Nequi:** un usuario dice que Nequi no dará su API a terceros. Es anecdótico, pero coincide con que no hay acceso público.
- **Decreto 0368 de 2026 y cronograma:** sin cambios respecto a las secciones 2 y 3. La Circular 001 de 2026 amplía a 30 meses los plazos de los estándares (hasta ~ago-2028) y hay un proyecto de decreto que sumaría 6 meses; **no confirmado** si ya se expidió. Las guías privadas difieren en fechas: usar siempre la norma y las circulares oficiales.
- **Conclusión:** la recomendación de la sección 1 se mantiene. Seguir con correo y extractos (que ya funcionan y no tocan claves bancarias), y **preguntar por escrito** a Belvo, Finerio y Nequi Negocios antes de invertir. Dejar la app lista para sumar una fuente más: el origen de cada movimiento (correo, extracto, manual, y mañana API) ya es intercambiable y el anti-duplicados ya los empareja.

### Qué necesitamos tener listo para cualquier integración (checklist)
1. Política de tratamiento de datos actualizada y registro de bases de datos (Ley 1581) si corresponde.
2. Pantalla de consentimiento propia: previo, expreso e informado, **por entidad y por finalidad**, revocable, con registro de cada autorización.
3. Cifrado de tokens, plan de respuesta a incidentes y borrado de datos al revocar (ya existe `derechos_titular.py`).
4. No guardar nunca usuario y clave del banco (nada de scraping).
5. Revisión legal (ya pendiente en `docs/salida/CHECKLIST_LANZAMIENTO.md`).

## 9. Borradores de correo (para enviar Daniel; no se envió nada)

Antes de enviar: completar los datos entre corchetes. Pedir siempre respuesta por escrito.

### 9.1 A Belvo (ventas / partnerships)
**Asunto:** Consulta de cobertura y condiciones para app de finanzas personales en Colombia (CuadraMe)

Hola equipo de Belvo,

Soy [nombre], de [empresa/proyecto] (DAPX). Estamos construyendo CuadraMe, una app web de finanzas personales para Colombia (con planes de expandirnos a México, Chile y Perú). Hoy leemos movimientos desde correos y extractos que el cliente autoriza; queremos evaluar una conexión estructurada con sus bancos.

Nos ayudaría que nos confirmen por escrito:
1. ¿Siguen activas hoy las conexiones de **Nequi, Bancolombia, Davivienda y Daviplata**? ¿Y Nu, Lulo y BBVA Colombia?
2. Si hay sandbox y cuánto tarda un piloto con pocas personas.
3. Modelo de precios (mínimo mensual, costo por usuario o por enlace activo).
4. Requisitos para una app como la nuestra: ¿registro como receptor de datos no vigilado, certificaciones (ISO 27001 u otras), política de datos, auditorías?
5. Qué datos de cada cuenta entregan (saldos, movimientos, histórico máximo) y con qué frecuencia de actualización.
6. Condiciones de consentimiento y revocación que debemos implementar de nuestro lado.

Gracias de antemano. Quedo atento para una llamada corta.

[Nombre] · [teléfono] · [correo]

### 9.2 A Nequi Negocios / alianzas
**Asunto:** Consulta sobre acceso a datos del cliente (con su autorización) para app de finanzas personales

Hola,

Soy [nombre], de [empresa/proyecto]. Desarrollamos CuadraMe, una app de finanzas personales. Vimos que el portal de APIs de Nequi está orientado a comercios (cobros y suscripciones).

Quisiéramos saber, por escrito:
1. Si Nequi ofrece, o planea ofrecer, acceso a **movimientos y saldo de un cliente a terceros con su consentimiento** (Open Finance / Decreto 0368 de 2026), y por qué canal (directo, agregador o alianza).
2. Si el acuerdo con Belvo sigue vigente y qué otros agregadores están habilitados.
3. Requisitos que exigen a un tercero no vigilado (seguridad, política de datos, registro de bases de datos, pruebas).
4. A quién contactamos para iniciar el proceso.

Mientras tanto seguiremos leyendo los correos de movimientos y los extractos que el propio cliente autoriza.

[Nombre] · [teléfono] · [correo]

### 9.3 A Finerio Connect
Mismo texto que 9.1, cambiando el saludo, y preguntando además por su alianza con Bancolombia y la cobertura de Nequi.

## 10. Fuentes de esta actualización
- Nequi, APIs para negocios: https://www.nequi.com.co/negocios/apis
- Belvo y Nequi, primer acuerdo de Open Finance: https://belvo.com/es/blog/belvo-nequi-lideran-camino-primer-acuerdo-open-finance/
- Fintable, estado de la conexión Nequi/Belvo: https://fintable.io/coverage/banks/Colombia/1243227_nequi
- Comunidad Nequi (foro): https://comunidad.nequi.co/foros/discusion/verificacion-pagos-via-api/
- Holland & Knight, Decreto 0368: https://www.hklaw.com/en/insights/publications/2026/04/nuevo-decreto-incorpora-el-sistema-de-finanzas-abiertas-en-colombia
- URF: https://www.urf.gov.co/w/colombia-consolida-el-sistema-de-finanzas-abiertas-obligatorio
- AFIC, ajuste de plazos (Circular 001 de 2026): https://afic.com.co/sfc-ajusta-el-cronograma-de-finanzas-abiertas-en-colombia-conoce-las-nuevas-fechas-limite/
