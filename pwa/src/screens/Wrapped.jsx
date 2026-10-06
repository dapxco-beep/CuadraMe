import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, ChevronLeft, ChevronRight, PieChart, Share2 } from 'lucide-react'
import { nombreMesLargo } from '../lib/informe'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { useDialogos } from '../lib/DialogosContext'
import { Isotipo } from '../brand/Marca'
import { esCampoDeTexto } from '../lib/atajos'
import BarraProgreso from '../components/BarraProgreso'
import { compartirImagen, construirDiapositivas, nombreMes } from '../lib/wrappedImagen'

// Desglose del mes por categoría: la diapositiva solo cuenta cuánto gastaste, esto dice en qué.
function DetalleCategorias({ datos, fmt, onVerInforme }) {
  const lista = datos.categorias || []
  if (lista.length === 0) return null
  const mayor = Math.max(...lista.map((c) => c.monto), 1)
  return (
    <section className="mx-6 mb-6 card-marca bg-paper-raised border border-line p-4" aria-label="Gasto por categoría">
      <h2 className="text-[15px] font-bold">En qué gastaste en {nombreMesLargo(datos.mes)}</h2>
      <p className="text-xs text-ink-soft mt-0.5">Total: {fmt(datos.gasto_total)}</p>
      <ul className="mt-3 space-y-3">
        {lista.map((c) => {
          const sube = c.variacion_pct !== null && c.variacion_pct > 0
          return (
            <li key={c.categoria}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="font-medium truncate">{c.categoria}</span>
                <span className="font-semibold shrink-0">{fmt(c.monto)}</span>
              </div>
              <BarraProgreso
                pct={Math.max(3, (c.monto / mayor) * 100)}
                label={`Gasto en ${c.categoria}`}
                className="mt-1 h-2 rounded-full bg-line overflow-hidden"
              />
              <p className="mt-1 text-xs text-ink-soft">
                {c.pct}% del gasto
                {c.variacion_pct === null
                  ? ' · sin gasto el mes anterior'
                  : ` · ${sube ? '↑' : c.variacion_pct < 0 ? '↓' : '='} ${Math.abs(c.variacion_pct)}% frente al mes anterior`}
              </p>
            </li>
          )
        })}
      </ul>
      <button type="button" onClick={onVerInforme}
        className="mt-4 w-full min-h-[44px] rounded-2xl border border-line text-sm font-semibold text-accent flex items-center justify-center gap-2">
        <PieChart size={16} /> Ver informe completo de este mes
      </button>
    </section>
  )
}

function mesRelativo(delta) {
  const h = new Date()
  const f = new Date(h.getFullYear(), h.getMonth() + delta, 1)
  return `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, '0')}`
}

