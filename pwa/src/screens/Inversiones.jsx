import { aFecha } from '../lib/fechaLocal'
import { textoError } from '../lib/textoError'
import { useEffect, useState } from 'react'
import { ChevronDown, CircleHelp, Plus, RefreshCw, TrendingUp, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP, formatMoneda } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import {
  AVISO_EDUCATIVO, BROKERS_SUGERIDOS, EJEMPLO_CSV, ETIQUETA_TIPO, GLOSARIO, TIPOS_BROKER, TIPOS_POSICION,
  colorSigno, hayConcentracion, pctTexto, serieEvolucion, textoEstadoPrecio,
} from '../lib/inversiones'
import { puntosSerie, trazoLinea } from '../lib/patrimonio'
import DonaDistribucion from '../components/DonaDistribucion'
import GraficoPatrimonio from '../components/GraficoPatrimonio'
import Hoja from '../components/Hoja'
import InputMonto from '../components/InputMonto'
import { EsqueletoTarjeta } from '../components/Esqueletos'
import VerMas from '../components/VerMas'
import EnlacesRelacionados from '../components/EnlacesRelacionados'

const MONEDAS = ['COP', 'USD', 'EUR', 'MXN', 'CLP', 'BRL', 'ARS', 'PEN']
const clsInput = 'w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent'

function Campo({ etiqueta, children }) {
  return (
    <label className="block mb-3">
      <span className="text-xs text-ink-soft">{etiqueta}</span>
      <div className="mt-1">{children}</div>
    </label>
  )
}

const soloNumero = (v) => v.replace(/[^0-9.]/g, '')

