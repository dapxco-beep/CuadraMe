import { useMemo, useState } from 'react'
import { abreviarEje } from '../lib/graficos'
import { pctTexto } from '../lib/informe'
import { useEvolucionCategorias } from '../lib/useEvolucionCategorias'
import { useCategorias } from '../lib/CategoriasContext'

// «Historial por categoría»: TODAS las categorías en una tabla, mes a mes (6 o 12 meses), con el total y el promedio.
// La primera columna queda fija al desplazar de lado; el mes en curso va atenuado y marcado. Cifras del servidor.
export default function HistorialCategorias({ fmt, className = '' }) {
  const { iconoDe } = useCategorias()
  const [nMeses, setNMeses] = useState(6)
  const [verTodas, setVerTodas] = useState(false)
  const { datos, cargando, error } = useEvolucionCategorias(nMeses, null)

  const filas = useMemo(() => datos?.categorias || [], [datos])
  const visibles = verTodas ? filas : filas.slice(0, 8)
  const maxCelda = useMemo(() => Math.max(1, ...filas.flatMap((c) => c.valores)), [filas])

  if (error) return null
  if (cargando && !datos) {
    return (
      <section className={`card-marca bg-paper-raised border border-line p-4 ${className}`} aria-busy="true">
        <h2 className="text-sm font-semibold">Historial por categoría</h2>
        <p className="text-xs text-ink-soft mt-2">Cargando…</p>
      </section>
    )
  }
  if (!datos?.hay_datos) return null

  return (
    <section id="historial-categorias" className={`card-marca bg-paper-raised border border-line p-4 ${className}`} aria-label="Historial por categoría">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1 basis-48">
          <h2 className="text-[15px] font-semibold">Historial por categoría</h2>
          <p className="text-[11px] text-ink-soft mt-0.5">Cuánto gastaste en cada una, mes a mes. Desliza de lado para ver todos los meses.</p>
        </div>
        <div role="group" aria-label="Meses del historial" className="flex rounded-full bg-paper border border-line p-0.5 shrink-0">
          {[6, 12].map((n) => (
            <button key={n} type="button" aria-pressed={nMeses === n} onClick={() => setNMeses(n)}
              className={`px-3 min-h-[32px] rounded-full text-xs font-semibold ${nMeses === n ? 'bg-accent text-paper-raised' : 'text-ink-soft'}`}>{n} meses</button>
          ))}
        </div>
      </div>

      <div className="mt-3 -mx-4 overflow-x-auto" tabIndex={0} role="region" aria-label="Tabla del historial por categoría">
        <table className="text-xs border-separate border-spacing-0 min-w-full">
          <thead>
            <tr>
              <th scope="col" className="sticky left-0 z-10 bg-paper-raised text-left font-semibold text-ink-soft px-4 py-2 min-w-[8.5rem] border-b border-line">Categoría</th>
              {datos.meses.map((m) => (
                <th key={m.mes} scope="col" className={`text-right font-semibold px-2 py-2 whitespace-nowrap border-b border-line ${m.parcial ? 'text-ink-soft/70' : 'text-ink-soft'}`}>
                  {m.etiqueta}{m.parcial ? '*' : ''}
                </th>
              ))}
              <th scope="col" className="text-right font-semibold text-ink px-3 py-2 whitespace-nowrap border-b border-line">Total</th>
              <th scope="col" className="text-right font-semibold text-ink-soft pl-2 pr-4 py-2 whitespace-nowrap border-b border-line">Promedio</th>
            </tr>
          </thead>
          <tbody>
            {visibles.map((c) => (
              <tr key={c.categoria}>
                <th scope="row" className="sticky left-0 z-10 bg-paper-raised text-left font-medium px-4 py-2 border-b border-line">
                  <span className="flex items-center gap-2 min-w-0">
                    <span aria-hidden="true">{iconoDe(c.categoria)}</span>
                    <span className="truncate max-w-[7rem]">{c.categoria}</span>
                  </span>
                </th>
                {c.valores.map((v, i) => {
                  const parcial = datos.meses[i].parcial
                  return (
                    <td key={datos.meses[i].mes} className={`text-right px-2 py-2 whitespace-nowrap border-b border-line tabular-nums ${parcial ? 'opacity-60' : ''}`}
                      style={v > 0 ? { background: `color-mix(in srgb, var(--color-brand) ${Math.round(6 + (v / maxCelda) * 26)}%, transparent)` } : undefined}
                      title={`${datos.meses[i].etiqueta_larga}${parcial ? ' (en curso)' : ''}: ${fmt(v)}`}>
                      {v > 0 ? abreviarEje(v) : <span className="text-ink-soft/60" aria-label="sin gasto">·</span>}
                    </td>
                  )
                })}
                <td className="text-right font-semibold px-3 py-2 whitespace-nowrap border-b border-line tabular-nums">{fmt(c.total)}</td>
                <td className="text-right text-ink-soft pl-2 pr-4 py-2 whitespace-nowrap border-b border-line tabular-nums">{fmt(c.promedio)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="sticky left-0 z-10 bg-paper-raised text-left font-semibold px-4 py-2">Todo</th>
              {datos.total_mensual.map((v, i) => (
                <td key={datos.meses[i].mes} className={`text-right font-semibold px-2 py-2 whitespace-nowrap tabular-nums ${datos.meses[i].parcial ? 'opacity-60' : ''}`}>{abreviarEje(v)}</td>
              ))}
              <td className="text-right font-bold px-3 py-2 whitespace-nowrap tabular-nums">{fmt(datos.serie_total.total)}</td>
              <td className="text-right text-ink-soft pl-2 pr-4 py-2 whitespace-nowrap tabular-nums">{fmt(datos.serie_total.promedio)}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="flex items-center justify-between gap-3 mt-2">
        <p className="text-[11px] text-ink-soft">* mes en curso; no cuenta en el promedio.</p>
        {filas.length > 8 && (
          <button type="button" onClick={() => setVerTodas((v) => !v)} aria-expanded={verTodas}
            className="text-xs font-semibold text-accent min-h-[44px] px-3 shrink-0">
            {verTodas ? 'Ver menos' : `Ver las ${filas.length} categorías`}
          </button>
        )}
      </div>
      {datos.serie_total.resumen && datos.serie_total.resumen.vs_promedio_pct != null && (
        <p className="sr-only">Último mes completo: {fmt(datos.serie_total.resumen.valor)}, {pctTexto(datos.serie_total.resumen.vs_promedio_pct)} frente al promedio.</p>
      )}
    </section>
  )
}