export default function Wrapped() {
  const navigate = useNavigate()
  const volver = useVolver('/')
  const { fmt } = useBloqueo()
  const { avisar } = useDialogos()
  const [mes, setMes] = useState(null) // se decide al saber qué meses tienen datos
  const [meses, setMeses] = useState([]) // claves AAAA-MM con movimientos
  const [ultimo, setUltimo] = useState(null)
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [i, setI] = useState(0)
  const [dir, setDir] = useState(1)
  const [compartiendo, setCompartiendo] = useState(false)

  // Meses con movimientos: por defecto el actual si tiene datos; si no, el último que sí.
  useEffect(() => {
    let activo = true
    api.informeMeses()
      .then((r) => {
        if (!activo) return
        const claves = (r?.meses ?? []).map((m) => m.mes)
        setMeses(claves)
        setUltimo(r?.ultimo_con_datos ?? null)
        const actual = mesRelativo(0)
        setMes(claves.includes(actual) || !r?.ultimo_con_datos ? actual : r.ultimo_con_datos)
      })
      .catch(() => activo && setMes(mesRelativo(0)))
    return () => {
      activo = false
    }
  }, [])

  useEffect(() => {
    if (!mes) return undefined
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

  const diapos = datos && datos.num_movimientos > 0 ? construirDiapositivas(datos, fmt) : []

  // Lista del selector: meses con datos + el actual, ordenados.
  const opciones = [...new Set([...meses, mesRelativo(0), ...(mes ? [mes] : [])])].sort()
  const indice = opciones.indexOf(mes)
  const hayAnterior = indice > 0
  const haySiguiente = indice >= 0 && indice < opciones.length - 1

  function ir(n) {
    if (n < 0 || n >= diapos.length) return
    setDir(n > i ? 1 : -1)
    setI(n)
  }

  async function compartir() {
    setCompartiendo(true)
    try {
      const r = await compartirImagen(datos, fmt)
      if (r === 'descargado') avisar('Se descargó la imagen de tu resumen.')
    } catch (err) {
      avisar(err.message || 'No se pudo compartir')
    } finally {
      setCompartiendo(false)
    }
  }

  const d = diapos[i]

  // Flechas ← → cambian de diapositiva con el teclado (no cuando se está en un campo o lista,
  // donde las flechas ya significan otra cosa, ni con una hoja abierta).
  useEffect(() => {
    function alTeclear(e) {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
      if (esCampoDeTexto(e.target) || document.querySelector('[role="dialog"][aria-modal="true"]')) return
      e.preventDefault()
      ir(e.key === 'ArrowRight' ? i + 1 : i - 1)
    }
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  })

  return (
    <div className="flex-1 flex flex-col overflow-y-auto screen-enter pantalla-ancha">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold flex-1">Tu resumen</h1>
            </header>

      {mes && (
        <div className="px-6 pb-1 flex items-center gap-2" role="group" aria-label="Mes del resumen">
          <button type="button" aria-label="Mes anterior" disabled={!hayAnterior} onClick={() => setMes(opciones[indice - 1])}
            className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center disabled:opacity-40">
            <ChevronLeft size={16} />
          </button>
          <select value={mes} onChange={(e) => setMes(e.target.value)} aria-label="Elegir mes"
            className="flex-1 min-h-[40px] rounded-full border border-line bg-paper-raised px-4 text-sm font-semibold text-center capitalize">
            {opciones.map((m) => (
              <option key={m} value={m}>{nombreMesLargo(m)}{meses.includes(m) ? '' : ' (sin datos)'}</option>
            ))}
          </select>
          <button type="button" aria-label="Mes siguiente" disabled={!haySiguiente} onClick={() => setMes(opciones[indice + 1])}
            className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center disabled:opacity-40">
            <ChevronRight size={16} />
          </button>
        </div>
      )}

      {datos && datos.num_movimientos === 0 && (
        <div className="mx-6 mt-8 text-center">
          <p className="text-sm font-semibold">No hay movimientos en {nombreMesLargo(mes)}</p>
          <p className="text-xs text-ink-soft mt-1">Elige otro mes con las flechas o la lista.</p>
          {ultimo && ultimo !== mes && (
            <button type="button" onClick={() => setMes(ultimo)} className="mt-3 text-sm text-accent font-semibold min-h-[44px] px-3">
              Ver {nombreMesLargo(ultimo)}
            </button>
          )}
        </div>
      )}

      {error && <p role="alert" className="mx-6 mt-6 text-sm text-danger text-center">{error}</p>}
      {mes && !datos && !error && <p className="text-sm text-ink-soft text-center mt-10">Cargando...</p>}

      {d && (
        <div className="dos-col dos-col-6-5">
          <div className="col">
          {/* Los toques en el tercio izquierdo/derecho cambian de diapositiva, como en las historias */}
          <div className="relative flex-1 mx-6 mt-3 mb-3 overflow-hidden bg-[#17140f] text-[#f5f1e8] min-h-[360px] lg:min-h-[520px] card-marca"
            style={{
              backgroundImage:
                'linear-gradient(to right, rgb(255 255 255 / 0.045) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / 0.045) 1px, transparent 1px)',
              backgroundSize: '27px 27px',
            }}
          >
            <div className="absolute top-3 inset-x-4 flex gap-1.5 z-10" aria-hidden="true">
              {diapos.map((s, n) => (
                <span key={s.id} className="flex-1 h-1 rounded-full bg-white/20 overflow-hidden">
                  <span className="block h-full w-full bg-[#e8823f] barra-fill" style={{ transform: `scaleX(${n <= i ? 1 : 0})` }} />
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
            <div className="absolute bottom-4 inset-x-0 flex items-center justify-center gap-1.5 text-[#b9b19e]" aria-hidden="true">
              <Isotipo size={18} />
              <span className="wordmark text-[13px]">Cuadra<b style={{ color: '#e8823f' }}>Me</b></span>
            </div>
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
          </div>

          <div className="col">
          <DetalleCategorias datos={datos} fmt={fmt} onVerInforme={() => navigate(`/informe?mes=${datos.mes}`)} />
          </div>
        </div>
      )}
    </div>
  )
}
