import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, ChevronDown, ChevronRight, SlidersHorizontal } from 'lucide-react'
import Icono from './Icono'
import Hoja from './Hoja'
import { Boton } from './ui'
import { CATALOGO_ACCESOS, MAX_ACCESOS, useAccesosInicio } from '../lib/accesosInicio'
import { cuentasEnNegativo } from '../lib/inicioSimple'

// Bloques prácticos del Inicio simple: por qué el disponible está en negativo, accesos rápidos y «Este mes».

// Accesos del Inicio: por defecto dos filas (anotar, traer, dividir cuenta, metas, deudas, pagos fijos);
// «Personalizar» deja elegir cuáles y en qué orden (el orden es el de selección).
export function AccionesRapidas({ max = null, margen = 'mx-6 mt-3' }) {
  const { ids, accesos, guardar, restablecer } = useAccesosInicio()
  const [editando, setEditando] = useState(false)
  const [elegidos, setElegidos] = useState(ids)

  function abrir() {
    setElegidos(ids)
    setEditando(true)
  }
  function alternar(id) {
    setElegidos((previos) => (previos.includes(id) ? previos.filter((x) => x !== id) : previos.length < MAX_ACCESOS ? [...previos, id] : previos))
  }

  return (
    <>
      <nav className={`${margen} grid grid-cols-4 gap-2 lg:grid-cols-2 xl:grid-cols-4`} aria-label="Acciones rápidas" data-testid="acciones-rapidas">
        {(max ? accesos.slice(0, max) : accesos).map((a) => (
          <Link
            key={a.id}
            to={a.ruta}
            className="tarjeta min-h-[76px] flex flex-col items-center justify-start pt-2.5 gap-1 px-1 text-xs leading-tight text-center font-semibold text-ink active:scale-[0.97] transition-transform"
          >
            <span className="w-9 h-9 rounded-full bg-accent-soft text-accent flex items-center justify-center">
              <Icono icono={a.icono} tam="md" />
            </span>
            {a.texto}
          </Link>
        ))}
      </nav>
      {!max && <div className={`${margen.includes('mx-') ? 'mx-6' : ''} flex justify-end`}>
        <button type="button" onClick={abrir} data-testid="personalizar-accesos" className="min-h-11 inline-flex items-center gap-1.5 text-xs font-semibold text-accent">
          <Icono icono={SlidersHorizontal} tam="sm" /> Personalizar
        </button>
      </div>}
      {editando && (
        <Hoja onCerrar={() => setEditando(false)} titulo="Tus accesos del Inicio">
          {({ cerrar }) => (
            <div data-testid="hoja-accesos">
              <p className="t-apoyo">Toca para poner o quitar. Salen en el orden en que los eliges (hasta {MAX_ACCESOS}).</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {CATALOGO_ACCESOS.map((a) => {
                  const puesto = elegidos.indexOf(a.id)
                  return (
                    <button
                      key={a.id}
                      type="button"
                      aria-pressed={puesto >= 0}
                      onClick={() => alternar(a.id)}
                      className={`min-h-12 flex items-center gap-2 rounded-2xl border px-3 text-left text-sm font-medium ${puesto >= 0 ? 'border-accent bg-accent-soft text-ink' : 'border-line bg-paper text-ink-soft'}`}
                    >
                      <Icono icono={a.icono} tam="sm" className="text-accent shrink-0" />
                      <span className="flex-1 min-w-0">{a.texto}</span>
                      {puesto >= 0 && <span className="text-[11px] font-bold text-accent">{puesto + 1}</span>}
                    </button>
                  )
                })}
              </div>
              <div className="mt-4 flex gap-2">
                <Boton variante="secundario" onClick={() => { restablecer(); cerrar() }} className="flex-1">
                  Como estaba
                </Boton>
                <Boton onClick={() => { if (elegidos.length) guardar(elegidos); cerrar() }} className="flex-1">
                  Listo
                </Boton>
              </div>
            </div>
          )}
        </Hoja>
      )}
    </>
  )
}

// Solo aparece si el disponible es negativo: dice cuáles cuentas lo causan y qué suele ser.
export function AvisoNegativo({ saldo, cuentas, fmt }) {
  const negativas = cuentasEnNegativo(cuentas)
  if (!(saldo < 0) || negativas.length === 0) return null
  return (
    <section className="mx-6 mt-3 rounded-2xl bg-danger-soft border border-danger/30 p-4" role="note" data-testid="aviso-negativo">
      <div className="flex items-start gap-3">
        <Icono icono={AlertTriangle} tam="md" className="text-danger mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="t-cuerpo font-semibold">Tu disponible está en negativo</p>
          <p className="t-apoyo mt-0.5">
            {negativas.length === 1 ? 'Esta cuenta tiene' : 'Estas cuentas tienen'} el saldo por debajo de cero. Suele ser porque falta anotar un ingreso o
            el saldo inicial, o porque un movimiento quedó en la cuenta equivocada.
          </p>
          <ul className="mt-2 divide-y divide-danger/20">
            {negativas.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-3 py-1.5">
                <span className="t-cuerpo break-words min-w-0">{c.nombre}</span>
                <span className="t-cuerpo font-semibold t-cifra text-danger shrink-0">{fmt(c.saldo)}</span>
              </li>
            ))}
          </ul>
          <Link to="/cuentas" className="mt-2 min-h-11 inline-flex items-center gap-1 text-sm font-semibold text-accent">
            Revisar mis cuentas <Icono icono={ChevronRight} tam="sm" />
          </Link>
        </div>
      </div>
    </section>
  )
}

