import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { EsqueletoLista } from '../components/Esqueletos'
import { EstadoVacio } from '../brand/Marca'
import { Boton } from '../components/ui'
import { Link, useLocation, useNavigate, useNavigationType, useSearchParams } from 'react-router-dom'
import { ArrowLeftRight, Check, RefreshCw, ChevronDown, ChevronRight, Download, ListChecks, PieChart, Search, Shuffle, SlidersHorizontal, Trash2, Upload, X } from 'lucide-react'
import Icono from '../components/Icono'
import { formatCOP, formatMoneda } from '../lib/format'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import { useDialogos } from '../lib/DialogosContext'
import { contextoDeCuentas, totalesIngresosGastos } from '../lib/contabilidad'
import { direccionDe, etiquetaTraslado, signoDe } from '../lib/traslados'
import { esAuto, claveComercio } from '../lib/comercio'
import { useModoPantalla } from '../lib/useAncho'
import { guardarCacheLista, leerCacheLista, parchearEnCaches, quitarDeCaches, useEstadoLista } from '../lib/useEstadoLista'
import {
  agruparPorComercio,
  categoriasRecientes,
  coincideFiltros,
  consultaServidor,
  ORIGENES_FILTRO,
  hayFiltros,
  huellaDe,
  leerFiltros,
} from '../lib/movimientosLista'
import { InsigniaAuto } from '../components/CategorizacionAuto'
import SelectorCategoria from '../components/SelectorCategoria'
import Hoja from '../components/Hoja'
import TablaMovimientos from '../components/TablaMovimientos'
import DetalleMovimiento from './DetalleMovimiento'
import EtiquetaOrigen from '../components/EtiquetaOrigen'
import { fechaHoraMovimiento, fechaDeMovimiento } from '../lib/fechaMovimiento'
import PorRevisarCorreo from '../components/PorRevisarCorreo'
import { BotonLapiz, EditorNombre, PistaBanco } from '../components/NombreEditable'
import { limpiarNombre, MIN_REPETICIONES_NOMBRE, nombreDe, tieneNombrePropio } from '../lib/tituloMovimiento'
import { usePorRevisarCorreo } from '../lib/usePorRevisarCorreo'
import { OPCIONES_BORRADO_VARIOS, vinoDeCorreoOExtracto } from '../lib/canales'
import { actualizarDesdeCorreo, resumenActualizacion } from '../lib/sincronizarGmail'

const TAMANO_PAGINA = 200
const MAX_LOTES = 15 // tope de seguridad al re-pedir lo ya cargado (3.000 movimientos)
const PRESION_LARGA_MS = 450
const ALTO_DIA_BASE = 40 // etiqueta del día + espacio, para estimar antes de medir
const ALTO_FILA_ESTIMADO = 72
const MARGEN_VENTANA = 800 // px extra arriba y abajo para que el scroll rápido no muestre vacío

function etiquetaDia(fechaISO) {
  const fecha = new Date(fechaISO)
  const hoy = new Date()
  const ayer = new Date(hoy)
  ayer.setDate(hoy.getDate() - 1)
  const mismodiaQue = (a, b) => a.toDateString() === b.toDateString()

  if (mismodiaQue(fecha, hoy)) return 'Hoy'
  if (mismodiaQue(fecha, ayer)) return 'Ayer'
  return fecha.toLocaleDateString('es-CO', { day: 'numeric', month: 'long' })
}

// Una fila de la lista. Está memoizada: al categorizar UN movimiento solo se vuelve a pintar su
// fila (las demás reciben las mismas props y React las salta), clave con miles de movimientos.
const FilaMovimiento = memo(function FilaMovimiento({
  m, icono, moneda, cuentaNombre, esSel, modoSel, panel, botonConfirmar, indice, onToggle, onChip, onConfirmar, onAbrir, onNombre,
}) {
  const timer = useRef(null)
  const larga = useRef(false)
  const inicio = useRef({ x: 0, y: 0 })
  const esTransfer = m.fuente === 'transferencia_interna'
  const direccion = direccionDe(m) // todo movimiento tiene dirección: el signo y el color la siguen
  const traslado = etiquetaTraslado(m)

  function cancelar() {
    clearTimeout(timer.current)
    timer.current = null
  }
  // Pulsación larga (dedo o lápiz): entra al modo selección con este movimiento marcado
  function empezar(e) {
    if (e.pointerType === 'mouse' || modoSel) return
    larga.current = false
    inicio.current = { x: e.clientX, y: e.clientY }
    cancelar()
    timer.current = setTimeout(() => {
      timer.current = null
      larga.current = true
      navigator.vibrate?.(15)
      onToggle(m.id, true)
    }, PRESION_LARGA_MS)
  }
  function mover(e) {
    if (timer.current && Math.hypot(e.clientX - inicio.current.x, e.clientY - inicio.current.y) > 10) cancelar()
  }
  function alClic(e) {
    if (larga.current) {
      e.preventDefault()
      larga.current = false
      return
    }
    if (modoSel) {
      e.preventDefault()
      onToggle(m.id)
    } else if (panel) {
      e.preventDefault()
      onAbrir(m.id)
    }
  }

  return (
    <div
      className="relative stagger-item [-webkit-touch-callout:none]"
      style={{ '--stagger-i': indice }}
      data-fila={m.id}
      onPointerDown={empezar}
      onPointerMove={mover}
      onPointerUp={cancelar}
      onPointerCancel={cancelar}
      onPointerLeave={cancelar}
      onContextMenu={(e) => {
        if (larga.current) e.preventDefault()
      }}
    >
      <span
        className={`absolute -left-5 top-[18px] w-2.5 h-2.5 rounded-full border-2 border-paper ${
          direccion === 'income' ? 'bg-accent-2' : 'bg-ink'
        }`}
      />
      <div className="flex items-start gap-3">
        <button
          type="button"
          role="checkbox"
          aria-checked={esSel}
          aria-label={`Seleccionar ${m.descripcion}`}
          onClick={() => onToggle(m.id)}
          className={`${modoSel ? 'flex' : 'hidden md:flex'} relative before:absolute before:-inset-3 before:content-[''] mt-3 w-5 h-5 rounded-md border-2 shrink-0 items-center justify-center ${
            esSel ? 'bg-accent border-accent' : 'border-line'
          }`}
        >
          {esSel && <Check size={16} className="text-paper-raised" />}
        </button>
        <div className="min-w-0 flex-1">
          <Link to={`/movimientos/${m.id}`} onClick={alClic} className="block pt-2.5 min-w-0">
            <p className="text-sm font-semibold break-words line-clamp-4" title={m.descripcion}>{nombreDe(m)}</p>
            {tieneNombrePropio(m) && <PistaBanco original={m.descripcion} />}
            <p className="text-xs text-ink-soft mt-0.5 break-words" data-testid="fila-fecha-cuenta">
              {[fechaHoraMovimiento(fechaDeMovimiento(m)), cuentaNombre].filter(Boolean).join(' · ')}
            </p>
            <EtiquetaOrigen origen={m.origen} canales={m.canales} className="mt-1" />
          </Link>
          <div className="flex items-center flex-wrap gap-y-1 pt-0.5 pb-2.5">
            {esTransfer ? (
              <span className="text-xs text-ink-soft">
                <Icono icono={ArrowLeftRight} tam="sm" className="inline -mt-0.5" /> {m.categoria}
              </span>
            ) : (
              <button
                type="button"
                onClick={() => (modoSel ? onToggle(m.id) : onChip(m))}
                aria-label={`Cambiar categoría de ${m.descripcion}`}
                className="relative before:absolute before:-inset-y-1.5 before:inset-x-0 before:content-[''] inline-flex items-center gap-1 text-xs text-ink-soft rounded-full border border-line px-2.5 min-h-[32px] hover:border-accent hover:text-ink"
              >
                <span aria-hidden="true">{icono}</span> {m.categoria}{m.subcategoria ? ` · ${m.subcategoria}` : ''}
                <ChevronDown size={16} aria-hidden="true" />
              </button>
            )}
            {onNombre && !esTransfer && !modoSel && <BotonLapiz className="ml-1.5" original={m.descripcion} onClick={() => onNombre(m)} />}
            {traslado && !esTransfer && (
              <span className="ml-2 text-[11px] font-semibold text-ink-soft rounded-full bg-paper-raised border border-line px-2 py-0.5">
                {traslado}
              </span>
            )}
            {esAuto(m) && <InsigniaAuto movimiento={m} />}
            {botonConfirmar && esAuto(m) && (
              <button
                onClick={() => onConfirmar(m)}
                aria-label={`Confirmar categoría de ${m.descripcion}`}
                className="ml-2 flex items-center gap-1 text-xs font-semibold px-3 min-h-[32px] rounded-full bg-accent text-paper-raised"
              >
                <Check size={16} /> Confirmar
              </button>
            )}
          </div>
        </div>
        <Link
          to={`/movimientos/${m.id}`}
          onClick={alClic}
          tabIndex={-1}
          aria-hidden="true"
          className="pt-2.5 shrink-0 max-w-[45%]"
        >
          <span className={`text-[15px] font-bold tabular-nums whitespace-nowrap ${direccion === 'income' ? 'text-gold' : direccion ? 'text-ink' : 'text-ink-soft'}`}>
            {signoDe(m)}
            {formatMoneda(m.monto, moneda)}
          </span>
        </Link>
      </div>
    </div>
  )
})

