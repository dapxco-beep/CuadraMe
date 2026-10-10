import { leerMonto } from '../lib/cuentaNueva'
import InputMonto from './InputMonto'

const campo = 'w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mt-1'

// Estado inicial de los campos de "cuenta nueva" para usar con CamposCuentaNueva.
export const CAMPOS_VACIOS = { saldo: '', cupo: '', debes: '', corte: '', pago: '', tasa: '' }

// Saldo de una cuenta nueva. En una tarjeta de crédito cambia por completo: se
// pregunta cuánto debes (no "saldo") para que no se lea como saldo a favor.
export default function CamposCuentaNueva({ tipo, valores, onCambio }) {
  const set = (k, v) => onCambio({ ...valores, [k]: v })
  if (tipo !== 'credito') {
    return (
      <InputMonto
        value={valores.saldo}
        onValor={(v) => set('saldo', v)}
        placeholder="Saldo actual (opcional)"
        aria-label="Saldo actual"
        className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
      />
    )
  }
  const debes = leerMonto(valores.debes)
  return (
    <div className="mb-4" data-testid="campos-tarjeta">
      <label className="block mb-3">
        <span className="text-xs text-ink-soft">Cupo total</span>
        <span className="block text-[11px] text-ink-soft">El máximo que el banco te deja gastar con la tarjeta. Lo encuentras en la app de tu banco, en el detalle de la tarjeta.</span>
        <InputMonto
          value={valores.cupo}
          onValor={(v) => set('cupo', v)}
          placeholder="Ej. 5.000.000"
          aria-label="Cupo total"
          className={campo}
        />
      </label>
      <label className="block mb-3">
        <span className="text-xs text-ink-soft">¿Cuánto debes hoy?</span>
        <InputMonto
          value={valores.debes}
          onValor={(v) => set('debes', v)}
          placeholder="Lo que has gastado y aún no pagas"
          aria-label="Cuánto debes hoy"
          className={campo}
        />
        <span className="block text-[11px] text-ink-soft mt-1">
          Escríbelo en positivo{debes > 0 ? ` (guardamos que debes ${debes.toLocaleString('es-CO')})` : ''}. Si no debes nada, déjalo vacío.
        </span>
      </label>
      <div className="grid grid-cols-2 gap-3 mb-1">
        <label className="block">
          <span className="text-xs text-ink-soft">Día de corte (opcional)</span>
          <input
            value={valores.corte}
            onChange={(e) => set('corte', e.target.value.replace(/\D/g, '').slice(0, 2))}
            inputMode="numeric"
            placeholder="1-31"
            aria-label="Día de corte"
            className={campo}
          />
        </label>
        <label className="block">
          <span className="text-xs text-ink-soft">Día de pago (opcional)</span>
          <input
            value={valores.pago}
            onChange={(e) => set('pago', e.target.value.replace(/\D/g, '').slice(0, 2))}
            inputMode="numeric"
            placeholder="1-31"
            aria-label="Día de pago"
            className={campo}
          />
        </label>
      </div>
      <p className="text-[11px] text-ink-soft mb-3">
        El corte es el día en que el banco cierra tu extracto; el pago es la fecha límite para pagarlo sin intereses. Los dos los encuentras en la app de tu banco, en el detalle de la tarjeta o en tu extracto.
      </p>
      <label className="block">
        <span className="text-xs text-ink-soft">Tasa efectiva anual % (opcional)</span>
        <input
          value={valores.tasa}
          onChange={(e) => set('tasa', e.target.value.replace(/[^\d.]/g, ''))}
          inputMode="decimal"
          placeholder="Ej. 28.5"
          aria-label="Tasa efectiva anual"
          className={campo}
        />
      </label>
    </div>
  )
}
