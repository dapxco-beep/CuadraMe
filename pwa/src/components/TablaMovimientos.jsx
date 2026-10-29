import { memo, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowUp, ArrowUpDown, Check, Columns3 } from 'lucide-react'
import Icono from './Icono'
import { formatCOP, formatMoneda } from '../lib/format'
import { direccionDe, signoDe } from '../lib/traslados'
import { COLUMNAS_TABLA, ordenarMovimientos } from '../lib/movimientosLista'
import EtiquetaOrigen from './EtiquetaOrigen'
import { nombreDe, tieneNombrePropio } from '../lib/tituloMovimiento'
import { fechaHoraMovimiento } from '../lib/fechaMovimiento'

// Tabla de movimientos para escritorio. Mismas reglas que la lista: filas virtualizadas (alto fijo,
// solo se pintan las visibles más un margen), selección masiva con casillas y el detalle en el panel.
export const ALTO_FILA_TABLA = 48
// Anchos fijos (px). Descripción toma lo que sobra y no baja de MIN_DESCRIPCION; si no cabe todo, se ocultan Cuenta y luego Categoría.
const ANCHO = { casilla: 44, fecha: 200, categoria: 156, cuenta: 144, monto: 124 }
const MIN_DESCRIPCION = 160
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

const fechaCorta = (iso) => fechaHoraMovimiento(iso, { anio: true })

const Casilla = ({ marcada, etiqueta, onClick }) => (
  <button type="button" role="checkbox" aria-checked={marcada} aria-label={etiqueta} onClick={onClick} className="w-11 h-11 flex items-center justify-center">
    <span className={`w-5 h-5 rounded-md border-2 flex items-center justify-center ${marcada ? 'bg-accent border-accent' : 'border-line'}`}>
      {marcada && <Check size={16} className="text-paper-raised" aria-hidden="true" />}
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
      <td className="px-3 text-xs text-ink-soft truncate">{fechaCorta(m.fecha)}</td>
      <td className="px-3 overflow-hidden">
        <Link
          to={`/movimientos/${m.id}`}
          onClick={(e) => {
            e.preventDefault()
            onAbrir(m.id)
          }}
          title={m.titulo ? `${m.titulo} (banco: ${m.descripcion})` : m.descripcion} className="block truncate text-sm font-semibold py-2"
        >
          {nombreDe(m)}
          {tieneNombrePropio(m) && <span className="ml-2 text-[11px] font-normal text-ink-soft">Banco: {m.descripcion}</span>}
          <EtiquetaOrigen origen={m.origen} canales={m.canales} soloAvisos className="ml-2 align-middle" />
        </Link>
      </td>
      {columnas.categoria && (
        <td className="px-3 overflow-hidden">
          {esTransfer ? (
            <span className="block truncate text-xs text-ink-soft">{m.categoria}</span>
          ) : (
            <button
              type="button"
              onClick={() => onChip(m)}
              aria-label={`Cambiar categoría de ${m.descripcion}`}
              className="inline-flex items-center gap-1 max-w-full text-xs text-ink-soft rounded-full border border-line px-2.5 min-h-[32px] hover:border-accent hover:text-ink"
            >
              <span aria-hidden="true" className="shrink-0">{icono}</span>
              <span className="truncate">{m.categoria}{m.subcategoria ? ` · ${m.subcategoria}` : ''}</span>
            </button>
          )}
        </td>
      )}
      {columnas.cuenta && <td className="px-3 text-xs text-ink-soft truncate" title={cuenta}>{cuenta}</td>}
      <td className={`px-3 pr-4 text-right text-[15px] font-bold tabular-nums whitespace-nowrap ${dir === 'income' ? 'text-gold' : dir ? 'text-ink' : 'text-ink-soft'}`}>
        {signoDe(m)}
        {formatMoneda(m.monto, moneda)}
      </td>
    </tr>
  )
})

