import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, Users } from 'lucide-react'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'

const MODOS = [
  { id: 'iguales', label: 'Iguales' },
  { id: 'montos', label: 'Montos' },
  { id: 'porcentajes', label: '%' },
  { id: 'partes', label: 'Partes' },
]
const AYUDA_MODO = {
  iguales: 'Todos pagan lo mismo.',
  montos: 'Escribe cuánto le toca a cada uno; debe sumar el total.',
  porcentajes: 'Escribe el porcentaje de cada uno; debe sumar 100.',
  partes: 'Escribe cuántas partes le tocan a cada uno (ej. una pareja = 2).',
}

// Pantalla "Dividir este gasto". Llega desde Agregar con el monto, la descripción
// y la cuenta ya escritos (router state); aquí solo se decide con quién y cómo se reparte.
export default function DividirGasto() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const { cuentas, recargar: recargarCuentas } = useCuentas()
  const [monto, setMonto] = useState(String(state?.monto || ''))
  const [descripcion, setDescripcion] = useState(state?.descripcion || '')
  const [cuentaId, setCuentaId] = useState(state?.cuentaId || '')
  const [contactos, setContactos] = useState([])
  const [grupos, setGrupos] = useState([])
  const [grupoId, setGrupoId] = useState('')
  const [elegidos, setElegidos] = useState(['yo'])
  const [modo, setModo] = useState('iguales')
  const [valores, setValores] = useState({})
  const [pagador, setPagador] = useState('yo')
  const [registro, setRegistro] = useState('mi_parte')
  const [nuevo, setNuevo] = useState(null) // { nombre, telefono } mientras se agrega un contacto
  const [nombreGrupo, setNombreGrupo] = useState(null)
  const [vista, setVista] = useState({ partes: null, aviso: '' })
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  const cuenta = cuentas.find((c) => c.id === cuentaId) || cuentas[0]
  const moneda = cuenta?.moneda || 'COP'
  const nombres = useMemo(
    () => ({ yo: 'Tú', ...Object.fromEntries(contactos.map((c) => [c.id, c.nombre])) }),
    [contactos]
  )

  useEffect(() => {
    api.contactosGasto().then(setContactos).catch(() => {})
    api.gruposGasto().then(setGrupos).catch(() => {})
  }, [])

  const total = Number(monto) || 0
  const participantes = elegidos.map((id) => ({
    id,
    valor: Number(valores[id] ?? (modo === 'partes' ? 1 : 0)) || 0,
  }))
  const clavePeticion = JSON.stringify([total, moneda, modo, participantes])

  // Vista previa calculada por el servidor (misma matemática que al guardar),
  // con una pausa corta para no llamar en cada tecla.
  useEffect(() => {
    if (total <= 0 || elegidos.length === 0) {
      setVista({ partes: null, aviso: '' })
      return
    }
    const t = setTimeout(() => {
      api
        .calcularDivision({ total, moneda, modo, participantes })
        .then((r) => setVista({ partes: r.partes, aviso: '' }))
        .catch((e) => setVista({ partes: null, aviso: e.message }))
    }, 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clavePeticion])

  function alternar(id) {
    setGrupoId('')
    setElegidos((prev) => {
      const sale = prev.includes(id)
      if (sale && pagador === id) setPagador('yo')
      return sale ? prev.filter((x) => x !== id) : [...prev, id]
    })
  }

  function elegirGrupo(g) {
    if (grupoId === g.id) return setGrupoId('')
    setGrupoId(g.id)
    setElegidos(['yo', ...g.miembros])
  }

  async function agregarContacto() {
    if (!nuevo?.nombre.trim()) return setError('Escribe el nombre del contacto')
    setError('')
    try {
      const c = await api.crearContactoGasto({ nombre: nuevo.nombre.trim(), telefono: nuevo.telefono.trim() })
      setContactos((prev) => [...prev, c])
      setElegidos((prev) => [...prev, c.id])
      setNuevo(null)
    } catch (e) {
      setError(e.message || 'No se pudo crear el contacto')
    }
  }

  async function guardarGrupo() {
    const miembros = elegidos.filter((id) => id !== 'yo')
    if (!nombreGrupo?.trim()) return setError('Ponle un nombre al grupo')
    if (miembros.length === 0) return setError('Elige al menos un amigo para el grupo')
    setError('')
    try {
      const g = await api.crearGrupoGasto({ nombre: nombreGrupo.trim(), miembros })
      setGrupos((prev) => [...prev, g])
      setGrupoId(g.id)
      setNombreGrupo(null)
    } catch (e) {
      setError(e.message || 'No se pudo crear el grupo')
    }
  }

  async function guardar() {
    setError('')
    if (total <= 0) return setError('Ingresa un monto válido')
    if (!descripcion.trim()) return setError('Ingresa una descripción')
    if (!elegidos.some((id) => id !== 'yo')) return setError('Elige al menos a una persona más para dividir')
    if (vista.aviso) return setError(vista.aviso)
    if (!cuenta) return setError('Crea una cuenta primero')
    setGuardando(true)
    try {
      await api.crearGastoCompartido({
        descripcion: descripcion.trim(),
        total,
        moneda,
        modo,
        participantes,
        pagador_id: pagador,
        grupo_id: grupoId || undefined,
        registro: pagador === 'yo' ? registro : 'mi_parte',
        cuenta_id: cuenta.id,
        categoria: state?.categoria || undefined,
        fecha: state?.fecha ? `${state.fecha}T12:00:00` : undefined,
      })
      await recargarCuentas()
      navigate('/amigos')
    } catch (e) {
      setError(e.message || 'No se pudo guardar')
    } finally {
      setGuardando(false)
    }
  }

  const campo =
    'w-full rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm outline-none focus:border-accent'
  const miParte = vista.partes?.yo

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      <header className="px-5 pt-14 pb-2 flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="w-9 h-9 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Volver"
        >
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-2xl font-semibold">Dividir gasto</h1>
      </header>

      <div className="px-5 mt-3 grid grid-cols-[1fr_auto] gap-2">
        <input
          aria-label="Descripción"
          value={descripcion}
          onChange={(e) => setDescripcion(e.target.value)}
          placeholder="¿Qué se pagó? (ej. Cena, Airbnb)"
          className={campo}
        />
        <input
          aria-label="Total"
          value={monto}
          onChange={(e) => setMonto(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          placeholder="Total"
          className={`${campo} w-32 text-right tabular-nums`}
        />
      </div>
      {cuentas.length > 1 && (
        <div className="px-5 mt-2">
          <select
            aria-label="Cuenta"
            value={cuenta?.id || ''}
            onChange={(e) => setCuentaId(e.target.value)}
            className={campo}
          >
            {cuentas.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre} ({c.moneda})
              </option>
            ))}
          </select>
        </div>
      )}

      <section className="px-5 mt-5">
        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">¿Con quién?</p>
        {grupos.length > 0 && (
          <div className="flex gap-2 overflow-x-auto no-scrollbar mb-2">
            {grupos.map((g) => (
              <button
                key={g.id}
                onClick={() => elegirGrupo(g)}
                aria-pressed={grupoId === g.id}
                className={`shrink-0 rounded-2xl border px-3.5 py-2 text-xs font-semibold flex items-center gap-1.5 ${
                  grupoId === g.id ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
                }`}
              >
                <Users size={13} /> {g.nombre}
              </button>
            ))}
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          {['yo', ...contactos.map((c) => c.id)].map((id) => (
            <button
              key={id}
              onClick={() => alternar(id)}
              aria-pressed={elegidos.includes(id)}
              className={`rounded-2xl border px-3.5 py-2 text-sm font-medium ${
                elegidos.includes(id) ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper-raised'
              }`}
            >
              {nombres[id]}
            </button>
          ))}
          <button
            onClick={() => setNuevo({ nombre: '', telefono: '' })}
            className="rounded-2xl border border-dashed border-line px-3.5 py-2 text-sm text-ink-soft flex items-center gap-1"
          >
            <Plus size={14} /> Amigo
          </button>
        </div>

        {nuevo && (
          <div className="mt-3 rounded-2xl border border-line bg-paper-raised p-3 flex flex-col gap-2">
            <input
              aria-label="Nombre del amigo"
              value={nuevo.nombre}
              onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })}
              placeholder="Nombre"
              className={campo}
            />
            <input
              aria-label="Teléfono del amigo"
              value={nuevo.telefono}
              onChange={(e) => setNuevo({ ...nuevo, telefono: e.target.value })}
              placeholder="Celular (opcional, para cobrar por WhatsApp)"
              inputMode="tel"
              className={campo}
            />
            <div className="flex gap-2">
              <button onClick={agregarContacto} className="flex-1 bg-ink text-paper rounded-2xl py-2.5 text-sm font-semibold">
                Agregar amigo
              </button>
              <button onClick={() => setNuevo(null)} className="px-4 text-sm text-ink-soft">
                Cancelar
              </button>
            </div>
            <p className="text-[11px] text-ink-soft">Tu amigo no necesita tener cuenta: solo guardamos nombre y celular, en privado.</p>
          </div>
        )}

        {elegidos.filter((i) => i !== 'yo').length > 0 && !grupoId && (
          nombreGrupo === null ? (
            <button onClick={() => setNombreGrupo('')} className="mt-2 text-xs text-accent font-medium">
              Guardar estas personas como grupo (viaje, casa...)
            </button>
          ) : (
            <div className="mt-2 flex gap-2">
              <input
                aria-label="Nombre del grupo"
                value={nombreGrupo}
                onChange={(e) => setNombreGrupo(e.target.value)}
                placeholder="Ej. Viaje a Cartagena"
                className={campo}
              />
              <button onClick={guardarGrupo} className="shrink-0 bg-ink text-paper rounded-2xl px-4 text-sm font-semibold">
                Guardar
              </button>
            </div>
          )
        )}
      </section>

      <section className="px-5 mt-5">
        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">¿Cómo se divide?</p>
        <div className="flex gap-2">
          {MODOS.map((m) => (
            <button
              key={m.id}
              onClick={() => setModo(m.id)}
              aria-pressed={modo === m.id}
              className={`flex-1 rounded-2xl py-2.5 text-sm font-semibold border ${
                modo === m.id ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-ink-soft mt-2">{AYUDA_MODO[modo]}</p>

        <ul className="mt-3 flex flex-col gap-2">
          {elegidos.map((id) => (
            <li key={id} className="flex items-center gap-3 rounded-2xl border border-line bg-paper-raised px-4 py-2.5">
              <span className="flex-1 text-sm font-medium truncate">{nombres[id]}</span>
              {modo !== 'iguales' && (
                <input
                  aria-label={`Valor de ${nombres[id]}`}
                  value={valores[id] ?? (modo === 'partes' ? '1' : '')}
                  onChange={(e) => setValores({ ...valores, [id]: e.target.value.replace(/[^\d.]/g, '') })}
                  inputMode="decimal"
                  placeholder="0"
                  className="w-20 text-right bg-transparent border-b border-line outline-none tabular-nums text-sm"
                />
              )}
              <span className="w-24 text-right text-sm tabular-nums text-ink-soft">
                {vista.partes ? formatMoneda(vista.partes[id] ?? 0, moneda) : '—'}
              </span>
            </li>
          ))}
        </ul>
        {vista.aviso && <p role="alert" className="text-xs text-danger mt-2">{vista.aviso}</p>}
      </section>

      <section className="px-5 mt-5">
        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">¿Quién pagó?</p>
        <select aria-label="Quién pagó" value={pagador} onChange={(e) => setPagador(e.target.value)} className={campo}>
          {[...new Set(['yo', ...elegidos])].map((id) => (
            <option key={id} value={id}>
              {id === 'yo' ? 'Yo pagué' : `${nombres[id]} pagó`}
            </option>
          ))}
        </select>

        {pagador === 'yo' ? (
          <div className="mt-3 flex flex-col gap-2">
            {[
              { id: 'mi_parte', titulo: 'Registrar solo mi parte', detalle: miParte != null ? `Mi gasto: ${formatMoneda(miParte, moneda)}` : '' },
              { id: 'total', titulo: 'Registrar el total que pagué', detalle: 'El resto queda como "me deben"' },
            ].map((o) => (
              <button
                key={o.id}
                onClick={() => setRegistro(o.id)}
                aria-pressed={registro === o.id}
                className={`text-left rounded-2xl border px-4 py-3 ${
                  registro === o.id ? 'bg-accent-soft border-accent' : 'border-line bg-paper-raised'
                }`}
              >
                <p className="text-sm font-semibold">{o.titulo}</p>
                {o.detalle && <p className="text-xs text-ink-soft mt-0.5">{o.detalle}</p>}
              </button>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-soft mt-2">Como pagó otra persona, en tus movimientos solo queda tu parte.</p>
        )}
      </section>

      {error && <p role="alert" className="px-5 mt-4 text-sm text-danger">{error}</p>}

      <div className="px-5 mt-5">
        <button
          onClick={guardar}
          disabled={guardando}
          className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] active:scale-[0.98] transition-transform disabled:opacity-60"
        >
          {guardando ? 'Guardando...' : 'Guardar gasto dividido'}
        </button>
      </div>
    </div>
  )
}
