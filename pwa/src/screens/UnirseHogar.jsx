import { textoError } from '../lib/textoError'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { useDialogos } from '../lib/DialogosContext'

// Pantalla a la que llega quien recibe una invitación a un parche: ve el nombre, elige cómo lo verán y se une.
export default function UnirseHogar() {
  const { token } = useParams()
  const navigate = useNavigate()
  const { avisar } = useDialogos()
  const { usuario } = useAuth()
  const [inv, setInv] = useState(null)
  const [error, setError] = useState('')
  const [apodo, setApodo] = useState('')
  const [uniendo, setUniendo] = useState(false)

  useEffect(() => {
    api.verInvitacionHogar(token).then(setInv).catch((e) => setError(e.status === 404 ? 'Esta invitación no existe, ya se usó o venció. Pídele a quien te invitó una nueva.' : textoError(e, 'cargar la invitación')))
  }, [token])
  useEffect(() => {
    setApodo((a) => a || usuario?.nombrePila || usuario?.nombre || '')
  }, [usuario])

  async function unirme() {
    setUniendo(true)
    try {
      const r = await api.aceptarInvitacionHogar(token, apodo.trim())
      navigate(`/hogares/${r.id}`, { replace: true })
    } catch (e) {
      avisar(e.message || 'No se pudo unir al parche. Intenta de nuevo.')
      setUniendo(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto pb-10 screen-enter">
      <header className="px-5 pantalla-top pb-2">
        <p className="text-xs text-ink-soft font-semibold uppercase tracking-wide">CuadraMe · Parche</p>
        <h1 className="text-2xl font-semibold mt-1">Te invitaron a un parche</h1>
      </header>
      {error && (
        <div className="px-5 mt-4" role="alert">
          <p className="text-sm text-ink-soft">{error}</p>
          <button onClick={() => navigate('/hogares', { replace: true })} className="mt-3 text-sm text-accent font-medium">Ir a mis hogares</button>
        </div>
      )}
      {inv && (
        <div className="px-5 mt-4 flex flex-col gap-3">
          <div className="rounded-2xl border border-line bg-paper-raised p-4">
            <p className="text-lg font-semibold break-words">{inv.hogar}</p>
            <p className="text-xs text-ink-soft mt-1">Verás los gastos del parche y lo que se debe cada uno. Nadie ve tus cuentas ni tus movimientos.</p>
          </div>
          <label className="text-xs text-ink-soft font-medium uppercase tracking-wide">
            ¿Cómo te verán los demás?
            <input value={apodo} onChange={(e) => setApodo(e.target.value)} maxLength={40} placeholder="Tu nombre o apodo" className="mt-1 w-full rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm normal-case tracking-normal text-ink outline-none focus:border-accent" />
          </label>
          <button onClick={unirme} disabled={uniendo} className="w-full bg-ink text-paper rounded-2xl py-3.5 text-sm font-semibold disabled:opacity-40">
            {uniendo ? 'Uniéndote…' : 'Unirme al parche'}
          </button>
        </div>
      )}
    </div>
  )
}
