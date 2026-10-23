import { CalendarClock, CreditCard } from 'lucide-react'
import Icono from './Icono'
import BarraProgreso from './BarraProgreso'
import { useBloqueo } from '../lib/BloqueoContext'
import { datosDeuda } from '../lib/deudaTarjeta'

// «Debes $X · Cupo $C · Disponible $D» con una barra de uso del cupo, el corte, el pago hasta y el pago mínimo.
// La tarjeta es deuda: aquí nunca aparece «saldo» ni «ingresos». `compacta`: sin el número grande (el encabezado ya lo trae).
export default function DeudaTarjeta({ vista, moneda = 'COP', compacta = false, saldoAFavor = null, className = '' }) {
  const { fmt } = useBloqueo()
  const d = datosDeuda(vista, fmt, moneda)
  if (!d) return null
  return (
    <div className={className} data-testid="deuda-tarjeta">
      <p className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm" data-testid="deuda-resumen">
        <Icono icono={CreditCard} tam="sm" className="self-center text-accent" />
        <span className="text-ink-soft">{d.aFavor ? 'Saldo a favor' : 'Debes'}</span>
        <span className={`font-bold tabular-nums ${compacta ? '' : 'text-base'}`}>{d.aFavor && saldoAFavor > 0 ? fmt(saldoAFavor, moneda) : d.debes}</span>
        {d.cupo && <span className="text-ink-soft">· Cupo <span className="tabular-nums">{d.cupo}</span></span>}
        {d.disponible && <span className="text-ink-soft">· Cupo disponible <span className="tabular-nums">{d.disponible}</span></span>}
      </p>
      {d.usoPct != null && (
        <div className="mt-2">
          <BarraProgreso pct={d.usoPct} label="Uso del cupo" texto={`${Math.round(d.usoPct)} % del cupo usado`} />
          <p className="text-[11px] text-ink-soft mt-1">{Math.round(d.usoPct)} % del cupo usado</p>
        </div>
      )}
      {d.corte && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-soft" data-testid="corte-pago">
          <Icono icono={CalendarClock} tam="sm" /> <span>{d.corte}</span>
        </p>
      )}
      {d.pagoMinimo && <p className="mt-1 text-xs text-ink-soft" data-testid="pago-minimo">Pago mínimo <span className="font-semibold tabular-nums">{d.pagoMinimo}</span></p>}
    </div>
  )
}
