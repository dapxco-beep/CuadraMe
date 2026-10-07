import { useEffect, useState } from 'react'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Lightbulb, TrendingUp } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP, formatPorcentaje } from '../lib/format'
import { useDialogos } from '../lib/DialogosContext'

function mesAnterior() {
  const d = new Date()
  d.setDate(1)
  d.setMonth(d.getMonth() - 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function Fila({ etiqueta, valor, fuerte }) {
  return (
    <div className="flex items-center justify-between py-2.5">
      <span className="text-sm text-ink-soft">{etiqueta}</span>
      <span className={`text-sm ${fuerte ? 'font-bold' : 'font-medium'}`}>{valor}</span>
    </div>
  )
}

export default function CierreMes() {
  const volver = useVolver('/')
  const { avisar } = useDialogos()
  const [lista, setLista] = useState(null)
  const [mes, setMes] = useState(null)
  const [informe, setInforme] = useState(null)
  const [correo, setCorreo] = useState(false)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  useEffect(() => {
    api.cierrePreferencias().then((p) => setCorreo(!!p.correo)).catch(() => {})
    api
      .cierresMes()
      .then((l) => {
        setLista(l)
        setMes(l[0]?.mes || mesAnterior())
      })
      .catch((e) => setError(e.message || 'No se pudo cargar'))
  }, [])

  useEffect(() => {
    if (!mes) return
    setInforme(null)
    setError('')
    api.cierreMes(mes).then(setInforme).catch(() => setInforme(false))
  }, [mes])

  async function generar() {
    setCargando(true)
    try {
      setInforme(await api.generarCierreMes(mes))
    } catch (e) {
      setError(e.message || 'No se pudo generar')
    } finally {
      setCargando(false)
    }
  }

  async function alternarCorreo() {
    const nuevo = !correo
    setCorreo(nuevo)
    try {
      await api.guardarCierrePreferencias(nuevo)
    } catch {
      setCorreo(!nuevo)
      avisar('No se pudo guardar')
    }
  }

  const meses = [...new Set([...(lista || []).map((l) => l.mes), mesAnterior()])].sort().reverse()

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Volver">
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-xl font-semibold flex-1">Cierre de mes</h1>
        {mes && (
          <select aria-label="Mes" value={mes} onChange={(e) => setMes(e.target.value)} className="rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm">
            {meses.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        )}
      </header>

      <div className="px-5 mt-3">
        {error && <p className="text-sm text-danger mb-3">{error}</p>}

        {informe === false && (
          <div className="rounded-2xl bg-paper-raised border border-line p-5 text-center">
            <p className="text-sm text-ink-soft mb-3">Aún no hay cierre de {mes}. Se genera solo cada mes; también puedes crearlo ahora.</p>
            <button onClick={generar} disabled={cargando} className="bg-ink text-paper rounded-2xl px-5 py-3 text-sm font-semibold disabled:opacity-60">
              {cargando ? 'Generando...' : 'Generar cierre'}
            </button>
          </div>
        )}

        {informe && (
          <>
            <div className="rounded-2xl bg-paper-raised border border-line p-4">
              <p className="text-xs text-ink-soft">{informe.titulo}</p>
              <p className="text-sm mt-1">{informe.resumen_corto}</p>
              <div className="divide-y divide-line mt-2">
                <Fila etiqueta="Ingresos" valor={formatCOP(informe.ingresos)} />
                <Fila etiqueta="Gastos" valor={formatCOP(informe.gastos)} />
                <Fila etiqueta={`Ahorro (${formatPorcentaje(informe.tasa_ahorro)})`} valor={formatCOP(informe.ahorro)} fuerte />
                {informe.intereses_pagados > 0 && <Fila etiqueta="Intereses pagados" valor={formatCOP(informe.intereses_pagados)} />}
                {informe.patrimonio && informe.patrimonio.variacion !== null && (
                  <Fila etiqueta="Patrimonio del mes" valor={`${informe.patrimonio.variacion >= 0 ? '+' : '-'}${formatCOP(Math.abs(informe.patrimonio.variacion))}`} />
                )}
              </div>
              <p className="text-[11px] text-ink-soft mt-2">No incluye pagos de tarjeta ni traslados entre tus cuentas, para no contar dos veces.</p>
            </div>

            {informe.categoria_que_mas_subio && (
              <div className="rounded-2xl bg-paper-raised border border-line p-4 mt-3 flex gap-3">
                <TrendingUp size={18} className="text-danger shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">Lo que más subió: {informe.categoria_que_mas_subio.categoria}</p>
                  <p className="text-xs text-ink-soft">
                    {formatCOP(informe.categoria_que_mas_subio.monto_anterior)} → {formatCOP(informe.categoria_que_mas_subio.monto)}
                  </p>
                </div>
              </div>
            )}

            <div className="rounded-2xl bg-accent-soft p-4 mt-3">
              <p className="text-sm font-semibold flex items-center gap-2 mb-2"><Lightbulb size={16} className="text-accent" /> Para el próximo mes</p>
              <ul className="space-y-1.5 text-sm list-disc pl-5">
                {informe.acciones.map((a) => <li key={a}>{a}</li>)}
              </ul>
            </div>
          </>
        )}

        <label className="flex items-start gap-2 text-xs mt-6">
          <input type="checkbox" checked={correo} onChange={alternarCorreo} className="w-4 h-4 mt-0.5 accent-accent" />
          <span>Enviarme también el cierre por correo (por defecto solo recibes una notificación en la app)</span>
        </label>
      </div>
    </div>
  )
}
