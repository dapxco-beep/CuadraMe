# Inversiones: diseño e investigación (14-oct-2026)

Información educativa, no es asesoría de inversión. **Alcance:** todo es opcional; sin posiciones o activos no aparece nada en Inicio ni cambia el menú (entra por «Más funciones»/Patrimonio con la pregunta «¿Tienes inversiones o bienes que quieras seguir?» y «Ahora no»).

## 1. Proveedores de precios por ticker
Fuente: conocimiento de cada proveedor a la fecha, **sin verificación en vivo en esta sesión**; confirmar cada límite en la página del plan antes de producción.

| Proveedor | Plan gratuito (según lo conocido) | Cobertura | Observaciones |
|---|---|---|---|
| Twelve Data | ~800 créditos/día, ~8/min | EE. UU. y muchas bolsas; BVC, BMV, B3, BCS, BYMA: **no confirmado** en plan gratis | API oficial; revisar ToS. **Elegido como principal** |
| Alpha Vantage | ~25 peticiones/día | EE. UU. y sufijos internacionales (p. ej. .SAO); Colombia: no confirmado | Muy bajo para muchos tickers; **respaldo** |
| Finnhub | ~60/min | Acciones EE. UU. en gratis; internacionales de pago | No implementado |
| Financial Modeling Prep | ~250/día | EE. UU.; internacional de pago | No implementado |
| Yahoo Finance (no oficial) | Sin plan; endpoint no documentado | Cubre ECOPETROL.CL, PFBCOLOM.CL, ISA.CL, .MX, .SA, .SN, .BA | Sus términos no autorizan este uso y puede bloquear: **apagado por defecto** (`INVERSIONES_YAHOO_ACTIVO=1`), detrás de la abstracción |
| CoinGecko | Demo gratuito ~30/min con tope mensual | Cripto (precio en USD) | **Principal para cripto** |
| BVC / BMV / B3 / BCS / BYMA | Datos oficiales de pago o sin API pública gratuita | Nativos | **No confirmado**: se cubre con precio manual |

**Retraso y moneda:** los planes gratuitos suelen dar precio con ~15 min de retraso o cierre diario; la moneda la devuelve el proveedor (la posición guarda la suya). **Tickers colombianos** (ECOPETROL, PFBCOLOM, ISA, GRUPOSURA): cobertura gratuita **no confirmada**; por eso el precio manual es siempre un camino de primera clase.

## 2. Brokers/plataformas de usuarios (LATAM)
Trii, Tyba, Valores Bancolombia, Davivienda Corredores, Interactive Brokers, Hapi, XTB, eToro, Binance, Skandia (fondos), fiduciarias/FIC. **Ninguno se integra por API** (no hay acceso): se registra a mano o por CSV genérico `ticker,cantidad,costo`. El broker es un campo opcional.

## 3. Recomendación y política de caché
- Principal: Twelve Data (acciones/ETF) y CoinGecko (cripto); respaldo Alpha Vantage; manual como último recurso.
- Caché compartida por ticker (no son datos personales): TTL 15 min; un ticker sin datos no se reintenta por 6 h.
- Topes: global 700/día y 20/usuario/día (variables). El cron deduplica tickers entre usuarios. Mensajes honestos: «Sin datos para este ticker», «Precio de hace 3 días», «Llegaste al máximo de hoy».
- Símbolos con sufijo de mercado (CL, MX, SA, SN, BA, US) mapeados por proveedor en `precios_ticker.py` (mapeos de bolsas **no confirmados**).

## 4. Catálogo de tipos y valoración
| Tipo | Valoración | Rentabilidad |
|---|---|---|
| Acciones/ETF/cripto | precio por ticker (proveedor + manual); broker opcional | no realizada, realizada, dividendos, TIR, periodos |
| Fondos/FIC/pensiones/cesantías | valor de unidad o saldo a mano con fecha | TIR por aportes y comparación contra lo aportado |
| CDT/depósitos | capital, tasa E.A., fechas → valor hoy y a vencimiento (Patrimonio) | TIR |
| Inmuebles | valor de compra y estimado a mano; arriendo opcional; recordatorio a 6 meses | valorización y % de arriendo (no «rentabilidad de mercado») |
| Vehículos | valor de compra, año, depreciación % anual configurable (estimación) | depreciación |
| Otros | nombre libre y valor a mano | — |

Las cifras manuales muestran «actualizado hace X» y una invitación suave a revisarlas; nunca bloquean. Las deudas se enlazan con `deuda_id`; el patrimonio neto sigue siendo activos − deudas.

## 5. Arquitectura (sin duplicar Patrimonio)
- Cada posición tiene un activo «espejo» en `activos_patrimonio` (`fuente_precio="inversiones"`): Patrimonio ve el valor una sola vez; si el usuario enlaza un activo existente (`activo_id`) se actualiza ese mismo. El cron antiguo de Patrimonio lo ignora.
- Costo: **promedio ponderado** (comisiones suman al costo; una venta no cambia el promedio del resto). XIRR con compras/aportes (−) y ventas/retiros/dividendos (+) más el valor actual; no se muestra con menos de 30 días. Periodos YTD/12 m por Dietz modificado con las fotos mensuales de Patrimonio; «desde el inicio» sin foto previa.
- Moneda: `ProveedorFX` intercambiable (por defecto `app.fx`; `FXManual` de respaldo). Sin tasa, el valor en COP queda vacío en vez de sumarse como COP. No toca la configuración de país.
- Contabilidad (regla única): compra/aporte enlazado = traslado neutral «a Inversiones» (tipo transfer, categoría Transferencia); venta/retiro = traslado que entra; dividendo = ingreso «Rendimientos». Borrar la transacción revierte movimiento y saldo.
- Consejos (`consejos.py`, descartables, ids estables): `inv-concentracion:*` (>40 %), `inv-fondo-primero:*`, `inv-plata-ociosa:*`.
- Informe/Evolución: las clases de inversión ya viajan en las fotos de Patrimonio, así que «Inversiones» aparece como parte del patrimonio.
- Opcional: push semanal del portafolio (`pref_inversiones.resumen_semanal`).

## 6. Pendiente / no hecho
Precios reales de proveedores no probados (sin claves ni red en pruebas). Enlace hipoteca↔inmueble en la UI (el campo `deuda_id` existe en el API). Correo semanal (solo push). La evolución usa las fotos mensuales de clases de mercado (incluye fondos de Patrimonio).
