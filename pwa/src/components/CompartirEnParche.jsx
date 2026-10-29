import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, Users } from 'lucide-react'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { useDialogos } from '../lib/DialogosContext'
import { compartirMovimientoEnParche } from '../lib/hogares'
import InputMonto from './InputMonto'

const MODOS = [
  { id: 'iguales', label: 'Iguales' },
  { id: 'montos', label: 'Montos' },
  { id: 'porcentajes', label: '%' },
]

/**
 * «Compartir en un parche» para un gasto que ya registraste. Lo normal es un toque: eliges el parche y se divide en
 * partes iguales entre todos; tú pagaste, así que los demás te deben su parte. Si no es así, «Cambiar cómo se divide»:
 * eliges entre quiénes y si es por montos o porcentajes. Tu movimiento no cambia ni se crea otro.
 */
export default function CompartirEnParche({ movimiento, className = '' }) {
  const { avisar } = useDialogos() || {}
  const [parches, setParches] = useState(null) // null = cargando
  const [compartidoEn, setCompartidoEn] = useState([])
  const [elegido, setElegido] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [detalle, setDetalle] = useState(null) // miembros del parche elegido
  const [abierto, setAbierto] = useState(false)
  const [entre, setEntre] = useState([]) // ids de miembros que dividen
  const [modo, setModo] = useState('iguales')
  const [valores, setValores] = useState({})

  const cargar = useCallback(async () => {
    try {
      const [ps, ya] = await Promise.all([
        Promise.resolve(api.hogares?.()).then((x) => x || []),
        Promise.resolve(api.parchesDeMovimiento?.(movimiento.id)).then((x) => x || []).catch(() => []),
      ])
      setParches(ps)
      setCompartidoEn(ya)
      setElegido((e) => e || (ps.length === 1 ? ps[0].id : ''))
    } catch {
      setParches([])
    }
  }, [movimiento.id])
  useEffect(() => {
    cargar()
  }, [cargar])

  // Los miembros del parche elegido: solo se piden cuando hacen falta (al abrir «Cambiar cómo se divide»).
  useEffect(() => {
    setDetalle(null)
    setEntre([])
    setValores({})
    setModo('iguales')
    if (!elegido || !abierto) return
    Promise.resolve(api.hogar?.(elegido)).then((h) => {
      if (!h) return
      setDetalle(h)
      setEntre((h.miembros || []).filter((m) => m.activo).map((m) => m.id))
    }).catch(() => {})
  }, [elegido, abierto])

  const miembros = useMemo(() => (detalle?.miembros || []).filter((m) => m.activo), [detalle])
  const total = Number(movimiento.monto) || 0
  const suma = entre.reduce((s, id) => s + (Number(valores[id]) || 0), 0)
  const falta = modo === 'montos' ? Math.round(total - suma) : modo === 'porcentajes' ? Math.round((100 - suma) * 100) / 100 : 0
  const repartoOk = entre.length > 0 && (modo === 'iguales' || falta === 0)

  if (movimiento.tipo !== 'expense' || parches === null) return null

  async function compartir() {
    setEnviando(true)
    try {
      const opciones = abierto && detalle
        ? { modo, participantes: entre.map((id) => ({ id, valor: modo === 'iguales' ? 1 : Number(valores[id]) || 0 })) }
        : {}
      const r = await compartirMovimientoEnParche(elegido, movimiento, opciones)
      avisar?.(`Compartido en ${r.parche}`, 'ok')
      await cargar()
    } catch (e) {
      avisar?.(e.status === 409 ? 'Este gasto ya está compartido en un parche.' : e.message || 'No se pudo compartir. Intenta de nuevo.')
    }
    setEnviando(false)
  }

  const alternar = (id) => setEntre((e) => (e.includes(id) ? e.filter((x) => x !== id) : [...e, id]))

  if (compartidoEn.length > 0) {
    return (
      <section className={`rounded-2xl border border-line bg-paper-raised p-4 ${className}`} aria-label="Compartido en un parche" data-testid="compartido-en-parche">
        <p className="text-sm font-semibold flex items-center gap-2"><Users size={16} aria-hidden="true" /> Compartido en {compartidoEn.map((x) => x.nombre).join(', ')}</p>
        <p className="text-xs text-ink-soft mt-1">Pagaste tú. En el parche ves lo que te debe cada uno.</p>
        <Link to={`/hogares/${compartidoEn[0].hogar_id}`} className="mt-2 inline-block text-sm font-semibold text-accent min-h-11 leading-[44px]">Ver el parche</Link>
      </section>
    )
  }

  if (parches.length === 0) {
    return (
      <section className={`rounded-2xl border border-dashed border-line p-4 ${className}`} aria-label="Compartir en un parche">
        <p className="text-sm font-semibold flex items-center gap-2"><Users size={16} aria-hidden="true" /> ¿Fue con otras personas?</p>
        <p className="text-xs text-ink-soft mt-1">Crea un parche y ves quién le debe a quién.</p>
        <Link to="/hogares" className="mt-2 inline-block text-sm font-semibold text-accent min-h-11 leading-[44px]">Crear un parche</Link>
      </section>
    )
  }

  const campo = 'w-28 rounded-xl border border-line bg-paper px-3 py-2 text-sm text-right tabular-nums outline-none focus:border-accent'
  return (
    <section className={`rounded-2xl border border-line bg-paper-raised p-4 ${className}`} aria-label="Compartir en un parche" data-testid="compartir-en-parche">
      <p className="text-sm font-semibold flex items-center gap-2"><Users size={16} aria-hidden="true" /> Compartir en un parche</p>
      <div className="mt-2 flex flex-wrap gap-2" role="radiogroup" aria-label="Parche">
        {parches.map((p) => (
          <button
            key={p.id}
            role="radio"
            aria-checked={elegido === p.id}
            onClick={() => setElegido(p.id)}
            className={`rounded-2xl border px-3.5 py-2 text-sm font-medium ${elegido === p.id ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper'}`}
          >
            {p.nombre}
          </button>
        ))}
      </div>

      {elegido && !abierto && (
        <p className="text-xs text-ink-soft mt-2">En partes iguales entre todos. Tú pagaste: ellos te deben su parte.</p>
      )}

      {elegido && (
        <button type="button" onClick={() => setAbierto((v) => !v)} aria-expanded={abierto} className="mt-2 min-h-11 inline-flex items-center gap-1 text-sm font-semibold text-accent">
          Cambiar cómo se divide <ChevronDown size={16} aria-hidden="true" className={abierto ? 'rotate-180' : ''} />
        </button>
      )}

      {elegido && abierto && (
        <div className="mt-1 flex flex-col gap-3" data-testid="como-se-divide">
          {!detalle && <p className="text-xs text-ink-soft" role="status">Cargando…</p>}
          {detalle && (
            <>
              <div>
                <p className="text-xs text-ink-soft font-medium uppercase tracking-wide mb-1.5">¿Entre quiénes?</p>
                <div className="flex flex-wrap gap-2">
                  {miembros.map((m) => (
                    <button key={m.id} aria-pressed={entre.includes(m.id)} onClick={() => alternar(m.id)}
                      className={`rounded-2xl border px-3 py-1.5 text-sm font-medium ${entre.includes(m.id) ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper'}`}>
                      {m.soy_yo ? 'Yo' : m.apodo}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Cómo se reparte">
                {MODOS.map((m) => (
                  <button key={m.id} role="radio" aria-checked={modo === m.id} onClick={() => setModo(m.id)}
                    className={`rounded-xl border py-2 text-sm font-semibold ${modo === m.id ? 'bg-accent-soft border-accent text-accent' : 'border-line bg-paper'}`}>
                    {m.label}
                  </button>
                ))}
              </div>
              {modo !== 'iguales' && (
                <ul className="flex flex-col gap-2">
                  {miembros.filter((m) => entre.includes(m.id)).map((m) => (
                    <li key={m.id} className="flex items-center gap-3">
                      <span className="flex-1 min-w-0 truncate text-sm">{m.soy_yo ? 'Yo' : m.apodo}</span>
                      <InputMonto entero={modo === 'montos'} aria-label={`${modo === 'montos' ? 'Monto' : 'Porcentaje'} de ${m.apodo}`} value={valores[m.id] || ''} onValor={(v) => setValores({ ...valores, [m.id]: v })} placeholder={modo === 'montos' ? 'Monto' : '%'} className={campo} />
                    </li>
                  ))}
                </ul>
              )}
              <p className={`text-xs ${repartoOk ? 'text-ink-soft' : 'text-danger'}`} role="status">
                {entre.length === 0
                  ? 'Elige al menos una persona.'
                  : modo === 'iguales'
                    ? `Cada uno pone ${formatMoneda(total / entre.length, movimiento.moneda || 'COP')}.`
                    : falta === 0
                      ? 'Listo: suma exacto.'
                      : modo === 'montos'
                        ? `${falta > 0 ? 'Faltan' : 'Sobran'} ${formatMoneda(Math.abs(falta), movimiento.moneda || 'COP')}.`
                        : `${falta > 0 ? 'Falta' : 'Sobra'} ${Math.abs(falta)}%.`}
              </p>
              <p className="text-[11px] text-ink-soft">
                ¿Pagó otra persona? Anótalo desde el parche, en «Nuevo gasto».{' '}
                <Link to={`/hogares/${elegido}/gasto`} className="text-accent font-semibold underline">Ir al parche</Link>
              </p>
            </>
          )}
        </div>
      )}

      <button onClick={compartir} disabled={!elegido || enviando || (abierto && (!detalle || !repartoOk))} className="mt-3 w-full min-h-11 rounded-2xl bg-ink text-paper text-sm font-semibold disabled:opacity-40">
        {enviando ? 'Compartiendo…' : 'Compartir'}
      </button>
    </section>
  )
}
