import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import {
  ArrowLeft, CheckCheck, CheckCircle2, FileCheck2, FileText, KeyRound, Mail, RefreshCw, Tag, Wallet, X,
} from 'lucide-react'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { useCategorias } from '../lib/CategoriasContext'
import { useCuentas } from '../lib/CuentasContext'
import { haceCuanto, resumenSync, sincronizarTodo } from '../lib/sincronizarGmail'
import {
  BANCO_SIN_IDENTIFICAR, agruparPorBanco, conciliarExtracto, estadoCelda, ESTADOS_CELDA, nombreMes,
  resumenTareas, textoEstadoExtracto,
} from '../lib/sincronizacion'
import CrearCuentaBanco from '../components/CrearCuentaBanco'

// Una sola pantalla para saber qué ya se concilió, qué falta y qué hay que preguntar.
// Todo lo que muestra viene de GET /sincronizacion/estado (una llamada); cada acción
// reutiliza el flujo que ya existía (Gmail por lotes, conciliar extracto, recategorizar).

const TAREAS = {
  falta_clave: { icono: KeyRound, accion: 'Poner clave' },
  extractos_por_conciliar: { icono: FileCheck2, accion: 'Ver extractos' },
  sin_cuenta: { icono: Wallet, accion: 'Crear cuenta' },
  movimientos_por_categorizar: { icono: Tag, accion: 'Categorizar' },
  movimientos_por_confirmar: { icono: CheckCheck, accion: 'Revisar' },
  correos_por_revisar: { icono: Mail, accion: 'Revisar' },
}

const EXTRACTOS_VISIBLES = 6