export default function Inversiones() {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [hoja, setHoja] = useState(null) // { tipo: 'broker'|'posicion'|'csv'|'detalle'|'glosario', ... }
  const [mensaje, setMensaje] = useState('')
  const [actualizando, setActualizando] = useState(false)
  const [opciones, setOpciones] = useState({ resumen_semanal: false })

  async function cargar() {
    setError('')
    try {
      setDatos(await api.inversiones())
      api.opcionesInversiones?.().then((o) => o && setOpciones(o)).catch(() => {})
    } catch (e) {
      setError(textoError(e, 'cargar tus inversiones'))
    }
  }
  useEffect(() => { cargar() }, [])

  async function actualizarAhora() {
    setActualizando(true)
    setMensaje('')
    try {
      const r = await api.actualizarPreciosInversiones()
      setMensaje(r.mensaje || 'Precios al día.')
      await cargar()
    } catch (e) {
      setMensaje(e.message || 'No se pudo actualizar ahora. Inténtalo más tarde.')
    }
    setActualizando(false)
  }

  async function alternarSemanal() {
    const nuevo = !opciones.resumen_semanal
    setOpciones({ resumen_semanal: nuevo })
    try { await api.guardarOpcionesInversiones({ resumen_semanal: nuevo }) } catch { setOpciones({ resumen_semanal: !nuevo }) }
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter pantalla-ancha">
      <header className="px-5 pantalla-top pb-2 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Inversiones</h1>
        <div className="flex gap-2">
          <button onClick={() => setHoja({ tipo: 'glosario' })} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="¿Qué significan estos términos?">
            <CircleHelp size={20} />
          </button>
          <button onClick={() => setHoja({ tipo: 'posicion' })} className="w-11 h-11 rounded-full bg-accent text-paper-raised flex items-center justify-center" aria-label="Agregar inversión">
            <Plus size={20} />
          </button>
        </div>
      </header>
      <p className="mx-5 text-xs text-ink-soft">{AVISO_EDUCATIVO}</p>

      {!datos && !error && <div className="mx-5 mt-3"><EsqueletoTarjeta alto={128} etiqueta="Cargando tus inversiones" /></div>}
      {error && !datos && (
        <div className="mx-5 mt-6 rounded-2xl bg-danger-soft p-6 text-center" role="alert">
          <p className="text-sm text-danger mb-3">{error}</p>
          <button onClick={cargar} className="text-sm font-semibold text-danger underline">Reintentar</button>
        </div>
      )}

      {datos && !datos.tiene && <Vacio onAgregar={() => setHoja({ tipo: 'posicion' })} onCsv={() => setHoja({ tipo: 'csv' })} />}

      {datos && datos.tiene && (
        <div className="dos-col dos-col-5-6">
          <div className="col">
            <Resumen d={datos} />
            {hayConcentracion(datos.concentracion, datos.posiciones.length) && (
              <p className="mx-5 mt-3 rounded-2xl bg-accent-soft p-3 text-xs" role="note">
                {datos.concentracion.nombre} pesa el {datos.concentracion.pct.toFixed(0)} % de tu portafolio.
              </p>
            )}
            {datos.sin_precio.length > 0 && (
              <p className="mx-5 mt-3 text-xs text-ink-soft">
                Sin precio: {datos.sin_precio.join(', ')}.
              </p>
            )}
            <div className="mx-5 mt-3 flex items-center gap-3">
              <button onClick={actualizarAhora} disabled={actualizando} className="min-h-11 px-4 rounded-full border border-line bg-paper-raised text-sm font-semibold flex items-center gap-2 disabled:opacity-60">
                <RefreshCw size={16} className={actualizando ? 'animate-spin' : ''} aria-hidden="true" /> Actualizar ahora
              </button>
              {mensaje && <span className="text-xs text-ink-soft" role="status">{mensaje}</span>}
            </div>
            <VerMas titulo="gráficos y reparto">
              {datos.evolucion.length > 0 && (
                <section className="mx-5 mt-4 rounded-2xl bg-paper-raised border border-line p-4">
                  <h2 className="text-sm font-semibold mb-3">Cómo ha cambiado tu portafolio</h2>
                  <GraficoPatrimonio historial={serieEvolucion(datos.evolucion)} />
                </section>
              )}
              <Distribuciones d={datos} />
            </VerMas>
          </div>
          <div className="col">
            <section className="mx-5 mt-4">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-sm font-semibold">Mi portafolio</h2>
                <button onClick={() => setHoja({ tipo: 'broker' })} className="text-xs font-semibold text-accent min-h-11 px-2">Agregar plataforma</button>
              </div>
              <div className="space-y-3">
                {datos.brokers.map((b) => (
                  <BloqueBroker key={b.id || 'sin'} b={b} onAbrir={(p) => setHoja({ tipo: 'detalle', id: p.id })} />
                ))}
              </div>
              <button onClick={() => setHoja({ tipo: 'csv' })} className="mt-3 text-xs font-semibold text-accent min-h-11">Importar desde un archivo CSV</button>
            </section>
            <VerMas titulo="más opciones">
              <label className="mx-5 mt-4 flex items-center gap-3 text-sm min-h-11">
                <input type="checkbox" checked={opciones.resumen_semanal} onChange={alternarSemanal} />
                Avisarme cada semana cómo va
              </label>
            </VerMas>
            <EnlacesRelacionados enlaces={[
              { a: '/patrimonio', texto: 'Ver todo lo que tienes' },
              { a: '/cuentas', texto: 'Mis cuentas' },
              { a: '/metas', texto: 'Metas de ahorro' },
            ]} />
          </div>
        </div>
      )}

      {hoja?.tipo === 'broker' && <FormBroker onClose={() => setHoja(null)} onListo={() => { setHoja(null); cargar() }} />}
      {hoja?.tipo === 'posicion' && <FormPosicion brokers={datos?.brokers || []} onClose={() => setHoja(null)} onListo={() => { setHoja(null); cargar() }} />}
      {hoja?.tipo === 'csv' && <FormCsv brokers={datos?.brokers || []} onClose={() => setHoja(null)} onListo={() => { setHoja(null); cargar() }} />}
      {hoja?.tipo === 'detalle' && <Detalle id={hoja.id} onClose={() => setHoja(null)} onCambio={cargar} />}
      {hoja?.tipo === 'glosario' && <Glosario onClose={() => setHoja(null)} />}
    </div>
  )
}

