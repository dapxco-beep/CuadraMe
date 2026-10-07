import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { bandejaAbierta, debePreguntarMovimiento, ocultarPreguntaHoy, preguntaOcultaHoy } from '../lib/bandeja'

/**
 * Pregunta discreta en Inicio: "¿Hiciste algún movimiento?". Sale si hoy no hay
 * movimientos o pasaron varias horas desde el último, y espera a que la bandeja
 * de "por confirmar" se cierre. "No hice ninguno" la oculta hasta mañana.
 */
export default function PreguntaMovimiento({ ultimaFecha }) {
  const navigate = useNavigate()
  const [oculta, setOculta] = useState(() => preguntaOcultaHoy())
  const [bandeja, setBandeja] = useState(() => bandejaAbierta())

  useEffect(() => {
    const alCambiar = (e) => setBandeja(!!e.detail?.abierta)
    window.addEventListener('cuadrame:bandeja', alCambiar)
    return () => window.removeEventListener('cuadrame:bandeja', alCambiar)
  }, [])

  if (bandeja || !debePreguntarMovimiento({ ultimaFecha, oculta })) return null

  function ninguno() {
    ocultarPreguntaHoy()
    setOculta(true)
  }

  return (
    <section
      className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line px-4 py-3.5 stagger-item"
      style={{ '--stagger-i': 1 }}
      aria-label="¿Hiciste algún movimiento?"
      data-testid="pregunta-movimiento"
    >
      <p className="text-sm font-semibold">¿Hiciste algún movimiento?</p>
      <p className="text-xs text-ink-soft mt-0.5">Anótalo ahora y tu fin de mes cuadra con la realidad.</p>
      <div className="flex gap-2 mt-3">
        <button
          onClick={() => navigate('/agregar?foco=monto')}
          className="flex-1 flex items-center justify-center gap-1.5 bg-accent text-white font-semibold rounded-xl py-2.5 text-sm"
        >
          <Plus size={16} /> Registrar gasto
        </button>
        <button onClick={ninguno} className="flex-1 rounded-xl border border-line text-ink-soft font-medium py-2.5 text-sm">
          No hice ninguno
        </button>
      </div>
    </section>
  )
}
