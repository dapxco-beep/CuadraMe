# Formatos de extracto que la app lee

Los extractos PDF se leen en `backend/app/conciliacion.py` (`parse_texto_con_regex`). Desde noviembre de 2026 los bancos
colombianos tienen un lector **por formato** en `backend/app/extractos_co.py`; antes, todo lo que no era Nequi o Nu caía en
un lector genérico que casi nunca funcionaba con extractos reales.

## Qué se reconoce hoy

| Formato | Cómo se reconoce (encabezado, no el nombre de un banco suelto) | Cómo se verifica |
|---|---|---|
| Davivienda «Informe del mes» | `INFORME DEL MES: MARZO/2026` + `Clase de Movimiento` | Más créditos / Menos débitos / Nuevo saldo |
| Bancolombia «Estado de cuenta» | `ESTADO DE CUENTA DESDE: aaaa/mm/dd HASTA: …` + `VALOR SALDO` | Total abonos / Total cargos (suma todos los periodos del PDF) |
| Bancolombia «Sucursal Virtual» | `Sucursal Virtual Personas` + `Movimientos:` | No trae totales: no se puede verificar (se dice) |
| Banco Caja Social «Extracto individual» | `Periodo del Informe` + `Banco Caja Social` | Resumen de cada mes; el signo sale de los saldos |
| BBVA cuenta corriente | `SALDO CIERRE MES ANTERIOR` + `PERÍODO DESDE` | Cada mes debe terminar en su `SALDO FINAL` |
| Davibank (Davivienda) | `SALDO ANTERIOR … DEPÓSITOS Y OTROS CRÉDITOS … NUEVO SALDO` | Resumen de cada mes |
| Nequi, Nu (cuenta y tarjeta) | lectores propios en `conciliacion.py` / `extractos_tarjeta_nu.py` | Su resumen |

Cada lector devuelve `lectura_completa`: `True` (lo leído suma lo que dice el extracto), `False` (falta o sobra algo: la app
avisa «puede faltar algo» en vez de importar a ciegas) o `None` (el extracto no trae totales). `huecos` cuenta los meses que
faltan dentro de un PDF con varios extractos (el saldo inicial de un mes no es el final del anterior).

## Por qué por formato y no por banco
Un mismo banco imprime formatos distintos, y el nombre de otro banco aparece suelto en los movimientos («TRANSFERENCIAS A
NEQUI», «enviada a Daviplata»). Detectar por esas menciones hacía leer extractos de Bancolombia y Davivienda como si fueran de
Nequi. La firma de cada formato es de su encabezado.

## Cómo sumar un formato nuevo
1. Pasa los PDFs por la herramienta (no imprime datos personales):
   `cd backend && venv/Scripts/python.exe tools/probar_extractos.py "<carpeta>" --desde-hoy --texto textos_locales`
   Dice qué banco detecta, si hay lector, cuántos movimientos lee y si cuadra.
2. Mira el texto extraído (`textos_locales/`, **no se sube al repositorio**: trae nombres y cuentas) para ver cómo viene cada fila.
3. En `extractos_co.py` agrega `_firma_*` (qué lo identifica) y `_leer_*` (fila → movimiento, y qué total se compara) y regístralo en
   `_FORMATOS` y `_BANCO_DE_FORMATO`.
4. Escribe la prueba en `tests/test_extractos_co.py` con un texto **sintético**: la misma estructura con nombres, cuentas y
   cifras inventadas que cuadren entre sí. Nunca pegues un extracto real.
5. Pruébalo con los PDFs reales hasta que `cuadra` diga `sí` (o `-` si el formato no trae totales).

## Reglas que ya costaron un error
- El signo: Davivienda lo pone al final del valor (`$18,200.00-`); Bancolombia lo trae delante; Caja Social y BBVA no lo traen y se
  decide con los saldos del banco (`saldo anterior ± monto = saldo`). Nunca por el orden de las columnas.
- Un PDF puede traer varios extractos: el año de cada fila sale del periodo que tiene encima, y los totales se suman todos.
- Hay filas sin fecha propia (impuesto acumulado de fin de mes en Davibank): se aceptan solo si la cadena de saldos las confirma.
- El banco puede restar devoluciones de «cargos» en vez de listarlas como abono (BBVA): por eso BBVA se verifica con el saldo final
  de cada mes, no con los totales por categoría.

## Pendiente (formatos vistos y NO soportados)
- Extractos de bancos de EE. UU. en inglés (TD Bank, Bank of America): fuera del alcance de la app hoy. El de Bank of America
  trae el texto del PDF dañado (la fuente cambia letras y cifras por signos), así que ni siquiera se puede leer sin OCR.