function irA(id) {
  const el = typeof document !== 'undefined' ? document.getElementById(id) : null
  el?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

function Seccion({ id, titulo, ayuda, children }) {
  return (
    <section id={id} className="mx-6 mt-7 scroll-mt-4" aria-label={titulo}>
      <h2 className="text-[15px] font-semibold">{titulo}</h2>
      {ayuda && <p className="text-xs text-ink-soft mt-0.5">{ayuda}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

export default function Sincronizacion() {
  const navigate = useNavigate()
  const volver = useVolver('/')
  const { cuentas } = useCuentas() || { cuentas: [] }
  const { nombres = [], iconoDe = () => '💳' } = useCategorias() || {}
  const { fmt } = useBloqueo()

  const [estado, setEstado] = useState(null)
  const [gmail, setGmail] = useState(null)
  const [extractos, setExtractos] = useState([])
  const [ignorados, setIgnorados] = useState(null) // null = no cargados
  const [verTodos, setVerTodos] = useState(false)
  const [cola, setCola] = useState({ items: [], total: 0 })
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [progreso, setProgreso] = useState(null)
  const [resumen, setResumen] = useState('')
  const [errorSync, setErrorSync] = useState('')
  const [detalle, setDetalle] = useState(null) // { cuentaId, mes }
  const [crearBanco, setCrearBanco] = useState(null)
  const [cuentaPorExtracto, setCuentaPorExtracto] = useState({})
  const [ocupados, setOcupados] = useState(new Set())
  const [avisoExt, setAvisoExt] = useState('')
  const [claveConfigurada, setClaveConfigurada] = useState(false)
  const [claveInput, setClaveInput] = useState('')
  const [mostrarClave, setMostrarClave] = useState(false)
  const [recordar, setRecordar] = useState({}) // id -> false cuando la casilla se desmarca
  const montado = useRef(true)

  useEffect(() => {
    montado.current = true
    return () => {
      montado.current = false
    }
  }, [])

  const cargar = useCallback(async () => {
    try {
      const [est, gm, ex, clave, porCat] = await Promise.all([
        api.sincronizacionEstado(),
        api.gmailEstado().catch(() => null),
        api.extractosCorreo().catch(() => []),
        api.clavePdfEstado().catch(() => ({})),
        api.sincronizacionPorCategorizar(0).catch(() => ({ items: [], total: 0 })),
      ])
      if (!montado.current) return
      setEstado(est)
      setGmail(gm)
      setExtractos(Array.isArray(ex) ? ex : [])
      setClaveConfigurada(Boolean(clave?.configurada))
      setCola({ items: porCat?.items || [], total: porCat?.total || 0 })
      setError('')
    } catch (err) {
      if (montado.current) setError(err.message || 'No se pudo cargar la sincronización')
    } finally {
      if (montado.current) setCargando(false)
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  // ── Sincronizar todo (Gmail por lotes) ─────────────────────────────
  const sincronizando = Boolean(progreso)

  async function sincronizar() {
    setErrorSync('')
    setResumen('')
    setProgreso({ leidos: 0, total_estimado: 0 })
    try {
      const r = await sincronizarTodo({
        onProgreso: (p) => montado.current && setProgreso({ leidos: p.leidos, total_estimado: p.total_estimado }),
      })
      if (!r?.ok) {
        setErrorSync(r?.error || 'No se pudo sincronizar')
      } else {
        const leidos = r.leidos ? `Leí ${r.leidos} correos. ` : ''
        setResumen(`${leidos}${resumenSync(r)}`)
        try {
          localStorage.setItem('cuadrame_gmail_sync', String(Date.now()))
        } catch {
          /* sin almacenamiento */
        }
        await cargar()
      }
    } catch (err) {
      setErrorSync(err.message || 'Error al sincronizar')
    } finally {
      if (montado.current) setProgreso(null)
    }
  }

  // ── Tareas ─────────────────────────────────────────────────────────
  function accionTarea(t) {
    if (t.id === 'falta_clave') {
      setMostrarClave(true)
      return irA('sinc-extractos')
    }
    if (t.id === 'sin_cuenta' && estado?.sin_cuenta?.length === 1) return setCrearBanco(estado.sin_cuenta[0].banco)
    const ancla = t.ruta?.startsWith('/sincronizacion#') ? t.ruta.split('#')[1] : null
    if (ancla) return irA(`sinc-${ancla}`)
    navigate(t.ruta)
  }

  // ── Extractos ──────────────────────────────────────────────────────
  const cuentaElegida = (ex) => cuentaPorExtracto[ex.id] || ex.cuenta_sugerida_id || ''
  const nombreCuenta = (id) => cuentas.find((c) => c.id === id)?.nombre

  async function conciliar(ex) {
    if (ocupados.has(ex.id)) return
    setOcupados((s) => new Set(s).add(ex.id))
    setAvisoExt('')
    try {
      const r = await conciliarExtracto(ex, cuentaElegida(ex))
      if (r.ok) navigate('/conciliacion', { state: { historialId: r.historialId } })
      else {
        setAvisoExt(r.error)
        await cargar()
      }
    } catch (err) {
      setAvisoExt(err.message || 'No se pudo conciliar el extracto')
    } finally {
      if (montado.current) {
        setOcupados((s) => {
          const n = new Set(s)
          n.delete(ex.id)
          return n
        })
      }
    }
  }

  async function ignorar(ex) {
    await api.descartarExtractoCorreo(ex.id)
    await cargar()
    if (ignorados) setIgnorados(null)
  }

  async function verIgnorados() {
    try {
      const lista = await api.extractosCorreo('descartado')
      setIgnorados(Array.isArray(lista) ? lista : [])
    } catch (err) {
      setAvisoExt(err.message || 'No se pudieron cargar los ignorados')
    }
  }

  async function guardarClave() {
    if (!claveInput.trim()) return
    setAvisoExt('')
    try {
      await api.guardarClavePdf(claveInput.trim())
      setClaveInput('')
      setClaveConfigurada(true)
      setAvisoExt('Clave guardada. Toca "Sincronizar todo" para abrir esos extractos.')
    } catch (err) {
      setAvisoExt(err.message || 'No se pudo guardar la clave')
    }
  }

  // ── Por categorizar ────────────────────────────────────────────────
  async function categorizar(m, categoria) {
    if (!categoria || ocupados.has(m.id)) return
    setOcupados((s) => new Set(s).add(m.id))
    try {
      await api.recategorizarComercio(m.id, {
        categoria,
        aplicar_a_todos: recordar[m.id] !== false,
        ...(m.patron ? { patron: m.patron } : {}),
      })
      await cargar()
    } catch (err) {
      setAvisoExt(err.message || 'No se pudo cambiar la categoría')
    } finally {
      if (montado.current) {
        setOcupados((s) => {
          const n = new Set(s)
          n.delete(m.id)
          return n
        })
      }
    }
  }

  async function masPorCategorizar() {
    const mas = await api.sincronizacionPorCategorizar(cola.items.length)
    setCola((c) => ({ items: [...c.items, ...(mas?.items || [])], total: mas?.total ?? c.total }))
  }

  // ── Render ─────────────────────────────────────────────────────────
  if (cargando) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-ink-soft">Cargando...</p>
      </div>
    )
  }

  if (error && !estado) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 px-8 text-center">
        <p className="text-sm text-danger" role="alert">{error}</p>
        <button onClick={() => { setCargando(true); cargar() }} className="text-sm text-accent font-medium">
          Reintentar
        </button>
      </div>
    )
  }

  const tareas = estado?.tareas || []
  const sinCuenta = estado?.sin_cuenta || []
  const meses = estado?.meses || []
  const filasCuentas = estado?.cuentas || []
  const conectado = Boolean(gmail?.conectado)
  const pct = progreso?.total_estimado ? Math.min(100, Math.round((progreso.leidos / progreso.total_estimado) * 100)) : 0
  const ultima = haceCuanto(estado?.ultima_sync)

  const celdaDetalle = detalle
    ? filasCuentas.find((c) => c.id === detalle.cuentaId)?.meses.find((m) => m.mes === detalle.mes)
    : null
  const cuentaDetalle = detalle ? filasCuentas.find((c) => c.id === detalle.cuentaId) : null

  const visibles = verTodos ? extractos : extractos.slice(0, EXTRACTOS_VISIBLES)

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter pantalla-ancha">
      {/* a) Encabezado: una línea de resumen y el botón principal */}
      <header className="px-6 pantalla-top pb-1 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold">Sincronización</h1>
          <p className="text-sm text-ink-soft" data-testid="resumen-tareas">{resumenTareas(tareas)}</p>
        </div>
      </header>

      <div className="dos-col dos-col-4-7">
      <div className="col">
      <section className="mx-6 mt-3">
        {conectado ? (
          <button
            onClick={sincronizar}
            disabled={sincronizando}
            className="w-full flex items-center justify-center gap-2 bg-ink text-paper font-semibold rounded-2xl py-3.5 text-[15px] disabled:opacity-60"
          >
            <RefreshCw size={16} className={sincronizando ? 'animate-spin' : ''} />
            {sincronizando ? 'Sincronizando...' : 'Sincronizar todo'}
          </button>
        ) : (
          <button
            onClick={() => navigate('/correos')}
            className="w-full flex items-center justify-center gap-2 bg-ink text-paper font-semibold rounded-2xl py-3.5 text-[15px]"
          >
            <Mail size={16} /> Conectar Gmail
          </button>
        )}
        {progreso && (
          <div className="mt-3" role="status">
            <div className="h-2 rounded-full bg-line overflow-hidden" role="progressbar" aria-label="Progreso de la sincronización" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
              <div className="h-full w-full bg-accent barra-fill" style={{ transform: `scaleX(${pct / 100})` }} />
            </div>
            <p className="text-xs text-ink-soft mt-1.5">
              {progreso.total_estimado ? `Leí ${progreso.leidos} de ${progreso.total_estimado}` : 'Empezando...'}
            </p>
          </div>
        )}
        {errorSync && <p className="text-xs text-danger mt-2" role="alert">{errorSync}</p>}
        {resumen && !errorSync && !progreso && (
          <p className="text-sm font-semibold mt-3 rounded-2xl bg-cuadra-soft text-cuadra px-4 py-3" role="status">{resumen}</p>
        )}
        {error && estado && <p className="text-xs text-danger mt-2" role="alert">{error}</p>}
      </section>

      {/* b) Qué falta */}
      <Seccion id="sinc-tareas" titulo="Qué falta">
        {tareas.length === 0 ? (
          <div className="rounded-2xl bg-paper-raised border border-line p-6 text-center" data-testid="todo-al-dia">
            <CheckCircle2 size={28} className="text-cuadra mx-auto" aria-hidden="true" />
            <p className="text-[15px] font-semibold mt-2">Todo al día</p>
            <p className="text-xs text-ink-soft mt-1">
              {ultima ? `Última sincronización: ${ultima}` : 'Aún no has sincronizado tu correo.'}
            </p>
          </div>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {tareas.map((t) => {
              const { icono: Icono, accion } = TAREAS[t.id] || { icono: CheckCheck, accion: 'Abrir' }
              return (
                <li key={t.id} className="rounded-2xl bg-paper-raised border border-line p-3.5 flex items-center gap-3" data-testid={`tarea-${t.id}`}>
                  <span className="w-10 h-10 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
                    <Icono size={18} aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold leading-tight">
                      {t.titulo} <span className="text-accent" aria-label={`${t.cantidad} pendientes`}>{t.cantidad}</span>
                    </p>
                    <p className="text-xs text-ink-soft mt-0.5">{t.detalle}</p>
                  </div>
                  <button
                    onClick={() => accionTarea(t)}
                    className="shrink-0 rounded-xl bg-accent text-white text-xs font-semibold px-3.5 py-2.5 min-h-[40px]"
                  >
                    {accion}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </Seccion>

      </div>
      <div className="col">
      {/* c) Cuentas por mes */}
      <Seccion id="sinc-cuentas" titulo="Cuentas por mes" ayuda="Toca un mes para ver el detalle.">
        {filasCuentas.length === 0 ? (
          <p className="text-sm text-ink-soft">Aún no tienes cuentas.</p>
        ) : (
          <div className="rounded-2xl bg-paper-raised border border-line p-3">
            <div role="table" aria-label="Estado de cada cuenta en los últimos meses">
              <div role="row" className="grid grid-cols-[minmax(0,1.5fr)_repeat(6,minmax(0,1fr))] gap-1 items-end mb-1.5">
                <span role="columnheader" className="text-[11px] text-ink-soft">Cuenta</span>
                {meses.map((m) => (
                  <span key={m.clave} role="columnheader" className="text-[11px] text-ink-soft text-center capitalize">{m.etiqueta}</span>
                ))}
              </div>
              {filasCuentas.map((c) => (
                <div key={c.id} role="row" className="grid grid-cols-[minmax(0,1.5fr)_repeat(6,minmax(0,1fr))] gap-1 items-center mb-1">
                  <span role="rowheader" className="text-xs font-medium truncate pr-1">{c.nombre}</span>
                  {c.meses.map((m) => {
                    const e = estadoCelda(m.estado)
                    const activa = detalle?.cuentaId === c.id && detalle?.mes === m.mes
                    return (
                      <div key={m.mes} role="cell" className="contents">
                        <button
                          onClick={() => setDetalle(activa ? null : { cuentaId: c.id, mes: m.mes })}
                          aria-pressed={activa}
                          aria-label={`${c.nombre}, ${nombreMes(m.mes)}: ${e.texto}`}
                          className={`h-10 rounded-lg border text-sm font-semibold flex items-center justify-center ${e.clase} ${activa ? 'ring-2 ring-ink' : ''}`}
                        >
                          <span aria-hidden="true">{e.simbolo}</span>
                        </button>
                      </div>
                    )
                  })}
                </div>
              ))}
              {sinCuenta.map((s) => (
                <div key={s.banco} className="mt-2 rounded-xl border border-dashed border-accent/50 bg-accent-soft/50 px-3 py-2.5 flex items-center gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold">Sin cuenta · {s.banco}</p>
                    <p className="text-[11px] text-ink-soft">
                      {[s.correos ? `${s.correos} ${s.correos === 1 ? 'correo' : 'correos'}` : '', s.extractos ? `${s.extractos} ${s.extractos === 1 ? 'extracto' : 'extractos'}` : '']
                        .filter(Boolean).join(' y ')}
                    </p>
                  </div>
                  <button onClick={() => setCrearBanco(s.banco)} className="shrink-0 rounded-xl bg-accent text-white text-xs font-semibold px-3 py-2 min-h-[36px]">
                    Crear cuenta {s.banco}
                  </button>
                </div>
              ))}
            </div>

            <ul className="flex flex-wrap gap-x-3 gap-y-1 mt-3 text-[11px] text-ink-soft" aria-label="Leyenda">
              {['conciliado', 'extracto_pendiente', 'falta_clave', 'sin_extracto'].map((k) => (
                <li key={k}><span aria-hidden="true">{ESTADOS_CELDA[k].simbolo}</span> {ESTADOS_CELDA[k].texto}</li>
              ))}
            </ul>

            {celdaDetalle && cuentaDetalle && (
              <div className="mt-3 rounded-xl bg-paper border border-line p-3" role="region" aria-label="Detalle del mes">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold capitalize">{cuentaDetalle.nombre} · {nombreMes(celdaDetalle.mes)}</p>
                    <p className="text-xs font-medium mt-0.5">
                      <span aria-hidden="true">{estadoCelda(celdaDetalle.estado).simbolo}</span> {estadoCelda(celdaDetalle.estado).texto}
                    </p>
                  </div>
                  <button onClick={() => setDetalle(null)} aria-label="Cerrar detalle" className="w-11 h-11 flex items-center justify-center text-ink-soft">
                    <X size={16} />
                  </button>
                </div>
                <p className="text-xs text-ink-soft mt-2">
                  {celdaDetalle.movimientos} {celdaDetalle.movimientos === 1 ? 'movimiento' : 'movimientos'} · {celdaDetalle.conciliados} conciliados · {celdaDetalle.por_confirmar} por confirmar
                  {celdaDetalle.extractos ? ` · ${celdaDetalle.extractos} ${celdaDetalle.extractos === 1 ? 'extracto' : 'extractos'}` : ''}
                </p>
                <div className="flex gap-2 mt-3">
                  {celdaDetalle.estado === 'extracto_pendiente' && (
                    <button onClick={() => irA('sinc-extractos')} className="rounded-xl bg-accent text-white text-xs font-semibold px-3.5 py-2.5">Conciliar</button>
                  )}
                  {celdaDetalle.estado === 'falta_clave' && (
                    <button onClick={() => { setMostrarClave(true); irA('sinc-extractos') }} className="rounded-xl bg-accent text-white text-xs font-semibold px-3.5 py-2.5">Poner clave</button>
                  )}
                  {celdaDetalle.estado === 'sin_extracto' && (
                    <button onClick={() => (conectado ? sincronizar() : navigate('/correos'))} className="rounded-xl bg-accent text-white text-xs font-semibold px-3.5 py-2.5">
                      {conectado ? 'Buscar extracto' : 'Conectar Gmail'}
                    </button>
                  )}
                  {celdaDetalle.movimientos > 0 && (
                    <button onClick={() => navigate('/movimientos')} className="rounded-xl border border-line text-xs font-semibold px-3.5 py-2.5">Ver movimientos</button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </Seccion>

      {/* d) Extractos por banco */}
      <Seccion id="sinc-extractos" titulo="Extractos">
        {avisoExt && <p className="text-xs text-danger mb-2" role="alert">{avisoExt}</p>}

        {(mostrarClave || tareas.some((t) => t.id === 'falta_clave')) && (
          <div id="sinc-clave" className="rounded-2xl bg-paper-raised border border-line p-4 mb-3">
            <p className="flex items-center gap-1.5 text-xs font-semibold mb-1"><KeyRound size={13} /> Clave del PDF</p>
            <p className="text-xs text-ink-soft mb-2">
              {claveConfigurada ? 'Hay una clave guardada.' : 'Normalmente es tu cédula.'} Se guarda cifrada y no se muestra de nuevo.
            </p>
            <div className="flex gap-2">
              <input
                type="password"
                autoComplete="off"
                value={claveInput}
                onChange={(e) => setClaveInput(e.target.value)}
                placeholder={claveConfigurada ? 'Nueva clave' : 'Clave (ej. tu cédula)'}
                aria-label="Clave del PDF"
                className="flex-1 min-w-0 rounded-xl border border-line bg-paper px-3 py-2 text-sm outline-none focus:border-accent"
              />
              <button onClick={guardarClave} disabled={!claveInput.trim()} className="px-4 rounded-xl bg-ink text-paper text-sm font-semibold disabled:opacity-50">
                Guardar
              </button>
            </div>
          </div>
        )}

        {!conectado ? (
          <div className="rounded-2xl bg-paper-raised border border-line p-5 text-center">
            <p className="text-sm font-semibold">Conecta Gmail para traer tus extractos</p>
            <button onClick={() => navigate('/correos')} className="mt-3 rounded-xl bg-ink text-paper text-sm font-semibold px-5 py-2.5">Conectar Gmail</button>
          </div>
        ) : extractos.length === 0 ? (
          <div className="rounded-2xl bg-paper-raised border border-line p-5 text-center">
            <p className="text-sm text-ink-soft">Aún no encontré extractos en tu correo.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {agruparPorBanco(visibles).map((g) => (
              <div key={g.banco}>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-soft mb-1.5">
                  {g.banco} · {g.items.length}
                </p>
                <div className="flex flex-col gap-2.5">
                  {g.items.map((ex) => (
                    <FilaExtracto
                      key={ex.id}
                      ex={ex}
                      cuentas={cuentas}
                      cuentaId={cuentaElegida(ex)}
                      nombreCuenta={nombreCuenta(ex.cuenta_sugerida_id)}
                      ocupado={ocupados.has(ex.id)}
                      onCuenta={(id) => setCuentaPorExtracto((p) => ({ ...p, [ex.id]: id }))}
                      onConciliar={() => conciliar(ex)}
                      onVer={() => navigate('/conciliacion', { state: { historialId: ex.historial_id } })}
                      onClave={() => { setMostrarClave(true); irA('sinc-clave') }}
                      onIgnorar={() => ignorar(ex)}
                    />
                  ))}
                </div>
              </div>
            ))}
            {extractos.length > EXTRACTOS_VISIBLES && (
              <button onClick={() => setVerTodos((v) => !v)} className="border border-line rounded-xl py-2.5 text-sm font-semibold">
                {verTodos ? 'Ver menos' : `Ver los ${extractos.length} extractos`}
              </button>
            )}
          </div>
        )}

        {conectado && (
          ignorados === null ? (
            <button onClick={verIgnorados} className="text-xs text-ink-soft mt-3 underline">Ver extractos ignorados</button>
          ) : (
            <div className="mt-3 rounded-2xl border border-line divide-y divide-line">
              {ignorados.length === 0 && <p className="text-xs text-ink-soft p-3">No hay extractos ignorados.</p>}
              {ignorados.map((ex) => (
                <div key={ex.id} className="p-3">
                  <p className="text-sm font-medium">{ex.banco || BANCO_SIN_IDENTIFICAR} · {ex.periodo || ex.asunto}</p>
                  <p className="text-xs text-ink-soft">{textoEstadoExtracto(ex)}</p>
                </div>
              ))}
            </div>
          )
        )}
      </Seccion>

      {/* e) Por categorizar */}
      <Seccion
        id="sinc-categorizar"
        titulo={`Por categorizar${cola.total ? ` (${cola.total})` : ''}`}
        ayuda="Elige la categoría y la recuerdo para ese comercio."
      >
        {cola.items.length === 0 ? (
          <div className="rounded-2xl bg-paper-raised border border-line p-5 text-center">
            <p className="text-sm text-ink-soft">Nada por categorizar.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2.5">
            {cola.items.map((m) => (
              <div key={m.id} className="rounded-2xl bg-paper-raised border border-line p-3.5" data-testid={`cat-${m.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold truncate">{m.descripcion}</p>
                    <p className="text-xs text-ink-soft">
                      {m.categoria === 'Otros' ? 'Sin categoría' : `Puse ${iconoDe(m.categoria)} ${m.categoria}`}
                    </p>
                  </div>
                  <p className="text-sm font-bold shrink-0">{fmt(m.monto)}</p>
                </div>
                <select
                  value=""
                  disabled={ocupados.has(m.id)}
                  onChange={(e) => categorizar(m, e.target.value)}
                  aria-label={`Categoría de ${m.descripcion}`}
                  className="w-full mt-2.5 rounded-xl border border-line bg-paper px-3 py-2.5 text-sm"
                >
                  <option value="">{m.categoria === 'Otros' ? 'Elige la categoría' : `Confirmar o cambiar (${m.categoria})`}</option>
                  {nombres.map((n) => (
                    <option key={n} value={n}>{iconoDe(n)} {n}</option>
                  ))}
                </select>
                <label className="flex items-center gap-2 mt-2 text-xs text-ink-soft min-h-[32px]">
                  <input
                    type="checkbox"
                    checked={recordar[m.id] !== false}
                    onChange={(e) => setRecordar((r) => ({ ...r, [m.id]: e.target.checked }))}
                    className="w-4 h-4 accent-[var(--c-accent)]"
                  />
                  Recordar para este comercio{m.patron ? ` (${m.patron})` : ''}
                </label>
              </div>
            ))}
            {cola.items.length < cola.total && (
              <button onClick={masPorCategorizar} className="border border-line rounded-xl py-2.5 text-sm font-semibold">Cargar más</button>
            )}
          </div>
        )}
      </Seccion>

      </div>
      </div>

      <p className="mx-6 mt-8 text-xs text-ink-soft text-center">
        <button onClick={() => navigate('/correos')} className="underline">Correos bancarios</button>
        {' · '}
        <button onClick={() => navigate('/conexiones')} className="underline">Estado de las conexiones</button>
      </p>

      {crearBanco && (
        <CrearCuentaBanco
          banco={crearBanco}
          onClose={() => setCrearBanco(null)}
          onCreada={() => {
            setCrearBanco(null)
            cargar()
          }}
        />
      )}
    </div>
  )
}

function FilaExtracto({ ex, cuentas, cuentaId, nombreCuenta, ocupado, onCuenta, onConciliar, onVer, onClave, onIgnorar }) {
  const banco = ex.banco || BANCO_SIN_IDENTIFICAR
  const sinBanco = !ex.banco
  const puedeConciliar = ex.estado === 'nuevo'
  return (
    <div className="rounded-2xl bg-paper-raised border border-line p-3.5" data-testid={`extracto-${ex.id}`}>
      <div className="flex items-start gap-3">
        <FileText size={18} className="text-accent shrink-0 mt-0.5" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold truncate">{banco}{ex.periodo ? ` · ${ex.periodo}` : ''}</p>
          <p className="text-xs text-ink-soft truncate">
            {nombreCuenta ? `Cuenta: ${nombreCuenta}` : 'Cuenta sin elegir'}
          </p>
          <p className={`text-xs font-medium mt-0.5 ${ex.estado === 'falta_clave' || ex.estado === 'error' ? 'text-danger' : ex.estado === 'procesado' ? 'text-cuadra' : 'text-accent'}`}>
            {textoEstadoExtracto(ex)}
          </p>
        </div>
      </div>

      {puedeConciliar && (
        <select
          value={cuentaId}
          onChange={(e) => onCuenta(e.target.value)}
          aria-label={`Cuenta del extracto ${banco}`}
          required
          className="w-full mt-3 rounded-xl border border-line bg-paper px-3 py-2 text-xs"
        >
          <option value="">{sinBanco ? 'Elige la cuenta (obligatorio)' : 'Elige la cuenta'}</option>
          {cuentas.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre}{c.id === ex.cuenta_sugerida_id ? ' (sugerida)' : ''}
            </option>
          ))}
        </select>
      )}

      <div className="flex gap-2 mt-3">
        {ex.estado === 'procesado' && ex.historial_id && (
          <button onClick={onVer} className="flex-1 border border-line rounded-xl py-2.5 text-sm font-semibold">Ver conciliación</button>
        )}
        {puedeConciliar && (
          <button
            onClick={onConciliar}
            disabled={ocupado || !cuentaId}
            className="flex-1 bg-accent text-white font-semibold rounded-xl py-2.5 text-sm disabled:opacity-50"
          >
            {ocupado ? 'Conciliando...' : 'Conciliar'}
          </button>
        )}
        {ex.estado === 'falta_clave' && (
          <button onClick={onClave} className="flex-1 bg-accent text-white font-semibold rounded-xl py-2.5 text-sm">Poner clave</button>
        )}
        {ex.estado !== 'procesado' && (
          <button onClick={onIgnorar} className="px-4 rounded-xl border border-line text-sm text-ink-soft" aria-label={`Ignorar extracto ${banco}`}>
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  )
}
