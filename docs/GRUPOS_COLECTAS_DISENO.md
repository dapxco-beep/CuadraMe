# Colectas (vacas) y grupos — diseño para revisar

Estado: PROPUESTA, nada construido. La migración necesita el "sí" explícito de Daniel.

## Lo que ya existe (se reutiliza)
`ContactoGasto` (personas sin cuenta), `GrupoGasto`, `GastoCompartido`, `ParteGasto` y `/gastos-compartidos/saldos`.
Todo vive en el libro de UNA persona (el organizador): él ve quién le debe. No hay privacidad nueva que resolver.

## Fase 1 — Colecta (vaca): inscripción del equipo, paseo, regalo
Idea: el organizador crea una meta y marca quién ha puesto. Los demás NO necesitan cuenta.

Tablas nuevas (2):
- `colectas`: id, usuario_id (organizador), nombre, valor_por_persona (o meta total), fecha_limite, moneda, token_publico, estado, creado_en.
- `aportes_colecta`: id, colecta_id, usuario_id, contacto_id (de `ContactoGasto`), debe, pagado, pagado_en, nota.

Pantallas:
1. **Colectas** (lista): tarjeta por colecta con barra «$420.000 de $900.000 · faltan 3 personas».
2. **Detalle**: lista de participantes con ✓ pagó / ⏳ falta, botón «Marcar pagó» (con monto parcial), botón «Recordar por WhatsApp» (abre wa.me con el mensaje armado; nada se envía solo).
3. **Compartir**: enlace de solo lectura (`/c/<token>`) con el estado y nombres de pila; sin cuentas ni movimientos del organizador.
4. **Al cobrar**: el aporte puede registrarse como ingreso en la cuenta que elija el organizador (opcional), ya con la regla de cuadre de CuadraMe.

Endpoints: `GET/POST /colectas`, `GET/PATCH/DELETE /colectas/{id}`, `POST /colectas/{id}/aportes/{aporte}/pagar`, `GET /publico/colectas/{token}` (sin sesión, solo lectura, con límite de peticiones).

Seguridad/privacidad: filtrar siempre por `usuario_id`; el enlace público expone solo nombre de la colecta, valores y nombres de pila; token largo y aleatorio, revocable; agregar las rutas a la lista SIN_SESION de la prueba de aislamiento y probar que otro usuario recibe 404.

## Fase 2 — Hogar / pareja (miembros con cuenta)
Cada miembro tiene su cuenta y ve SOLO lo del grupo, nunca sus finanzas personales. Tablas: `hogares`, `miembros_hogar` (rol), `gastos_hogar` (quién pagó, división). Saldo «quién le debe a quién» con el mínimo de pagos. Es el cambio de permisos más delicado: se diseña aparte, con pruebas de aislamiento primero.

## Orden y tamaño
Fase 1 ≈ 2 migraciones pequeñas, 8 endpoints, 3 pantallas, pruebas de aislamiento. Fase 2 es ~3 veces más grande.

## Decisiones que pide a Daniel
1. ¿Empezamos por la Fase 1? 2. ¿Meta por persona (inscripción) o también total libre? 3. ¿Enlace público de solo lectura, sí o no?
