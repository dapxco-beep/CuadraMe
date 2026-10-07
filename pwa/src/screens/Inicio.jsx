import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeftRight, Bot, ChevronRight, CreditCard, Gift, HeartPulse, Landmark, LayoutGrid, Lightbulb, ListChecks, PieChart,
  PiggyBank, Plus, RefreshCw, Repeat, Sparkles, Wallet,
} from 'lucide-react'
import { IlustracionVacia, Isotipo, Monto, SelloCuadre } from '../brand/Marca'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import BotonOjo from '../components/BotonOjo'
import TarjetaSalud from '../components/TarjetaSalud'
import { useAuth } from '../lib/AuthContext'
import { useCategorias } from '../lib/CategoriasContext'
import MazoCuentas from '../components/MazoCuentas'
import ArbolFinanciero from '../components/ArbolFinanciero'
import CarruselDescubrir from '../components/CarruselDescubrir'
import AsistentePrimerUso from '../components/AsistentePrimerUso'
import { etapaPorScore } from '../lib/saludFinanciera'
import ResumenSaldo from '../components/ResumenSaldo'
import PreguntaMovimiento from '../components/PreguntaMovimiento'
import SeccionPlegable from '../components/SeccionPlegable'
import Sparkline, { resumenTendencia } from '../components/Sparkline'
import Icono from '../components/Icono'
import { Boton } from '../components/ui'
import { Bloque, EsqueletoFila } from '../components/Esqueletos'
import { textoActualizado } from '../lib/saldos'

// Patrimonio y el resto de pantallas viven en «Más»; aquí quedan a un toque los más usados.
const ACCESOS_RAPIDOS = [
  { to: '/patrimonio', icon: Landmark, label: 'Patrimonio' },
  { to: '/metas', icon: PiggyBank, label: 'Metas' },
  { to: '/deudas', icon: CreditCard, label: 'Deudas' },
  { to: '/recurrentes', icon: Repeat, label: 'Recurrentes' },
  { to: '/insights', icon: Sparkles, label: 'Insights' },
]

// Fila de enlace dentro de una sección: ícono + título + apoyo + flecha
function FilaEnlace({ to, icono, titulo, apoyo, testId }) {
  return (
    <Link to={to} data-testid={testId} className="flex items-center gap-3 py-3 min-h-[56px]">
      <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
        <Icono icono={icono} tam="md" />
      </span>
      <span className="flex-1 min-w-0">
        <span className="block t-cuerpo font-semibold">{titulo}</span>
        {apoyo && <span className="block t-apoyo">{apoyo}</span>}
      </span>
      <Icono icono={ChevronRight} tam="sm" className="text-ink-soft" />
    </Link>
  )
}

