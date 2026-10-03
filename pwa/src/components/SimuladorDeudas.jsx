import { useState } from 'react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

// El backend manda la fecha libre como "2028-03"; aquí se lee como "marzo de 2028".
function fechaLegible(clave) {
  if (!clave) return 'No se termina de pagar'
  const [anio, mes] = clave.split('-')
  return `${MESES[parseInt(mes, 10) - 1]} de ${anio}`
}

function duracion(meses) {
  if (meses == null) return '—'
  const a = Math.floor(meses / 12)
  const m = meses % 12
  const partes = []
  if (a) partes.push(`${a} ${a === 1 ? 'año' : 'años'}`)
  if (m || !a) partes.push(`${m} ${m === 1 ? 'mes' : 'meses'}`)
  return partes.join(' y ')
}

const METODOS = [
  { id: 'sin_extra', titulo: 'Solo cuotas', color: 'var(--color-ink-soft)' },
  { id: 'bola_de_nieve', titulo: 'Bola de nieve', color: 'var(--color-accent-2)' },
  { id: 'avalancha', titulo: 'Avalancha', color: 'var(--color-accent)' },
]

// Barras horizontales: el largo es proporcional a los intereses totales, así
// se ve de un vistazo cuál método cuesta menos.
function GraficoComparativo({ resultado }) {
  const max = Math.max(1, ...METODOS.map((m) => resultado[m.id].intereses_totales))
  return (
    <div className="space-y-3" role="img" aria-label="Comparación de intereses totales por método">
      {METODOS.map((m) => {
        const r = resultado[m.id]
        const pct = Math.max(2, (r.intereses_totales / max) * 100)
        return (
          <div key={m.id}>
            <div className="flex justify-between text-xs mb-1">
              <span className="font-medium">{m.titulo}</span>
              <span className="text-ink-soft">{formatCOP(r.intereses_totales)}</span>
            </div>
            <div className="h-3 rounded-full bg-paper overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{ width: `${pct}%`, background: m.color, transition: 'width 600ms ease-out' }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function TarjetaMetodo({ titulo, descripcion, r, mejor }) {
  return (
    <div className={`rounded-2xl border p-3 ${mejor ? 'border-accent bg-accent-soft' : 'border-line bg-paper-raised'}`}>
      <div className="flex items-center justify-between mb-0.5">
        <p className="text-sm font-semibold">{titulo}</p>
        {mejor && <span className="text-[10px] font-semibold text-accent">Menos intereses</span>}
      </div>
      <p className="text-[11px] text-ink-soft mb-2">{descripcion}</p>
      <p className="text-xs text-ink-soft">Libre de deudas</p>
      <p className="text-sm font-bold mb-2">{fechaLegible(r.fecha_libre)}</p>
      <p className="text-xs text-ink-soft">{duracion(r.meses)}</p>
      <p className="text-xs mt-1">
        Intereses: <span className="font-semibold">{formatCOP(r.intereses_totales)}</span>
      </p>
      {r.ahorro_intereses != null && (
        <p className="text-xs text-accent font-semibold mt-1">Ahorras {formatCOP(r.ahorro_intereses)}</p>
      )}
    </div>
  )
}

export default function SimuladorDeudas() {
  const [extra, setExtra] = useState('')
  const [resultado, setResultado] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')

  async function simular() {
    setError('')
    setCargando(true)
    try {
      setResultado(await api.estrategiaDeudas(Number(extra) || 0))
    } catch (err) {
      setError(err.message || 'No se pudo simular')
    } finally {
      setCargando(false)
    }
  }

  return (
    <section className="mx-5 mt-5 rounded-2xl bg-paper-raised border border-line p-4" aria-label="Simulador de estrategia">
      <h2 className="text-sm font-semibold mb-1">¿Cómo salir más rápido de deudas?</h2>
      <p className="text-xs text-ink-soft mb-3">
        Avalancha paga primero la deuda con mayor interés (ahorras más). Bola de nieve paga primero la de menor saldo
        (cierras deudas rápido y te motivas). Cuando saldas una, su cuota pasa a la siguiente.
      </p>

      <label className="block text-xs text-ink-soft mb-1" htmlFor="extra-mensual">
        ¿Cuánto extra puedes pagar al mes?
      </label>
      <div className="flex gap-2">
        <input
          id="extra-mensual"
          value={extra}
          onChange={(e) => setExtra(e.target.value.replace(/\D/g, ''))}
          onKeyDown={(e) => e.key === 'Enter' && simular()}
          inputMode="numeric"
          placeholder="Ej. 200000"
          className="flex-1 min-w-0 rounded-2xl border border-line bg-paper px-4 py-3 text-sm outline-none focus:border-accent"
        />
        <button
          onClick={simular}
          disabled={cargando}
          className="bg-ink text-paper font-semibold rounded-2xl px-5 text-sm disabled:opacity-60"
        >
          {cargando ? 'Simulando...' : 'Simular'}
        </button>
      </div>

      {error && <p role="alert" className="text-sm text-danger mt-3">{error}</p>}

      {resultado && (
        <div className="mt-4 space-y-4 screen-enter">
          {resultado.sin_extra.meses == null && (
            <p className="text-xs text-danger">
              Con las cuotas actuales alguna deuda no baja (la cuota no cubre ni el interés). El pago extra es clave.
            </p>
          )}
          <div className="grid grid-cols-2 gap-3">
            <TarjetaMetodo
              titulo="Avalancha"
              descripcion="Mayor interés primero"
              r={resultado.avalancha}
              mejor={resultado.mejor === 'avalancha'}
            />
            <TarjetaMetodo
              titulo="Bola de nieve"
              descripcion="Menor saldo primero"
              r={resultado.bola_de_nieve}
              mejor={resultado.mejor === 'bola_de_nieve'}
            />
          </div>
          <GraficoComparativo resultado={resultado} />
          <p className="text-[11px] text-ink-soft">
            Estimación con tus cuotas y tasas registradas. Los intereses reales dependen de lo que cobre cada entidad.
          </p>
        </div>
      )}
    </section>
  )
}
