import { useCallback, useDeferredValue, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { Link } from 'react-router-dom'
import { Check, Download, Search, SlidersHorizontal, X } from 'lucide-react'
import { formatCOP, formatMoneda } from '../lib/format'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import { useDialogos } from '../lib/DialogosContext'

const TAMANO_PAGINA = 200

// ── Virtualización ────────────────────────────────────────────────────────
// Con 1.500+ filas, pintar todo el DOM hace lento el celular. Solo se dibujan las
// filas que se ven (más un margen). Para que sea simple y rápido, cada tipo de fila
// tiene ALTO FIJO: así la posición de cada una se calcula sumando, sin medir el DOM.
const ALTO = {
  movil: { dia: 40, mov: 60 },
  ancho: { dia: 36, mov: 44 },
}
const MARGEN_PX = 600 // filas extra arriba/abajo para que el scroll rápido no muestre vacío
const CLAVE_VOLVER = 'cuadrame.movimientos.volver'

// ¿La pantalla es de escritorio/iPad horizontal? Se reacciona al cambiar de tamaño.
function useEsAncho() {
  const consulta = '(min-width: 1024px)'
  return useSyncExternalStore(
    (cb) => {
      const mq = window.matchMedia(consulta)
      mq.addEventListener?.('change', cb)
      return () => mq.removeEventListener?.('change', cb)
    },
    () => window.matchMedia(consulta).matches,
    () => false
  )
}

// Búsqueda binaria: índice de la fila que contiene la posición `y`.
function indiceEn(offsets, y) {
  let lo = 0
  let hi = offsets.length - 2
  while (lo < hi) {
    const medio = (lo + hi + 1) >> 1
    if (offsets[medio] <= y) lo = medio
    else hi = medio - 1
  }
  return lo
}

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

// Lo que se guarda al abrir un movimiento, para que "Volver" deje todo como estaba.
function leerVolver() {
  try {
    return JSON.parse(sessionStorage.getItem(CLAVE_VOLVER) || 'null')
  } catch {
    return null
  }
}

function SkeletonLista({ ancho }) {
  const alto = ancho ? ALTO.ancho.mov : ALTO.movil.mov
  return (
    <div className="mx-5 space-y-1" aria-busy="true" aria-label="Cargando movimientos" role="status">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="flex items-center gap-3" style={{ height: alto }}>
          <div className="flex-1 space-y-2">
            <div className="skeleton h-3.5 w-2/3" />
            <div className="skeleton h-3 w-1/3" />
          </div>
          <div className="skeleton h-4 w-20" />
        </div>
      ))}
    </div>
  )
}