function Vacio({ onAgregar, onCsv }) {
  return (
    <div className="mx-5 mt-6 rounded-2xl bg-paper-raised border border-line p-6 text-center" data-testid="inversiones-vacio">
      <TrendingUp size={32} className="mx-auto mb-3 text-accent" aria-hidden="true" />
      <p className="text-sm font-semibold mb-1">Aquí verás tus inversiones</p>
      <p className="text-sm text-ink-soft mb-4">
        Sigue tus acciones, fondos, cripto o CDT. Es opcional.
      </p>
      <button onClick={onAgregar} className="bg-ink text-paper font-semibold rounded-2xl px-5 py-3 text-sm">Agregar mi primera inversión</button>
      <div><button onClick={onCsv} className="mt-2 text-xs font-semibold text-accent min-h-11">Tengo un archivo CSV</button></div>
    </div>
  )
}

function Resumen({ d }) {
  const p = d.periodos || {}
  return (
    <div className="mx-5 mt-3 hero-marca card-marca p-5">
      <p className="t-kicker mb-2">Valor de tus inversiones</p>
      <p className="text-[34px] t-display tabular-nums">{formatCOP(d.valor_total)}</p>
      <div className="grid grid-cols-2 gap-3 mt-4 text-xs">
        <div><p className="opacity-90">Lo que aportaste</p><p className="font-semibold tabular-nums">{formatCOP(d.costo_total)}</p></div>
        <div>
          <p className="opacity-90">Ganancia o pérdida</p>
          <p className="font-semibold tabular-nums">{d.no_realizada >= 0 ? '+' : '-'}{formatCOP(Math.abs(d.no_realizada))} ({pctTexto(d.no_realizada_pct)})</p>
        </div>
        {d.hoy_cop !== null && d.hoy_cop !== undefined && (
          <div><p className="opacity-90">Hoy</p><p className="font-semibold tabular-nums">{d.hoy_cop >= 0 ? '+' : '-'}{formatCOP(Math.abs(d.hoy_cop))}</p></div>
        )}
        {d.dividendos > 0 && <div><p className="opacity-90">Dividendos</p><p className="font-semibold tabular-nums">{formatCOP(d.dividendos)}</p></div>}
      </div>
      <div className="grid grid-cols-3 gap-2 mt-4 text-xs" aria-label="Rentabilidad por periodo">
        <div><p className="opacity-90">Este año</p><p className="font-semibold">{pctTexto(p.ytd_pct)}</p></div>
        <div><p className="opacity-90">12 meses</p><p className="font-semibold">{pctTexto(p.doce_meses_pct)}</p></div>
        <div><p className="opacity-90">Desde el inicio</p><p className="font-semibold">{pctTexto(p.desde_inicio_pct)}</p></div>
      </div>
      {d.tir_pct !== null && d.tir_pct !== undefined && (
        <p className="mt-3 text-xs opacity-90">Rinde al año (TIR): <strong>{pctTexto(d.tir_pct)}</strong></p>
      )}
    </div>
  )
}

