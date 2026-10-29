import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Users } from 'lucide-react'
import { api } from '../lib/api'
import { useDialogos } from '../lib/DialogosContext'
import { compartirMovimientoEnParche } from '../lib/hogares'

/**
 * «Compartir en un parche» para un gasto que ya registraste: eliges el parche y listo. Se divide en partes iguales entre
 * quienes están en el parche; tú pagaste todo, así que los demás te deben su parte (la ves en el parche).
 * Tu movimiento queda como lo pagaste: no se crea otro ni se cambia tu saldo.
 */
export default function CompartirEnParche({ movimiento, className = '' }) {
  const { avisar } = useDialogos() || {}
  const [parches, setParches] = useState(null) // null = cargando
  const [compartidoEn, setCompartidoEn] = useState([])
  const [elegido, setElegido] = useState('')
  const [enviando, setEnviando] = useState(false)

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

  if (movimiento.tipo !== 'expense' || parches === null) return null

  async function compartir() {
    setEnviando(true)
    try {
      const r = await compartirMovimientoEnParche(elegido, movimiento)
      avisar?.(`Compartido en ${r.parche}`, 'ok')
      await cargar()
    } catch (e) {
      avisar?.(e.status === 409 ? 'Este gasto ya está compartido en un parche.' : e.message || 'No se pudo compartir. Intenta de nuevo.')
    }
    setEnviando(false)
  }

  if (compartidoEn.length > 0) {
    return (
      <section className={`rounded-2xl border border-line bg-paper-raised p-4 ${className}`} aria-label="Compartido en un parche" data-testid="compartido-en-parche">
        <p className="text-sm font-semibold flex items-center gap-2"><Users size={16} aria-hidden="true" /> Compartido en {compartidoEn.map((x) => x.nombre).join(', ')}</p>
        <p className="text-xs text-ink-soft mt-1">Tú pagaste todo; en el parche ves cuánto te debe cada uno.</p>
        <Link to={`/hogares/${compartidoEn[0].hogar_id}`} className="mt-2 inline-block text-sm font-semibold text-accent min-h-11 leading-[44px]">Ver el parche</Link>
      </section>
    )
  }

  if (parches.length === 0) {
    return (
      <section className={`rounded-2xl border border-dashed border-line p-4 ${className}`} aria-label="Compartir en un parche">
        <p className="text-sm font-semibold flex items-center gap-2"><Users size={16} aria-hidden="true" /> ¿Fue con otras personas?</p>
        <p className="text-xs text-ink-soft mt-1">Crea un parche con tu pareja, tu casa o tus amigos y comparte este gasto: ves quién le debe a quién.</p>
        <Link to="/hogares" className="mt-2 inline-block text-sm font-semibold text-accent min-h-11 leading-[44px]">Crear un parche</Link>
      </section>
    )
  }

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
      <p className="text-[11px] text-ink-soft mt-2">Se divide en partes iguales entre quienes están en el parche. Tú pagaste todo: ellos te deben su parte.</p>
      <button onClick={compartir} disabled={!elegido || enviando} className="mt-3 w-full min-h-11 rounded-2xl bg-ink text-paper text-sm font-semibold disabled:opacity-40">
        {enviando ? 'Compartiendo…' : 'Compartir'}
      </button>
    </section>
  )
}
