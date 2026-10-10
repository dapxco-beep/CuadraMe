import { useCallback, useEffect, useState } from 'react'
import { EsqueletoTarjeta } from '../components/Esqueletos'
import { ArrowLeft, Check, GraduationCap, Search } from 'lucide-react'
import { EstadoVacio } from '../brand/Marca'
import { useVolver } from '../lib/useVolver'
import { api } from '../lib/api'
import { formatCOP, formatPorcentaje, formatVeces } from '../lib/format'
import { useCategorias } from '../lib/CategoriasContext'

/** Texto de progreso de arriba: «Entrenaste 12 comercios · 83% de tus movimientos ya tienen categoría». */
export function textoProgreso(p) {
  if (!p) return ''
  const n = p.comercios_entrenados
  return `Entrenaste ${n} ${n === 1 ? 'comercio' : 'comercios'} · ${formatPorcentaje(p.porcentaje)} de tus movimientos ya tienen categoría`
}

function Fila({ item, categorias, onGuardar }) {
  const inicial = item.categoria_actual && item.categoria_actual !== 'Otros' ? item.categoria_actual : ''
  const [categoria, setCategoria] = useState(inicial)
  const [anteriores, setAnteriores] = useState(true)
  const [forzar, setForzar] = useState(false)
  const [estado, setEstado] = useState('') // '' | guardando
  const [error, setError] = useState('')

  async function guardar() {
    if (!categoria) return setError('Elige una categoría')
    setEstado('guardando')
    setError('')
    try {
      await onGuardar(item, categoria, anteriores, forzar)
    } catch (err) {
      setError(err.message || 'No se pudo guardar. Revisa tu conexión e intenta de nuevo.')
      setEstado('')
    }
  }

  return (
    <li className="px-4 py-3.5" data-testid="fila-entrenar">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold truncate">{item.clave}</p>
          <p className="text-xs text-ink-soft truncate">Ej.: {item.ejemplo}</p>
          <p className="text-xs text-ink-soft mt-0.5">
            {formatVeces(item.conteo)} · {formatCOP(item.monto_total)}
            {item.categoria_actual !== 'Otros' ? ` · hoy en ${item.categoria_actual} (sin confirmar)` : ' · sin categoría'}
          </p>
        </div>
      </div>
      <div className="flex gap-2 mt-2.5">
        <select
          aria-label={`Categoría para ${item.clave}`}
          value={categoria}
          onChange={(e) => setCategoria(e.target.value)}
          className="flex-1 min-w-0 rounded-xl border border-line bg-paper px-3 py-2 text-xs"
        >
          <option value="">Elige categoría…</option>
          {categorias.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <button
          onClick={guardar}
          disabled={estado === 'guardando'}
          className="rounded-xl bg-ink text-paper px-3.5 text-xs font-semibold flex items-center gap-1.5 disabled:opacity-60"
        >
          <Check size={16} /> {estado === 'guardando' ? 'Guardando…' : 'Guardar regla'}
        </button>
      </div>
      <label className="flex items-center gap-2 text-xs text-ink-soft mt-2">
        <input type="checkbox" checked={anteriores} onChange={(e) => setAnteriores(e.target.checked)} className="w-4 h-4 accent-accent" />
        Aplicar también a los anteriores
      </label>
      {item.peligrosa && (
        <label className="flex items-start gap-2 text-xs text-ink-soft mt-2">
          <input type="checkbox" checked={forzar} onChange={(e) => setForzar(e.target.checked)} className="w-4 h-4 mt-0.5 accent-accent" />
          <span>{item.peligrosa}. Marca esta casilla para guardarla de todos modos.</span>
        </label>
      )}
      {error && <p className="text-xs text-danger mt-2" role="alert">{error}</p>}
    </li>
  )
}

export default function EntrenarCategorias() {
  const volver = useVolver('/reglas-categoria')
  const { nombres } = useCategorias()
  const categorias = nombres.filter((n) => n !== 'Transferencias')
  const [datos, setDatos] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [q, setQ] = useState('')
  const [explicacion, setExplicacion] = useState(null)
  const [buscando, setBuscando] = useState(false)

  const cargar = useCallback(async () => {
    setError('')
    try {
      setDatos(await api.vocabularioCategorias())
    } catch (err) {
      setError(err.message || 'No se pudo cargar tu vocabulario. Revisa tu conexión e intenta de nuevo.')
    }
    setCargando(false)
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function guardar(item, categoria, anteriores, forzar) {
    // Comercios: la descripción de ejemplo da la misma huella que el grupo. Palabras: la propia palabra.
    const r = await api.aprenderRegla({
      descripcion: item.tipo === 'palabra' ? item.clave : item.ejemplo,
      categoria,
      aplicar_anteriores: anteriores,
      confirmar_peligrosa: forzar,
    })
    if (!r.guardada) throw new Error(r.motivo || 'No se guardó la regla')
    setAviso(
      r.anteriores_actualizados > 0
        ? `Listo: «${r.huella}» es ${categoria}. Corregí ${r.anteriores_actualizados} ${r.anteriores_actualizados === 1 ? 'movimiento' : 'movimientos'} anteriores.`
        : `Listo: la próxima vez que salga «${r.huella}» ya sabré que es ${categoria}.`
    )
    await cargar()
  }

  async function buscar(e) {
    e.preventDefault()
    if (q.trim().length < 2) return
    setBuscando(true)
    setExplicacion(null)
    try {
      setExplicacion(await api.explicarCategoria(q.trim()))
    } catch (err) {
      setError(err.message || 'No se pudo buscar. Revisa tu conexión e intenta de nuevo.')
    }
    setBuscando(false)
  }

  const comercios = datos?.comercios || []
  const palabras = datos?.palabras || []

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Enseñar categorías</h1>
      </header>

      <p className="mx-6 mt-2 text-xs text-ink-soft">
        Enséñame qué es cada comercio y no te lo vuelvo a preguntar. Primero van los que más plata mueven.
      </p>

      {datos && (
        <div className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-4" data-testid="progreso-entrenar">
          <p className="text-sm font-semibold">{textoProgreso(datos.progreso)}</p>
          <div
            className="h-2 rounded-full bg-line mt-2.5 overflow-hidden"
            role="progressbar"
            aria-valuenow={datos.progreso.porcentaje}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Movimientos con categoría"
          >
            <div className="h-full w-full bg-accent rounded-full barra-fill" style={{ transform: `scaleX(${datos.progreso.porcentaje / 100})` }} />
          </div>
        </div>
      )}

      {aviso && (
        <p className="mx-6 mt-3 rounded-2xl bg-accent-soft px-4 py-3 text-sm text-ink" role="status">{aviso}</p>
      )}

      <form onSubmit={buscar} className="mx-6 mt-4">
        <label className="text-xs text-ink-soft font-medium uppercase tracking-wide">¿Por qué se categorizó así?</label>
        <div className="flex gap-2 mt-1.5">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Busca un movimiento (ej. vento, pan, uber)"
            aria-label="Buscar un movimiento de ejemplo"
            className="flex-1 min-w-0 rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={buscando || q.trim().length < 2}
            className="w-12 rounded-2xl bg-accent text-white flex items-center justify-center disabled:opacity-60"
            aria-label="Buscar"
          >
            <Search size={16} />
          </button>
        </div>
      </form>

      {explicacion && (
        <ul className="mx-6 mt-3 rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden" data-testid="explicaciones">
          {explicacion.resultados.map((r, i) => (
            <li key={i} className="px-4 py-3">
              <p className="text-sm font-medium truncate">{r.descripcion}</p>
              <p className="text-xs text-ink-soft mt-0.5">
                {r.es_ejemplo ? 'No tienes un movimiento así; con esa descripción: ' : r.categoria_guardada ? `Guardado en ${r.categoria_guardada}. Hoy lo pondría en ` : 'Lo pondría en '}
                <b>{r.categoria_sugerida}</b>
              </p>
              <p className="text-xs text-accent mt-0.5">{r.razon}</p>
              <p className="text-[11px] text-ink-soft mt-0.5">Nombre con el que lo reconozco: «{r.huella || '—'}»</p>
            </li>
          ))}
        </ul>
      )}

      {cargando ? (
        <EsqueletoTarjeta alto={220} className="mx-6 mt-6" etiqueta="Cargando movimientos por entrenar" />
      ) : error ? (
        <div className="mx-6 mt-6 rounded-2xl bg-danger-soft p-6 text-center">
          <p className="text-sm text-danger mb-3">{error}</p>
          <button onClick={cargar} className="text-sm font-semibold text-danger underline">Reintentar</button>
        </div>
      ) : comercios.length === 0 && palabras.length === 0 ? (
        <EstadoVacio
          icono={GraduationCap}
          titulo="No hay nada por enseñar"
          texto="Todo lo que tienes ya está categorizado. Cuando importes un extracto con comercios nuevos, aparecerán aquí."
          className="mx-6 mt-6"
        />
      ) : (
        <>
          {comercios.length > 0 && (
            <section className="mx-6 mt-5" aria-label="Comercios por enseñar">
              <h2 className="text-sm font-semibold mb-2">Comercios que aún no conozco ({comercios.length})</h2>
              <ul className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
                {comercios.map((c) => (
                  <Fila key={`c-${c.clave}`} item={c} categorias={categorias} onGuardar={guardar} />
                ))}
              </ul>
            </section>
          )}
          {palabras.length > 0 && (
            <section className="mx-6 mt-5" aria-label="Palabras por enseñar">
              <h2 className="text-sm font-semibold mb-1">Palabras que se repiten</h2>
              <p className="text-xs text-ink-soft mb-2">Una palabra suelta (ej. «pan») sirve para todos los comercios que la contengan.</p>
              <ul className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
                {palabras.map((p) => (
                  <Fila key={`p-${p.clave}`} item={p} categorias={categorias} onGuardar={guardar} />
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  )
}
