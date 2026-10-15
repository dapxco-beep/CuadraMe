# Regla única de ingresos y gastos

Fuente: `backend/app/contabilidad.py` (`clasificar` / `tipos_efectivos`, `delta_saldo` para saldos). Espejo: `pwa/src/lib/contabilidad.js`.
Casos compartidos Python↔JS: `backend/tests/fixtures/contabilidad_casos.json` (`test_traslados_robustos.py`, `contabilidad_paridad.test.js`).
Guardián: `backend/tests/test_guardian_contabilidad.py` (lista blanca por archivo, con razón).

Neutral = ni ingreso ni gasto: traslados (par detectado, decisión, regla, creado en la app), pagos de tarjeta y su abono, ajustes de saldo, aportes a meta y «posibles traslados» (pista fuerte sin la otra pata). La neutralidad NO depende de la categoría «Transferencias» ni del tipo guardado.

## Inventario (quién suma ingresos/gastos)
| Lugar | Cómo cuenta |
|---|---|
| Informes, «En qué gasto mi plata», ingresos vs gastos, diario, meses | `informe_datos.cargar_movs_efectivos` → `clasificar` |
| Presupuestos, alertas de presupuesto, resumen semanal (correo/push) | `gastos_por_categoria` / `presupuesto_servicio` → `tipos_efectivos` (con reglas y nombre) |
| Cierre de mes, impuestos (GMF), costos bancarios, metas (aportes), cuotas | `tipos_de_cuentas(cuentas, db)` + `tipos_efectivos` o `cargar_movs_efectivos` |
| Consejos, insights, wrapped, edad del dinero, salud financiera, asistente (herramientas) | `tipos_efectivos` / `cargar_movs_efectivos` |
| Exportes CSV/Excel, reportes mensual/tendencias/flujo | `tipos_efectivos` |
| Recurrentes | `tipo_efectivo_receta` (pagos fijos, no movimientos) |
| Rendimientos | por categoría de sistema «Rendimientos» (no depende de traslados) |
| PWA: Movimientos (totales), Inicio (gastos de la semana) | `lib/contabilidad.js` (`totalesIngresosGastos`, `tiposEfectivos`) |
| **Excepción documentada**: «consignaciones» de renta (impuestos) | cuentan traslados entre cuentas propias A PROPÓSITO (la DIAN mira consignaciones brutas). No cambiar. |

## Decisiones de la persona
`POST /traslados/decidir {ids, decision: traslado|real, recordar}` guarda la marca en `movimientos.notas` (`es_traslado_propio` / `no_es_traslado`) y, con `recordar`, una regla por huella en `reglas_traslado`. `GET /traslados/sugerencias` alimenta «Revisar posibles traslados» (`/traslados`).

## SQL opcional (idempotente, NO ejecutado)
`backend/supabase/migraciones/reglas_traslado.sql`: tabla `reglas_traslado`. Sin ella todo funciona; solo no se recuerdan decisiones por regla.

## Traslados propios: endurecimiento (una sola punta, nombres, homónimos)
**Qué reconoce sin la otra punta** («pista fuerte», neutral): tu nombre con >= 2 palabras (sin tildes/mayúsculas, cualquier orden, con la última palabra truncada por el banco: `DANIEL ALFONSO PARR`), «a/de/desde mi|tu cuenta|Nequi|Nu|llave|ahorro|cajita|bolsillo|meta», «cuenta propia», «movimiento/traslado entre cuentas», «traslado a ahorro/cajita», «avance en efectivo», «entre tus cuentas», recarga entre bancos propios, la marca del lector y lo que la persona decidió o recordó por regla.
**Nombre del titular**: `perfiles.nombre_preferido` + `perfiles.nombre_titular` (nombre completo de Google, guardado por `GET /perfil/nombre` solo para esto; no se muestra ni sale del servidor). SQL opcional `supabase/migraciones/perfil_nombre_titular.sql` (también en `migraciones.py`, idempotente). Sin la columna todo funciona con el nombre preferido.
**Homónimos**: una sola palabra («Daniel») nunca basta; un homónimo que coincide en >= 2 palabras con el titular queda como **posible traslado** (ni gasto ni traslado confirmado) hasta que la persona responda en «Revisar posibles traslados».
**Parejas**: mismo monto, cuentas y moneda distintas, <= 2 días con cualquier pista; hasta 4 días (puente festivo) solo con pistas fuertes (suma >= 3). «Envío», «Recibido» y «Avance» cuentan sin importar tildes.
**Pendiente de confirmar**: un «posible traslado» es neutral PROVISIONAL (no infla ingresos ni gastos del mes) y aparece en `/traslados/sugerencias` y «No se cuenta». «No es un traslado» lo vuelve ingreso/gasto real y no se sugiere de nuevo.
**Superficies corregidas**: `/cuentas/{id}/detalle` (clasificaba solo con esa cuenta y sin nombre/reglas), `/insights/preguntar` (mandaba a la IA el tipo guardado), alerta de renta (ahora usa el mismo contexto de nombres/reglas).
Casos sintéticos: `backend/tests/fixtures/contabilidad_casos.json` (compartidos con la PWA) y `backend/tests/test_traslados_propios_endurecidos.py`.
