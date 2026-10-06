import { useState } from 'react'
import { X } from 'lucide-react'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'
import SelectorCuenta from './SelectorCuenta'
import Hoja from './Hoja'
import CamposCuentaNueva, { CAMPOS_VACIOS } from './CamposCuentaNueva'
import { datosCuentaNueva, validarTarjetaNueva } from '../lib/cuentaNueva'

// Hoja para crear la cuenta de un banco detectado ("Crear cuenta Nequi"): usa el
// mismo selector de cuenta de siempre, con el banco ya elegido.
// onCreada(cuenta) se llama cuando la cuenta ya existe y el contexto de cuentas se recargó.
export default function CrearCuentaBanco({ banco, onClose, onCreada }) {
  const { recargar } = useCuentas()
  const [nombre, setNombre] = useState(banco || '')
  const [tipo, setTipo] = useState('ahorro')
  const [icono, setIcono] = useState('🏦')
  const [moneda, setMoneda] = useState('COP')
  const [campos, setCampos] = useState(CAMPOS_VACIOS)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function crear() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre a tu cuenta')
    if (tipo === 'credito') {
      const problema = validarTarjetaNueva(campos)
      if (problema) return setError(problema)
    }
    setGuardando(true)
    try {
      const cuenta = await api.crearCuenta(datosCuentaNueva({ nombre, tipo, icono, moneda, ...campos }))
      await recargar?.()
      onCreada?.(cuenta)
    } catch (err) {
      setError(err.message || 'No se pudo crear la cuenta')
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onClose} ariaLabel={`Crear cuenta ${banco || ""}`.trim()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{banco ? `Crear cuenta ${banco}` : 'Nueva cuenta'}</h2>
          <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
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
        <CamposCuentaNueva tipo={tipo} valores={campos} onCambio={setCampos} />
        {error && <p className="text-sm text-danger mb-3" role="alert">{error}</p>}
        <button
          onClick={crear}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60"
        >
          {guardando ? 'Creando...' : 'Crear cuenta'}
        </button>
    </Hoja>
  )
}
