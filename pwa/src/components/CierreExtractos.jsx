import { useState } from 'react'
import { AlertTriangle, CalendarClock, CheckCircle2, ChevronDown, CircleDashed, Landmark, Scale, XCircle } from 'lucide-react'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { useCuentas } from '../lib/CuentasContext'
import { mensajeAmable } from '../lib/mensajes'
import { textoFechasTarjeta } from '../lib/fechasTarjeta'
import { CLASE_OTRO, CONCEPTO_RESUMEN, conSigno, estadoCuenta, notaIncluye, origenEmpece, textoBanco, textoPeriodo } from '../lib/cierreExtractos'
import { Accion, EnlaceInterno } from './CuadreEncadenado'
import CambiarCuentaExtracto from './CambiarCuentaExtracto'
import AvisoSinTasa from './AvisoSinTasa'
import SaldoInicialAutomatico from './SaldoInicialAutomatico'

// «Cierre de mes» contra el extracto: por banco y por cuenta, con cuánto empecé, ingresos, gastos, otros movimientos,
// con cuánto terminé y lo que dice el extracto (cuadra o no, y por cuánto). Los números vienen del servidor
// (GET /cierre-mes/extractos); aquí solo se muestran. Móvil primero: una columna, filas de dos columnas.

const PILDORA = {
  cuadra: 'bg-cuadra-soft text-cuadra',
  no_cuadra: 'bg-danger-soft text-danger',
  sin_extracto: 'bg-paper text-ink-soft border border-line',
}
const ICONO_ESTADO = { cuadra: CheckCircle2, no_cuadra: XCircle, sin_extracto: CircleDashed }

