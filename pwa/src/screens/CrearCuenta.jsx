import { useState } from 'react'
import { Mail, Sparkles, Wallet } from 'lucide-react'
import { api } from '../lib/api'
import { EncabezadoMarca } from '../brand/Marca'
import SelectorCuenta, { TIPOS_CUENTA } from '../components/SelectorCuenta'
import AgregarOtraDelBanco from '../components/AgregarOtraDelBanco'
import CamposCuentaNueva, { CAMPOS_VACIOS } from '../components/CamposCuentaNueva'
import { datosCuentaNueva, productoAlterno, validarTarjetaNueva } from '../lib/cuentaNueva'
import { marcarRecorridoPendiente } from '../lib/recorrido'
import { useAuth } from '../lib/AuthContext'
import { useAlertaVisible } from '../lib/useAlertaVisible'

const PASOS_BIENVENIDA = [
  {
    icon: Wallet,
    titulo: 'Registra en segundos',
    texto: 'Agrega un gasto o ingreso a mano, por voz con Siri, o deja que la app lo sugiera sola.',
  },
  {
    icon: Mail,
    titulo: 'O que lo haga por ti',
    texto: 'Conecta tu Gmail y te sugerimos cada movimiento que llega de tu banco — tú solo apruebas.',
  },
  {
    icon: Sparkles,
    titulo: 'Entiende tus finanzas',
    texto: 'Presupuestos, metas de ahorro, y un medidor visual de qué tan bien vas cada mes.',
  },
]

function Bienvenida({ onContinuar }) {
  return (
    <div className="flex-1 flex flex-col justify-center px-8 py-10 pantalla-centrada">
      <EncabezadoMarca titulo="Bienvenido a CuadraMe" lema="Esto es lo que puedes hacer" />

      <div className="flex flex-col gap-3 mb-8">
        {PASOS_BIENVENIDA.map((p, i) => (
          <div
            key={p.titulo}
            className="flex items-start gap-3 rounded-2xl bg-paper-raised border border-line p-4 stagger-item"
            style={{ '--stagger-i': i }}
          >
            <div className="w-10 h-10 rounded-full bg-accent-soft flex items-center justify-center shrink-0">
              <p.icon size={18} className="text-accent" />
            </div>
            <div>
              <p className="text-sm font-semibold">{p.titulo}</p>
              <p className="text-xs text-ink-soft mt-0.5">{p.texto}</p>
            </div>
          </div>
        ))}
      </div>

      <button
        onClick={onContinuar}
        className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] active:scale-[0.98] transition-transform"
      >
        Empezar — crea tu primera cuenta
      </button>
    </div>
  )
}

export default function CrearCuenta({ onCreada }) {
  const { usuario } = useAuth() || {}
  // Cuenta nueva: al entrar a Inicio se abre solo el recorrido guiado (una vez).
  function terminar(cuenta) {
    marcarRecorridoPendiente(usuario?.id || "anon")
    onCreada(cuenta)
  }

  const [paso, setPaso] = useState('bienvenida')
  const [nombre, setNombre] = useState('')
  const [tipo, setTipo] = useState('ahorro')
  const [icono, setIcono] = useState('🏦')
  const [campos, setCampos] = useState(CAMPOS_VACIOS)
  const [moneda, setMoneda] = useState('COP')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const refError = useAlertaVisible(error)
  // Banco elegido con los chips y lo ya creado de ese banco: tras crear una cuenta se ofrece
  // la otra (ahorros <-> tarjeta de crédito) sin volver a elegir banco.
  const [banco, setBanco] = useState('')
  const [creada, setCreada] = useState(null) // { cuenta, banco, tipo, nombre }
  const [hechos, setHechos] = useState({ banco: '', tipos: [] })
  const [version, setVersion] = useState(0) // remonta el selector al pasar a «la otra cuenta»

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre a tu cuenta')

    if (tipo === 'credito') {
      const problema = validarTarjetaNueva(campos)
      if (problema) return setError(problema)
    }
    setGuardando(true)
    try {
      const cuenta = await api.crearCuenta(datosCuentaNueva({ nombre, tipo, icono, moneda, ...campos }))
      const tiposDelBanco = hechos.banco === banco ? hechos.tipos : []
      const alterno = productoAlterno(tipo)
      if (banco && alterno && !tiposDelBanco.includes(alterno)) {
        setHechos({ banco, tipos: [...tiposDelBanco, tipo] })
        setCreada({ cuenta, banco, tipo, nombre: nombre.trim() })
      } else {
        terminar(cuenta)
      }
    } catch (err) {
      setError(err.message || 'No se pudo crear la cuenta')
    } finally {
      setGuardando(false)
    }
  }

  function agregarOtra() {
    const alterno = productoAlterno(creada.tipo)
    const t = TIPOS_CUENTA.find((x) => x.id === alterno)
    setTipo(alterno)
    setIcono(t.icono)
    setNombre(`${creada.banco}${t.sufijo}`)
    setCampos(CAMPOS_VACIOS)
    setError('')
    setCreada(null)
    setVersion((v) => v + 1)
  }

  if (paso === 'bienvenida') {
    return <Bienvenida onContinuar={() => setPaso('formulario')} />
  }

  if (creada) {
    return (
      <div className="flex-1 overflow-y-auto flex flex-col justify-center px-6 py-10 screen-enter">
        <AgregarOtraDelBanco
          banco={creada.banco}
          tipoCreado={creada.tipo}
          nombreCreada={creada.nombre}
          onAgregar={agregarOtra}
          onListo={() => terminar(creada.cuenta)}
          textoListo="No, continuar"
        />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto flex flex-col px-6 py-10 screen-enter">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold">Crea tu primera cuenta</h1>
        <p className="text-sm text-ink-soft mt-1">Elige la que uses más. Luego agregas las demás.</p>
      </div>

      <div className="mb-4">
        <SelectorCuenta
          key={version}
          bancoInicial={version > 0 ? banco : ''}
          onBanco={setBanco}
          nombre={nombre}
          setNombre={setNombre}
          tipo={tipo}
          setTipo={setTipo}
          setIcono={setIcono}
          moneda={moneda}
          setMoneda={setMoneda}
          mostrarMoneda={false}
        />
      </div>

      <CamposCuentaNueva tipo={tipo} valores={campos} onCambio={setCampos} />

      <div className="flex gap-2 mb-5" role="group" aria-label="Moneda de la cuenta">
        {['COP', 'USD', 'EUR'].map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={moneda === m}
            onClick={() => setMoneda(m)}
            className={`flex-1 rounded-2xl border py-2.5 text-sm font-medium min-h-[44px] ${
              moneda === m ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      {error && <p ref={refError} role="alert" className="text-sm text-danger mb-3">{error}</p>}

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
