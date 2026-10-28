import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, ChevronLeft, CircleDashed, Lightbulb, Loader2, TrendingUp } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP, formatPorcentaje } from '../lib/format'
import { useDialogos } from '../lib/DialogosContext'
import CelebracionCuadri from '../brand/CelebracionCuadri'
import CierreExtractos from '../components/CierreExtractos'
import { FRASES } from '../lib/cuadri'
import { PASOS, cosasRaras, estadoPasos, listoParaCerrar, pendientesDeCierre, textoAvance } from '../lib/cierreAsistente'

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

const ICONO = { ok: CheckCircle2, atencion: AlertTriangle, cargando: Loader2, neutro: CircleDashed }
const COLOR = { ok: 'text-cuadra', atencion: 'text-danger', cargando: 'text-ink-soft', neutro: 'text-ink-soft' }

function Icono({ estado, className = '' }) {
  const I = ICONO[estado] || CircleDashed
  return <I size={20} aria-hidden="true" className={`${COLOR[estado] || ''} ${estado === 'cargando' ? 'animate-spin' : ''} ${className}`} />
}

// Los cuatro pasos en una fila: tocas uno para ir, ves de un vistazo cuál está bien y cuál pide atención.
function Pasos({ pasos, actual, onIr }) {
  return (
    <ol className="grid grid-cols-4 gap-1.5" aria-label="Pasos del cierre">
      {pasos.map((p, i) => (
        <li key={p.id}>
          <button
            type="button"
            onClick={() => onIr(i)}
            aria-current={i === actual ? 'step' : undefined}
            aria-label={`Paso ${i + 1}: ${p.titulo}`}
            className={`w-full min-h-14 rounded-xl border px-1.5 py-2 flex flex-col items-center justify-center gap-1 text-[11px] font-semibold ${
              i === actual ? 'border-accent bg-accent-soft text-accent' : 'border-line bg-paper-raised text-ink-soft'
            }`}
          >
            <Icono estado={p.estado} />
            <span className="truncate max-w-full">{p.corto}</span>
          </button>
        </li>
      ))}
    </ol>
  )
}

function CabeceraPaso({ paso, indice, pasos }) {
  return (
    <div className="mt-4">
      <p className="text-xs text-ink-soft font-medium">{textoAvance(indice, pasos)}</p>
      <h2 className="text-xl font-bold mt-1 flex items-start gap-2">
        <Icono estado={paso.estado} className="mt-1 shrink-0" />
        <span>{paso.titulo}</span>
      </h2>
      <p className={`text-sm mt-1 ${paso.estado === 'atencion' ? 'text-danger font-medium' : 'text-ink-soft'}`} role="status">
        {paso.resumen}
      </p>
    </div>
  )
}

