# Expansión a LATAM: investigación y arquitectura

Fecha: 2026-10-14. Nivel de confianza: **V** = verificado en fuente web en esta fecha; **NC** = no confirmado
(conocimiento general; validar con fuente oficial o abogado/contador local antes de afirmarlo al usuario).

## 1. Qué dejó el código
- `backend/app/paises.py` es la fuente única; `pwa/src/lib/paises.js` es su espejo GENERADO
  (`python tools/generar_paises_js.py`), con paridad probada en `backend/tests/test_paises.py`.
- Perfil: `GET/PUT /perfil/pais`, `GET /perfil/paises`. Sin país guardado = Colombia (perfiles anteriores).
- Sugerencia de país: zona horaria / idioma del navegador. Nunca IP ni geolocalización; la persona confirma.
- Gating: renta DIAN, 4x1000/GMF y UVT solo si el país tiene esas funciones (`renta_dian`, `gmf`, `uvt`).
  Fuera de CO la pantalla Impuestos muestra un recordatorio informativo (SAT, SII, SUNAT...), sin cálculos.
  El consejo de renta y el cron de aviso de renta también se saltan a quien no es de Colombia.
- Remitentes de correo por país: `extractos_gmail.dominios_de_pais(pais)`; la sincronización de Gmail pide los
  remitentes del país del usuario (CO por defecto: comportamiento de siempre).
- fx desacoplado: `app/fx.py` (`convertir`, proveedor intercambiable, tasa manual, fecha del tipo de cambio).
- Textos por país: `pwa/src/lib/textosPais.js` (cómo agregar es-MX / es-AR / pt-BR: ver su cabecera).

## 2. Fichas por país
| País | Moneda / formato | Pago inmediato | Banco central y tasa | Unidad tributaria | Impuestos clave | Ley de datos |
|---|---|---|---|---|---|---|
| Colombia | COP, `$ 1.234.567`, 0 dec. | Bre-B | BanRep (usura, IBR) | UVT | Renta DIAN, GMF 4x1000 | Ley 1581/2012, SIC |
| México | MXN, `$1,234.50`, 2 dec. | SPEI / CoDi | Banxico (TIIE, objetivo) | UMA | Declaración anual SAT (abril) | LFPDPPP nueva (DOF 20-mar-2025, **V**), Sec. Anticorrupción y Buen Gobierno |
| Chile | CLP, `$1.234.567`, 0 dec. | Transferencia electrónica | BCCh (TPM) | UTM / UF | Operación Renta SII (abril) | Ley 19.628; Ley 21.719 vigente 1-dic-2026, con proyecto (1-sep-2026) para postergarla a 2027 (**V**; sin confirmar si se aprobó) |
| Perú | PEN, `S/ 1,234.50`, 2 dec. | Yape / Plin | BCRP | UIT | Renta anual SUNAT (mar-abr, NC), ITF (NC) | Ley 29733 |
| Argentina | ARS, `$ 1.234,50`, 2 dec. | Transferencias 3.0 (CBU/CVU/alias) | BCRA | MNI (Ganancias) | Ganancias, Bienes Personales; Impuesto PAIS terminó a fines de 2024 (**V**, fuentes difieren entre 22 y 31-dic); impuesto a débitos y créditos (NC) | Ley 25.326, AAIP |
| Uruguay | UYU, 2 dec. | Transferencia | BCU | BPC | IRPF, DGI (NC) | Ley 18.331, URCDP |
| Ecuador | USD, 2 dec. | Transferencia interbancaria | BCE | Fracción básica | Renta SRI (NC), ISD | LOPDP 2021 (NC autoridad) |
| Panamá | USD/PAB, 2 dec. | ACH / Yappy | SBP | n/a | Renta DGI (NC) | Ley 81/2019 |
| Costa Rica | CRC `₡`, 0 dec. | SINPE Móvil | BCCR | n/a | Renta Hacienda (NC) | Ley 8968, PRODHAB |
| Brasil | BRL `R$ 1.234,50` | PIX | BCB (Selic) | n/a | IRPF (NC) | LGPD, ANPD |

Bancos y billeteras por país: ver `paises.py`. Remitentes de correo y colores de marca solo para México, Chile y
Perú, y **todos son NC**: se escribieron de memoria y hay que validarlos con correos reales (el filtro es por
dominio, así que un dominio errado simplemente no encuentra correos).

Formatos de extracto: PDF con clave y Excel/CSV son los comunes (NC); OFX relevante en Brasil (NC). En los países
nuevos NO hay lector de extractos validado: la app debe decirlo y ofrecer Excel/CSV o registro manual.

Fuentes consultadas (2026-10-14):
- Ley 21.719 Chile: diarioconstitucional.cl (12-jun-2026), cuatrecasas.com (proyecto de postergación).
- LFPDPPP México 2025: garrigues.com, basham.com.mx, hoganlovells.com.
- Impuesto PAIS Argentina: baenegocios.com, kpmg.com/ar (dic-2024), iprofesional.com.
- Todo lo marcado NC viene de conocimiento general, sin fuente en esta corrida.

## 3. Primera fase: México, Chile y Perú
1. **México**: mayor mercado de la lista, pago inmediato universal (SPEI), billeteras con tracción (Mercado Pago, Nu,
   Spin) y bancos que notifican por correo; ley de datos recién reformada (requiere borrador legal).
2. **Chile**: bancarización alta, correos transaccionales estandarizados, cartolas PDF; ley nueva en puerta
   (buen momento para diseñar consentimientos correctos desde el inicio).
3. **Perú**: el más parecido a Colombia en uso (Yape/Plin como Nequi/Bre-B), 2 decimales y ley 29733 estable.

Argentina queda para fase 2: inflación alta, varios tipos de cambio y cambios fiscales frecuentes exigen un modelo
monetario propio. Brasil requiere portugués. Uruguay, Ecuador, Panamá y Costa Rica tienen solo configuración básica.

## 4. Lo que falta / limitaciones honestas
- Los totales del backend (patrimonio, informes) todavía se suman en COP (`convertir_a_cop`); fuera de Colombia la
  app los muestra con el código «COP». Siguiente paso: pasar `perfiles.moneda_base` a `contabilidad`,
  `asistente_datos`, `consejos`, `costos_bancarios` y `cuotas_servicio` y usar `fx.convertir`.
- `SelectorPais` está listo pero **no está montado en Perfil** (módulo de otro agente): agregar `<SelectorPais />`
  allí. En el primer uso, `SugerenciaPais` ya aparece en Inicio.
- Voseo (AR/UY): `tratamiento: "vos"` queda en el registro y hay claves de ejemplo en `textosPais.js`; el resto de la
  app sigue en «tú». Pendiente para fase 2.
- Feriados por país y tasas de referencia por país en «Tu plata trabajando»: no implementados (solo la entidad y el
  nombre de la tasa en el registro).
- Categorías por país: sin cambios.
- Palabras clave de extractos/correos por país (`palabras_extracto`) están en el registro pero el clasificador de
  correos aún usa las de siempre.
- Las pruebas no usaron cuentas bancarias ni extractos reales de otros países.