// Esqueleto con la misma estructura que el Inicio real (héroe + acciones + lista de secciones)
// para que al llegar los datos no se mueva nada.
function EsqueletoInicio() {
  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter pantalla-ancha" role="status" aria-busy="true" aria-label="Cargando tu inicio">
      <div aria-hidden="true" className="px-6 pantalla-top pb-2 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Bloque className="w-[30px] h-[30px]" />
          <Bloque className="h-5 w-32" />
        </div>
        <Bloque className="w-10 h-10 rounded-full!" />
      </div>
      <div aria-hidden="true" className="dos-col">
        <div className="col">
          <div className="mx-6 mt-3">
            <Bloque className="w-full" style={{ height: 216, borderRadius: '18px 30px 18px 18px' }} />
          </div>
          <div className="mx-6 mt-3 grid grid-cols-2 gap-3">
            <Bloque className="h-11 rounded-full!" />
            <Bloque className="h-11 rounded-full!" />
          </div>
        </div>
        <div className="col">
          <div className="mx-6 mt-4 tarjeta-lista">
            {Array.from({ length: 6 }, (_, i) => (
              <EsqueletoFila key={i} className="h-14" />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

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
  const [tendencia, setTendencia] = useState(null)
  const [gmailConectado, setGmailConectado] = useState(true)
  const [conexionFalla, setConexionFalla] = useState(false)
  const [tareasSync, setTareasSync] = useState(null)
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
    // Cuántas cosas esperan en «Traer movimientos» (si falla, el acceso se muestra sin número).
    Promise.resolve().then(() => api.sincronizacionEstado?.()).then((s) => activo && setTareasSync(s?.tareas?.length ?? null)).catch(() => {})
    // Tendencia del gasto de los últimos meses para la mini gráfica (opcional: sin datos no se dibuja).
    Promise.resolve().then(() => api.tendencias?.(6)).then((t) => activo && setTendencia(t?.meses ?? null)).catch(() => {})
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
    return <EsqueletoInicio />
  }

  // "Cuadrar" = lo que tienes alcanza para lo que ya comprometiste este mes
  // (gastos fijos pendientes + aportes a metas). La diferencia es lo que falta.
  const diferencia = bolsillo ? bolsillo.disponible_real : null
  const cuadra = diferencia === null ? null : diferencia >= 0
  const gastarHoy = bolsillo ? bolsillo.disponible_real_por_dia : null
  const hayPorResolver = (tareasSync || 0) > 0 || conexionFalla

  const gastosMensuales = (tendencia || []).map((m) => Number(m.gastos)).filter((v) => Number.isFinite(v))
  const hayTendencia = gastosMensuales.length >= 2 && gastosMensuales.some((v) => v > 0)
  const textoTendencia = hayTendencia ? resumenTendencia(gastosMensuales, fmt) : ''

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter pantalla-ancha">
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

      {/* Primeros pasos: solo mientras falte algo (y no se haya ocultado); luego vive en Perfil */}
      <AsistentePrimerUso variante="inicio" />

      {/* ≥1024 px: dos columnas (lo principal | el resto plegado). En teléfono los wrappers
          no existen visualmente y el orden es: héroe, dos acciones, secciones. */}
      <div className="dos-col">
        <div className="col">
          {/* BLOQUE 1 — protagonista: cuánto puedes gastar hoy + estado de cuadre + saldo total */}
          <section
            className="mx-6 mt-3 hero-marca card-marca relative overflow-hidden p-5 min-h-[216px] stagger-item"
            style={{ '--stagger-i': 0 }}
            aria-label="Cuánto puedes gastar hoy"
          >
            <Isotipo mono cuadra={cuadra !== false} size={150} className="absolute -right-6 -bottom-8 opacity-[0.1]" />
            <div className="relative">
              <p className="t-kicker">{gastarHoy !== null ? 'Puedes gastar hoy' : 'Saldo actual'}</p>
              <p className="text-[44px] t-display mt-2.5">
                <Monto texto={fmt(gastarHoy !== null ? gastarHoy : saldoTotal)} />
              </p>
              {gastarHoy !== null && <p className="text-xs mt-1.5 opacity-90">Sin quedar mal el resto del mes</p>}

              {bolsillo && (
                <div className="mt-4 flex items-start gap-3">
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
                    <p className="text-xs mt-0.5 leading-relaxed opacity-90">
                      {cuadra
                        ? `Tras gastos fijos y metas de este mes te sobran ${fmt(diferencia)}.`
                        : 'Tus gastos fijos y metas de este mes superan lo que tienes en cuentas.'}
                    </p>
                  </div>
                </div>
              )}

              {resumen && !resumen.hay_movimientos && (
                <p className="mt-3 rounded-2xl bg-black/20 px-3.5 py-3 text-xs leading-relaxed" data-testid="guia-saldo">
                  <b>¿Qué es el saldo?</b> Es la plata que tienes hoy en tus cuentas: la que ya pusiste al crearlas más
                  lo que registres. Si no coincide con lo que ves en tu banco, entra a «Cuentas» y toca «Ajustar saldo».
                </p>
              )}

              <div className="mt-4 pt-3 border-t border-white/20 flex items-end justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[11px] opacity-90">
                    Saldo total · {cuentas.length} {cuentas.length === 1 ? 'cuenta' : 'cuentas'}
                  </p>
                  <p className="text-lg font-bold t-cifra mt-0.5">{fmt(saldoTotal)}</p>
                  {resumen && <p className="text-[11px] opacity-90 mt-0.5">{textoActualizado(resumen.ultimo_movimiento)}</p>}
                </div>
                {hayTendencia && (
                  <figure className="m-0 shrink-0 text-right" data-testid="tendencia-gasto">
                    <Sparkline valores={gastosMensuales} resumen={textoTendencia} className="ml-auto" />
                    <figcaption className="text-[11px] opacity-90 mt-0.5">Tu gasto mensual</figcaption>
                  </figure>
                )}
              </div>
            </div>
            {hayTendencia && <p className="sr-only">{textoTendencia}</p>}
          </section>

          {/* BLOQUE 2 — las dos acciones principales */}
          <div className="mx-6 mt-3 grid grid-cols-2 gap-2.5 stagger-item" style={{ '--stagger-i': 1 }}>
            <Boton to="/agregar" icono={Plus} className="btn-compacto">
              Agregar movimiento
            </Boton>
            <Boton to="/sincronizacion" variante="secundario" icono={RefreshCw} className="btn-compacto" data-testid="acceso-sincronizacion">
              Traer movimientos
              {tareasSync > 0 && (
                <span className="ml-0.5 min-w-5 h-5 px-1.5 rounded-full bg-accent text-paper-raised text-[11px] font-bold flex items-center justify-center t-cifra">
                  <span className="sr-only">{tareasSync} por resolver</span>
                  <span aria-hidden="true">{tareasSync}</span>
                </span>
              )}
            </Boton>
          </div>

          {/* Pregunta rápida si hoy no hay movimientos (sale tras la bandeja de «por confirmar») */}
          <PreguntaMovimiento ultimaFecha={movimientos[0]?.fecha} />
        </div>

        <div className="col">
          {/* BLOQUE 3 — todo lo demás, plegado y ordenado por importancia (cada sección recuerda su estado) */}
          <div className="mx-6 mt-4 tarjeta-lista stagger-item" style={{ '--stagger-i': 2 }}>
            <SeccionPlegable
              id="cuentas"
              titulo="Cuentas"
              icono={Wallet}
              resumen={`${cuentas.length} ${cuentas.length === 1 ? 'cuenta' : 'cuentas'}`}
            >
              <MazoCuentas cuentas={cuentas} ultimos={resumen?.ultimo_por_cuenta} />
              <ResumenSaldo resumen={resumen} bolsillo={bolsillo} className="mt-3" />
              <div className="mt-3 flex gap-2">
                <Boton to="/cuentas" variante="secundario" tam="sm" className="flex-1">
                  Ajustar saldo
                </Boton>
                <Boton to="/conciliacion" variante="secundario" tam="sm" className="flex-1">
                  Conciliar con mi banco
                </Boton>
              </div>
            </SeccionPlegable>

            <SeccionPlegable
              id="movimientos"
              abiertaPorDefecto={movimientos.length === 0} // sin movimientos, la invitación a registrar el primero va a la vista
              titulo="Movimientos recientes"
              icono={ArrowLeftRight}
              resumen={movimientos.length ? '' : 'Sin movimientos'}
            >
              {movimientos.length === 0 ? (
                <div className="py-4 text-center">
                  <IlustracionVacia icono={ArrowLeftRight} size={92} />
                  <p className="t-cuerpo font-semibold mt-3">Aún no tienes movimientos registrados</p>
                  <p className="t-apoyo mt-1">Registra el primero con el botón + y empieza a cuadrar.</p>
                </div>
              ) : (
                <div className="divide-y divide-line">
                  {movimientos.map((m) => (
                    <Link key={m.id} to={`/movimientos/${m.id}`} className="flex items-center gap-3 py-3 min-h-[56px]">
                      <span className="w-10 h-10 rounded-full bg-accent-soft flex items-center justify-center text-lg shrink-0 text-accent" aria-hidden="true">
                        {m.tipo === 'transfer' ? <Icono icono={ArrowLeftRight} tam="md" /> : iconoDe(m.categoria)}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="t-cuerpo font-medium truncate">{m.descripcion}</p>
                        <p className="t-apoyo">{m.categoria}</p>
                      </div>
                      <span className={`t-cuerpo font-semibold t-cifra shrink-0 ${m.tipo === 'income' ? 'text-accent' : 'text-ink'}`}>
                        {m.tipo === 'income' ? '+' : m.tipo === 'expense' ? '-' : ''}
                        {fmt(m.monto)}
                      </span>
                    </Link>
                  ))}
                </div>
              )}
              <Link to="/movimientos" className="mt-2 flex items-center justify-center gap-1 text-sm text-accent font-semibold py-2">
                Ver todo <Icono icono={ChevronRight} tam="sm" />
              </Link>
            </SeccionPlegable>

            <SeccionPlegable
              id="resolver"
              titulo="Por resolver"
              icono={ListChecks}
              aviso={hayPorResolver}
              abiertaPorDefecto={false}
              resumen={tareasSync === null ? '' : tareasSync === 0 && !conexionFalla ? 'Todo al día' : `${tareasSync || 0} por resolver`}
            >
              <div className="divide-y divide-line">
                <FilaEnlace
                  to="/sincronizacion"
                  icono={RefreshCw}
                  titulo="Traer movimientos"
                  apoyo={tareasSync === null ? 'Correos, extractos y archivos' : tareasSync === 0 ? 'Todo al día' : `${tareasSync} por resolver`}
                />
                {conexionFalla && <FilaEnlace to="/conexiones" icono={Sparkles} titulo="Una conexión está fallando" apoyo="Ver el estado de tus conexiones" />}
              </div>
            </SeccionPlegable>

            <SeccionPlegable
              id="presupuesto"
              titulo="Presupuesto del mes"
              icono={PieChart}
              resumen={bolsillo ? `Disponible ${fmt(bolsillo.disponible_real)}` : ''}
            >
              {bolsillo && (
                <div className="space-y-1.5 pt-2">
                  <div className="flex items-center justify-between t-apoyo">
                    <span>Saldo actual en tus cuentas</span>
                    <span className="font-medium text-ink t-cifra">{fmt(bolsillo.saldo_total)}</span>
                  </div>
                  <div className="flex items-center justify-between t-apoyo">
                    <span>− Gastos fijos que faltan este mes</span>
                    <span className="font-medium text-ink t-cifra">{fmt(bolsillo.recurrentes_pendientes_mes)}</span>
                  </div>
                  <div className="flex items-center justify-between t-apoyo">
                    <span>− Lo que aparto para tus metas</span>
                    <span className="font-medium text-ink t-cifra">{fmt(bolsillo.aportes_comprometidos_mes)}</span>
                  </div>
                  <div className="flex items-center justify-between t-cuerpo pt-1.5 border-t border-line">
                    <span className="font-semibold">= Disponible real este mes</span>
                    <span className={`font-bold t-cifra ${bolsillo.disponible_real < 0 ? 'text-danger' : 'text-ink'}`}>
                      {fmt(bolsillo.disponible_real)}
                    </span>
                  </div>
                </div>
              )}
              {disponible && disponible.categorias?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-line">
                  <p className="t-apoyo">Además, dentro de tus presupuestos por categoría te quedan</p>
                  <p className={`text-xl font-bold mt-0.5 t-cifra ${disponible.disponible_total_hoy < 0 ? 'text-danger' : 'text-ink'}`}>
                    {fmt(disponible.disponible_total_hoy)}/día
                  </p>
                  <p className="t-apoyo mt-1">
                    {fmt(disponible.disponible_total_mes)} disponibles para los {disponible.dias_restantes_mes} días restantes del mes — un límite aparte, más estricto que el número de arriba
                  </p>
                </div>
              )}
              {reporte && reporte.top_categorias.length > 0 && (
                <div className="mt-3 pt-3 border-t border-line">
                  <p className="t-h2 mb-1">Gastos por categoría</p>
                  <div className="divide-y divide-line">
                    {reporte.top_categorias.map((c) => (
                      <div key={c.categoria} className="flex items-center gap-3 py-2.5">
                        <span className="w-9 h-9 rounded-xl shrink-0 bg-accent-soft flex items-center justify-center text-lg" aria-hidden="true">
                          {iconoDe(c.categoria)}
                        </span>
                        <p className="flex-1 t-cuerpo font-medium">{c.categoria}</p>
                        <p className="t-cuerpo font-semibold t-cifra">{fmt(c.monto)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className="mt-2 flex items-center justify-between">
                <Link to="/presupuesto" className="text-sm text-accent font-semibold flex items-center py-2">
                  Ver presupuesto <Icono icono={ChevronRight} tam="sm" />
                </Link>
                <Link to="/informe" className="text-sm text-accent font-semibold flex items-center py-2">
                  Ver informe <Icono icono={ChevronRight} tam="sm" />
                </Link>
              </div>
            </SeccionPlegable>

            <SeccionPlegable
              id="salud"
              titulo="Salud financiera"
              icono={HeartPulse}
              resumen={reporte ? `${reporte.salud.score}/100` : ''}
            >
              {reporte && (
                <Link to="/ahorcado" className="flex items-center gap-4 py-2">
                  <div className="w-14 h-14 shrink-0">
                    <ArbolFinanciero etapa={etapaPorScore(reporte.salud.score)} />
                  </div>
                  <div className="flex-1">
                    <p className="t-cuerpo font-semibold">{reporte.salud.score >= 70 ? 'Vas muy bien este mes' : 'Hay espacio para mejorar'}</p>
                    <p className="t-apoyo mt-0.5">{reporte.salud.tips[0]}</p>
                  </div>
                  <Icono icono={ChevronRight} tam="sm" className="text-ink-soft" />
                </Link>
              )}
              {/* Puntaje de salud financiera (0-100) con desglose y consejos */}
              <TarjetaSalud embebida />
            </SeccionPlegable>

            <SeccionPlegable id="accesos" titulo="Accesos" icono={LayoutGrid}>
              <div className="grid grid-cols-5 gap-2 pt-2">
                {ACCESOS_RAPIDOS.map(({ to, icon, label }) => (
                  <Link
                    key={to}
                    to={to}
                    className="flex flex-col items-center justify-center gap-1.5 card-marca-sm bg-paper border border-line py-3 min-h-[60px]"
                  >
                    <Icono icono={icon} tam="md" className="text-accent" />
                    <span className="text-[11px] font-medium text-ink-soft">{label}</span>
                  </Link>
                ))}
              </div>
              <div className="divide-y divide-line mt-2">
                <FilaEnlace to="/informe" icono={PieChart} titulo="En qué gasto mi plata" apoyo="Por categoría, comercios y periodo a tu medida" />
                <FilaEnlace to="/asistente" icono={Bot} titulo="Pregúntale a CuadraMe AI" apoyo="«¿Puedo comprar un celular?» · «Gasté 18.000 en almuerzo»" />
                <FilaEnlace to="/resumen" icono={Gift} titulo="Tu resumen del mes" apoyo="Míralo en diapositivas y compártelo" />
              </div>
            </SeccionPlegable>

            <SeccionPlegable id="recomendaciones" titulo="Recomendaciones" icono={Lightbulb}>
              {/* Funciones por descubrir: mismo patrón que la alerta de Gmail, rotando varias */}
              <CarruselDescubrir gmailConectado={gmailConectado} cuentasCount={cuentas.length} embebida />
            </SeccionPlegable>
          </div>
        </div>
      </div>
    </div>
  )
}
