import { error as hapticoError, exito } from '../lib/haptico'
import { mensajeDeError } from '../lib/mensajes'
import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { EsqueletoLista } from '../components/Esqueletos'
import { EstadoVacio } from '../brand/Marca'
import { Boton, Chip } from '../components/ui'
import { Link, useLocation, useNavigate, useNavigationType, useSearchParams } from 'react-router-dom'
import { ArrowLeftRight, Check, Mail, RefreshCw, ChevronDown, ChevronRight, Download, ListChecks, MoreHorizontal, PieChart, Search, Shuffle, SlidersHorizontal, Tag, Trash2, Upload, X } from 'lucide-react'
import Icono from '../components/Icono'
import { formatCOP, formatMoneda } from '../lib/format'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import { useDialogos } from '../lib/DialogosContext'
import { contextoDeCuentas, tiposEfectivos, totalesConTipos } from '../lib/contabilidad'
import { rangoPeriodo } from '../lib/informe'
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
import { fechaHoraMovimiento, horaCorta, fechaDeMovimiento, claveDia, etiquetaDia } from '../lib/fechaMovimiento'
import PorRevisarCorreo from '../components/PorRevisarCorreo'
import TarjetaMovimientosCorreo from '../components/TarjetaMovimientosCorreo'
import { BotonLapiz, EditorNombre, PistaBanco } from '../components/NombreEditable'
import { limpiarNombre, MIN_REPETICIONES_NOMBRE, nombreDe, tieneNombrePropio } from '../lib/tituloMovimiento'
import { usePorRevisarCorreo } from '../lib/usePorRevisarCorreo'
import { OPCIONES_BORRADO, OPCIONES_BORRADO_VARIOS, vinoDeCorreoOExtracto } from '../lib/canales'
import FilaDeslizable from '../components/FilaDeslizable'
import { actualizarDesdeCorreo, resumenActualizacion } from '../lib/sincronizarGmail'
import { useJalarParaRefrescar } from '../lib/jalarRefrescar'

const TAMANO_PAGINA = 200
// En escritorio ancho (≥1280 px) la TABLA es la vista por defecto (más densa y ordenable); en 1024-1279 px es angosta y la
// lista se lee mejor. Lo que la persona elija se recuerda.
const VISTA_GUARDADA = 'cuadrame:mov-vista'
function leerVistaGuardada() {
  try {
    const v = localStorage.getItem(VISTA_GUARDADA)
    return v === 'lista' || v === 'tabla' ? v : null
  } catch {
    return null
  }
}
function useAnchoDeTabla() {
  const consulta = '(min-width: 1280px)'
  const [ancha, setAncha] = useState(() => typeof window !== 'undefined' && !!window.matchMedia?.(consulta).matches)
  useEffect(() => {
    if (!window.matchMedia) return undefined
    const m = window.matchMedia(consulta)
    const alCambiar = () => setAncha(m.matches)
    m.addEventListener?.('change', alCambiar)
    alCambiar()
    return () => m.removeEventListener?.('change', alCambiar)
  }, [])
  return ancha
}
const MAX_LOTES = 15 // tope de seguridad al re-pedir lo ya cargado (3.000 movimientos)
const PRESION_LARGA_MS = 450
const ALTO_DIA_BASE = 40 // etiqueta del día + espacio, para estimar antes de medir
const ALTO_FILA_ESTIMADO = 68
const MARGEN_VENTANA = 800 // px extra arriba y abajo para que el scroll rápido no muestre vacío

