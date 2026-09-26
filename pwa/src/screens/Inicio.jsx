import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDownLeft, ArrowUpRight, ChevronRight, Wallet } from 'lucide-react'
import { formatCOP } from '../lib/format'
import { api } from '../lib/api'

export default function Inicio() {
  const [cuentas, setCuentas] = useState([])
  const [movimientos, setMovimientos] = useState([])
  const [reporte, setReporte] = useState(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    let activo = true
    Promise.all([api.cuentas(), api.movimientos(4), api.reporteMensual()])
      .then(([c, m, r]) => {
        if (!activo) return
        setCuentas(c)
        setMovimientos(m)
        setReporte(r)
      })
      .catch(() => {})
      .finally(() => activo && setCargando(false))
    return () => {
      activo = false
    }
  }, [])

  const saldoTotal = cuentas.reduce((s, c) => s + c.saldo, 0)

  if (cargando) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-ink-soft">Cargando...</p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6">
      <header className="px-6 pt-14 pb-2 flex items-center justify-between">
        <p className="text-lg font-bold">Hola, Daniel</p>
        <div className="w-10 h-10 rounded-full bg-paper-raised border border-line flex items-center justify-center">
          <Wallet size={18} className="text-ink-soft" />
        </div>
      </header>

      {/* Tarjeta de saldo */}
      <section className="px-6 mt-3">
        <div
          className="rounded-[28px] p-6 relative overflow-hidden"
          style={{ background: 'linear-gradient(135deg, var(--color-accent) 0%, color-mix(in srgb, var(--color-accent) 80%, black) 100%)' }}
        >
          <div
            className="absolute -right-10 -top-10 w-40 h-40 rounded-full"
            style={{ background: 'color-mix(in srgb, var(--color-accent-2) 25%, transparent)' }}
          />
          <div
            className="absolute -right-4 bottom-4 w-24 h-24 rounded-full"
            style={{ background: 'rgba(255,255,255,0.06)' }}
          />
          <p className="text-sm text-white/70 relative">Saldo total</p>
          <p className="text-4xl font-bold text-white mt-1 relative tracking-tight">
            {formatCOP(saldoTotal)}
          </p>
          {reporte && (
            <div className="flex items-center gap-4 mt-4 relative">
              <span className="flex items-center gap-1 text-sm font-medium text-white/90">
                <ArrowUpRight size={15} /> {formatCOP(reporte.ingresos)}
              </span>
              <span className="flex items-center gap-1 text-sm font-medium text-white/70">
                <ArrowDownLeft size={15} /> {formatCOP(reporte.gastos)}
              </span>
            </div>
          )}
        </div>

        {cuentas.length > 0 && (
          <div className="flex gap-3 mt-3">
            {cuentas.map((c) => (
              <div
                key={c.id}
                className="flex-1 rounded-2xl bg-paper-raised border border-line p-4 flex items-center gap-3"
              >
                <span className="text-xl">{c.icono}</span>
                <div className="min-w-0">
                  <p className="text-xs text-ink-soft truncate">{c.nombre}</p>
                  <p className="text-sm font-bold truncate">{formatCOP(c.saldo)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Salud financiera */}
      {reporte && (
        <section className="mx-6 mt-5 rounded-2xl bg-accent-soft p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-paper-raised flex items-center justify-center font-bold text-accent shrink-0">
            {Math.round(reporte.tasa_ahorro)}%
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-ink">
              {reporte.salud.score >= 70 ? 'Vas muy bien este mes' : 'Hay espacio para mejorar'}
            </p>
            <p className="text-xs text-ink-soft mt-0.5">{reporte.salud.tips[0]}</p>
          </div>
        </section>
      )}

      {/* Categorías */}
      {reporte && reporte.top_categorias.length > 0 && (
        <section className="mx-6 mt-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[15px] font-semibold">Gastos por categoría</h2>
          </div>
          <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line">
            {reporte.top_categorias.map((c) => (
              <div key={c.categoria} className="flex items-center gap-3 px-4 py-3.5">
                <div className="w-9 h-9 rounded-xl shrink-0 bg-accent" />
                <p className="flex-1 text-sm font-medium">{c.categoria}</p>
                <p className="text-sm font-semibold">{formatCOP(c.monto)}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Movimientos */}
      <section className="mx-6 mt-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[15px] font-semibold">Movimientos recientes</h2>
          <Link to="/movimientos" className="text-sm text-accent font-medium flex items-center">
            Ver todo <ChevronRight size={15} />
          </Link>
        </div>
        {movimientos.length === 0 ? (
          <div className="rounded-2xl bg-paper-raised border border-line p-6 text-center">
            <p className="text-sm text-ink-soft">Aún no tienes movimientos registrados</p>
          </div>
        ) : (
          <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden">
            {movimientos.map((m, i) => (
              <Link
                key={m.id}
                to={`/movimientos/${m.id}`}
                className={`flex items-center gap-3 px-4 py-3.5 ${i !== 0 ? 'border-t border-line' : ''}`}
              >
                <span className="w-10 h-10 rounded-full bg-accent-soft flex items-center justify-center text-lg shrink-0">
                  💳
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{m.descripcion}</p>
                  <p className="text-xs text-ink-soft">{m.categoria}</p>
                </div>
                <span className={`text-sm font-semibold shrink-0 ${m.tipo === 'income' ? 'text-accent' : 'text-ink'}`}>
                  {m.tipo === 'income' ? '+' : '-'}
                  {formatCOP(m.monto)}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
