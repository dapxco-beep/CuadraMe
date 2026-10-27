import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus } from 'lucide-react'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import { useDialogos } from '../lib/DialogosContext'
import InputMonto from '../components/InputMonto'

const MODOS = [
  { id: 'por_persona', label: 'Un valor por persona', ayuda: 'Ej. la inscripción: cada uno pone lo mismo.' },
  { id: 'meta_total', label: 'Una meta total', ayuda: 'Se reparte en partes iguales entre quienes elijas.' },
]

// Crear una colecta: nombre, cuánto, quiénes (tus contactos; no necesitan cuenta) y, si quieres,
// la cuenta donde entra la plata para que cada pago quede como ingreso.
export default function NuevaColecta() {
  const navigate = useNavigate()
  const { avisar } = useDialogos()
  const { cuentas } = useCuentas()
  const [nombre, setNombre] = useState('')
  const [modo, setModo] = useState('por_persona')
  const [valor, setValor] = useState('')
  const [contactos, setContactos] = useState([])
  const [elegidos, setElegidos] = useState([])
  const [incluirme, setIncluirme] = useState(false)
  const [cuentaId, setCuentaId] = useState('')
  const [fecha, setFecha] = useState('')
  const [nuevo, setNuevo] = useState(null)
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    api.contactosGasto().then(setContactos).catch(() => {})
  }, [])

  const personas = elegidos.length + (incluirme ? 1 : 0)
  const cuenta = cuentas.find((c) => c.id === cuentaId)
  const moneda = cuenta?.moneda || 'COP'
  const total = useMemo(() => {
    const v = Number(valor) || 0
    return modo === 'por_persona' ? v * personas : v
  }, [valor, modo, personas])

  const alternar = (id) => setElegidos((e) => (e.includes(id) ? e.filter((x) => x !== id) : [...e, id]))

  async function agregarContacto() {
    if (!nuevo?.nombre.trim()) return
    try {
      const c = await api.crearContactoGasto({ nombre: nuevo.nombre.trim(), telefono: nuevo.telefono.trim() })
      setContactos((cs) => [...cs, c])
      setElegidos((e) => [...e, c.id])
      setNuevo(null)
    } catch (e) {
      avisar(e.message || 'No se pudo agregar a la persona. Intenta de nuevo.')
    }
  }

  const puede = nombre.trim() && Number(valor) > 0 && personas > 0 && !guardando

  async function crear() {
    setGuardando(true)
    try {
      const r = await api.crearColecta({
        nombre: nombre.trim(),
        modo,
        valor: Number(valor),
        participantes: elegidos,
        incluirme,
        cuenta_id: cuentaId || undefined,
        moneda,
        fecha_limite: fecha ? `${fecha}T12:00:00` : undefined,
      })
      navigate(`/colectas/${r.id}`, { replace: true })
    } catch (e) {
      avisar(e.message || 'No se pudo crear la colecta. Revisa tu conexión e intenta de nuevo.')
      setGuardando(false)
    }
  }

  const campo = 'w-full rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm outline-none focus:border-accent'
  const chip = (activo) =>
    `rounded-2xl border px-3.5 py-2 text-sm font-medium ${activo ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'}`

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
        <button
          onClick={() => navigate('/colectas')}
          className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Volver"
        >
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-2xl font-semibold">Nueva colecta</h1>
      </header>

      <div className="px-5 mt-3 flex flex-col gap-3">
        <input
          aria-label="Nombre de la colecta"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="¿Para qué es? (ej. Inscripción del torneo)"
          maxLength={80}
          className={campo}
        />

        <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Tipo de colecta">
          {MODOS.map((m) => (
            <button
              key={m.id}
              role="radio"
              aria-checked={modo === m.id}
              onClick={() => setModo(m.id)}
              className={`rounded-2xl border px-3 py-3 text-sm font-semibold ${
                modo === m.id ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-ink-soft -mt-1">{MODOS.find((m) => m.id === modo).ayuda}</p>

        <InputMonto
          entero
          aria-label={modo === 'por_persona' ? 'Valor por persona' : 'Meta total'}
          value={valor}
          onValor={setValor}
          placeholder={modo === 'por_persona' ? 'Valor por persona' : 'Meta total'}
          className={`${campo} text-right tabular-nums`}
        />
      </div>

      <section className="px-5 mt-5">
        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">¿Quiénes ponen?</p>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setIncluirme((v) => !v)} aria-pressed={incluirme} className={chip(incluirme)}>
            Yo también
          </button>
          {contactos.map((c) => (
            <button key={c.id} onClick={() => alternar(c.id)} aria-pressed={elegidos.includes(c.id)} className={chip(elegidos.includes(c.id))}>
              {c.nombre}
            </button>
          ))}
          <button
            onClick={() => setNuevo({ nombre: '', telefono: '' })}
            className="rounded-2xl border border-dashed border-line px-3.5 py-2 text-sm text-ink-soft flex items-center gap-1"
          >
            <Plus size={16} /> Persona
          </button>
        </div>
        {nuevo && (
          <div className="mt-3 rounded-2xl border border-line bg-paper-raised p-3 flex flex-col gap-2">
            <input
              aria-label="Nombre de la persona"
              value={nuevo.nombre}
              onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })}
              placeholder="Nombre"
              className={campo}
            />
            <input
              aria-label="Celular de la persona"
              value={nuevo.telefono}
              onChange={(e) => setNuevo({ ...nuevo, telefono: e.target.value })}
              placeholder="Celular (opcional, para recordarle por WhatsApp)"
              inputMode="tel"
              className={campo}
            />
            <div className="flex gap-2">
              <button onClick={agregarContacto} className="flex-1 bg-ink text-paper rounded-2xl py-2.5 text-sm font-semibold">
                Agregar
              </button>
              <button onClick={() => setNuevo(null)} className="px-4 text-sm text-ink-soft">
                Cancelar
              </button>
            </div>
            <p className="text-[11px] text-ink-soft">No necesita cuenta: solo guardamos nombre y celular, en privado.</p>
          </div>
        )}
      </section>

      <section className="px-5 mt-5 flex flex-col gap-3">
        {cuentas.length > 0 && (
          <label className="text-xs text-ink-soft font-medium uppercase tracking-wide">
            ¿A qué cuenta entra la plata? (opcional)
            <select value={cuentaId} onChange={(e) => setCuentaId(e.target.value)} className={`${campo} mt-1 normal-case tracking-normal text-ink`}>
              <option value="">No registrar como ingreso</option>
              {cuentas.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre} ({c.moneda})
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="text-xs text-ink-soft font-medium uppercase tracking-wide">
          Fecha límite (opcional)
          <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} className={`${campo} mt-1 normal-case tracking-normal text-ink`} />
        </label>
      </section>

      <div className="px-5 mt-6">
        {personas > 0 && Number(valor) > 0 && (
          <p className="text-sm text-ink-soft mb-2 tabular-nums">
            {personas} {personas === 1 ? 'persona' : 'personas'} · meta {formatMoneda(total, moneda)}
          </p>
        )}
        <button onClick={crear} disabled={!puede} className="w-full bg-ink text-paper rounded-2xl py-3.5 text-sm font-semibold disabled:opacity-40">
          {guardando ? 'Creando…' : 'Crear colecta'}
        </button>
      </div>
    </div>
  )
}
