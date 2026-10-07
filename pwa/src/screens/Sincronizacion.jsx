import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { useEstadoLista } from '../lib/useEstadoLista'
import {
  ArrowLeft, CheckCheck, CheckCircle2, ChevronLeft, ChevronRight, FileCheck2, FileText, KeyRound, Mail, Plug, RefreshCw, Tag,
  Upload, Wallet, X,
} from 'lucide-react'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { useCategorias } from '../lib/CategoriasContext'
import { useCuentas } from '../lib/CuentasContext'
import { haceCuanto, marcarSincronizado, resumenSync, sincronizarTodo, tocaSincronizar } from '../lib/sincronizarGmail'
import {
  BANCO_SIN_IDENTIFICAR, agruparPorBanco, conciliarExtracto, estadoCelda, ESTADOS_CELDA, nombreMes,
  moverMes, nombresDesambiguados, resumenTareas, separarExtractos, textoEstadoExtracto,
} from '../lib/sincronizacion'
import { cantidadDe, pasoActual, sinDatos, tareasDeBloque } from '../lib/centro'
import BarraProgreso from '../components/BarraProgreso'
import BloqueCentro from '../components/BloqueCentro'
import ConexionGmail from '../components/ConexionGmail'
import CorreosPorRevisar from '../components/CorreosPorRevisar'
import CrearCuentaBanco from '../components/CrearCuentaBanco'
import ExtractosYaConciliados from '../components/ExtractosYaConciliados'
import Hoja from '../components/Hoja'
import PasosCentro from '../components/PasosCentro'
import SubirArchivos from '../components/SubirArchivos'
import Conexiones from './Conexiones'
import { mensajeAmable } from '../lib/mensajes'

// "Traer movimientos": UN solo centro para todo lo que trae movimientos a CuadraMe.
//   Arriba: estado y «Sincronizar todo».  Luego tres bloques plegables con contador:
//   Desde tu correo (Gmail) · Subir archivos (PDF/Excel/CSV) · Por revisar.
// Todo lo que muestra viene de GET /sincronizacion/estado (una llamada) más lo propio de cada
// bloque; las rutas viejas (/correos, /conciliacion, /importar, /conexiones) redirigen aquí.

const EXTRACTOS_VISIBLES = 6

function irA(id) {
  setTimeout(() => {
    const el = typeof document !== 'undefined' ? document.getElementById(id) : null
    el?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }, 60)
}

// Subsección dentro de un bloque: título corto, contador y su propio «Todo al día».
function Sub({ id, titulo, cuenta = 0, children }) {
  return (
    <div id={id} className="mt-5 scroll-mt-4">
      <h3 className="text-[13px] font-semibold flex items-center gap-2">
        {titulo}
        {cuenta > 0 && <span className="text-accent" aria-label={`${cuenta} pendientes`}>{cuenta}</span>}
      </h3>
      <div className="mt-2">{children}</div>
    </div>
  )
}

function AlDia({ texto = 'Todo al día' }) {
  return (
    <p className="flex items-center gap-1.5 text-xs text-ink-soft rounded-xl bg-paper border border-line px-3 py-2.5">
      <CheckCircle2 size={14} className="text-cuadra shrink-0" aria-hidden="true" /> {texto}
    </p>
  )
}

const ICONO_TAREA = {
  falta_clave: KeyRound,
  extractos_por_conciliar: FileCheck2,
  sin_cuenta: Wallet,
  movimientos_por_categorizar: Tag,
  movimientos_por_confirmar: CheckCheck,
  correos_por_revisar: Mail,
}

