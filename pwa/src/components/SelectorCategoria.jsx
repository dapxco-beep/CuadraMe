import { useEffect, useMemo, useState } from 'react'
import { Plus, Search, X } from 'lucide-react'
import { api } from '../lib/api'
import { useCategorias } from '../lib/CategoriasContext'
import { claveComercio, huellaPeligrosa, patronDeComercio } from '../lib/comercio'
import Hoja from './Hoja'

const sinTildes = (t) => (t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

/**
 * Selector rápido de categoría: se abre desde el chip de cada fila de Movimientos (o desde la
 * barra de selección múltiple) y guarda AL ELEGIR, sin botón "Guardar".
 *  - Hoja inferior en teléfono, modal centrado en pantallas anchas (es la Hoja de siempre).
 *  - Arriba las más usadas recientemente, búsqueda y "Crear categoría".
 *  - Con `movimiento` (uno solo o un grupo de comercio) ofrece "Recordar para «comercio»"
 *    (marcada) y "Aplicar a los anteriores" con cuántos son. En edición masiva no hay reglas.
 * onElegir(categoria, { recordar, anteriores }) lo resuelve la pantalla (actualización optimista).
 */
export default function SelectorCategoria({ titulo, subtitulo, categoriaActual, movimiento, recientes = [], onElegir, onCerrar }) {
  const { nombres, iconoDe, recargar } = useCategorias()
  const [busqueda, setBusqueda] = useState('')
  const [creando, setCreando] = useState(false)
  const [aviso, setAviso] = useState('')

  const huella = movimiento ? claveComercio(patronDeComercio(movimiento.descripcion)) : ''
  const peligro = movimiento ? huellaPeligrosa(huella) : null
  const puedeRecordar = !!movimiento && !peligro
  const [recordar, setRecordar] = useState(true)
  const [anteriores, setAnteriores] = useState(false)
  const [similares, setSimilares] = useState(0)

  // Cuántos movimientos MÁS son del mismo comercio ("12 movimientos más")
  useEffect(() => {
    if (!puedeRecordar) return undefined
    let vigente = true
    Promise.resolve(api.similaresConteo?.(movimiento.descripcion, movimiento.id))
      .then((r) => vigente && setSimilares(r?.conteo || 0))
      .catch(() => {})
    return () => {
      vigente = false
    }
  }, [puedeRecordar, movimiento?.descripcion, movimiento?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const q = sinTildes(busqueda.trim())
  const filtradas = useMemo(() => nombres.filter((n) => !q || sinTildes(n).includes(q)), [nombres, q])
  const sugeridas = useMemo(
    () => (q ? [] : recientes.filter((n) => nombres.includes(n)).slice(0, 5)),
    [recientes, nombres, q]
  )
  const existeExacta = nombres.some((n) => sinTildes(n) === q)

  function elegir(categoria, cerrar) {
    onElegir(categoria, { recordar: puedeRecordar && recordar, anteriores: puedeRecordar && recordar && anteriores })
    cerrar()
  }

  async function crear(cerrar) {
    const nombre = busqueda.trim()
    if (!nombre) {
      setAviso('Escribe arriba el nombre de la nueva categoría')
      return
    }
    setCreando(true)
    setAviso('')
    try {
      await api.crearCategoria({ nombre, icono: '🏷️', tipo: 'ambos', color: null })
      await recargar?.()
      elegir(nombre, cerrar)
    } catch (err) {
      setAviso(err.message || 'No se pudo crear la categoría')
      setCreando(false)
    }
  }

  const chip = (n, cerrar) => (
    <button
      key={n}
      type="button"
      aria-pressed={categoriaActual === n}
      onClick={() => elegir(n, cerrar)}
      className={`text-sm px-3 py-2 min-h-[40px] rounded-full border ${
        categoriaActual === n ? 'bg-ink text-paper border-ink' : 'border-line text-ink'
      }`}
    >
      <span aria-hidden="true">{iconoDe(n)}</span> {n}
    </button>
  )

  return (
    <Hoja onCerrar={onCerrar} titulo={titulo || 'Elegir categoría'}>
      {({ cerrar }) => (
        <>
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-lg font-semibold">{titulo || 'Elegir categoría'}</h2>
            <button onClick={cerrar} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
              <X size={16} />
            </button>
          </div>
          {subtitulo && <p className="text-xs text-ink-soft mb-3 truncate">{subtitulo}</p>}

          {movimiento && (
            <div className="rounded-2xl border border-line bg-paper-raised p-3 mb-3 space-y-2">
              <label className={`flex items-start gap-3 ${puedeRecordar ? 'cursor-pointer' : 'opacity-60'}`}>
                <input
                  type="checkbox"
                  checked={puedeRecordar && recordar}
                  disabled={!puedeRecordar}
                  onChange={(e) => setRecordar(e.target.checked)}
                  className="mt-0.5 w-4 h-4 accent-[var(--c-accent)]"
                />
                <span className="text-sm">
                  Recordar para «{huella || patronDeComercio(movimiento.descripcion)}»
                  {peligro && <span className="block text-xs text-ink-soft mt-0.5">{peligro}: solo cambio este movimiento.</span>}
                </span>
              </label>
              {puedeRecordar && similares > 0 && (
                <label className={`flex items-start gap-3 ${recordar ? 'cursor-pointer' : 'opacity-50'}`}>
                  <input
                    type="checkbox"
                    checked={recordar && anteriores}
                    disabled={!recordar}
                    onChange={(e) => setAnteriores(e.target.checked)}
                    className="mt-0.5 w-4 h-4 accent-[var(--c-accent)]"
                  />
                  <span className="text-sm">
                    Aplicar a los anteriores del mismo comercio
                    <span className="block text-xs text-ink-soft mt-0.5">
                      {similares} {similares === 1 ? 'movimiento más' : 'movimientos más'}
                    </span>
                  </span>
                </label>
              )}
            </div>
          )}

          <div className="flex items-center gap-2 bg-paper-raised border border-line rounded-2xl px-3 py-2.5 mb-3">
            <Search size={16} className="text-ink-soft" />
            <input
              value={busqueda}
              onChange={(e) => {
                setBusqueda(e.target.value)
                setAviso('')
              }}
              aria-label="Buscar categoría"
              placeholder="Buscar o crear categoría"
              autoFocus={typeof window !== 'undefined' && !!window.matchMedia?.('(pointer: fine)').matches}
              className="bg-transparent outline-none text-sm flex-1 placeholder:text-ink-soft"
            />
          </div>

          {sugeridas.length > 0 && (
            <>
              <p className="text-[11px] font-bold text-ink-soft uppercase tracking-wide mb-1.5">Recientes</p>
              <div className="flex flex-wrap gap-2 mb-3" role="group" aria-label="Categorías recientes">
                {sugeridas.map((n) => chip(n, cerrar))}
              </div>
            </>
          )}

          <p className="text-[11px] font-bold text-ink-soft uppercase tracking-wide mb-1.5">{q ? 'Resultados' : 'Todas'}</p>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Categorías">
            {filtradas.map((n) => (sugeridas.includes(n) ? null : chip(n, cerrar)))}
            {filtradas.length === 0 && <p className="text-sm text-ink-soft">Ninguna categoría coincide.</p>}
          </div>

          {aviso && <p className="text-sm text-danger mt-3">{aviso}</p>}
          {!existeExacta && (
            <button
              type="button"
              onClick={() => crear(cerrar)}
              disabled={creando}
              className="mt-4 w-full flex items-center justify-center gap-2 rounded-2xl border border-dashed border-accent text-accent font-semibold py-3 text-sm disabled:opacity-60"
            >
              <Plus size={16} /> {busqueda.trim() ? `Crear categoría «${busqueda.trim()}»` : 'Crear categoría'}
            </button>
          )}
        </>
      )}
    </Hoja>
  )
}
