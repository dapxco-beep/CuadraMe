import { useEffect, useState } from 'react'
import { EsqueletoLista } from '../components/Esqueletos'
import { EstadoVacio } from '../brand/Marca'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Plus, Sparkles, X, Repeat } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP, formatVeces } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import Hoja from '../components/Hoja'
import InputMonto from '../components/InputMonto'
import { CampoTexto, CampoMonto } from '../components/ui'
import { useDialogos } from '../lib/DialogosContext'
import EnlacesRelacionados from '../components/EnlacesRelacionados'

const estadoColor = {
  pagado: 'text-accent',
  proximo: 'text-gold',
  vencido: 'text-danger',
  pendiente: 'text-ink-soft',
}

const estadoLabel = {
  pagado: 'Pagado este mes',
  proximo: 'Próximo a vencer',
  vencido: 'Vencido',
  pendiente: 'Pendiente',
}

export default function Recurrentes() {
  const volver = useVolver('/perfil')
  const { avisar } = useDialogos() || {}
  const { recargar: recargarCuentas } = useCuentas()
  const [recs, setRecs] = useState([])
  const [sugerencias, setSugerencias] = useState([])
  const [cargando, setCargando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [error, setError] = useState('')

  async function cargar() {
    setCargando(true)
    setError('')
    try {
      setRecs(await api.recurrentes())
    } catch (err) {
      setError(err.message || 'No pudimos cargar tus pagos fijos. Revisa tu conexión y toca «Reintentar».')
    }
    try {
      setSugerencias(await api.sugerenciasRecurrentes())
    } catch {}
    setCargando(false)
  }

  useEffect(() => {
    cargar()
  }, [])

  async function marcarPagado(r) {
    try {
      await api.marcarRecurrentePagado(r.id)
      await recargarCuentas()
      avisar?.(`Listo: «${r.nombre}» quedó pagado este mes y ya está en tus movimientos.`, 'ok')
      cargar()
    } catch (err) {
      avisar?.(err.message || 'No pudimos marcarlo como pagado. Intenta de nuevo.')
    }
  }

  async function aceptarSugerencia(s) {
    await api.crearRecurrente({
      nombre: s.descripcion,
      monto: s.monto_promedio,
      tipo: s.tipo,
      categoria: s.categoria,
      cuenta_id: s.cuenta_id,
      dia_del_mes: s.dia_del_mes,
    })
    setSugerencias((prev) => prev.filter((x) => x.descripcion !== s.descripcion))
    avisar?.(`Agregamos «${s.descripcion}» a tus pagos fijos.`, 'ok')
    cargar()
  }

  function descartarSugerencia(s) {
    setSugerencias((prev) => prev.filter((x) => x.descripcion !== s.descripcion))
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={volver}
            className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
           aria-label="Volver">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-xl font-semibold">Pagos fijos</h1>
        </div>
        <button
          onClick={() => setMostrarForm(true)}
          className="w-11 h-11 rounded-full bg-accent text-paper-raised flex items-center justify-center"
         aria-label="Agregar un pago fijo">
          <Plus size={20} />
        </button>
      </header>

      <p className="mx-5 mt-1 text-xs text-ink-soft">Lo que pagas o recibes cada mes, como el arriendo, una suscripción o la nómina.</p>

      {!cargando && sugerencias.length > 0 && (
        <section className="mx-5 mt-4">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles size={16} className="text-accent" />
            <h2 className="text-sm font-semibold">Parece que estos se repiten cada mes</h2>
          </div>
          <div className="flex flex-col gap-2">
            {sugerencias.map((s) => (
              <div key={s.descripcion} className="rounded-2xl bg-accent-soft p-3.5 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{s.descripcion}</p>
                  <p className="text-xs text-ink-soft">
                    {formatCOP(s.monto_promedio)} · {formatVeces(s.ocurrencias)} detectado
                  </p>
                </div>
                <button
                  onClick={() => aceptarSugerencia(s)}
                  className="min-h-11 px-4 rounded-full bg-accent text-paper-raised text-sm font-semibold flex items-center justify-center shrink-0"
                 aria-label={`Agregar «${s.descripcion}» a mis pagos fijos`}>
                  Agregar
                </button>
                <button
                  onClick={() => descartarSugerencia(s)}
                  className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center shrink-0"
                 aria-label={`Descartar «${s.descripcion}»`}>
                  <X size={16} />
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {cargando ? (
        <EsqueletoLista filas={4} className="mx-5 mt-6" etiqueta="Cargando tus pagos fijos" />
      ) : error ? (
        <div className="mx-5 mt-6 rounded-2xl bg-danger-soft p-6 text-center">
          <p className="text-sm text-danger mb-3">{error}</p>
          <button onClick={cargar} className="text-sm font-semibold text-danger underline">
            Reintentar
          </button>
        </div>
      ) : recs.length === 0 ? (
        <EstadoVacio icono={Repeat} titulo="Aún no tienes pagos fijos" texto="Arriendo, suscripciones, nómina: anótalos una vez y te avisamos cuando se acerquen." className="mx-5 mt-6">
          <button onClick={() => setMostrarForm(true)} className="btn btn-primario btn-sm mt-4">Agregar un pago fijo</button>
        </EstadoVacio>
      ) : (
        <div className="mx-5 mt-4 rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
          {recs.map((r, i) => (
            <div key={r.id} className="flex items-center gap-3 px-4 py-3.5 stagger-item" style={{ '--stagger-i': i }}>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{r.nombre}</p>
                <p className={`text-xs ${estadoColor[r.estado]}`}>
                  {estadoLabel[r.estado]} · día {r.dia_del_mes}
                </p>
              </div>
              <p className={`text-sm font-semibold shrink-0 ${r.tipo === 'income' ? 'text-accent' : 'text-ink'}`}>
                {r.tipo === 'income' ? '+' : '-'}
                {formatCOP(r.monto)}
              </p>
              {r.estado !== 'pagado' && (
                <button
                  onClick={() => marcarPagado(r)}
                  className="min-h-11 px-3.5 rounded-full bg-accent-soft text-accent text-xs font-semibold flex items-center justify-center shrink-0"
                 aria-label={`Marcar «${r.nombre}» como pagado`}>
                  Ya pagué
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {!cargando && !error && (
        <EnlacesRelacionados enlaces={[
          { a: '/cuentas', texto: 'Mis cuentas', apoyo: 'Desde dónde se paga cada cosa' },
          { a: '/deudas', texto: 'Mis deudas', apoyo: 'Cuotas de créditos y tarjetas' },
          { a: '/presupuesto', texto: 'Mi presupuesto', apoyo: 'Cuánto te queda después de los pagos fijos' },
        ]} />
      )}

      {mostrarForm && (
        <FormRecurrente
          onClose={() => setMostrarForm(false)}
          onGuardado={() => {
            setMostrarForm(false)
            cargar()
          }}
        />
      )}
    </div>
  )
}

function FormRecurrente({ onClose, onGuardado }) {
  const { cuentas } = useCuentas()
  const [nombre, setNombre] = useState('')
  const [monto, setMonto] = useState('')
  const [tipo, setTipo] = useState('expense')
  const [diaMes, setDiaMes] = useState('1')
  const [cuentaId, setCuentaId] = useState(cuentas[0]?.id || '')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const { avisar } = useDialogos() || {}

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Escribe cómo lo reconoces, por ejemplo «Arriendo» o «Netflix».')
    if (!monto || Number(monto) <= 0) return setError('Escribe de cuánto es, solo números. Por ejemplo 45000.')
    const dia = Number(diaMes)
    if (dia < 1 || dia > 31) return setError('El día va entre 1 y 31.')

    setGuardando(true)
    try {
      await api.crearRecurrente({
        nombre: nombre.trim(),
        monto: Number(monto),
        tipo,
        dia_del_mes: Number(diaMes) || 1,
        cuenta_id: cuentaId || null,
      })
      avisar?.(`Listo: «${nombre.trim()}» quedó en tus pagos fijos.`, 'ok')
      onGuardado()
    } catch (err) {
      setError(err.message || 'No pudimos guardarlo. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onClose}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Nuevo pago fijo</h2>
        <button onClick={onClose} aria-label="Cerrar" className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center">
          <X size={16} />
        </button>
      </div>

      <div className="flex gap-2 mb-3">
        {[
          { id: 'expense', label: 'Gasto' },
          { id: 'income', label: 'Ingreso' },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTipo(t.id)}
            className={`flex-1 rounded-2xl py-2.5 text-sm font-semibold border ${
              tipo === t.id ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <CampoTexto
        etiqueta="¿Qué es?"
        value={nombre}
        onChange={(e) => setNombre(e.target.value)}
        placeholder="Ej. Netflix, Arriendo"
        className="mb-3"
      />
      <CampoMonto
        entero
        etiqueta="¿De cuánto es?"
        value={monto}
        onValor={setMonto}
        placeholder="Ej. 45000"
        className="mb-3"
      />
      <CampoTexto
        etiqueta="¿Qué día del mes?"
        ayuda="Un número entre 1 y 31."
        value={diaMes}
        onChange={(e) => setDiaMes(e.target.value.replace(/\D/g, '').slice(0, 2))}
        inputMode="numeric"
        className="mb-3"
      />

      {cuentas.length > 1 && (
        <label className="block mb-4">
          <span className="text-xs text-ink-soft">Cuenta de la que se paga</span>
          <select
            value={cuentaId}
            onChange={(e) => setCuentaId(e.target.value)}
            className="w-full mt-1 rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
          >
            {cuentas.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>
        </label>
      )}

      {error && <p role="alert" className="text-sm text-danger mb-3">{error}</p>}

      <button
        onClick={guardar}
        disabled={guardando}
        className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
      >
        {guardando ? 'Guardando...' : 'Guardar pago fijo'}
      </button>
    </Hoja>
  )
}
