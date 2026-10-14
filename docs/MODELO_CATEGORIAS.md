# Modelo de categorías de CuadraMe

Sin datos reales: solo agregados. Medido con el historial confirmado de la persona dueña del proyecto
(307 movimientos confirmados, 94 de comercios y 213 transferencias entre personas).

## Cómo se decide la categoría hoy

Una sola función pura, `autocat.decidir_categoria` (la usa `ClasificadorUsuario` y el script de evaluación).
Orden:

1. Pago de tarjeta (no es gasto).
2. Reglas del usuario (huella exacta de comercio, luego «contiene»). Confianza 1.0, origen `regla`.
3. Cobros y rendimientos del banco (4x1000, cuota de manejo, intereses, comisiones, rendimientos):
   categorías de sistema, el historial no las pisa. Tampoco se aprenden (`build_model` las ignora).
4. Aprendido de movimientos confirmados (Naive Bayes por palabras del comercio). Origen `similar`.
   La confianza sube con la evidencia (veces vista la palabra). Si es débil (< 0.8) y el diccionario
   reconoce una marca distinta, gana la marca.
5. Diccionario de palabras clave (pasarelas, QR Bre-B con negocio reconocido, marcas). Origen `comercio`.
6. Nada: «Otros» y se pregunta.

Normalización: `clave_comercio` quita prefijos de pasarela («PAGO PSE», «BOLD*», «DLO*», «Pagaste en»),
ciudades, NIT y códigos. El modelo usa todas las palabras del comercio (`palabras_comercio`).

Personas y Bre-B: «Para X», «Enviaste a X», «ENVIO CON BRE-B A:» son transferencias entre personas.
Se proponen como «Transferencias» con confianza baja (0.5, nunca se confirma sola) y NO se aprende del
nombre propio. «PAGO EN QR BRE-B: <negocio>» usa la categoría del negocio si el diccionario lo conoce.

## ¿Se guarda el aprendido? ¿Qué es «reentrenar»?

No hay artefacto guardado: `ClasificadorUsuario` reconstruye el modelo al vuelo desde los movimientos
confirmados de ESE usuario (`cat_confirmada` distinto de False y categoría distinta de «Otros»). Por eso
«reentrenar» es automático y por usuario: al confirmar o corregir un movimiento, la siguiente
clasificación ya lo usa. Lo que la app puso sola sin confirmar no entrena. Nunca se mezclan usuarios.
No hay cron de recálculo porque no hay nada que recalcular.

## Calidad en el tiempo

Al corregir una sugerencia queda `cat_origen = "corregida:<categoría sugerida>"`; al aceptarla se conserva
el origen y `cat_confirmada = True`. «Salud del negocio» (`/metricas/panel`, solo admin, 404 al resto)
muestra conteos acertadas / corregidas / sin revisar y exactitud por categoría. Las categorías inventadas
por cada persona se agrupan como «Personalizadas». Sin descripciones, montos ni ids.

## Evaluación offline

`python backend/tools/evaluar_clasificador.py export.json [--modo comercio|movimiento] [--mostrar-errores]`.
`comercio` deja fuera todo el comercio (comercios nuevos); `movimiento` solo el evaluado (comercios que se
repiten). Imprime solo agregados; los comercios que más fallan salen enmascarados salvo marcas públicas.

## Métricas (antes -> después, agregadas)

| Medida | Antes | Después |
|---|---|---|
| Exactitud global, comercios nuevos | 54.4 % | 49.2 % |
| Exactitud global, comercios repetidos | 67.8 % | 51.8 % |
| Exactitud en comercios cuando propone (nuevos / repetidos) | 71.4 % / 72.7 % | 75.0 % / 79.1 % |
| Exactitud en comercios, total (nuevos / repetidos) | 63.8 % / 70.2 % | 63.8 % / 72.3 % |
| Quedan en «Otros» | 7.8 % | 11.1 % |
| Transferencias entre personas propuestas como «Transferencias» | 75 % | 100 % |
| Reglas sugeribles (huella en ≥3 meses) | n/d | 12, cubren 33 % del historial |

Lectura honesta: la exactitud global baja porque antes el modelo «acertaba» copiando la categoría de un
nombre propio (p. ej. a quién se le paga siempre lo mismo). Eso es sobreajuste y falla con otra persona.
Ahora todas las transferencias entre personas se proponen como «Transferencias» y se pregunta: el 57 % de
esas la persona las dejó con otra categoría porque el nombre no revela el gasto. En comercios, que es donde
el modelo puede saber, la exactitud sube. Lo que no mejora: ese 57 % solo lo resuelve una regla del usuario.

## Ideas que requieren consentimiento

Un diccionario compartido derivado de correcciones de varios usuarios no se hizo: exige consentimiento
explícito (Ley 1581) y agregación sin contenido.
