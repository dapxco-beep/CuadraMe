import { useEffect, useState } from 'react'
import { EsqueletoTarjeta } from '../components/Esqueletos'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Lightbulb } from 'lucide-react'
import { api } from '../lib/api'
import Cuadri from '../brand/Cuadri'
import { estadoPorScore, MENSAJE_POR_ESTADO } from '../lib/saludFinanciera'

const ESCALA = ['critico', 'mal', 'cansado', 'regular', 'bien', 'radiante']
const NOMBRE_ESTADO = { critico: 'Apuros', mal: 'Mal', cansado: 'Cansado', regular: 'Regular', bien: 'Bien', radiante: 'Radiante' }

export default function Ahorcado() {
  const volver = useVolver('/')
  const [reporte, setReporte] = useState(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    api.reporteMensual().then(setReporte).catch(() => {}).finally(() => setCargando(false))
  }, [])

  const estado = reporte ? estadoPorScore(reporte.salud.score) : 'regular'

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 shrink-0 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Cómo está Cuadri</h1>
      </header>

      <p className="mx-6 mt-2 text-xs text-ink-soft">
        Cuadri refleja la salud de tus finanzas: si cuidas tu plata se pone radiante; si te descuidas se ve cansado y apagado.
        Se actualiza solo con tus movimientos reales.
      </p>

      {cargando ? (
        <EsqueletoTarjeta alto={260} className="mx-6 mt-4" etiqueta="Cargando a Cuadri" />
      ) : reporte ? (
        <section className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-6">
          <div className="flex justify-center pop-in py-2">
            <Cuadri estado={estado} size={230} siempre titulo={MENSAJE_POR_ESTADO[estado]} />
          </div>
          <p className="text-center text-base font-semibold mt-3">{MENSAJE_POR_ESTADO[estado]}</p>
          <p className="text-center text-xs text-ink-soft mt-1">
            Salud financiera: {reporte.salud.score}/100 — refleja tu mes en curso
          </p>
          <ol className="mt-4 grid grid-cols-6 gap-1" aria-label="Estados de Cuadri, de peor a mejor">
            {ESCALA.map((e) => (
              <li key={e} className={`flex flex-col items-center rounded-xl py-1.5 ${e === estado ? 'bg-accent-soft ring-1 ring-accent' : 'opacity-60'}`} aria-current={e === estado ? 'true' : undefined}>
                <Cuadri estado={e} size={38} animar={false} siempre />
                <span className="text-[9px] leading-tight mt-0.5 font-medium">{NOMBRE_ESTADO[e]}</span>
              </li>
            ))}
          </ol>
          {reporte.salud.tips?.[0] && (
            <p className="text-xs text-ink-soft flex items-center justify-center gap-1.5 mt-4 pt-4 border-t border-line">
              <Lightbulb size={16} className="shrink-0" /> {reporte.salud.tips[0]}
            </p>
          )}
        </section>
      ) : (
        <div className="mx-6 mt-6 rounded-2xl bg-paper-raised border border-line p-8 text-center">
          <p className="text-sm text-ink-soft">Registra movimientos este mes para ver cómo está Cuadri</p>
        </div>
      )}

      <footer className="flex flex-col items-center gap-1.5 mt-10 mb-2">
        <img src="/icons/icon-192.png" alt="CuadraMe" className="w-8 h-8 rounded-xl" />
        <p className="text-[11px] text-ink-soft">CuadraMe · Hecho por DAPX</p>
      </footer>
    </div>
  )
}
