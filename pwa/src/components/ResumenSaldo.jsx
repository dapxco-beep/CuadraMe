import { useState } from 'react'
import { useBloqueo } from '../lib/BloqueoContext'
import { filasPorModo } from '../lib/saldos'

const MODOS = [
  { id: 'total', label: 'Total' },
  { id: 'moneda', label: 'Por moneda' },
  { id: 'tipo', label: 'Por tipo' },
]

// Explica de dónde sale el "Saldo actual" y deja verlo de tres formas:
//  Total  -> disponible hoy / comprometido este mes / deudas de tarjeta
//  Moneda -> un renglón por cada moneda (COP, USD...) en su moneda original
//  Tipo   -> ahorros, efectivo, tarjetas, inversión (en pesos)
// Hereda el color del contenedor para servir tanto en el héroe oscuro como en tarjetas claras.
export default function ResumenSaldo({ resumen, bolsillo, className = '' }) {
  const [modo, setModo] = useState('total')
  const { fmt } = useBloqueo()
  if (!resumen) return null

  const comprometido = bolsillo ? (bolsillo.recurrentes_pendientes_mes || 0) + (bolsillo.aportes_comprometidos_mes || 0) : null
  const filas = filasPorModo(modo, resumen)

  return (
    <div className={className}>
      <div className="flex gap-1.5" role="group" aria-label="Ver saldo">
        {MODOS.map((m) => (
          <button
            key={m.id}
            type="button"
            aria-pressed={modo === m.id}
            onClick={() => setModo(m.id)}
            className={`relative before:absolute before:-inset-y-[9px] before:inset-x-0 before:content-[''] rounded-full px-3 py-1 text-[11px] font-semibold border border-current ${modo === m.id ? 'bg-[color-mix(in_srgb,currentColor_16%,transparent)]' : 'opacity-70'}`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="mt-3 rounded-2xl bg-[color-mix(in_srgb,currentColor_9%,transparent)] px-3.5 py-3 space-y-1.5 text-xs" data-testid="desglose-saldo">
        {modo === 'total' ? (
          <>
            <Fila k="Disponible hoy (en tus cuentas, sin contar tarjetas)" v={fmt(resumen.disponible_cop)} />
            {comprometido !== null && <Fila k="Comprometido este mes (pagos fijos y metas)" v={`− ${fmt(comprometido)}`} />}
            <Fila k="Lo que debes en tarjetas de crédito" v={`− ${fmt(resumen.deudas_tarjeta_cop)}`} />
            {bolsillo?.cuotas_tarjeta_mes > 0 && (
              <Fila k="De eso, en cuotas este mes" v={fmt(bolsillo.cuotas_tarjeta_mes)} />
            )}
            <p className="pt-1 opacity-80 leading-snug">
              Tu saldo es lo que tienes en tus cuentas menos lo que debes en tarjetas.
              {comprometido !== null ? ' Lo comprometido aún no se descuenta de tu saldo: es plata que ya sabes que vas a pagar.' : ''}
            </p>
          </>
        ) : filas.length === 0 ? (
          <p>Aún no hay nada que mostrar. Registra un movimiento y aparecerá aquí.</p>
        ) : (
          filas.map((f) => <Fila key={f.clave} k={f.etiqueta} v={fmt(f.valor, f.moneda)} />)
        )}
      </div>
    </div>
  )
}

function Fila({ k, v }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="opacity-85">{k}</span>
      <span className="font-semibold shrink-0">{v}</span>
    </div>
  )
}
