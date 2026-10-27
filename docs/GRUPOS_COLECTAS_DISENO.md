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

---

# Fase 2 — Hogar / pareja (diseño detallado, PROPUESTA)

Estado: Fase 1 desplegada el 2026-10-26. Esta fase NO está construida.

## Qué resuelve
Una pareja, familia o compañeros de casa: cada quien con su cuenta de CuadraMe, y UN libro común donde se ve quién pagó qué de la casa y cuánto le debe cada uno a quién. Cada persona sigue viendo SOLO lo suyo más ese libro.

## Lo que se reutiliza
- `division.py`: reparto exacto (iguales, montos, %, partes) y `simplificar_deudas` (el mínimo de pagos para quedar a mano).
- `InvitacionCuenta` como modelo del flujo de invitar por correo y aceptar.
- `/gastos-compartidos` como modelo de pantallas (saldos, cobrar por WhatsApp, deshacer).

## Principio de privacidad (lo más importante)
El libro del hogar es un recurso nuevo con permisos por MEMBRESÍA, no por `usuario_id`. Reglas:
1. Un miembro ve solo: nombre del hogar, miembros (apodo), gastos del hogar, saldos y pagos. Nunca cuentas, movimientos, saldos ni categorías personales de otro miembro.
2. Un no miembro recibe 404 (no 403) en cualquier ruta del hogar: no se revela que existe.
3. Quien sale o es sacado pierde el acceso en el acto; lo que ya aportó se conserva en el libro (para que los saldos no cambien) con su nombre reemplazado por «Ex miembro» si pidió borrar sus datos (Ley 1581).
4. Un gasto del hogar solo se copia a las cuentas PERSONALES de quien lo pidió, y solo su parte.

## Tablas nuevas (6)
- `hogares`: id, nombre, moneda, creado_por, creado_en.
- `miembros_hogar`: hogar_id, usuario_id, rol (admin|miembro), apodo, unido_en. Único (hogar_id, usuario_id).
- `invitaciones_hogar`: hogar_id, email, token, invitado_por, estado, vence_en.
- `gastos_hogar`: id, hogar_id, descripcion, total, moneda, pagador_usuario_id, modo, fecha, creado_por, movimiento_id (opcional, el del pagador).
- `partes_gasto_hogar`: gasto_id, usuario_id, monto.
- `pagos_hogar`: hogar_id, de_usuario_id, a_usuario_id, monto, moneda, nota, fecha (liquidaciones).

## Endpoints (prefijo `/hogares`)
`GET/POST /hogares` · `GET/PATCH/DELETE /hogares/{id}` · `POST /hogares/{id}/invitar` · `POST /hogares/invitaciones/{token}/aceptar` · `DELETE /hogares/{id}/miembros/{uid}` (admin, o uno mismo para salir) · `GET/POST /hogares/{id}/gastos` · `DELETE /hogares/{id}/gastos/{gid}` (autor o admin) · `GET /hogares/{id}/saldos` · `POST /hogares/{id}/pagos` · `DELETE /hogares/{id}/pagos/{pid}`.

Toda ruta pasa por UNA función `miembro_o_404(db, usuario, hogar_id)`; ninguna consulta toca `gastos_hogar` sin ese filtro.

## Pantallas
1. **Hogar**: tarjeta de saldos («Ana le debe 150.000 a Luis») + botón «Ya le pagué».
2. **Nuevo gasto del hogar**: qué, cuánto, quién pagó, cómo se reparte (reutiliza la hoja de Dividir gasto) y casilla «Registrarlo también en mi cuenta (mi parte)».
3. **Miembros e invitaciones**: invitar por correo o enlace, quitar, salir.
4. **Resumen del mes del hogar**: cuánto puso cada uno y en qué categoría se fue.

## Riesgos y cómo se cubren
- Fuga entre hogares o hacia no miembros: pruebas nuevas de aislamiento (no miembro → 404 en TODAS las rutas; miembro de otro hogar → 404; ex miembro → 404) y se agrega el hogar a `test_aislamiento_usuarios.py`.
- Borrado de cuenta: se quita su membresía y sus gastos quedan con «Ex miembro»; se agrega a la prueba de borrado de cuenta y al respaldo.
- Invitación a un correo equivocado: el token vence en 7 días, es de un solo uso y el admin puede cancelarla.
- Concurrencia al registrar pagos: mismo cuidado de `bloquear_cuenta` cuando el gasto se copia a una cuenta personal.

## Tamaño y orden
≈ 3 veces la Fase 1: 6 tablas, ~14 endpoints, 4 pantallas, y la mayor parte del esfuerzo en pruebas de aislamiento. Orden: (1) hogar + miembros + invitación con pruebas de aislamiento, (2) gastos y saldos, (3) pagos y copia a mi cuenta, (4) resumen del mes.

## Decisiones para Daniel
1. ¿Invitar por correo (como las cuentas compartidas) o también por enlace de un solo uso?
2. ¿Un usuario puede estar en varios hogares (casa + viaje)? Recomiendo sí.
3. ¿Los miembros editan gastos de otros o solo el autor y el admin? Recomiendo autor y admin.
4. ¿Avisos (push) cuando alguien registra un gasto? Recomiendo sí, apagables.
