# Informes — validación previa al despliegue (2026-11-26)

Rama de trabajo: worktree `wt-informes-integracion` (código de `origin/infra/render` en 599bb33 + el rediseño de Informes).
Nada de esto está en producción ni en `main`. Los cambios están sin commit.

## Resultado por validación

| # | Validación | Resultado |
|---|---|---|
| 1 | Tasa de ahorro (ingresos cero, flujo negativo, devoluciones, ajustes, periodos parciales) | OK: 7 casos por API con cifras calculadas a mano, más las pruebas puras del cálculo |
| 2 | Presupuesto vs. gasto real (mitad de mes, límites cambiados, sin presupuesto, varios meses, sobres) | OK. **Un error real corregido** (presupuestos duplicados contaban el gasto dos veces). Una limitación documentada |
| 3 | Selector global: pestañas, recarga, enlaces compartidos, `?mes=` antiguo | OK, 30 verificaciones en navegador real |
| 4 | Gráficos y hallazgos sin datos | OK: 3 casos por API y 15 de interfaz. **Un defecto corregido**: sin ingresos decía «flujo negativo» a secas; ahora dice «no registraste ingresos» |
| 5 | Enlaces a Movimientos conservan contexto | OK: periodo, categoría y tipo; «Atrás» vuelve al mismo periodo y pestaña |
| 6 | Revisión visual en 360, 390, 768 y 1280 px | OK tras 6 ajustes de jerarquía (ver abajo) |
| 7 | Pruebas sobre la base correcta, sin datos demo | OK. SQLite temporal por prueba; se añadió un guardia que **aborta** si `DATABASE_URL` no es SQLite |

## Casos de prueba (resumen)
- **Backend**
  - `test_informe_resumen.py`: 22 pruebas puras con cifras a mano.
  - `test_informe_resumen_validacion.py`: 37 pruebas por API con un usuario nuevo por caso.
  - Mutación: se rompió el código a propósito de 8 maneras; 7 las atrapó la suite y la octava es una mutación equivalente (sumar cero).
- **Frontend**: `periodo_informes` (22), `informes_resumen` (20), `informes_resumen_vacios` (15), más las pruebas existentes actualizadas.
- **Navegador real** (`e2e`, Chrome): 30 verificaciones, entre ellas:
  - Elegir periodo → cambiar de pestaña → recargar → conserva.
  - Enlace compartido (válido, inventado, rango al revés).
  - `/informe?mes=2026-09` y `/resumen?mes=2026-08`.
  - «Mi mes», «Cierre» e «Impuestos» toman el mes/año correcto del periodo.
  - Mover el mes en «Mi mes» cambia todo el informe.
  - Enlaces a `/movimientos` y botón «Atrás».
- **Totales**:
  - Frontend (árbol integrado): 182 archivos, 1.594 pruebas, todo verde.
  - Backend (suite completa en árbol integrado): 3.391 pasan, 1 falla.

### El único fallo de la suite
`test_aislamiento_usuarios.py::test_todo_endpoint_esta_clasificado` falla por `POST /formas-asunto/pantalla` y `GET /formas-asunto/cron/pantallas` (medición de uso de la otra sesión). **Falla igual en `origin/infra/render` limpio, sin mis cambios**. Mis endpoints sí están clasificados (la prueba de aislamiento los cubre automáticamente y pasa). Hay que clasificar esos dos endpoints antes de cualquier despliegue que exija la suite verde.

## Revisión de seguridad y compatibilidad

**Endpoint nuevo `GET /informes/resumen`** y parámetros nuevos `tipo`, `fuente` en `GET /informes/gasto/movimientos`.
- Autenticación: `get_current_user` obligatorio; sin sesión → 401 (probado en ambos).
- Aislamiento: todo sale de `cargar_movs_efectivos` (cuentas accesibles de la persona) y `Presupuesto.usuario_id`. Probado con dos usuarios: B no ve nada de A, tampoco por `fuente`.
- Inyección: ningún parámetro llega a SQL (se compara en Python). `periodo`/`mes`/`desde`/`hasta` se validan en `rango_periodo` (422); `agrupar` y `tipo` con patrón. Probados: SQL, `../`, `<script>`, 5.000 caracteres, unicode, `%00` → 422 o respuesta vacía, nunca 500 ni rastro de error.
- Abuso: límite **90 consultas/minuto por persona** (429 con `Retry-After`) y tope de rango de 5 años.
- Datos: la respuesta solo contiene datos de la propia persona; sin identificadores internos nuevos.
- Compatibilidad: el cambio es **aditivo**.
  - `/reportes/ingresos-gastos` y `/informes/gasto` no cambian (se compara campo por campo con el resumen).
  - `/informes/gasto/movimientos` sin `tipo` ni `fuente` se comporta igual.
  - No hay migraciones ni cambios en `models.py`.
