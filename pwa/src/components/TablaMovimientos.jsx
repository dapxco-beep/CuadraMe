import { memo, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowUp, ArrowUpDown, Check, Columns3 } from 'lucide-react'
import Icono from './Icono'
import { formatMoneda } from '../lib/format'
import { direccionDe, signoDe } from '../lib/traslados'
import { COLUMNAS_TABLA, ordenarMovimientos } from '../lib/movimientosLista'

// Tabla de movimientos para escritorio. Mismas reglas que la lista: filas virtualizadas (alto fijo,
// solo se pintan las visibles más un margen), selección masiva con casillas y el detalle en el panel.
export const ALTO_FILA_TABLA = 48
const MARGEN = 600
const LLAVE_COLUMNAS = 'cuadrame:tabla-movimientos:columnas'

function leerColumnas() {
  try {
    const g = JSON.parse(localStorage.getItem(LLAVE_COLUMNAS) || 'null')
    if (g && typeof g === 'object') return g
  } catch {
    // sin almacenamiento: se usan las columnas por defecto
  }
  return {}
}

const fechaCorta = (iso) => new Date(iso).toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' })

const Casilla = ({ marcada, etiqueta, onClick }) => (
  <button type="button" role="checkbox" aria-checked={marcada} aria-label={etiqueta} onClick={onClick} className="w-11 h-11 flex items-center justify-center">
    <span className={`w-5 h-5 rounded-md border-2 flex items-center justify-center ${marcada ? 'bg-accent border-accent' : 'border-line'}`}>
      {marcada && <Check size={16} className="text-white" aria-hidden="true" />}
    </span>
  </button>
)

const Fila = memo(function Fila({ m, columnas, icono, moneda, cuenta, esSel, activa, onToggle, onAbrir, onChip }) {
  const dir = direccionDe(m)
  const esTransfer = m.fuente === 'transferencia_interna'
  return (
    <tr
      data-fila={m.id}
      aria-selected={esSel || undefined}
      style={{ height: ALTO_FILA_TABLA }}
      className={`border-b border-line ${activa ? 'bg-accent-soft' : esSel ? 'bg-paper-raised' : 'hover:bg-paper-raised'}`}
    >
      <td className="w-11 pl-2">
        <Casilla marcada={esSel} etiqueta={`Seleccionar ${m.descripcion}`} onClick={() => onToggle(m.id)} />
      </td>
      <td className="px-3 text-xs text-ink-soft whitespace-nowrap">{fechaCorta(m.fecha)}</td>
      <td className="px-3 min-w-0 max-w-0 w-full">
        <Link
          to={`/movimientos/${m.id}`}
          onClick={(e) => {
            e.preventDefault()
            onAbrir(m.id)
          }}
          className="block truncate text-sm font-semibold py-2"
        >
          {m.descripcion}
        </Link>
      </td>
      {columnas.categoria && (
        <td className="px-3 whitespace-nowrap">
          {esTransfer ? (
            <span className="text-xs text-ink-soft">{m.categoria}</span>
          ) : (
            <button
              type="button"
              onClick={() => onChip(m)}
              aria-label={`Cambiar categoría de ${m.descripcion}`}
              className="inline-flex items-center gap-1 text-xs text-ink-soft rounded-full border border-line px-2.5 min-h-[32px] hover:border-accent hover:text-ink"
            >
              <span aria-hidden="true">{icono}</span> {m.categoria}
            </button>
          )}
        </td>
      )}
      {columnas.cuenta && <td className="px-3 text-xs text-ink-soft whitespace-nowrap max-w-[160px] truncate">{cuenta}</td>}
      <td className={`px-3 pr-4 text-right text-[15px] font-bold tabular-nums whitespace-nowrap ${dir === 'income' ? 'text-gold' : dir ? 'text-ink' : 'text-ink-soft'}`}>
        {signoDe(m)}
        {formatMoneda(m.monto, moneda)}
      </td>
    </tr>
  )
})

