import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowDownLeft, ArrowLeftRight, ArrowUpRight, ChevronRight, Download } from 'lucide-react'
import Icono from './Icono'
import { cuentasEnNegativo } from '../lib/inicioSimple'

// Bloques prácticos del Inicio simple: por qué el disponible está en negativo, accesos rápidos y «Este mes».

const ACCIONES = [
  { texto: 'Gasto', icono: ArrowUpRight, ruta: '/agregar?foco=monto' },
  { texto: 'Ingreso', icono: ArrowDownLeft, ruta: '/agregar?tipo=income&foco=monto' },
  { texto: 'Pasar plata', icono: ArrowLeftRight, ruta: '/agregar?tipo=transfer' },
  { texto: 'Traer', icono: Download, ruta: '/sincronizacion' },
]

export function AccionesRapidas() {
  return (
    <nav className="mx-6 mt-3 grid grid-cols-4 gap-2" aria-label="Acciones rápidas" data-testid="acciones-rapidas">
      {ACCIONES.map((a) => (
        <Link
          key={a.texto}
          to={a.ruta}
          className="tarjeta min-h-[76px] flex flex-col items-center justify-start pt-2.5 gap-1 text-xs leading-tight text-center font-semibold text-ink active:scale-[0.97] transition-transform"
        >
          <span className="w-9 h-9 rounded-full bg-accent-soft text-accent flex items-center justify-center">
            <Icono icono={a.icono} tam="md" />
          </span>
          {a.texto}
        </Link>
      ))}
    </nav>
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
