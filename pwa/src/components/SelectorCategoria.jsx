import { textoError } from '../lib/textoError'
import { useEffect, useMemo, useState } from 'react'
import { Plus, Search, X } from 'lucide-react'
import { api } from '../lib/api'
import { useCategorias } from '../lib/CategoriasContext'
import { claveComercio, huellaPeligrosa, patronDeComercio } from '../lib/comercio'
import { recordarPorDefecto, textoVistaPrevia } from '../lib/porCategorizar'
import Hoja from './Hoja'

const sinTildes = (t) => (t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

/**
 * Selector rápido de categoría: se abre desde el chip de cada fila de Movimientos (o desde la
 * barra de selección múltiple) y guarda AL ELEGIR, sin botón "Guardar".
 *  - Hoja inferior en teléfono, modal centrado en pantallas anchas (es la Hoja de siempre).
 *  - Arriba las más usadas recientemente, búsqueda y "Crear categoría".
 *  - Con `movimiento` (uno solo o un grupo de comercio) ofrece "Recordar para «comercio»"
 *    (marcada) y "Aplicar a los anteriores" con cuántos son. En edición masiva no hay reglas.
 *  - Subcategorías (opcionales, docs/SUBCATEGORIAS.md): si la categoría elegida ya tiene, se abre un segundo
 *    paso con chips + «Nueva subcategoría» (crea y asigna en un toque) + «Solo {categoría}» para saltarlo.
 *    Si no tiene, guarda de una como siempre; «Con subcategoría» deja detallar desde cero en un toque.
 * onElegir(categoria, { recordar, anteriores, subcategoria }) lo resuelve la pantalla (actualización optimista).
 */
export default function SelectorCategoria({ titulo, subtitulo, categoriaActual, movimiento, tipoMovimiento, recientes = [], conSubcategorias = true, onElegir, onCerrar }) {
  const { nombres: todas, nombresDe, iconoDe, recargar, subsDe: subsDeTodas } = useCategorias()
  // Solo las categorías que valen para este movimiento (gasto o ingreso); sin tipo, todas.
  const tipoMov = tipoMovimiento || movimiento?.tipo
  const nombres = useMemo(() => (nombresDe ? nombresDe(tipoMov, categoriaActual) : todas), [nombresDe, todas, tipoMov, categoriaActual]) // eslint-disable-line react-hooks/exhaustive-deps
  // Pantallas que aún no guardan subcategoría (conSubcategorias={false}) siguen en un solo paso.
  const subsDe = conSubcategorias ? subsDeTodas : undefined
  const [paso, setPaso] = useState(null) // categoría elegida cuando se está escogiendo su subcategoría
  const [detallar, setDetallar] = useState(false)
  const [nuevaSub, setNuevaSub] = useState(null) // null = cerrado; string = texto del input
  const [guardandoSub, setGuardandoSub] = useState(false)
  const [busqueda, setBusqueda] = useState('')
  const [creando, setCreando] = useState(false)
  const [aviso, setAviso] = useState('')

  const huella = movimiento ? claveComercio(patronDeComercio(movimiento.descripcion)) : ''
  const peligro = movimiento ? huellaPeligrosa(huella) : null
  const puedeRecordar = !!movimiento && !peligro
  // La regla es OPCIONAL: solo viene activada si el comercio se repite 3 o más veces (compras únicas: apagada).
  const [recordar, setRecordar] = useState(false)
  const [tocoRecordar, setTocoRecordar] = useState(false)
  const [anteriores, setAnteriores] = useState(false)
  const [similares, setSimilares] = useState(0)

  // Cuántos movimientos MÁS son del mismo comercio ("12 movimientos más")
  useEffect(() => {
    if (!puedeRecordar) return undefined
    let vigente = true
    Promise.resolve(api.similaresConteo?.(movimiento.descripcion, movimiento.id))
      .then((r) => {
        if (!vigente) return
        const otros = r?.conteo || 0
        setSimilares(otros)
        // Con el interruptor sin tocar, se activa solo si con este movimiento son 3 o más.
        setRecordar((actual) => (tocoRecordar ? actual : recordarPorDefecto(otros + 1)))
      })
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

  function elegir(categoria, cerrar, subcategoria = null) {
    onElegir(categoria, {
      recordar: puedeRecordar && recordar,
      anteriores: puedeRecordar && recordar && anteriores,
      ...(subcategoria ? { subcategoria } : {}),
    })
    cerrar()
  }

  // Tocar una categoría: si tiene subcategorías (o pidió detallar) se abre el paso 2; si no, guarda de una.
  function tocar(categoria, cerrar) {
    const tiene = (subsDe ? subsDe(categoria) : []).length > 0
    if (tiene || detallar) {
      setPaso(categoria)
      setNuevaSub(tiene ? null : '')
      setAviso('')
      return
    }
    elegir(categoria, cerrar)
  }

  async function crearSub(cerrar) {
    const nombre = (nuevaSub || '').trim()
    if (!nombre) {
      setAviso('Escribe el nombre de la subcategoría')
      return
    }
    setGuardandoSub(true)
    setAviso('')
    try {
      const s = await api.crearSubcategoria(paso, nombre)
      await recargar?.()
      elegir(paso, cerrar, s?.nombre || nombre)
    } catch (err) {
      setAviso(textoError(err, 'crear la subcategoría'))
      setGuardandoSub(false)
    }
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
      setAviso(textoError(err, 'crear la categoría'))
      setCreando(false)
    }
  }

  const chip = (n, cerrar) => (
    <button
      key={n}
      type="button"
      aria-pressed={categoriaActual === n}
      onClick={() => tocar(n, cerrar)}
      className={`text-sm px-3 py-2 min-h-[40px] rounded-full border ${
        categoriaActual === n ? 'bg-ink text-paper border-ink' : 'border-line text-ink'
      }`}
    >
      <span aria-hidden="true">{iconoDe(n)}</span> {n}
      {(subsDe ? subsDe(n) : []).length > 0 && <span className="text-ink-soft text-xs" aria-hidden="true"> ›</span>}
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
                  onChange={(e) => {
                    setTocoRecordar(true)
                    setRecordar(e.target.checked)
                  }}
                  className="mt-0.5 w-4 h-4 accent-[var(--c-accent)]"
                />
                <span className="text-sm">
                  Recordar para este comercio
                  <span className="block text-xs text-ink-soft mt-0.5">«{huella || patronDeComercio(movimiento.descripcion)}»</span>
                  {puedeRecordar && recordar && (
                    <span className="block text-xs text-ink-soft mt-0.5" data-testid="vista-previa-regla">{textoVistaPrevia(similares)}</span>
                  )}
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

          {paso && (
            <div data-testid="paso-subcategoria">
              <p className="text-sm font-semibold mb-0.5">
                <span aria-hidden="true">{iconoDe(paso)}</span> {paso}
              </p>
              <p className="text-xs text-ink-soft mb-3">¿Cuál es? Es opcional.</p>
              <div className="flex flex-wrap gap-2" role="group" aria-label={`Subcategorías de ${paso}`}>
                {(subsDe ? subsDe(paso) : []).map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => elegir(paso, cerrar, s.nombre)}
                    className="text-sm px-3 py-2 min-h-[40px] rounded-full border border-line text-ink"
                  >
                    {s.nombre}
                  </button>
                ))}
                {nuevaSub === null && (
                  <button
                    type="button"
                    onClick={() => setNuevaSub('')}
                    className="text-sm px-3 py-2 min-h-[40px] rounded-full border border-dashed border-accent text-accent font-semibold"
                  >
                    + Nueva subcategoría
                  </button>
                )}
              </div>
              {nuevaSub !== null && (
                <div className="flex items-center gap-2 mt-3">
                  <input
                    value={nuevaSub}
                    onChange={(e) => {
                      setNuevaSub(e.target.value)
                      setAviso('')
                    }}
                    onKeyDown={(e) => e.key === 'Enter' && crearSub(cerrar)}
                    aria-label="Nombre de la subcategoría"
                    placeholder="Ej: Gasolina"
                    maxLength={40}
                    autoFocus
                    className="flex-1 bg-paper-raised border border-line rounded-2xl px-3 py-2.5 text-sm outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => crearSub(cerrar)}
                    disabled={guardandoSub}
                    className="rounded-2xl bg-ink text-paper text-sm font-semibold px-4 min-h-[44px] disabled:opacity-60"
                  >
                    Crear y poner
                  </button>
                </div>
              )}
              {aviso && <p className="text-sm text-danger mt-3">{aviso}</p>}
              <button
                type="button"
                onClick={() => elegir(paso, cerrar)}
                className="mt-4 w-full rounded-2xl border border-line py-3 text-sm font-semibold"
              >
                Solo {paso}
              </button>
              <button
                type="button"
                onClick={() => {
                  setPaso(null)
                  setNuevaSub(null)
                  setAviso('')
                }}
                className="mt-2 w-full text-xs text-ink-soft underline py-2"
              >
                Cambiar categoría
              </button>
            </div>
          )}

          {!paso && (
          <>
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
          <button
            type="button"
            onClick={() => setDetallar((d) => !d)}
            aria-pressed={detallar}
            hidden={!conSubcategorias}
            className={`mt-3 w-full text-xs underline py-2 ${detallar ? 'text-accent font-semibold' : 'text-ink-soft'}`}
          >
            {detallar ? 'Con subcategoría: toca la categoría' : 'Con subcategoría'}
          </button>
          </>
          )}
        </>
      )}
    </Hoja>
  )
}
