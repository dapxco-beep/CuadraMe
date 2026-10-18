import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { mensajeAmable } from '../lib/mensajes'

// «Saldo inicial automático»: con cuánto empezó la cuenta, leído de su extracto más antiguo. No es un ingreso ni un
// gasto. Si llega un extracto anterior o cambian movimientos de antes, el servidor lo recalcula solo; «Volver a
// calcular» lo fuerza (y reactiva el cálculo si la persona lo había deshecho). Se usa en el detalle de la cuenta y en
// el Cierre de mes. `info` = { monto, fecha, explicacion } (puede venir null con `desactivado`).
const EXPLICACION = 'Es lo que tenías antes de tu primer extracto. No cuenta como ingreso ni gasto.'

function fechaCorta(iso) {
  if (!iso) return ''
  const [a, m, d] = iso.slice(0, 10).split('-').map(Number)
  const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
  return `${d} ${meses[m - 1]} ${a}`
}

export default function SaldoInicialAutomatico({ cuentaId, moneda, info, desactivado = false, onCambio }) {
  const { fmt } = useBloqueo()
  const [ocupado, setOcupado] = useState(false)
  const [aviso, setAviso] = useState('')
  if (!info && !desactivado) return null

  async function recalcular() {
    setOcupado(true)
    setAviso('')
    try {
      const r = await api.cuadreSaldoInicialAutoRecalcular(cuentaId)
      setAviso(r?.texto || 'Listo, el saldo inicial está al día.')
      onCambio?.()
    } catch (err) {
      setAviso(mensajeAmable(err?.message, { porDefecto: 'No pude volver a calcular. Intenta de nuevo.' }))
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div className="rounded-2xl bg-paper-raised border border-line p-3 mt-3" data-testid="saldo-inicial-auto">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold">Saldo inicial automático</p>
        {info && <p className="text-sm font-semibold tabular-nums shrink-0">{fmt(info.monto, moneda)}</p>}
      </div>
      {info?.fecha && <p className="text-[11px] text-ink-soft">Al {fechaCorta(info.fecha)}</p>}
      <p className="text-xs text-ink-soft mt-1">
        {info ? (info.explicacion || EXPLICACION) : 'Lo deshiciste, así que no lo calculo solo. Puedes volver a calcularlo.'}
      </p>
      <button type="button" onClick={recalcular} disabled={ocupado}
        className="mt-1 min-h-11 inline-flex items-center gap-2 text-xs font-semibold text-accent">
        <RefreshCw size={16} aria-hidden="true" className={ocupado ? 'animate-spin' : ''} />
        {ocupado ? 'Calculando…' : 'Volver a calcular'}
      </button>
      <p role="status" aria-live="polite" className="text-[11px] text-ink-soft">{aviso}</p>
    </div>
  )
}
