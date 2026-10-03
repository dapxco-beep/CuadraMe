import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { api } from '../lib/api'
import { PERIODOS } from '../lib/planificacion'

// Ajustes de planificación: periodo por defecto para presupuestos nuevos, día de
// pago (alinea la quincena), regla de reparto (50/30/20 editable) y qué
// presupuestos arrastran el sobrante al periodo siguiente.
export default function ConfigPlanificacion({ presupuestos, onClose, onGuardado }) {
  const [cfg, setCfg] = useState(null)
  const [diaPago, setDiaPago] = useState('')
  const [periodo, setPeriodo] = useState('monthly')
  const [regla, setRegla] = useState({ necesidades: 50, deseos: 30, ahorro: 20 })
  const [arrastre, setArrastre] = useState([])
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.configPlanificacion().then((c) => {
      if (!c || Array.isArray(c)) return
      setCfg(c)
      setDiaPago(c.dia_pago ? String(c.dia_pago) : '')
      setPeriodo(c.periodo_defecto || 'monthly')
      setRegla(c.regla || { necesidades: 50, deseos: 30, ahorro: 20 })
      setArrastre(c.arrastre_ids || [])
    }).catch(() => {})
  }, [])

  const suma = Number(regla.necesidades) + Number(regla.deseos) + Number(regla.ahorro)

  function cambiarRegla(clave, valor) {
    setRegla((r) => ({ ...r, [clave]: valor === '' ? '' : Math.min(100, Number(valor.replace(/\D/g, ''))) }))
  }

  async function guardar() {
    setError('')
    if (Math.abs(suma - 100) > 0.01) return setError(`La regla suma ${suma}%; debe sumar 100%`)
    const dia = diaPago ? Number(diaPago) : null
    if (dia !== null && (dia < 1 || dia > 31)) return setError('El día de pago va de 1 a 31')
    setGuardando(true)
    try {
      await api.guardarConfigPlanificacion({
        ...(dia ? { dia_pago: dia } : { sin_dia_pago: true }),
        periodo_defecto: periodo,
        regla_necesidades: Number(regla.necesidades),
        regla_deseos: Number(regla.deseos),
        regla_ahorro: Number(regla.ahorro),
        arrastre_ids: arrastre,
      })
      onGuardado()
    } catch (err) {
      setError(err.message || 'No se pudo guardar')
    }
    setGuardando(false)
  }

  function alternarArrastre(id) {
    setArrastre((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]))
  }

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-50 sheet-backdrop">
      <div className="w-full max-w-[480px] bg-paper rounded-t-[28px] p-6 pb-8 max-h-[90vh] overflow-y-auto sheet-content">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Ajustes de planificación</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>

        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Periodo para presupuestos nuevos</p>
        <div className="grid grid-cols-3 gap-2 mb-4">
          {PERIODOS.map((p) => (
            <button
              key={p.valor}
              onClick={() => setPeriodo(p.valor)}
              className={`rounded-2xl border py-2.5 text-sm font-medium ${periodo === p.valor ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'}`}
            >
              {p.etiqueta}
            </button>
          ))}
        </div>

        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Día de pago (alinea tu quincena)</p>
        <input
          value={diaPago}
          onChange={(e) => setDiaPago(e.target.value.replace(/\D/g, '').slice(0, 2))}
          inputMode="numeric"
          placeholder="Vacío = quincena 1-15 y 16-fin"
          aria-label="Día de pago"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
        />

        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Regla para repartir ingresos</p>
        <div className="grid grid-cols-3 gap-2 mb-1">
          {[['necesidades', 'Fijos'], ['deseos', 'Libre'], ['ahorro', 'Ahorro']].map(([k, et]) => (
            <label key={k} className="text-xs text-ink-soft">
              {et} %
              <input
                value={regla[k]}
                onChange={(e) => cambiarRegla(k, e.target.value)}
                inputMode="numeric"
                aria-label={`Porcentaje ${et}`}
                className="mt-1 w-full rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-sm text-ink outline-none focus:border-accent"
              />
            </label>
          ))}
        </div>
        <p className={`text-xs mb-4 ${Math.abs(suma - 100) > 0.01 ? 'text-danger' : 'text-ink-soft'}`}>Suma: {suma}%</p>

        {presupuestos.length > 0 && (
          <>
            <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Arrastrar el sobrante al siguiente periodo</p>
            <div className="space-y-1.5 mb-4">
              {presupuestos.map((p) => (
                <label key={p.id} className="flex items-center gap-3 rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm">
                  <input type="checkbox" checked={arrastre.includes(p.id)} onChange={() => alternarArrastre(p.id)} />
                  <span className="flex-1">{p.categoria}</span>
                </label>
              ))}
            </div>
          </>
        )}

        {error && <p className="text-sm text-danger mb-3" role="alert">{error}</p>}
        <button
          onClick={guardar}
          disabled={guardando || !cfg}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
        >
          {guardando ? 'Guardando...' : 'Guardar ajustes'}
        </button>
      </div>
    </div>
  )
}
