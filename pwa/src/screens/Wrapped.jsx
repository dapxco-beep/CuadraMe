import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, ChevronLeft, ChevronRight, Share2 } from 'lucide-react'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { useDialogos } from '../lib/DialogosContext'
import { compartirImagen, construirDiapositivas, nombreMes } from '../lib/wrappedImagen'

function mesRelativo(delta) {
  const h = new Date()
  const f = new Date(h.getFullYear(), h.getMonth() + delta, 1)
  return `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, '0')}`
}

export default function Wrapped() {
  const navigate = useNavigate()
  const { fmt } = useBloqueo()
  const { avisar } = useDialogos()
  const [mes, setMes] = useState(mesRelativo(0))
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [i, setI] = useState(0)
  const [dir, setDir] = useState(1)
  const [compartiendo, setCompartiendo] = useState(false)

  useEffect(() => {
    let activo = true
    setDatos(null)
    setError('')
    setI(0)
    api.wrapped(mes)
      .then((d) => activo && setDatos(d))
      .catch((e) => activo && setError(e.message || 'No se pudo cargar tu resumen'))
    return () => {
      activo = false
    }
  }, [mes])

  const diapos = datos ? construirDiapositivas(datos, fmt) : []

  function ir(n) {
    if (n < 0 || n >= diapos.length) return
    setDir(n > i ? 1 : -1)
    setI(n)
  }

  async function compartir() {
    setCompartiendo(true)
    try {
      const r = await compartirImagen(datos)
      if (r === 'descargado') avisar('Se descargó la imagen de tu resumen.')
    } catch (err) {
      avisar(err.message || 'No se pudo compartir')
    } finally {
      setCompartiendo(false)
    }
  }

  const d = diapos[i]

  return (
    <div className="flex-1 flex flex-col overflow-hidden screen-enter">
      <header className="px-6 pt-14 pb-2 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="w-9 h-9 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold flex-1">Tu resumen</h1>
        <div className="flex gap-1.5" role="group" aria-label="Mes del resumen">
          {[0, -1].map((delta) => (
            <button
              key={delta}
              type="button"
              aria-pressed={mes === mesRelativo(delta)}
              onClick={() => setMes(mesRelativo(delta))}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border ${
                mes === mesRelativo(delta) ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
              }`}
            >
              {delta === 0 ? 'Este mes' : 'Mes pasado'}
            </button>
          ))}
        </div>
      </header>

      {error && <p role="alert" className="mx-6 mt-6 text-sm text-danger text-center">{error}</p>}
      {!datos && !error && <p className="text-sm text-ink-soft text-center mt-10">Cargando...</p>}

      {d && (
        <>
          {/* Los toques en el tercio izquierdo/derecho cambian de diapositiva, como en las historias */}
          <div className="relative flex-1 mx-6 mt-3 mb-3 rounded-[28px] overflow-hidden bg-[#17140f] text-[#f5f1e8] min-h-[360px]">
            <div className="absolute top-3 inset-x-4 flex gap-1.5 z-10" aria-hidden="true">
              {diapos.map((s, n) => (
                <span key={s.id} className="flex-1 h-1 rounded-full bg-white/20 overflow-hidden">
                  <span className="block h-full bg-[#e8823f] transition-all duration-300" style={{ width: n <= i ? '100%' : '0%' }} />
                </span>
              ))}
            </div>
            <button type="button" aria-label="Anterior" onClick={() => ir(i - 1)} className="absolute inset-y-0 left-0 w-1/3 z-10" />
            <button type="button" aria-label="Siguiente" onClick={() => ir(i + 1)} className="absolute inset-y-0 right-0 w-1/3 z-10" />

            <AnimatePresence mode="wait" custom={dir}>
              <motion.div
                key={d.id}
                custom={dir}
                initial={{ opacity: 0, x: dir * 40 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: dir * -40 }}
                transition={{ duration: 0.22 }}
                className="absolute inset-0 flex flex-col items-center justify-center text-center px-8"
                aria-live="polite"
              >
                <span className="text-6xl mb-5" aria-hidden="true">{d.emoji}</span>
                <p className="text-sm text-[#a39c8a]">{d.titulo}</p>
                <p className="text-4xl font-extrabold mt-2 break-words max-w-full">{d.valor}</p>
                <p className="text-sm text-[#a39c8a] mt-3">{d.detalle}</p>
              </motion.div>
            </AnimatePresence>
          </div>

          <div className="px-6 pb-4 flex items-center gap-3">
            <button type="button" onClick={() => ir(i - 1)} disabled={i === 0} aria-label="Diapositiva anterior"
              className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center disabled:opacity-40">
              <ChevronLeft size={18} />
            </button>
            <button
              type="button"
              onClick={compartir}
              disabled={compartiendo}
              className="flex-1 bg-ink text-paper font-semibold rounded-2xl py-3.5 text-[15px] flex items-center justify-center gap-2 disabled:opacity-60"
            >
              <Share2 size={16} /> {compartiendo ? 'Preparando...' : `Compartir mi ${nombreMes(datos.mes)}`}
            </button>
            <button type="button" onClick={() => ir(i + 1)} disabled={i === diapos.length - 1} aria-label="Diapositiva siguiente"
              className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center disabled:opacity-40">
              <ChevronRight size={18} />
            </button>
          </div>
        </>
      )}
    </div>
  )
}
