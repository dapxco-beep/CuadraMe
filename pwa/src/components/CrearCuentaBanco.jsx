import { useState } from 'react'
import { X } from 'lucide-react'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'
import SelectorCuenta from './SelectorCuenta'

// Hoja para crear la cuenta de un banco detectado ("Crear cuenta Nequi"): usa el
// mismo selector de cuenta de siempre, con el banco ya elegido.
// onCreada(cuenta) se llama cuando la cuenta ya existe y el contexto de cuentas se recargó.
export default function CrearCuentaBanco({ banco, onClose, onCreada }) {
  const { recargar } = useCuentas()
  const [nombre, setNombre] = useState(banco || '')
  const [tipo, setTipo] = useState('ahorro')
  const [icono, setIcono] = useState('🏦')
  const [moneda, setMoneda] = useState('COP')
  const [saldo, setSaldo] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function crear() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre a tu cuenta')
    setGuardando(true)
    try {
      const cuenta = await api.crearCuenta({ nombre: nombre.trim(), tipo, icono, moneda, saldo: Number(saldo) || 0 })
      await recargar?.()
      onCreada?.(cuenta)
    } catch (err) {
      setError(err.message || 'No se pudo crear la cuenta')
      setGuardando(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-end justify-center z-50 sheet-backdrop">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Crear cuenta ${banco || ''}`.trim()}
        className="w-full max-w-[480px] bg-paper rounded-t-[28px] p-6 pb-8 max-h-[90vh] overflow-y-auto sheet-content"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{banco ? `Crear cuenta ${banco}` : 'Nueva cuenta'}</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>
        <div className="mb-4">
          <SelectorCuenta
            nombre={nombre}
            setNombre={setNombre}
            tipo={tipo}
            setTipo={setTipo}
            setIcono={setIcono}
            moneda={moneda}
            setMoneda={setMoneda}
            bancoInicial={banco || ''}
          />
        </div>
        <input
          value={saldo}
          onChange={(e) => setSaldo(e.target.value.replace(/[^\d.]/g, ''))}
          inputMode="decimal"
          placeholder="Saldo actual (opcional)"
          aria-label="Saldo actual"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
        />
        {error && <p className="text-sm text-danger mb-3" role="alert">{error}</p>}
        <button
          onClick={crear}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
        >
          {guardando ? 'Creando...' : 'Crear cuenta'}
        </button>
      </div>
    </div>
  )
}
