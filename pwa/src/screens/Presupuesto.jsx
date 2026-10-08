import { useEffect, useState } from 'react'
import { EsqueletoLista } from '../components/Esqueletos'
import { Link } from 'react-router-dom'
import { ArrowLeftRight, CalendarClock, ChevronRight, HandCoins, PieChart, Plus, SlidersHorizontal, TrendingUp, X } from 'lucide-react'
import { EstadoVacio } from '../brand/Marca'
import { formatCOP, formatPorcentaje } from '../lib/format'
import { api } from '../lib/api'
import GraficoTendencia from '../components/GraficoTendencia'
import { useCategorias } from '../lib/CategoriasContext'
import BarraProgreso from '../components/BarraProgreso'
import BarraProyeccion from '../components/BarraProyeccion'
import ConfigPlanificacion from '../components/ConfigPlanificacion'
import SugerenciaIngreso from '../components/SugerenciaIngreso'
import { PERIODOS, etiquetaPeriodo, textoRango } from '../lib/planificacion'
import Hoja from '../components/Hoja'
import Ayudita from '../components/Ayudita'

const MESES_CORTOS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

export default function Presupuesto() {
  const [presupuestos, setPresupuestos] = useState([])
  const [gastosPorCategoria, setGastosPorCategoria] = useState({})
  const [tendencias, setTendencias] = useState(null)
  const [flujoCaja, setFlujoCaja] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [mostrarMover, setMostrarMover] = useState(false)
  const [animarBarras, setAnimarBarras] = useState(false)
  const [proyecciones, setProyecciones] = useState({})
  const [configPlan, setConfigPlan] = useState(null)
  const [mostrarConfig, setMostrarConfig] = useState(false)
  const [mostrarIngreso, setMostrarIngreso] = useState(false)

  useEffect(() => {
    if (cargando) return
    const t = setTimeout(() => setAnimarBarras(true), 60)
    return () => clearTimeout(t)
  }, [cargando])

  useEffect(() => {
    cargar()
  }, [])

  async function cargar() {
    setCargando(true)
    try {
      const [ps, reporte, tend, flujo, proy] = await Promise.all([
        api.presupuestos(),
        api.reporteMensual(),
        api.tendencias(12), // 12 meses una sola vez; la gráfica recorta a 3/6/12 en el cliente
        api.flujoCajaFuturo(),
        // Si la proyección falla, la pantalla sigue funcionando como antes.
        api.proyeccionPresupuestos().catch(() => null),
      ])
      setPresupuestos(ps)
      const gastos = {}
      reporte.top_categorias.forEach((c) => {
        gastos[c.categoria] = c.monto
      })
      setGastosPorCategoria(gastos)
      setTendencias(tend)
      setFlujoCaja(flujo)
      const porId = {}
      ;(proy?.items || []).forEach((i) => {
        porId[i.presupuesto_id] = i
      })
      setProyecciones(porId)
      setConfigPlan(proy?.config || null)
    } catch {}
    setCargando(false)
  }

  async function eliminar(id) {
    await api.eliminarPresupuesto(id)
    cargar()
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter pantalla-ancha">
      <header className="px-6 pantalla-top pb-2 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Presupuesto</h1>
        <div className="flex items-center gap-2">
          {presupuestos.length > 1 && (
            <button
              onClick={() => setMostrarMover(true)}
              className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
              aria-label="Mover plata entre categorías"
            >
              <ArrowLeftRight size={20} className="text-ink-soft" />
            </button>
          )}
          <button
            onClick={() => setMostrarForm(true)}
            className="w-11 h-11 rounded-full bg-accent text-white flex items-center justify-center"
           aria-label="Nuevo presupuesto">
            <Plus size={20} />
          </button>
        </div>
      </header>

      {/* ≥1024 px: resumen/proyección a la izquierda, categorías a la derecha */}
      <div className="dos-col dos-col-6-5">
      <div className="col">
      <div className="px-6 pt-2 flex gap-2">
        <button
          onClick={() => setMostrarIngreso(true)}
          className="chip font-semibold"
        >
          <HandCoins size={16} className="text-accent" /> Repartir un ingreso
        </button>
        <button
          onClick={() => setMostrarConfig(true)}
          className="chip font-semibold"
        >
          <SlidersHorizontal size={16} className="text-ink-soft" /> Ajustes
        </button>
      </div>

      <Link
        to="/informe"
        className="mx-6 mt-4 card-marca bg-accent-soft border border-accent/20 p-3.5 flex items-center gap-3"
      >
        <span className="w-10 h-10 rounded-xl bg-paper-raised flex items-center justify-center shrink-0">
          <PieChart size={20} className="text-accent" />
        </span>
        <div className="flex-1">
          <p className="text-sm font-semibold">En qué gasto mi plata</p>
          <p className="text-xs text-ink-soft mt-0.5">Por categoría, comercios y comparación con el periodo anterior</p>
        </div>
        <ChevronRight size={16} className="text-ink-soft shrink-0" />
      </Link>

      {!cargando && tendencias && (
        <section className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp size={16} className="text-ink-soft" />
            <p className="text-sm font-semibold">Tendencia mensual</p>
          </div>
          <GraficoTendencia meses={tendencias.meses ?? []} />

          {tendencias.proyeccion && (
          <div className="mt-4 pt-4 border-t border-line">
            <p className="text-xs text-ink-soft">Proyección de gasto este mes <Ayudita termino="proyeccion" /></p>
            <p className="text-xl font-bold mt-0.5">
              {formatCOP(tendencias.proyeccion.gasto_proyectado_mes)}
            </p>
            <p className="text-xs text-ink-soft mt-0.5">
              Al ritmo de {formatCOP(tendencias.proyeccion.ritmo_diario)}/día, con{' '}
              {tendencias.proyeccion.dias_restantes_mes} días restantes
            </p>
          </div>
          )}
        </section>
      )}

      {!cargando && flujoCaja && flujoCaja.meses.length > 0 && (
        <section className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-4">
          <div className="flex items-center gap-2 mb-3">
            <CalendarClock size={16} className="text-ink-soft" />
            <p className="text-sm font-semibold">Proyección de saldo</p>
          </div>
          <div className="flex items-stretch gap-2">
            <div className="flex-1 min-w-0">
              <p className="text-xs text-ink-soft">Hoy</p>
              <p className="text-sm font-bold truncate">{formatCOP(flujoCaja.saldo_actual)}</p>
            </div>
            {flujoCaja.meses.map((m) => (
              <div key={m.mes} className="flex-1 min-w-0">
                <p className="text-xs text-ink-soft">{MESES_CORTOS[parseInt(m.mes.split('-')[1], 10) - 1]}</p>
                <p className={`text-sm font-bold truncate ${m.saldo_proyectado < 0 ? 'text-danger' : ''}`}>
                  {formatCOP(m.saldo_proyectado)}
                </p>
              </div>
            ))}
          </div>
          <p className="text-xs text-ink-soft mt-3">
            Estimado según tus recurrentes conocidos y tu ritmo de gasto habitual
          </p>
        </section>
      )}

      </div>
      <div className="col">
      {cargando ? (
        <EsqueletoLista filas={4} className="mx-5 mt-4" etiqueta="Cargando tu presupuesto" />
      ) : presupuestos.length === 0 ? (
        <EstadoVacio
          icono={TrendingUp}
          titulo="Aún no tienes presupuestos definidos"
          texto="Ponle un tope a una categoría y mira cómo va cuadrando el mes."
          className="mx-6 mt-6"
        >
          <button
            onClick={() => setMostrarForm(true)}
            className="mt-4 text-sm text-accent font-semibold min-h-[44px] px-3"
          >
            Crear el primero
          </button>
        </EstadoVacio>
      ) : (
        (() => {
          const conDatos = presupuestos.map((p) => {
            // Con proyección, el gasto y el límite son los de SU periodo (quincena,
            // semana...) e incluyen el sobrante arrastrado; sin ella, el mes de siempre.
            const proy = proyecciones[p.id]
            const gastado = proy ? proy.gastado : gastosPorCategoria[p.categoria] || 0
            const limiteEfectivo = proy ? proy.limite : p.limite + (p.sobre_ajuste || 0)
            const pctReal = (gastado / limiteEfectivo) * 100
            return { ...p, proy, gastado, limite: limiteEfectivo, pctReal, pct: Math.min(100, Math.round(pctReal)) }
          })
          const limiteTotal = conDatos.reduce((s, p) => s + p.limite, 0)
          const gastadoTotal = conDatos.reduce((s, p) => s + p.gastado, 0)
          const pctGeneral = limiteTotal > 0 ? Math.min(100, Math.round((gastadoTotal / limiteTotal) * 100)) : 0
          const colorNivel = pctGeneral >= 100 ? 'var(--color-danger)' : pctGeneral >= 80 ? 'var(--color-accent-2)' : 'var(--color-accent)'

          return (
            <div className="mx-6 mt-4 flex gap-4">
              {/* Termómetro: nivel general del mes de un vistazo */}
              <div className="flex flex-col items-center pt-1 shrink-0">
                <BarraProgreso
                  vertical
                  pct={animarBarras ? pctGeneral : 0}
                  color={colorNivel}
                  label="Uso general del presupuesto del mes"
                  className="w-8 rounded-full bg-line overflow-hidden relative flex items-end"
                  fillClass="rounded-full"
                  style={{ height: `${Math.max(180, conDatos.length * 76)}px` }}
                />
                <p className="text-[11px] text-ink-soft text-center mt-2.5 leading-tight font-medium">
                  {formatPorcentaje(pctGeneral)} del<br />mes usado
                </p>
              </div>

              {/* Categorías, cada una con su propia barra */}
              <div className="flex-1 min-w-0 space-y-3">
                {conDatos.map((p, i) => {
                  const sobrepasado = p.pctReal > 100
                  const cercaDelLimite = !sobrepasado && p.pct >= p.alerta_pct
                  return (
                    <div key={p.id} className="rounded-2xl bg-paper-raised border border-line p-4 stagger-item" style={{ '--stagger-i': i }}>
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-semibold">
                          {p.categoria}
                          {p.proy && p.proy.periodo !== 'monthly' && (
                            <span className="ml-1.5 text-[11px] font-bold text-ink-soft" data-testid="chip-periodo">
                              {etiquetaPeriodo(p.proy.periodo)} · {textoRango(p.proy.inicio, p.proy.fin)}
                            </span>
                          )}
                          {p.sobre_ajuste !== 0 && (
                            <span className={`ml-1.5 text-[11px] font-bold ${p.sobre_ajuste > 0 ? 'text-gold' : 'text-ink-soft'}`}>
                              {p.sobre_ajuste > 0 ? '+' : ''}{formatCOP(p.sobre_ajuste)}
                            </span>
                          )}
                        </p>
                        <div className="flex items-center gap-2">
                          <p className="text-xs text-ink-soft">
                            {formatCOP(p.gastado)} / {formatCOP(p.limite)}
                          </p>
                          <button onClick={() => eliminar(p.id)} className="w-11 h-11 -mr-1.5 flex items-center justify-center text-ink-soft shrink-0" aria-label="Cerrar">
                            <X size={16} />
                          </button>
                        </div>
                      </div>
                      {p.proy && p.proy.estado !== 'sin_limite' ? (
                        <BarraProyeccion item={p.proy} animar={animarBarras} />
                      ) : (
                        <BarraProgreso
                          pct={animarBarras ? p.pct : 0}
                          label={`Gastado en ${p.categoria}`}
                          texto={`${formatPorcentaje(p.pct)} del límite`}
                          color={
                            sobrepasado
                              ? 'var(--color-danger)'
                              : cercaDelLimite
                              ? 'var(--color-accent-2)'
                              : 'var(--color-accent)'
                          }
                        />
                      )}
                      {p.proy && p.proy.arrastre > 0 && (
                        <p className="text-[11px] text-gold mt-1.5">
                          Incluye {formatCOP(p.proy.arrastre)} que te sobraron del periodo anterior <Ayudita termino="sobrante" />
                        </p>
                      )}
                      {p.proy && p.proy.mensaje && (
                        <p
                          className={`text-xs mt-1.5 ${p.proy.estado === 'excedido' || p.proy.estado === 'en_riesgo' ? 'text-danger' : 'text-ink-soft'}`}
                          data-testid="mensaje-proyeccion"
                        >
                          {p.proy.mensaje}
                        </p>
                      )}
                      {!p.proy && sobrepasado && (
                        <p className="text-xs text-danger mt-1.5">
                          Te pasaste por {formatCOP(p.gastado - p.limite)} — ajusta el resto del mes para compensarlo
                        </p>
                      )}
                      {!p.proy && cercaDelLimite && (
                        <p className="text-xs text-ink-soft mt-1.5">
                          Te quedan {formatCOP(Math.max(0, p.limite - p.gastado))} para no pasarte este mes
                        </p>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })()
      )}
      </div>
      </div>

      {mostrarConfig && (
        <ConfigPlanificacion
          presupuestos={presupuestos}
          onClose={() => setMostrarConfig(false)}
          onGuardado={() => {
            setMostrarConfig(false)
            cargar()
          }}
        />
      )}

      {mostrarIngreso && <SugerenciaIngreso onClose={() => setMostrarIngreso(false)} onAplicado={cargar} />}

      {mostrarForm && (
        <FormPresupuesto
          periodoInicial={configPlan?.periodo_defecto || 'monthly'}
          onClose={() => setMostrarForm(false)}
          onGuardado={() => {
            setMostrarForm(false)
            cargar()
          }}
        />
      )}

      {mostrarMover && (
        <FormMoverSobre
          presupuestos={presupuestos}
          onClose={() => setMostrarMover(false)}
          onMovido={() => {
            setMostrarMover(false)
            cargar()
          }}
        />
      )}
    </div>
  )
}

function FormPresupuesto({ onClose, onGuardado, periodoInicial = 'monthly' }) {
  const { nombres } = useCategorias()
  const categoriasSugeridas = nombres.filter((c) => c !== 'Ingresos' && c !== 'Transferencias')
  const [categoria, setCategoria] = useState('')
  const [limite, setLimite] = useState('')
  const [periodo, setPeriodo] = useState(periodoInicial)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (!categoria) return setError('Elige una categoría')
    if (!limite || Number(limite) <= 0) return setError('Ingresa un límite válido')

    setGuardando(true)
    try {
      await api.crearPresupuesto({ categoria, limite: Number(limite), periodo })
      onGuardado()
    } catch (err) {
      setError(err.message || 'No se pudo guardar')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onClose}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Nuevo presupuesto</h2>
        <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>

      <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Categoría</p>
      <div className="grid grid-cols-3 gap-2 mb-4">
        {categoriasSugeridas.map((c) => (
          <button
            key={c}
            onClick={() => setCategoria(c)}
            className={`rounded-2xl border py-3 text-sm font-medium ${
              categoria === c ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Periodo</p>
      <div className="grid grid-cols-3 gap-2 mb-4">
        {PERIODOS.map((pe) => (
          <button
            key={pe.valor}
            onClick={() => setPeriodo(pe.valor)}
            className={`rounded-2xl border py-2.5 text-sm font-medium ${
              periodo === pe.valor ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
            }`}
          >
            {pe.etiqueta}
          </button>
        ))}
      </div>

      <p className="text-xs text-ink-soft mb-1">
        Pon un tope de gasto para esta categoría y te avisamos antes de pasarte. <Ayudita termino="limite-presupuesto" />
      </p>
      <input
        value={limite}
        onChange={(e) => setLimite(e.target.value.replace(/\D/g, ''))}
        inputMode="numeric"
        placeholder={`Límite ${etiquetaPeriodo(periodo).toLowerCase()} (ej. 500000)`}
        className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
      />

      {error && <p className="text-sm text-danger mb-3">{error}</p>}

      <button
        onClick={guardar}
        disabled={guardando}
        className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
      >
        {guardando ? 'Guardando...' : 'Guardar presupuesto'}
      </button>
    </Hoja>
  )
}

function FormMoverSobre({ presupuestos, onClose, onMovido }) {
  const [origenId, setOrigenId] = useState(presupuestos[0]?.id || '')
  const [destinoId, setDestinoId] = useState(presupuestos[1]?.id || '')
  const [monto, setMonto] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (origenId === destinoId) return setError('Elige dos categorías distintas')
    if (!monto || Number(monto) <= 0) return setError('Ingresa un monto válido')

    setGuardando(true)
    try {
      await api.moverSobre(origenId, destinoId, Number(monto))
      onMovido()
    } catch (err) {
      setError(err.message || 'No se pudo mover')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onClose}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Mover plata entre categorías</h2>
        <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>

      <p className="text-xs text-ink-soft mb-4">
        Lo que te sobró en una categoría lo puedes pasar a otra que se quedó corta,
        en vez de perderlo cada mes.
      </p>

      <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Desde</p>
      <select
        value={origenId}
        onChange={(e) => setOrigenId(e.target.value)}
        className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm mb-3"
      >
        {presupuestos.map((p) => (
          <option key={p.id} value={p.id}>{p.categoria}</option>
        ))}
      </select>

      <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Hacia</p>
      <select
        value={destinoId}
        onChange={(e) => setDestinoId(e.target.value)}
        className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm mb-3"
      >
        {presupuestos.map((p) => (
          <option key={p.id} value={p.id}>{p.categoria}</option>
        ))}
      </select>

      <input
        value={monto}
        onChange={(e) => setMonto(e.target.value.replace(/\D/g, ''))}
        inputMode="numeric"
        placeholder="Monto a mover"
        className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
      />

      {error && <p className="text-sm text-danger mb-3">{error}</p>}

      <button
        onClick={guardar}
        disabled={guardando}
        className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
      >
        {guardando ? 'Moviendo...' : 'Mover plata'}
      </button>
    </Hoja>
  )
}
