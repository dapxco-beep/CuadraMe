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
