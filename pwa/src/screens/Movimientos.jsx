import { useEffect, useState } from 'react'
import { EstadoVacio } from '../brand/Marca'
import { Link, useSearchParams } from 'react-router-dom'
import { Check, Download, Search, SlidersHorizontal, Upload, X } from 'lucide-react'
import { formatCOP, formatMoneda } from '../lib/format'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import { useDialogos } from '../lib/DialogosContext'
import { tipoEfectivo } from '../lib/contabilidad'
import { esAuto, porRevisar } from '../lib/comercio'
import { HojaCambiarCategoria, InsigniaAuto } from '../components/CategorizacionAuto'

const TAMANO_PAGINA = 200

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

export default function Movimientos() {
  const { cuentas } = useCuentas()
  const { nombres: CATEGORIAS, iconoDe } = useCategorias()
  const { avisar, confirmar } = useDialogos()
  const monedaDe = Object.fromEntries(cuentas.map((c) => [c.id, c.moneda]))
  const [movimientos, setMovimientos] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [filtro, setFiltro] = useState('Todos')
  const [cuentaId, setCuentaId] = useState('')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [mostrarFiltrosFecha, setMostrarFiltrosFecha] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [exportando, setExportando] = useState(false)
  const [modoSeleccion, setModoSeleccion] = useState(false)
  const [seleccionados, setSeleccionados] = useState(new Set())
  const [aplicandoCategoria, setAplicandoCategoria] = useState(false)
  const [hayMas, setHayMas] = useState(false)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [errorCarga, setErrorCarga] = useState('')
  // "Por revisar": lo que la app categorizó sola sin confirmar + lo que quedó en 'Otros'.
  const [params, setParams] = useSearchParams()
  const soloRevisar = params.get('revisar') === '1'
  const [conteo, setConteo] = useState({ auto: 0, otros: 0, total: 0 })
  const [cambiando, setCambiando] = useState(null)

  // En la vista normal se llama como siempre; "Por revisar" agrega el filtro.
  function pedirMovimientos(offset) {
    return soloRevisar
      ? api.movimientos(TAMANO_PAGINA, offset, { porRevisar: true })
      : api.movimientos(TAMANO_PAGINA, offset)
  }

  function recargarConteo() {
    Promise.resolve(api.conteoPorRevisar?.())
      .then((c) => c && setConteo(c))
      .catch(() => {})
  }

  useEffect(() => {
    setCargando(true)
    setErrorCarga('')
    pedirMovimientos(0)
      .then((movs) => {
        setMovimientos(movs)
        setHayMas(movs.length === TAMANO_PAGINA)
      })
      .catch((err) => setErrorCarga(err.message || 'No se pudieron cargar los movimientos'))
      .finally(() => setCargando(false))
    recargarConteo()
  }, [soloRevisar])

  function alternarRevisar() {
    setFiltro('Todos')
    setParams(soloRevisar ? {} : { revisar: '1' }, { replace: true })
  }

  async function confirmarUno(m) {
    try {
      await api.confirmarCategorias([m.id])
      setMovimientos((prev) =>
        soloRevisar && m.categoria !== 'Otros'
          ? prev.filter((x) => x.id !== m.id)
          : prev.map((x) => (x.id === m.id ? { ...x, cat_confirmada: true, cat_origen: null } : x))
      )
      recargarConteo()
    } catch {
      avisar('No se pudo confirmar la categoría')
    }
  }

  async function confirmarTodas() {
    const ok = await confirmar(
      'Se dejarán como correctas las categorías que la app puso sola. Los de "Otros" siguen pendientes.',
      { titulo: `¿Confirmar ${conteo.auto} categorías?`, confirmarTexto: 'Confirmar todas' }
    )
    if (!ok) return
    try {
      await api.confirmarCategorias(null)
      const movs = await pedirMovimientos(0)
      setMovimientos(movs)
      setHayMas(movs.length === TAMANO_PAGINA)
      recargarConteo()
    } catch {
      avisar('No se pudieron confirmar')
    }
  }

  async function alCambiarCategoria(r) {
    setCambiando(null)
    avisar(
      r.actualizados > 1
        ? `Listo: ${r.actualizados} movimientos movidos y regla creada para "${r.patron}"`
        : 'Categoría actualizada',
      'ok'
    )
    try {
      const movs = await pedirMovimientos(0)
      setMovimientos(movs)
      setHayMas(movs.length === TAMANO_PAGINA)
    } catch {
      /* se queda con lo que había */
    }
    recargarConteo()
  }

  async function cargarMas() {
    setCargandoMas(true)
    try {
      const siguientes = await pedirMovimientos(movimientos.length)
      setMovimientos((prev) => [...prev, ...siguientes])
      setHayMas(siguientes.length === TAMANO_PAGINA)
    } catch {
      avisar('No se pudieron cargar más movimientos')
    } finally {
      setCargandoMas(false)
    }
  }

  const categorias = ['Todos', ...new Set(movimientos.map((m) => m.categoria))]

  const filtrados = movimientos.filter((m) => {
    const coincideBusqueda = m.descripcion.toLowerCase().includes(busqueda.toLowerCase())
    const coincideFiltro = filtro === 'Todos' || m.categoria === filtro
    const coincideCuenta = !cuentaId || m.cuenta_id === cuentaId
    const coincideDesde = !desde || m.fecha.slice(0, 10) >= desde
    const coincideHasta = !hasta || m.fecha.slice(0, 10) <= hasta
    return coincideBusqueda && coincideFiltro && coincideCuenta && coincideDesde && coincideHasta
  })

  // Totales con la regla contable: el pago de la tarjeta y los traslados propios no suman.
  const tiposCuenta = Object.fromEntries(cuentas.map((c) => [c.id, c.tipo]))
  const totalIngresos = filtrados.filter((m) => tipoEfectivo(m, tiposCuenta) === 'income').reduce((s, m) => s + m.monto, 0)
  const totalGastos = filtrados.filter((m) => tipoEfectivo(m, tiposCuenta) === 'expense').reduce((s, m) => s + m.monto, 0)
  const hayFiltrosActivos = !!(cuentaId || desde || hasta || (filtro !== 'Todos') || busqueda)

  const grupos = []
  for (const m of filtrados) {
    const diaKey = m.fecha.slice(0, 10)
    let grupo = grupos.find((g) => g.diaKey === diaKey)
    if (!grupo) {
      grupo = { diaKey, label: etiquetaDia(m.fecha), items: [] }
      grupos.push(grupo)
    }
    grupo.items.push(m)
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
      setMovimientos((prev) =>
        prev.map((m) => (seleccionados.has(m.id) ? { ...m, categoria, cat_confirmada: true, cat_origen: null } : m))
      )
      salirModoSeleccion()
      recargarConteo()
    } catch {
      avisar('No se pudo actualizar la categoría')
    } finally {
      setAplicandoCategoria(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter pantalla-ancha">
      <header className="px-5 pantalla-top pb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Movimientos</h1>
        {modoSeleccion ? (
          <button onClick={salirModoSeleccion} className="text-sm text-accent font-medium">
            Cancelar
          </button>
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
              className={`w-11 h-11 rounded-full border flex items-center justify-center ${
                mostrarFiltrosFecha || desde || hasta ? 'bg-accent-soft border-accent text-accent' : 'border-line text-ink-soft'
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
              to="/importar"
              className="w-11 h-11 rounded-full border border-line text-ink-soft flex items-center justify-center"
              aria-label="Importar desde Excel o CSV"
            >
              <Upload size={16} />
            </Link>
          </div>
        )}
      </header>

      {/* ≥1024 px: filtros y resumen a la izquierda (fijos al hacer scroll), lista a la derecha */}
      <div className="dos-col dos-col-5-6">
      <div className="col col-sticky">
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
          <Search size={18} className="text-ink-soft" />
          <input
            value={busqueda}
            aria-label="Buscar movimiento"
            data-atajo-buscar
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar movimiento"
            className="bg-transparent outline-none text-sm flex-1 placeholder:text-ink-soft"
          />
        </div>
      </div>

      {(conteo.total > 0 || soloRevisar) && (
        <div className="px-5 mb-3 flex items-center gap-2">
          <button
            onClick={alternarRevisar}
            aria-pressed={soloRevisar}
            className={`text-sm px-4 py-1.5 rounded-full border font-medium ${
              soloRevisar ? 'bg-accent text-white border-accent' : 'border-accent text-accent'
            }`}
          >
            Por revisar{conteo.total > 0 ? ` (${conteo.total})` : ''}
          </button>
          {soloRevisar && conteo.auto > 0 && (
            <button onClick={confirmarTodas} className="text-xs text-ink-soft font-medium underline">
              Confirmar las {conteo.auto} automáticas
            </button>
          )}
        </div>
      )}

      {!soloRevisar && categorias.length > 1 && (
        <div className="px-5 flex gap-2 mb-4 overflow-x-auto no-scrollbar lg:flex-wrap lg:overflow-visible">
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

      </div>
      <div className="col">
      {cargando ? (
        <p className="text-sm text-ink-soft text-center mt-8">Cargando...</p>
      ) : errorCarga ? (
        <div role="alert" className="mx-5 rounded-3xl bg-danger-soft border border-danger/30 p-6 text-center">
          <p className="text-sm text-danger">{errorCarga}</p>
        </div>
      ) : filtrados.length === 0 ? (
        <EstadoVacio
          icono={Search}
          titulo={soloRevisar && !hayFiltrosActivos ? 'Todo está revisado' : 'No hay movimientos que coincidan'}
          texto={
            soloRevisar && !hayFiltrosActivos
              ? 'No hay categorías automáticas pendientes ni movimientos en "Otros".'
              : 'Prueba con otro filtro o búsqueda.'
          }
          className="mx-5"
        />
      ) : (
        <div className="mx-5 relative pl-5">
          <div className="absolute left-[9px] top-1.5 bottom-1.5 w-0.5 bg-line" />
          {(() => {
            let indiceGlobal = 0
            return grupos.map((grupo) => (
            <div key={grupo.diaKey}>
              <p className="text-[11px] font-bold text-ink-soft uppercase tracking-wide mt-5 mb-2.5 first:mt-0">
                {grupo.label}
              </p>
              {grupo.items.map((m) => {
                const staggerI = Math.min(indiceGlobal++, 12)
                const contenido = (
                  <>
                    <span
                      className={`absolute -left-5 top-[18px] w-2.5 h-2.5 rounded-full border-2 border-paper ${
                        m.tipo === 'income' ? 'bg-accent-2' : 'bg-ink'
                      }`}
                    />
                    <div className="flex items-center justify-between gap-3">
                      {modoSeleccion && (
                        <span
                          className={`w-5 h-5 rounded-md border-2 shrink-0 flex items-center justify-center ${
                            seleccionados.has(m.id) ? 'bg-accent border-accent' : 'border-line'
                          }`}
                        >
                          {seleccionados.has(m.id) && <Check size={13} className="text-white" />}
                        </span>
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold truncate">{m.descripcion}</p>
                        <p className="text-xs text-ink-soft mt-0.5">
                          <span aria-hidden="true">{m.tipo === 'transfer' ? '🔁' : iconoDe(m.categoria)}</span> {m.categoria}
                          {esAuto(m) && <InsigniaAuto movimiento={m} />}
                        </p>
                      </div>
                      <span className={`text-[15px] font-bold shrink-0 ${m.tipo === 'income' ? 'text-accent-2' : m.tipo === 'transfer' ? 'text-ink-soft' : 'text-ink'}`}>
                        {m.tipo === 'income' ? '+' : m.tipo === 'expense' ? '-' : ''}
                        {formatMoneda(m.monto, monedaDe[m.cuenta_id])}
                      </span>
                    </div>
                  </>
                )
                return modoSeleccion ? (
                  <button
                    key={m.id}
                    onClick={() => toggleSeleccion(m.id)}
                    className="relative block w-full text-left py-2.5 stagger-item"
                    style={{ '--stagger-i': staggerI }}
                  >
                    {contenido}
                  </button>
                ) : (
                  <div key={m.id} className="relative stagger-item" style={{ '--stagger-i': staggerI }}>
                    <Link to={`/movimientos/${m.id}`} className="relative block py-2.5">
                      {contenido}
                    </Link>
                    {soloRevisar && porRevisar(m) && (
                      <div className="flex gap-2 pb-2.5 -mt-1">
                        {esAuto(m) && (
                          <button
                            onClick={() => confirmarUno(m)}
                            aria-label={`Confirmar categoría de ${m.descripcion}`}
                            className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-full bg-accent text-white"
                          >
                            <Check size={13} /> Confirmar
                          </button>
                        )}
                        <button
                          onClick={() => setCambiando(m)}
                          aria-label={`Cambiar categoría de ${m.descripcion}`}
                          className="text-xs font-semibold px-3 py-1.5 rounded-full border border-line text-ink-soft"
                        >
                          Cambiar categoría
                        </button>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ))
          })()}
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

      {cambiando && (
        <HojaCambiarCategoria movimiento={cambiando} onClose={() => setCambiando(null)} onHecho={alCambiarCategoria} />
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
            className="w-11 h-11 shrink-0 rounded-xl bg-paper flex items-center justify-center"
            aria-label="Cerrar"
          >
            <X size={16} className="text-ink" />
          </button>
        </div>
      )}
    </div>
  )
}
