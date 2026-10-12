import { useEffect, useMemo, useState } from 'react'
import { EsqueletoGrafica, EsqueletoLista } from '../components/Esqueletos'
import { Link, useSearchParams } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { ArrowDownRight, ArrowLeft, ArrowUpRight, ChevronDown, PieChart, Store } from 'lucide-react'
import { EstadoVacio } from '../brand/Marca'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { useCategorias } from '../lib/CategoriasContext'
import { nombreMesLargo, pctTexto, rangoPeriodo } from '../lib/informe'
import { formatVeces } from '../lib/format'
import SelectorPeriodo from '../components/SelectorPeriodo'
import BarraProgreso from '../components/BarraProgreso'
import EnlaceCostos from '../components/EnlaceCostos'

// Colores distintos para la dona (cada segmento también lleva su nombre y % en la
// lista, así que el color nunca es la única señal).
// Colores de la serie: tokens del tema (claro y oscuro) en index.css
const COLORES = [1, 2, 3, 4, 5, 6].map((n) => `var(--c-serie-${n})`)
const MAX_SEGMENTOS = 5

// Segmentos de la dona: las N categorías más grandes y el resto agrupado en "Otras".
export function segmentosDona(categorias, max = MAX_SEGMENTOS) {
  const top = categorias.slice(0, max).map((c) => ({ nombre: c.categoria, monto: c.monto, pct: c.pct }))
  const resto = categorias.slice(max)
  if (resto.length) {
    top.push({
      nombre: 'Otras',
      monto: resto.reduce((s, c) => s + c.monto, 0),
      pct: Math.round(resto.reduce((s, c) => s + c.pct, 0) * 10) / 10,
    })
  }
  return top
}

function Dona({ segmentos, total, fmt }) {
  let acumulado = 0
  return (
    <svg viewBox="0 0 42 42" className="w-28 h-28 min-[400px]:w-36 min-[400px]:h-36 sm:w-40 sm:h-40 shrink-0" role="img" aria-label={`Gasto por categoría, total ${fmt(total)}`}>
      <circle cx="21" cy="21" r="15.9155" fill="none" stroke="var(--color-line)" strokeWidth="5" />
      {segmentos.map((s, i) => {
        const largo = Math.max(s.pct - 0.6, 0.2) // pequeña separación entre segmentos
        const el = (
          <circle
            key={s.nombre}
            cx="21" cy="21" r="15.9155" fill="none"
            stroke={COLORES[i % COLORES.length]} strokeWidth="5"
            strokeDasharray={`${largo} ${100 - largo}`}
            strokeDashoffset={25 - acumulado}
          />
        )
        acumulado += s.pct
        return el
      })}
      <text x="21" y="20" textAnchor="middle" fontSize="3.2" fill="var(--color-ink-soft)" style={{ fontFamily: 'var(--font-sans)' }}>Total</text>
      <text x="21" y="25" textAnchor="middle" fontSize="3.6" fontWeight="700" fill="var(--color-ink)" style={{ fontFamily: 'var(--font-sans)' }}>
        {fmt(total)}
      </text>
    </svg>
  )
}

