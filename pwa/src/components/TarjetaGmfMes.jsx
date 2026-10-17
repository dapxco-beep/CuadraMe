import { useEffect, useState } from 'react'
import { Info, TriangleAlert } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOPFijo as formatCOP } from '../lib/format'
import BarraProgreso from './BarraProgreso'
import Ayudita from './Ayudita'
import Icono from './Icono'

/** «4x1000 este mes»: lo que ya te cobraron y qué tan cerca estás del tope exento de tu cuenta marcada. */
export default function TarjetaGmfMes() {
  const [g, setG] = useState(null)

  useEffect(() => {
    let activo = true
    Promise.resolve()
      .then(() => api.gmfEstimado())
      .then((d) => activo && setG(d))
      .catch(() => {})
    return () => {
      activo = false
    }
  }, [])

  if (!g) return null
  const medido = g.tiene_cuenta_exenta ? g.debitos_cuenta_exenta : g.debitos_total

  return (
    <section className="px-5 mt-5" aria-label="4x1000 este mes" data-testid="tarjeta-gmf-mes">
      <h2 className="text-[15px] font-semibold mb-1 inline-flex items-center">
        4x1000 este mes <Ayudita termino="4x1000" />
      </h2>
      <div className="rounded-2xl bg-paper-raised border border-line p-4">
        <p className="text-xs text-ink-soft">Ya te cobraron</p>
        <p className="text-2xl font-bold">{formatCOP(g.gmf_pagado)}</p>

        <p className="text-xs text-ink-soft mt-3">
          {g.tiene_cuenta_exenta ? 'Lo que ha salido de tu cuenta exenta' : 'Lo que ha salido de tus cuentas de ahorro'}
          {' '}(tope sin cobro: {formatCOP(g.tope_exento_mensual)} al mes)
        </p>
        <BarraProgreso
          pct={g.uso_pct}
          color={g.alerta ? 'var(--color-gold)' : 'var(--color-accent-2)'}
          label={`Uso del tope exento: ${g.uso_pct} %`}
          texto={`${g.uso_pct} % del tope`}
          className="h-2 rounded-full bg-line overflow-hidden mt-1.5"
        />
        <p className="text-xs mt-1">{formatCOP(medido)} ({String(g.uso_pct).replace('.', ',')} %)</p>

        {g.alerta && (
          <p role="status" className="mt-3 rounded-xl bg-accent-soft p-3 text-sm font-medium flex items-start gap-2">
            <Icono icono={TriangleAlert} tam="sm" className="text-accent mt-0.5" /> {g.mensaje}
          </p>
        )}
        {!g.tiene_cuenta_exenta && (
          <p className="mt-3 text-xs text-ink-soft flex items-start gap-2">
            <Icono icono={Info} tam="sm" className="mt-0.5" /> Aún no marcas tu cuenta exenta aquí abajo: así podemos avisarte cuando te acerques al tope.
          </p>
        )}
        <ul className="list-disc pl-4 mt-3 space-y-0.5 text-[11px] text-ink-soft">
          {g.recordatorio.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
        <p className="text-[11px] text-ink-soft mt-2">{g.nota} Orientación educativa, no es asesoría tributaria.</p>
      </div>
    </section>
  )
}
