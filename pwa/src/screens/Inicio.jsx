import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, CreditCard, Gift, Mail, PiggyBank, Repeat, Sparkles, Wallet } from 'lucide-react'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import BotonOjo from '../components/BotonOjo'
import TarjetaSalud from '../components/TarjetaSalud'
import { useAuth } from '../lib/AuthContext'
import { useCategorias } from '../lib/CategoriasContext'
import TarjetaCuenta from '../components/TarjetaCuenta'
import ArbolFinanciero from '../components/ArbolFinanciero'
import CarruselDescubrir from '../components/CarruselDescubrir'
import { etapaPorScore } from '../lib/saludFinanciera'

const ACCESOS_RAPIDOS = [
  { to: '/metas', icon: PiggyBank, label: 'Metas' },
  { to: '/deudas', icon: CreditCard, label: 'Deudas' },
  { to: '/recurrentes', icon: Repeat, label: 'Recurrentes' },
  { to: '/insights', icon: Sparkles, label: 'Insights' },
]

export default function Inicio() {
  const { usuario } = useAuth()
  const { iconoDe } = useCategorias()
  const { fmt } = useBloqueo()
  const primerNombre = (usuario?.nombre || '').trim().split(/\s+/)[0]
  const [cuentas, setCuentas] = useState([])
  const [movimientos, setMovimientos] = useState([])
  const [reporte, setReporte] = useState(null)
  const [disponible, setDisponible] = useState(null)
  const [bolsillo, setBolsillo] = useState(null)
  const [gmailConectado, setGmailConectado] = useState(true)
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState('')
  const [intento, setIntento] = useState(0)

  useEffect(() => {
    let activo = true
    Promise.all([api.cuentas(), api.movimientos(4), api.reporteMensual()])
      .then(([c, m, r]) => {
        if (!activo) return
        setErrorCarga('')
        setCuentas(c)
        setMovimientos(m)
        setReporte(r)
      })
      .catch((err) => activo && setErrorCarga(err.message || 'No se pudo cargar tu información'))
      .finally(() => activo && setCargando(false))
    api.disponibleHoy().then((d) => activo && setDisponible(d)).catch(() => {})
    api.enMiBolsillo().then((b) => activo && setBolsillo(b)).catch(() => {})
    api.gmailEstado().then((e) => activo && setGmailConectado(!!e.conectado)).catch(() => {})
    return () => {
      activo = false
    }
  }, [intento])

  // El total viene convertido a COP desde el backend (cuentas en USD, etc.);
  // mientras llega, se suma solo lo que ya está en pesos para no mezclar monedas.
  const saldoTotal =
    bolsillo?.saldo_total ?? cuentas.filter((c) => (c.moneda || 'COP') === 'COP').reduce((s, c) => s + c.saldo, 0)

  if (cargando) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-ink-soft">Cargando...</p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pt-14 pb-2 flex items-center justify-between">
        <p className="text-lg font-bold">{primerNombre ? `Hola, ${primerNombre}` : 'Hola'}</p>
        <div className="flex items-center gap-2">
          <BotonOjo />
          <div className="w-10 h-10 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-hidden="true">
            <Wallet size={18} className="text-ink-soft" />
          </div>
        </div>
      </header>

      {errorCarga && (
        <div role="alert" className="mx-6 mt-2 rounded-2xl bg-danger-soft border border-danger/30 p-3 flex items-center justify-between gap-3">
          <p className="text-xs text-danger">{errorCarga}</p>
          <button
            onClick={() => {
              setCargando(true)
              setIntento((n) => n + 1)
            }}
            className="text-xs font-semibold text-danger shrink-0"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Mazo de cuentas — cada tarjeta con el color real de su entidad, apiladas
          como en una billetera física, para que multi-cuenta se entienda de un vistazo */}
      <section className="px-6 mt-3 stagger-item" style={{ '--stagger-i': 0 }}>
        <div className="flex items-baseline justify-between mb-2">
          <p className="text-xs text-ink-soft">Saldo total</p>
          <p className="text-xs text-ink-soft">{cuentas.length} {cuentas.length === 1 ? 'cuenta' : 'cuentas'}</p>
        </div>
        <p className="text-4xl font-extrabold tracking-tight mb-3">{fmt(saldoTotal)}</p>

        {cuentas.length > 0 && (
          <Link to="/cuentas" className="relative block" style={{ height: `${88 + (cuentas.length - 1) * 18}px` }}>
            {cuentas.map((c, i) => (
              <TarjetaCuenta
                key={c.id}
                cuenta={c}
                className="absolute inset-x-0"
                style={{
                  top: `${i * 18}px`,
                  zIndex: cuentas.length - i,
                  width: `${100 - i * 6}%`,
                }}
              />
            ))}
          </Link>
        )}
      </section>

      {/* Carrusel de funciones a descubrir — mismo patrón que la alerta de
          Gmail que ya funcionaba, pero rotando varias en vez de solo una */}
      {!cargando && (
        <CarruselDescubrir gmailConectado={gmailConectado} cuentasCount={cuentas.length} />
      )}

      {/* Accesos rápidos a funciones clave */}
      <section className="px-6 mt-4 stagger-item" style={{ '--stagger-i': 2 }}>
        <div className="grid grid-cols-5 gap-2">
          {ACCESOS_RAPIDOS.map(({ to, icon: Icon, label }) => (
            <Link
              key={to}
              to={to}
              className="flex flex-col items-center gap-1.5 rounded-2xl bg-paper-raised border border-line py-3"
            >
              <Icon size={18} className="text-accent" />
              <span className="text-[11px] font-medium text-ink-soft">{label}</span>
            </Link>
          ))}
          <Link
            to="/correos"
            className="flex flex-col items-center gap-1.5 rounded-2xl bg-paper-raised border border-line py-3"
          >
            <Mail size={18} className="text-accent" />
            <span className="text-[11px] font-medium text-ink-soft">Correos</span>
          </Link>
        </div>
      </section>

      {/* Cuánto puedo gastar — un solo número principal, con el detalle como apoyo */}
      {bolsillo && (
        <section className="mx-6 mt-5 rounded-2xl bg-paper-raised border border-line p-4 stagger-item" style={{ '--stagger-i': 3 }}>
          <p className="text-xs text-ink-soft">Puedes gastar hoy sin quedar mal el resto del mes</p>
          <p className={`text-3xl font-bold mt-0.5 ${bolsillo.disponible_real_por_dia < 0 ? 'text-danger' : 'text-ink'}`}>
            {fmt(bolsillo.disponible_real_por_dia)}
          </p>
          <div className="mt-3 pt-3 border-t border-line space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-ink-soft">Saldo en tus cuentas</span>
              <span className="font-medium">{fmt(bolsillo.saldo_total)}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-ink-soft">− Gastos fijos que faltan este mes</span>
              <span className="font-medium">{fmt(bolsillo.recurrentes_pendientes_mes)}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-ink-soft">− Lo que aparto para tus metas</span>
              <span className="font-medium">{fmt(bolsillo.aportes_comprometidos_mes)}</span>
            </div>
            <div className="flex items-center justify-between text-xs pt-1 border-t border-line">
              <span className="text-ink font-semibold">= Disponible real este mes</span>
              <span className={`font-bold ${bolsillo.disponible_real < 0 ? 'text-danger' : 'text-ink'}`}>
                {fmt(bolsillo.disponible_real)}
              </span>
            </div>
          </div>
        </section>
      )}

      {/* Disponible hoy por categoría (solo si tiene presupuestos configurados) */}
      {disponible && disponible.categorias?.length > 0 && (
        <section className="mx-6 mt-3 rounded-2xl bg-paper-raised border border-line p-4">
          <p className="text-xs text-ink-soft">
            Además, dentro de tus presupuestos por categoría te quedan
          </p>
          <p className={`text-xl font-bold mt-0.5 ${disponible.disponible_total_hoy < 0 ? 'text-danger' : 'text-ink'}`}>
            {fmt(disponible.disponible_total_hoy)}/día
          </p>
          <p className="text-xs text-ink-soft mt-1">
            {fmt(disponible.disponible_total_mes)} disponibles para los {disponible.dias_restantes_mes} días restantes del mes — esto es un límite aparte, más estricto que el número de arriba
          </p>
        </section>
      )}

      {/* Salud financiera — mini preview del árbol que crece con tus decisiones */}
      {reporte && (
        <Link to="/ahorcado" className="block mx-6 mt-5 rounded-2xl bg-accent-soft p-4 flex items-center gap-4 stagger-item" style={{ '--stagger-i': 4 }}>
          <div className="w-14 h-14 shrink-0 pop-in">
            <ArbolFinanciero etapa={etapaPorScore(reporte.salud.score)} />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-ink">
              {reporte.salud.score >= 70 ? 'Vas muy bien este mes' : 'Hay espacio para mejorar'}
            </p>
            <p className="text-xs text-ink-soft mt-0.5">{reporte.salud.tips[0]}</p>
          </div>
          <ChevronRight size={16} className="text-ink-soft shrink-0" />
        </Link>
      )}

      {/* Puntaje de salud financiera (0-100) con desglose y consejos */}
      <TarjetaSalud />

      {/* Resumen mensual compartible */}
      <Link
        to="/resumen"
        className="mx-6 mt-3 rounded-2xl bg-paper-raised border border-line p-4 flex items-center gap-3 stagger-item"
        style={{ '--stagger-i': 5 }}
      >
        <span className="w-10 h-10 rounded-xl bg-accent-soft flex items-center justify-center shrink-0">
          <Gift size={18} className="text-accent" />
        </span>
        <div className="flex-1">
          <p className="text-sm font-semibold">Tu resumen del mes</p>
          <p className="text-xs text-ink-soft mt-0.5">Míralo en diapositivas y compártelo</p>
        </div>
        <ChevronRight size={16} className="text-ink-soft shrink-0" />
      </Link>

      {/* Categorías */}
      {reporte && reporte.top_categorias.length > 0 && (
        <section className="mx-6 mt-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[15px] font-semibold">Gastos por categoría</h2>
          </div>
          <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line">
            {reporte.top_categorias.map((c) => (
              <div key={c.categoria} className="flex items-center gap-3 px-4 py-3.5">
                <span className="w-9 h-9 rounded-xl shrink-0 bg-accent-soft flex items-center justify-center text-lg" aria-hidden="true">
                  {iconoDe(c.categoria)}
                </span>
                <p className="flex-1 text-sm font-medium">{c.categoria}</p>
                <p className="text-sm font-semibold">{fmt(c.monto)}</p>
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
                className={`flex items-center gap-3 px-4 py-3.5 stagger-item ${i !== 0 ? 'border-t border-line' : ''}`}
                style={{ '--stagger-i': 5 + i }}
              >
                <span className="w-10 h-10 rounded-full bg-accent-soft flex items-center justify-center text-lg shrink-0" aria-hidden="true">
                  {m.tipo === 'transfer' ? '🔁' : iconoDe(m.categoria)}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{m.descripcion}</p>
                  <p className="text-xs text-ink-soft">{m.categoria}</p>
                </div>
                <span className={`text-sm font-semibold shrink-0 ${m.tipo === 'income' ? 'text-accent' : 'text-ink'}`}>
                  {m.tipo === 'income' ? '+' : m.tipo === 'expense' ? '-' : ''}
                  {fmt(m.monto)}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
