import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeftRight, Bot, ChevronRight, CreditCard, Gift, Landmark, PieChart, PiggyBank, Repeat, Sparkles } from 'lucide-react'
import { CargandoMarca, IlustracionVacia, Isotipo, Monto, SelloCuadre } from '../brand/Marca'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import BotonOjo from '../components/BotonOjo'
import TarjetaSalud from '../components/TarjetaSalud'
import { useAuth } from '../lib/AuthContext'
import { useCategorias } from '../lib/CategoriasContext'
import MazoCuentas from '../components/MazoCuentas'
import ArbolFinanciero from '../components/ArbolFinanciero'
import CarruselDescubrir from '../components/CarruselDescubrir'
import { etapaPorScore } from '../lib/saludFinanciera'
import ResumenSaldo from '../components/ResumenSaldo'
import PreguntaMovimiento from '../components/PreguntaMovimiento'
import { textoActualizado } from '../lib/saldos'

// Patrimonio vive en "Más" dentro de la barra; aquí queda a un toque.
const ACCESOS_RAPIDOS = [
  { to: '/patrimonio', icon: Landmark, label: 'Patrimonio' },
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
  const [resumen, setResumen] = useState(null)
  const [gmailConectado, setGmailConectado] = useState(true)
  const [conexionFalla, setConexionFalla] = useState(false)
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
    // Desglose del saldo (disponible / tarjetas / por moneda y tipo). Si falla, el héroe sigue funcionando.
    Promise.resolve().then(() => api.resumenCuentas()).then((r) => activo && setResumen(r)).catch(() => {})
    api.gmailEstado().then((e) => activo && setGmailConectado(!!e.conectado)).catch(() => {})
    // Aviso solo si algo se rompió (semáforo rojo); si el tablero falla, no se muestra nada.
    Promise.resolve().then(() => api.conexionesEstado?.()).then((c) => activo && setConexionFalla(!!c?.hay_falla)).catch(() => {})
    return () => {
      activo = false
    }
  }, [intento])

  // La bandeja "por confirmar" avisa cuando confirma/edita/descarta algo: se recargan los datos.
  useEffect(() => {
    const recargar = () => setIntento((n) => n + 1)
    window.addEventListener('cuadrame:movimientos-cambio', recargar)
    return () => window.removeEventListener('cuadrame:movimientos-cambio', recargar)
  }, [])

  // El total viene convertido a COP desde el backend (cuentas en USD, etc.);
  // mientras llega, se suma solo lo que ya está en pesos para no mezclar monedas.
  const saldoTotal =
    bolsillo?.saldo_total ?? cuentas.filter((c) => (c.moneda || 'COP') === 'COP').reduce((s, c) => s + c.saldo, 0)

  if (cargando) {
    return <CargandoMarca />
  }

  // "Cuadrar" = lo que tienes alcanza para lo que ya comprometiste este mes
  // (gastos fijos pendientes + aportes a metas). La diferencia es lo que falta.
  const diferencia = bolsillo ? bolsillo.disponible_real : null
  const cuadra = diferencia === null ? null : diferencia >= 0

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Isotipo size={30} cuadra={cuadra !== false} />
          <p className="t-title text-lg">{primerNombre ? `Hola, ${primerNombre}` : 'Hola'}</p>
        </div>
        <BotonOjo />
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

      {conexionFalla && (
        <Link
          to="/conexiones"
          role="alert"
          data-testid="aviso-conexiones"
          className="mx-6 mt-2 rounded-2xl bg-danger-soft border border-danger/30 p-3 flex items-center justify-between gap-3"
        >
          <p className="text-xs text-danger">Una de tus conexiones está fallando.</p>
          <span className="text-xs font-semibold text-danger shrink-0">Ver estado</span>
        </Link>
      )}

      {/* Mazo de cuentas — cada tarjeta con el color real de su entidad, apiladas
          como en una billetera física, para que multi-cuenta se entienda de un vistazo */}
      {/* Héroe de marca: saldo total + el estado de cuadre del mes */}
      <section
        className="mx-6 mt-3 hero-marca card-marca relative overflow-hidden p-5 stagger-item"
        style={{ '--stagger-i': 0 }}
        aria-label="Estado de tus cuentas"
      >
        <Isotipo mono cuadra={cuadra !== false} size={150} className="absolute -right-6 -bottom-8 opacity-[0.1]" />
        <div className="relative">
          <p className="t-kicker">
            Saldo actual · {cuentas.length} {cuentas.length === 1 ? 'cuenta' : 'cuentas'}
          </p>
          <p className="text-[44px] t-display mt-2.5">
            <Monto texto={fmt(saldoTotal)} />
          </p>
          {resumen && (
            <p className="text-xs mt-1 opacity-85">
              En pesos, sumando todas tus cuentas · {textoActualizado(resumen.ultimo_movimiento)}
            </p>
          )}
          {resumen && !resumen.hay_movimientos && (
            <p className="mt-3 rounded-2xl bg-black/20 px-3.5 py-3 text-xs leading-relaxed" data-testid="guia-saldo">
              <b>¿Qué es el saldo?</b> Es la plata que tienes hoy en tus cuentas: la que ya pusiste al crearlas más
              lo que registres. Si no coincide con lo que ves en tu banco, toca «Ajustar saldo» y escribe el real.
            </p>
          )}
          <ResumenSaldo resumen={resumen} bolsillo={bolsillo} className="mt-3" />
          <div className="mt-3 flex gap-2">
            <Link to="/cuentas" className="flex-1 text-center rounded-full border border-current px-3 py-2 text-xs font-semibold">
              Ajustar saldo
            </Link>
            <Link to="/conciliacion" className="flex-1 text-center rounded-full border border-current px-3 py-2 text-xs font-semibold">
              Conciliar con mi banco
            </Link>
          </div>
          {bolsillo && (
            <div className="mt-4 flex items-start gap-3 rounded-2xl bg-black/20 px-3.5 py-3">
              {cuadra ? (
                <SelloCuadre size={26} />
              ) : (
                <span className="shrink-0 mt-0.5">
                  <Isotipo mono cuadra={false} size={26} />
                </span>
              )}
              <div className="min-w-0">
                <p className="text-sm font-bold leading-snug">
                  {cuadra ? 'Tus cuentas cuadran' : `Te faltan ${fmt(-diferencia)} por cuadrar`}
                </p>
                <p className="text-xs mt-0.5 leading-relaxed">
                  {cuadra
                    ? `Tras gastos fijos y metas de este mes te sobran ${fmt(diferencia)}.`
                    : 'Tus gastos fijos y metas de este mes superan lo que tienes en cuentas.'}
                </p>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Tras la bandeja de "por confirmar": una pregunta rápida si hoy no hay movimientos */}
      <PreguntaMovimiento ultimaFecha={movimientos[0]?.fecha} />

      <section className="px-6 mt-4 stagger-item" style={{ '--stagger-i': 1 }}>
        <MazoCuentas cuentas={cuentas} ultimos={resumen?.ultimo_por_cuenta} />
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
              className="flex flex-col items-center justify-center gap-1.5 card-marca-sm bg-paper-raised border border-line py-3 min-h-[60px]"
            >
              <Icon size={19} className="text-accent" />
              <span className="text-[11px] font-medium text-ink-soft">{label}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* Cuánto puedo gastar — un solo número principal, con el detalle como apoyo */}
      {bolsillo && (
        <section className="mx-6 mt-5 card-marca bg-paper-raised border border-line p-4 stagger-item" style={{ '--stagger-i': 3 }}>
          <p className="t-kicker text-ink-soft">Para gastar hoy</p>
          <p className={`text-[34px] t-display mt-1.5 ${bolsillo.disponible_real_por_dia < 0 ? 'text-danger' : 'text-ink'}`}>
            <Monto texto={fmt(bolsillo.disponible_real_por_dia)} />
          </p>
          <p className="text-xs text-ink-soft mt-1.5">Sin quedar mal el resto del mes</p>
          <div className="mt-3 pt-3 border-t border-line space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-ink-soft">Saldo actual en tus cuentas</span>
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
        <Link to="/ahorcado" className="block mx-6 mt-5 card-marca bg-accent-soft p-4 flex items-center gap-4 stagger-item" style={{ '--stagger-i': 4 }}>
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

      {/* Informe "En qué gasto": categorías, comercios y comparación por periodo */}
      <Link
        to="/informe"
        className="mx-6 mt-5 card-marca bg-paper-raised border border-line p-4 flex items-center gap-3 stagger-item"
        style={{ '--stagger-i': 4 }}
      >
        <span className="w-10 h-10 rounded-xl bg-accent-soft flex items-center justify-center shrink-0">
          <PieChart size={18} className="text-accent" />
        </span>
        <div className="flex-1">
          <p className="text-sm font-semibold">En qué gasto mi plata</p>
          <p className="text-xs text-ink-soft mt-0.5">Por categoría, comercios y periodo a tu medida</p>
        </div>
        <ChevronRight size={16} className="text-ink-soft shrink-0" />
      </Link>

      {/* CuadraMe AI: entrada al asistente (registra por texto, simula compras, arma planes) */}
      <Link
        to="/asistente"
        className="mx-6 mt-5 card-marca bg-accent-soft border border-accent/20 p-4 flex items-center gap-3 stagger-item"
        style={{ '--stagger-i': 4 }}
      >
        <span className="w-10 h-10 rounded-xl bg-paper-raised flex items-center justify-center shrink-0">
          <Bot size={18} className="text-accent" />
        </span>
        <div className="flex-1">
          <p className="text-sm font-semibold">Pregúntale a CuadraMe AI</p>
          <p className="text-xs text-ink-soft mt-0.5">«¿Puedo comprar un celular?» · «Gasté 18.000 en almuerzo»</p>
        </div>
        <ChevronRight size={16} className="text-ink-soft shrink-0" />
      </Link>

      {/* Puntaje de salud financiera (0-100) con desglose y consejos */}
      <TarjetaSalud />

      {/* Resumen mensual compartible */}
      <Link
        to="/resumen"
        className="mx-6 mt-3 card-marca bg-paper-raised border border-line p-4 flex items-center gap-3 stagger-item"
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
            <Link to="/informe" className="text-sm text-accent font-medium flex items-center">
              Ver informe <ChevronRight size={15} />
            </Link>
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
          <div className="card-marca bg-paper-raised border border-line p-6 text-center">
            <IlustracionVacia icono={ArrowLeftRight} size={92} />
            <p className="text-sm font-semibold mt-3">Aún no tienes movimientos registrados</p>
            <p className="text-xs text-ink-soft mt-1">Registra el primero con el botón + y empieza a cuadrar.</p>
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
