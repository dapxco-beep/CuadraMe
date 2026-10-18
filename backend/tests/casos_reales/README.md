# Corpus de regresión: casos reales

Cada falla que ya le pasó a alguien está aquí como prueba, con **datos 100 % inventados**. Si un cambio
futuro la reintroduce, estas pruebas fallan antes de desplegar. Corren en menos de 10 s:

```
cd backend
venv/Scripts/python.exe -m pytest tests/casos_reales -q
```

(o `scripts/verificar_todo.ps1 -Rapido` desde la raíz del repositorio).

| # | Caso | Archivo | Fecha aprox. | Qué rompería si vuelve |
|---|------|---------|--------------|------------------------|
| 1 | NIT / cuenta / teléfono / cédula leídos como monto (NIT con dígito `901.658.107-2` en asunto, fragmento y cuerpo) | `test_caso_01_03_montos_mal_leidos.py` | oct-2026 | «Por revisar» con un gasto de $901.658.107 |
| 2 | Monto ×100 por el punto final (`La cantidad de: $1.000.000,00.`) | `test_caso_01_03_montos_mal_leidos.py` | oct-2026 | Gastos 100 veces más grandes |
| 3 | Montos sin «$» (Nequi/Bre-B), años y horas como monto | `test_caso_01_03_montos_mal_leidos.py` | oct-2026 | Correos perdidos (monto 0) o montos falsos |
| 4 | Avisos que no son transacciones (extracto listo, tarjeta agregada, pago fallido, publicidad) | `test_caso_04_05_avisos_y_comercio.py` | oct-2026 | Basura en «Por revisar» |
| 5 | Comercio vacío (`Pagaste en:\nICETEX`, `Compraste en:`) | `test_caso_04_05_avisos_y_comercio.py` | oct-2026 | Movimientos sin descripción o con «La cantidad de» como comercio |
| 6 | Extracto Nu: saldos de cuenta, `Pago $A -$B -$C`, `Cobro por cuota $X - $X -`, líneas ambiguas | `test_caso_06_extracto_nu.py` | oct-2026 | Gastos fantasma, saldos que no cuadran |
| 7 | Extracto de tarjeta asignado a cuenta de ahorros; creación de la cuenta de tarjeta | `test_caso_07_14_extracto_en_cuenta_equivocada.py` | oct-2026 | Compras de la tarjeta restando ahorros |
| 8 | Correo descartado por movimiento borrado + recuperar | `test_caso_08_09_correos_descartados_y_huecos.py` | oct-2026 | Gasto borrado que resucita, o correo imposible de recuperar |
| 9 | Ventana de correos con huecos (correo de hace 2 días que no entró) | `test_caso_08_09_correos_descartados_y_huecos.py` | oct-2026 | Movimientos que nunca llegan |
| 10 | Migración desplegada editada (0001-0006 congeladas, lo nuevo al final) | `test_caso_10_11_12_operacion.py` | oct-2026 | 500 `UndefinedColumn` en producción |
| 11 | Error 500 sin CORS | `test_caso_10_11_12_operacion.py` | oct-2026 | La app dice «sin conexión» cuando es un error del servidor |
| 12 | Importar dos veces / en paralelo | `test_caso_10_11_12_operacion.py` | oct-2026 | Movimientos y saldo duplicados |
| 13 | Traslados propios (nombre truncado, «Envío a mi Nequi») | `test_caso_13_traslados_propios.py` | oct-2026 | Ingresos/gastos inflados por mover plata entre cuentas propias |
| 14 | Cambiar la cuenta de un extracto: mueve saldos sin cambiar el patrimonio | `test_caso_07_14_extracto_en_cuenta_equivocada.py` | oct-2026 | Patrimonio que sube o baja al reasignar |

## Cómo agregar un caso nuevo (estándar)

1. Cuando algo falle en producción, **primero** escribe aquí la prueba que lo reproduce (falla), luego lo arreglas.
2. Datos inventados siempre (nombres, NIT, cifras). Nada del dueño ni de clientes.
3. Docstring: qué pasó, por qué, y qué regla lo evita. Un archivo `test_caso_NN_<tema>.py` (o amplía uno).
4. Reutiliza helpers de `tests/` (`GmailFalso`, `Escena`, `mundo`...) en vez de copiar lógica.
5. Agrega la fila a la tabla de arriba.
6. Si es una migración desplegada, súmala a `DESPLEGADAS` en `test_caso_10_11_12_operacion.py`.