export default function Movimientos() {
  const { cuentas } = useCuentas()
  const { nombres: CATEGORIAS, iconoDe } = useCategorias()
  const { avisar } = useDialogos()
  const esAncho = useEsAncho()
  const alturas = esAncho ? ALTO.ancho : ALTO.movil
  const monedaDe = useMemo(() => Object.fromEntries(cuentas.map((c) => [c.id, c.moneda])), [cuentas])
  const nombreCuenta = useMemo(() => Object.fromEntries(cuentas.map((c) => [c.id, c.nombre])), [cuentas])

  // Si se viene de abrir un movimiento, se recupera lo que la persona tenía puesto.
  const [volver] = useState(leerVolver)
  const f0 = volver?.filtros || {}

  const [movimientos, setMovimientos] = useState([])
  const [busqueda, setBusqueda] = useState(f0.busqueda || '')
  const [filtro, setFiltro] = useState(f0.filtro || 'Todos')
  const [cuentaId, setCuentaId] = useState(f0.cuentaId || '')
  const [desde, setDesde] = useState(f0.desde || '')
  const [hasta, setHasta] = useState(f0.hasta || '')
  const [mostrarFiltrosFecha, setMostrarFiltrosFecha] = useState(!!(f0.desde || f0.hasta || f0.cuentaId))
  const [cargando, setCargando] = useState(true)
  const [exportando, setExportando] = useState(false)
  const [modoSeleccion, setModoSeleccion] = useState(false)
  const [seleccionados, setSeleccionados] = useState(new Set())
  const [aplicandoCategoria, setAplicandoCategoria] = useState(false)
  const [hayMas, setHayMas] = useState(false)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [errorCarga, setErrorCarga] = useState('')

  const scrollRef = useRef(null)
  const listaRef = useRef(null)

  useEffect(() => {
    let activo = true
    // Al volver se piden de nuevo tantas páginas como las que había cargadas.
    const paginas = Math.min(8, Math.max(1, Math.ceil((volver?.cargados || 0) / TAMANO_PAGINA)))
    ;(async () => {
      try {
        let todos = []
        let ultima = []
        for (let p = 0; p < paginas; p++) {
          ultima = await api.movimientos(TAMANO_PAGINA, todos.length)
          todos = [...todos, ...ultima]
          if (ultima.length < TAMANO_PAGINA) break
        }
        if (!activo) return
        setMovimientos(todos)
        setHayMas(ultima.length === TAMANO_PAGINA)
      } catch (err) {
        if (activo) setErrorCarga(err.message || 'No se pudieron cargar los movimientos')
      } finally {
        if (activo) setCargando(false)
      }
    })()
    sessionStorage.removeItem(CLAVE_VOLVER)
    return () => {
      activo = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function cargarMas() {
    setCargandoMas(true)
    try {
      const siguientes = await api.movimientos(TAMANO_PAGINA, movimientos.length)
      setMovimientos((prev) => [...prev, ...siguientes])
      setHayMas(siguientes.length === TAMANO_PAGINA)
    } catch {
      avisar('No se pudieron cargar más movimientos')
    } finally {
      setCargandoMas(false)
    }
  }

  // useDeferredValue: al teclear, la lista se actualiza sin trabar el campo de texto.
  const busquedaDiferida = useDeferredValue(busqueda)

  const categorias = useMemo(() => ['Todos', ...new Set(movimientos.map((m) => m.categoria))], [movimientos])

  const filtrados = useMemo(() => {
    const q = busquedaDiferida.toLowerCase()
    return movimientos.filter((m) => {
      if (q && !m.descripcion.toLowerCase().includes(q)) return false
      if (filtro !== 'Todos' && m.categoria !== filtro) return false
      if (cuentaId && m.cuenta_id !== cuentaId) return false
      if (desde && m.fecha.slice(0, 10) < desde) return false
      if (hasta && m.fecha.slice(0, 10) > hasta) return false
      return true
    })
  }, [movimientos, busquedaDiferida, filtro, cuentaId, desde, hasta])

  const { totalIngresos, totalGastos } = useMemo(() => {
    let i = 0
    let g = 0
    for (const m of filtrados) {
      if (m.tipo === 'income') i += m.monto
      else if (m.tipo === 'expense') g += m.monto
    }
    return { totalIngresos: i, totalGastos: g }
  }, [filtrados])

  const hayFiltrosActivos = !!(cuentaId || desde || hasta || filtro !== 'Todos' || busqueda)

  // Lista plana: encabezados de día y movimientos en una sola secuencia (llegan ordenados por fecha).
  const filas = useMemo(() => {
    const out = []
    let diaActual = null
    for (const m of filtrados) {
      const diaKey = m.fecha.slice(0, 10)
      if (diaKey !== diaActual) {
        diaActual = diaKey
        out.push({ tipo: 'dia', key: `d-${diaKey}`, label: etiquetaDia(m.fecha) })
      }
      out.push({ tipo: 'mov', key: m.id, m })
    }
    return out
  }, [filtrados])

  // offsets[i] = y donde empieza la fila i; el último valor es el alto total.
  const offsets = useMemo(() => {
    const o = new Array(filas.length + 1)
    let y = 0
    for (let i = 0; i < filas.length; i++) {
      o[i] = y
      y += alturas[filas[i].tipo]
    }
    o[filas.length] = y
    return o
  }, [filas, alturas])
  const altoTotal = offsets[filas.length]

  const [rango, setRango] = useState({ ini: 0, fin: 30 })
  const recalcular = useCallback(() => {
    const sc = scrollRef.current
    const lista = listaRef.current
    if (!sc || !lista || filas.length === 0) return
    const vista = sc.clientHeight || 800 // jsdom no mide: se asume una pantalla típica
    const arriba = sc.getBoundingClientRect().top - lista.getBoundingClientRect().top // px de la lista ya pasados
    const ini = indiceEn(offsets, arriba - MARGEN_PX)
    const fin = Math.min(filas.length, indiceEn(offsets, arriba + vista + MARGEN_PX) + 1)
    setRango((prev) => (prev.ini === ini && prev.fin === fin ? prev : { ini, fin }))
  }, [offsets, filas.length])

  useLayoutEffect(() => {
    recalcular()
  }, [recalcular, cargando])

  useEffect(() => {
    const sc = scrollRef.current
    if (!sc) return
    let pendiente = 0
    const programar = () => {
      if (pendiente) return
      pendiente = requestAnimationFrame(() => {
        pendiente = 0
        recalcular()
      })
    }
    sc.addEventListener('scroll', programar, { passive: true })
    window.addEventListener('resize', programar)
    return () => {
      sc.removeEventListener('scroll', programar)
      window.removeEventListener('resize', programar)
      if (pendiente) cancelAnimationFrame(pendiente)
    }
  }, [recalcular])

  // Restaurar la posición de scroll al volver desde el detalle.
  const scrollRestaurado = useRef(false)
  useEffect(() => {
    if (cargando || scrollRestaurado.current || !volver?.scroll) return
    scrollRestaurado.current = true
    requestAnimationFrame(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = volver.scroll
    })
  }, [cargando, volver])

  function recordarParaVolver() {
    try {
      sessionStorage.setItem(
        CLAVE_VOLVER,
        JSON.stringify({
          filtros: { busqueda, filtro, cuentaId, desde, hasta },
          scroll: scrollRef.current?.scrollTop || 0,
          cargados: movimientos.length,
        })
      )
    } catch {
      /* sin sessionStorage simplemente no se restaura */
    }
  }

  async function exportar(formato) {
    setExportando(true)
    try {
      await (formato === 'xlsx' ? api.exportarExcel() : api.exportarCSV())
    } catch {
      avisar('No se pudo exportar')
    } finally {
      setExportando(false)
    }
  }

  function toggleSeleccion(id) {
    setSeleccionados((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function salirModoSeleccion() {
    setModoSeleccion(false)
    setSeleccionados(new Set())
  }

  async function aplicarCategoriaMasiva(categoria) {
    if (seleccionados.size === 0) return
    setAplicandoCategoria(true)
    try {
      await api.recategorizarMasivo([...seleccionados], categoria)
      setMovimientos((prev) => prev.map((m) => (seleccionados.has(m.id) ? { ...m, categoria } : m)))
      salirModoSeleccion()
    } catch {
      avisar('No se pudo actualizar la categoría')
    } finally {
      setAplicandoCategoria(false)
    }
  }

  const todosSeleccionados = filtrados.length > 0 && seleccionados.size === filtrados.length

  function signo(m) {
    return m.tipo === 'income' ? '+' : m.tipo === 'expense' ? '-' : ''
  }
  function colorMonto(m) {
    return m.tipo === 'income' ? 'text-accent-2' : m.tipo === 'transfer' ? 'text-ink-soft' : 'text-ink'
  }
  function casilla(m) {
    const marcado = seleccionados.has(m.id)
    return (
      <span
        aria-hidden="true"
        className={`w-5 h-5 rounded-md border-2 shrink-0 flex items-center justify-center ${marcado ? 'bg-accent border-accent' : 'border-line'}`}
      >
        {marcado && <Check size={16} className="text-white" />}
      </span>
    )
  }

  // Envoltorio común: en modo selección es un botón; si no, un enlace al detalle.
  function envolver(m, className, style, hijos, extra = {}) {
    return modoSeleccion ? (
      <button
        key={m.id}
        onClick={() => toggleSeleccion(m.id)}
        className={`${className} text-left`}
        style={style}
        aria-pressed={seleccionados.has(m.id)}
        {...extra}
      >
        {hijos}
      </button>
    ) : (
      <Link key={m.id} to={`/movimientos/${m.id}`} onClick={recordarParaVolver} className={className} style={style} {...extra}>
        {hijos}
      </Link>
    )
  }

  function filaMovil(fila, top) {
    const m = fila.m
    const estilo = { top, height: alturas.mov, left: 20, right: 0 }
    return envolver(
      m,
      'absolute flex items-center',
      estilo,
      <>
        <span
          className={`absolute -left-5 top-1/2 -mt-[5px] w-2.5 h-2.5 rounded-full border-2 border-paper ${m.tipo === 'income' ? 'bg-accent-2' : 'bg-ink'}`}
        />
        <div className="flex items-center justify-between gap-3 w-full">
          {modoSeleccion && casilla(m)}
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold truncate">{m.descripcion}</p>
            <p className="text-xs text-ink-soft mt-0.5 truncate">
              <span aria-hidden="true">{m.tipo === 'transfer' ? '🔁' : iconoDe(m.categoria)}</span> {m.categoria}
            </p>
          </div>
          <span className={`text-[15px] font-bold shrink-0 ${colorMonto(m)}`}>
            {signo(m)}
            {formatMoneda(m.monto, monedaDe[m.cuenta_id])}
          </span>
        </div>
      </>
    )
  }

  // Tabla de escritorio: mismas filas virtualizadas, pero en columnas.
  const COLUMNAS = 'grid grid-cols-[110px_minmax(0,1fr)_190px_170px_150px] items-center gap-4 px-4'
  function filaTabla(fila, top, indice) {
    const m = fila.m
    return envolver(
      m,
      `absolute inset-x-0 ${COLUMNAS} border-b border-line hover:bg-paper-raised`,
      { top, height: alturas.mov },
      <>
        <span role="cell" className="text-xs text-ink-soft">
          {modoSeleccion ? (
            <span className="flex items-center gap-2">{casilla(m)}{m.fecha.slice(0, 10)}</span>
          ) : (
            m.fecha.slice(0, 10)
          )}
        </span>
        <span role="cell" className="text-sm font-semibold truncate">{m.descripcion}</span>
        <span role="cell" className="text-sm text-ink-soft truncate">
          <span aria-hidden="true">{m.tipo === 'transfer' ? '🔁' : iconoDe(m.categoria)}</span> {m.categoria}
        </span>
        <span role="cell" className="text-sm text-ink-soft truncate">{nombreCuenta[m.cuenta_id] || ''}</span>
        <span role="cell" className={`text-sm font-bold text-right ${colorMonto(m)}`}>
          {signo(m)}
          {formatMoneda(m.monto, monedaDe[m.cuenta_id])}
        </span>
      </>,
      { role: 'row', 'aria-rowindex': indice + 2 }
    )
  }

  const visibles = filas.slice(rango.ini, rango.fin)

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto pb-6 screen-enter pantalla-ancha">
      <header className="px-5 pt-14 pb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Movimientos</h1>
        {modoSeleccion ? (
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSeleccionados(todosSeleccionados ? new Set() : new Set(filtrados.map((m) => m.id)))}
              className="text-sm text-ink-soft font-medium"
            >
              {todosSeleccionados ? 'Quitar todos' : `Seleccionar los ${filtrados.length}`}
            </button>
            <button onClick={salirModoSeleccion} className="text-sm text-accent font-medium">
              Cancelar
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setModoSeleccion(true)}
              className="text-xs text-ink-soft font-medium px-3 py-1.5 rounded-full border border-line"
            >
              Seleccionar
            </button>
            <button
              onClick={() => setMostrarFiltrosFecha((v) => !v)}
              aria-label="Filtros de fecha y cuenta"
              aria-expanded={mostrarFiltrosFecha}
              className={`w-9 h-9 rounded-full border flex items-center justify-center ${
                mostrarFiltrosFecha || desde || hasta ? 'bg-accent-soft border-accent text-accent' : 'border-line text-ink-soft'
              }`}
            >
              <SlidersHorizontal size={16} />
            </button>
            <button
              onClick={() => exportar('csv')}
              disabled={exportando}
              className="w-9 h-9 rounded-full border border-line text-ink-soft flex items-center justify-center disabled:opacity-50"
              aria-label="Exportar CSV"
            >
              <Download size={16} />
            </button>
          </div>
        )}
      </header>

      {mostrarFiltrosFecha && (
        <div className="px-5 mb-4">
          <div className="flex gap-2">
            <input
              type="date"
              aria-label="Desde"
              value={desde}
              onChange={(e) => setDesde(e.target.value)}
              className="flex-1 rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-xs"
            />
            <input
              type="date"
              aria-label="Hasta"
              value={hasta}
              onChange={(e) => setHasta(e.target.value)}
              className="flex-1 rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-xs"
            />
            <button onClick={() => exportar('xlsx')} className="text-xs text-accent font-medium shrink-0 px-2" aria-label="Exportar a Excel">
              .xlsx
            </button>
          </div>
          {cuentas.length > 1 && (
            <select
              aria-label="Filtrar por cuenta"
              value={cuentaId}
              onChange={(e) => setCuentaId(e.target.value)}
              className="w-full mt-2 rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-xs"
            >
              <option value="">Todas las cuentas</option>
              {cuentas.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </select>
          )}
        </div>
      )}

      {hayFiltrosActivos && filtrados.length > 0 && (
        <div className="px-5 mb-4 flex gap-3">
          <div className="flex-1 rounded-2xl bg-paper-raised border border-line p-3">
            <p className="text-[11px] text-ink-soft uppercase tracking-wide">Ingresos</p>
            <p className="text-sm font-bold text-accent-2 mt-0.5">{formatCOP(totalIngresos)}</p>
          </div>
          <div className="flex-1 rounded-2xl bg-paper-raised border border-line p-3">
            <p className="text-[11px] text-ink-soft uppercase tracking-wide">Gastos</p>
            <p className="text-sm font-bold text-ink mt-0.5">{formatCOP(totalGastos)}</p>
          </div>
        </div>
      )}

      <div className="px-5 mb-4">
        <div className="flex items-center gap-2 bg-paper-raised border border-line rounded-2xl px-4 py-3">
          <Search size={20} className="text-ink-soft" />
          <input
            value={busqueda}
            aria-label="Buscar movimiento"
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar movimiento"
            className="bg-transparent outline-none text-sm flex-1 placeholder:text-ink-soft"
          />
        </div>
      </div>

      {categorias.length > 1 && (
        <div className="px-5 flex gap-2 mb-4 overflow-x-auto no-scrollbar lg:flex-wrap">
          {categorias.map((f) => (
            <button
              key={f}
              onClick={() => setFiltro(f)}
              className={`shrink-0 text-sm px-4 py-1.5 rounded-full border ${
                filtro === f ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      )}

      {cargando ? (
        <SkeletonLista ancho={esAncho} />
      ) : errorCarga ? (
        <div role="alert" className="mx-5 rounded-3xl bg-danger-soft border border-danger/30 p-6 text-center">
          <p className="text-sm text-danger">{errorCarga}</p>
        </div>
      ) : filtrados.length === 0 ? (
        <div className="mx-5 rounded-3xl bg-paper-raised border border-line p-8 text-center">
          <p className="text-sm text-ink-soft">No hay movimientos que coincidan</p>
        </div>
      ) : esAncho ? (
        <div role="table" aria-label="Movimientos" aria-rowcount={filas.length + 1} className="mx-5 rounded-2xl border border-line overflow-hidden bg-paper">
          <div role="row" aria-rowindex={1} className={`${COLUMNAS} h-10 bg-paper-raised border-b border-line text-[11px] font-bold text-ink-soft uppercase tracking-wide`}>
            <span role="columnheader">Fecha</span>
            <span role="columnheader">Descripción</span>
            <span role="columnheader">Categoría</span>
            <span role="columnheader">Cuenta</span>
            <span role="columnheader" className="text-right">Monto</span>
          </div>
          <div ref={listaRef} className="relative" style={{ height: altoTotal }}>
            {visibles.map((f, k) => {
              const i = rango.ini + k
              return f.tipo === 'dia' ? (
                <div
                  key={f.key}
                  role="row"
                  aria-rowindex={i + 2}
                  className="absolute inset-x-0 px-4 flex items-end pb-1.5 bg-paper-raised border-b border-line text-[11px] font-bold text-ink-soft uppercase tracking-wide"
                  style={{ top: offsets[i], height: alturas.dia }}
                >
                  <span role="columnheader">{f.label}</span>
                </div>
              ) : (
                filaTabla(f, offsets[i], i)
              )
            })}
          </div>
        </div>
      ) : (
        <div className="mx-5 relative">
          <div className="absolute left-[9px] top-1.5 bottom-1.5 w-0.5 bg-line" />
          <div ref={listaRef} className="relative" style={{ height: altoTotal }}>
            {visibles.map((f, k) => {
              const i = rango.ini + k
              return f.tipo === 'dia' ? (
                <p
                  key={f.key}
                  className="absolute text-[11px] font-bold text-ink-soft uppercase tracking-wide flex items-end pb-2"
                  style={{ top: offsets[i], height: alturas.dia, left: 20 }}
                >
                  {f.label}
                </p>
              ) : (
                filaMovil(f, offsets[i])
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

      {modoSeleccion && seleccionados.size > 0 && (
        <div className="sticky bottom-0 mx-5 mt-4 rounded-2xl bg-ink p-3 flex items-center gap-2 shadow-lg pop-in">
          <span className="text-xs text-paper font-medium shrink-0 px-1">
            {seleccionados.size} seleccionado{seleccionados.size === 1 ? '' : 's'}
          </span>
          <select
            disabled={aplicandoCategoria}
            aria-label="Mover los movimientos seleccionados a una categoría"
            onChange={(e) => {
              if (e.target.value) aplicarCategoriaMasiva(e.target.value)
            }}
            defaultValue=""
            className="flex-1 rounded-xl bg-paper text-ink px-3 py-2 text-sm outline-none"
          >
            <option value="" disabled>
              {aplicandoCategoria ? 'Aplicando...' : 'Mover a categoría...'}
            </option>
            {CATEGORIAS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <button
            onClick={salirModoSeleccion}
            className="w-9 h-9 shrink-0 rounded-xl bg-paper flex items-center justify-center"
            aria-label="Cerrar"
          >
            <X size={16} className="text-ink" />
          </button>
        </div>
      )}
    </div>
  )
}
