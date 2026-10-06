import { useState } from 'react'
import { Pencil, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import Hoja from './Hoja'
import ComprasACuotas from './ComprasACuotas'

const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

// "2026-10-15" -> "15 oct". Se parte el texto a mano: new Date('2026-10-15')
// se interpreta en UTC y en Colombia mostraría el 14.
function fechaCorta(iso) {
  if (!iso) return '—'
  const [, m, d] = iso.split('-')
  return `${parseInt(d, 10)} ${MESES_CORTOS[parseInt(m, 10) - 1]}`
}

function enDias(n) {
  if (n == null) return ''
  if (n === 0) return 'hoy'
  return `en ${n} ${n === 1 ? 'día' : 'días'}`
}

const NIVELES = {
  ok: { barra: 'var(--color-accent)', texto: 'text-ink-soft', aviso: '' },
  alerta: {
    barra: 'var(--color-accent-2)',
    texto: 'text-accent-2',
    aviso: 'Uso moderado: lo ideal es mantenerte por debajo del 30% del cupo.',
  },
  critico: {
    barra: 'var(--color-danger)',
    texto: 'text-danger',
    aviso: 'Uso muy alto (más del 80%): te deja sin margen y puede afectar tu historial crediticio.',
  },
  sin_cupo: { barra: 'var(--color-line)', texto: 'text-ink-soft', aviso: '' },
}

// "Para no pagar intereses": lo que hay que pagar es la deuda al último corte (el
// extracto), no el cupo usado de hoy; las compras nuevas van al siguiente extracto.
export function BloqueExtracto({ t, moneda }) {
  if (t.total_extracto == null || t.total_extracto <= 0) return null
  const pct = Math.min(100, t.pagado_pct || 0)
  const pagado = t.falta_para_evitar_intereses <= 0
  return (
    <div className="mt-3 rounded-xl border border-line bg-paper p-3 text-xs" data-testid="bloque-extracto">
      <p className="font-semibold text-sm">
        {pagado ? (
          <span className="text-accent">Extracto pagado: no pagas intereses</span>
        ) : t.fecha_limite_pago ? (
          <>
            Para no pagar intereses: {formatMoneda(t.falta_para_evitar_intereses, moneda)}{' '}
            <span className="font-normal text-ink-soft">antes del {fechaCorta(t.fecha_limite_pago)}</span>
          </>
        ) : (
          <>Para no pagar intereses: {formatMoneda(t.falta_para_evitar_intereses, moneda)}</>
        )}
      </p>
      {t.vencido && <p className="text-danger mt-1">El plazo ya pasó: paga cuanto antes para frenar los intereses.</p>}
      {!pagado && !t.vencido && t.dias_para_limite != null && t.dias_para_limite <= 7 && (
        <p className={`mt-1 font-medium ${t.dias_para_limite <= 3 ? 'text-danger' : 'text-accent-2'}`} data-testid="aviso-dias-pago">
          {t.dias_para_limite === 0 ? 'Hoy vence tu pago.' : `Te quedan ${t.dias_para_limite} ${t.dias_para_limite === 1 ? 'día' : 'días'} para el pago.`}
          {t.pago_minimo_del_extracto && t.pago_minimo != null && ` Pago mínimo de tu extracto: ${formatMoneda(t.pago_minimo, moneda)}.`}
        </p>
      )}
      {t.total_del_banco && <p className="text-[11px] text-ink-soft mt-1">Total tomado de tu extracto del banco.</p>}
      <div
        className="h-2 rounded-full bg-paper-raised overflow-hidden mt-2"
        role="progressbar"
        aria-label="Pagado del extracto"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: 'var(--color-accent)', transition: 'width 600ms ease-out' }} />
      </div>
      <div className="flex justify-between text-[11px] text-ink-soft mt-1.5">
        <span>Total del extracto {formatMoneda(t.total_extracto, moneda)}</span>
        <span>Pagado {formatMoneda(t.pagado_desde_corte || 0, moneda)}</span>
      </div>
      {t.compras_despues_corte > 0 && (
        <p className="text-[11px] text-ink-soft mt-1.5">
          Compras después del corte: {formatMoneda(t.compras_despues_corte, moneda)} (van en el próximo extracto).
        </p>
      )}
    </div>
  )
}