// Ingresos, gastos y neto del mes, más las categorías donde más se va la plata.
export function EsteMes({ reporte, fmt, iconoDe }) {
  if (!reporte) return null
  const ingresos = Number(reporte.ingresos) || 0
  const gastos = Number(reporte.gastos) || 0
  if (!ingresos && !gastos) return null
  const neto = ingresos - gastos
  // El monto de cada categoría viene en `monto` (se acepta `total` por si otra versión de la API lo manda así)
  const top = (reporte.top_categorias || [])
    .map((c) => ({ ...c, monto: Number(c.monto ?? c.total) || 0 }))
    .filter((c) => c.monto > 0)
    .slice(0, 3)
  const mayor = Math.max(...top.map((c) => Number(c.monto) || 0), 1)
  return (
    <section className="mx-6 mt-3 tarjeta p-4" aria-label="Este mes" data-testid="este-mes">
      <div className="flex items-center justify-between">
        <h2 className="t-h2">Este mes</h2>
        <Link to="/informe" className="min-h-11 flex items-center gap-1 text-sm font-semibold text-accent">
          Ver informe <Icono icono={ChevronRight} tam="sm" />
        </Link>
      </div>
      <div className="grid grid-cols-3 gap-2 mt-1">
        <div>
          <p className="text-[11px] text-ink-soft uppercase tracking-wide">Entró</p>
          <p className="t-cuerpo font-bold t-cifra text-gold">{fmt(ingresos)}</p>
        </div>
        <div>
          <p className="text-[11px] text-ink-soft uppercase tracking-wide">Salió</p>
          <p className="t-cuerpo font-bold t-cifra">{fmt(gastos)}</p>
        </div>
        <div>
          <p className="text-[11px] text-ink-soft uppercase tracking-wide">Neto</p>
          <p className={`t-cuerpo font-bold t-cifra ${neto < 0 ? 'text-danger' : 'text-gold'}`}>
            {neto < 0 ? '-' : '+'}
            {fmt(Math.abs(neto))}
          </p>
        </div>
      </div>
      {top.length > 0 && (
        <ul className="mt-3 pt-3 border-t border-line space-y-2.5" aria-label="Donde más gastas">
          {top.map((c) => (
            <li key={c.categoria}>
              <div className="flex items-center gap-2">
                <span aria-hidden="true" className="text-base">{iconoDe(c.categoria)}</span>
                <p className="t-cuerpo flex-1 min-w-0 break-words">{c.categoria}</p>
                <p className="t-cuerpo font-semibold t-cifra shrink-0">{fmt(c.monto)}</p>
              </div>
              <div className="h-1.5 rounded-full bg-line mt-1 overflow-hidden" aria-hidden="true">
                <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(4, ((Number(c.monto) || 0) / mayor) * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// Una carga principal falló: se dice en la misma tarjeta y se deja reintentar (nunca un hueco mudo).
// `enOscuro`: para usarlo sobre la tarjeta de color del saldo.
export function NoCargo({ onReintentar, className = '', enOscuro = false }) {
  return (
    <p role="status" data-testid="no-cargo" className={`${className} flex flex-wrap items-center gap-x-2 text-xs ${enOscuro ? 'opacity-95' : 'text-ink-soft'}`}>
      <span>No pudimos cargar esto</span>
      <span aria-hidden="true">·</span>
      <button type="button" onClick={onReintentar} className="min-h-11 font-semibold underline underline-offset-2">
        Reintentar
      </button>
    </p>
  )
}

// Avisos importantes: solo se ve el más importante (el primero de la lista); el resto queda tras «Ver más avisos».
// `items`: [{ id, nodo }] ya ordenados de más a menos importante.
export function AvisosPrioridad({ items = [] }) {
  const [abierto, setAbierto] = useState(false)
  if (!items.length) return null
  const [primero, ...resto] = items
  return (
    <div data-testid="avisos-prioridad">
      <div key={primero.id}>{primero.nodo}</div>
      {resto.length > 0 && (
        <div className="mx-6 mt-1">
          <button
            type="button"
            aria-expanded={abierto}
            onClick={() => setAbierto((v) => !v)}
            className="min-h-11 flex items-center gap-1 text-xs font-semibold text-accent"
          >
            {abierto ? 'Ver menos avisos' : `Ver más avisos (${resto.length})`}
            <Icono icono={ChevronDown} tam="sm" className={abierto ? 'rotate-180' : ''} />
          </button>
        </div>
      )}
      {abierto && resto.map((a) => <div key={a.id}>{a.nodo}</div>)}
    </div>
  )
}