export default function CierreMes() {
  const volver = useVolver('/')
  const navigate = useNavigate()
  const { avisar } = useDialogos()
  const [lista, setLista] = useState(null)
  const listaRef = useRef(null) // cierres existentes, para no pedir los que no existen
  const [mes, setMes] = useState(null)
  const [informe, setInforme] = useState(null)
  const [correo, setCorreo] = useState(false)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)
  const [ext, setExt] = useState(null) // cierre contra los extractos: null = cargando, false = no se pudo
  const [mesesExt, setMesesExt] = useState([]) // selector de 12 meses que manda el servidor
  const [porCategorizar, setPorCategorizar] = useState(null) // comercios sin categoría: null = cargando
  const [alertas, setAlertas] = useState(null) // cosas raras: null = cargando, false = no se pudo
  const [paso, setPaso] = useState(0)
  const movido = useRef(false) // si la persona ya se movió entre pasos, no la saltamos nosotros
  const mesPrevio = useRef(null)

  useEffect(() => {
    api.cierrePreferencias().then((p) => setCorreo(!!p.correo)).catch(() => {})
    api
      .cierresMes()
      .then((l) => {
        listaRef.current = Array.isArray(l) ? l : null
        setLista(l)
        setMes(l[0]?.mes || mesAnterior())
      })
      .catch((e) => setError(e.message || 'No se pudo cargar. Revisa tu conexión e intenta de nuevo.'))
  }, [])

  useEffect(() => {
    if (!mes) return
    setInforme(null)
    setError('')
    if (mesPrevio.current && mesPrevio.current !== mes) { // otro mes: se empieza de nuevo (la primera carga no pisa lo que ya tocó)
      movido.current = false
      setPaso(0)
    }
    mesPrevio.current = mes
    // Si la lista de cierres ya cargó y este mes no está, no hay nada que pedir: así no se hace
    // una petición que el servidor contesta con 404 (error rojo en la consola en cada visita).
    const conocidos = listaRef.current
    if (conocidos && !conocidos.some((l) => l.mes === mes)) {
      setInforme(false)
      return
    }
    // 404 o null = "aún no hay cierre", un estado normal
    api.cierreMes(mes).then((r) => setInforme(r || false)).catch(() => setInforme(false))
  }, [mes])

  // Si el cierre de este mes ya existe, se abre directo en el resumen (lo que la persona viene a ver).
  useEffect(() => {
    if (informe && !movido.current) setPaso(PASOS.length - 1)
  }, [informe])

  const cargarExtractos = useCallback((m) => {
    if (!m) return Promise.resolve()
    return Promise.resolve(api.cierreExtractos?.(m))
      .then((r) => {
        if (r && Array.isArray(r.bancos)) {
          setExt(r)
          setMesesExt(Array.isArray(r.meses) ? r.meses : [])
        } else setExt(false)
      })
      .catch(() => setExt(false))
  }, [])

  useEffect(() => {
    setExt(null)
    cargarExtractos(mes)
  }, [mes, cargarExtractos])

  // Pasos 2 y 3: no dependen del mes (lo pendiente es lo pendiente), se leen al entrar.
  useEffect(() => {
    Promise.resolve(api.sincronizacionPorCategorizar?.(0, 1))
      .then((r) => setPorCategorizar(Number(r?.total) || 0))
      .catch(() => setPorCategorizar(0))
    Promise.resolve(api.alertasProactivas?.())
      .then((r) => setAlertas(r || { comisiones: [], cobros_duplicados: [] }))
      .catch(() => setAlertas(false))
  }, [])

  async function generar() {
    setCargando(true)
    try {
      const nuevo = await api.generarCierreMes(mes)
      listaRef.current = [...(listaRef.current || []), { mes }]
      setInforme(nuevo)
    } catch (e) {
      setError(e.message || 'No se pudo generar. Revisa tu conexión e intenta de nuevo.')
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
      avisar('No se pudo guardar. Revisa tu conexión e intenta de nuevo.')
    }
  }

  const ir = (i) => {
    movido.current = true
    setPaso(Math.max(0, Math.min(PASOS.length - 1, i)))
  }

  // Últimos 12 meses (los manda el servidor); mientras llegan, los del historial de cierres.
  const meses = [...new Set(mesesExt.length ? [...mesesExt.map((x) => x.mes), mes] : [...(lista || []).map((l) => l.mes), mesAnterior()])].filter(Boolean).sort().reverse()
  const etiquetaMes = (m) => {
    const x = mesesExt.find((y) => y.mes === m)
    return x ? `${x.etiqueta}${x.con_extracto ? ' · con extracto' : ''}` : m
  }

  // «septiembre 2026»: lo que se ve en la pantalla habla en palabras, no en «2026-09».
  const nombreDelMes = (() => {
    const x = mesesExt.find((y) => y.mes === mes)
    if (x?.etiqueta) return String(x.etiqueta).toLowerCase()
    const [a, m] = String(mes || '').split('-').map(Number)
    return a && m ? new Date(a, m - 1, 1).toLocaleDateString('es-CO', { month: 'long', year: 'numeric' }) : mes
  })()
  const pasos = estadoPasos({ ext, porCategorizar, alertas, informe })
  const actual = pasos[paso]
  const pendientes = pendientesDeCierre(pasos)
  const listo = listoParaCerrar(pasos)
  const raras = cosasRaras(alertas)
  const siguiente = pasos[paso + 1]

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-semibold flex-1">Cierre de mes</h1>
      </header>

      {mes && (
        <div className="px-5 mt-1">
          <select aria-label="Mes" value={mes} onChange={(e) => setMes(e.target.value)} className="w-full min-h-11 rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm">
            {meses.map((m) => <option key={m} value={m}>{etiquetaMes(m)}</option>)}
          </select>
        </div>
      )}

      <div className="px-5 mt-3">
        {error && <p className="text-sm text-danger mb-3">{error}</p>}

        {informe === false && actual.id !== 'resumen' && (
          <p className="text-sm text-ink-soft mb-3">Aún no hay cierre de {nombreDelMes}. Revísalo paso a paso y ciérralo cuando todo esté bien.</p>
        )}

        <Pasos pasos={pasos} actual={paso} onIr={ir} />
        <CabeceraPaso paso={actual} indice={paso} pasos={pasos} />

        <div className="mt-4">
          {actual.id === 'cuentas' && (
            <>
              {ext === null && <p className="text-sm text-ink-soft" role="status">Mirando tus extractos...</p>}
              {ext && <CierreExtractos datos={ext} onCambio={() => cargarExtractos(mes)} />}
              {ext === false && (
                <p className="text-sm text-ink-soft">Cuando traigas tus extractos, aquí verás si cada cuenta cuadra con su banco.</p>
              )}
              {actual.estado === 'atencion' && (
                <button onClick={() => navigate('/sincronizacion')} className="mt-3 w-full min-h-11 rounded-2xl border border-line bg-paper-raised text-sm font-semibold">
                  Traer los extractos que faltan
                </button>
              )}
            </>
          )}

          {actual.id === 'categorias' && (
            <div className="rounded-2xl bg-paper-raised border border-line p-4">
              {porCategorizar > 0 ? (
                <>
                  <p className="text-3xl font-bold tabular-nums">{porCategorizar}</p>
                  <p className="text-sm text-ink-soft mt-1">Con categoría tus gráficos y tu presupuesto salen ciertos. Lo haces una vez por comercio y CuadraMe lo recuerda.</p>
                  <button onClick={() => navigate('/categorizar')} className="mt-3 w-full min-h-11 rounded-2xl bg-ink text-paper text-sm font-semibold">
                    Ponerles categoría
                  </button>
                </>
              ) : (
                <p className="text-sm text-ink-soft">Todos tus movimientos tienen categoría. Tus gráficos de este mes salen completos.</p>
              )}
            </div>
          )}

          {actual.id === 'raro' && (
            <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden">
              {raras.length === 0 ? (
                <p className="p-4 text-sm text-ink-soft">No encontré comisiones fuera de lo normal ni cobros repetidos.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {raras.map((r) => (
                    <li key={r.clave} className="px-4 py-3">
                      {r.tipo === 'comision' ? (
                        <>
                          <p className="text-sm font-medium">{r.descripcion}</p>
                          <p className="text-xs text-ink-soft mt-0.5">{formatCOP(r.total_mes)} en comisiones este mes. Vale la pena revisar si se puede evitar.</p>
                        </>
                      ) : (
                        <>
                          <p className="text-sm font-medium">Posible cobro repetido: {r.descripcion}</p>
                          <p className="text-xs text-ink-soft mt-0.5">{formatCOP(r.monto)} cobrado dos veces en menos de 48 horas. Si fue un error, puedes reclamarlo.</p>
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              <button onClick={() => navigate('/insights')} className="w-full min-h-11 border-t border-line text-sm font-semibold text-accent">
                Ver todas las cosas raras
              </button>
            </div>
          )}

          {actual.id === 'resumen' && (
            <>
              {pendientes.length > 0 && informe === false && (
                <div className="rounded-2xl border border-line bg-paper-raised p-4 mb-3" data-testid="faltan-antes-de-cerrar">
                  <p className="text-sm font-semibold">Antes de cerrar te falta:</p>
                  <ul className="mt-2 flex flex-col gap-1.5">
                    {pendientes.map((p) => (
                      <li key={p.id}>
                        <button onClick={() => ir(pasos.indexOf(p))} className="w-full min-h-11 flex items-center justify-between gap-2 text-left text-sm">
                          <span className="flex items-center gap-2"><AlertTriangle size={16} className="text-danger shrink-0" aria-hidden="true" /> {p.resumen}</span>
                          <ArrowRight size={16} className="shrink-0 text-ink-soft" aria-hidden="true" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {listo && informe === false && (
                <p className="text-sm text-cuadra font-medium mb-3" role="status">Todo en orden. Ya puedes cerrar el mes.</p>
              )}

              {informe === false && (
                <div className="rounded-2xl bg-paper-raised border border-line p-5 text-center">
                  <p className="text-sm text-ink-soft mb-3">Aún no hay cierre de {nombreDelMes}. Se genera solo cada mes; también puedes crearlo ahora.</p>
                  <button onClick={generar} disabled={cargando} className="bg-ink text-paper rounded-2xl px-5 py-3 text-sm font-semibold disabled:opacity-60">
                    {cargando ? 'Generando...' : pendientes.length ? 'Generar cierre de todos modos' : 'Generar cierre'}
                  </button>
                </div>
              )}

              {informe && informe.ahorro > 0 && (
                <CelebracionCuadri id={`cierre-${mes}`} titulo={`Cierre de ${mes}`} texto={FRASES.celebraMes[0]} />
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
                    <p className="text-[11px] text-ink-soft mt-2">No incluye pagos de tarjeta ni la plata que pasaste entre tus cuentas, para no contar dos veces.</p>
                  </div>

                  {informe.categoria_que_mas_subio && (
                    <div className="rounded-2xl bg-paper-raised border border-line p-4 mt-3 flex gap-3">
                      <TrendingUp size={20} className="text-danger shrink-0 mt-0.5" />
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

                  <button onClick={() => navigate('/resumen')} className="mt-3 w-full min-h-11 rounded-2xl border border-line bg-paper-raised text-sm font-semibold">
                    Ver y compartir mi resumen del mes
                  </button>
                </>
              )}

              <label className="flex items-start gap-2 text-xs mt-6 min-h-[44px]">
                <input type="checkbox" checked={correo} onChange={alternarCorreo} className="w-4 h-4 mt-0.5 accent-accent" />
                <span>Enviarme también el cierre por correo (por defecto solo recibes una notificación en la app)</span>
              </label>
            </>
          )}
        </div>

        <nav className="mt-6 flex items-center justify-between gap-3" aria-label="Moverse entre pasos">
          <button onClick={() => ir(paso - 1)} disabled={paso === 0} className="min-h-11 px-4 rounded-2xl border border-line bg-paper-raised text-sm font-semibold flex items-center gap-1.5 disabled:opacity-30">
            <ChevronLeft size={16} aria-hidden="true" /> Atrás
          </button>
          {siguiente && (
            <button onClick={() => ir(paso + 1)} className="min-h-11 flex-1 px-4 rounded-2xl bg-ink text-paper text-sm font-semibold flex items-center justify-center gap-1.5">
              {actual.estado === 'atencion' ? 'Seguir sin resolverlo' : 'Siguiente'}: {siguiente.corto} <ArrowRight size={16} aria-hidden="true" />
            </button>
          )}
        </nav>
      </div>
    </div>
  )
}
