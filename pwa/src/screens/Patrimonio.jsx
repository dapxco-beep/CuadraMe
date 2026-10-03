import { useEffect, useState } from 'react'
import { Plus, TrendingDown, TrendingUp, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP, formatMoneda } from '../lib/format'
import { useDialogos } from '../lib/DialogosContext'
import { CLASES, CLASES_BIEN, CLASES_MERCADO, formatPct, valorCDT } from '../lib/patrimonio'
import GraficoPatrimonio from '../components/GraficoPatrimonio'
import DonaDistribucion from '../components/DonaDistribucion'

const MONEDAS = ['COP', 'USD', 'EUR']
const CLASES_ACTIVO = ['cdt', 'fondo', 'etf', 'accion', 'cripto', 'inmueble', 'vehiculo']

function colorGanancia(v) {
  if (v === null || v === undefined || v === 0) return 'text-ink-soft'
  return v > 0 ? 'text-accent' : 'text-danger'
}

function fechaCorta(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function Patrimonio() {
  const [datos, setDatos] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [formulario, setFormulario] = useState(null) // null | { activo?: objeto }

  async function cargar() {
    setCargando(true)
    setError('')
    try {
      setDatos(await api.patrimonio())
    } catch (err) {
      setError(err.message || 'No se pudo cargar tu patrimonio')
    }
    setCargando(false)
  }

  useEffect(() => {
    cargar()
  }, [])

  const vacio = datos && datos.activos.length === 0 && datos.pasivos.length === 0 && datos.total_cuentas === 0

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-5 pt-14 pb-2 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Patrimonio</h1>
        <button
          onClick={() => setFormulario({})}
          className="w-10 h-10 rounded-full bg-accent text-white flex items-center justify-center"
          aria-label="Agregar activo"
        >
          <Plus size={20} />
        </button>
      </header>

      {cargando && !datos ? (
        <div className="mx-5 mt-3 space-y-3">
          <div className="skeleton h-32" />
          <div className="skeleton h-48" />
        </div>
      ) : error && !datos ? (
        <div className="mx-5 mt-6 rounded-2xl bg-danger-soft p-6 text-center" role="alert">
          <p className="text-sm text-danger mb-3">{error}</p>
          <button onClick={cargar} className="text-sm font-semibold text-danger underline">
            Reintentar
          </button>
        </div>
      ) : (
        datos && (
          <>
            <TarjetaNeto datos={datos} />

            {datos.historial.length > 0 && (
              <section className="mx-5 mt-4 rounded-2xl bg-paper-raised border border-line p-4 stagger-item" style={{ '--stagger-i': 1 }}>
                <h2 className="text-sm font-semibold mb-3">Evolución</h2>
                <GraficoPatrimonio historial={datos.historial} />
              </section>
            )}

            {datos.distribucion.length > 0 && (
              <section className="mx-5 mt-4 rounded-2xl bg-paper-raised border border-line p-4 stagger-item" style={{ '--stagger-i': 2 }}>
                <h2 className="text-sm font-semibold mb-3">Distribución</h2>
                <DonaDistribucion distribucion={datos.distribucion} />
              </section>
            )}

            <section className="mx-5 mt-4">
              <h2 className="text-sm font-semibold mb-2">Mis activos</h2>
              {datos.activos.length === 0 ? (
                <div className="rounded-2xl bg-paper-raised border border-line p-6 text-center">
                  <p className="text-sm text-ink-soft mb-3">
                    {vacio
                      ? 'Aún no hay nada que contar. Agrega tu primer CDT, fondo, inmueble o vehículo.'
                      : 'Agrega tus CDT, fondos, acciones, inmuebles o vehículos para ver tu patrimonio completo.'}
                  </p>
                  <button onClick={() => setFormulario({})} className="text-sm font-semibold text-accent">
                    Agregar activo
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {datos.activos.map((a, i) => (
                    <TarjetaActivo key={a.id} activo={a} indice={i} onEditar={() => setFormulario({ activo: a })} />
                  ))}
                </div>
              )}
            </section>

            {datos.pasivos.length > 0 && (
              <section className="mx-5 mt-4">
                <h2 className="text-sm font-semibold mb-2">Pasivos (tus deudas)</h2>
                <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line">
                  {datos.pasivos.map((p) => (
                    <div key={p.id} className="flex items-center justify-between px-4 py-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{p.nombre}</p>
                        {p.entidad && <p className="text-xs text-ink-soft truncate">{p.entidad}</p>}
                      </div>
                      <p className="text-sm font-semibold text-danger">-{formatCOP(p.saldo)}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <p className="mx-5 mt-4 text-[11px] text-ink-soft leading-relaxed">
              Los totales se expresan en pesos colombianos (COP) con la tasa de cambio del día. La rentabilidad de cada
              activo se calcula en su propia moneda. El valor de fondos, acciones, inmuebles y vehículos depende del
              precio que registres.
            </p>
          </>
        )
      )}

      {formulario && (
        <FormActivo
          activo={formulario.activo}
          onClose={() => setFormulario(null)}
          onGuardado={() => {
            setFormulario(null)
            cargar()
          }}
        />
      )}
    </div>
  )
}

function TarjetaNeto({ datos }) {
  const variacion = datos.variacion_mes_anterior
  const sube = variacion !== null && variacion !== undefined && variacion >= 0
  return (
    <div className="mx-5 mt-3 rounded-3xl bg-ink text-paper p-5 stagger-item" style={{ '--stagger-i': 0 }}>
      <p className="text-xs opacity-70 mb-1">Patrimonio neto</p>
      <p className="text-3xl font-bold tracking-tight tabular-nums">{formatCOP(datos.patrimonio_neto)}</p>
      {variacion !== null && variacion !== undefined && (
        <p className="mt-1 text-xs flex items-center gap-1 opacity-90">
          {sube ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          {sube ? '+' : '-'}
          {formatCOP(Math.abs(variacion))} vs. el mes anterior
        </p>
      )}
      <div className="grid grid-cols-3 gap-2 mt-4 text-xs">
        <div>
          <p className="opacity-70">Inversiones y bienes</p>
          <p className="font-semibold tabular-nums">{formatCOP(datos.total_activos)}</p>
        </div>
        <div>
          <p className="opacity-70">Cuentas</p>
          <p className="font-semibold tabular-nums">{formatCOP(datos.total_cuentas)}</p>
        </div>
        <div>
          <p className="opacity-70">Deudas</p>
          <p className="font-semibold tabular-nums">-{formatCOP(datos.total_deudas)}</p>
        </div>
      </div>
    </div>
  )
}

function TarjetaActivo({ activo: a, indice, onEditar }) {
  const meta = CLASES[a.clase]
  return (
    <button
      onClick={onEditar}
      className="w-full text-left rounded-2xl bg-paper-raised border border-line p-4 stagger-item"
      style={{ '--stagger-i': indice }}
      aria-label={`Editar ${a.nombre}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold truncate">
            {meta?.emoji} {a.nombre}
          </p>
          <p className="text-xs text-ink-soft">
            {meta?.label}
            {a.ticker ? ` · ${a.ticker}` : ''}
            {a.moneda !== 'COP' ? ` · ${a.moneda}` : ''}
          </p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-sm font-bold tabular-nums">{formatMoneda(a.valor, a.moneda)}</p>
          {a.moneda !== 'COP' && <p className="text-[11px] text-ink-soft tabular-nums">{formatCOP(a.valor_cop)}</p>}
        </div>
      </div>

      <div className="flex items-center justify-between mt-3 text-xs">
        <span className={`font-semibold tabular-nums ${colorGanancia(a.ganancia)}`}>
          {a.rentabilidad_pct === null ? 'Sin costo registrado' : formatPct(a.rentabilidad_pct)}
          {a.rentabilidad_pct !== null && ` · ${a.ganancia >= 0 ? '+' : '-'}${formatMoneda(Math.abs(a.ganancia), a.moneda)}`}
        </span>
        {a.xirr_pct !== null && a.xirr_pct !== undefined && (
          <span className="text-ink-soft tabular-nums" title="Tasa interna de retorno efectiva anual (XIRR)">
            XIRR {formatPct(a.xirr_pct)} E.A.
          </span>
        )}
      </div>

      {a.clase === 'cdt' && (
        <p className="text-[11px] text-ink-soft mt-1.5">
          {a.tasa_ea}% E.A. · {a.vencido ? 'Vencido' : `vence en ${a.dias_al_vencimiento} días`} · al vencimiento{' '}
          {formatMoneda(a.valor_vencimiento, a.moneda)}
        </p>
      )}
      {a.clase !== 'cdt' && a.precio_fecha && (
        <p className="text-[11px] text-ink-soft mt-1.5">Precio al {fechaCorta(a.precio_fecha)} (manual)</p>
      )}
    </button>
  )
}

const claseInput =
  'w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent'

function Campo({ etiqueta, children }) {
  return (
    <label className="block mb-3">
      <span className="text-xs text-ink-soft">{etiqueta}</span>
      <div className="mt-1">{children}</div>
    </label>
  )
}

const soloNumero = (v) => v.replace(/[^0-9.]/g, '')
const aFecha = (v) => (v ? `${v}T00:00:00` : null)
const deFecha = (iso) => (iso ? String(iso).slice(0, 10) : '')

function FormActivo({ activo, onClose, onGuardado }) {
  const { confirmar } = useDialogos()
  const editando = Boolean(activo)
  const hoy = new Date().toISOString().slice(0, 10)

  const [clase, setClase] = useState(activo?.clase || 'cdt')
  const [nombre, setNombre] = useState(activo?.nombre || '')
  const [moneda, setMoneda] = useState(activo?.moneda || 'COP')
  const [capital, setCapital] = useState(activo?.capital ? String(activo.capital) : '')
  const [tasaEA, setTasaEA] = useState(activo?.tasa_ea != null ? String(activo.tasa_ea) : '')
  const [inicio, setInicio] = useState(deFecha(activo?.fecha_inicio) || hoy)
  const [vencimiento, setVencimiento] = useState(deFecha(activo?.fecha_vencimiento))
  const [ticker, setTicker] = useState(activo?.ticker || '')
  const [unidades, setUnidades] = useState(activo?.unidades ? String(activo.unidades) : '')
  const [costoPromedio, setCostoPromedio] = useState(activo?.costo_promedio != null ? String(activo.costo_promedio) : '')
  const [precio, setPrecio] = useState(activo?.precio_actual != null ? String(activo.precio_actual) : '')
  const [costoAdq, setCostoAdq] = useState(activo?.costo_adquisicion != null ? String(activo.costo_adquisicion) : '')
  const [fechaAdq, setFechaAdq] = useState(deFecha(activo?.fecha_adquisicion))
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  const esCDT = clase === 'cdt'
  const esMercado = CLASES_MERCADO.includes(clase)
  const esBien = CLASES_BIEN.includes(clase)

  const vistaCDT =
    esCDT && Number(capital) > 0 && tasaEA !== '' && inicio && vencimiento && vencimiento > inicio
      ? {
          hoy: valorCDT(Number(capital), Number(tasaEA), inicio, hoy, vencimiento),
          final: valorCDT(Number(capital), Number(tasaEA), inicio, vencimiento, vencimiento),
        }
      : null

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre')
    const base = { clase, nombre: nombre.trim(), moneda }
    let payload
    if (esCDT) {
      if (!(Number(capital) > 0)) return setError('Ingresa el capital del CDT')
      if (tasaEA === '') return setError('Ingresa la tasa E.A.')
      if (!inicio || !vencimiento) return setError('Ingresa las fechas de inicio y vencimiento')
      if (vencimiento <= inicio) return setError('El vencimiento debe ser posterior al inicio')
      payload = { ...base, capital: Number(capital), tasa_ea: Number(tasaEA), fecha_inicio: aFecha(inicio), fecha_vencimiento: aFecha(vencimiento) }
    } else if (esMercado) {
      if (!(Number(unidades) > 0)) return setError('Ingresa cuántas unidades tienes')
      if (costoPromedio === '') return setError('Ingresa tu costo promedio por unidad')
      payload = {
        ...base,
        ticker: ticker.trim() || null,
        unidades: Number(unidades),
        costo_promedio: Number(costoPromedio),
        precio_actual: precio === '' ? null : Number(precio),
      }
    } else {
      if (!(Number(precio) > 0)) return setError('Ingresa el valor estimado actual')
      payload = {
        ...base,
        precio_actual: Number(precio),
        costo_adquisicion: costoAdq === '' ? null : Number(costoAdq),
        fecha_adquisicion: aFecha(fechaAdq),
      }
    }

    setGuardando(true)
    try {
      if (editando) await api.editarActivo(activo.id, payload)
      else await api.crearActivo(payload)
      onGuardado()
    } catch (err) {
      setError(err.message || 'No se pudo guardar')
    } finally {
      setGuardando(false)
    }
  }

  async function eliminar() {
    const ok = await confirmar('Dejará de contar en tu patrimonio. Tu historial mensual no cambia.', {
      titulo: `¿Eliminar "${activo.nombre}"?`,
      confirmarTexto: 'Eliminar',
      peligro: true,
    })
    if (!ok) return
    setGuardando(true)
    try {
      await api.eliminarActivo(activo.id)
      onGuardado()
    } catch (err) {
      setError(err.message || 'No se pudo eliminar')
      setGuardando(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-50 overflow-y-auto sheet-backdrop">
      <div className="w-full max-w-[480px] bg-paper rounded-t-[28px] p-6 pb-8 sheet-content max-h-[92vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{editando ? 'Editar activo' : 'Nuevo activo'}</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>

        {!editando && (
          <div className="flex flex-wrap gap-2 mb-4" role="group" aria-label="Clase de activo">
            {CLASES_ACTIVO.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setClase(c)}
                aria-pressed={clase === c}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                  clase === c ? 'bg-accent text-white border-accent' : 'bg-paper-raised border-line text-ink-soft'
                }`}
              >
                {CLASES[c].emoji} {CLASES[c].label}
              </button>
            ))}
          </div>
        )}

        <Campo etiqueta="Nombre">
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder={esCDT ? 'Ej. CDT Bancolombia 360 días' : esBien ? 'Ej. Apartamento Chicó' : 'Ej. S&P 500 ETF'}
            className={claseInput}
          />
        </Campo>

        <Campo etiqueta="Moneda">
          <select value={moneda} onChange={(e) => setMoneda(e.target.value)} className={claseInput}>
            {MONEDAS.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </Campo>

        {esCDT && (
          <>
            <Campo etiqueta="Capital invertido">
              <input value={capital} onChange={(e) => setCapital(soloNumero(e.target.value))} inputMode="decimal" className={claseInput} />
            </Campo>
            <Campo etiqueta="Tasa efectiva anual (%)">
              <input value={tasaEA} onChange={(e) => setTasaEA(soloNumero(e.target.value))} inputMode="decimal" placeholder="Ej. 12.5" className={claseInput} />
            </Campo>
            <div className="grid grid-cols-2 gap-3">
              <Campo etiqueta="Fecha de inicio">
                <input type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} className={claseInput} />
              </Campo>
              <Campo etiqueta="Vencimiento">
                <input type="date" value={vencimiento} onChange={(e) => setVencimiento(e.target.value)} className={claseInput} />
              </Campo>
            </div>
            {vistaCDT && (
              <div className="rounded-2xl bg-accent-soft p-3 mb-3 text-xs">
                <p>Valor hoy: <strong>{formatMoneda(vistaCDT.hoy, moneda)}</strong></p>
                <p>Al vencimiento: <strong>{formatMoneda(vistaCDT.final, moneda)}</strong></p>
              </div>
            )}
          </>
        )}

        {esMercado && (
          <>
            <Campo etiqueta="Ticker o código (opcional, para precios automáticos futuros)">
              <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} placeholder="Ej. VOO, BTC" className={claseInput} />
            </Campo>
            <div className="grid grid-cols-2 gap-3">
              <Campo etiqueta="Unidades">
                <input value={unidades} onChange={(e) => setUnidades(soloNumero(e.target.value))} inputMode="decimal" className={claseInput} />
              </Campo>
              <Campo etiqueta="Costo promedio por unidad">
                <input value={costoPromedio} onChange={(e) => setCostoPromedio(soloNumero(e.target.value))} inputMode="decimal" className={claseInput} />
              </Campo>
            </div>
            <Campo etiqueta="Precio actual por unidad (manual)">
              <input value={precio} onChange={(e) => setPrecio(soloNumero(e.target.value))} inputMode="decimal" placeholder="Si lo dejas vacío se usa el costo" className={claseInput} />
            </Campo>
          </>
        )}

        {esBien && (
          <>
            <Campo etiqueta="Valor estimado actual">
              <input value={precio} onChange={(e) => setPrecio(soloNumero(e.target.value))} inputMode="decimal" className={claseInput} />
            </Campo>
            <div className="grid grid-cols-2 gap-3">
              <Campo etiqueta="Costo de compra (opcional)">
                <input value={costoAdq} onChange={(e) => setCostoAdq(soloNumero(e.target.value))} inputMode="decimal" className={claseInput} />
              </Campo>
              <Campo etiqueta="Fecha de compra (opcional)">
                <input type="date" value={fechaAdq} onChange={(e) => setFechaAdq(e.target.value)} className={claseInput} />
              </Campo>
            </div>
          </>
        )}

        {error && <p className="text-sm text-danger mb-3" role="alert">{error}</p>}

        <button
          onClick={guardar}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
        >
          {guardando ? 'Guardando...' : editando ? 'Guardar cambios' : 'Agregar activo'}
        </button>
        {editando && (
          <button onClick={eliminar} disabled={guardando} className="w-full mt-3 text-sm font-semibold text-danger py-2">
            Eliminar activo
          </button>
        )}
      </div>
    </div>
  )
}
