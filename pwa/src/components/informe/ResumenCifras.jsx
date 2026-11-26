import { Link } from 'react-router-dom'
import { Cambio, Panel, conSigno, pctSimple } from './comun'

// Lo primero que se ve en Informes: ¿me alcanzó la plata? Todas las cifras salen de GET /informes/resumen
// (regla única de contabilidad: sin traslados entre tus cuentas ni pagos de tarjeta) y se comparan con el periodo
// anterior equivalente que el servidor calcula (ver `informe.periodo_anterior`).
const AYUDA =
  'Ingresos: plata que entró. Gastos: plata que salió. Flujo neto: ingresos menos gastos. Tasa de ahorro: qué parte de ' +
  'tus ingresos te sobró (flujo neto ÷ ingresos). No se cuentan los traslados entre tus cuentas, los pagos de tarjeta ' +
  'ni los ajustes de saldo, porque no son plata que entra o sale de verdad.'

function Cifra({ etiqueta, descripcion, children }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-ink-soft" title={descripcion}>{etiqueta}</dt>
      {children}
    </div>
  )
}

export default function ResumenCifras({ d, fmt, parametrosMov = '' }) {
  const ant = d.anterior
  const sinBase = ant.ingresos === 0 && ant.gastos === 0 // el periodo anterior está vacío: no hay con qué comparar
  const colorNeto = d.balance > 0 ? 'text-cuadra' : d.balance < 0 ? 'text-danger' : 'text-ink'
  const estado = d.balance > 0 ? 'te sobró' : d.balance < 0 ? 'te faltó' : 'quedaste en cero'
  return (
    <Panel titulo="¿Me alcanzó la plata?" pregunta={`Flujo neto · ${d.etiqueta}`} info={AYUDA}>
      <p
        className={`text-[34px] leading-none t-display t-cifra ${colorNeto}`}
        aria-label={`Flujo neto: ${estado}${d.balance === 0 ? '' : ` ${fmt(Math.abs(d.balance))}`}`}
      >
        {conSigno(d.balance, fmt)}
      </p>
      <p className="mt-1 text-xs text-ink-soft">
        {d.balance === 0 ? 'Quedaste en cero' : `En este periodo ${estado} esta plata`}
        {!sinBase && <> · <Cambio pct={d.variacion.balance_pct} actual={d.balance} className="align-middle" /></>}
      </p>

      <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-line pt-3">
        <Cifra etiqueta="Ingresos" descripcion="Plata que entró en el periodo">
          <dd className="text-[15px] font-bold t-cifra text-ink">{fmt(d.ingresos)}</dd>
          {!sinBase && <Cambio pct={d.variacion.ingresos_pct} actual={d.ingresos} mejorSube />}
        </Cifra>
        <Cifra etiqueta="Gastos" descripcion="Plata que salió en el periodo">
          <dd className="text-[15px] font-bold t-cifra text-ink">{fmt(d.gastos)}</dd>
          {!sinBase && <Cambio pct={d.variacion.gastos_pct} actual={d.gastos} mejorSube={false} />}
        </Cifra>
        <Cifra etiqueta="Tasa de ahorro" descripcion="Qué parte de tus ingresos te sobró">
          <dd className="text-[15px] font-bold t-cifra text-ink">{pctSimple(d.tasa_ahorro)}</dd>
          {d.tasa_ahorro === null ? (
            <span className="text-[11px] text-ink-soft">sin ingresos</span>
          ) : sinBase ? null : (
            <Cambio pct={d.variacion.tasa_ahorro_puntos} actual={d.tasa_ahorro} puntos mejorSube />
          )}
        </Cifra>
      </dl>

      {sinBase ? (
        <p className="mt-3 text-xs text-ink-soft leading-relaxed" data-testid="sin-base">
          No hay movimientos en {ant.etiqueta}, así que todavía no hay con qué comparar este periodo.
        </p>
      ) : (
        <p className="mt-3 text-xs text-ink-soft leading-relaxed">
          Frente a {ant.etiqueta}: ingresos {fmt(ant.ingresos)}, gastos {fmt(ant.gastos)}, flujo neto {conSigno(ant.balance, fmt)}
          {ant.tasa_ahorro !== null ? `, tasa de ahorro ${pctSimple(ant.tasa_ahorro)}` : ''}.
        </p>
      )}
      {d.en_curso && !sinBase && (
        <p className="mt-1 text-xs text-ink-soft">
          El periodo sigue en curso: la comparación usa el mismo tramo del periodo anterior para que sea justa.
        </p>
      )}
      <Link to={`/movimientos?${parametrosMov}`} className="mt-1 inline-flex items-center min-h-11 text-sm font-semibold text-accent">
        Ver los movimientos de este periodo
      </Link>
    </Panel>
  )
}
