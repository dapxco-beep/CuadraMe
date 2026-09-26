import { useState } from 'react'
import { api } from '../lib/api'

const iconos = ['🏦', '💜', '💵', '💳', '📈']
const tipos = [
  { id: 'ahorro', label: 'Ahorros' },
  { id: 'efectivo', label: 'Efectivo' },
  { id: 'credito', label: 'Crédito' },
  { id: 'inversion', label: 'Inversión' },
]

export default function CrearCuenta({ onCreada }) {
  const [nombre, setNombre] = useState('')
  const [tipo, setTipo] = useState('ahorro')
  const [icono, setIcono] = useState('🏦')
  const [saldo, setSaldo] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre a tu cuenta')

    setGuardando(true)
    try {
      const cuenta = await api.crearCuenta({
        nombre: nombre.trim(),
        tipo,
        icono,
        saldo: Number(saldo) || 0,
      })
      onCreada(cuenta)
    } catch (err) {
      setError(err.message || 'No se pudo crear la cuenta')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col justify-center px-8 py-10">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold">Crea tu primera cuenta</h1>
        <p className="text-sm text-ink-soft mt-1">Bancolombia, Nequi, efectivo... la que uses más</p>
      </div>

      <div className="flex gap-2 justify-center mb-5">
        {iconos.map((ic) => (
          <button
            key={ic}
            onClick={() => setIcono(ic)}
            className={`w-12 h-12 rounded-2xl border-2 flex items-center justify-center text-xl ${
              icono === ic ? 'border-accent bg-accent-soft' : 'border-line'
            }`}
          >
            {ic}
          </button>
        ))}
      </div>

      <input
        value={nombre}
        onChange={(e) => setNombre(e.target.value)}
        placeholder="Nombre de la cuenta (ej. Bancolombia Ahorro)"
        className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
      />

      <input
        value={saldo}
        onChange={(e) => setSaldo(e.target.value.replace(/\D/g, ''))}
        inputMode="numeric"
        placeholder="Saldo actual (opcional)"
        className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-3"
      />

      <div className="grid grid-cols-2 gap-2 mb-5">
        {tipos.map((t) => (
          <button
            key={t.id}
            onClick={() => setTipo(t.id)}
            className={`rounded-2xl border py-3 text-sm font-medium ${
              tipo === t.id ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-danger mb-3">{error}</p>}

      <button
        onClick={guardar}
        disabled={guardando}
        className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] active:scale-[0.98] transition-transform disabled:opacity-60"
      >
        {guardando ? 'Creando...' : 'Continuar'}
      </button>
    </div>
  )
}
