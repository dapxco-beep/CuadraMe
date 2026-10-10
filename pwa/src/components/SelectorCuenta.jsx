import { useEffect, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { ENTIDADES_FINANCIERAS_CO, marcaDeEntidad } from '../lib/entidadesFinancierasCO'
import Bandera from './Bandera'

// Elegir con toques en vez de escribir: país → tipo de cuenta → banco o billetera.
// Lo único que se escribe a mano es el banco cuando no está en la lista.
// El país solo fija la moneda inicial y qué lista de bancos se ofrece; la moneda
// sigue siendo editable aparte (hay quien tiene una cuenta en USD en un banco local).

export const PAISES = [
  { id: 'CO', nombre: 'Colombia', moneda: 'COP' },
  { id: 'US', nombre: 'Estados Unidos', moneda: 'USD' },
  { id: 'EU', nombre: 'Europa', moneda: 'EUR' },
  { id: 'OTRO', nombre: 'Otro', moneda: null },
]

export const TIPOS_CUENTA = [
  { id: 'ahorro', label: 'Ahorros', icono: '🏦', sufijo: '' },
  { id: 'efectivo', label: 'Efectivo', icono: '💵', sufijo: '' },
  { id: 'credito', label: 'Tarjeta de crédito', icono: '💳', sufijo: ' Crédito' },
  { id: 'inversion', label: 'Inversión', icono: '📈', sufijo: ' Inversión' },
]

// Las que usa la mayoría; el resto queda detrás de "Ver todas".
const POPULARES = [
  'Bancolombia', 'Nequi', 'Daviplata', 'Davivienda', 'Nu Colombia', 'BBVA Colombia', 'Banco de Bogotá', 'Lulo Bank',
]

function Chip({ activo, onClick, children, className = '' }) {
  return (
    <button
      type="button"
      aria-pressed={activo}
      onClick={onClick}
      className={`rounded-2xl border px-3 py-2.5 text-sm font-medium min-h-[44px] transition-colors ${
        activo ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
      } ${className}`}
    >
      {children}
    </button>
  )
}

function ChipBanco({ nombre, activo, onClick }) {
  const marca = marcaDeEntidad(nombre)
  return (
    <button
      type="button"
      aria-pressed={activo}
      onClick={onClick}
      className={`flex items-center gap-2 rounded-2xl border px-2.5 py-2 text-left min-h-[48px] transition-colors ${
        activo ? 'bg-accent-soft border-accent' : 'border-line bg-paper-raised'
      }`}
    >
      <span
        aria-hidden="true"
        className="w-8 h-8 rounded-lg shrink-0 flex items-center justify-center text-[11px] font-extrabold"
        style={{ background: marca.bg, color: marca.fg }}
      >
        {marca.mono}
      </span>
      <span className="text-[13px] font-medium leading-tight">{nombre}</span>
    </button>
  )
}

// Pregunta en lenguaje simple al elegir un banco: cada opción explica en una línea qué es.
const PRODUCTOS = [
  { id: 'ahorro', titulo: 'Mi cuenta de ahorros o débito', explica: 'Gastas plata que ya tienes: cada pago se descuenta de tu saldo.' },
  { id: 'credito', titulo: 'Mi tarjeta de crédito', explica: 'Gastas plata del banco y la devuelves después: cada compra suma a lo que debes.' },
]

function PreguntaProducto({ tipo, onElegir }) {
  return (
    <section aria-label="Cuenta de ahorros o tarjeta de crédito" data-testid="pregunta-producto">
      <p className="text-xs text-ink-soft mb-1.5">¿Es tu cuenta de ahorros/débito o tu tarjeta de crédito?</p>
      <div className="grid gap-2" role="group" aria-label="¿Es tu cuenta de ahorros/débito o tu tarjeta de crédito?">
        {PRODUCTOS.map((p) => (
          <button
            key={p.id}
            type="button"
            aria-pressed={tipo === p.id}
            onClick={() => onElegir(p.id)}
            className={`text-left rounded-2xl border px-3.5 py-3 min-h-[44px] transition-colors ${
              tipo === p.id ? 'bg-accent-soft border-accent' : 'border-line bg-paper-raised'
            }`}
          >
            <span className={`block text-sm font-semibold ${tipo === p.id ? 'text-accent' : ''}`}>{p.titulo}</span>
            <span className="block text-xs text-ink-soft mt-0.5">{p.explica}</span>
          </button>
        ))}
      </div>
    </section>
  )
}

export default function SelectorCuenta({
  nombre, setNombre, tipo, setTipo, setIcono, moneda, setMoneda, mostrarMoneda = true, bancoInicial = '', onBanco,
}) {
  const [pais, setPais] = useState('CO')
  const [verTodas, setVerTodas] = useState(false)
  const [busqueda, setBusqueda] = useState('')
  // `bancoInicial` deja el banco ya elegido (p. ej. "Crear cuenta Nequi" desde Sincronización).
  const [banco, setBanco] = useState(bancoInicial)

  const tipoActual = TIPOS_CUENTA.find((t) => t.id === tipo) || TIPOS_CUENTA[0]

  // Quien usa el selector (formularios) se entera del banco para ofrecer luego «la otra cuenta del banco».
  useEffect(() => {
    onBanco?.(banco)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [banco])

  useEffect(() => {
    if (bancoInicial) setNombre(`${bancoInicial}${tipoActual.sufijo}`)
    // Solo al montar: después manda lo que el usuario toque.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const lista = useMemo(() => {
    if (!verTodas) return bancoInicial && !POPULARES.includes(bancoInicial) ? [bancoInicial, ...POPULARES] : POPULARES
    const q = busqueda.trim().toLowerCase()
    return ENTIDADES_FINANCIERAS_CO.filter((e) => e.toLowerCase().includes(q))
  }, [verTodas, busqueda])

  function elegirPais(p) {
    setPais(p.id)
    setBanco('')
    if (p.moneda) setMoneda(p.moneda)
  }

  function elegirTipo(t) {
    setTipo(t.id)
    setIcono?.(t.icono)
    if (t.id === 'efectivo') {
      setBanco('')
      setNombre('Efectivo')
    } else if (banco) {
      setNombre(`${banco}${t.sufijo}`)
    } else if (nombre === 'Efectivo') {
      setNombre('')
    }
  }

  function elegirBanco(b) {
    setBanco(b)
    setNombre(`${b}${tipoActual.sufijo}`)
  }

  const esEfectivo = tipo === 'efectivo'

  return (
    <div className="space-y-5">
      <section aria-label="País">
        <p className="text-xs text-ink-soft mb-1.5">¿De qué país es tu cuenta?</p>
        <div className="grid grid-cols-2 gap-2">
          {PAISES.map((p) => (
            <Chip key={p.id} activo={pais === p.id} onClick={() => elegirPais(p)}>
              <Bandera pais={p.id} className="inline-block align-[-2px] mr-1" /> {p.nombre}
            </Chip>
          ))}
        </div>
      </section>

      <section aria-label="Tipo de cuenta">
        <p className="text-xs text-ink-soft mb-1.5">¿Qué tipo de cuenta es?</p>
        <div className="grid grid-cols-2 gap-2">
          {TIPOS_CUENTA.map((t) => (
            <Chip key={t.id} activo={tipo === t.id} onClick={() => elegirTipo(t)}>
              <span aria-hidden="true">{t.icono}</span> {t.label}
            </Chip>
          ))}
        </div>
      </section>

      {!esEfectivo && pais === 'CO' && (
        <section aria-label="Banco o billetera">
          <p className="text-xs text-ink-soft mb-1.5">¿Cuál es tu banco o billetera?</p>
          {verTodas && (
            <div className="relative mb-2">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-soft" aria-hidden="true" />
              <input
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                placeholder="Buscar banco"
                aria-label="Buscar banco"
                className="w-full rounded-2xl border border-line bg-paper-raised pl-10 pr-4 py-3 text-sm outline-none focus:border-accent"
              />
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            {lista.map((b) => (
              <ChipBanco key={b} nombre={b} activo={banco === b} onClick={() => elegirBanco(b)} />
            ))}
          </div>
          {verTodas && lista.length === 0 && (
            <p className="text-xs text-ink-soft mt-2">No está en la lista: escríbelo abajo en el nombre de la cuenta.</p>
          )}
          <button
            type="button"
            onClick={() => setVerTodas((v) => !v)}
            className="mt-2 text-sm font-semibold text-accent min-h-[44px]"
          >
            {verTodas ? 'Ver menos' : 'Ver todas'}
          </button>
        </section>
      )}

      {banco && (tipo === 'ahorro' || tipo === 'credito') && <PreguntaProducto tipo={tipo} onElegir={(id) => elegirTipo(TIPOS_CUENTA.find((t) => t.id === id))} />}

      <section aria-label="Datos de la cuenta">
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder={
            esEfectivo ? 'Nombre de la cuenta (ej. Efectivo)' : 'Nombre de la cuenta (ej. Bancolombia Ahorros)'
          }
          aria-label="Nombre de la cuenta"
          className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
        />
        {!esEfectivo && pais !== 'CO' && (
          <p className="text-xs text-ink-soft mt-1.5">Escribe el nombre de tu banco o billetera.</p>
        )}
      </section>

      {mostrarMoneda && (
        <section aria-label="Moneda">
          <p className="text-xs text-ink-soft mb-1.5">Moneda</p>
          <div className="flex gap-2" role="group" aria-label="Moneda de la cuenta">
            {['COP', 'USD', 'EUR'].map((m) => (
              <Chip key={m} activo={moneda === m} onClick={() => setMoneda(m)} className="flex-1">
                {m}
              </Chip>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