- **Orden obligatorio**: web nueva + API vieja → la pestaña de entrada («Resumen») muestra error. Desplegar API primero.
- Contenido ya cargado en navegadores: la web vieja contra la API nueva funciona (no usa nada nuevo).

## Riesgos pendientes
1. **Colisión con la otra sesión (alto).** `infra/render` ya avanzó 3 commits que también rediseñan Informes (Días unido a Gastos, paneles fusionados, perfil Esencial). Mi rediseño chocaba en 5 archivos; ya está integrado y probado sobre 599bb33, pero la otra sesión puede seguir empujando. Antes de desplegar: `git fetch` y volver a integrar si hay commits nuevos. Conviene pausar esa sesión en Informes hasta desplegar.
2. **Presupuesto sin historial.** No se guarda fecha de creación ni cambios de límite: un mes pasado se mide con el límite de hoy. Los periodos son meses de calendario, no el periodo de pago (`dia_pago`) de la pantalla Presupuesto. Está dicho en pantalla y fijado con pruebas.
3. **Devoluciones.** Una devolución que entra a ahorros cuenta como ingreso (regla vigente en toda la app); la que entra a la tarjeta es abono y no cuenta. No cambié la regla.
4. **Rendimiento no medido a escala.** El resumen lee hasta 5 años de movimientos por consulta; con miles de movimientos y el plan gratis de Render no tengo medición. Mitigación: límite por persona y una sola lectura.
5. **Zoom.** Quitado el bloqueo (WCAG 1.4.4). Los 4 anchos se verificaron sin ampliar; no se probó el comportamiento ampliado en un iPhone/Android real.
6. **Pruebas visuales con sesión simulada** y datos de demostración; no con una cuenta real.
7. **Menores:** el chip activo del selector queda recortado a la izquierda en 768 px; el recuadro «Salud» del mapa de categorías (de la otra sesión) parte la palabra en 390 px.

## Procedimiento de despliegue (con tu autorización explícita; no se ha ejecutado nada)
0. `git fetch`; comprobar que `origin/infra/render` sea ancestro del commit a desplegar. Si hay commits nuevos de la otra sesión, integrarlos y repetir las pruebas.
1. Clasificar los 2 endpoints de `/formas-asunto` o decidir con la otra sesión quién lo hace; suite backend verde.
2. Commit en rama propia; `git push origin HEAD:infra/render` (tu «sí» explícito).
3. **API primero** (Render, servicio `cuadrame-api-oregon`). No hay migración, así que `git diff <desplegado> HEAD -- backend/app/migraciones.py backend/app/models.py` debe salir vacío.
4. Verificar la API: `/health` → `{"ok": true}`; `/version` con el commit nuevo; `GET /informes/resumen?periodo=mes&mes=<mes con datos>` con una cuenta de prueba → 200 con `flujo`, `fuentes`, `presupuesto`, `hallazgos`.
5. **Web después** (Vercel, desde `pwa/`): `npx vercel deploy --prod --yes --build-env COMMIT_SHA=<sha>`.
6. `scripts/verificar_produccion.sh <sha>`; abrir Informes con una cuenta de prueba: Resumen, cambiar periodo, recargar, enlace compartido.
7. Vigilar 30 minutos los registros de Render por 5xx y 429 en `/informes/resumen`.

## Procedimiento de reversión
- **Web primero** (si algo falla en pantalla): en Vercel, promover el despliegue anterior (o `vercel rollback`). No hay datos que restaurar: las preferencias de paneles viven en el navegador y la clave nueva (`informe-paneles-resumen`) es inofensiva.
- **API después** (si el fallo es del servidor): en Render, redesplegar el commit anterior (hoy `bd28ffd`). El endpoint nuevo desaparece y la web anterior no lo usa.
- Nunca revertir la API con la web nueva activa: «Resumen» (entrada por defecto) mostraría error.
- No hay migraciones ni escrituras nuevas: la reversión no toca la base de datos.
- Después: `scripts/verificar_produccion.sh <commit anterior>`.

## Cambios visuales de esta fase (por la revisión en 4 resoluciones)
Barra de periodo como tarjeta propia (distinta de las pestañas) con el rango siempre completo; chip activo centrado; sin «sin base para comparar» repetido tres veces (una sola explicación); flujo neto en escritorio con la gráfica a la izquierda y la lectura a la derecha; «Presupuesto» a ancho completo y «Lo que dicen tus números» en dos columnas en escritorio; resumen de Gastos sin barra «Antes» vacía, con la frase «en del 1 de junio…» corregida y cifras que ya no se cortan en móvil.