export default function Movimientos() {
  const { cuentas, recargar: recargarCuentas } = useCuentas()
  const { nombres: CATEGORIAS, iconoDe } = useCategorias()
  const { avisar, confirmar, elegir } = useDialogos()
  const modo = useModoPantalla()
  const lateral = modo === 'lateral'
  const location = useLocation()
  const [params, setParams] = useSearchParams()
  const raiz = useRef(null)

  // --- Filtros: viven en la URL (sobreviven a atrás, a recargar y a compartir el enlace) ---
  const f = useMemo(() => leerFiltros(params), [params])
  const panelId = lateral ? params.get('mov') : null
  const claveLista = useMemo(() => {
    const p = new URLSearchParams(params)
    p.delete('mov') // abrir el panel de detalle no cambia de lista
    const s = p.toString()
    return `${location.pathname}${s ? `?${s}` : ''}`
  }, [params, location.pathname])

  const cambiarParams = useCallback(
    (cambios) => {
      setParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          for (const [k, v] of Object.entries(cambios)) {
            if (v === '' || v == null || v === false) n.delete(k)
            else n.set(k, v === true ? '1' : v)
          }
          return n
        },
        { replace: true } // los filtros no ensucian el historial: "atrás" sale de la pantalla
      )
    },
    [setParams]
  )

  // Lo que llegó por el correo y espera aprobación: sección propia arriba de la lista (filtro «Del correo»).
  const porCorreo = usePorRevisarCorreo()
  const soloCorreo = params.get('filtro') === 'por-revisar'
  const navigate = useNavigate()
  // Cuántos correos descartados se pueden recuperar (una consulta corta; el tope es 100).
  const [descartados, setDescartados] = useState(0)
  useEffect(() => {
    let vivo = true
    Promise.resolve(api.correosLista?.('descartados', 0, 100))
      .then((l) => vivo && setDescartados(Array.isArray(l) ? l.length : 0))
      .catch(() => {})
    return () => {
      vivo = false
    }
  }, [porCorreo.correos.length])

  // Movimientos «en vivo»: al abrir, al volver a la app (máx. 1 vez cada 5 min) y con el botón de refresco
  // se leen las notificaciones del banco. Lo nuevo cae en «Por revisar» (arriba); la lista no se mueve.
  const [leyendoCorreo, setLeyendoCorreo] = useState(false)
  const [avisoCorreo, setAvisoCorreo] = useState('')
  const gmailConectado = useRef(null) // null = aún no se sabe
  const leyendoRef = useRef(false)
  const actualizarCorreo = useCallback(
    async (manual = false) => {
      if (leyendoRef.current) return
      if (gmailConectado.current === null) {
        try {
          const e = await Promise.resolve(api.gmailEstado?.())
          gmailConectado.current = !!e?.conectado
        } catch {
          gmailConectado.current = false
        }
      }
      if (!gmailConectado.current) {
        if (manual) setAvisoCorreo('Conecta tu correo en «Traer movimientos» para leer tus notificaciones.')
        return
      }
      leyendoRef.current = true
      setLeyendoCorreo(true)
      const r = await actualizarDesdeCorreo({ manual })
      leyendoRef.current = false
      setLeyendoCorreo(false)
      if (r.omitido) return
      if (r.error) setAvisoCorreo(manual ? r.error : '')
      else {
        if (r.nuevos || manual) porCorreo.recargar() // tras el refresco, «Por revisar» siempre al día
        if (r.nuevos || manual) setAvisoCorreo(resumenActualizacion(r))
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [porCorreo.recargar]
  )
  useEffect(() => {
    actualizarCorreo(false)
    const alVolver = () => document.visibilityState === 'visible' && actualizarCorreo(false)
    document.addEventListener('visibilitychange', alVolver)
    return () => document.removeEventListener('visibilitychange', alVolver)
  }, [actualizarCorreo])
  useEffect(() => {
    if (!avisoCorreo) return undefined
    const t = setTimeout(() => setAvisoCorreo(''), 6000)
    return () => clearTimeout(t)
  }, [avisoCorreo])

  const consulta = useMemo(() => consultaServidor(f), [f])
  const consultaKey = JSON.stringify(consulta)

  // --- Datos: arrancan del caché si ya se vio esta lista (pinta al instante y se revalida) ---
  // Al VOLVER (POP) se recupera también cuántos había y el scroll; al entrar tocando el menú se
  // muestra lo último visto desde arriba, con la primera página, y se actualiza sola al llegar lo nuevo.
  const vuelve = useNavigationType() === 'POP'
  const [cacheInicial] = useState(() => leerCacheLista(claveLista))
  const [movimientos, setMovimientos] = useState(cacheInicial?.items || [])
  const [hayMas, setHayMas] = useState(!!cacheInicial?.hayMas)
  const [cargando, setCargando] = useState(!cacheInicial)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [errorCarga, setErrorCarga] = useState('')
  const [conteo, setConteo] = useState({ auto: 0, otros: 0, total: 0 })
  const [exportando, setExportando] = useState(false)
  const [mostrarFiltros, setMostrarFiltros] = useState(false)
  const [texto, setTexto] = useState(f.q)
  const [selector, setSelector] = useState(null)
  const [moverACuenta, setMoverACuenta] = useState(false)
  const [modoSeleccion, setModoSeleccion] = useState(false)
  const [seleccionados, setSeleccionados] = useState(() => new Set())
  const [aplicando, setAplicando] = useState(false)
  const [expandidos, setExpandidos] = useState(() => new Set())

  const peticion = useRef(0)
  const ultimaConsulta = useRef(null)
  const claveDeItems = useRef(cacheInicial ? claveLista : null)

  const guardado = useEstadoLista(claveLista, {
    contenedorRef: raiz,
    cantidad: movimientos.length,
    listo: !cargando && !errorCarga,
  })

  const pedir = useCallback(
    (offset) => (Object.keys(consulta).length ? api.movimientos(TAMANO_PAGINA, offset, consulta) : api.movimientos(TAMANO_PAGINA, offset)),
    [consulta]
  )

  // Pide páginas hasta juntar `objetivo` movimientos (al volver, los que ya había cargados)
  const traerHasta = useCallback(
    async (objetivo) => {
      let acum = []
      let hay = true
      for (let i = 0; i < MAX_LOTES; i++) {
        const lote = await pedir(acum.length)
        acum = acum.concat(lote)
        hay = lote.length === TAMANO_PAGINA
        if (!hay || acum.length >= objetivo) break
      }
      return { items: acum, hay }
    },
    [pedir]
  )

  // Al aprobar o descartar un correo: sale de la sección y, si pasó a la lista, aparece sin recargar la pantalla.
  const correoResuelto = useCallback(
    async (c) => {
      porCorreo.quitar(c)
      try {
        const { items, hay } = await traerHasta(Math.max(TAMANO_PAGINA, movimientos.length))
        setMovimientos(items)
        setHayMas(hay)
      } catch {
        /* la lista se actualiza sola la próxima vez */
      }
      recargarConteo()
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [porCorreo.quitar, traerHasta, movimientos.length]
  )

  const recargarConteo = useCallback(() => {
    Promise.resolve(api.conteoPorRevisar?.())
      .then((c) => c && setConteo(c))
      .catch(() => {})
  }, [])

  useEffect(() => {
    const cambioFiltro = ultimaConsulta.current !== null && ultimaConsulta.current !== consultaKey
    const silencioso = !cambioFiltro && !!cacheInicial // volver a una lista conocida: se revalida sin tapar nada
    ultimaConsulta.current = consultaKey
    const objetivo = cambioFiltro
      ? TAMANO_PAGINA
      : vuelve
        ? Math.max(TAMANO_PAGINA, guardado?.cantidad || 0, cacheInicial?.items?.length || 0)
        : TAMANO_PAGINA
    const mia = ++peticion.current
    if (!silencioso) {
      claveDeItems.current = null
      setCargando(true)
      setErrorCarga('')
      if (cambioFiltro && raiz.current) raiz.current.scrollTop = 0
      setSeleccionados(new Set())
    }
    traerHasta(objetivo)
      .then(({ items, hay }) => {
        if (mia !== peticion.current) return
        claveDeItems.current = claveLista
        setMovimientos(items)
        setHayMas(hay)
        setErrorCarga('')
      })
      .catch((err) => {
        if (mia !== peticion.current || silencioso) return
        setErrorCarga(err.message || 'No se pudieron cargar los movimientos. Revisa tu conexión e intenta de nuevo.')
      })
      .finally(() => mia === peticion.current && setCargando(false))
    recargarConteo()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [consultaKey])

  // El caché sigue a la lista (incluye los cambios optimistas) para pintarla al volver
  useEffect(() => {
    if (!cargando && !errorCarga && claveDeItems.current === claveLista) {
      guardarCacheLista(claveLista, { items: movimientos, hayMas })
    }
  }, [movimientos, hayMas, cargando, errorCarga, claveLista])

  // Búsqueda: se escribe sin demora y pasa a la URL 300 ms después de la última tecla
  useEffect(() => setTexto(f.q), [f.q])
  useEffect(() => {
    if (texto === f.q) return undefined
    const t = setTimeout(() => cambiarParams({ q: texto.trim() ? texto : '' }), 300)
    return () => clearTimeout(t)
  }, [texto]) // eslint-disable-line react-hooks/exhaustive-deps

  // --- Derivados ---
  const monedaDe = useMemo(() => Object.fromEntries(cuentas.map((c) => [c.id, c.moneda])), [cuentas])
  const filtrados = useMemo(() => movimientos.filter((m) => coincideFiltros(m, f)), [movimientos, f])
  const filtradosRef = useRef(filtrados)
  filtradosRef.current = filtrados
  const activos = hayFiltros(f)
  // Regla única: se empareja sobre TODA la lista cargada (la otra pata puede estar filtrada) y se suma lo filtrado.
  const totales = useMemo(() => {
    const ids = new Set(filtrados.map((m) => m.id))
    return totalesIngresosGastos(movimientos, contextoDeCuentas(cuentas), (m) => ids.has(m.id))
  }, [movimientos, filtrados, cuentas])
  const totalIngresos = totales.ingresos
  const totalGastos = totales.gastos
  const gruposDia = useMemo(() => {
    const mapa = new Map()
    for (const m of filtrados) {
      const k = m.fecha.slice(0, 10)
      let g = mapa.get(k)
      if (!g) {
        g = { diaKey: k, label: etiquetaDia(m.fecha), items: [] }
        mapa.set(k, g)
      }
      g.items.push(m)
    }
    return [...mapa.values()]
  }, [filtrados])
  const gruposComercio = useMemo(
    () => (f.comercio ? agruparPorComercio(filtrados, f.orden) : []),
    [filtrados, f.comercio, f.orden]
  )
  const recientes = useMemo(() => categoriasRecientes(movimientos, CATEGORIAS), [movimientos, CATEGORIAS])
  const vistaActiva = f.comercio ? 'comercio' : lateral && f.tabla ? 'tabla' : 'lista'
  const filtrosVisibles = mostrarFiltros || lateral || !!(f.cuenta || f.desde || f.hasta || f.tipo || f.origen)

  // --- Ventana (virtualización por días) ---
  // Con 1.500+ movimientos solo se pintan los días que se ven más un margen; lo de arriba y abajo
  // se reemplaza por dos espacios en blanco del alto exacto. Un día tiene alto variable (la fila
  // cambia si hay etiqueta de traslado o botón Confirmar), así que se MIDE cada día al pintarlo y,
  // mientras no se ha pintado, se usa una estimación. Las filas siguen siendo FilaMovimiento.
  const listaRef = useRef(null)
  const alturas = useRef(new Map()) // diaKey -> alto medido en px
  const [version, setVersion] = useState(0) // sube cuando una medida cambia, para recalcular
  const [vista, setVista] = useState(0) // sube al hacer scroll/redimensionar
  const { offs, total } = useMemo(() => {
    const o = new Array(gruposDia.length + 1)
    let y = 0
    gruposDia.forEach((g, i) => {
      o[i] = y
      y += alturas.current.get(g.diaKey) || ALTO_DIA_BASE + g.items.length * ALTO_FILA_ESTIMADO
    })
    o[gruposDia.length] = y
    return { offs: o, total: y }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gruposDia, version])
  const ventana = useMemo(() => {
    const n = gruposDia.length
    const lista = listaRef.current
    // Posición de la lista respecto a la pantalla: sirve igual si hace scroll el contenedor o la página
    const rect = lista ? lista.getBoundingClientRect() : { top: 0 }
    const vh = (typeof window !== 'undefined' && window.innerHeight) || 800
    const desde = -rect.top - MARGEN_VENTANA
    const hasta = -rect.top + vh + MARGEN_VENTANA
    let ini = 0
    while (ini < n - 1 && offs[ini + 1] <= desde) ini++
    let fin = ini + 1
    while (fin < n && offs[fin] < hasta) fin++
    return { ini, fin, arriba: offs[ini] || 0, abajo: Math.max(0, total - (offs[fin] ?? total)) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gruposDia, offs, total, vista, f.comercio, cargando])

  useEffect(() => {
    let pendiente = 0
    const programar = () => {
      if (pendiente) return
      pendiente = requestAnimationFrame(() => {
        pendiente = 0
        setVista((v) => v + 1)
      })
    }
    // El evento scroll no burbuja: en captura sobre document cubre el contenedor y la página
    document.addEventListener('scroll', programar, { capture: true, passive: true })
    window.addEventListener('resize', programar)
    return () => {
      document.removeEventListener('scroll', programar, { capture: true })
      window.removeEventListener('resize', programar)
      if (pendiente) cancelAnimationFrame(pendiente)
    }
  }, [])

  // Medir los días pintados; si alguno difiere de lo estimado, se recalculan las posiciones
  useLayoutEffect(() => {
    const lista = listaRef.current
    if (!lista) return
    let cambio = false
    for (const el of lista.querySelectorAll('[data-dia]')) {
      const h = el.getBoundingClientRect().height
      const previo = alturas.current.get(el.dataset.dia)
      if (h > 0 && (previo === undefined || Math.abs(previo - h) > 1)) {
        alturas.current.set(el.dataset.dia, h)
        cambio = true
      }
    }
    if (cambio) setVersion((v) => v + 1)
  })

  // --- Categorizar sin abrir el movimiento (actualización optimista + Deshacer) ---
  const categorizar = useCallback(
    async (items, categoria, { recordar = false, anteriores = false, subcategoria = null } = {}) => {
      const ids = items.map((m) => m.id)
      const idSet = new Set(ids)
      const previos = items.map((m) => ({ id: m.id, categoria: m.categoria, subcategoria: m.subcategoria || null }))
      const huella = items.length ? huellaDe(items[0]) : ''
      // Con "aplicar a los anteriores" los que ya están cargados cambian a la vez
      const afectados = new Set(idSet)
      if (anteriores && huella) {
        for (const m of filtradosRef.current) if (huellaDe(m) === huella && m.fuente !== 'transferencia_interna') afectados.add(m.id)
      }
      const siguiente =
        items.length === 1 && f.cat === 'Otros' && categoria !== 'Otros'
          ? filtradosRef.current[filtradosRef.current.findIndex((m) => m.id === items[0].id) + 1]
          : null

      setMovimientos((prev) =>
        prev.map((m) =>
          afectados.has(m.id)
            ? {
                ...m,
                categoria,
                // otra categoría = la subcategoría anterior ya no aplica; la misma sin elegir otra se conserva
                subcategoria: subcategoria || (m.categoria === categoria ? m.subcategoria || null : null),
                cat_confirmada: true,
                cat_origen: null,
              }
            : m
        )
      )

      let regla = null
      try {
        const llamadas = [subcategoria ? api.recategorizarMasivo(ids, categoria, subcategoria) : api.recategorizarMasivo(ids, categoria)]
        if (recordar && items.length) {
          llamadas.push(
            Promise.resolve(
              api.aprenderRegla({
                descripcion: items[0].descripcion,
                categoria,
                ...(subcategoria ? { subcategoria } : {}),
                aplicar_anteriores: anteriores,
              })
            ).then((r) => {
              regla = r
            })
          )
        }
        await Promise.all(llamadas)
      } catch (err) {
        // Falló: se devuelve todo como estaba
        setMovimientos((prev) =>
          prev.map((m) => {
            const p = previos.find((x) => x.id === m.id)
            return p ? { ...m, categoria: p.categoria, subcategoria: p.subcategoria } : m
          })
        )
        avisar(err.message || 'No se pudo cambiar la categoría. Revisa tu conexión e intenta de nuevo.')
        return
      }
      recargarConteo()

      const extra = anteriores && regla?.anteriores_actualizados ? regla.anteriores_actualizados : 0
      const recuerda = recordar && regla?.guardada
      const destino = `${iconoDe(categoria)} ${categoria}${subcategoria ? ` · ${subcategoria}` : ''}`
      const mensaje =
        items.length === 1
          ? extra
            ? `Listo: ${extra + 1} movimientos movidos a ${destino}`
            : `Movido a ${destino}${recuerda ? ` · recordaré «${regla.huella}»` : ''}`
          : `${items.length} movimientos movidos a ${destino}`

      async function deshacer() {
        const porCategoria = new Map()
        for (const p of previos) {
          if (p.categoria === categoria && !subcategoria) continue
          const clave = `${p.categoria} ${p.subcategoria || ''}`
          porCategoria.set(clave, { cat: p.categoria, sub: p.subcategoria, ids: [...(porCategoria.get(clave)?.ids || []), p.id] })
        }
        setMovimientos((prev) =>
          prev.map((m) => {
            const p = previos.find((x) => x.id === m.id)
            return p ? { ...m, categoria: p.categoria, subcategoria: p.subcategoria } : m
          })
        )
        try {
          await Promise.all(
            [...porCategoria.values()].map(({ cat, sub, ids: lista }) =>
              sub
                ? api.recategorizarMasivo(lista, cat, sub)
                // misma categoría y antes sin subcategoría: hay que quitar la que se agregó ('' la limpia)
                : cat === categoria ? api.recategorizarMasivo(lista, cat, '') : api.recategorizarMasivo(lista, cat)
            )
          )
          // Si el aviso creó la regla del comercio, se quita (si solo la actualizó, se deja)
          if (recuerda && !regla.actualizada) {
            const reglas = await api.reglasCategoria()
            const r = (reglas || []).find((x) => claveComercio(x.patron) === regla.huella)
            if (r) await api.eliminarReglaCategoria(r.id)
          }
          recargarConteo()
        } catch {
          avisar('No se pudo deshacer. Revisa tu conexión e intenta de nuevo.')
        }
      }
      // Con "aplicar a los anteriores" cambiaron movimientos que no están en pantalla: sin Deshacer
      avisar(mensaje, 'ok', extra ? {} : { accion: { texto: 'Deshacer', onClick: deshacer } })

      // Flujo de limpieza continuo: con "Sin categorizar" activo, pasa solo al siguiente
      if (siguiente) setTimeout(() => setSelector(selectorDeFila(siguiente)), 280)
    },
    [f.cat, avisar, iconoDe, recargarConteo] // eslint-disable-line react-hooks/exhaustive-deps
  )

  function selectorDeFila(m) {
    return { items: [m], movimiento: m, categoriaActual: m.categoria, titulo: 'Categoría', subtitulo: m.descripcion, clave: m.id }
  }
  const abrirChip = useCallback((m) => setSelector(selectorDeFila(m)), [])

  // Nombre propio desde la lista: solo cambia lo que se ve; el texto del banco queda en el detalle.
  const [renombrando, setRenombrando] = useState(null)
  const [repeticionesNombre, setRepeticionesNombre] = useState(0)
  const abrirNombre = useCallback((m) => {
    setRenombrando(m)
    setRepeticionesNombre(0)
    api.similaresConteo(m.descripcion, m.id).then((r) => setRepeticionesNombre(Number(r?.conteo) || 0)).catch(() => {})
  }, [])
  async function guardarNombre(texto, recordar) {
    const m = renombrando
    try {
      const limpio = limpiarNombre(texto)
      const actualizado = await api.editarMovimiento(m.id, { titulo: limpio, ...(recordar ? { recordar_titulo: true } : {}) })
      parchearEnCaches(actualizado)
      setMovimientos((prev) => prev.map((x) => (x.id === m.id ? { ...x, ...actualizado } : x)))
      setRenombrando(null)
      avisar(limpio ? 'Nombre guardado' : 'Volvió el nombre del banco', 'ok')
    } catch (err) {
      avisar(err.message || 'No se pudo guardar. Revisa tu conexión e intenta de nuevo.')
    }
  }
  function abrirChipGrupo(g) {
    setSelector({
      items: g.items,
      movimiento: g.items[0],
      categoriaActual: g.mixta ? '' : g.categoria,
      titulo: 'Categoría del comercio',
      subtitulo: `${g.nombre} · ${g.conteo} movimientos`,
      clave: g.huella,
    })
  }
  function abrirChipMasivo() {
    const items = movimientos.filter((m) => seleccionados.has(m.id))
    setSelector({
      items, movimiento: null, categoriaActual: '', masivo: true,
      titulo: 'Categoría para la selección', subtitulo: `${items.length} seleccionados`, clave: 'masivo',
    })
  }

  const confirmarUno = useCallback(
    async (m) => {
      try {
        await api.confirmarCategorias([m.id])
        setMovimientos((prev) => prev.map((x) => (x.id === m.id ? { ...x, cat_confirmada: true, cat_origen: null } : x)))
        recargarConteo()
      } catch {
        avisar('No se pudo confirmar la categoría. Revisa tu conexión e intenta de nuevo.')
      }
    },
    [avisar, recargarConteo]
  )

  async function confirmarTodas() {
    const ok = await confirmar(
      'Se dejarán como correctas las categorías que la app puso sola. Los de "Otros" siguen pendientes.',
      { titulo: `¿Confirmar ${conteo.auto} categorías?`, confirmarTexto: 'Confirmar todas' }
    )
    if (!ok) return
    try {
      await api.confirmarCategorias(null)
      const { items, hay } = await traerHasta(Math.max(TAMANO_PAGINA, movimientos.length))
      setMovimientos(items)
      setHayMas(hay)
      recargarConteo()
    } catch {
      avisar('No se pudieron confirmar. Revisa tu conexión e intenta de nuevo.')
    }
  }

  async function cargarMas() {
    setCargandoMas(true)
    try {
      const siguientes = await pedir(movimientos.length)
      setMovimientos((prev) => [...prev, ...siguientes])
      setHayMas(siguientes.length === TAMANO_PAGINA)
    } catch {
      avisar('No se pudieron cargar más movimientos. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setCargandoMas(false)
    }
  }

  async function exportar(formato) {
    setExportando(true)
    try {
      await (formato === 'xlsx' ? api.exportarExcel() : api.exportarCSV())
    } catch {
      avisar('No se pudo exportar. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setExportando(false)
    }
  }

  // --- Selección múltiple ---
  const alternar = useCallback((id, entrar = false) => {
    setModoSeleccion(true)
    setSeleccionados((prev) => {
      const n = new Set(prev)
      if (entrar || !n.has(id)) n.add(id)
      else n.delete(id)
      return n
    })
  }, [])

  function salirModoSeleccion() {
    setModoSeleccion(false)
    setSeleccionados(new Set())
  }
  const seleccionarTodoFiltrado = () => setSeleccionados(new Set(filtrados.map((m) => m.id)))
  function seleccionarSimilares() {
    const huellas = new Set(movimientos.filter((m) => seleccionados.has(m.id)).map(huellaDe))
    setSeleccionados((prev) => {
      const n = new Set(prev)
      for (const m of filtrados) if (huellas.has(huellaDe(m))) n.add(m.id)
      return n
    })
  }

  async function moverSeleccion(cuentaId) {
    setMoverACuenta(false)
    const ids = [...seleccionados]
    setAplicando(true)
    try {
      const r = await api.moverMovimientosMasivo(ids, cuentaId)
      const idSet = new Set(ids)
      setMovimientos((prev) => prev.map((m) => (idSet.has(m.id) && m.fuente !== 'transferencia_interna' ? { ...m, cuenta_id: cuentaId } : m)))
      await recargarCuentas?.()
      const destino = cuentas.find((c) => c.id === cuentaId)?.nombre || 'la cuenta'
      avisar(
        r.omitidos
          ? `${r.actualizados} movidos a ${destino}. ${r.omitidos} no se pudieron mover (transferencias, aportes a metas u otra moneda).`
          : `${r.actualizados} movimientos movidos a ${destino}`,
        'ok'
      )
      salirModoSeleccion()
    } catch (err) {
      avisar(err.message || 'No se pudieron mover. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setAplicando(false)
    }
  }

  async function eliminarSeleccion() {
    const ids = [...seleccionados]
    const titulo = `¿Eliminar ${ids.length} ${ids.length === 1 ? 'movimiento' : 'movimientos'}?`
    const aviso = 'El saldo de las cuentas se ajustará como si estos movimientos nunca hubieran existido. Esto no se puede deshacer.'
    // Si alguno vino del correo o de un extracto se pregunta UNA sola vez «¿Qué pasó?» para todos (no uno por uno).
    // Sin ninguno de esos, es la confirmación de siempre y el servidor aplica «duplicado» (no hay correo que vuelva).
    let motivo
    if (movimientos.some((m) => ids.includes(m.id) && vinoDeCorreoOExtracto(m))) {
      motivo = await elegir(aviso, { titulo: `${titulo} ¿Qué pasó?`, opciones: OPCIONES_BORRADO_VARIOS })
      if (!motivo) return
    } else {
      const ok = await confirmar(aviso, { titulo, confirmarTexto: 'Eliminar', peligro: true })
      if (!ok) return
    }
    setAplicando(true)
    // Optimista: las filas salen de la lista al instante (el servidor tarda 150-300 ms por viaje).
    // Las transferencias se omiten en el servidor, así que desde el principio no se quitan.
    const previa = movimientos
    const omitidas = new Set(movimientos.filter((m) => ids.includes(m.id) && m.fuente === 'transferencia_interna').map((m) => m.id))
    const borrados = ids.filter((id) => !omitidas.has(id))
    const set = new Set(borrados)
    setMovimientos((prev) => prev.filter((m) => !set.has(m.id)))
    try {
      const r = await (motivo ? api.eliminarMovimientosMasivo(ids, motivo) : api.eliminarMovimientosMasivo(ids))
      borrados.forEach((id) => quitarDeCaches(id))
      recargarCuentas?.() // los saldos se actualizan en segundo plano: no se espera
      recargarConteo()
      avisar(
        r.omitidos
          ? `${r.actualizados} eliminados. ${r.omitidos} no se eliminaron (las transferencias se borran de una en una).`
          : `${r.actualizados} ${r.actualizados === 1 ? 'movimiento eliminado' : 'movimientos eliminados'}`,
        'ok'
      )
      salirModoSeleccion()
    } catch (err) {
      setMovimientos(previa) // no se pudo: vuelven a aparecer
      avisar(err.message || 'No se pudieron eliminar. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setAplicando(false)
    }
  }

  // --- Detalle como panel lateral (≥1024 px): la lista no se desmonta ---
  const abrirPanel = useCallback((id) => cambiarParams({ mov: id }), [cambiarParams])
  const cerrarPanel = useCallback(() => cambiarParams({ mov: '' }), [cambiarParams])
  function alCambioDetalle(actualizado, eliminadoId) {
    if (eliminadoId) {
      quitarDeCaches(eliminadoId)
      setMovimientos((prev) => prev.filter((m) => m.id !== eliminadoId))
    } else if (actualizado) {
      parchearEnCaches(actualizado)
      setMovimientos((prev) => prev.map((m) => (m.id === actualizado.id ? { ...m, ...actualizado } : m)))
    }
    recargarConteo()
  }

  const nombreCuenta = (id) => cuentas.find((c) => c.id === id)?.nombre || 'Cuenta'
  const nombreCuentaTabla = useCallback((id) => cuentas.find((c) => c.id === id)?.nombre || 'Cuenta', [cuentas])
  const enTabla = lateral && f.tabla && !f.comercio
  const alternarTodos = useCallback(
    (marcar) => {
      if (marcar) {
        setModoSeleccion(true)
        setSeleccionados(new Set(filtrados.map((m) => m.id)))
      } else {
        setSeleccionados(new Set())
      }
    },
    [filtrados]
  )
  const chipsActivos = [
    f.q && { k: 'q', texto: `Texto: ${f.q}` },
    f.cuenta && { k: 'cuenta', texto: nombreCuenta(f.cuenta) },
    f.cat && f.cat !== 'Otros' && { k: 'cat', texto: f.cat },
    f.tipo && { k: 'tipo', texto: { income: 'Ingresos', expense: 'Gastos', transfer: 'Transferencias' }[f.tipo] || f.tipo },
    f.origen && { k: 'origen', texto: ORIGENES_FILTRO.find((o) => o.id === f.origen)?.texto || f.origen },
    f.desde && { k: 'desde', texto: `Desde ${f.desde}` },
    f.hasta && { k: 'hasta', texto: `Hasta ${f.hasta}` },
  ].filter(Boolean)

  const campo = 'rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-xs'
  const botonChip = (activo) =>
    `shrink-0 text-sm px-4 py-1.5 min-h-[44px] rounded-full border font-medium ${
      activo ? 'bg-accent text-paper-raised border-accent' : 'border-accent text-accent'
    }`

  return (
    <div ref={raiz} className="flex-1 overflow-y-auto pb-6 screen-enter pantalla-ancha">
      <header className="px-5 pantalla-top pb-4 flex flex-wrap items-center justify-between gap-y-2">
        <h1 className="text-2xl font-semibold">Movimientos</h1>
        {modoSeleccion ? (
          <button onClick={salirModoSeleccion} className="text-sm text-accent font-medium min-h-[44px] px-2">
            Cancelar
          </button>
        ) : (
          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={() => actualizarCorreo(true)}
              disabled={leyendoCorreo}
              aria-label="Actualizar desde el correo"
              className="w-11 h-11 rounded-full border border-line text-ink-soft flex items-center justify-center disabled:opacity-60"
            >
              <RefreshCw size={16} className={leyendoCorreo ? 'animate-spin' : ''} />
            </button>
            <button
              onClick={() => setModoSeleccion(true)}
              className="text-xs text-ink-soft font-medium px-3 min-h-[44px] rounded-full border border-line"
            >
              Seleccionar
            </button>
            <button
              onClick={() => setMostrarFiltros((v) => !v)}
              aria-label="Filtros de fecha y cuenta"
              aria-expanded={filtrosVisibles}
              className={`w-11 h-11 rounded-full border flex items-center justify-center ${
                filtrosVisibles ? 'bg-accent-soft border-accent text-accent' : 'border-line text-ink-soft'
              }`}
            >
              <SlidersHorizontal size={16} />
            </button>
            <button
              onClick={() => exportar('csv')}
              disabled={exportando}
              className="w-11 h-11 rounded-full border border-line text-ink-soft flex items-center justify-center disabled:opacity-50"
              aria-label="Exportar CSV"
            >
              <Download size={16} />
            </button>
            <Link
              to="/sincronizacion"
              state={{ abrir: 'subir', manual: true }}
              className="w-11 h-11 rounded-full border border-line text-ink-soft flex items-center justify-center"
              aria-label="Importar desde Excel o CSV"
            >
              <Upload size={16} />
            </Link>
          </div>
        )}
      </header>

      <p role="status" aria-live="polite" className="px-5 -mt-2 mb-2 text-xs text-ink-soft min-h-[16px]" data-testid="estado-correo">
        {leyendoCorreo ? 'Leyendo tu correo…' : avisoCorreo}
      </p>

      {/* ≥1024 px: filtros (o el detalle del movimiento) a la izquierda, lista a la derecha */}
      <div className={`dos-col ${enTabla ? 'dos-col-riel-tabla' : 'dos-col-5-6'}`}>
        <div className="col col-sticky lg:max-h-[calc(100svh-2rem)] lg:overflow-y-auto">
          {panelId ? (
            <DetalleMovimiento key={panelId} id={panelId} embebido onCerrar={cerrarPanel} onCambio={alCambioDetalle} />
          ) : (
            <>
              <div className="px-5 mb-3">
                <div className="flex items-center gap-2 bg-paper-raised border border-line rounded-2xl px-4 py-3">
                  <Search size={20} className="text-ink-soft" />
                  <input
                    value={texto}
                    aria-label="Buscar movimiento"
                    data-atajo-buscar
                    onChange={(e) => setTexto(e.target.value)}
                    placeholder="Buscar movimiento"
                    className="bg-transparent outline-none text-sm flex-1 placeholder:text-ink-soft"
                  />
                </div>
              </div>

              {/* Del listado al detalle: en qué se va la plata (por categoría, comercio y periodo) */}
              <div className="px-5 mb-3">
                <Link
                  to="/informe"
                  data-testid="ver-detalle-gastos"
                  className="flex items-center gap-3 rounded-2xl border border-line bg-paper-raised px-4 min-h-[52px]"
                >
                  <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
                    <PieChart size={20} aria-hidden="true" />
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm font-semibold leading-tight">Ver detalle de tus gastos</span>
                    <span className="block text-xs text-ink-soft mt-0.5">Por categoría, comercio y periodo</span>
                  </span>
                  <ChevronRight size={16} className="text-ink-soft shrink-0" aria-hidden="true" />
                </Link>
              </div>

              {(porCorreo.correos.length > 0 || descartados > 0) && (
                <div className="px-5 mb-3 flex flex-col gap-2" data-testid="accesos-correo">
                  {porCorreo.correos.length > 0 && (
                    <button
                      onClick={() => cambiarParams({ filtro: 'por-revisar' })}
                      className="w-full min-h-[56px] flex items-center gap-3 rounded-2xl bg-accent-soft/50 border border-accent/30 px-4 py-2.5 text-left"
                    >
                      <span className="flex-1 min-w-0">
                        <span className="block text-sm font-semibold text-accent">Correos por revisar ({porCorreo.correos.length})</span>
                        <span className="block text-xs text-ink-soft">Los leí de tu banco. Apruébalos para que pasen a tu lista.</span>
                      </span>
                      <ChevronRight size={16} className="text-ink-soft shrink-0" aria-hidden="true" />
                    </button>
                  )}
                  {descartados > 0 && (
                    <button
                      onClick={() => navigate('/sincronizacion', { state: { abrir: 'correos-descartados' } })}
                      className="w-full min-h-[56px] flex items-center gap-3 rounded-2xl bg-paper-raised border border-line px-4 py-2.5 text-left"
                    >
                      <span className="flex-1 min-w-0">
                        <span className="block text-sm font-semibold">Correos descartados ({descartados >= 100 ? '99+' : descartados})</span>
                        <span className="block text-xs text-ink-soft">Los descartaste al borrar un movimiento parecido. Recupéralos si sí eran tuyos.</span>
                      </span>
                      <ChevronRight size={16} className="text-ink-soft shrink-0" aria-hidden="true" />
                    </button>
                  )}
                </div>
              )}

              <div className="px-5 mb-3 flex gap-2 overflow-x-auto no-scrollbar lg:flex-wrap lg:overflow-visible">
                {(porCorreo.correos.length > 0 || soloCorreo) && (
                  <button onClick={() => cambiarParams({ filtro: soloCorreo ? '' : 'por-revisar' })} aria-pressed={soloCorreo} className={botonChip(soloCorreo)}>
                    Del correo por revisar{porCorreo.correos.length > 0 ? ` (${porCorreo.correos.length})` : ''}
                  </button>
                )}
                {/* Sin repetir la misma lista con dos nombres: «Por revisar» no sale si es idéntica a «Sin categorizar»,
                    y «Por confirmar» solo sale cuando hay además otra clase de pendientes. */}
                {(((conteo.total > 0) && !(conteo.otros > 0 && conteo.auto === 0)) || f.revisar) && (
                  <button onClick={() => cambiarParams({ revisar: !f.revisar })} aria-pressed={f.revisar} className={botonChip(f.revisar)}>
                    Por revisar{conteo.total > 0 ? ` (${conteo.total})` : ''}
                  </button>
                )}
                {(conteo.otros > 0 || f.cat === 'Otros') && (
                  <button
                    onClick={() => cambiarParams({ cat: f.cat === 'Otros' ? '' : 'Otros' })}
                    aria-pressed={f.cat === 'Otros'}
                    className={botonChip(f.cat === 'Otros')}
                  >
                    Sin categorizar{conteo.otros > 0 ? ` (${conteo.otros})` : ''}
                  </button>
                )}
                {((conteo.auto > 0 && conteo.otros > 0) || f.conf) && (
                  <button onClick={() => cambiarParams({ conf: !f.conf })} aria-pressed={f.conf} className={botonChip(f.conf)}>
                    Por confirmar{conteo.auto > 0 ? ` (${conteo.auto})` : ''}
                  </button>
                )}
              </div>
              {conteo.total > 0 && !f.revisar && (
                <div className="px-5 mb-3">
                  <Link to="/categorizar" className="text-xs text-ink-soft font-medium underline">
                    Si quieres, ordena lo que más pesa
                  </Link>
                </div>
              )}
              {f.revisar && conteo.auto > 0 && (
                <div className="px-5 mb-3">
                  <button onClick={confirmarTodas} className="text-xs text-ink-soft font-medium underline">
                    Confirmar las {conteo.auto} automáticas
                  </button>
                </div>
              )}

              {filtrosVisibles && (
                <div className="px-5 mb-3 grid grid-cols-2 gap-2 [.dos-col-riel-tabla_&]:grid-cols-1">
                  <input
                    type="date"
                    aria-label="Desde"
                    value={f.desde}
                    onChange={(e) => cambiarParams({ desde: e.target.value })}
                    className={campo}
                  />
                  <input
                    type="date"
                    aria-label="Hasta"
                    value={f.hasta}
                    onChange={(e) => cambiarParams({ hasta: e.target.value })}
                    className={campo}
                  />
                  {cuentas.length > 1 && (
                    <select
                      aria-label="Filtrar por cuenta"
                      value={f.cuenta}
                      onChange={(e) => cambiarParams({ cuenta: e.target.value })}
                      className={campo}
                    >
                      <option value="">Todas las cuentas</option>
                      {cuentas.map((c) => (
                        <option key={c.id} value={c.id}>{c.nombre}</option>
                      ))}
                    </select>
                  )}
                  <select
                    aria-label="Filtrar por categoría"
                    value={f.cat}
                    onChange={(e) => cambiarParams({ cat: e.target.value })}
                    className={campo}
                  >
                    <option value="">Todas las categorías</option>
                    {[...new Set([...CATEGORIAS, ...(f.cat ? [f.cat] : [])])].map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <select
                    aria-label="Filtrar por tipo"
                    value={f.tipo}
                    onChange={(e) => cambiarParams({ tipo: e.target.value })}
                    className={campo}
                  >
                    <option value="">Ingresos y gastos</option>
                    <option value="expense">Solo gastos</option>
                    <option value="income">Solo ingresos</option>
                    <option value="transfer">Transferencias</option>
                  </select>
                  <select
                    aria-label="Filtrar por origen"
                    value={f.origen}
                    onChange={(e) => cambiarParams({ origen: e.target.value })}
                    className={campo}
                  >
                    <option value="">Todos los orígenes</option>
                    {ORIGENES_FILTRO.map((o) => (
                      <option key={o.id} value={o.id}>{o.texto}</option>
                    ))}
                  </select>
                  <button onClick={() => exportar('xlsx')} className="text-xs text-accent font-medium px-2 text-left" aria-label="Exportar a Excel">
                    Exportar .xlsx
                  </button>
                </div>
              )}

              {activos && (
                <div className="px-5 mb-3 flex items-center flex-wrap gap-2" aria-label="Filtros activos">
                  {chipsActivos.map((c) => (
                    <button
                      key={c.k}
                      onClick={() => cambiarParams({ [c.k]: '' })}
                      aria-label={`Quitar filtro ${c.texto}`}
                      className="inline-flex items-center gap-1 text-xs px-3 min-h-[32px] rounded-full bg-ink text-paper"
                    >
                      {c.texto} <X size={16} aria-hidden="true" />
                    </button>
                  ))}
                  <button
                    onClick={() => {
                      setTexto('')
                      cambiarParams({ q: '', cuenta: '', cat: '', tipo: '', origen: '', desde: '', hasta: '', revisar: false, conf: false })
                    }}
                    className="text-xs font-semibold text-accent underline px-1 min-h-[32px]"
                  >
                    Limpiar
                  </button>
                </div>
              )}

              {activos && filtrados.length > 0 && (
                <div className="px-5 mb-3 flex gap-3">
                  <div className="flex-1 rounded-2xl bg-paper-raised border border-line p-3">
                    <p className="text-[11px] text-ink-soft uppercase tracking-wide">Ingresos</p>
                    <p className="text-sm font-bold text-gold mt-0.5">{formatCOP(totalIngresos)}</p>
                  </div>
                  <div className="flex-1 rounded-2xl bg-paper-raised border border-line p-3">
                    <p className="text-[11px] text-ink-soft uppercase tracking-wide">Gastos</p>
                    <p className="text-sm font-bold text-ink mt-0.5">{formatCOP(totalGastos)}</p>
                  </div>
                </div>
              )}

              <div className="px-5 mb-4 flex items-center gap-2">
                <div role="group" aria-label="Vista" className="inline-flex rounded-full border border-line p-0.5 bg-paper-raised">
                  {[
                    { id: 'lista', texto: 'Lista' },
                    ...(lateral ? [{ id: 'tabla', texto: 'Tabla' }] : []),
                    { id: 'comercio', texto: 'Por comercio' },
                  ].map((v) => (
                    <button
                      key={v.texto}
                      aria-pressed={vistaActiva === v.id}
                      onClick={() => cambiarParams({ vista: v.id === 'lista' ? '' : v.id })}
                      className={`text-sm px-4 min-h-[44px] rounded-full font-medium ${
                        vistaActiva === v.id ? 'bg-ink text-paper' : 'text-ink-soft'
                      }`}
                    >
                      {v.texto}
                    </button>
                  ))}
                </div>
                {f.comercio && (
                  <select
                    aria-label="Ordenar comercios"
                    value={f.orden}
                    onChange={(e) => cambiarParams({ orden: e.target.value === 'monto' ? 'monto' : '' })}
                    className={`${campo} ml-auto`}
                  >
                    <option value="cantidad">Más movimientos</option>
                    <option value="monto">Mayor monto</option>
                  </select>
                )}
              </div>
            </>
          )}
        </div>

        <div className="col">
          <PorRevisarCorreo correos={porCorreo.correos} onResuelto={correoResuelto} onCuentaCreada={porCorreo.recargar} onRecargar={porCorreo.recargar} className="mx-5 mb-4" />
          {soloCorreo ? (
            porCorreo.cargado && porCorreo.correos.length === 0 && (
              <EstadoVacio icono={ListChecks} titulo="Nada por revisar del correo" texto="Cuando llegue una notificación de tu banco, la verás aquí con su fecha." className="mx-5" />
            )
          ) : cargando ? (
            <EsqueletoLista filas={8} className="mx-5" etiqueta="Cargando movimientos" />
          ) : errorCarga ? (
            <div role="alert" className="mx-5 rounded-3xl bg-danger-soft border border-danger/30 p-6 text-center">
              <p className="text-sm text-danger">{errorCarga}</p>
            </div>
          ) : filtrados.length === 0 && chipsActivos.length === 0 && !f.revisar && !f.cat && !f.conf && !f.comercio ? (
            // Sin ningún filtro y sin filas: la persona aún no tiene movimientos (no es "búsqueda sin resultados")
            <EstadoVacio
              icono={ListChecks}
              titulo="Aún no tienes movimientos"
              texto="Anota el primero o trae los de tu banco: aquí los verás ordenados por día."
              className="mx-5"
            >
              <div className="mt-4 flex flex-col gap-2">
                <Boton to="/agregar" bloque>Anotar un movimiento</Boton>
                <Boton to="/sincronizacion" variante="secundario" bloque>Traer movimientos del banco</Boton>
              </div>
            </EstadoVacio>
          ) : filtrados.length === 0 ? (
            <EstadoVacio
              icono={Search}
              titulo={f.revisar && chipsActivos.length === 0 && !f.cat && !f.conf ? 'Todo está revisado' : 'No hay movimientos que coincidan'}
              texto={
                f.revisar && chipsActivos.length === 0 && !f.cat && !f.conf
                  ?'No hay categorías automáticas pendientes ni movimientos en "Otros".'
                  : 'Prueba con otro filtro o búsqueda.'
              }
              className="mx-5"
            />
          ) : f.comercio ? (
            <div className="mx-5 space-y-2.5">
              {gruposComercio.map((g) => (
                <div key={g.huella} className="rounded-2xl border border-line bg-paper-raised p-3" data-comercio={g.huella}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold truncate">{g.nombre}</p>
                      <p className="text-xs text-ink-soft mt-0.5">
                        {g.conteo} {g.conteo === 1 ? 'movimiento' : 'movimientos'} · {formatCOP(g.total)}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => abrirChipGrupo(g)}
                      aria-label={`Categoría de ${g.nombre}`}
                      className="inline-flex items-center gap-1 text-sm rounded-full border border-accent text-accent px-3 min-h-[40px] shrink-0"
                    >
                      {g.mixta ? <Icono icono={Shuffle} tam="sm" /> : <span aria-hidden="true">{iconoDe(g.categoria)}</span>} {g.mixta ? 'Varias' : g.categoria}
                      <ChevronDown size={16} aria-hidden="true" />
                    </button>
                  </div>
                  <button
                    onClick={() =>
                      setExpandidos((prev) => {
                        const n = new Set(prev)
                        if (n.has(g.huella)) n.delete(g.huella)
                        else n.add(g.huella)
                        return n
                      })
                    }
                    aria-expanded={expandidos.has(g.huella)}
                    className="mt-1 text-xs text-ink-soft underline min-h-[32px]"
                  >
                    {expandidos.has(g.huella) ? 'Ocultar movimientos' : 'Ver movimientos'}
                  </button>
                  {expandidos.has(g.huella) && (
                    <ul className="mt-1 divide-y divide-line">
                      {g.items.slice(0, 50).map((m) => (
                        <li key={m.id}>
                          <Link
                            to={`/movimientos/${m.id}`}
                            onClick={(e) => {
                              if (lateral) {
                                e.preventDefault()
                                abrirPanel(m.id)
                              }
                            }}
                            className="flex items-start justify-between gap-3 py-2.5 min-h-[44px] text-xs"
                          >
                            <span className="min-w-0 break-words">
                              <span className="block line-clamp-3">{nombreDe(m)}</span>
                              <span className="block text-ink-soft">{fechaHoraMovimiento(fechaDeMovimiento(m))}</span>
                            </span>
                            <span className="font-semibold shrink-0">{formatMoneda(m.monto, monedaDe[m.cuenta_id])}</span>
                          </Link>
                        </li>
                      ))}
                      {g.items.length > 50 && <li className="py-2 text-xs text-ink-soft">y {g.items.length - 50} más</li>}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          ) : enTabla ? (
            <TablaMovimientos
              items={filtrados}
              iconoDe={iconoDe}
              monedaDe={monedaDe}
              nombreCuenta={nombreCuentaTabla}
              seleccionados={seleccionados}
              panelId={panelId}
              onToggle={alternar}
              onToggleTodos={alternarTodos}
              onAbrir={abrirPanel}
              onChip={abrirChip}
            />
          ) : (
            <div className="mx-5 relative pl-5">
              <div className="absolute left-[9px] top-1.5 bottom-1.5 w-0.5 bg-line" />
              <div ref={listaRef} style={{ paddingTop: ventana.arriba, paddingBottom: ventana.abajo }}>
              {gruposDia.slice(ventana.ini, ventana.fin).map((grupo, k) => {
                const gi = ventana.ini + k
                return (
                <div key={grupo.diaKey} data-dia={grupo.diaKey} className={gi === 0 ? '' : 'pt-5'}>
                  <p className="text-[11px] font-bold text-ink-soft uppercase tracking-wide mb-1">
                    {grupo.label}
                  </p>
                  {grupo.items.map((m, i) => (
                    <FilaMovimiento
                      key={m.id}
                      m={m}
                      icono={iconoDe(m.categoria)}
                      moneda={monedaDe[m.cuenta_id]}
                      cuentaNombre={nombreCuentaTabla(m.cuenta_id)}
                      esSel={seleccionados.has(m.id)}
                      modoSel={modoSeleccion}
                      panel={lateral}
                      botonConfirmar={f.revisar}
                      indice={gi === 0 ? Math.min(i, 12) : 0}
                      onToggle={alternar}
                      onChip={abrirChip}
                      onConfirmar={confirmarUno}
                      onAbrir={abrirPanel}
                      onNombre={abrirNombre}
                    />
                  ))}
                </div>
                )
              })}
              </div>
            </div>
          )}

          {!cargando && !errorCarga && hayMas && (
            <div className="px-5 mt-6">
              <button
                onClick={cargarMas}
                disabled={cargandoMas}
                className="w-full rounded-2xl border border-line bg-paper-raised py-3.5 text-sm font-semibold text-ink-soft disabled:opacity-60"
              >
                {cargandoMas ? 'Cargando...' : 'Cargar movimientos anteriores'}
              </button>
            </div>
          )}
        </div>
      </div>

      {selector && (
        <SelectorCategoria
          key={selector.clave}
          titulo={selector.titulo}
          subtitulo={selector.subtitulo}
          categoriaActual={selector.categoriaActual}
          movimiento={selector.movimiento}
          recientes={recientes}
          onCerrar={() => setSelector(null)}
          onElegir={(cat, opts) => {
            const s = selector
            categorizar(s.items, cat, opts)
            if (s.masivo) salirModoSeleccion()
          }}
        />
      )}

      {renombrando && (
        <Hoja onCerrar={() => setRenombrando(null)} titulo="Nombre del movimiento">
          {({ cerrar }) => (
            <>
              <h2 className="text-lg font-semibold mb-2">Nombre del movimiento</h2>
              <EditorNombre
                original={renombrando.descripcion}
                valor={renombrando.titulo || ''}
                conRecordar
                recordarInicial={repeticionesNombre + 1 >= MIN_REPETICIONES_NOMBRE}
                onCancelar={cerrar}
                onGuardar={guardarNombre}
              />
            </>
          )}
        </Hoja>
      )}

      {moverACuenta && (
        <Hoja onCerrar={() => setMoverACuenta(false)} titulo="Mover a otra cuenta">
          {({ cerrar }) => (
            <>
              <h2 className="text-lg font-semibold mb-1">Mover a otra cuenta</h2>
              <p className="text-xs text-ink-soft mb-3">
                {seleccionados.size} seleccionados. Los saldos de ambas cuentas se ajustan solos.
              </p>
              <div className="space-y-2">
                {cuentas.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => moverSeleccion(c.id)}
                    className="w-full text-left rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm font-medium min-h-[44px]"
                  >
                    {c.nombre}
                  </button>
                ))}
              </div>
              <button onClick={cerrar} className="w-full mt-3 rounded-2xl border border-line py-3 text-sm font-semibold">
                Cancelar
              </button>
            </>
          )}
        </Hoja>
      )}

      {modoSeleccion && (
        <div className="sticky bottom-0 mx-5 mt-4 rounded-2xl bg-ink p-3 shadow-lg pop-in z-10" role="toolbar" aria-label="Acciones sobre la selección">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-paper font-medium shrink-0 px-1" aria-live="polite">
              {seleccionados.size} seleccionado{seleccionados.size === 1 ? '' : 's'}
            </span>
            <button
              disabled={seleccionados.size === 0 || aplicando}
              onClick={abrirChipMasivo}
              className="rounded-xl bg-paper text-ink px-3 min-h-[44px] text-sm font-semibold disabled:opacity-40"
            >
              Categoría
            </button>
            {cuentas.length > 1 && (
              <button
                disabled={seleccionados.size === 0 || aplicando}
                onClick={() => setMoverACuenta(true)}
                className="rounded-xl bg-paper text-ink px-3 min-h-[44px] text-sm font-semibold disabled:opacity-40"
              >
                Cuenta
              </button>
            )}
            <button
              disabled={seleccionados.size === 0 || aplicando}
              onClick={eliminarSeleccion}
              className="rounded-xl bg-danger text-paper-raised px-3 min-h-[44px] text-sm font-semibold disabled:opacity-40 flex items-center gap-1"
            >
              <Trash2 size={16} /> Eliminar
            </button>
            <button
              onClick={salirModoSeleccion}
              className="ml-auto w-11 h-11 shrink-0 rounded-xl bg-paper flex items-center justify-center"
              aria-label="Cerrar"
            >
              <X size={16} className="text-ink" />
            </button>
          </div>
          <div className="flex gap-3 mt-2 px-1">
            <button onClick={seleccionarTodoFiltrado} className="text-xs text-paper underline min-h-[32px]">
              Seleccionar todo lo filtrado ({filtrados.length})
            </button>
            <button
              onClick={seleccionarSimilares}
              disabled={seleccionados.size === 0}
              className="text-xs text-paper underline min-h-[32px] disabled:opacity-40"
            >
              Seleccionar los similares
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