// Detalle de una cuenta de crédito: barra de utilización, fechas de corte y
// pago, y una estimación de qué pasa si no pagas el total.
export default function PanelTarjetaCredito({ cuenta, onCambio }) {
  const [editando, setEditando] = useState(false)
  const t = cuenta.tarjeta
  if (!t) return null

  const nivel = NIVELES[t.nivel_utilizacion] || NIVELES.ok
  const configurada = cuenta.cupo_total || cuenta.dia_corte || cuenta.dia_pago

  return (
    <div className="mt-2 rounded-2xl bg-paper-raised border border-line p-4" data-testid="panel-tarjeta">
      {!configurada ? (
        <p className="text-xs text-ink-soft mb-3">
          Agrega el cupo, el día de corte y el de pago para ver tu utilización y recibir un aviso antes de pagar.
        </p>
      ) : (
        <>
          {t.utilizacion_pct != null && (
            <>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="font-semibold">Cupo usado</span>
                <span className={`font-semibold ${nivel.texto}`}>{t.utilizacion_pct}%</span>
              </div>
              <div
                className="h-2.5 rounded-full bg-paper overflow-hidden"
                role="progressbar"
                aria-label="Utilización del cupo"
                aria-valuenow={Math.min(100, t.utilizacion_pct)}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.min(100, t.utilizacion_pct)}%`,
                    background: nivel.barra,
                    transition: 'width 600ms ease-out',
                  }}
                />
              </div>
              <div className="flex justify-between text-[11px] text-ink-soft mt-1.5">
                <span>Debes {formatMoneda(t.cupo_usado, cuenta.moneda)}</span>
                <span>Disponible del cupo: {formatMoneda(t.cupo_disponible, cuenta.moneda)}</span>
              </div>
              {nivel.aviso && <p className={`text-xs mt-2 ${nivel.texto}`}>{nivel.aviso}</p>}
            </>
          )}

          <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
            <div>
              <p className="text-ink-soft">Próximo corte</p>
              <p className="font-semibold">
                {fechaCorta(t.proximo_corte)} <span className="font-normal text-ink-soft">{enDias(t.dias_para_corte)}</span>
              </p>
            </div>
            <div>
              <p className="text-ink-soft">Fecha límite de pago</p>
              <p className="font-semibold">
                {fechaCorta(t.proximo_pago)} <span className="font-normal text-ink-soft">{enDias(t.dias_para_pago)}</span>
              </p>
            </div>
          </div>

          <BloqueExtracto t={t} moneda={cuenta.moneda} />

          {t.cupo_usado > 0 && (
            <div className="mt-3 rounded-xl bg-paper p-3 text-xs space-y-1">
              <p>
                <span className="text-ink-soft">{t.pago_minimo_del_extracto ? 'Pago mínimo (de tu extracto): ' : 'Pago mínimo estimado: '}</span>
                <span className="font-semibold">{formatMoneda(t.pago_minimo ?? t.pago_minimo_estimado, cuenta.moneda)}</span>
              </p>
              {t.interes_estimado != null ? (
                <p>
                  <span className="text-ink-soft">Interés si no pagas el total: </span>
                  <span className="font-semibold text-danger">~{formatMoneda(t.interes_estimado, cuenta.moneda)} al mes</span>
                </p>
              ) : (
                <p className="text-ink-soft">Agrega la tasa efectiva anual para estimar los intereses.</p>
              )}
              {t.proximo_pago && t.total_extracto == null && (
                <p className="text-ink-soft">Paga el total antes del {fechaCorta(t.proximo_pago)} para no pagar intereses.</p>
              )}
            </div>
          )}
        </>
      )}

      <ComprasACuotas cuenta={cuenta} />

      <button
        onClick={() => setEditando(true)}
        className="mt-3 flex items-center gap-1.5 text-sm text-accent font-medium"
      >
        <Pencil size={14} /> {configurada ? 'Editar datos de la tarjeta' : 'Configurar tarjeta'}
      </button>

      {editando && (
        <FormTarjeta
          cuenta={cuenta}
          onClose={() => setEditando(false)}
          onGuardada={() => {
            setEditando(false)
            onCambio?.()
          }}
        />
      )}
    </div>
  )
}

function FormTarjeta({ cuenta, onClose, onGuardada }) {
  const [cupo, setCupo] = useState(cuenta.cupo_total ? String(cuenta.cupo_total) : '')
  const [corte, setCorte] = useState(cuenta.dia_corte ? String(cuenta.dia_corte) : '')
  const [pago, setPago] = useState(cuenta.dia_pago ? String(cuenta.dia_pago) : '')
  const [tasa, setTasa] = useState(cuenta.tasa_ea != null ? String(cuenta.tasa_ea) : '')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  function diaValido(v) {
    return v === '' || (Number(v) >= 1 && Number(v) <= 31)
  }

  async function guardar() {
    setError('')
    if (!diaValido(corte) || !diaValido(pago)) return setError('Los días deben estar entre 1 y 31')
    if (tasa !== '' && (Number(tasa) < 0 || Number(tasa) > 200)) return setError('La tasa debe estar entre 0 y 200%')

    setGuardando(true)
    try {
      await api.editarCuenta(cuenta.id, {
        cupo_total: cupo === '' ? null : Number(cupo),
        dia_corte: corte === '' ? null : Number(corte),
        dia_pago: pago === '' ? null : Number(pago),
        tasa_ea: tasa === '' ? null : Number(tasa),
      })
      onGuardada()
    } catch (err) {
      setError(err.message || 'No se pudo guardar')
    } finally {
      setGuardando(false)
    }
  }

  const campo = 'w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent'

  return (
    <Hoja onCerrar={onClose}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Datos de "{cuenta.nombre}"</h2>
        <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>

      <label className="block mb-3">
        <span className="text-xs text-ink-soft">Cupo total</span>
        <input
          value={cupo}
          onChange={(e) => setCupo(e.target.value.replace(/[^\d.]/g, ''))}
          inputMode="decimal"
          placeholder="Ej. 5000000"
          aria-label="Cupo total"
          className={`${campo} mt-1`}
        />
      </label>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <label className="block">
          <span className="text-xs text-ink-soft">Día de corte</span>
          <input
            value={corte}
            onChange={(e) => setCorte(e.target.value.replace(/\D/g, '').slice(0, 2))}
            inputMode="numeric"
            placeholder="1-31"
            aria-label="Día de corte"
            className={`${campo} mt-1`}
          />
        </label>
        <label className="block">
          <span className="text-xs text-ink-soft">Día de pago</span>
          <input
            value={pago}
            onChange={(e) => setPago(e.target.value.replace(/\D/g, '').slice(0, 2))}
            inputMode="numeric"
            placeholder="1-31"
            aria-label="Día de pago"
            className={`${campo} mt-1`}
          />
        </label>
      </div>
      <label className="block mb-2">
        <span className="text-xs text-ink-soft">Tasa efectiva anual % (opcional)</span>
        <input
          value={tasa}
          onChange={(e) => setTasa(e.target.value.replace(/[^\d.]/g, ''))}
          inputMode="decimal"
          placeholder="Ej. 28.5"
          aria-label="Tasa efectiva anual"
          className={`${campo} mt-1`}
        />
      </label>
      <p className="text-xs text-ink-soft mb-4">
        Lo usamos para calcular tu utilización, el pago mínimo y los intereses estimados, y para avisarte antes de la fecha de pago.
      </p>

      {error && <p role="alert" className="text-sm text-danger mb-3">{error}</p>}

      <button
        onClick={guardar}
        disabled={guardando}
        className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
      >
        {guardando ? 'Guardando...' : 'Guardar'}
      </button>
    </Hoja>
  )
}