function Variacion({ pct, anteriorLabel }) {
  if (pct === null || pct === undefined) return <span className="text-[11px] text-ink-soft">sin base para comparar</span>
  const sube = pct > 0
  const Icono = sube ? ArrowUpRight : ArrowDownRight
  return (
    <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${pct === 0 ? 'text-ink-soft' : sube ? 'text-danger' : 'text-cuadra'}`} title={anteriorLabel}>
      {pct !== 0 && <Icono size={16} aria-hidden="true" />}
      {pctTexto(pct)}
    </span>
  )
}

export default function Informe() {
  const volver = useVolver('/')
  const { fmt } = useBloqueo()
  const { iconoDe } = useCategorias()
  const [valor, setValor] = useState({ periodo: 'este_mes', ...rangoPeriodo('este_mes') })
  const [consulta] = useSearchParams()
  const mesPedido = consulta.get('mes')
  // Salto a un mes concreto: desde el estado vacío o desde el enlace del resumen (?mes=2026-09).
  const [mes, setMes] = useState(/^\d{4}-(0[1-9]|1[0-2])$/.test(mesPedido || '') ? mesPedido : null)
  const [informe, setInforme] = useState(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(true)
  const [abierta, setAbierta] = useState(null)
  const [detalles, setDetalles] = useState({})

  const params = useMemo(
    () => (mes
      ? { periodo: 'mes', mes }
      : { periodo: valor.periodo, ...(valor.periodo === 'rango' ? { desde: valor.desde, hasta: valor.hasta } : {}) }),
    [valor, mes]
  )

  useEffect(() => {
    let activo = true
    setCargando(true)
    setError('')
    setAbierta(null)
    setDetalles({})
    api.informeGasto(params)
      .then((d) => activo && setInforme(d))
      .catch((e) => activo && setError(e.message || 'No se pudo cargar el informe. Revisa tu conexión e intenta de nuevo.'))
      .finally(() => activo && setCargando(false))
    return () => {
      activo = false
    }
  }, [params])

  function alternar(cat) {
    if (abierta === cat) return setAbierta(null)
    setAbierta(cat)
    if (!detalles[cat]) {
      api.informeMovimientos({ ...params, categoria: cat })
        .then((d) => setDetalles((p) => ({ ...p, [cat]: d })))
        .catch(() => setDetalles((p) => ({ ...p, [cat]: { error: true, movimientos: [] } })))
    }
  }

  const segmentos = informe?.categorias ? segmentosDona(informe.categorias) : []

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter pantalla-ancha">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">En qué gasto</h1>
      </header>

      <section className="px-6 mt-2">
        <SelectorPeriodo
          valor={mes ? { periodo: 'mes' } : valor}
          onChange={(v) => { setMes(null); setValor(v) }}
        />
      </section>

      <EnlaceCostos className="mx-6 mt-3" />

      {cargando && <div className="mx-6 mt-6 space-y-4"><EsqueletoGrafica alto={160} etiqueta="Cargando tu informe" /><EsqueletoLista filas={4} /></div>}
      {error && <p role="alert" className="mx-6 mt-6 text-sm text-danger text-center">{error}</p>}

      {!cargando && informe && !informe.hay_datos && (
        <EstadoVacio
          icono={PieChart}
          titulo={`No hay gastos en ${informe.etiqueta}`}
          texto="Prueba con otro periodo o revisa un mes en el que sí registraste movimientos."
          className="mx-6 mt-6"
        >
          {informe.ultimo_mes_con_datos && (
            <button
              type="button"
              onClick={() => setMes(informe.ultimo_mes_con_datos)}
              className="mt-4 text-sm text-accent font-semibold min-h-[44px] px-3"
            >
              Ver {nombreMesLargo(informe.ultimo_mes_con_datos)}
            </button>
          )}
        </EstadoVacio>
      )}

      {!cargando && informe?.hay_datos && (
        <div className="dos-grid">
          <section className="mx-6 mt-4 card-marca bg-paper-raised border border-line p-4 lg:col-start-1 lg:row-start-1">
            <p className="t-kicker text-ink-soft capitalize">Gastaste en {informe.etiqueta}</p>
            <p className="text-[32px] t-display mt-1">{fmt(informe.total)}</p>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <Variacion pct={informe.variacion_pct} anteriorLabel={informe.anterior.etiqueta} />
              <span className="text-xs text-ink-soft">
                frente a {informe.anterior.etiqueta} ({fmt(informe.total_anterior)})
              </span>
            </div>
            {informe.ingresos > 0 && (
              <p className="text-xs text-ink-soft mt-2">
                Ingresos {fmt(informe.ingresos)} · {informe.ahorro >= 0 ? 'Te sobró' : 'Te faltó'} {fmt(Math.abs(informe.ahorro))}
              </p>
            )}
          </section>

          <section className="mx-6 mt-4 card-marca bg-paper-raised border border-line p-4 lg:col-start-2 lg:row-start-1 lg:row-span-2">
            <h2 className="text-[15px] font-semibold mb-3">Por categoría</h2>
            <div className="flex items-center gap-4">
              <Dona segmentos={segmentos} total={informe.total} fmt={fmt} />
              <ul className="flex-1 min-w-0 space-y-1.5" aria-label="Leyenda de la dona">
                {segmentos.map((s, i) => (
                  <li key={s.nombre} className="flex items-center gap-2 text-xs">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: COLORES[i % COLORES.length] }} aria-hidden="true" />
                    <span className="flex-1 min-w-0 leading-tight break-words">{s.nombre}</span>
                    <span className="font-semibold shrink-0 whitespace-nowrap">{String(s.pct).replace('.', ',')} %</span>
                  </li>
                ))}
              </ul>
            </div>

            <ul className="mt-4 divide-y divide-line border-t border-line">
              {informe.categorias.map((c) => {
                const det = detalles[c.categoria]
                const abiertaAhora = abierta === c.categoria
                return (
                  <li key={c.categoria}>
                    <button
                      type="button"
                      onClick={() => alternar(c.categoria)}
                      aria-expanded={abiertaAhora}
                      className="w-full text-left py-3 min-h-[56px]"
                    >
                      <div className="flex items-center gap-3">
                        <span className="w-9 h-9 rounded-xl shrink-0 bg-accent-soft flex items-center justify-center text-lg" aria-hidden="true">
                          {iconoDe(c.categoria)}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{c.categoria}</p>
                          <BarraProgreso
                            pct={Math.max(c.pct, 1.5)}
                            label={`Participación de ${c.categoria}`}
                            className="h-1.5 rounded-full bg-line mt-1.5 overflow-hidden"
                            fillClass="rounded-full bg-brand"
                            color="var(--color-brand)"
                          />
                        </div>
                        <div className="text-right shrink-0">
                          <p className="text-sm font-semibold">{fmt(c.monto)}</p>
                          <p className="text-[11px] text-ink-soft">{String(c.pct).replace('.', ',')} % · <Variacion pct={c.variacion_pct} anteriorLabel={`antes ${fmt(c.anterior)}`} /></p>
                        </div>
                        <ChevronDown size={16} className={`text-ink-soft shrink-0 transition-transform ${abiertaAhora ? 'rotate-180' : ''}`} aria-hidden="true" />
                      </div>
                    </button>
                    {abiertaAhora && (
                      <div className="pb-3 pl-12">
                        {!det && <p className="text-xs text-ink-soft py-2">Cargando movimientos...</p>}
                        {det?.error && <p className="text-xs text-danger py-2">No se pudieron cargar los movimientos.</p>}
                        {det && !det.error && (
                          <ul className="space-y-1" aria-label={`Movimientos de ${c.categoria}`}>
                            {det.movimientos.map((m) => (
                              <li key={m.id}>
                                <Link to={`/movimientos/${m.id}`} className="flex items-center justify-between gap-3 py-1.5 text-xs min-h-[44px]">
                                  <span className="min-w-0">
                                    <span className="block font-medium truncate">{m.descripcion}</span>
                                    <span className="text-ink-soft">{m.fecha.slice(0, 10)}</span>
                                  </span>
                                  <span className="font-semibold shrink-0">{fmt(m.monto)}</span>
                                </Link>
                              </li>
                            ))}
                            {det.truncado && <li className="text-[11px] text-ink-soft">Se muestran los {det.movimientos.length} más recientes.</li>}
                          </ul>
                        )}
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          </section>

          {informe.comercios.length > 0 && (
            <section className="mx-6 mt-4 card-marca bg-paper-raised border border-line p-4 lg:col-start-1 lg:row-start-2">
              <div className="flex items-center gap-2 mb-2">
                <Store size={16} className="text-ink-soft" aria-hidden="true" />
                <h2 className="text-[15px] font-semibold">Dónde más gastas</h2>
              </div>
              <ol className="divide-y divide-line">
                {informe.comercios.map((c, i) => (
                  <li key={c.nombre} className="flex items-center gap-3 py-2.5 text-sm">
                    <span className="w-5 text-xs text-ink-soft">{i + 1}</span>
                    <span className="flex-1 min-w-0 truncate">{c.nombre}</span>
                    <span className="text-[11px] text-ink-soft">{formatVeces(c.num)}</span>
                    <span className="font-semibold">{fmt(c.monto)}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>
      )}
    </div>
  )
}
