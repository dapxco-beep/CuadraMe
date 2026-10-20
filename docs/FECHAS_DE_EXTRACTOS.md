# Fechas de los extractos

- **Tarjeta Nu**: `fecha_corte` = corte del resumen, `periodo_inicio` = inicio del periodo facturado, `lectura_json.periodo_fin` = fin. Nunca la fecha límite de pago.
- **Mes de un extracto de tarjeta** (vistas por mes, cierre, cuadre): el mes de su fecha de corte. Ahorros: mes calendario, sin cambios.
- **Rellenar lo viejo**: «Releer este extracto», la relectura automática (`VERSION_LECTOR`) y el autoarreglo completan o corrigen las fechas con el resumen ya guardado. Si no hay resumen, el corte se estima con la fecha del correo y queda marcado en `lectura_json.fechas_estimadas`; una fecha leída del PDF nunca se pisa con una estimada.
- **Hallazgo `fechas_extracto_dudosas`**: (a) conciliado sin corte o inicio y (d) extracto repetido (misma cuenta, periodo y saldos) los repara solo el autoarreglo, con registro en `arreglos_auto` y deshacer; (b) corte en el futuro o antes del inicio y (c) periodos que se cruzan los decide la persona.
- **Repetido**: se marca en `lectura_json.duplicado_de` (el que más importó se queda). No se toca ningún movimiento ni saldo; las vistas lo ocultan.
- Sin columnas ni migraciones nuevas.
