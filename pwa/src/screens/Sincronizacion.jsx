import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { useEstadoLista } from '../lib/useEstadoLista'
import {
  ArrowLeft, CalendarDays, CheckCircle2, ChevronLeft, ChevronRight, FileText, GraduationCap, KeyRound, ListChecks, Mail, Plug, X, Pencil,
} from 'lucide-react'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { useDialogos } from '../lib/DialogosContext'
import { useCategorias } from '../lib/CategoriasContext'
import { useCuentas } from '../lib/CuentasContext'
import { haceCuanto, marcarSincronizado, resumenSync, sincronizarCarriles, sincronizarTodo, tocaSincronizar } from '../lib/sincronizarGmail'
import { NOMBRE_CARRIL, resumenLectura, textoUltimaLectura } from '../lib/carriles'
import {
  BANCO_SIN_IDENTIFICAR, agruparPorBanco, conciliarExtracto, estadoCelda, ESTADOS_CELDA, nombreMes,
  moverMes, nombresDesambiguados, separarExtractos, textoEstadoExtracto,
} from '../lib/sincronizacion'
import { cantidadDe, sinDatos } from '../lib/centro'
import { construirPasos, estadoGeneral, obligatorios, progresoPasos, textoBusqueda } from '../lib/siguientePaso'
import PasoGuiado from '../components/PasoGuiado'
import AvisoSalud from '../components/AvisoSalud'
import EstadoPorCuenta from '../components/EstadoPorCuenta'
import BancoNoEsta, { EnlaceBancoNoEsta } from '../components/BancoNoEsta'
import { InterruptoresLectura } from '../components/CarrilesCorreo'
import ConexionGmail from '../components/ConexionGmail'
import CorreosYaRegistrados from '../components/CorreosYaRegistrados'
import CorreosDescartados, { FilaRecuperable, recuperarCorreo } from '../components/CorreosDescartados'
import CrearCuentaBanco from '../components/CrearCuentaBanco'
import EstadoClavePdf, { textoEstadoClave } from '../components/EstadoClavePdf'
import TodosLosExtractos from '../components/TodosLosExtractos'
import ExtractosAMedias from '../components/ExtractosAMedias'
import CambiarCuentaExtracto from '../components/CambiarCuentaExtracto'
import { extractosAMedias } from '../lib/retomar'
import BuscarExtractoPorAsunto from '../components/BuscarExtractoPorAsunto'
import MisReglasCorreo from '../components/MisReglasCorreo'
import CuadreEncadenado from '../components/CuadreEncadenado'
import PuntoDePartida from '../components/PuntoDePartida'
import { LEYENDA_COBERTURA, textoDetalleCelda } from '../lib/estadoTraer'
import { FILTRO_DE_TAREA } from '../lib/extractosVista'
import Hoja from '../components/Hoja'
import SubirArchivos from '../components/SubirArchivos'
import Conexiones from './Conexiones'
import { mensajeAmable } from '../lib/mensajes'
import SelectorCuentaBanco from '../components/SelectorCuentaBanco'
import { cuentaRecordada, productoDeTexto } from '../lib/cuentasBanco'
import { posponerPuntoDePartida, puntoDePartidaPospuesto } from '../lib/puntoPartida'

// «Traer movimientos»: un asistente, no un tablero. La pantalla muestra UN estado y UNA acción principal
// (lib/siguientePaso.js escoge cuál por prioridad) y, al resolverla, pasa sola a la siguiente. Al abrir, lee
// el correo, prueba la clave guardada y relee saldos sin que toques nada. Todo lo demás está detrás:
//   «Ver todo» (extractos, correos, cobertura por mes) · «Conexiones y claves» (Gmail, clave del PDF, otras formas de traer).
// Todo lo que muestra viene de GET /sincronizacion/estado (una llamada) más lo propio de cada hoja;
// las rutas viejas (/correos, /conciliacion, /importar, /conexiones) redirigen aquí.

const EXTRACTOS_VISIBLES = 6

// Las rutas viejas piden 'correo' (Gmail) o 'subir' (archivos): hoy abren «Ver todo» en su pestaña o la hoja del archivo.
const SECCION_DE_RUTA = { correo: 'movimientos', subir: 'extractos', movimientos: 'movimientos', 'correos-descartados': 'movimientos', extractos: 'extractos', conexion: 'conexion', revisar: 'revisar' }
const seccionDeRuta = (abrir) => SECCION_DE_RUTA[abrir] || null
const QUINCE_MIN = 15 * 60 * 1000 // al abrir: no se vuelve a leer el correo si se leyó hace menos de esto

function irA(id) {
  setTimeout(() => {
    const el = typeof document !== 'undefined' ? document.getElementById(id) : null
    el?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }, 60)
}

// Subsección dentro de un bloque: título corto, contador y su propio «Todo al día».
function Sub({ id, titulo, cuenta = 0, children }) {
  return (
    <div id={id} className="mt-6 pt-5 border-t border-line/50 scroll-mt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-soft flex items-center gap-2">
        {titulo}
        {cuenta > 0 && <span className="text-accent normal-case" aria-label={`${cuenta} pendientes`}>{cuenta}</span>}
      </h3>
      <div className="mt-3">{children}</div>
    </div>
  )
}

function AlDia({ texto = 'Todo al día' }) {
  return (
    <p className="flex items-center gap-2 text-xs text-ink-soft py-1.5">
      <CheckCircle2 size={16} className="text-cuadra shrink-0" aria-hidden="true" /> {texto}
    </p>
  )
}

