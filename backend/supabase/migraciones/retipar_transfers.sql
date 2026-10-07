-- Re-tipar los movimientos 'transfer' importados de extractos (sin dirección) a income/expense.
--
-- Contexto: antes de esta regla, los renglones de transferencia de un extracto (Nequi 'Transfer',
-- Nu 'Transferencia'...) se guardaban con tipo='transfer': NO movían el saldo de la cuenta y
-- perdían si fueron entrada o salida. La regla correcta: todo movimiento tiene dirección y
-- SIEMPRE mueve el saldo; que sea traslado propio (neutral) o gasto/ingreso real lo decide
-- contabilidad.tipos_efectivos (par detectado entre cuentas propias), no el tipo.
--
-- QUÉ HACE (todo en UNA transacción, idempotente, NO se ha ejecutado):
--   1. Re-tipa SOLO lo deducible con certeza por la descripción:
--        expense: 'Para …', 'Enviaste…', 'Envío…', 'Transferencia a …', 'Trf a …', 'Transferiste…'
--        income : 'De …', 'Recibiste…', 'Transferencia de …', 'Trf de …', 'Giro de …', 'Te enviaron…'
--      (ambas o ninguna -> NO se toca; el saldo por fila no se guarda en notas, así que no hay
--      segunda fuente de dirección). Se EXCLUYEN los traslados creados en la app
--      (fuente transferencia_interna: son pares out/in que sí mueven saldo), los ajustes de saldo
--      y los aportes a meta.
--   2. Ajusta el saldo por el efecto que el movimiento DEBIÓ tener, por cuenta:
--        - cuenta SIN 'ajuste_saldo': saldo += suma de (income +monto, expense -monto)
--          (salvo fuente importado_sin_saldo: el banco ya lo reflejaba, no se mueve).
--        - cuenta CON 'ajuste_saldo' (el usuario forzó el saldo real a mano): el saldo YA era el
--          real, así que NO cambia; el último ajuste absorbe la diferencia (ajuste -= suma) y se
--          borra si queda en cero. Así el libro (suma de movimientos) iguala al saldo real.
--   3. Comprobaciones que ABORTAN (RAISE EXCEPTION => rollback de todo).
--
-- ANTES: ejecutar las consultas de SOLO LECTURA de abajo (conteo por cuenta y no deducibles) y
-- hacer respaldo (pg_dump / backup de Supabase). DESPUÉS: revisar la sección 'verificación'.
-- Se corre a mano en el SQL Editor de Supabase o con `supabase db query --linked -f <este archivo>`.
--
-- ── CONSULTAS DE SOLO LECTURA (correr antes) ─────────────────────────────────────────────────
-- a) 'transfer' por cuenta y cuántos NO se pueden deducir:
--    SELECT left(cuenta_id,8) AS cuenta, count(*) AS transfers,
--           count(*) FILTER (WHERE descripcion ~* '^\s*(para|enviaste|envi[oó]|transferencia a|trf a|transferiste)(\s|$)'
--                              AND NOT descripcion ~* '^\s*(de|recib(i|í|iste)|transferencia de|trf de|giro de|te enviaron)(\s|$)') AS salen,
--           count(*) FILTER (WHERE descripcion ~* '^\s*(de|recib(i|í|iste)|transferencia de|trf de|giro de|te enviaron)(\s|$)'
--                              AND NOT descripcion ~* '^\s*(para|enviaste|envi[oó]|transferencia a|trf a|transferiste)(\s|$)') AS entran
--    FROM movimientos WHERE tipo='transfer' AND coalesce(fuente,'') NOT IN ('transferencia_interna','ajuste_saldo','aporte_meta')
--    GROUP BY 1 ORDER BY 2 DESC;
-- b) Lista de los NO deducibles (sin descripciones):
--    SELECT id, fecha::date, monto, left(cuenta_id,8) AS cuenta FROM movimientos
--    WHERE tipo='transfer' AND coalesce(fuente,'') NOT IN ('transferencia_interna','ajuste_saldo','aporte_meta')
--      AND NOT (descripcion ~* '^\s*(para|enviaste|envi[oó]|transferencia a|trf a|transferiste)(\s|$)')
--      AND NOT (descripcion ~* '^\s*(de|recib(i|í|iste)|transferencia de|trf de|giro de|te enviaron)(\s|$)');
--    (los que coinciden con AMBOS patrones también quedan sin tocar; revísalos a mano en la app.)

BEGIN;

CREATE TEMP TABLE _rt ON COMMIT DROP AS
SELECT m.id, m.cuenta_id, m.monto, m.fuente,
       CASE
         WHEN m.descripcion ~* '^\s*(para|enviaste|envi[oó]|transferencia a|trf a|transferiste)(\s|$)'
              AND NOT m.descripcion ~* '^\s*(de|recib(i|í|iste)|transferencia de|trf de|giro de|te enviaron)(\s|$)' THEN 'expense'
         WHEN m.descripcion ~* '^\s*(de|recib(i|í|iste)|transferencia de|trf de|giro de|te enviaron)(\s|$)'
              AND NOT m.descripcion ~* '^\s*(para|enviaste|envi[oó]|transferencia a|trf a|transferiste)(\s|$)' THEN 'income'
       END AS nuevo
FROM movimientos m
WHERE m.tipo = 'transfer'
  AND coalesce(m.fuente, '') NOT IN ('transferencia_interna', 'ajuste_saldo', 'aporte_meta');

DELETE FROM _rt WHERE nuevo IS NULL;

