import { useEffect, useState } from 'react'
import { Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { mensajeDeError } from '../lib/mensajes'

// «Mis reglas de correo»: lo que le enseñaste a leer. Son solo tuyas; se pueden borrar una por una.
export function describirRegla(r) {
  const datos = [r.marca_monto && 'el monto', r.marca_comercio && 'el nombre'].filter(Boolean).join(' y ')
  const quien = r.tipo === 'income' ? 'ingreso' : 'gasto'
  return `Lee ${datos || 'el correo'} como ${quien}`
}

export default function MisReglasCorreo() {
  const [reglas, setReglas] = useState(null)
  const [error, setError] = useState('')
  const [confirmando, setConfirmando] = useState(null)
  const [borrando, setBorrando] = useState(null)

  useEffect(() => {
    let vivo = true
    api.reglasCorreo()
      .then((r) => vivo && setReglas(Array.isArray(r) ? r : []))
      .catch((e) => vivo && setError(mensajeDeError(e)))
    return () => {
      vivo = false
    }
  }, [])

  async function borrar(r) {
    if (borrando) return
    setBorrando(r.id)
    setError('')
    try {
      await api.borrarReglaCorreo(r.id)
      setReglas((lista) => (lista || []).filter((x) => x.id !== r.id))
      setConfirmando(null)
    } catch (e) {
      setError(mensajeDeError(e))
    } finally {
      setBorrando(null)
    }
  }

  return (
    <div data-testid="mis-reglas-correo">
      <p className="mt-1 text-xs text-ink-soft">
        Son los correos que le enseñaste a leer. Valen solo para ti. Si borras una, ese tipo de correo vuelve a leerse como antes.
      </p>
      {error && <p className="mt-2 text-sm text-danger" role="alert">{error}</p>}
      {reglas && reglas.length === 0 && (
        <p className="mt-4 text-sm text-ink-soft">Aún no le has enseñado ninguno. Lo haces desde un correo por revisar sin monto.</p>
      )}
      <ul className="mt-3 flex flex-col gap-2">
        {(reglas || []).map((r) => (
          <li key={r.id} className="rounded-xl bg-paper p-3" data-testid={`regla-${r.id}`}>
            <p className="text-sm font-semibold break-words">{r.esqueleto_asunto}</p>
            <p className="text-xs text-ink-soft break-words">{r.remitente_dominio} · {describirRegla(r)}</p>
            <p className="text-xs text-ink-soft">{r.usos ? `La usé ${r.usos} ${r.usos === 1 ? 'vez' : 'veces'}` : 'Aún no la he usado'}</p>
            {confirmando === r.id ? (
              <div className="mt-2 flex gap-2">
                <button type="button" onClick={() => borrar(r)} disabled={borrando === r.id} className="flex-1 min-h-[44px] rounded-xl bg-danger text-paper-raised text-sm font-semibold disabled:opacity-50">
                  Sí, borrar
                </button>
                <button type="button" onClick={() => setConfirmando(null)} className="flex-1 min-h-[44px] rounded-xl border border-line text-sm text-ink-soft">
                  Conservar
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmando(r.id)}
                aria-label={`Borrar la regla ${r.esqueleto_asunto}`}
                className="mt-2 min-h-[44px] px-3 rounded-xl border border-line text-sm text-ink-soft flex items-center gap-1.5"
              >
                <Trash2 size={16} aria-hidden="true" /> Borrar
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