function Pildora({ estado, children, sinIcono = false }) {
  const I = ICONO_ESTADO[estado] || CircleDashed
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${PILDORA[estado] || PILDORA.sin_extracto}`}>
      {!sinIcono && <I size={16} aria-hidden="true" />} {children}
    </span>
  )
}

function Fila({ etiqueta, valor, nota, fuerte, tono = '', children }) {
  return (
    <div className="py-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className={`text-sm ${fuerte ? 'font-semibold' : 'text-ink-soft'}`}>{etiqueta}</span>
        <span className={`text-sm tabular-nums ${fuerte ? 'font-bold' : 'font-medium'} ${tono}`}>{valor}</span>
      </div>
      {nota && <p className="text-[11px] text-ink-soft mt-0.5">{nota}</p>}
      {children}
    </div>
  )
}

/** Lo que el resumen de tu extracto trae y no es una línea de movimientos (rendimientos, 4x1000, costos por retiro). */
function DetalleResumen({ items, fmt, moneda }) {
  const [abierto, setAbierto] = useState(false)
  if (!items?.length) return null
  return (
    <>
      <button type="button" onClick={() => setAbierto(!abierto)} aria-expanded={abierto} data-testid="detalle-resumen-boton"
        className="min-h-11 inline-flex items-center gap-1 text-xs font-semibold text-accent">
        {abierto ? 'Ocultar lo que trae tu extracto' : 'Ver lo que trae tu extracto'}
        <ChevronDown size={16} aria-hidden="true" className={abierto ? 'rotate-180' : ''} />
      </button>
      {abierto && (
        <ul className="rounded-xl bg-paper p-3 text-xs space-y-1.5" data-testid="detalle-resumen">
          {items.map((d, i) => (
            <li key={`${d.fecha}-${d.concepto}-${i}`} className="flex justify-between gap-3">
              <span className="min-w-0">
                <span className="block truncate">{d.descripcion}</span>
                <span className="block text-[11px] text-ink-soft">{CONCEPTO_RESUMEN[d.concepto] || 'Resumen'} · {d.fecha.slice(5)}</span>
              </span>
              <span className="tabular-nums shrink-0">{conSigno(d.concepto === 'rendimientos' ? d.monto : -d.monto, fmt, moneda)}</span>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

function QueFalta({ cuenta, fmt }) {
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  const [abierto, setAbierto] = useState(false)
  async function alternar() {
    const abrir = !abierto
    setAbierto(abrir)
    if (abrir && !d) {
      try {
        setD(await api.cuadreQueFalta(cuenta.cuenta_id, cuenta.historial_id))
      } catch (err) {
        setError(mensajeAmable(err?.message, { porDefecto: 'No pude mirar qué falta. Intenta de nuevo.' }))
      }
    }
  }
  const sin = d?.sin_pareja_en_tus_movimientos || []
  const sobran = d?.sin_respaldo_en_el_extracto || []
  const linea = (x, i) => (
    <li key={`${x.fecha}-${i}`} className="flex justify-between gap-3">
      <span className="truncate">{String(x.fecha || '').slice(5, 10)} · {x.descripcion}</span>
      <span className="tabular-nums shrink-0">{fmt(x.monto, cuenta.moneda)}</span>
    </li>
  )
  return (
    <div className="mt-1">
      <button type="button" onClick={alternar} aria-expanded={abierto}
        className="min-h-11 inline-flex items-center gap-1.5 text-xs font-semibold text-accent">
        <Scale size={16} aria-hidden="true" /> Ver qué falta
        <ChevronDown size={16} aria-hidden="true" className={abierto ? 'rotate-180' : ''} />
      </button>
      {abierto && (
        <div className="rounded-xl bg-paper p-3 text-xs" data-testid="que-falta">
          {error && <p role="alert" className="text-danger">{error}</p>}
          {!d && !error && <p className="text-ink-soft" role="status">Mirando...</p>}
          {d && !sin.length && !sobran.length && <p className="text-ink-soft">No encuentro líneas sueltas en este mes.</p>}
          {sin.length > 0 && (
            <>
              <p className="font-semibold">Está en tu extracto, no en tus movimientos</p>
              <ul className="mt-1 space-y-1 text-ink-soft">{sin.slice(0, 6).map(linea)}</ul>
            </>
          )}
          {sobran.length > 0 && (
            <>
              <p className="font-semibold mt-2">Está en tus movimientos, no en el extracto</p>
              <ul className="mt-1 space-y-1 text-ink-soft">{sobran.slice(0, 6).map(linea)}</ul>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function BloqueCuenta({ c, mostrarNombre, onCambio }) {
  const { fmt } = useBloqueo()
  const { cuentas = [] } = useCuentas() || {}
  const [otros, setOtros] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [cambiando, setCambiando] = useState(null)
  const m = c.moneda
  const cuadra = c.estado === 'cuadra'
  const no = c.estado === 'no_cuadra'
  const periodo = textoPeriodo(c.periodo)
  const hayOtros = Math.abs(c.otros) >= 0.5 || (c.otros_detalle || []).length > 0

  return (
    <div className="py-3 first:pt-0" data-testid="cierre-cuenta" data-estado={c.estado}>
      {(mostrarNombre || periodo || c.estado === 'sin_extracto') && (
        <div className="flex items-center justify-between gap-2 mb-1">
          <p className="text-sm font-semibold truncate">{c.nombre}{c.tarjeta ? ' · Tarjeta' : ''}</p>
          {c.estado === 'sin_extracto' && <Pildora estado="sin_extracto">Sin extracto</Pildora>}
        </div>
      )}
      {periodo && <p className="text-[11px] text-ink-soft mb-1">{periodo}</p>}
      {c.tarjeta && c.tarjeta_fechas && textoFechasTarjeta(c.tarjeta_fechas) && (
        <p className="text-xs text-ink-soft mb-1 flex items-center gap-1.5" data-testid="fechas-tarjeta">
          <CalendarClock size={16} aria-hidden="true" className="shrink-0" />
          <span>{textoFechasTarjeta(c.tarjeta_fechas)}</span>
        </p>
      )}
      {c.cuadre_desde?.texto && (
        <p className={`text-xs font-semibold mb-1 flex items-start gap-2 ${c.cuadre_desde.estado === 'cuadra' ? 'text-cuadra' : 'text-danger'}`}
          data-testid="cuadra-desde">
          {c.cuadre_desde.estado === 'cuadra'
            ? <CheckCircle2 size={16} aria-hidden="true" className="shrink-0" />
            : <AlertTriangle size={16} aria-hidden="true" className="shrink-0" />}
          <span>{c.cuadre_desde.texto}</span>
        </p>
      )}
      <div className="divide-y divide-line">
        <Fila etiqueta="Empecé con" valor={fmt(c.empece, m)} nota={`Saldo ${origenEmpece(c)}`} />
        <Fila etiqueta="Ingresos" valor={conSigno(c.ingresos, fmt, m)} tono="text-cuadra"
          nota={notaIncluye([[c.rendimientos, 'rendimientos']], fmt, m)} />
        <Fila etiqueta="Gastos" valor={conSigno(-c.gastos, fmt, m)}
          nota={notaIncluye([[c.impuesto_4x1000, 'impuesto 4x1000'], [c.costos_retiro, 'costos por retiro']], fmt, m)}>
          <DetalleResumen items={c.detalle_resumen} fmt={fmt} moneda={m} />
        </Fila>
        {hayOtros && (
          <Fila etiqueta="Otros movimientos" valor={conSigno(c.otros, fmt, m)}
            nota="Plata que se movió sin ser ingreso ni gasto">
            <button type="button" onClick={() => setOtros(!otros)} aria-expanded={otros}
              className="min-h-11 inline-flex items-center gap-1 text-xs font-semibold text-accent">
              {otros ? 'Ocultar el detalle' : 'Ver el detalle'}
              <ChevronDown size={16} aria-hidden="true" className={otros ? 'rotate-180' : ''} />
            </button>
            {otros && (
              <ul className="rounded-xl bg-paper p-3 text-xs space-y-1.5" data-testid="otros-detalle">
                {c.otros_detalle.map((o, i) => (
                  <li key={`${o.fecha}-${i}`} className="flex justify-between gap-3">
                    <span className="min-w-0">
                      <span className="block truncate">{o.descripcion || CLASE_OTRO[o.clase]}</span>
                      <span className="block text-[11px] text-ink-soft">{CLASE_OTRO[o.clase] || CLASE_OTRO.otro} · {o.fecha.slice(5)}</span>
                    </span>
                    <span className="tabular-nums shrink-0">{conSigno(o.monto, fmt, m)}</span>
                  </li>
                ))}
                {c.otros_total_movimientos > c.otros_detalle.length && (
                  <li className="text-ink-soft">y {c.otros_total_movimientos - c.otros_detalle.length} más</li>
                )}
              </ul>
            )}
          </Fila>
        )}
        <Fila etiqueta="Terminé con" valor={fmt(c.termine, m)} fuerte />
        {c.estado !== 'sin_extracto' && (
          <Fila etiqueta="Según tu extracto" valor={fmt(c.segun_extracto, m)}>
            <div className="mt-1.5"><Pildora estado={c.estado}>{estadoCuenta(c, fmt)}</Pildora></div>
          </Fila>
        )}
      </div>

      {!c.tarjeta && c.ajuste_inicial && (
        <SaldoInicialAutomatico cuentaId={c.cuenta_id} moneda={m} info={c.ajuste_inicial} onCambio={() => onCambio?.()} />
      )}
      {c.tarjeta && <p className="text-[11px] text-ink-soft mt-1">En una tarjeta, un saldo negativo es lo que debes.</p>}
      {c.estado === 'sin_extracto' && (
        <p className="text-[11px] text-ink-soft mt-1">
          {c.motivo_sin_extracto || 'Sin el extracto de este mes no puedo comprobar el saldo; te muestro lo que calculé.'}
        </p>
      )}

      {no && (
        <div className="mt-3 rounded-xl bg-danger-soft/60 p-3" data-testid="cierre-diagnostico">
          <p className="text-sm font-semibold flex items-start gap-2">
            <AlertTriangle size={16} className="text-danger shrink-0 mt-0.5" aria-hidden="true" />
            <span>{c.motivo}</span>
          </p>
          <div className="mt-2 flex flex-col gap-1">
            {(c.acciones || []).filter((a) => a.tipo !== 'ajuste').slice(0, 2).map((a, i) => (
              a.tipo === 'cambiar_cuenta' ? (
                <button key={`${a.tipo}-${i}`} type="button" onClick={() => setCambiando(a)}
                  className="min-h-11 w-full rounded-xl bg-accent text-paper-raised text-xs font-semibold px-3">
                  {a.texto}
                </button>
              ) : (
                <Accion key={`${a.tipo}-${i}`} accion={a} moneda={m} ocupado={ocupado} setOcupado={setOcupado} onHecho={onCambio} />
              )
            ))}
            <QueFalta cuenta={c} fmt={fmt} />
            <EnlaceInterno to="/sincronizacion#cuadre" className="min-h-11 inline-flex items-center text-xs font-semibold text-accent">
              Abrir el cuadre de {c.nombre}
            </EnlaceInterno>
          </div>
        </div>
      )}
      {cuadra && c.aviso && <p className="text-[11px] text-ink-soft mt-1">{c.aviso}</p>}
      {cambiando && (
        <CambiarCuentaExtracto historialId={c.historial_id} titulo={`Extracto de ${c.nombre}`} cuentaActualId={c.cuenta_id}
          cuentas={cuentas} destinoInicial={cambiando.destino_id} onCerrar={() => setCambiando(null)} onListo={() => onCambio?.()} />
      )}
    </div>
  )
}

function ResumenBancos({ datos, fmt }) {
  const lista = datos.resumen_bancos || []
  if (!lista.length) return null
  return (
    <ul className="flex flex-wrap gap-2" aria-label="Resumen por banco" data-testid="resumen-bancos">
      {lista.map((b) => (
        <li key={b.banco}>
          <Pildora estado={b.estado} sinIcono>{textoBanco(b, (v) => fmt(v, datos.moneda_base))}</Pildora>
        </li>
      ))}
    </ul>
  )
}

export default function CierreExtractos({ datos, onCambio }) {
  const { fmt } = useBloqueo()
  if (!datos || !Array.isArray(datos.bancos)) return null
  if (!datos.hay_datos) {
    return (
      <div className="rounded-2xl bg-paper-raised border border-line p-5 text-center" data-testid="cierre-sin-datos">
        <Landmark size={24} className="mx-auto text-ink-soft" aria-hidden="true" />
        <p className="text-sm font-semibold mt-2">No hay movimientos en {String(datos.etiqueta || '').toLowerCase()}</p>
        <p className="text-xs text-ink-soft mt-1">Cuando traigas tus movimientos o el extracto de ese mes, aquí verás si cuadra con tu banco.</p>
      </div>
    )
  }
  const t = datos.total || {}
  const base = datos.moneda_base
  return (
    <section aria-label="Cierre contra tus extractos" data-testid="cierre-extractos" className="flex flex-col gap-3">
      <div>
        <h2 className="text-base font-semibold">Así cerró {String(datos.etiqueta || '').toLowerCase()}</h2>
        <p className="text-xs text-ink-soft mt-0.5">
          {datos.parcial ? 'El mes aún no termina: estas cifras cambiarán. ' : ''}
          Con cuánto empezaste, qué entró y salió, y con cuánto terminaste, comparado con tu extracto.
        </p>
      </div>
      <ResumenBancos datos={datos} fmt={fmt} />
      <AvisoSinTasa monedas={datos.monedas_sin_tasa} base={base} onResuelto={onCambio} />

      {datos.bancos.map((b) => (
        <div key={b.banco} className="rounded-2xl bg-paper-raised border border-line p-4" data-testid="cierre-banco" data-estado={b.estado}>
          <div className="flex items-center justify-between gap-2 mb-2">
            <h3 className="text-base font-semibold flex items-center gap-2 min-w-0">
              <Landmark size={20} className="text-ink-soft shrink-0" aria-hidden="true" /> <span className="truncate">{b.banco}</span>
            </h3>
            <Pildora estado={b.estado}>
              {b.estado === 'cuadra' ? 'Cuadra' : b.estado === 'no_cuadra' ? `No cuadra por ${fmt(b.diferencia, base)}` : 'Sin extracto'}
            </Pildora>
          </div>
          <div className="divide-y divide-line">
            {b.cuentas.map((c) => (
              <BloqueCuenta key={c.cuenta_id} c={c} mostrarNombre={b.cuentas.length > 1 || c.nombre !== b.banco} onCambio={onCambio} />
            ))}
          </div>
          {b.cuentas.length > 1 && b.total && (
            <div className="mt-2 pt-2 border-t border-line" data-testid="total-banco">
              <Fila etiqueta={`Total ${b.banco}`} valor={fmt(b.total.termine, base)} fuerte
                nota={`Empezó con ${fmt(b.total.empece, base)} · ingresos ${conSigno(b.total.ingresos, fmt, base)} · gastos ${conSigno(-b.total.gastos, fmt, base)}`} />
            </div>
          )}
        </div>
      ))}

      <div className="rounded-2xl bg-accent-soft p-4" data-testid="cierre-total">
        <h3 className="text-base font-semibold">Todas tus cuentas</h3>
        <div className="divide-y divide-line/60 mt-1">
          <Fila etiqueta="Empecé con" valor={fmt(t.empece, base)} />
          <Fila etiqueta="Ingresos" valor={conSigno(t.ingresos, fmt, base)} tono="text-cuadra"
            nota={notaIncluye([[t.rendimientos, 'rendimientos']], fmt, base)} />
          <Fila etiqueta="Gastos" valor={conSigno(-t.gastos, fmt, base)}
            nota={notaIncluye([[t.impuesto_4x1000, 'impuesto 4x1000']], fmt, base)} />
          {Math.abs(t.otros || 0) >= 0.5 && <Fila etiqueta="Otros movimientos" valor={conSigno(t.otros, fmt, base)} />}
          <Fila etiqueta="Terminé con" valor={fmt(t.termine, base)} fuerte />
        </div>
        <p className="text-xs text-ink-soft mt-2">
          {t.no_cuadran === 0 && t.cuadran > 0
            ? `${t.cuadran === 1 ? 'Tu cuenta con extracto cuadra' : `Las ${t.cuadran} cuentas con extracto cuadran`}.`
            : t.cuadran + t.no_cuadran > 0
              ? `${t.cuadran} de ${t.cuadran + t.no_cuadran} cuentas con extracto cuadran.`
              : 'Ninguna cuenta tiene extracto este mes.'}
          {t.sin_extracto > 0 ? ` ${t.sin_extracto} ${t.sin_extracto === 1 ? 'cuenta va' : 'cuentas van'} sin extracto.` : ''}
        </p>
        <p className="text-[11px] text-ink-soft mt-1">Ingresos y gastos son los mismos de tu informe: no cuentan pagos de tarjeta ni plata que pasaste entre tus cuentas.</p>
      </div>
    </section>
  )
}