-- Efecto en saldo por cuenta (lo que debió moverse) y si la cuenta tiene ajuste de saldo.
CREATE TEMP TABLE _delta ON COMMIT DROP AS
SELECT r.cuenta_id,
       coalesce(sum(CASE WHEN r.fuente IS DISTINCT FROM 'importado_sin_saldo'
                         THEN CASE r.nuevo WHEN 'income' THEN r.monto ELSE -r.monto END END), 0) AS delta,
       EXISTS (SELECT 1 FROM movimientos a WHERE a.cuenta_id = r.cuenta_id AND a.fuente = 'ajuste_saldo') AS con_ajuste
FROM _rt r GROUP BY r.cuenta_id;

-- Comprobaciones previas: toda cuenta existe; ningún monto inválido.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM _delta d LEFT JOIN cuentas c ON c.id = d.cuenta_id WHERE c.id IS NULL) THEN
    RAISE EXCEPTION 'retipar_transfers: hay movimientos transfer cuya cuenta no existe';
  END IF;
  IF EXISTS (SELECT 1 FROM _rt WHERE monto IS NULL OR monto <= 0) THEN
    RAISE EXCEPTION 'retipar_transfers: hay movimientos transfer con monto invalido';
  END IF;
END $$;

CREATE TEMP TABLE _saldo_antes ON COMMIT DROP AS
SELECT id, saldo FROM cuentas WHERE id IN (SELECT cuenta_id FROM _delta);

-- 1) Re-tipar.
UPDATE movimientos m
SET tipo = r.nuevo,
    notas = CASE WHEN coalesce(m.notas, '') LIKE '%retipado_desde_transfer%' THEN m.notas
                 ELSE trim(both ' ' from coalesce(m.notas, '') || ' · retipado_desde_transfer') END
FROM _rt r WHERE r.id = m.id;

-- 2a) Cuentas sin ajuste de saldo: el saldo se corrige por el efecto que faltaba.
UPDATE cuentas c SET saldo = coalesce(c.saldo, 0) + d.delta
FROM _delta d WHERE d.cuenta_id = c.id AND NOT d.con_ajuste AND d.delta <> 0;

-- 2b) Cuentas con ajuste: el saldo ya era el real; el último ajuste absorbe la diferencia.
-- (el nuevo valor firmado se calcula UNA vez en _aj, antes de tocar nada)
CREATE TEMP TABLE _aj ON COMMIT DROP AS
SELECT u.id,
       (CASE u.tipo WHEN 'income' THEN u.monto ELSE -u.monto END) - d.delta AS firmado
FROM (
  SELECT DISTINCT ON (a.cuenta_id) a.id, a.cuenta_id, a.tipo, a.monto
  FROM movimientos a JOIN _delta d0 ON d0.cuenta_id = a.cuenta_id AND d0.con_ajuste
  WHERE a.fuente = 'ajuste_saldo'
  ORDER BY a.cuenta_id, a.fecha DESC, a.id DESC
) u JOIN _delta d ON d.cuenta_id = u.cuenta_id;

UPDATE movimientos m
SET tipo = CASE WHEN n.firmado >= 0 THEN 'income' ELSE 'expense' END,
    monto = abs(n.firmado)
FROM _aj n WHERE n.id = m.id AND abs(n.firmado) >= 0.005;

DELETE FROM movimientos m USING _aj n WHERE n.id = m.id AND abs(n.firmado) < 0.005;

-- 3) Comprobaciones finales que ABORTAN.
DO $$
DECLARE restantes int; mal numeric;
BEGIN
  SELECT count(*) INTO restantes FROM movimientos m JOIN _rt r ON r.id = m.id WHERE m.tipo = 'transfer';
  IF restantes > 0 THEN
    RAISE EXCEPTION 'retipar_transfers: quedaron % movimientos deducibles sin re-tipar', restantes;
  END IF;
  -- Cuentas sin ajuste: el saldo cambió exactamente por el delta; con ajuste: no cambió.
  SELECT count(*) INTO mal FROM cuentas c
    JOIN _saldo_antes s ON s.id = c.id JOIN _delta d ON d.cuenta_id = c.id
   WHERE abs((coalesce(c.saldo,0) - coalesce(s.saldo,0)) - CASE WHEN d.con_ajuste THEN 0 ELSE d.delta END) > 0.005;
  IF mal > 0 THEN
    RAISE EXCEPTION 'retipar_transfers: % cuentas con saldo distinto al esperado', mal;
  END IF;
  IF EXISTS (SELECT 1 FROM cuentas WHERE saldo IS NULL OR saldo <> saldo) THEN
    RAISE EXCEPTION 'retipar_transfers: hay saldos nulos o NaN';
  END IF;
END $$;

COMMIT;

-- ── VERIFICACIÓN (solo lectura, después) ──────────────────────────────────────────────────────
-- Cuántos 'transfer' sin dirección quedan (deben ser solo los no deducibles; revisarlos a mano):
--   SELECT count(*) FROM movimientos WHERE tipo='transfer' AND coalesce(fuente,'') NOT IN ('transferencia_interna','ajuste_saldo','aporte_meta');
-- ¿El libro iguala al saldo? (cuentas sin saldo inicial manual; diferencia = saldo inicial o ajustes pendientes)
--   SELECT left(c.id,8) AS cuenta, c.saldo,
--          coalesce(sum(CASE WHEN m.fuente = 'importado_sin_saldo' THEN 0 WHEN m.tipo='income' THEN m.monto WHEN m.tipo='expense' THEN -m.monto
--                           WHEN m.fuente='transferencia_interna' AND m.notas LIKE '%:in' THEN m.monto
--                           WHEN m.fuente='transferencia_interna' AND m.notas LIKE '%:out' THEN -m.monto ELSE 0 END),0) AS libro
--   FROM cuentas c LEFT JOIN movimientos m ON m.cuenta_id = c.id GROUP BY c.id, c.saldo;