function Distribuciones({ d }) {
  const [vista, setVista] = useState('distribucion_broker')
  const opciones = [['distribucion_broker', 'Plataforma'], ['distribucion_tipo', 'Tipo'], ['distribucion_moneda', 'Moneda']]
  const etiquetas = { ...ETIQUETA_TIPO, 'Sin plataforma': 'Sin plataforma' }
  const lista = d[vista] || []
  if (!lista.length) return null
  return (
    <section className="mx-5 mt-4 rounded-2xl bg-paper-raised border border-line p-4">
      <h2 className="text-sm font-semibold mb-3">En qué está repartida tu plata</h2>
      <div className="flex gap-2 mb-3" role="group" aria-label="Agrupar por">
        {opciones.map(([id, label]) => (
          <button key={id} onClick={() => setVista(id)} aria-pressed={vista === id}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border ${vista === id ? 'bg-accent text-paper-raised border-accent' : 'bg-paper-raised border-line text-ink-soft'}`}>
            {label}
          </button>
        ))}
      </div>
      <DonaDistribucion distribucion={lista} etiquetas={etiquetas} />
    </section>
  )
}

function BloqueBroker({ b, onAbrir }) {
  const [abierto, setAbierto] = useState(true)
  return (
    <div className="rounded-2xl bg-paper-raised border border-line">
      <button onClick={() => setAbierto(!abierto)} aria-expanded={abierto} className="w-full flex items-center justify-between px-4 py-3 min-h-11">
        <span className="text-sm font-semibold truncate">{b.nombre}</span>
        <span className="flex items-center gap-2 text-sm tabular-nums">
          {formatCOP(b.valor_cop)}
          <ChevronDown size={16} className={abierto ? 'rotate-180' : ''} aria-hidden="true" />
        </span>
      </button>
      {abierto && (
        <ul className="divide-y divide-line border-t border-line">
          {b.posiciones.length === 0 && <li className="px-4 py-3 text-xs text-ink-soft">Aún no hay posiciones aquí.</li>}
          {b.posiciones.map((p) => (
            <li key={p.id}>
              <button onClick={() => onAbrir(p)} className="w-full text-left px-4 py-3 min-h-11">
                <div className="flex justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{p.nombre}</p>
                    <p className="text-xs text-ink-soft truncate">
                      {p.ticker ? `${p.ticker} · ` : ''}{p.cantidad} u. · {p.precio === null ? '—' : formatMoneda(p.precio, p.moneda)}
                    </p>
                    <p className="text-[11px] text-ink-soft">{textoEstadoPrecio(p)}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-semibold tabular-nums">{p.valor === null ? 'Sin precio' : formatMoneda(p.valor, p.moneda)}</p>
                    <p className={`text-xs tabular-nums ${colorSigno(p.no_realizada)}`}>{pctTexto(p.no_realizada_pct)}</p>
                  </div>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Encabezado({ titulo, onClose }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-lg font-semibold">{titulo}</h2>
      <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
        <X size={16} />
      </button>
    </div>
  )
}

function FormBroker({ onClose, onListo }) {
  const [nombre, setNombre] = useState('')
  const [tipo, setTipo] = useState('acciones')
  const [moneda, setMoneda] = useState('COP')
  const [error, setError] = useState('')
  async function guardar() {
    if (!nombre.trim()) return setError('Ponle un nombre')
    try {
      await api.crearBrokerInversion({ nombre: nombre.trim(), tipo, moneda })
      onListo()
    } catch (e) { setError(e.message || 'No se pudo guardar.') }
  }
  return (
    <Hoja onCerrar={onClose}>
      <Encabezado titulo="Agregar plataforma" onClose={onClose} />
      <p className="text-xs text-ink-soft mb-3">Dónde tienes la inversión (broker, fiduciaria…).</p>
      <Campo etiqueta="Nombre">
        <input list="brokers-sugeridos" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej. Trii" className={clsInput} />
        <datalist id="brokers-sugeridos">{BROKERS_SUGERIDOS.map((b) => <option key={b} value={b} />)}</datalist>
      </Campo>
      <div className="grid grid-cols-2 gap-3">
        <Campo etiqueta="Qué manejas">
          <select value={tipo} onChange={(e) => setTipo(e.target.value)} className={clsInput}>
            {TIPOS_BROKER.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </Campo>
        <Campo etiqueta="Moneda">
          <select value={moneda} onChange={(e) => setMoneda(e.target.value)} className={clsInput}>
            {MONEDAS.map((m) => <option key={m}>{m}</option>)}
          </select>
        </Campo>
      </div>
      {error && <p className="text-sm text-danger mb-3" role="alert">{error}</p>}
      <button onClick={guardar} className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px]">Guardar plataforma</button>
    </Hoja>
  )
}

function FormPosicion({ brokers, onClose, onListo }) {
  const [tipo, setTipo] = useState('accion')
  const [nombre, setNombre] = useState('')
  const [ticker, setTicker] = useState('')
  const [mercado, setMercado] = useState('')
  const [moneda, setMoneda] = useState('COP')
  const [brokerId, setBrokerId] = useState('')
  const [cantidad, setCantidad] = useState('')
  const [costo, setCosto] = useState('')
  const [precio, setPrecio] = useState('')
  const [sugeridos, setSugeridos] = useState([])
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const usaTicker = ['accion', 'etf', 'cripto'].includes(tipo)

  useEffect(() => {
    if (!usaTicker || ticker.trim().length < 2) { setSugeridos([]); return undefined }
    const t = setTimeout(() => {
      api.tickersInversion?.(ticker.trim()).then((r) => setSugeridos(r || [])).catch(() => setSugeridos([]))
    }, 250)
    return () => clearTimeout(t)
  }, [ticker, usaTicker])

  function elegir(s) {
    setTicker(s.ticker); setNombre(s.nombre); setMercado(s.mercado); setMoneda(s.moneda); setTipo(s.tipo); setSugeridos([])
  }

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre')
    setGuardando(true)
    try {
      await api.crearPosicionInversion({
        nombre: nombre.trim(), tipo, ticker: usaTicker ? ticker.trim() || null : null, mercado, moneda,
        broker_id: brokerId || null, cantidad: Number(cantidad) || 0, costo_promedio: Number(costo) || 0,
        precio_manual: precio === '' ? null : Number(precio),
      })
      onListo()
    } catch (e) { setError(e.message || 'No se pudo guardar.') }
    setGuardando(false)
  }

  return (
    <Hoja onCerrar={onClose}>
      <Encabezado titulo="Agregar inversión" onClose={onClose} />
      <div className="flex flex-wrap gap-2 mb-4" role="group" aria-label="Tipo de inversión">
        {TIPOS_POSICION.map((t) => (
          <button key={t.id} type="button" onClick={() => setTipo(t.id)} aria-pressed={tipo === t.id}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border ${tipo === t.id ? 'bg-accent text-paper-raised border-accent' : 'bg-paper-raised border-line text-ink-soft'}`}>
            {t.label}
          </button>
        ))}
      </div>
      {usaTicker && (
        <Campo etiqueta="Ticker (el código en la bolsa)">
          <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} placeholder="Ej. ECOPETROL, VOO, BTC" className={clsInput} />
          {sugeridos.length > 0 && (
            <ul className="mt-1 rounded-2xl border border-line bg-paper-raised divide-y divide-line" role="listbox">
              {sugeridos.map((s) => (
                <li key={`${s.ticker}-${s.mercado}`}>
                  <button type="button" onClick={() => elegir(s)} className="w-full text-left px-4 py-2 text-sm min-h-11">
                    <strong>{s.ticker}</strong> · {s.nombre}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Campo>
      )}
      <Campo etiqueta="Nombre">
        <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder={TIPOS_POSICION.find((t) => t.id === tipo)?.ejemplo} className={clsInput} />
      </Campo>
      <div className="grid grid-cols-2 gap-3">
        <Campo etiqueta="Moneda">
          <select value={moneda} onChange={(e) => setMoneda(e.target.value)} className={clsInput}>
            {MONEDAS.map((m) => <option key={m}>{m}</option>)}
          </select>
        </Campo>
        <Campo etiqueta="Plataforma (opcional)">
          <select value={brokerId} onChange={(e) => setBrokerId(e.target.value)} className={clsInput}>
            <option value="">Ninguna</option>
            {brokers.filter((b) => b.id).map((b) => <option key={b.id} value={b.id}>{b.nombre}</option>)}
          </select>
        </Campo>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Campo etiqueta="Cantidad que tienes">
          <input value={cantidad} onChange={(e) => setCantidad(soloNumero(e.target.value))} inputMode="decimal" placeholder="Ej. 100" className={clsInput} />
        </Campo>
        <Campo etiqueta="Costo promedio por unidad">
          <InputMonto value={costo} onValor={setCosto} placeholder="Ej. 2.300" className={clsInput} />
        </Campo>
      </div>
      <Campo etiqueta="Precio actual por unidad (opcional; si hay ticker se actualiza solo)">
        <InputMonto value={precio} onValor={setPrecio} className={clsInput} />
      </Campo>
      {error && <p className="text-sm text-danger mb-3" role="alert">{error}</p>}
      <button onClick={guardar} disabled={guardando} className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60">
        {guardando ? 'Guardando...' : 'Agregar inversión'}
      </button>
    </Hoja>
  )
}

function FormCsv({ brokers, onClose, onListo }) {
  const [texto, setTexto] = useState('')
  const [moneda, setMoneda] = useState('COP')
  const [brokerId, setBrokerId] = useState('')
  const [vista, setVista] = useState(null)
  const [error, setError] = useState('')
  async function enviar(aplicar) {
    setError('')
    try {
      const r = await api.importarInversiones({ csv: texto, moneda, broker_id: brokerId || null, aplicar })
      if (aplicar) onListo()
      else setVista(r)
    } catch (e) { setError(e.message || 'No pudimos leer el archivo.') }
  }
  async function archivo(e) {
    const f = e.target.files?.[0]
    if (f) setTexto(await f.text())
  }
  return (
    <Hoja onCerrar={onClose}>
      <Encabezado titulo="Importar posiciones" onClose={onClose} />
      <p className="text-xs text-ink-soft mb-2">Un archivo con las columnas <strong>ticker, cantidad, costo</strong>. Ejemplo:</p>
      <pre className="text-[11px] bg-paper-raised border border-line rounded-xl p-2 mb-3 overflow-x-auto">{EJEMPLO_CSV}</pre>
      <input type="file" accept=".csv,text/csv" onChange={archivo} className="mb-3 text-sm" aria-label="Elegir archivo CSV" />
      <Campo etiqueta="…o pega el contenido">
        <textarea value={texto} onChange={(e) => { setTexto(e.target.value); setVista(null) }} rows={4} className={clsInput} />
      </Campo>
      <div className="grid grid-cols-2 gap-3">
        <Campo etiqueta="Moneda">
          <select value={moneda} onChange={(e) => setMoneda(e.target.value)} className={clsInput}>
            {MONEDAS.map((m) => <option key={m}>{m}</option>)}
          </select>
        </Campo>
        <Campo etiqueta="Plataforma (opcional)">
          <select value={brokerId} onChange={(e) => setBrokerId(e.target.value)} className={clsInput}>
            <option value="">Ninguna</option>
            {brokers.filter((b) => b.id).map((b) => <option key={b.id} value={b.id}>{b.nombre}</option>)}
          </select>
        </Campo>
      </div>
      {vista && (
        <div className="mb-3 rounded-2xl border border-line divide-y divide-line text-xs" data-testid="vista-previa-csv">
          {vista.filas.map((f, i) => (
            <p key={i} className={`px-3 py-2 ${f.ok ? '' : 'text-danger'}`}>
              {f.ticker || '(sin ticker)'} · {f.cantidad ?? '?'} u. · costo {f.costo ?? '?'} {f.ok ? '' : `— ${f.error}`}
            </p>
          ))}
        </div>
      )}
      {error && <p className="text-sm text-danger mb-3" role="alert">{error}</p>}
      {!vista ? (
        <button onClick={() => enviar(false)} disabled={!texto.trim()} className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60">Ver vista previa</button>
      ) : (
        <button onClick={() => enviar(true)} disabled={vista.validas === 0} className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60">
          Importar {vista.validas} {vista.validas === 1 ? 'posición' : 'posiciones'}
        </button>
      )}
    </Hoja>
  )
}

function Detalle({ id, onClose, onCambio }) {
  const [p, setP] = useState(null)
  const [error, setError] = useState('')
  const [form, setForm] = useState(null) // 'tx' | 'precio'
  const { cuentas = [] } = useCuentas() || {}
  async function cargar() {
    try { setP(await api.posicionInversion(id)) } catch (e) { setError(e.message || 'No se pudo cargar.') }
  }
  useEffect(() => { cargar() }, [id])
  const hist = (p?.historial_precio || []).map((h) => h.valor)
  const pts = hist.length > 1 ? puntosSerie(hist, 100, 40) : []
  async function borrarTx(tx) {
    await api.eliminarTransaccionInversion(tx)
    await cargar()
    onCambio()
  }
  async function quitar() {
    await api.eliminarPosicionInversion(id)
    onCambio()
    onClose()
  }
  return (
    <Hoja onCerrar={onClose}>
      <Encabezado titulo={p?.nombre || 'Inversión'} onClose={onClose} />
      {error && <p className="text-sm text-danger" role="alert">{error}</p>}
      {p && (
        <>
          <p className="text-2xl font-bold tabular-nums">{p.valor === null ? 'Sin precio' : formatMoneda(p.valor, p.moneda)}</p>
          <p className={`text-sm tabular-nums ${colorSigno(p.no_realizada)}`}>
            {p.no_realizada === null ? '' : `${p.no_realizada >= 0 ? '+' : '-'}${formatMoneda(Math.abs(p.no_realizada), p.moneda)} · ${pctTexto(p.no_realizada_pct)}`}
          </p>
          <p className="text-xs text-ink-soft mt-1">{textoEstadoPrecio(p)}</p>
          <dl className="grid grid-cols-2 gap-2 mt-4 text-xs">
            <div><dt className="text-ink-soft">Cantidad</dt><dd className="font-semibold">{p.cantidad}</dd></div>
            <div><dt className="text-ink-soft">Costo promedio</dt><dd className="font-semibold">{formatMoneda(p.costo_promedio, p.moneda)}</dd></div>
            <div><dt className="text-ink-soft">Ganancia realizada</dt><dd className="font-semibold">{formatMoneda(p.realizada, p.moneda)}</dd></div>
            <div><dt className="text-ink-soft">Dividendos</dt><dd className="font-semibold">{formatMoneda(p.dividendos, p.moneda)}</dd></div>
            {p.tir_pct !== null && p.tir_pct !== undefined && <div><dt className="text-ink-soft">TIR anual</dt><dd className="font-semibold">{pctTexto(p.tir_pct)}</dd></div>}
          </dl>
          {pts.length > 0 && (
            <svg viewBox="0 0 100 40" className="w-full mt-4" style={{ height: 80 }} preserveAspectRatio="none" role="img" aria-label="Evolución del precio">
              <path d={trazoLinea(pts)} fill="none" stroke="var(--color-accent)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
            </svg>
          )}
          <div className="flex gap-2 mt-4">
            <button onClick={() => setForm('tx')} className="flex-1 min-h-11 rounded-2xl bg-ink text-paper text-sm font-semibold">Registrar movimiento</button>
            <button onClick={() => setForm('precio')} className="flex-1 min-h-11 rounded-2xl border border-line text-sm font-semibold">Poner precio a mano</button>
          </div>
          {form === 'precio' && <FormPrecio id={id} moneda={p.moneda} onListo={() => { setForm(null); cargar(); onCambio() }} />}
          {form === 'tx' && <FormTx id={id} cuentas={cuentas} onListo={() => { setForm(null); cargar(); onCambio() }} />}
          <h3 className="text-sm font-semibold mt-5 mb-2">Historial</h3>
          {p.transacciones.length === 0 ? <p className="text-xs text-ink-soft">Aún no hay movimientos.</p> : (
            <ul className="divide-y divide-line text-xs">
              {p.transacciones.map((t) => (
                <li key={t.id} className="py-2 flex justify-between gap-2">
                  <span>{aFecha(t.fecha)?.toLocaleDateString('es-CO')} · {t.tipo}{t.cantidad ? ` · ${t.cantidad} u. a ${formatMoneda(t.precio, p.moneda)}` : t.monto ? ` · ${formatMoneda(t.monto, p.moneda)}` : ''}</span>
                  <button onClick={() => borrarTx(t.id)} className="text-danger font-semibold min-h-11 px-2" aria-label="Eliminar movimiento">Quitar</button>
                </li>
              ))}
            </ul>
          )}
          <button onClick={quitar} className="w-full mt-4 text-sm font-semibold text-danger py-2">Quitar esta inversión</button>
          <p className="text-[11px] text-ink-soft mt-2">{AVISO_EDUCATIVO}</p>
        </>
      )}
    </Hoja>
  )
}

function FormPrecio({ id, moneda, onListo }) {
  const [v, setV] = useState('')
  const [error, setError] = useState('')
  async function ok() {
    if (!(Number(v) > 0)) return setError('Escribe un precio mayor a 0')
    try { await api.precioManualInversion(id, Number(v)); onListo() } catch (e) { setError(e.message) }
  }
  return (
    <div className="mt-3 rounded-2xl border border-line p-3">
      <Campo etiqueta={`Precio por unidad (${moneda})`}><InputMonto value={v} onValor={setV} className={clsInput} /></Campo>
      {error && <p className="text-sm text-danger mb-2" role="alert">{error}</p>}
      <button onClick={ok} className="w-full min-h-11 rounded-2xl bg-accent text-paper-raised text-sm font-semibold">Guardar precio</button>
    </div>
  )
}

function FormTx({ id, cuentas, onListo }) {
  const [tipo, setTipo] = useState('compra')
  const [cantidad, setCantidad] = useState('')
  const [precio, setPrecio] = useState('')
  const [comision, setComision] = useState('')
  const [monto, setMonto] = useState('')
  const [cuentaId, setCuentaId] = useState('')
  const [error, setError] = useState('')
  const porUnidad = tipo === 'compra' || tipo === 'venta'
  async function ok() {
    setError('')
    try {
      await api.registrarTransaccionInversion(id, {
        tipo, cantidad: Number(cantidad) || 0, precio: Number(precio) || 0, comision: Number(comision) || 0,
        monto: Number(monto) || 0, cuenta_id: cuentaId || null,
      })
      onListo()
    } catch (e) { setError(e.message || 'No se pudo guardar.') }
  }
  const textos = { compra: 'Compra', venta: 'Venta', dividendo: 'Dividendo', aporte: 'Aporte', retiro: 'Retiro' }
  return (
    <div className="mt-3 rounded-2xl border border-line p-3">
      <div className="flex flex-wrap gap-2 mb-3" role="group" aria-label="Tipo de movimiento">
        {Object.entries(textos).map(([k, v]) => (
          <button key={k} type="button" onClick={() => setTipo(k)} aria-pressed={tipo === k}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border ${tipo === k ? 'bg-accent text-paper-raised border-accent' : 'bg-paper-raised border-line text-ink-soft'}`}>{v}</button>
        ))}
      </div>
      {porUnidad ? (
        <div className="grid grid-cols-3 gap-2">
          <Campo etiqueta="Cantidad"><input value={cantidad} onChange={(e) => setCantidad(soloNumero(e.target.value))} inputMode="decimal" className={clsInput} /></Campo>
          <Campo etiqueta="Precio"><InputMonto value={precio} onValor={setPrecio} className={clsInput} /></Campo>
          <Campo etiqueta="Comisión"><InputMonto value={comision} onValor={setComision} className={clsInput} /></Campo>
        </div>
      ) : (
        <Campo etiqueta="Monto"><InputMonto value={monto} onValor={setMonto} className={clsInput} /></Campo>
      )}
      {cuentas.length > 0 && (
        <Campo etiqueta={tipo === 'dividendo' ? 'Cuenta donde lo recibiste (opcional)' : 'Enlazar con una cuenta (opcional)'}>
          <select value={cuentaId} onChange={(e) => setCuentaId(e.target.value)} className={clsInput}>
            <option value="">No enlazar</option>
            {cuentas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
          {cuentaId && (
            <span className="text-[11px] text-ink-soft block mt-1">
              {tipo === 'dividendo' ? 'Se guardará como ingreso de «Rendimientos».' : 'Se guardará como traslado a Inversiones: no cuenta como gasto.'}
            </span>
          )}
        </Campo>
      )}
      {error && <p className="text-sm text-danger mb-2" role="alert">{error}</p>}
      <button onClick={ok} className="w-full min-h-11 rounded-2xl bg-accent text-paper-raised text-sm font-semibold">Guardar movimiento</button>
    </div>
  )
}

function Glosario({ onClose }) {
  return (
    <Hoja onCerrar={onClose}>
      <Encabezado titulo="¿Qué es esto?" onClose={onClose} />
      <dl className="space-y-3">
        {GLOSARIO.map(([t, d]) => (
          <div key={t}><dt className="text-sm font-semibold">{t}</dt><dd className="text-sm text-ink-soft">{d}</dd></div>
        ))}
      </dl>
      <p className="text-[11px] text-ink-soft mt-4">{AVISO_EDUCATIVO}</p>
    </Hoja>
  )
}