export default function TablaMovimientos({
  items, iconoDe, monedaDe, nombreCuenta, seleccionados, panelId, onToggle, onToggleTodos, onAbrir, onChip, totales = null, netoSeleccion = 0,
}) {
  const [orden, setOrden] = useState({ col: 'fecha', dir: 'desc' })
  const [columnas, setColumnas] = useState(() => ({
    categoria: true,
    // En pantallas medianas la tabla es angosta: la cuenta queda oculta hasta que se pida
    cuenta: typeof window === 'undefined' || window.innerWidth >= 1440,
    ...leerColumnas(),
  }))
  const [menu, setMenu] = useState(false)
  const [vista, setVista] = useState(0)
  const raiz = useRef(null)
  const [ancho, setAncho] = useState(0) // ancho real del recuadro (0 = aún no se sabe)
  useLayoutEffect(() => {
    const el = raiz.current
    if (!el) return undefined
    const medir = () => setAncho(Math.round(el.getBoundingClientRect().width))
    medir()
    if (typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(medir)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

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
  // Lo que cabe de verdad en el recuadro (no en la ventana): con zoom, ventana angosta o nombres largos, primero se
  // oculta Cuenta y luego Categoría; el Monto siempre se ve completo.
  const efectivas = { ...columnas }
  if (ancho > 0) {
    const cabe = (c) => ANCHO.casilla + ANCHO.fecha + ANCHO.monto + (c.categoria ? ANCHO.categoria : 0) + (c.cuenta ? ANCHO.cuenta : 0) + MIN_DESCRIPCION <= ancho
    if (!cabe(efectivas)) efectivas.cuenta = false
    if (!cabe(efectivas)) efectivas.categoria = false
  }
  const sinEspacio = (columnas.cuenta && !efectivas.cuenta) || (columnas.categoria && !efectivas.categoria)
  const visibles = COLUMNAS_TABLA.filter((c) => c.fija || efectivas[c.id])
  const total = visibles.length + 1

  return (
    <div className="mx-5" data-testid="tabla-movimientos">
      <div className="flex items-center justify-between mb-2">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-soft min-w-0" aria-live="polite" data-testid="tabla-totales">
          <span>
            {n} {n === 1 ? 'movimiento' : 'movimientos'}
          </span>
          {totales && n > 0 && (
            <>
              <span>
                Entró <b className="text-gold t-cifra">{formatCOP(totales.ingresos)}</b>
              </span>
              <span>
                Salió <b className="text-ink t-cifra">{formatCOP(totales.gastos)}</b>
              </span>
              <span>
                Neto{' '}
                <b className={`t-cifra ${totales.neto < 0 ? 'text-danger' : 'text-gold'}`}>
                  {totales.neto < 0 ? '-' : '+'}
                  {formatCOP(Math.abs(totales.neto))}
                </b>
              </span>
              {seleccionados.size > 0 && (
                <span data-testid="tabla-total-seleccion">
                  {seleccionados.size} {seleccionados.size === 1 ? 'seleccionado' : 'seleccionados'}:{' '}
                  <b className="text-ink t-cifra">
                    {netoSeleccion < 0 ? '-' : '+'}
                    {formatCOP(Math.abs(netoSeleccion))}
                  </b>
                </span>
              )}
            </>
          )}
        </div>
        <div className="relative flex items-center gap-3 shrink-0">
          {sinEspacio && (
            <span className="hidden xl:inline text-[11px] text-ink-soft" data-testid="tabla-sin-espacio">
              Sin espacio para todas las columnas
            </span>
          )}
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
        <table className="w-full table-fixed border-collapse text-left" aria-label="Movimientos en tabla" aria-rowcount={n + 1}>
          <colgroup>
            <col style={{ width: ANCHO.casilla }} />
            <col style={{ width: ANCHO.fecha }} />
            <col />
            {efectivas.categoria && <col style={{ width: ANCHO.categoria }} />}
            {efectivas.cuenta && <col style={{ width: ANCHO.cuenta }} />}
            <col style={{ width: ANCHO.monto }} />
          </colgroup>
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
                columnas={efectivas}
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
