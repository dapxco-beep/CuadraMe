# Moneda base (fases 1 y 2)

**Regla única:** todo total que ve la persona está en la moneda base de su perfil (`Perfil.moneda_base`; sin ella, la de su país; perfiles viejos = COP).
Código: `a_base`, `ConvertidorBase` y `moneda_base_de` en `backend/app/contabilidad.py`; espejo `aBase` en `pwa/src/lib/contabilidad.js` (fixture compartido `backend/tests/fixtures/moneda_base_casos.json`).

## Sin tasa no se suma
`ConvertidorBase.contar()` devuelve 0 para una moneda sin tasa y la anota en `sin_tasa`; la respuesta trae `moneda_base` y `monedas_sin_tasa`.
La PWA muestra `AvisoSinTasa` («No tenemos la tasa de MXN: esas cuentas no están sumadas en el total. Poner tasa»).

## Tasa manual por usuario (fase 2)
Tabla `tasas_manuales` (migración `0005`), privada por usuario: `GET /perfil/tasas`, `PUT /perfil/tasas/{moneda}` (`{tasa}`: 1 moneda = tasa de la base), `DELETE /perfil/tasas/{moneda}`.
Orden de tasas: manual del usuario > proveedor (`app/fx.py`) > aproximada. `ConvertidorBase.de_usuario(db, uid)` ya las incluye (se leen solo si aparece otra moneda).

## Pantallas en moneda base (fase 2)
Cuentas/resumen, presupuestos (disponible hoy, en mi bolsillo), cuotas, reportes (mensual, tendencias, flujo futuro, wrapped), informes (gasto, diario, evolución), insights, cierre de mes, traslados, planificación, inversiones, rendimientos, patrimonio, asistente.
Los nombres `*_cop`, `valor_cop`, `total_cop` son históricos: **llevan la moneda base**.
En la PWA, `formatCOP` formatea en la base; `formatCOPFijo` siempre en COP.

## Se queda en COP a propósito
- **Impuestos (DIAN/renta/GMF):** `routers/impuestos.py`, `renta_alerta.py` y las tarjetas de renta/GMF: la declaración colombiana es en pesos sin importar la base (`calcular_resumen(..., base="COP")`).
- `movimientos.py` (atajo de pago): convierte a la moneda **de la cuenta** (solo cuentas COP), no es un total del perfil.
- Valores por defecto de formularios (`moneda='COP'` en altas) y el catálogo de tickers de la BVC.