export default function Sincronizacion() {
  const navigate = useNavigate()
  const location = useLocation()
  const volver = useVolver('/')
  const { cuentas, recargar: recargarCuentas } = useCuentas() || { cuentas: [] }
  const { nombres = [], iconoDe = () => '💳' } = useCategorias() || {}
  const { fmt } = useBloqueo()
  const { confirmar, avisar } = useDialogos() || {}
  const llegada = location.state || null

  const [estado, setEstado] = useState(null)
  const [gmail, setGmail] = useState(null)
  const [extractos, setExtractos] = useState([])
  const [ignorados, setIgnorados] = useState(null) // extractos ignorados; null = no cargados
  const [correosIgnorados, setCorreosIgnorados] = useState(null)
  const [verTodos, setVerTodos] = useState(false)
  // Filtros de «Todos los extractos» (los abren «Por hacer» y la cobertura por mes).
  const [filtroExt, setFiltroExt] = useState({ estados: [], cuenta: '', mes: '', texto: '' })
  const [cola, setCola] = useState({ items: [], total: 0 })
  const [cargando, setCargando] = useState(true)
  const raiz = useRef(null)
  useEstadoLista('/sincronizacion', { contenedorRef: raiz, listo: !cargando }) // al volver, misma posición
  const [error, setError] = useState('')
  const [progreso, setProgreso] = useState(null)
  const [resumen, setResumen] = useState('')
  const [errorSync, setErrorSync] = useState('')
  const [errorReleer, setErrorReleer] = useState('')
  // Cada uso del correo tiene su propia lectura, resultado y error (si falla uno, el otro sigue).
  const [leyendo, setLeyendo] = useState({})
  const [resultadosCarril, setResultadosCarril] = useState({})
  const [erroresCarril, setErroresCarril] = useState({})
  const [guardandoLectura, setGuardandoLectura] = useState({})
  const [detalle, setDetalle] = useState(null) // { cuentaId, mes }
  const [crearBanco, setCrearBanco] = useState(null)
  const [elegirBanco, setElegirBanco] = useState(false)
  const [bancoNoEsta, setBancoNoEsta] = useState(null) // «Mi banco no está» desde una fila: null = cerrado, texto = banco
  const [cuentaPorExtracto, setCuentaPorExtracto] = useState({})
  const [ocupados, setOcupados] = useState(new Set())
  const [avisoExt, setAvisoExt] = useState('')
  const [releyendo, setReleyendo] = useState(new Set()) // historiales que se están releyendo
  const [resultadosReleer, setResultadosReleer] = useState({}) // {historialId: {ok, texto}}
  const [cambiandoCuenta, setCambiandoCuenta] = useState(null) // { historialId, titulo, cuentaId, destino }
  const [claveInfo, setClaveInfo] = useState({}) // GET /correos/clave-pdf (nunca trae la clave)
  const [probandoClave, setProbandoClave] = useState(false)
  const [pruebaClave, setPruebaClave] = useState({ resultado: null, mensaje: '', error: '' })
  const [pospuestoPP, setPospuestoPP] = useState(() => puntoDePartidaPospuesto())
  const [, setPpRecien] = useState(false) // acaba de elegir: se queda a la vista con su resumen
  const [recordar, setRecordar] = useState({}) // id -> false cuando la casilla se desmarca
  // La hoja abierta (null = ninguna): todo | conexion | clave | categorizar | subir | asunto | punto.
  const [hoja, setHoja] = useState(() => (/[?&]gmail=/.test(location.search || '') || seccionDeRuta(llegada?.abrir) === 'conexion' ? 'conexion' : null))
  const [tab, setTab] = useState(() => (seccionDeRuta(llegada?.abrir) === 'movimientos' ? 'correos' : 'extractos'))
  const [fase, setFase] = useState(null) // qué se está leyendo: movimientos | extractos | correo | clave | saldos
  const [recien, setRecien] = useState(false) // acaba de resolverse un paso
  const maxPasos = useRef(0)
  const previoPrincipal = useRef(null)
  const estadoRef = useRef(null)
  const [erroresInterruptor, setErroresInterruptor] = useState({})
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
      const [est, gm, ex, clave, porCat] = await Promise.all([
        api.sincronizacionEstado(hastaRef.current),
        api.gmailEstado().catch(() => null),
        api.extractosCorreo().catch(() => []),
        api.clavePdfEstado().catch(() => ({})),
        api.sincronizacionPorCategorizar(0).catch(() => ({ items: [], total: 0 })),
      ])
      if (!montado.current) return
      const ultimoMes = est?.meses?.[est.meses.length - 1]?.clave
      if (hastaRef.current && ultimoMes && ultimoMes !== hastaRef.current) {
        // el servidor ignoró la ventana pedida: no se puede desplazar
        hastaRef.current = null
        setHasta(null)
        setVentanaFija(true)
      }
      iniciado.current = true
      setEstado(est)
      setGmail(gm)
      setExtractos(Array.isArray(ex) ? ex : [])
      setClaveInfo(clave && typeof clave === 'object' ? clave : {})
      setCola({ items: porCat?.items || [], total: porCat?.total || 0 })
      setError('')
    } catch (err) {
      if (montado.current) setError(err.message || 'No se pudo cargar. Revisa tu conexión e intenta de nuevo.')
    } finally {
      if (montado.current) setCargando(false)
    }
  }, [])

  // Una vez al abrir: si una cuenta tiene extracto con su saldo inicial y nadie registró con cuánto empezó, la app lo
  // registra sola (idempotente en el servidor) y lo avisa con «Deshacer».
  useEffect(() => {
    Promise.resolve(api.cuadreSaldoInicialAuto?.())
      .then((r) => {
        const hechos = r?.registrados || []
        if (!hechos.length) return
        recargarCuentas?.()
        cargar()
        hechos.forEach((h) => avisar?.(h.texto, 'info', {
          accion: {
            texto: 'Deshacer',
            onClick: () => Promise.resolve(api.cuadreDeshacer(h.movimiento_id)).then(() => { recargarCuentas?.(); cargar() }).catch(() => {}),
          },
        }))
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    cargar()
    // Al abrir «Traer movimientos»: los extractos en error por clave que vinieron de un correo se reintentan solos.
    Promise.resolve(api.reintentarErroresExtractos?.())
      .then((r) => { if (r?.leidos && montado.current) cargar() })
      .catch(() => {})
    // Y los que quedaron por revisar con una lectura vieja se releen solos, una vez por mejora del lector.
    Promise.resolve(api.releerPendientes?.())
      .then((r) => { if (r?.cambiados && montado.current) cargar() })
      .catch(() => {})
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

  // ── Hojas y llegadas desde las rutas viejas ─────────────
  // Los nombres viejos (bloque + ancla) se traducen a la hoja que hoy tiene ese contenido.
  const abrirTodo = useCallback((pestana) => {
    if (pestana) setTab(pestana)
    setHoja('todo')
  }, [])
  const abrirBloque = useCallback((bloque, ancla) => {
    if (ancla === 'sinc-clave') return setHoja('clave')
    if (ancla === 'sinc-categorizar') return setHoja('categorizar')
    if (ancla === 'sinc-subir' || bloque === 'subir') return setHoja('subir')
    if (ancla === 'sinc-cuadre') return abrirTodo('meses')
    const seccion = seccionDeRuta(bloque)
    if (seccion === 'conexion') return setHoja('conexion')
    if (seccion === 'revisar') return setHoja('categorizar')
    return abrirTodo(seccion === 'movimientos' ? 'correos' : 'extractos')
  }, [abrirTodo])

  function pedirSubir(pedido) {
    setSubir({ ...pedido, n: Date.now() })
    abrirBloque('subir', 'sinc-subir')
  }

  // Al llegar (o volver a llegar) con state: abre el bloque que pidió la ruta vieja.
  useEffect(() => {
    const abrir = llegada?.abrir
    if (!abrir) return
    if (abrir === 'estado') {
      setVerEstado(true)
      return
    }
    if (seccionDeRuta(abrir) === 'extractos' && (llegada.historialId || llegada.mes || llegada.cuentaId || llegada.manual)) {
      setSubir({ historialId: llegada.historialId, cuentaId: llegada.cuentaId, mes: llegada.mes, manual: llegada.manual, n: Date.now() })
      setHoja('subir')
      return
    }
    abrirBloque(abrir, abrir === 'subir' ? 'sinc-subir' : undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key])

  // Al abrir, sin tocar nada: lee el correo (si no se leyó hace poco), prueba la clave guardada y relee saldos. Sin ruido si falla.
  useEffect(() => {
    if (cargando || autoSync.current) return
    autoSync.current = true
    if (gmail?.conectado && tocaSincronizar(QUINCE_MIN)) sincronizar(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cargando])

  // ── Traer todo ahora (Gmail por lotes) ─────────────────────────────
  const sincronizando = Boolean(progreso)

  async function sincronizar(silencioso = false) {
    if (progreso) return
    setErrorSync('')
    setResumen('')
    setErroresCarril({})
    setResultadosCarril({})
    setProgreso({ leidos: 0, total_estimado: 0 })
    const activos = lecturaActiva()
    try {
      if (silencioso === true) {
        // Al abrir la pantalla: una sola lectura (sin ruido ni errores por carril) con lo que esté encendido.
        const tipo = activos.movimientos && activos.extractos ? 'todo' : activos.movimientos ? 'movimientos' : activos.extractos ? 'extractos' : null
        if (tipo) {
          setFase(tipo === 'todo' ? 'correo' : tipo)
          const r = await sincronizarTodo({ tipo, onProgreso: (p) => montado.current && setProgreso({ leidos: p.leidos, total_estimado: p.total_estimado }) })
          if (r?.ok) {
            marcarSincronizado()
            await cargar()
            await despuesDeBuscar()
          }
        }
        return
      }
      // «Traer todo» es un atajo: corre cada uso por separado y dice cuál falló, sin frenar al otro.
      const res = await sincronizarCarriles({
        activos,
        onProgreso: (tipo, p) => {
          if (!montado.current) return
          setFase(tipo)
          setProgreso({ leidos: p.leidos, total_estimado: p.total_estimado })
          setLeyendo((l) => ({ ...l, [tipo]: { leidos: p.leidos, total_estimado: p.total_estimado } }))
        },
      })
      const errores = {}
      const textos = {}
      let leidos = 0
      const ultimos = []
      for (const tipo of Object.keys(res)) {
        if (res[tipo].error) errores[tipo] = mensajeAmable(res[tipo].error, { porDefecto: 'No pudimos leerlo. Intenta de nuevo.' })
        else {
          leidos += res[tipo].r.leidos || 0
          textos[tipo] = resumenLectura(tipo, res[tipo].r)
          ultimos.push(res[tipo].r)
        }
      }
      if (montado.current) {
        setErroresCarril(errores)
        setResultadosCarril(textos)
      }
      const fallaron = Object.keys(errores)
      if (silencioso !== true) {
        if (!Object.keys(res).length) setResumen('Tienes apagadas las dos lecturas del correo: no leí nada.')
        else if (fallaron.length === Object.keys(res).length) setErrorSync(errores[fallaron[0]])
        else {
          const nuevos = ultimos.reduce((s, r) => s + (r.nuevos || 0), 0)
          const ext = ultimos.reduce((s, r) => s + (r.extractos_encontrados ?? r.extractos_nuevos ?? 0), 0)
          setResumen(`${leidos ? `Leí ${leidos} correos. ` : ''}${resumenSync({ nuevos, extractos_encontrados: ext })}${fallaron.length ? ` No pude leer: ${fallaron.map((t) => NOMBRE_CARRIL[t]).join(' ni ')}.` : ''}`)
        }
      }
      if (fallaron.length < Object.keys(res).length) marcarSincronizado()
      await cargar()
      if (fallaron.length < Object.keys(res).length) await despuesDeBuscar()
    } catch (err) {
      if (silencioso !== true) setErrorSync(err.message || 'No pudimos traer tus movimientos. Intenta de nuevo.')
    } finally {
      if (montado.current) {
        setProgreso(null)
        setLeyendo({})
        setFase(null)
      }
    }
  }

  // Lo que se hace solo después de leer el correo: probar la clave guardada en los PDF que siguen cerrados
  // y releer saldos de los extractos nuevos. Nunca muestra la clave ni interrumpe si algo falla.
  async function despuesDeBuscar() {
    if (!montado.current) return
    setProgreso({ leidos: 0, total_estimado: 0 })
    try {
      const ci = await api.clavePdfEstado().catch(() => null)
      if (ci?.configurada && (ci.protegidos || 0) - (ci.abrieron || 0) > 0 && typeof api.probarClavePdf === 'function') {
        setFase('clave')
        await probarClave()
      }
    } catch { /* sin ruido: el paso «clave» seguirá a la vista */ }
    try {
      const faltanSaldos = (estadoRef.current?.cuadre_mensual || []).some((c) => c.sin_saldo?.length)
      if (faltanSaldos && typeof api.cuadreReleerSaldos === 'function') {
        setFase('saldos')
        await api.cuadreReleerSaldos()
        await cargar()
      }
    } catch { /* sin ruido */ }
  }

  // Lo que el usuario dejó encendido (por defecto los dos, como siempre).
  function lecturaActiva() {
    return { movimientos: gmail?.leer_movimientos !== false, extractos: gmail?.leer_extractos !== false }
  }

  // Un solo uso del correo: su propio botón, progreso, resultado y error.
  async function traerCarril(tipo) {
    if (progreso || leyendo[tipo]) return
    setErrorSync('')
    setResumen('')
    setErroresCarril((e) => ({ ...e, [tipo]: '' }))
    setResultadosCarril((r) => ({ ...r, [tipo]: '' }))
    setLeyendo((l) => ({ ...l, [tipo]: { leidos: 0, total_estimado: 0 } }))
    try {
      const r = await sincronizarTodo({
        tipo,
        onProgreso: (p) => montado.current && setLeyendo((l) => ({ ...l, [tipo]: { leidos: p.leidos, total_estimado: p.total_estimado } })),
      })
      if (!montado.current) return
      if (!r?.ok) setErroresCarril((e) => ({ ...e, [tipo]: mensajeAmable(r?.error, { porDefecto: 'No pudimos leerlo. Intenta de nuevo.' }) }))
      else {
        setResultadosCarril((x) => ({ ...x, [tipo]: resumenLectura(tipo, r) }))
        await cargar()
      }
    } catch (err) {
      if (montado.current) setErroresCarril((e) => ({ ...e, [tipo]: err.message || 'No pudimos leerlo. Intenta de nuevo.' }))
    } finally {
      if (montado.current) setLeyendo((l) => ({ ...l, [tipo]: undefined }))
    }
  }

  // «Releer los últimos 60 días»: lectura de movimientos con ventana larga (el servidor la limita a una por hora).
  async function releerMovimientos() {
    if (progreso || leyendo.movimientos) return
    setErrorReleer('')
    setLeyendo((l) => ({ ...l, movimientos: { leidos: 0, total_estimado: 0 } }))
    try {
      const r = await sincronizarTodo({ completa: true, tipo: 'movimientos', dias: 60, releer: true })
      if (!montado.current) return
      if (!r?.ok) setErrorReleer(mensajeAmable(r?.error, { porDefecto: 'No pudimos releer. Intenta de nuevo.' }))
      else {
        setResultadosCarril((x) => ({ ...x, movimientos: resumenLectura('movimientos', r) }))
        await cargar()
      }
    } catch (err) {
      if (montado.current) setErrorReleer(err.message || 'No pudimos releer. Intenta de nuevo.')
    } finally {
      if (montado.current) setLeyendo((l) => ({ ...l, movimientos: undefined }))
    }
  }

  // Interruptor «Leer esto de mi correo» de cada uso.
  async function cambiarLectura(tipo, valor) {
    const campo = tipo === 'movimientos' ? 'leer_movimientos' : 'leer_extractos'
    setGuardandoLectura((g) => ({ ...g, [tipo]: true }))
    setErroresInterruptor((e) => ({ ...e, [tipo]: '' }))
    try {
      await api.gmailLectura({ [campo]: valor })
      if (montado.current) setGmail((g) => ({ ...(g || {}), [campo]: valor }))
      await cargar()
    } catch (err) {
      if (montado.current) setErroresInterruptor((e) => ({ ...e, [tipo]: err.message || 'No se pudo guardar el cambio. Intenta de nuevo.' }))
    } finally {
      if (montado.current) setGuardandoLectura((g) => ({ ...g, [tipo]: false }))
    }
  }

  // ── Tareas ─────────────────────────────────────────────────────────
  function accionTarea(t) {
    switch (t.id) {
      case 'falta_clave':
        return setHoja('clave')
      case 'extractos_por_conciliar':
        return abrirGrupoExtractos(FILTRO_DE_TAREA.extractos_por_conciliar)
      case 'correos_por_revisar':
        return navigate('/movimientos?filtro=por-revisar') // los movimientos del correo se aprueban en Movimientos
      case 'sin_cuenta':
        // «Bancos sin cuenta» vive SOLO en «Por hacer» (y en el resumen de arriba): con un banco abre
        // directo «Crear cuenta»; con varios, una hoja para elegir cuál.
        if (estado?.sin_cuenta?.length === 1) return setCrearBanco(estado.sin_cuenta[0].banco)
        return setElegirBanco(true)
      case 'movimientos_por_categorizar':
        return abrirBloque('revisar', 'sinc-categorizar')
      case 'extractos_sin_leer':
        return abrirGrupoExtractos(FILTRO_DE_TAREA.extractos_sin_leer)
      case 'extracto_cuenta_dudosa':
        return abrirGrupoExtractos([], 'sinc-todos-extractos', { texto: 'tarjeta' })
      case 'correos_descartados':
        return abrirTodo('correos')
      case 'cuadre_no_cuadra':
        return abrirBloque('extractos', 'sinc-cuadre')
      case 'posibles_duplicados':
        return navigate(t.ruta)
      default:
        return navigate(t.ruta)
    }
  }

  // ── Todos los extractos: abrir un grupo, acciones por fila ─────────
  // Abre la sección, deja solo ese estado (o ese mes y cuenta) y baja a la lista. `ancla` null = no mover la pantalla.
  function abrirGrupoExtractos(estados = [], ancla = 'sinc-todos-extractos', extra = {}) {
    setFiltroExt({ estados, cuenta: '', mes: '', texto: '', ...extra })
    abrirTodo('extractos')
    if (ancla) irA(ancla)
  }

  async function reintentarFila(it) {
    if (!it.extracto_id || ocupados.has(it.id)) return
    setOcupados((s) => new Set(s).add(it.id))
    setAvisoExt('')
    try {
      const r = await api.reintentarExtractoCorreo(it.extracto_id)
      setAvisoExt(r?.mensaje || (r?.ok ? 'Listo: ya lo podemos revisar.' : 'No pudimos leerlo todavía.'))
      await cargar()
    } catch (err) {
      setAvisoExt(mensajeAmable(err?.message, { porDefecto: 'No pudimos intentarlo ahora. Revisa tu conexión e intenta de nuevo.' }))
    } finally {
      if (montado.current) {
        setOcupados((s) => {
          const n = new Set(s)
          n.delete(it.id)
          return n
        })
      }
    }
  }

  // «Releer este extracto»: lo vuelve a leer con las mejoras sin perder lo ya importado.
  async function releerFila(historialId) {
    if (!historialId || releyendo.has(historialId)) return
    setReleyendo((s) => new Set(s).add(historialId))
    setResultadosReleer((r) => ({ ...r, [historialId]: null }))
    let resultado
    try {
      const r = await api.releerExtracto(historialId)
      resultado = { ok: true, texto: r?.mensaje || 'Listo, lo releí.' }
      await cargar()
    } catch (err) {
      resultado = { ok: false, texto: mensajeAmable(err?.message, { porDefecto: 'No pudimos releerlo ahora. Intenta de nuevo en un rato.' }) }
    } finally {
      if (montado.current) setReleyendo((s) => { const n = new Set(s); n.delete(historialId); return n })
    }
    if (montado.current) setResultadosReleer((r) => ({ ...r, [historialId]: resultado }))
  }

  // «Reintentar» (error con correo) y «Quitar de la lista» (solo filas en error; nunca conciliados).
  async function accionErrorFila(accion, it) {
    if (ocupados.has(it.id)) return
    const ids = it.historiales_error?.length ? it.historiales_error : (it.historial_id ? [it.historial_id] : [])
    if (!ids.length) return
    if (accion !== 'reintentar' && confirmar) {
      const varios = ids.length > 1
      const ok = await confirmar(
        varios
          ? `Se quitan ${ids.length} extractos que no se pudieron leer. Lo que ya importaste no se toca y puedes volver a subirlos cuando quieras.`
          : 'Se quita este extracto que no se pudo leer. Lo que ya importaste no se toca y puedes volver a subirlo cuando quieras.',
        { titulo: varios ? `¿Quitar ${ids.length} extractos de la lista?` : '¿Quitar este extracto de la lista?', confirmarTexto: 'Quitar', peligro: true },
      )
      if (!ok) return
    }
    setOcupados((s) => new Set(s).add(it.id))
    setAvisoExt('')
    try {
      if (accion === 'reintentar') {
        const r = await api.reintentarHistorialError(ids[0])
        setAvisoExt(r?.mensaje || (r?.ok ? 'Listo: ya lo podemos revisar.' : 'No pudimos leerlo todavía.'))
      } else {
        for (const id of ids) await api.quitarHistorialError(id)
        setAvisoExt(ids.length > 1 ? `Listo: quitamos ${ids.length} extractos de la lista.` : 'Listo: lo quitamos de la lista.')
      }
      await cargar()
    } catch (err) {
      setAvisoExt(mensajeAmable(err?.message, { porDefecto: 'No pudimos hacerlo ahora. Intenta de nuevo.' }))
    } finally {
      if (montado.current) {
        setOcupados((s) => {
          const n = new Set(s)
          n.delete(it.id)
          return n
        })
      }
    }
  }

  async function fijarMesFila(it, mes) {
    if (!it.extracto_id || !mes) return
    setAvisoExt('')
    try {
      await api.fijarMesExtracto(it.extracto_id, mes)
      await cargar()
    } catch (err) {
      setAvisoExt(mensajeAmable(err?.message, { porDefecto: 'No pudimos guardar el mes. Intenta de nuevo.' }))
    }
  }

  // El extracto de Gmail que está detrás de una fila (para conciliar con la cuenta que ya conocemos).
  const extractoDeFila = (it) => extractos.find((e) => e.id === it.extracto_id)
    || (it.extracto_id ? { id: it.extracto_id, cuenta_sugerida_id: it.cuenta_id, banco: it.banco, estado: 'nuevo' } : null)

  function accionFila(accion, it, destino = '') {
    switch (accion) {
      case 'releer':
        return releerFila(it.historial_id)
      case 'cambiar_cuenta':
        return setCambiandoCuenta({ historialId: it.historial_id, titulo: it.titulo, cuentaId: it.cuenta_id, destino })
      case 'ver':
        return pedirSubir({ historialId: it.historial_id })
      case 'revisar': {
        if (it.historial_id) return pedirSubir({ historialId: it.historial_id })
        const ex = extractoDeFila(it)
        if (ex && cuentaElegida(ex)) return conciliar(ex)
        setAvisoExt('Elige la cuenta de este extracto para poder revisarlo.')
        return abrirBloque('extractos', 'sinc-extractos-correo')
      }
      case 'revisar_de_nuevo': {
        const ex = extractoDeFila(it)
        return ex ? conciliar(ex) : null
      }
      case 'poner_clave':
        return setHoja('clave')
      case 'probar_clave':
        return probarClave(it.extracto_id)
      case 'intentar_de_nuevo':
        return reintentarFila(it)
      case 'reintentar':
      case 'quitar_de_la_lista':
        return accionErrorFila(accion, it)
      case 'subir_de_nuevo':
        return pedirSubir({ cuentaId: it.cuenta_id, manual: false })
      case 'mi_banco_no_esta':
        return setBancoNoEsta(it.banco || '')
      default:
        return null
    }
  }

  // ── Extractos ──────────────────────────────────────────────────────
  // Banco con varias cuentas sin ganadora: se usa la que la persona eligió antes para ese banco + tipo.
  const recordadaExt = (ex) => {
    if (!ex.pregunta_cuenta) return ''
    const id = cuentaRecordada(ex.banco, productoDeTexto(`${ex.asunto || ''} ${ex.archivo || ''}`), cuentas)
    return id && (!ex.cuentas_candidatas?.length || ex.cuentas_candidatas.includes(id)) ? id : ''
  }
  const cuentaElegida = (ex) => cuentaPorExtracto[ex.id] || ex.cuenta_sugerida_id || recordadaExt(ex) || ''
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
      setAvisoExt(err.message || 'No pudimos revisar el extracto')
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
      setAvisoExt(err.message || 'No se pudieron cargar los ignorados. Revisa tu conexión e intenta de nuevo.')
    }
  }

  const [recuperando, setRecuperando] = useState(null)
  async function recuperarIgnorado(c) {
    if (recuperando) return
    setRecuperando(c.id)
    try {
      setAvisoExt(await recuperarCorreo(c.id))
      setCorreosIgnorados((l) => (l || []).filter((x) => x.id !== c.id))
      cargar()
    } catch (err) {
      setAvisoExt(err.message || 'No se pudo recuperar el correo. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setRecuperando(null)
    }
  }

  async function verCorreosIgnorados() {
    try {
      const lista = await api.correosLista('ignorados', 0, 30)
      setCorreosIgnorados(Array.isArray(lista) ? lista : [])
    } catch (err) {
      setAvisoExt(err.message || 'No se pudieron cargar los correos ignorados. Revisa tu conexión e intenta de nuevo.')
    }
  }

  // Prueba la clave guardada AHORA (en un extracto o en todos los protegidos) y dice el resultado
  // con todas las letras: cuántos abrió y cuáles no. Nunca muestra la clave.
  async function probarClave(extractoId) {
    if (probandoClave || typeof api.probarClavePdf !== 'function') return
    setProbandoClave(true)
    setPruebaClave({ resultado: null, mensaje: '', error: '' })
    try {
      const r = await api.probarClavePdf(extractoId)
      if (!montado.current) return
      setPruebaClave({ resultado: r, mensaje: r?.mensaje || '', error: '' })
      await cargar()
    } catch (err) {
      if (montado.current) setPruebaClave({ resultado: null, mensaje: '', error: mensajeAmable(err?.message, { porDefecto: 'No pude probar la clave ahora. Intenta de nuevo.' }) })
    } finally {
      if (montado.current) setProbandoClave(false)
    }
  }

  async function guardarClave(valor) {
    const v = (valor || '').trim()
    if (!v) return
    setAvisoExt('')
    try {
      await api.guardarClavePdf(v)
      setClaveInfo((c) => ({ ...c, configurada: true }))
      setPruebaClave({ resultado: null, mensaje: '', error: '' })
      // Con extractos protegidos esperando, se prueba de una vez: así no queda la duda de si la cogió.
      const hayProtegidos = extractos.some((e) => e.estado === 'falta_clave') || (claveInfo.protegidos || 0) > 0
      if (hayProtegidos && typeof api.probarClavePdf === 'function') await probarClave()
      else setAvisoExt('Clave guardada. Toca «Traer todo ahora» para abrir esos extractos.')
    } catch (err) {
      setAvisoExt(err.message || 'No se pudo guardar la clave. Revisa tu conexión e intenta de nuevo.')
    }
  }

  async function borrarClave() {
    try {
      await api.borrarClavePdf()
      setClaveInfo((c) => ({ ...c, configurada: false }))
      setPruebaClave({ resultado: null, mensaje: '', error: '' })
    } catch (err) {
      setAvisoExt(err.message || 'No se pudo borrar la clave. Revisa tu conexión e intenta de nuevo.')
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
      setAvisoExt(err.message || 'No se pudo cambiar la categoría. Revisa tu conexión e intenta de nuevo.')
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

  // ── Lo pendiente, como pasos (una cosa a la vez) ────────────────────
  const tareas = estado?.tareas || []
  const sinCuenta = estado?.sin_cuenta || []
  const meses = estado?.meses || []
  const filasCuentas = estado?.cuentas || []
  const conectado = Boolean(gmail?.conectado)
  const aMedias = extractosAMedias(estado)
  const primerUso = sinDatos({ estado, conectado })
  const puntoPendiente = estado?.punto_partida?.definido === false && !pospuestoPP && (conectado || primerUso)
  const pasos = construirPasos({ tareas, aMedias, conectado, primerUso, claveConfigurada: Boolean(claveInfo.configurada), sinCuenta, puntoPendiente })
  const estadoG = estadoGeneral(pasos)
  const pendientesObl = obligatorios(pasos)
  const principal = pendientesObl[0] || null
  const sugerencia = estadoG.alDia || estadoG.casi ? pasos[0] || null : null
  const restantes = pendientesObl.length
  if (restantes === 0) maxPasos.current = 0
  else maxPasos.current = Math.max(maxPasos.current, restantes)
  const idPrincipal = principal?.id ?? null
  estadoRef.current = estado

  // «Listo ✓ — siguiente: …»: cuando el paso que se mostraba ya no está (lo resolviste, o se resolvió solo).
  useEffect(() => {
    if (cargando || !estado) return
    const antes = previoPrincipal.current
    if (antes && antes !== idPrincipal && !pendientesObl.some((p) => p.id === antes)) setRecien(true)
    previoPrincipal.current = idPrincipal
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idPrincipal, cargando, estado])
  useEffect(() => {
    if (!recien) return undefined
    const t = setTimeout(() => setRecien(false), 6000)
    return () => clearTimeout(t)
  }, [recien, idPrincipal])
  // La hoja de la clave se cierra sola cuando la clave ya resolvió ese paso.
  const faltaClave = pasos.some((p) => p.id === 'falta_clave')
  useEffect(() => {
    if (hoja !== 'clave' || faltaClave || !pruebaClave.resultado) return undefined
    const t = setTimeout(() => setHoja((h) => (h === 'clave' ? null : h)), 1600)
    return () => clearTimeout(t)
  }, [hoja, faltaClave, pruebaClave.resultado])

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

  const nombreFila = nombresDesambiguados(filasCuentas, cuentas)
  const ultima = haceCuanto(estado?.ultima_sync)
  const nCorreos = cantidadDe(tareas, 'correos_por_revisar')
  const punto = estado?.punto_partida

  const celdaDetalle = detalle
    ? filasCuentas.find((c) => c.id === detalle.cuentaId)?.meses.find((m) => m.mes === detalle.mes)
    : null
  const cuentaDetalle = detalle ? filasCuentas.find((c) => c.id === detalle.cuentaId) : null

  // Lo ya conciliado no es pendiente: va aparte.
  const { pendientes, conciliados } = separarExtractos(extractos)
  const todosExtractos = estado?.todos_extractos || null
  const visibles = verTodos ? pendientes : pendientes.slice(0, EXTRACTOS_VISIBLES)
  const activos = lecturaActiva()
  const verPorRevisar = () => navigate('/movimientos?filtro=por-revisar')
  const cerrarHoja = () => setHoja(null)

  // Lo que hace el botón grande de cada paso.
  function accionPaso(p) {
    setRecien(false)
    switch (p.id) {
      case 'conectar':
        return setHoja('conexion')
      case 'punto_partida':
        return setHoja('punto')
      case 'a_medias':
        return pedirSubir({ historialId: aMedias[0].historialId, cuentaId: aMedias[0].cuentaId })
      case 'extractos_por_conciliar': {
        // Con una sola cuenta clara se abre la revisión directo; si hay dudas, se pregunta en «Ver todo».
        const ex = pendientes.find((e) => e.estado === 'nuevo')
        if (ex && cuentaElegida(ex)) return conciliar(ex)
        if (ex) {
          setAvisoExt('Elige la cuenta de este extracto para poder revisarlo.')
          return abrirTodo('extractos')
        }
        return abrirGrupoExtractos(FILTRO_DE_TAREA.extractos_por_conciliar)
      }
      case 'movimientos_por_confirmar':
        return navigate('/movimientos?revisar=1')
      default:
        return accionTarea(p.tarea || { id: p.id })
    }
  }

  // Tocar un mes de «Estado por cuenta y mes»: abre la acción lógica de ese mes.
  function accionMes(cuenta, celda, vista) {
    const filtroMes = { cuenta: `c:${cuenta.id}`, mes: celda.mes }
    switch (vista.accion) {
      case 'ver':
      case 'revisar_error':
        return abrirGrupoExtractos([], 'sinc-todos-extractos', filtroMes)
      case 'importar': {
        const x = (celda.lista || []).find((l) => l.historial_id && l.estado_vista === 'por_revisar')
        if (x) return pedirSubir({ historialId: x.historial_id, cuentaId: cuenta.id })
        const y = (celda.lista || []).find((l) => l.extracto_id && l.acciones?.includes('revisar'))
        if (y) return accionFila('revisar', { ...y, cuenta_id: cuenta.id, historial_id: null })
        return abrirGrupoExtractos([], 'sinc-todos-extractos', filtroMes)
      }
      case 'clave':
        return setHoja('clave')
      case 'subir':
        return pedirSubir({ cuentaId: cuenta.id, mes: celda.mes })
      case 'pasar': {
        const o = (celda.en_otra_cuenta || [])[0]
        if (!o) return null
        return setCambiandoCuenta({ historialId: o.historial_id, titulo: o.titulo, cuentaId: o.desde_id, destino: cuenta.id })
      }
      default:
        return null
    }
  }

  const textoOcupado = sincronizando
    ? textoBusqueda({ fase: fase || 'correo', leidos: progreso.leidos, total: progreso.total_estimado })
    : fase ? textoBusqueda({ fase }) : ''
  const pctBusqueda = sincronizando && progreso.total_estimado ? Math.min(100, Math.round((progreso.leidos / progreso.total_estimado) * 100)) : 0
  const errorPrincipal = errorSync || (error && estado ? error : '')

  const claveEl = (
    <EstadoClavePdf
      info={claveInfo}
      onGuardar={guardarClave}
      onBorrar={borrarClave}
      onProbar={() => probarClave()}
      probando={probandoClave}
      resultado={pruebaClave.resultado}
      mensaje={pruebaClave.mensaje}
      error={pruebaClave.error}
    />
  )

  const verEnTab = (k, texto, n) => (
    <button
      key={k}
      type="button"
      role="tab"
      aria-selected={tab === k}
      onClick={() => setTab(k)}
      data-testid={`tab-${k}`}
      className={`min-h-[44px] rounded-xl text-sm font-semibold px-2 ${tab === k ? 'bg-paper-raised ring-1 ring-line/60 text-ink' : 'text-ink-soft'}`}
    >
      {texto}{n > 0 ? ` · ${n}` : ''}
    </button>
  )

  return (
    <div ref={raiz} className="flex-1 overflow-y-auto pb-8 screen-enter pantalla-ancha">
      <header className="px-6 pantalla-top pb-1 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="flex-1 min-w-0 text-xl font-bold leading-tight">Traer movimientos</h1>
        <button
          onClick={() => setHoja('conexion')}
          data-testid="abrir-conexiones"
          className="shrink-0 flex items-center justify-center gap-1.5 text-xs font-semibold text-accent min-h-[44px] min-w-[44px] px-1"
        >
          <Plug size={16} aria-hidden="true" /> <span className="max-[400px]:sr-only">Conexiones y claves</span>
        </button>
      </header>

      <div className="dos-col dos-col-6-5">
        <div className="col">
          <AvisoSalud className="mx-6 mt-3" />
          <div className="mx-6 mt-3">
            <PasoGuiado
              estado={estadoG}
              progreso={progresoPasos(restantes, maxPasos.current)}
              paso={principal}
              siguientes={pendientesObl.slice(1)}
              recien={recien}
              onPaso={accionPaso}
              buscando={textoOcupado}
              pctBusqueda={pctBusqueda}
              onBuscar={() => (conectado ? sincronizar() : setHoja('conexion'))}
              puedeBuscar={conectado}
              conectado={conectado}
              ultima={ultima || ''}
              resumen={resumen || (hoja ? '' : avisoExt)}
              error={errorPrincipal}
              sugerencia={sugerencia}
              onSugerencia={accionPaso}
              onVerTodo={() => abrirTodo(tab)}
            />
          </div>
          <EstadoPorCuenta cuentas={filasCuentas} meses={meses} onMes={accionMes} className="mx-6 mt-5 mb-2" />
        </div>

        {/* Escritorio: lo que sigue y lo que hago solo. En el celular no se ve: una pregunta a la vez. */}
        <div className="col max-lg:!hidden">
          <aside className="mx-6 lg:ml-0 mt-3 rounded-3xl bg-paper-raised ring-1 ring-line/60 p-5" aria-label="Lo que hago solo">
            <h2 className="text-sm font-semibold">Lo que hago solo</h2>
            <ul className="mt-3 flex flex-col gap-2 text-sm text-ink-soft">
              <li className="flex items-start gap-2"><CheckCircle2 size={16} className="text-cuadra shrink-0 mt-0.5" aria-hidden="true" /> Leo tu correo cuando abres esta pantalla.</li>
              <li className="flex items-start gap-2"><CheckCircle2 size={16} className="text-cuadra shrink-0 mt-0.5" aria-hidden="true" /> Pruebo la clave guardada en tus PDF.</li>
              <li className="flex items-start gap-2"><CheckCircle2 size={16} className="text-cuadra shrink-0 mt-0.5" aria-hidden="true" /> Elijo la cuenta cuando solo hay una opción.</li>
            </ul>
            {pendientesObl.length > 1 && (
              <>
                <h2 className="text-sm font-semibold mt-5">Lo que sigue</h2>
                <ol className="mt-3 flex flex-col gap-1.5 text-sm" data-testid="lista-siguientes">
                  {pendientesObl.slice(1).map((p) => (
                    <li key={p.id} className="text-ink-soft">{p.titulo}</li>
                  ))}
                </ol>
              </>
            )}
          </aside>
        </div>
      </div>

      {cambiandoCuenta && (
        <CambiarCuentaExtracto
          historialId={cambiandoCuenta.historialId}
          titulo={cambiandoCuenta.titulo}
          cuentaActualId={cambiandoCuenta.cuentaId}
          destinoInicial={cambiandoCuenta.destino}
          cuentas={cuentas}
          onCerrar={() => setCambiandoCuenta(null)}
          onListo={(texto) => { setAvisoExt(texto); cargar(); recargarCuentas?.() }}
        />
      )}

      {/* ── Todo lo demás, detrás de una hoja ─────────────────────── */}
      {hoja === 'todo' && (
        <Hoja onCerrar={cerrarHoja} titulo="Ver todo">
          {() => (
            <>
              <h2 className="text-lg font-bold">Ver todo</h2>
              <div role="tablist" aria-label="Qué quieres ver" className="mt-3 grid grid-cols-3 gap-1 rounded-2xl bg-paper-raised/70 p-1 ring-1 ring-line/40">
                {verEnTab('extractos', 'Extractos', pendientes.length)}
                {verEnTab('correos', 'Correos', nCorreos)}
                {verEnTab('meses', 'Por mes', 0)}
              </div>

              {tab === 'extractos' && (
                <div role="tabpanel" aria-label="Extractos" className="mt-4" data-testid="seccion-extractos">
                  <ExtractosAMedias
                    lista={aMedias}
                    onSeguir={(x) => pedirSubir({ historialId: x.historialId, cuentaId: x.cuentaId })}
                    onCambiarCuenta={(x, destino) => setCambiandoCuenta({ historialId: x.historialId, titulo: `${x.cuenta}${x.mes ? ` · ${x.mes}` : ''}`, cuentaId: x.cuentaId, destino })}
                    onReleer={(x) => releerFila(x.historialId)}
                    releyendo={releyendo}
                    resultadosReleer={resultadosReleer}
                    className="mb-4"
                  />
                  {avisoExt && <p className="text-xs text-danger mb-2" role="alert">{avisoExt}</p>}
                  {(faltaClave || (claveInfo.protegidos || 0) > 0) && (
                    <button onClick={() => setHoja('clave')} className="flex items-center gap-1 text-xs text-ink-soft mb-3 min-h-[44px]">
                      <KeyRound size={16} aria-hidden="true" /> Clave del PDF{claveInfo.configurada ? ` · ${textoEstadoClave(claveInfo)}` : ''}
                    </button>
                  )}
            {pendientes.length === 0 ? (
              <AlDia texto={gmail?.leer_extractos === false ? 'Lectura apagada: no busco extractos en tu correo' : conciliados.length ? 'No tienes extractos pendientes' : 'Aún no encontramos extractos en tu correo. Cuando tu banco te envíe uno, aparecerá aquí'} />
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
                          onClave={() => setHoja('clave')}
                          claveConfigurada={Boolean(claveInfo.configurada)}
                          probando={probandoClave}
                          onProbarClave={() => probarClave(ex.id)}
                          onIgnorar={() => ignorar(ex)}
                        />
                      ))}
                    </div>
                  </div>
                ))}
                {pendientes.length > EXTRACTOS_VISIBLES && (
                  <button onClick={() => setVerTodos((v) => !v)} className="bg-paper rounded-xl min-h-[44px] text-sm font-semibold">
                    {verTodos ? 'Ver menos' : `Ver los ${pendientes.length} extractos`}
                  </button>
                )}
              </div>
            )}
                  <TodosLosExtractos
                    datos={todosExtractos}
                    filtro={filtroExt}
                    onFiltro={setFiltroExt}
                    onAccion={accionFila}
                    onFijarMes={fijarMesFila}
                    ocupados={ocupados}
                    releyendo={releyendo}
                    resultadosReleer={resultadosReleer}
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
                </div>
              )}

              {tab === 'correos' && (
                <div role="tabpanel" aria-label="Correos" className="mt-4" data-testid="seccion-correos">
                  {conectado ? (
                    <>
                      {nCorreos > 0 && (
                        <button
                          type="button"
                          onClick={verPorRevisar}
                          data-testid="ver-por-revisar"
                          className="w-full flex items-center justify-center gap-2 bg-accent text-paper-raised font-semibold rounded-xl min-h-[44px] text-sm"
                        >
                          <ListChecks size={16} aria-hidden="true" /> Ver los {nCorreos} por revisar
                        </button>
                      )}
                      {nCorreos === 0 && <AlDia texto="No hay movimientos del correo por revisar" />}
                      {(punto?.anteriores?.correos || 0) > 0 && (
                        <p className="text-xs text-ink-soft mt-3 rounded-xl bg-paper px-3 py-2.5" data-testid="correos-anteriores">
                          {punto.anteriores.correos === 1
                            ? '1 correo anterior a tu fecha de inicio no se muestra.'
                            : `${punto.anteriores.correos} correos anteriores a tu fecha de inicio no se muestran.`}{' '}
                          <Link to="/perfil#punto-de-partida" className="font-semibold text-accent underline">Cambiar la fecha</Link>
                        </p>
                      )}
                      <CorreosYaRegistrados cantidad={estado?.correos_ya_registrados || 0} onCambio={cargar} />
                      <CorreosDescartados
                        cantidad={estado?.correos_descartados || 0}
                        abierto={llegada?.abrir === 'correos-descartados'}
                        onCambio={cargar}
                      />
            {correosIgnorados === null ? (
              <button onClick={verCorreosIgnorados} className="text-xs text-ink-soft mt-3 underline min-h-[32px]">Ver correos ignorados</button>
            ) : (
              <div className="mt-3 rounded-2xl border border-line divide-y divide-line">
                {correosIgnorados.length === 0 && <p className="text-xs text-ink-soft p-3">No hay correos ignorados.</p>}
                {avisoExt && <p className="text-xs text-ink-soft p-3" role="status">{avisoExt}</p>}
                {correosIgnorados.map((c) => (c.monto > 0 ? (
                  <FilaRecuperable key={c.id} c={c} ocupado={recuperando} onRecuperar={recuperarIgnorado} />
                ) : (
                  <div key={c.id} className="p-3">
                    <p className="text-sm font-medium truncate">{c.asunto || c.comercio}</p>
                    <p className="text-xs text-ink-soft truncate">{c.remitente}</p>
                  </div>
                )))}
              </div>
            )}
                    </>
                  ) : (
                    <div className="rounded-2xl bg-paper p-4">
                      <p className="text-sm font-semibold">Conecta tu Gmail para traer tus movimientos</p>
                      <button onClick={() => setHoja('conexion')} className="mt-1 text-xs font-semibold text-accent min-h-[44px]">Conectar Gmail</button>
                    </div>
                  )}
                </div>
              )}

              {tab === 'meses' && (
                <div role="tabpanel" aria-label="Por mes" className="mt-2" data-testid="seccion-meses">
                  <section aria-label="Cobertura por mes">
                    <Sub id="sinc-cuentas" titulo="Cobertura por mes · cuentas">
          {filasCuentas.length === 0 ? (
            <p className="text-sm text-ink-soft">Aún no tienes cuentas.</p>
          ) : (
            <div className="rounded-2xl bg-paper p-3">
              {!ventanaFija && (
                <div className="flex items-center justify-between mb-2" aria-label="Ventana de meses">
                  <button onClick={() => moverVentana(-1)} className="flex items-center gap-1 text-xs font-semibold text-accent min-h-[40px] pr-3">
                    <ChevronLeft size={16} aria-hidden="true" /> Meses anteriores
                  </button>
                  {hasta && (
                    <button onClick={() => moverVentana(1)} className="flex items-center gap-1 text-xs font-semibold text-accent min-h-[40px] pl-3">
                      Meses siguientes <ChevronRight size={16} aria-hidden="true" />
                    </button>
                  )}
                </div>
              )}
              {/* Casillas de mes de 44 px de toque como mínimo: con menos de 364 px de ancho (celulares de 360) el nombre de la
            cuenta pasa ARRIBA de sus 6 casillas (6 x 44 + 5 huecos de 4 px = 284 px) en vez de a la izquierda. */}
              <div role="table" className="@container" aria-label="Estado de cada cuenta en los últimos meses">
                <div role="row" className="grid grid-cols-6 gap-1 @min-[364px]:grid-cols-[minmax(76px,1.4fr)_repeat(6,minmax(0,1fr))] items-end mb-1.5">
                  <span role="columnheader" className="hidden @min-[364px]:block text-[11px] text-ink-soft">Cuenta</span>
                  {meses.map((m) => (
                    <span key={m.clave} role="columnheader" className="text-[11px] text-ink-soft text-center capitalize">{m.etiqueta}</span>
                  ))}
                </div>
                {filasCuentas.map((c) => (
                  <div key={c.id} role="row" className="grid grid-cols-6 gap-1 @min-[364px]:grid-cols-[minmax(76px,1.4fr)_repeat(6,minmax(0,1fr))] items-center mb-1">
                    <span role="rowheader" title={nombreFila[c.id]} className="col-span-6 @min-[364px]:col-span-1 text-xs font-medium leading-tight break-words line-clamp-3 pr-1">{nombreFila[c.id]}</span>
                    {c.meses.map((m) => {
                      const e = estadoCelda(m.estado)
                      const activa = detalle?.cuentaId === c.id && detalle?.mes === m.mes
                      return (
                        <div key={m.mes} role="cell" className="contents">
                          <button
                            onClick={() => setDetalle(activa ? null : { cuentaId: c.id, mes: m.mes })}
                            aria-pressed={activa}
                            aria-label={`${nombreFila[c.id]}, ${nombreMes(m.mes)}: ${e.texto}`}
                            className={`h-11 min-h-[44px] rounded-lg border text-sm font-semibold flex items-center justify-center ${e.clase} ${activa ? 'ring-2 ring-ink' : ''}`}
                          >
                            <span aria-hidden="true">{e.simbolo}</span>
                          </button>
                        </div>
                      )
                    })}
                  </div>
                ))}
              </div>

              <ul className="flex flex-wrap gap-x-3 gap-y-1 mt-3 text-[11px] text-ink-soft" aria-label="Leyenda">
                {LEYENDA_COBERTURA.map(({ clave, texto }) => (
                  <li key={clave}><span aria-hidden="true">{ESTADOS_CELDA[clave].simbolo}</span> {texto}</li>
                ))}
              </ul>

              {celdaDetalle && cuentaDetalle && (
                <div className="mt-3 rounded-xl bg-paper-raised ring-1 ring-line/60 p-3" role="region" aria-label="Detalle del mes">
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
                    {textoDetalleCelda(celdaDetalle)}
                    {celdaDetalle.extractos ? ` · ${celdaDetalle.extractos} ${celdaDetalle.extractos === 1 ? 'extracto' : 'extractos'}` : ''}
                  </p>
                  {celdaDetalle.lista?.length > 0 && (
                    <ul className="mt-2 flex flex-col gap-1" aria-label="Extractos de este mes">
                      {celdaDetalle.lista.map((x) => (
                        <li key={x.id} className="text-xs">
                          <span className="font-semibold">{x.titulo}</span> · {x.estado_etiqueta}
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="flex flex-wrap gap-2 mt-3">
                    {celdaDetalle.lista?.length > 0 && (
                      <button
                        onClick={() => abrirGrupoExtractos([], 'sinc-todos-extractos', { cuenta: `c:${cuentaDetalle.id}`, mes: celdaDetalle.mes })}
                        className="rounded-xl bg-accent text-paper-raised text-xs font-semibold px-3.5 py-2.5"
                      >
                        Ver {celdaDetalle.lista.length === 1 ? 'el extracto' : 'los extractos'} de este mes
                      </button>
                    )}
                    {celdaDetalle.estado === 'extracto_pendiente' && (
                      <button onClick={() => abrirBloque('extractos', 'sinc-extractos-correo')} className="rounded-xl bg-accent text-paper-raised text-xs font-semibold px-3.5 py-2.5">Revisar extracto</button>
                    )}
                    {celdaDetalle.estado === 'falta_clave' && (
                      <button onClick={() => setHoja('clave')} className="rounded-xl bg-accent text-paper-raised text-xs font-semibold px-3.5 py-2.5">Poner clave</button>
                    )}
                    {(celdaDetalle.estado === 'sin_extracto' || celdaDetalle.estado === 'vacio') && (
                      <button
                        onClick={() => pedirSubir({ cuentaId: cuentaDetalle.id, mes: celdaDetalle.mes })}
                        className="rounded-xl bg-accent text-paper-raised text-xs font-semibold px-3.5 py-2.5"
                      >
                        Subir el extracto de este mes
                      </button>
                    )}
                    {celdaDetalle.estado === 'sin_extracto' && (
                      <button onClick={() => (conectado ? sincronizar() : abrirBloque('conexion'))} className="rounded-xl border border-line text-xs font-semibold px-3.5 py-2.5">
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
                  </section>
        {(estado?.cuadre_mensual || []).filter((c) => c.meses?.length || c.sin_saldo?.length).map((c, i) => (
          <CuadreEncadenado key={c.cuenta_id} id={i === 0 ? 'sinc-cuadre' : undefined} cuentaId={c.cuenta_id} moneda={c.moneda}
            datos={c} onCambio={cargar} className="mt-5 scroll-mt-4" />
        ))}
                </div>
              )}
            </>
          )}
        </Hoja>
      )}

      {hoja === 'conexion' && (
        <Hoja onCerrar={cerrarHoja} titulo="Conexiones y claves">
          {() => (
            <>
              <h2 className="text-lg font-bold">Conexiones y claves</h2>
              <div className="mt-4">
                <ConexionGmail estado={gmail} onCambio={cargar} />
              </div>
              {conectado && (
                <>
                  <InterruptoresLectura activos={activos} errores={erroresInterruptor} guardando={guardandoLectura} onCambiar={cambiarLectura} />
                  <ul className="mt-3 text-xs text-ink-soft flex flex-col gap-1" aria-label="Estado de la lectura">
                    <li data-testid="conexion-ultima">
                      {ultima ? `Última vez que leí tu correo: ${ultima}` : 'Aún no he leído tu correo'}
                    </li>
                    {textoUltimaLectura(estado?.carriles?.movimientos?.ultima_lectura) && (
                      <li data-testid="conexion-ultima-lectura">{textoUltimaLectura(estado.carriles.movimientos.ultima_lectura)}</li>
                    )}
                    {Object.keys(erroresCarril).filter((k) => erroresCarril[k]).map((k) => (
                      <li key={k} className="text-danger">{NOMBRE_CARRIL[k]}: {erroresCarril[k]}</li>
                    ))}
                    {punto?.definido && punto?.fecha && (
                      <li data-testid="conexion-punto">
                        Leo desde el {String(punto.fecha).slice(0, 10).split('-').reverse().join('/')}.{' '}
                        <Link to="/perfil#punto-de-partida" className="font-semibold text-accent underline">Cambiar la fecha</Link>
                      </li>
                    )}
                  </ul>
                  {activos.movimientos !== false && (
                    <button
                      type="button"
                      onClick={releerMovimientos}
                      disabled={Boolean(progreso || leyendo.movimientos || leyendo.extractos)}
                      className="mt-3 w-full flex items-center justify-center gap-2 bg-paper shadow-sm font-semibold rounded-xl min-h-[44px] text-sm disabled:opacity-60"
                      data-testid="releer-60"
                    >
                      {leyendo.movimientos ? 'Releyendo…' : 'Releer los últimos 60 días'}
                    </button>
                  )}
                  {errorReleer && <p className="text-xs text-danger mt-2" role="alert">{errorReleer}</p>}
                  <div className="mt-5" id="sinc-clave">{claveEl}</div>
                </>
              )}

              <h3 className="mt-6 text-xs font-semibold uppercase tracking-wide text-ink-soft">Otras formas de traer movimientos</h3>
              <ul className="mt-2 flex flex-col">
                <FilaMenu icono={FileText} texto="Subir un archivo (PDF, Excel o CSV)" onClick={() => { setSubir({ n: Date.now() }); setHoja('subir') }} testid="menu-subir" />
                {conectado && <FilaMenu icono={Mail} texto="Buscar un extracto por su asunto" onClick={() => setHoja('asunto')} testid="menu-asunto" />}
                {conectado && <FilaMenu icono={Mail} texto="Buscar un movimiento por su asunto" onClick={() => setHoja('asunto-mov')} testid="menu-asunto-mov" />}
                {conectado && <FilaMenu icono={GraduationCap} texto="Mis reglas de correo" onClick={() => setHoja('reglas')} testid="menu-reglas" />}
                <FilaMenu icono={Pencil} texto="Agregar uno a mano" onClick={() => navigate('/agregar')} testid="menu-agregar" />
                <FilaMenu icono={CalendarDays} texto="Fecha desde la que leo tu correo" onClick={() => setHoja('punto')} testid="menu-punto" />
                <FilaMenu icono={Plug} texto="Estado de todas tus conexiones" onClick={() => { setHoja(null); setVerEstado(true) }} testid="menu-estado" />
                <li className="pt-2"><EnlaceBancoNoEsta /></li>
              </ul>
            </>
          )}
        </Hoja>
      )}

      {hoja === 'clave' && (
        <Hoja onCerrar={cerrarHoja} titulo="Clave de tus PDF">
          {() => (
            <>
              <h2 className="text-lg font-bold">Clave de tus PDF</h2>
              <div className="mt-3" id="sinc-clave">{claveEl}</div>
              {avisoExt && <p className="text-xs text-ink-soft mt-2" role="status">{avisoExt}</p>}
            </>
          )}
        </Hoja>
      )}

      {hoja === 'categorizar' && (
        <Hoja onCerrar={cerrarHoja} titulo="Poner categorías">
          {() => (
            <>
              <h2 className="text-lg font-bold">Poner categorías</h2>
              <p className="text-xs text-ink-soft mt-1">Elige una vez y la recuerdo para ese comercio.</p>
              <div id="sinc-categorizar" className="mt-3">
          {cola.items.length === 0 ? (
            <AlDia texto="Nada por categorizar" />
          ) : (
            <div className="flex flex-col gap-2.5">
              {cola.items.map((m) => (
                <div key={m.id} className="rounded-2xl bg-paper p-3.5" data-testid={`cat-${m.id}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold break-words line-clamp-2">{m.descripcion}</p>
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
                    className="w-full mt-2.5 rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-[13px]"
                  >
                    <option value="">{m.categoria === 'Otros' ? 'Elige la categoría' : `Confirmar o cambiar: ${m.categoria}`}</option>
                    {nombres.map((n) => (
                      <option key={n} value={n}>{iconoDe(n)} {n}</option>
                    ))}
                  </select>
                  <label className="flex items-center gap-2 mt-1 text-xs text-ink-soft min-h-[44px]">
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
                <button onClick={masPorCategorizar} className="bg-paper rounded-xl min-h-[44px] text-sm font-semibold">Cargar más</button>
              )}
            </div>
          )}
              </div>
            </>
          )}
        </Hoja>
      )}

      {hoja === 'subir' && (
        <Hoja onCerrar={() => { cerrarHoja(); cargar() }} titulo="Revisar un extracto" clasePanel="p-6 pb-8">
          {() => (
            <>
              <h2 className="text-lg font-bold">Extracto o archivo</h2>
              <div id="sinc-subir" className="mt-3">
                <SubirArchivos inicial={subir} onImportado={cargar} />
              </div>
            </>
          )}
        </Hoja>
      )}

      {hoja === 'asunto' && (
        <Hoja onCerrar={cerrarHoja} titulo="Buscar un extracto por su asunto">
          {() => (
            <>
              <h2 className="text-lg font-bold">Buscar por asunto</h2>
              <BuscarExtractoPorAsunto onAgregado={cargar} />
            </>
          )}
        </Hoja>
      )}

      {hoja === 'asunto-mov' && (
        <Hoja onCerrar={cerrarHoja} titulo="Buscar un movimiento por su asunto">
          {() => (
            <>
              <h2 className="text-lg font-bold">Buscar un movimiento</h2>
              <BuscarExtractoPorAsunto modo="movimiento" onAgregado={cargar} />
            </>
          )}
        </Hoja>
      )}

      {hoja === 'reglas' && (
        <Hoja onCerrar={cerrarHoja} titulo="Mis reglas de correo">
          {() => (
            <>
              <h2 className="text-lg font-bold">Mis reglas de correo</h2>
              <MisReglasCorreo />
            </>
          )}
        </Hoja>
      )}

      {hoja === 'punto' && (
        <Hoja onCerrar={cerrarHoja} titulo="Fecha de inicio">
          {() => (
            <PuntoDePartida
              variante={punto?.definido === false ? 'primera' : 'perfil'}
              inicial={punto}
              onGuardado={() => { setPpRecien(true); cargar() }}
              onPosponer={() => { posponerPuntoDePartida(); setPospuestoPP(true); setHoja(null) }}
            />
          )}
        </Hoja>
      )}

      {bancoNoEsta !== null && <BancoNoEsta bancoInicial={bancoNoEsta} onClose={() => setBancoNoEsta(null)} />}

      {elegirBanco && (
        <Hoja onCerrar={() => setElegirBanco(false)} titulo="Bancos sin cuenta">
          {({ cerrar }) => (
            <>
              <h2 className="text-lg font-bold">¿De qué banco creas la cuenta?</h2>
              <div className="flex flex-col gap-2 mt-3">
                {sinCuenta.map((s) => (
                  <button
                    key={s.banco}
                    type="button"
                    onClick={() => { cerrar(); setCrearBanco(s.banco) }}
                    className="rounded-xl bg-accent text-paper-raised text-sm font-semibold px-3 py-2 min-h-[44px]"
                  >
                    Crear cuenta {s.banco}
                  </button>
                ))}
              </div>
            </>
          )}
        </Hoja>
      )}

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

function FilaMenu({ icono: Icono, texto, onClick, testid }) {
  return (
    <li>
      <button type="button" onClick={onClick} data-testid={testid} className="w-full flex items-center gap-3 min-h-[52px] text-left border-b border-line/40">
        <Icono size={20} className="text-accent shrink-0" aria-hidden="true" />
        <span className="flex-1 text-sm font-medium">{texto}</span>
        <ChevronRight size={16} className="text-ink-soft shrink-0" aria-hidden="true" />
      </button>
    </li>
  )
}

function FilaExtracto({
  ex, cuentas, cuentaId, nombreCuenta, ocupado, onCuenta, onConciliar, onVer, onClave, onIgnorar,
  claveConfigurada = false, probando = false, onProbarClave,
}) {
  const banco = ex.banco || ex.asunto || BANCO_SIN_IDENTIFICAR
  const sinBanco = !ex.banco
  // De dónde salió (nada sin origen): el asunto del correo, el archivo y cuándo llegó.
  const cuando = ex.recibido_en ? new Date(/(Z|[+-]\d\d:?\d\d)$/.test(ex.recibido_en) ? ex.recibido_en : `${ex.recibido_en}Z`) : null
  const origen = [
    ex.banco && ex.asunto ? `«${ex.asunto}»` : '',
    ex.archivo,
    cuando && !Number.isNaN(cuando.getTime()) ? `llegó el ${cuando.toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })}` : '',
  ].filter(Boolean).join(' · ')
  const puedeConciliar = ex.estado === 'nuevo'
  // Correo de tarjeta de crédito y la persona no tiene una cuenta de crédito de ese banco: no se oculta, se avisa.
  const marca = (ex.banco || '').toLowerCase().split(/\s+/)[0]
  const faltaTarjeta = productoDeTexto(`${ex.asunto || ''} ${ex.archivo || ''}`) === 'credito'
    && !ex.cuenta_sugerida_id
    && !cuentas.some((c) => c.tipo === 'credito' && (!marca || (c.nombre || '').toLowerCase().includes(marca)))
  const nombreCorto = (b) => b.replace(/\s*colombia$/i, '')
  return (
    <div className="rounded-2xl bg-paper p-3.5" data-testid={`extracto-${ex.id}`}>
      <div className="flex items-start gap-3">
        <FileText size={20} className="text-accent shrink-0 mt-0.5" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold truncate">{banco}{ex.periodo ? ` · ${ex.periodo}` : ''}</p>
          {origen && <p className="text-xs text-ink-soft break-words" data-testid="origen-fila">{origen}</p>}
          {sinBanco && <p className="text-xs text-ink-soft">No pude saber de qué banco es: elige la cuenta.</p>}
          <p className="text-xs text-ink-soft truncate">
            {nombreCuenta ? `Cuenta: ${nombreCuenta}` : 'Cuenta sin elegir'}
          </p>
          <p className={`text-xs font-medium mt-0.5 ${ex.estado === 'falta_clave' || ex.estado === 'error' ? 'text-danger' : ex.estado === 'procesado' ? 'text-cuadra' : 'text-accent'}`}>
            {textoEstadoExtracto(ex)}
          </p>
          {ex.datos_cuerpo && (
            <p className="text-xs text-ink-soft mt-0.5" data-testid="datos-cuerpo">
              Según el correo:{' '}
              {[
                ex.datos_cuerpo.pago_minimo != null && `pago mínimo $${Math.round(ex.datos_cuerpo.pago_minimo).toLocaleString('es-CO')}`,
                ex.datos_cuerpo.periodo_facturado && `período ${ex.datos_cuerpo.periodo_facturado}`,
                ex.datos_cuerpo.fecha_corte && `corte ${ex.datos_cuerpo.fecha_corte}`,
                ex.datos_cuerpo.fecha_limite && `pagar antes del ${ex.datos_cuerpo.fecha_limite}`,
              ].filter(Boolean).join(' · ')}
            </p>
          )}
          {faltaTarjeta && (
            <p className="text-xs text-ink-soft mt-0.5" data-testid="falta-cuenta-tarjeta">
              Es el extracto de tu tarjeta de crédito {ex.banco ? nombreCorto(ex.banco) : ''}: crea tu cuenta de tarjeta para conciliarlo.
            </p>
          )}
          {ex.estado === 'falta_clave' && ex.clave_estado === 'no_abrio' && (
            <p className="text-xs text-danger mt-0.5" data-testid="clave-no-abrio">
              La clave guardada no abrió este extracto: revísala.
            </p>
          )}
          {ex.estado === 'falta_clave' && claveConfigurada && ex.clave_estado === 'por_probar' && (
            <p className="text-xs text-ink-soft mt-0.5">Falta probar la clave en este extracto.</p>
          )}
        </div>
      </div>

      {puedeConciliar && (
        <SelectorCuentaBanco
          className="mt-3"
          cuentas={cuentas}
          value={cuentaId}
          onChange={onCuenta}
          ariaLabel={`Cuenta del extracto ${banco}`}
          vacio={sinBanco ? 'Elige la cuenta (obligatorio)' : 'Elige la cuenta'}
          banco={ex.banco}
          producto={productoDeTexto(`${ex.asunto || ''} ${ex.archivo || ''}`)}
          pregunta={ex.pregunta_cuenta}
          sugeridaId={ex.cuenta_sugerida_id}
          candidatas={ex.cuentas_candidatas}
        />
      )}

      <div className="flex gap-2 mt-3">
        {ex.estado === 'procesado' && ex.historial_id && (
          <button onClick={onVer} className="flex-1 border border-line rounded-xl py-2.5 text-sm font-semibold">Ver qué se encontró</button>
        )}
        {puedeConciliar && (
          <button
            onClick={onConciliar}
            disabled={ocupado || !cuentaId}
            className="flex-1 bg-accent text-paper-raised font-semibold rounded-xl py-2.5 text-sm disabled:opacity-50"
          >
            {ocupado ? 'Revisando...' : 'Revisar extracto'}
          </button>
        )}
        {ex.estado === 'falta_clave' && claveConfigurada && onProbarClave && (
          <button
            onClick={onProbarClave}
            disabled={probando}
            className="flex-1 border border-line font-semibold rounded-xl py-2.5 text-sm disabled:opacity-60"
          >
            {probando ? 'Probando…' : 'Probar la clave ahora'}
          </button>
        )}
        {ex.estado === 'falta_clave' && (
          <button onClick={onClave} className="flex-1 bg-accent text-paper-raised font-semibold rounded-xl py-2.5 text-sm">
            {claveConfigurada ? 'Cambiar la clave' : 'Poner clave'}
          </button>
        )}
        {ex.estado !== 'procesado' && (
          <button onClick={onIgnorar} className="px-4 rounded-xl border border-line text-sm text-ink-soft" aria-label={`Ignorar extracto ${banco}`}>
            <X size={16} />
          </button>
        )}
      </div>
    </div>
  )
}