export default function Sincronizacion() {
  const navigate = useNavigate()
  const location = useLocation()
  const volver = useVolver('/')
  const { cuentas } = useCuentas() || { cuentas: [] }
  const { nombres = [], iconoDe = () => '💳' } = useCategorias() || {}
  const { fmt } = useBloqueo()
  const llegada = location.state || null

  const [estado, setEstado] = useState(null)
  const [gmail, setGmail] = useState(null)
  const [extractos, setExtractos] = useState([])
  const [correos, setCorreos] = useState([])
  const [ignorados, setIgnorados] = useState(null) // extractos ignorados; null = no cargados
  const [correosIgnorados, setCorreosIgnorados] = useState(null)
  const [verTodos, setVerTodos] = useState(false)
  const [cola, setCola] = useState({ items: [], total: 0 })
  const [cargando, setCargando] = useState(true)
  const raiz = useRef(null)
  useEstadoLista('/sincronizacion', { contenedorRef: raiz, listo: !cargando }) // al volver, misma posición
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
  const [abiertos, setAbiertos] = useState({
    correo: llegada?.abrir === 'correo', subir: llegada?.abrir === 'subir', revisar: llegada?.abrir === 'revisar',
  })
  const [subir, setSubir] = useState({}) // lo que pide abrir el bloque «Subir archivos»
  const [verEstado, setVerEstado] = useState(llegada?.abrir === 'estado')
  const montado = useRef(true)
  const iniciado = useRef(false)
  const autoSync = useRef(false)

  useEffect(() => {
    montado.current = true
    return () => {
      montado.current = false
    }
  }, [])

  // Ventana de meses: null = los más recientes. Se desplaza con "Antes"/"Después"; si el
  // servidor no soporta `hasta` (devuelve siempre la misma ventana) se esconden los botones.
  const [hasta, setHasta] = useState(null)
  const [ventanaFija, setVentanaFija] = useState(false)
  const hastaRef = useRef(null)

  const cargar = useCallback(async () => {
    try {
      const [est, gm, ex, clave, porCat, pend] = await Promise.all([
        api.sincronizacionEstado(hastaRef.current),
        api.gmailEstado().catch(() => null),
        api.extractosCorreo().catch(() => []),
        api.clavePdfEstado().catch(() => ({})),
        api.sincronizacionPorCategorizar(0).catch(() => ({ items: [], total: 0 })),
        api.correosPendientes().catch(() => []),
      ])
      if (!montado.current) return
      const ultimoMes = est?.meses?.[est.meses.length - 1]?.clave
      if (hastaRef.current && ultimoMes && ultimoMes !== hastaRef.current) {
        // el servidor ignoró la ventana pedida: no se puede desplazar
        hastaRef.current = null
        setHasta(null)
        setVentanaFija(true)
      }
      // Primera carga: se abre lo que tiene algo por hacer (nunca se cierra nada que el usuario abrió).
      // Va en el mismo lote que los datos, así no hay un instante con todo cerrado.
      if (!iniciado.current) {
        iniciado.current = true
        const t = est?.tareas || []
        const conectado = Boolean(gm?.conectado)
        setAbiertos((a) => ({
          correo: a.correo || !conectado || tareasDeBloque(t, 'correo').length > 0,
          subir: a.subir || t.length === 0 || sinDatos({ estado: est, conectado }),
          revisar: true, // incluye la cuadrícula: es el panorama, se ve siempre
        }))
      }
      setEstado(est)
      setGmail(gm)
      setExtractos(Array.isArray(ex) ? ex : [])
      setCorreos(Array.isArray(pend) ? pend : [])
      setClaveConfigurada(Boolean(clave?.configurada))
      setCola({ items: porCat?.items || [], total: porCat?.total || 0 })
      setError('')
    } catch (err) {
      if (montado.current) setError(err.message || 'No se pudo cargar')
    } finally {
      if (montado.current) setCargando(false)
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  function moverVentana(delta) {
    const hoy = new Date()
    const mesActual = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}`
    const nuevo = moverMes(hastaRef.current || mesActual, delta * 6)
    const siguiente = nuevo >= mesActual ? null : nuevo // null = la ventana más reciente
    hastaRef.current = siguiente
    setHasta(siguiente)
    setDetalle(null)
    cargar()
  }

  // ── Bloques abiertos y llegadas desde las rutas viejas ─────────────
  const abrirBloque = useCallback((bloque, ancla) => {
    setAbiertos((a) => ({ ...a, [bloque]: true }))
    irA(ancla || `sinc-${bloque}`)
  }, [])

  function pedirSubir(pedido) {
    setSubir({ ...pedido, n: Date.now() })
    abrirBloque('subir')
  }

  // Al llegar (o volver a llegar) con state: abre el bloque que pidió la ruta vieja.
  useEffect(() => {
    const abrir = llegada?.abrir
    if (!abrir) return
    if (abrir === 'estado') {
      setVerEstado(true)
      return
    }
    if (abrir === 'subir' && (llegada.historialId || llegada.mes || llegada.cuentaId || llegada.manual)) {
      setSubir({ historialId: llegada.historialId, cuentaId: llegada.cuentaId, mes: llegada.mes, manual: llegada.manual, n: Date.now() })
    }
    abrirBloque(abrir)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key])

  // Sincronización automática al abrir (como máximo cada 6 horas), sin ruido si falla.
  useEffect(() => {
    if (cargando || autoSync.current) return
    autoSync.current = true
    if (gmail?.conectado && tocaSincronizar()) sincronizar(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cargando])

  // ── Sincronizar todo (Gmail por lotes) ─────────────────────────────
  const sincronizando = Boolean(progreso)

  async function sincronizar(silencioso = false) {
    if (progreso) return
    setErrorSync('')
    setResumen('')
    setProgreso({ leidos: 0, total_estimado: 0 })
    try {
      const r = await sincronizarTodo({
        onProgreso: (p) => montado.current && setProgreso({ leidos: p.leidos, total_estimado: p.total_estimado }),
      })
      if (!r?.ok) {
        if (silencioso !== true) setErrorSync(mensajeAmable(r?.error, { porDefecto: 'No pudimos traer tus correos. Intenta de nuevo.' }))
      } else {
        const leidos = r.leidos ? `Leí ${r.leidos} correos. ` : ''
        if (silencioso !== true) setResumen(`${leidos}${resumenSync(r)}`)
        marcarSincronizado()
        await cargar()
      }
    } catch (err) {
      if (silencioso !== true) setErrorSync(err.message || 'No pudimos traer tus movimientos. Intenta de nuevo.')
    } finally {
      if (montado.current) setProgreso(null)
    }
  }

  // ── Tareas ─────────────────────────────────────────────────────────
  function accionTarea(t) {
    switch (t.id) {
      case 'falta_clave':
        setMostrarClave(true)
        return abrirBloque('correo', 'sinc-clave')
      case 'extractos_por_conciliar':
        return abrirBloque('correo', 'sinc-extractos')
      case 'correos_por_revisar':
        return abrirBloque('correo', 'sinc-correos')
      case 'sin_cuenta':
        if (estado?.sin_cuenta?.length === 1) return setCrearBanco(estado.sin_cuenta[0].banco)
        return abrirBloque('revisar', 'sinc-cuentas')
      case 'movimientos_por_categorizar':
        return abrirBloque('revisar', 'sinc-categorizar')
      default:
        return navigate(t.ruta)
    }
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
      if (r.ok) {
        pedirSubir({ historialId: r.historialId, cuentaId: cuentaElegida(ex) })
        cargar()
      } else {
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

  async function verCorreosIgnorados() {
    try {
      const lista = await api.correosLista('ignorados', 0, 30)
      setCorreosIgnorados(Array.isArray(lista) ? lista : [])
    } catch (err) {
      setAvisoExt(err.message || 'No se pudieron cargar los correos ignorados')
    }
  }

  async function guardarClave() {
    if (!claveInput.trim()) return
    setAvisoExt('')
    try {
      await api.guardarClavePdf(claveInput.trim())
      setClaveInput('')
      setClaveConfigurada(true)
      setAvisoExt('Clave guardada. Toca «Sincronizar todo» para abrir esos extractos.')
    } catch (err) {
      setAvisoExt(err.message || 'No se pudo guardar la clave')
    }
  }

  async function borrarClave() {
    try {
      await api.borrarClavePdf()
      setClaveConfigurada(false)
    } catch (err) {
      setAvisoExt(err.message || 'No se pudo borrar la clave')
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
      <div className="flex-1 flex items-center justify-center" role="status" aria-live="polite">
        <p className="text-sm text-ink-soft">Cargando...</p>
      </div>
    )
  }

  if (error && !estado) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 px-8 text-center">
        <p className="text-sm text-danger" role="alert">{error}</p>
        <button onClick={() => { setCargando(true); cargar() }} className="text-sm text-accent font-medium min-h-[44px]">
          Reintentar
        </button>
      </div>
    )
  }

  const tareas = estado?.tareas || []
  const sinCuenta = estado?.sin_cuenta || []
  const meses = estado?.meses || []
  const filasCuentas = estado?.cuentas || []
  const nombreFila = nombresDesambiguados(filasCuentas, cuentas)
  const conectado = Boolean(gmail?.conectado)
  const ultima = haceCuanto(estado?.ultima_sync)
  const tareasCorreo = tareasDeBloque(tareas, 'correo')
  const tareasRevisar = tareasDeBloque(tareas, 'revisar')
  const nCorreos = cantidadDe(tareas, 'correos_por_revisar')
  const nConfirmar = cantidadDe(tareas, 'movimientos_por_confirmar')

  const celdaDetalle = detalle
    ? filasCuentas.find((c) => c.id === detalle.cuentaId)?.meses.find((m) => m.mes === detalle.mes)
    : null
  const cuentaDetalle = detalle ? filasCuentas.find((c) => c.id === detalle.cuentaId) : null

  // Lo ya conciliado no es pendiente: va aparte, plegado.
  const { pendientes, conciliados } = separarExtractos(extractos)
  const visibles = verTodos ? pendientes : pendientes.slice(0, EXTRACTOS_VISIBLES)
  const alternar = (b) => setAbiertos((a) => ({ ...a, [b]: !a[b] }))

  return (
    <div ref={raiz} className="flex-1 overflow-y-auto pb-8 screen-enter pantalla-ancha">
      {/* Arriba: estado y botón principal */}
      <header className="px-6 pantalla-top pb-1 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold">Traer movimientos</h1>
          <p className="text-sm text-ink-soft" data-testid="resumen-tareas">{resumenTareas(tareas)}</p>
        </div>
        <button
          onClick={() => setVerEstado(true)}
          className="shrink-0 flex items-center gap-1.5 text-xs font-semibold text-accent min-h-[44px] px-1"
        >
          <Plug size={14} aria-hidden="true" /> Conexiones
        </button>
      </header>

      {sinDatos({ estado, conectado }) && <PasosCentro paso={pasoActual({ conectado, tareas })} />}

      <div className="dos-col dos-col-4-7">
      <div className="col">
      <section className="mx-6 mt-3" aria-label="Sincronizar">
        {conectado ? (
          <button
            onClick={() => sincronizar()}
            disabled={sincronizando}
            className="w-full flex items-center justify-center gap-2 bg-ink text-paper font-semibold rounded-2xl py-3.5 text-[15px] disabled:opacity-60"
          >
            <RefreshCw size={16} className={sincronizando ? 'animate-spin' : ''} aria-hidden="true" />
            {sincronizando ? 'Sincronizando...' : 'Sincronizar todo'}
          </button>
        ) : (
          <button
            onClick={() => abrirBloque('correo')}
            className="w-full flex items-center justify-center gap-2 bg-ink text-paper font-semibold rounded-2xl py-3.5 text-[15px]"
          >
            <Mail size={16} aria-hidden="true" /> Conectar Gmail
          </button>
        )}
        <div aria-live="polite" role="status">
          {progreso && (
            <div className="mt-3">
              <BarraProgreso
                pct={progreso.total_estimado ? Math.min(100, Math.round((progreso.leidos / progreso.total_estimado) * 100)) : 0}
                label="Progreso de la sincronización"
                className="h-2 rounded-full bg-line overflow-hidden"
                fillClass=""
              />
              <p className="text-xs text-ink-soft mt-1.5">
                {progreso.total_estimado ? `Leí ${progreso.leidos} de ${progreso.total_estimado}` : 'Empezando...'}
              </p>
            </div>
          )}
          {resumen && !errorSync && !progreso && (
            <p className="text-sm font-semibold mt-3 rounded-2xl bg-cuadra-soft text-cuadra px-4 py-3">{resumen}</p>
          )}
        </div>
        {errorSync && <p className="text-xs text-danger mt-2" role="alert">{errorSync}</p>}
        {error && estado && <p className="text-xs text-danger mt-2" role="alert">{error}</p>}

        {tareas.length === 0 ? (
          <p className="flex items-center justify-center gap-1.5 text-xs text-ink-soft mt-3" data-testid="todo-al-dia">
            <CheckCircle2 size={14} className="text-cuadra" aria-hidden="true" />
            {ultima ? `Todo al día · última sincronización ${ultima}` : 'Todo al día'}
          </p>
        ) : (
          <ul className="flex flex-col gap-2 mt-3" aria-label="Por resolver">
            {tareas.map((t) => {
              const Icono = ICONO_TAREA[t.id] || CheckCheck
              return (
                <li key={t.id}>
                  <button
                    onClick={() => accionTarea(t)}
                    data-testid={`tarea-${t.id}`}
                    className="w-full rounded-2xl bg-paper-raised border border-line px-3.5 py-2.5 min-h-[48px] flex items-center gap-3 text-left"
                  >
                    <span className="w-8 h-8 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
                      <Icono size={16} aria-hidden="true" />
                    </span>
                    <span className="flex-1 min-w-0 text-sm font-semibold leading-tight">{t.titulo}</span>
                    <span className="text-sm font-bold text-accent" aria-label={`${t.cantidad} pendientes`}>{t.cantidad}</span>
                    <ChevronRight size={14} className="text-ink-soft shrink-0" aria-hidden="true" />
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {/* a) Desde tu correo */}
      <BloqueCentro
        id="sinc-correo"
        titulo="Desde tu correo"
        icono={Mail}
        cuenta={tareasCorreo.length}
        abierto={abiertos.correo}
        onToggle={() => alternar('correo')}
      >
        <ConexionGmail estado={gmail} onCambio={cargar} />

        {conectado && (
          <>
            <Sub id="sinc-correos" titulo="Notificaciones por revisar" cuenta={nCorreos}>
              {correos.length === 0 ? (
                <AlDia texto="No hay correos por revisar" />
              ) : (
                <CorreosPorRevisar
                  correos={correos}
                  onResuelto={(c) => {
                    setCorreos((prev) => prev.filter((x) => x.id !== c.id))
                    cargar()
                  }}
                  onCuentaCreada={cargar}
                />
              )}
              {correosIgnorados === null ? (
                <button onClick={verCorreosIgnorados} className="text-xs text-ink-soft mt-3 underline min-h-[32px]">Ver correos ignorados</button>
              ) : (
                <div className="mt-3 rounded-2xl border border-line divide-y divide-line">
                  {correosIgnorados.length === 0 && <p className="text-xs text-ink-soft p-3">No hay correos ignorados.</p>}
                  {correosIgnorados.map((c) => (
                    <div key={c.id} className="p-3">
                      <p className="text-sm font-medium truncate">{c.asunto || c.comercio}</p>
                      <p className="text-xs text-ink-soft truncate">{c.remitente}</p>
                    </div>
                  ))}
                </div>
              )}
            </Sub>

            <Sub id="sinc-extractos" titulo="Extractos encontrados" cuenta={pendientes.length}>
              {avisoExt && <p className="text-xs text-danger mb-2" role="alert">{avisoExt}</p>}

              {(mostrarClave || tareas.some((t) => t.id === 'falta_clave')) && (
                <div id="sinc-clave" className="rounded-2xl bg-paper border border-line p-4 mb-3">
                  <p className="flex items-center gap-1.5 text-xs font-semibold mb-1"><KeyRound size={13} aria-hidden="true" /> Clave del PDF</p>
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
                      className="flex-1 min-w-0 rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm outline-none focus:border-accent"
                    />
                    <button onClick={guardarClave} disabled={!claveInput.trim()} className="px-4 rounded-xl bg-ink text-paper text-sm font-semibold disabled:opacity-50">
                      Guardar
                    </button>
                  </div>
                  {claveConfigurada && (
                    <button onClick={borrarClave} className="text-xs text-danger mt-2 min-h-[32px]">Borrar la clave guardada</button>
                  )}
                </div>
              )}
              {!mostrarClave && !tareas.some((t) => t.id === 'falta_clave') && (
                <button onClick={() => setMostrarClave(true)} className="flex items-center gap-1 text-xs text-ink-soft mb-3 min-h-[32px]">
                  <KeyRound size={13} aria-hidden="true" /> Clave del PDF
                </button>
              )}

              {pendientes.length === 0 ? (
                <AlDia texto={conciliados.length ? 'No tienes extractos pendientes' : 'Aún no encontramos extractos en tu correo. Cuando tu banco te envíe uno, aparecerá aquí'} />
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
                            onVer={() => pedirSubir({ historialId: ex.historial_id })}
                            onClave={() => { setMostrarClave(true); irA('sinc-clave') }}
                            onIgnorar={() => ignorar(ex)}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                  {pendientes.length > EXTRACTOS_VISIBLES && (
                    <button onClick={() => setVerTodos((v) => !v)} className="border border-line rounded-xl py-2.5 text-sm font-semibold">
                      {verTodos ? 'Ver menos' : `Ver los ${pendientes.length} extractos`}
                    </button>
                  )}
                </div>
              )}

              <ExtractosYaConciliados
                items={conciliados}
                nombreCuenta={nombreCuenta}
                ocupados={ocupados}
                onVer={(ex) => pedirSubir({ historialId: ex.historial_id })}
                onRevisar={conciliar}
              />

              {ignorados === null ? (
                <button onClick={verIgnorados} className="text-xs text-ink-soft mt-3 underline min-h-[32px]">Ver extractos ignorados</button>
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
              )}
            </Sub>
          </>
        )}
      </BloqueCentro>

      {/* b) Subir archivos */}
      <BloqueCentro
        id="sinc-subir"
        titulo="Subir archivos"
        icono={Upload}
        cuenta={0}
        mostrarAlDia={false}
        abierto={abiertos.subir}
        onToggle={() => alternar('subir')}
      >
        <SubirArchivos inicial={subir} onImportado={cargar} />
      </BloqueCentro>
      </div>

      <div className="col">
      {/* c) Por revisar */}
      <BloqueCentro
        id="sinc-revisar"
        titulo="Por revisar"
        icono={CheckCheck}
        cuenta={tareasRevisar.length}
        abierto={abiertos.revisar}
        onToggle={() => alternar('revisar')}
      >
        <Sub id="sinc-confirmar" titulo="Por confirmar" cuenta={nConfirmar}>
          {nConfirmar === 0 ? (
            <AlDia texto="Nada por confirmar" />
          ) : (
            <button
              onClick={() => navigate('/movimientos?revisar=1')}
              className="w-full rounded-xl bg-accent text-white text-sm font-semibold py-2.5"
            >
              Confirmar si son tuyos ({nConfirmar})
            </button>
          )}
        </Sub>

        <Sub id="sinc-categorizar" titulo="Por categorizar" cuenta={cola.total}>
          {cola.items.length === 0 ? (
            <AlDia texto="Nada por categorizar" />
          ) : (
            <div className="flex flex-col gap-2.5">
              {cola.items.map((m) => (
                <div key={m.id} className="rounded-2xl bg-paper border border-line p-3.5" data-testid={`cat-${m.id}`}>
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
                    className="w-full mt-2.5 rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-sm"
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
        </Sub>

        <Sub id="sinc-cuentas" titulo="Cuentas por mes" cuenta={sinCuenta.length}>
          {filasCuentas.length === 0 ? (
            <p className="text-sm text-ink-soft">Aún no tienes cuentas.</p>
          ) : (
            <div className="rounded-2xl bg-paper border border-line p-3">
              {!ventanaFija && (
                <div className="flex items-center justify-between mb-2" aria-label="Ventana de meses">
                  <button onClick={() => moverVentana(-1)} className="flex items-center gap-1 text-xs font-semibold text-accent min-h-[40px] pr-3">
                    <ChevronLeft size={14} aria-hidden="true" /> Meses anteriores
                  </button>
                  {hasta && (
                    <button onClick={() => moverVentana(1)} className="flex items-center gap-1 text-xs font-semibold text-accent min-h-[40px] pl-3">
                      Meses siguientes <ChevronRight size={14} aria-hidden="true" />
                    </button>
                  )}
                </div>
              )}
              <div role="table" aria-label="Estado de cada cuenta en los últimos meses">
                <div role="row" className="grid grid-cols-[minmax(0,1.5fr)_repeat(6,minmax(0,1fr))] gap-1 items-end mb-1.5">
                  <span role="columnheader" className="text-[11px] text-ink-soft">Cuenta</span>
                  {meses.map((m) => (
                    <span key={m.clave} role="columnheader" className="text-[11px] text-ink-soft text-center capitalize">{m.etiqueta}</span>
                  ))}
                </div>
                {filasCuentas.map((c) => (
                  <div key={c.id} role="row" className="grid grid-cols-[minmax(0,1.5fr)_repeat(6,minmax(0,1fr))] gap-1 items-center mb-1">
                    <span role="rowheader" title={nombreFila[c.id]} className="text-xs font-medium leading-tight break-words line-clamp-3 pr-1">{nombreFila[c.id]}</span>
                    {c.meses.map((m) => {
                      const e = estadoCelda(m.estado)
                      const activa = detalle?.cuentaId === c.id && detalle?.mes === m.mes
                      return (
                        <div key={m.mes} role="cell" className="contents">
                          <button
                            onClick={() => setDetalle(activa ? null : { cuentaId: c.id, mes: m.mes })}
                            aria-pressed={activa}
                            aria-label={`${nombreFila[c.id]}, ${nombreMes(m.mes)}: ${e.texto}`}
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
                <div className="mt-3 rounded-xl bg-paper-raised border border-line p-3" role="region" aria-label="Detalle del mes">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold capitalize">{nombreFila[cuentaDetalle.id]} · {nombreMes(celdaDetalle.mes)}</p>
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
                  <div className="flex flex-wrap gap-2 mt-3">
                    {celdaDetalle.estado === 'extracto_pendiente' && (
                      <button onClick={() => abrirBloque('correo', 'sinc-extractos')} className="rounded-xl bg-accent text-white text-xs font-semibold px-3.5 py-2.5">Conciliar</button>
                    )}
                    {celdaDetalle.estado === 'falta_clave' && (
                      <button onClick={() => { setMostrarClave(true); abrirBloque('correo', 'sinc-clave') }} className="rounded-xl bg-accent text-white text-xs font-semibold px-3.5 py-2.5">Poner clave</button>
                    )}
                    {(celdaDetalle.estado === 'sin_extracto' || celdaDetalle.estado === 'vacio') && (
                      <button
                        onClick={() => pedirSubir({ cuentaId: cuentaDetalle.id, mes: celdaDetalle.mes })}
                        className="rounded-xl bg-accent text-white text-xs font-semibold px-3.5 py-2.5"
                      >
                        Subir el extracto de este mes
                      </button>
                    )}
                    {celdaDetalle.estado === 'sin_extracto' && (
                      <button onClick={() => (conectado ? sincronizar() : abrirBloque('correo'))} className="rounded-xl border border-line text-xs font-semibold px-3.5 py-2.5">
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
        </Sub>
      </BloqueCentro>
      </div>
      </div>

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

      {verEstado && (
        <Hoja onCerrar={() => setVerEstado(false)} titulo="Conexiones y estado" clasePanel="p-0 pb-6">
          {({ cerrar }) => (
            <>
              <h2 className="px-6 pt-6 text-lg font-bold">Conexiones y estado</h2>
              <Conexiones
                embebido
                alIr={(bloque, st) => {
                  cerrar()
                  if (bloque === 'subir' && st?.historialId) pedirSubir({ historialId: st.historialId })
                  else abrirBloque(bloque)
                }}
              />
            </>
          )}
        </Hoja>
      )}
    </div>
  )
}

function FilaExtracto({ ex, cuentas, cuentaId, nombreCuenta, ocupado, onCuenta, onConciliar, onVer, onClave, onIgnorar }) {
  const banco = ex.banco || BANCO_SIN_IDENTIFICAR
  const sinBanco = !ex.banco
  const puedeConciliar = ex.estado === 'nuevo'
  return (
    <div className="rounded-2xl bg-paper border border-line p-3.5" data-testid={`extracto-${ex.id}`}>
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
          className="w-full mt-3 rounded-xl border border-line bg-paper-raised px-3 py-2 text-xs"
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
