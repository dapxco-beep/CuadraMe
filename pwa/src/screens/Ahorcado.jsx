import { useEffect, useState } from 'react'
import { EsqueletoTarjeta } from '../components/Esqueletos'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Lightbulb } from 'lucide-react'
import { api } from '../lib/api'
import ArbolFinanciero from '../components/ArbolFinanciero'
import { etapaPorScore, MENSAJE_POR_ETAPA } from '../lib/saludFinanciera'

export default function Ahorcado() {
  const volver = useVolver('/')
  const [reporte, setReporte] = useState(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    api.reporteMensual().then(setReporte).catch(() => {}).finally(() => setCargando(false))
  }, [])

  const etapa = reporte ? etapaPorScore(reporte.salud.score) : 0

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Tu árbol financiero</h1>
      </header>

      <p className="mx-6 mt-2 text-xs text-ink-soft">
        Un medidor visual de cómo va tu mes: entre mejor vayan tus finanzas, más crece y florece.
        Se actualiza solo con tus movimientos reales, no hay que jugar nada.
      </p>

      {cargando ? (
        <EsqueletoTarjeta alto={260} className="mx-6 mt-4" etiqueta="Cargando tu árbol" />
      ) : reporte ? (
        <section className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-6">
          <div className="w-full aspect-square max-w-[260px] mx-auto pop-in">
            <ArbolFinanciero etapa={etapa} />
          </div>
          <p className="text-center text-base font-semibold mt-3">{MENSAJE_POR_ETAPA[etapa]}</p>
          <p className="text-center text-xs text-ink-soft mt-1">
            Salud financiera: {reporte.salud.score}/100 — refleja tu mes en curso
          </p>
          {reporte.salud.tips?.[0] && (
            <p className="text-xs text-ink-soft flex items-center justify-center gap-1.5 mt-4 pt-4 border-t border-line">
              <Lightbulb size={13} className="shrink-0" /> {reporte.salud.tips[0]}
            </p>
          )}
        </section>
      ) : (
        <div className="mx-6 mt-6 rounded-2xl bg-paper-raised border border-line p-8 text-center">
          <p className="text-sm text-ink-soft">Registra movimientos este mes para ver tu árbol</p>
        </div>
      )}

      <footer className="flex flex-col items-center gap-1.5 mt-10 mb-2">
        <img src="/icons/icon-192.png" alt="CuadraMe" className="w-8 h-8 rounded-xl" />
        <p className="text-[11px] text-ink-soft">CuadraMe · Hecho por DAPX</p>
      </footer>
    </div>
  )
}