// Una fila de la lista. Está memoizada: al categorizar UN movimiento solo se vuelve a pintar su
// fila (las demás reciben las mismas props y React las salta), clave con miles de movimientos.
const FilaMovimiento = memo(function FilaMovimiento({
  m, icono, moneda, cuentaNombre, esSel, modoSel, panel, botonConfirmar, indice, onToggle, onChip, onConfirmar, onAbrir, onNombre, onBorrar,
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
      className={`relative stagger-item [-webkit-touch-callout:none] rounded-2xl transition-colors ${
        esSel ? 'bg-accent-soft' : 'md:hover:bg-paper-raised'
      }`}
      style={{ '--stagger-i': indice }}
      data-fila={m.id}
      data-seleccionada={esSel || undefined}
      onPointerDown={empezar}
      onPointerMove={mover}
      onPointerUp={cancelar}
      onPointerCancel={cancelar}
      onPointerLeave={cancelar}
      onContextMenu={(e) => {
        if (larga.current) e.preventDefault()
      }}
    >
      <FilaDeslizable
        desactivada={modoSel || panel}
        acciones={[
          ...(esTransfer ? [] : [{ id: 'categoria', texto: 'Categoría', icono: <Tag size={20} aria-hidden="true" />, onClick: () => onChip(m) }]),
          { id: 'borrar', texto: 'Borrar', tono: 'peligro', confirmar: true, icono: <Trash2 size={20} aria-hidden="true" />, onClick: () => onBorrar?.(m) },
        ]}
      >
      <div className="flex items-start gap-3 px-1">
        <button
          type="button"
          role="checkbox"
          aria-checked={esSel}
          aria-label={`Seleccionar ${m.descripcion}`}
          onClick={() => onToggle(m.id)}
          className={`${modoSel ? 'flex' : 'hidden md:flex'} relative before:absolute before:-inset-3 before:content-[''] mt-[18px] w-5 h-5 rounded-md border-2 shrink-0 items-center justify-center ${
            esSel ? 'bg-accent border-accent' : 'border-line'
          }`}
        >
          {esSel && <Check size={16} className="text-paper-raised" />}
        </button>
        {/* La categoría se ve de un vistazo en el icono; el nombre y el cambio de categoría están en la segunda línea */}
        <span aria-hidden="true" className="mt-2.5 w-10 h-10 shrink-0 rounded-xl bg-accent-soft flex items-center justify-center text-lg leading-none">
          {esTransfer ? <Icono icono={ArrowLeftRight} tam="md" className="text-accent" /> : icono}
        </span>
        <div className="min-w-0 flex-1">
          <Link to={`/movimientos/${m.id}`} onClick={alClic} className="block pt-2.5 min-w-0">
            <p className="text-sm font-semibold break-words line-clamp-2" title={m.descripcion}>{nombreDe(m)}</p>
            {tieneNombrePropio(m) && <PistaBanco original={m.descripcion} />}
            <EtiquetaOrigen origen={m.origen} canales={m.canales} soloAvisos className="mt-1" />
          </Link>
          {/* El día ya está en el encabezado del grupo; la hora va bajo el monto. Aquí: categoría, cuenta y lo que haya que atender */}
          <div className="flex items-center flex-wrap gap-x-2 gap-y-0.5 pt-0.5 pb-2.5">
            {esTransfer ? (
              <span className="text-xs font-medium text-ink-soft">{m.categoria}</span>
            ) : (
              <button
                type="button"
                onClick={() => (modoSel ? onToggle(m.id) : onChip(m))}
                aria-label={`${m.categoria}${m.subcategoria ? ` · ${m.subcategoria}` : ''}. Cambiar categoría de ${m.descripcion}`}
                className="relative before:absolute before:-inset-y-2.5 before:-inset-x-1 before:content-[''] inline-flex items-center gap-1 text-xs font-semibold text-accent rounded-full max-w-full"
              >
                <span className="truncate">{m.categoria}{m.subcategoria ? ` · ${m.subcategoria}` : ''}</span>
                <ChevronDown size={16} aria-hidden="true" className="shrink-0" />
              </button>
            )}
            <span className="text-xs text-ink-soft truncate min-w-0 max-w-full flex-1" data-testid="fila-fecha-cuenta" title={cuentaNombre}>
              {cuentaNombre}
            </span>
            {onNombre && !esTransfer && !modoSel && <BotonLapiz original={m.descripcion} onClick={() => onNombre(m)} />}
            {traslado && !esTransfer && (
              <span className="text-xs font-semibold text-ink-soft rounded-full bg-paper-raised border border-line px-2 py-0.5">
                {traslado}
              </span>
            )}
            {esAuto(m) && <InsigniaAuto movimiento={m} />}
            {botonConfirmar && esAuto(m) && (
              <button
                onClick={() => onConfirmar(m)}
                aria-label={`Confirmar categoría de ${m.descripcion}`}
                className="btn btn-primario btn-sm"
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
          className="pt-3 shrink-0 max-w-[45%]"
        >
          <span className={`block text-right text-[15px] font-bold tabular-nums whitespace-nowrap ${direccion === 'income' ? 'text-gold' : direccion ? 'text-ink' : 'text-ink-soft'}`}>
            {signoDe(m)}
            {formatMoneda(m.monto, moneda)}
          </span>
          {horaCorta(fechaDeMovimiento(m)) && (
            <span className="block text-right text-xs text-ink-soft mt-0.5 tabular-nums whitespace-nowrap">{horaCorta(fechaDeMovimiento(m))}</span>
          )}
        </Link>
      </div>
      </FilaDeslizable>
    </div>
  )
})

// Neto del día (ingresos − gastos reales); vacío si el día solo tuvo traslados.
function SubtotalDia({ items, tipos }) {
  const { ingresos, gastos, neto } = totalesConTipos(items, tipos)
  if (!ingresos && !gastos) return null
  return (
    <span className="text-[11px] font-semibold text-ink-soft tabular-nums" data-testid="subtotal-dia">
      {neto < 0 ? '-' : '+'}{formatCOP(Math.abs(neto))}
    </span>
  )
}

export default function Movimientos() {
  const { cuentas, recargar: recargarCuentas } = useCuentas()
  const { nombres: CATEGORIAS, iconoDe } = useCategorias()
  const { avisar, confirmar, elegir } = useDialogos()
  const modo = useModoPantalla()
  const lateral = modo === 'lateral'
  const hayAnchoParaTabla = useAnchoDeTabla()
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
  const [conectadoCorreo, setConectadoCorreo] = useState(null) // lo mismo, para pintarlo
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
      setConectadoCorreo(gmailConectado.current)
      if (!gmailConectado.current) {
        if (manual) setAvisoCorreo('Conecta tu correo en «Movimientos del correo» para leer tus notificaciones.')
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
  const [intento, setIntento] = useState(0) // «Reintentar» tras un error de carga
  const [conteo, setConteo] = useState({ auto: 0, otros: 0, total: 0 })
  const [exportando, setExportando] = useState(false)
  const [mostrarFiltros, setMostrarFiltros] = useState(false)
  const [menuAcciones, setMenuAcciones] = useState(false)
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

  // Jalar hacia abajo arriba del todo: vuelve a pedir lo cargado, el conteo y lo que llegó por correo.
  const jalar = useJalarParaRefrescar(async () => {
    try {
      const { items, hay } = await traerHasta(Math.max(TAMANO_PAGINA, movimientos.length))
      setMovimientos(items)
      setHayMas(hay)
    } catch {
      /* se queda lo que había */
    }
    recargarConteo()
    porCorreo.recargar?.()
    actualizarCorreo(false)
  })
  const asignarRaiz = useCallback(
    (nodo) => {
      raiz.current = nodo
      jalar.ref(nodo)
    },
    [jalar.ref] // eslint-disable-line react-hooks/exhaustive-deps
  )

  useEffect(() => {
    const cambioFiltro = ultimaConsulta.current !== null && ultimaConsulta.current !== consultaKey
    const silencioso = !cambioFiltro && !!cacheInicial && intento === 0 // volver a una lista conocida: se revalida sin tapar nada
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
  }, [consultaKey, intento])

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
  const tipos = useMemo(() => tiposEfectivos(movimientos, contextoDeCuentas(cuentas)), [movimientos, cuentas])
  const totales = useMemo(() => totalesConTipos(filtrados, tipos), [filtrados, tipos])
  const totalIngresos = totales.ingresos
  const totalGastos = totales.gastos
  const totalNeto = totales.neto
  const netoSeleccion = useMemo(
    () => totalesConTipos(movimientos.filter((m) => seleccionados.has(m.id)), tipos).neto,
    [movimientos, seleccionados, tipos]
  )
  const gruposDia = useMemo(() => {
    const mapa = new Map()
    for (const m of filtrados) {
      const k = claveDia(m.fecha) || String(m.fecha).slice(0, 10)
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
  const vistaParam = params.get('vista')
  const vistaActiva = f.comercio
    ? 'comercio'
    : !lateral
      ? 'lista'
      : vistaParam === 'lista' || vistaParam === 'tabla'
        ? vistaParam
        : leerVistaGuardada() || (hayAnchoParaTabla ? 'tabla' : 'lista')
  // Periodos rápidos (los chips): no cuentan como «filtro avanzado» ni abren el panel de fechas
  const PERIODOS = [
    { id: 'todo', texto: 'Todo', r: { desde: '', hasta: '' } },
    { id: 'este_mes', texto: 'Este mes', r: rangoPeriodo('este_mes') },
    { id: 'mes_pasado', texto: 'Mes pasado', r: rangoPeriodo('mes_pasado') },
  ]
  const periodoActivo = PERIODOS.find((p) => (f.desde || '') === (p.r.desde || '') && (f.hasta || '') === (p.r.hasta || ''))?.id || null
  const nFiltros = [f.cuenta, f.cat && f.cat !== 'Otros' ? f.cat : '', f.tipo, f.origen, periodoActivo ? '' : f.desde || f.hasta].filter(Boolean).length
  const filtrosVisibles = mostrarFiltros || lateral || nFiltros > 0

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

  // Borrar una fila desde el gesto de deslizar: el segundo toque ya confirmó; si vino del correo o de un extracto
  // se pregunta «¿Qué pasó?» igual que en el detalle. Optimista: sale de la lista y vuelve si el servidor falla.
  async function eliminarUno(m) {
    let motivo
    if (m.fuente !== 'transferencia_interna' && vinoDeCorreoOExtracto(m)) {
      motivo = await elegir('El saldo se ajusta como si nunca hubiera existido.', { titulo: '¿Qué pasó?', opciones: OPCIONES_BORRADO })
      if (!motivo) return
    }
    const previa = movimientos
    setMovimientos((prev) => prev.filter((x) => x.id !== m.id))
    try {
      await (motivo ? api.eliminarMovimiento(m.id, motivo) : api.eliminarMovimiento(m.id))
      quitarDeCaches(m.id)
      recargarCuentas?.()
      recargarConteo()
      avisar('Movimiento eliminado', 'ok')
      exito()
    } catch (err) {
      setMovimientos(previa)
      hapticoError()
      avisar(mensajeDeError(err, 'No se pudo eliminar. Revisa tu conexión e intenta de nuevo.'))
    }
  }

  async function eliminarSeleccion() {
    const ids = [...seleccionados]
    const titulo = `¿Eliminar ${ids.length} ${ids.length === 1 ? 'movimiento' : 'movimientos'}?`
    const aviso = 'El saldo se ajusta como si nunca hubieran existido. No se puede deshacer.'
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
  const enTabla = lateral && vistaActiva === 'tabla'
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
    f.tipo && { k: 'tipo', texto: { income: 'Ingresos', expense: 'Gastos', transfer: 'Plata entre tus cuentas' }[f.tipo] || f.tipo },
    f.origen && { k: 'origen', texto: ORIGENES_FILTRO.find((o) => o.id === f.origen)?.texto || f.origen },
    f.desde && { k: 'desde', texto: `Desde ${f.desde}` },
    f.hasta && { k: 'hasta', texto: `Hasta ${f.hasta}` },
  ].filter(Boolean)

  // Cuenta nueva sin movimientos: no se muestran periodos, resumen ni vistas (no hay nada que filtrar)
  const sinNada = !cargando && !errorCarga && filtrados.length === 0 && chipsActivos.length === 0 && !f.revisar && !f.cat && !f.conf && !f.comercio && !soloCorreo
  const campo = 'campo-entrada'
  const limpiarFiltros = () => {
    setTexto('')
    cambiarParams({ q: '', cuenta: '', cat: '', tipo: '', origen: '', desde: '', hasta: '', revisar: false, conf: false })
  }
  const elegirVista = (id) => {
    if (lateral && id !== 'comercio') {
      try {
        localStorage.setItem(VISTA_GUARDADA, id)
      } catch {
        /* sin almacenamiento: la preferencia dura solo esta visita */
      }
    }
    cambiarParams({ vista: id === 'lista' ? (lateral ? 'lista' : '') : id })
  }
  const selectorVista = (
    <div role="group" aria-label="Vista" className="inline-flex rounded-full border border-line p-0.5 bg-paper">
      {[
        { id: 'lista', texto: 'Lista' },
        ...(lateral ? [{ id: 'tabla', texto: 'Tabla' }] : []),
        { id: 'comercio', texto: 'Comercios' },
      ].map((v) => (
        <button
          key={v.id}
          type="button"
          aria-pressed={vistaActiva === v.id}
          onClick={() => elegirVista(v.id)}
          className={`text-xs px-2.5 min-h-11 rounded-full font-semibold ${vistaActiva === v.id ? 'bg-accent-soft text-accent' : 'text-ink-soft'}`}
        >
          {v.texto}
        </button>
      ))}
    </div>
  )
  const enlaceInforme = (
    <Link
      to="/informe"
      data-testid="ver-detalle-gastos"
      title="¿En qué gasto mi plata?"
      className="w-11 h-11 shrink-0 inline-flex items-center justify-center rounded-full text-accent hover:bg-accent-soft"
    >
      <PieChart size={20} aria-hidden="true" />
      <span className="sr-only">¿En qué gasto mi plata?</span>
    </Link>
  )

  return (
    <div ref={asignarRaiz} className="flex-1 overflow-y-auto pb-6 screen-enter pantalla-ancha">
      {jalar.indicador}
      <header className="px-5 pantalla-top pb-3 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Movimientos</h1>
        {modoSeleccion ? (
          <Boton variante="fantasma" tam="sm" onClick={salirModoSeleccion}>
            Cancelar
          </Boton>
        ) : (
          <button
            onClick={() => setMenuAcciones(true)}
            aria-haspopup="dialog"
            aria-label="Más acciones"
            title="Más acciones"
            className="ml-auto inline-flex items-center justify-center gap-2 text-sm text-ink-soft font-medium min-w-11 min-h-11 px-3 md:px-4 rounded-full border border-line hover:border-accent"
          >
            <MoreHorizontal size={20} aria-hidden="true" />
            <span className="hidden md:inline">Más acciones</span>
          </button>
        )}
      </header>

      {/* Solo si hay algo pendiente (avisos por revisar, una lectura en curso o su resultado); si no, queda el enlace discreto bajo los totales */}
      {(porCorreo.correos.length > 0 || leyendoCorreo || !!avisoCorreo) && (
        <TarjetaMovimientosCorreo
          className="mx-5 mb-3"
          conectado={conectadoCorreo}
          leyendo={leyendoCorreo}
          aviso={avisoCorreo}
          porRevisar={porCorreo.correos.length}
          onTraer={() => actualizarCorreo(true)}
        />
      )}

      {/* ≥1024 px: filtros (o el detalle del movimiento) a la izquierda, lista a la derecha */}
      <div className={`dos-col ${enTabla ? 'dos-col-riel-tabla' : 'dos-col-5-6'}`}>
        <div className="col col-sticky lg:max-h-[calc(100svh-2rem)] lg:overflow-y-auto">
          {panelId ? (
            <DetalleMovimiento key={panelId} id={panelId} embebido onCerrar={cerrarPanel} onCambio={alCambioDetalle} />
          ) : (
            <>
              {/* FILA 1 · buscar y filtrar (en escritorio los filtros siempre están a la vista) */}
              <div className="px-5 mb-3 flex items-center gap-2">
                <div className="flex-1 min-w-0 flex items-center gap-2 bg-paper-raised border border-line rounded-2xl pl-4 pr-1 min-h-12 focus-within:border-accent">
                  <Search size={20} className="text-ink-soft shrink-0" aria-hidden="true" />
                  <input
                    value={texto}
                    aria-label="Buscar movimiento"
                    data-atajo-buscar
                    onChange={(e) => setTexto(e.target.value)}
                    placeholder="Buscar movimiento"
                    className="bg-transparent outline-none text-sm flex-1 min-w-0 placeholder:text-ink-soft"
                  />
                  {texto && (
                    <button type="button" onClick={() => setTexto('')} aria-label="Borrar búsqueda" className="w-10 h-10 shrink-0 rounded-full inline-flex items-center justify-center text-ink-soft hover:text-ink">
                      <X size={16} aria-hidden="true" />
                    </button>
                  )}
                </div>
                {!lateral && (
                  <button
                    type="button"
                    onClick={() => setMostrarFiltros((v) => !v)}
                    aria-expanded={filtrosVisibles}
                    aria-controls="panel-filtros"
                    className={`relative shrink-0 inline-flex items-center justify-center gap-2 min-w-12 min-h-12 px-3 rounded-2xl border text-sm font-semibold ${
                      filtrosVisibles || nFiltros > 0 ? 'border-accent bg-accent-soft text-accent' : 'border-line bg-paper-raised text-ink-soft'
                    }`}
                  >
                    <SlidersHorizontal size={20} aria-hidden="true" />
                    <span className="sr-only md:not-sr-only">Filtros</span>
                    {nFiltros > 0 && (
                      <span aria-label={`${nFiltros} filtros activos`} className="min-w-5 h-5 px-1 rounded-full bg-accent text-paper-raised text-xs font-bold inline-flex items-center justify-center">
                        {nFiltros}
                      </span>
                    )}
                  </button>
                )}
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
                        <span className="block text-xs text-ink-soft">Apruébalos para que pasen a tu lista.</span>
                      </span>
                      <ChevronRight size={16} className="text-ink-soft shrink-0" aria-hidden="true" />
                    </button>
                  )}
                  {descartados > 0 && (
                    <button
                      onClick={() => navigate('/movimientos-correo', { state: { abrir: 'correos-descartados' } })}
                      className="w-full min-h-[56px] flex items-center gap-3 rounded-2xl bg-paper-raised border border-line px-4 py-2.5 text-left"
                    >
                      <span className="flex-1 min-w-0">
                        <span className="block text-sm font-semibold">Correos descartados ({descartados >= 100 ? '99+' : descartados})</span>
                        <span className="block text-xs text-ink-soft">Recupéralos si sí eran tuyos.</span>
                      </span>
                      <ChevronRight size={16} className="text-ink-soft shrink-0" aria-hidden="true" />
                    </button>
                  )}
                </div>
              )}

              {/* FILA 2 · periodo y pendientes en UNA sola fila de chips (antes eran dos grupos con estilos distintos) */}
              {!sinNada && (
              <div className="pl-5 pr-9 lg:px-5 mb-3 flex items-center gap-2 overflow-x-auto no-scrollbar borde-fade-der lg:flex-wrap lg:overflow-visible lg:[mask-image:none] lg:[-webkit-mask-image:none]">
                <div role="group" aria-label="Periodo" data-testid="chips-periodo" className="flex gap-2 shrink-0 lg:flex-wrap lg:shrink">
                  {PERIODOS.map((p) => (
                    <Chip key={p.id} activo={periodoActivo === p.id} onClick={() => cambiarParams({ desde: p.r.desde, hasta: p.r.hasta })}>
                      {p.texto}
                    </Chip>
                  ))}
                </div>
                {(porCorreo.correos.length > 0 || soloCorreo || conteo.total > 0 || f.revisar || conteo.otros > 0 || f.cat === 'Otros' || f.conf) && (
                  <span aria-hidden="true" className="w-px h-6 bg-line shrink-0 lg:hidden" />
                )}
                {(porCorreo.correos.length > 0 || soloCorreo) && (
                  <Chip className="shrink-0" activo={soloCorreo} onClick={() => cambiarParams({ filtro: soloCorreo ? '' : 'por-revisar' })}>
                    Del correo por revisar{porCorreo.correos.length > 0 ? ` (${porCorreo.correos.length})` : ''}
                  </Chip>
                )}
                {/* Sin repetir la misma lista con dos nombres: «Por revisar» no sale si es idéntica a «Sin categorizar»,
                    y «Por confirmar» solo sale cuando hay además otra clase de pendientes. */}
                {(((conteo.total > 0) && !(conteo.otros > 0 && conteo.auto === 0)) || f.revisar) && (
                  <Chip className="shrink-0" activo={f.revisar} onClick={() => cambiarParams({ revisar: !f.revisar })}>
                    Por revisar{conteo.total > 0 ? ` (${conteo.total})` : ''}
                  </Chip>
                )}
                {(conteo.otros > 0 || f.cat === 'Otros') && (
                  <Chip className="shrink-0" activo={f.cat === 'Otros'} onClick={() => cambiarParams({ cat: f.cat === 'Otros' ? '' : 'Otros' })}>
                    Sin categorizar{conteo.otros > 0 ? ` (${conteo.otros})` : ''}
                  </Chip>
                )}
                {((conteo.auto > 0 && conteo.otros > 0) || f.conf) && (
                  <Chip className="shrink-0" activo={f.conf} onClick={() => cambiarParams({ conf: !f.conf })}>
                    Por confirmar{conteo.auto > 0 ? ` (${conteo.auto})` : ''}
                  </Chip>
                )}
                {conteo.total > 0 && !f.revisar && (
                  <Link to="/categorizar" className="shrink-0 min-h-11 inline-flex items-center px-1 text-xs font-semibold text-accent underline underline-offset-2">
                    Poner categoría a lo que más pesa
                  </Link>
                )}
              </div>
              )}
              {f.revisar && conteo.auto > 0 && (
                <div className="px-5 mb-3">
                  <Boton variante="suave" tam="sm" onClick={confirmarTodas}>
                    Confirmar las {conteo.auto} automáticas
                  </Boton>
                </div>
              )}

              {filtrosVisibles && (
                <div id="panel-filtros" className="px-5 mb-3 grid grid-cols-2 gap-x-2 gap-y-3 [.dos-col-riel-tabla_&]:grid-cols-1">
                  <label className="block">
                    <span className="campo-etiqueta">Desde</span>
                    <input type="date" aria-label="Desde" value={f.desde} onChange={(e) => cambiarParams({ desde: e.target.value })} className={campo} />
                  </label>
                  <label className="block">
                    <span className="campo-etiqueta">Hasta</span>
                    <input type="date" aria-label="Hasta" value={f.hasta} onChange={(e) => cambiarParams({ hasta: e.target.value })} className={campo} />
                  </label>
                  {cuentas.length > 1 && (
                    <label className="block">
                      <span className="campo-etiqueta">Cuenta</span>
                      <select aria-label="Filtrar por cuenta" value={f.cuenta} onChange={(e) => cambiarParams({ cuenta: e.target.value })} className={campo}>
                        <option value="">Todas</option>
                        {cuentas.map((c) => (
                          <option key={c.id} value={c.id}>{c.nombre}</option>
                        ))}
                      </select>
                    </label>
                  )}
                  <label className="block">
                    <span className="campo-etiqueta">Categoría</span>
                    <select aria-label="Filtrar por categoría" value={f.cat} onChange={(e) => cambiarParams({ cat: e.target.value })} className={campo}>
                      <option value="">Todas</option>
                      {[...new Set([...CATEGORIAS, ...(f.cat ? [f.cat] : [])])].map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className="campo-etiqueta">Tipo</span>
                    <select aria-label="Filtrar por tipo" value={f.tipo} onChange={(e) => cambiarParams({ tipo: e.target.value })} className={campo}>
                      <option value="">Todos</option>
                      <option value="expense">Gastos</option>
                      <option value="income">Ingresos</option>
                      <option value="transfer">Entre tus cuentas</option>
                    </select>
                  </label>
                  <label className="block">
                    <span className="campo-etiqueta">Origen</span>
                    <select aria-label="Filtrar por origen" value={f.origen} onChange={(e) => cambiarParams({ origen: e.target.value })} className={campo}>
                      <option value="">Todos</option>
                      {ORIGENES_FILTRO.map((o) => (
                        <option key={o.id} value={o.id}>{o.texto}</option>
                      ))}
                    </select>
                  </label>
                  <Boton variante="fantasma" tam="sm" onClick={() => exportar('csv')} aria-label="Exportar CSV" className="col-span-full justify-start">
                    <Download size={16} aria-hidden="true" /> Descargar en CSV
                  </Boton>
                </div>
              )}

              {activos && (
                <div className="px-5 mb-3 flex items-center flex-wrap gap-2" aria-label="Filtros activos">
                  {chipsActivos.map((c) => (
                    <button
                      key={c.k}
                      onClick={() => cambiarParams({ [c.k]: '' })}
                      aria-label={`Quitar filtro ${c.texto}`}
                      className="inline-flex items-center gap-1 text-xs font-semibold px-3 min-h-[32px] rounded-full bg-accent-soft text-accent border border-accent/40"
                    >
                      {c.texto} <X size={16} aria-hidden="true" />
                    </button>
                  ))}
                  <button onClick={limpiarFiltros} className="text-xs font-semibold text-accent underline px-1 min-h-[32px]">
                    Limpiar
                  </button>
                </div>
              )}

              {/* RESUMEN de lo que se ve: una sola tarjeta (cifras, conteo y vista). En la tabla el resumen va sobre la tabla. */}
              {filtrados.length > 0 && !enTabla ? (
                <section data-testid="resumen-lista" aria-label="Resumen de lo que ves" className="mx-5 mb-3 rounded-2xl border border-line bg-paper-raised">
                  <dl className="grid grid-cols-3 divide-x divide-line max-[359px]:grid-cols-1 max-[359px]:divide-x-0 max-[359px]:divide-y">
                    <div className="px-2.5 py-2.5 min-w-0 max-[359px]:flex max-[359px]:items-baseline max-[359px]:justify-between">
                      <dt className="t-kicker text-ink-soft">Ingresos</dt>
                      <dd className="text-[13px] min-[400px]:text-sm font-bold text-gold mt-0.5 tabular-nums whitespace-nowrap">{formatCOP(totalIngresos)}</dd>
                    </div>
                    <div className="px-2.5 py-2.5 min-w-0 max-[359px]:flex max-[359px]:items-baseline max-[359px]:justify-between">
                      <dt className="t-kicker text-ink-soft">Gastos</dt>
                      <dd className="text-[13px] min-[400px]:text-sm font-bold text-ink mt-0.5 tabular-nums whitespace-nowrap">{formatCOP(totalGastos)}</dd>
                    </div>
                    <div className="px-2.5 py-2.5 min-w-0 max-[359px]:flex max-[359px]:items-baseline max-[359px]:justify-between">
                      <dt className="t-kicker text-ink-soft">Neto</dt>
                      <dd className={`text-[13px] min-[400px]:text-sm font-bold mt-0.5 tabular-nums whitespace-nowrap ${totalNeto >= 0 ? 'text-gold' : 'text-ink'}`}>
                        {totalNeto < 0 ? '-' : ''}{formatCOP(Math.abs(totalNeto))}
                      </dd>
                    </div>
                  </dl>
                  <div className="flex items-center justify-between gap-2 border-t border-line pl-3 pr-1 py-0.5">
                    <p className="text-xs text-ink-soft whitespace-nowrap pl-0.5" data-testid="resumen-conteo">
                      {filtrados.length}
                      {hayMas ? '+' : ''} movimiento{filtrados.length === 1 && !hayMas ? '' : 's'}
                    </p>
                    <div className="flex items-center shrink-0">
                      {selectorVista}
                      {enlaceInforme}
                    </div>
                  </div>
                </section>
              ) : (
                !sinNada && (
                  <div className="px-5 mb-3 flex items-center justify-between gap-2">
                    {selectorVista}
                    {enlaceInforme}
                  </div>
                )
              )}
              {f.comercio && (
                <div className="px-5 mb-3 flex justify-end">
                  <select aria-label="Ordenar comercios" value={f.orden} onChange={(e) => cambiarParams({ orden: e.target.value === 'monto' ? 'monto' : '' })} className={`${campo} !w-auto`}>
                    <option value="cantidad">Más movimientos</option>
                    <option value="monto">Mayor monto</option>
                  </select>
                </div>
              )}
            </>
          )}
        </div>

        <div className="col">
          <PorRevisarCorreo correos={porCorreo.correos} onResuelto={correoResuelto} onCuentaCreada={porCorreo.recargar} onRecargar={porCorreo.recargar} className="mx-5 mb-4" />
          {soloCorreo ? (
            porCorreo.cargado && porCorreo.correos.length === 0 && (
              <EstadoVacio icono={ListChecks} titulo="Nada por revisar del correo" texto="Los avisos de tu banco aparecerán aquí." className="mx-5" />
            )
          ) : cargando ? (
            <EsqueletoLista filas={8} className="mx-5" etiqueta="Cargando movimientos" />
          ) : errorCarga ? (
            <div role="alert" className="mx-5 rounded-3xl bg-danger-soft border border-danger/30 p-6 text-center">
              <p className="text-sm text-danger">{errorCarga}</p>
              <Boton variante="secundario" tam="sm" className="mt-3" onClick={() => setIntento((n) => n + 1)}>
                Reintentar
              </Boton>
            </div>
          ) : filtrados.length === 0 && chipsActivos.length === 0 && !f.revisar && !f.cat && !f.conf && !f.comercio ? (
            // Sin ningún filtro y sin filas: la persona aún no tiene movimientos (no es "búsqueda sin resultados")
            <EstadoVacio
              icono={ListChecks}
              titulo="Aún no tienes movimientos"
              texto="Anota el primero o trae los de tu banco."
              className="mx-5"
            >
              <div className="mt-4 flex flex-col gap-2">
                <Boton to="/agregar" bloque>Anotar un movimiento</Boton>
                <Boton to="/movimientos-correo" variante="secundario" bloque>Traer del correo</Boton>
                <Boton to="/sincronizacion" variante="secundario" bloque>Subir un extracto</Boton>
              </div>
            </EstadoVacio>
          ) : filtrados.length === 0 ? (
            <EstadoVacio
              icono={Search}
              titulo={f.revisar && chipsActivos.length === 0 && !f.cat && !f.conf ? 'Todo está revisado' : 'No hay movimientos que coincidan'}
              texto={
                f.revisar && chipsActivos.length === 0 && !f.cat && !f.conf
                  ?'No queda nada por confirmar.'
                  : 'Prueba con otro filtro o búsqueda.'
              }
              className="mx-5"
            >
              <Boton variante="secundario" tam="sm" className="mt-4" onClick={limpiarFiltros}>
                {f.revisar && chipsActivos.length === 0 && !f.cat && !f.conf ? 'Ver todos los movimientos' : 'Quitar los filtros'}
              </Boton>
            </EstadoVacio>
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
              totales={totales}
              netoSeleccion={netoSeleccion}
            />
          ) : (
            <div className="mx-5 relative">
              <div ref={listaRef} style={{ paddingTop: ventana.arriba, paddingBottom: ventana.abajo }}>
              {gruposDia.slice(ventana.ini, ventana.fin).map((grupo, k) => {
                const gi = ventana.ini + k
                return (
                <div key={grupo.diaKey} data-dia={grupo.diaKey} className={gi === 0 ? '' : 'pt-5'}>
                  {/* El día se queda fijo arriba mientras se recorre su grupo: siempre sabes de qué fecha estás leyendo */}
                  <div className="sticky top-0 z-[1] -mx-1 px-2 py-1.5 mb-0.5 flex items-baseline justify-between gap-3 bg-paper/95 backdrop-blur-sm rounded-lg">
                    <h2 className="text-xs font-bold text-ink-soft uppercase tracking-wide">{grupo.label}</h2>
                    <SubtotalDia items={grupo.items} tipos={tipos} />
                  </div>
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
                      onBorrar={eliminarUno}
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

      {menuAcciones && (
        <Hoja onCerrar={() => setMenuAcciones(false)} titulo="Más acciones">
          {({ cerrar }) => {
            const fila = 'w-full min-h-[52px] flex items-center gap-3 px-2 text-left text-sm font-medium border-b border-line last:border-0 disabled:opacity-50'
            const accion = (fn) => () => { cerrar(); fn() }
            return (
              <>
                <h2 className="text-lg font-semibold mb-2">Más acciones</h2>
                <div className="flex flex-col">
                  <button className={fila} onClick={accion(() => setTimeout(() => document.querySelector('[data-atajo-buscar]')?.focus(), 0))}>
                    <Search size={20} aria-hidden="true" /> Buscar
                  </button>
                  <button className={fila} onClick={accion(() => setMostrarFiltros((v) => !v))}>
                    <SlidersHorizontal size={20} aria-hidden="true" /> Filtrar por fecha, cuenta o categoría
                  </button>
                  <button className={fila} disabled={exportando} onClick={accion(() => exportar('xlsx'))}>
                    <Download size={20} aria-hidden="true" /> Descargar en Excel
                  </button>
                  <Link
                    to="/sincronizacion"
                    state={{ abrir: 'subir', manual: true }}
                    className={fila}
                    onClick={() => cerrar()}
                  >
                    <Upload size={20} aria-hidden="true" /> Subir archivo de Excel o CSV
                  </Link>
                  <button className={fila} onClick={accion(() => setModoSeleccion(true))}>
                    <ListChecks size={20} aria-hidden="true" /> Seleccionar varios
                  </button>
                  <Link to="/revisar" className={fila} onClick={() => cerrar()}>
                    <ArrowLeftRight size={20} aria-hidden="true" /> Revisar traslados y repetidos
                  </Link>
                  <Link to="/movimientos-correo" data-testid="ver-correo-discreto" className={fila} onClick={() => cerrar()}>
                    <Mail size={20} aria-hidden="true" /> Movimientos del correo
                  </Link>
                  <button className={fila} disabled={leyendoCorreo} onClick={accion(() => actualizarCorreo(true))}>
                    <RefreshCw size={20} aria-hidden="true" /> Actualizar desde el correo
                  </button>
                </div>
              </>
            )
          }}
        </Hoja>
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
                {seleccionados.size} seleccionados.
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
          <div className="flex items-start justify-between gap-2">
            <span className="text-sm text-paper font-semibold px-1 pt-1" aria-live="polite">
              {seleccionados.size} seleccionado{seleccionados.size === 1 ? '' : 's'}
              {seleccionados.size > 0 && (
                <span className="block text-xs font-normal opacity-80 tabular-nums" data-testid="suma-seleccion">
                  {netoSeleccion < 0 ? '-' : ''}{formatCOP(Math.abs(netoSeleccion))} en total
                </span>
              )}
            </span>
            <button onClick={salirModoSeleccion} className="w-11 h-11 shrink-0 -mt-1 -mr-1 rounded-xl flex items-center justify-center text-paper hover:bg-paper/10" aria-label="Cerrar">
              <X size={20} aria-hidden="true" />
            </button>
          </div>
          <div className={`grid gap-2 mt-2 ${cuentas.length > 1 ? 'grid-cols-3' : 'grid-cols-2'}`}>
            <button
              disabled={seleccionados.size === 0 || aplicando}
              onClick={abrirChipMasivo}
              className="rounded-xl bg-paper text-ink px-3 min-h-11 text-sm font-semibold disabled:opacity-40"
            >
              Categoría
            </button>
            {cuentas.length > 1 && (
              <button
                disabled={seleccionados.size === 0 || aplicando}
                onClick={() => setMoverACuenta(true)}
                className="rounded-xl bg-paper text-ink px-3 min-h-11 text-sm font-semibold disabled:opacity-40"
              >
                Cuenta
              </button>
            )}
            <button
              disabled={seleccionados.size === 0 || aplicando}
              onClick={eliminarSeleccion}
              className="rounded-xl bg-danger text-paper-raised px-3 min-h-11 text-sm font-semibold disabled:opacity-40 flex items-center justify-center gap-1.5"
            >
              <Trash2 size={16} aria-hidden="true" /> Eliminar
            </button>
          </div>
          <div className="flex flex-wrap gap-x-4 mt-1 px-1">
            <button onClick={seleccionarTodoFiltrado} className="text-xs text-paper underline min-h-11">
              Seleccionar todo lo filtrado ({filtrados.length})
            </button>
            <button onClick={seleccionarSimilares} disabled={seleccionados.size === 0} className="text-xs text-paper underline min-h-11 disabled:opacity-40">
              Seleccionar los similares
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
