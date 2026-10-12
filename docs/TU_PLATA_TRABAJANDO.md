# Tu plata trabajando (cajitas, bolsillos y rendimientos)

Orientación educativa, no es asesoría financiera. Todo rendimiento es una ESTIMACIÓN.

## Decisión de modelo: la cajita es una PARTE del saldo, no una cuenta aparte

Opciones evaluadas:

1. **Cuenta de tipo ahorro con `parent`**: obliga a sumar/restar en Patrimonio, "dinero disponible", resumen de cuentas,
   cierres y reportes, y mover plata exigiría dos movimientos de traslado (con sus reglas de emparejamiento). Muy invasivo
   y con riesgo de contar el saldo dos veces.
2. **Subcuenta como parte del saldo (elegida)**: tabla `cajitas` (cuenta, nombre, saldo, tasa E.A. propia, fecha de la tasa).
   `Cuenta.saldo` sigue siendo el total que el banco muestra (= saldo principal + cajitas).
   El saldo principal es `Cuenta.saldo - suma(cajitas)`.

Consecuencias de la opción 2:

- Mover plata entre el saldo principal y una cajita **no crea movimientos** ni toca `Cuenta.saldo`: es neutral por
  construcción (ni gasto ni ingreso), sin depender de `contabilidad.py`.
- Patrimonio, "dinero disponible", resumen de cuentas, informes y consejos siguen leyendo `Cuenta.saldo`: no hay doble conteo.
  Una prueba (`test_cajita_no_cambia_saldo_ni_patrimonio_ni_disponible`) lo verifica.
- Si luego el saldo de la cuenta baja por debajo de la suma de cajitas (gastos reales), el saldo principal se muestra en 0
  y se avisa «tus cajitas suman más que el saldo de la cuenta» (`descuadre`).
- Borrar una cajita devuelve su plata al saldo principal (se marca `activa = false`).

## Cálculo

`app/rendimientos.py`: interés compuesto E.A., `saldo * ((1 + EA)^(días/365) - 1)`. Se muestra por día, lo corrido del mes,
un mes tipo (365/12 días) y 12 meses, manteniendo el saldo de hoy. Se usa siempre la tasa y la fecha anotadas por la persona;
sin tasa no se inventa nada. Solo cuentas de tipo `ahorro` (la `tasa_ea` de una tarjeta es de interés a pagar, no rendimiento).

«Rendimientos reales recibidos»: suma de ingresos del mes cuya categoría empieza por «Rendimiento» (la clasifican los lectores
de extractos); se lee por nombre, no se crea la categoría.

## Tasas de referencia

Tabla `tasas_referencia` (entidad, producto, tipo, tasa_ea, vigente_desde, fuente_url, nota, activa). Nada de tasas en el
código: `SEMILLA` solo se carga si la tabla está vacía y queda marcada «referencia, verifica en la app de tu banco».
Lectura para todos (`GET /rendimientos/tasas`); edición solo ADMIN_EMAIL (`/rendimientos/tasas/admin`, `POST`, `PUT`; 404 al resto).
El panel «Salud del negocio» lista las tasas con más de 45 días sin actualizar (`tasas_referencia.desactualizadas`).

## Comparación y consejo «plata ociosa»

Si el saldo principal (≥ $200.000) rinde al menos 3 puntos E.A. menos que la **mediana** de las tasas de referencia de
ahorro a la vista, se muestra «en una cajita al ~X % serían ~$Z más al año». Se usa la mediana y la lista va en orden
alfabético para no favorecer a ningún banco. Consejo con id estable `plata-ociosa:<cuenta>:<AAAA-MM>`, descartable y
silenciable (la PWA guarda el prefijo `plata-ociosa` en el dispositivo).

## Tablas nuevas

`cajitas`, `tasas_referencia` (script idempotente sin ejecutar: `backend/supabase/migraciones/tu_plata_trabajando.sql`;
el backend las crea con `create_all`). No hay columnas nuevas en tablas existentes.