export default function TablaMovimientos({
  items, iconoDe, monedaDe, nombreCuenta, seleccionados, panelId, onToggle, onToggleTodos, onAbrir, onChip,
}) {
  const [orden, setOrden] = useState({ col: 'fecha', dir: 'desc' })
  const [columnas, setColumnas] = useState(() => ({ categoria: true, cuenta: true, ...leerColumnas() }))
  const [menu, setMenu] = useState(false)
  const [vista, setVista] = useState(0)
  const raiz = useRef(null)

  const ordenados = useMemo(
    () =>
      ordenarMovimientos(items, orden, {
        nombreCuenta,
        firmado: (m) => (Number(m.monto) || 0) * (direccionDe(m) === 'expense' ? -1 : 1),
      }),
    [items, orden, nombreCuenta]
  )

  useEffect(() => {
    let pendiente = 0
    const programar = () => {
      if (pendiente) return
      pendiente = requestAnimationFrame(() => {
        pendiente = 0
        setVista((v) => v + 1)
      })
    }
    document.addEventListener('scroll', programar, { capture: true, passive: true })
    window.addEventListener('resize', programar)
    return () => {
      document.removeEventListener('scroll', programar, { capture: true })
      window.removeEventListener('resize', programar)
      if (pendiente) cancelAnimationFrame(pendiente)
    }
  }, [])
  useLayoutEffect(() => {
    setVista((v) => v + 1)
  }, [items.length])

  const n = ordenados.length
  const rect = raiz.current ? raiz.current.getBoundingClientRect() : { top: 0 }
  const vh = (typeof window !== 'undefined' && window.innerHeight) || 800
  const desde = Math.max(0, -rect.top - MARGEN)
  const hasta = -rect.top + vh + MARGEN
  const ini = Math.min(Math.max(0, n - 1), Math.floor(desde / ALTO_FILA_TABLA))
  const fin = Math.min(n, Math.max(ini + 1, Math.ceil(hasta / ALTO_FILA_TABLA)))
  void vista // el estado fuerza el recálculo al hacer scroll

  function ordenarPor(col) {
    setOrden((o) =>
      o.col === col ? { col, dir: o.dir === 'asc' ? 'desc' : 'asc' } : { col, dir: col === 'fecha' || col === 'monto' ? 'desc' : 'asc' }
    )
  }
  function alternarColumna(id) {
    const nuevas = { ...columnas, [id]: !columnas[id] }
    setColumnas(nuevas)
    try {
      localStorage.setItem(LLAVE_COLUMNAS, JSON.stringify(nuevas))
    } catch {
      // no pasa nada: la elección vale mientras la pantalla esté abierta
    }
  }

  const todos = n > 0 && ordenados.every((m) => seleccionados.has(m.id))
  const visibles = COLUMNAS_TABLA.filter((c) => c.fija || columnas[c.id])
  const total = visibles.length + 1

  return (
    <div className="mx-5" data-testid="tabla-movimientos">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-ink-soft" aria-live="polite">
          {n} {n === 1 ? 'movimiento' : 'movimientos'}
        </p>
        <div className="relative">
          <button
            type="button"
            aria-expanded={menu}
            onClick={() => setMenu((v) => !v)}
            onKeyDown={(e) => e.key === 'Escape' && setMenu(false)}
            className="inline-flex items-center gap-1.5 text-sm text-ink-soft rounded-full border border-line px-3.5 min-h-[44px] hover:border-accent"
          >
            <Icono icono={Columns3} tam="sm" /> Columnas
          </button>
          {menu && (
            <div
              role="group"
              aria-label="Columnas visibles"
              onKeyDown={(e) => e.key === 'Escape' && setMenu(false)}
              className="absolute right-0 z-20 mt-1 w-48 rounded-2xl border border-line bg-paper-raised p-2 shadow-lg"
            >
              {COLUMNAS_TABLA.filter((c) => !c.fija).map((c) => (
                <label key={c.id} className="flex items-center gap-2 px-2 min-h-[44px] text-sm cursor-pointer">
                  <input type="checkbox" checked={!!columnas[c.id]} onChange={() => alternarColumna(c.id)} className="w-4 h-4 accent-[var(--color-accent)]" />
                  {c.titulo}
                </label>
              ))}
            </div>
          )}
        </div>
      </div>

      <div ref={raiz} className="rounded-2xl border border-line bg-paper overflow-clip">
        <table className="w-full border-collapse text-left" aria-label="Movimientos en tabla" aria-rowcount={n + 1}>
          <thead className="sticky top-0 z-10 bg-paper-raised">
            <tr className="border-b border-line" style={{ height: ALTO_FILA_TABLA }}>
              <th scope="col" className="w-11 pl-2">
                <Casilla marcada={todos} etiqueta="Seleccionar todos los movimientos" onClick={() => onToggleTodos(!todos)} />
              </th>
              {visibles.map((c) => {
                const activa = orden.col === c.id
                return (
                  <th
                    key={c.id}
                    scope="col"
                    aria-sort={activa ? (orden.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    className={`px-3 text-xs font-bold uppercase tracking-wide text-ink-soft ${c.id === 'monto' ? 'text-right pr-4' : ''}`}
                  >
                    <button
                      type="button"
                      onClick={() => ordenarPor(c.id)}
                      className={`inline-flex items-center gap-1 min-h-[44px] uppercase tracking-wide hover:text-ink ${activa ? 'text-ink' : ''}`}
                    >
                      {c.titulo}
                      <Icono icono={activa ? (orden.dir === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown} tam="sm" />
                    </button>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {ini > 0 && (
              <tr aria-hidden="true" style={{ height: ini * ALTO_FILA_TABLA }}>
                <td colSpan={total} />
              </tr>
            )}
            {ordenados.slice(ini, fin).map((m) => (
              <Fila
                key={m.id}
                m={m}
                columnas={columnas}
                icono={iconoDe(m.categoria)}
                moneda={monedaDe[m.cuenta_id]}
                cuenta={nombreCuenta(m.cuenta_id)}
                esSel={seleccionados.has(m.id)}
                activa={panelId === m.id}
                onToggle={onToggle}
                onAbrir={onAbrir}
                onChip={onChip}
              />
            ))}
            {fin < n && (
              <tr aria-hidden="true" style={{ height: (n - fin) * ALTO_FILA_TABLA }}>
                <td colSpan={total} />
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
