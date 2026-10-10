import { useCallback, useEffect, useState } from 'react'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Check, Mail, Trash2, UserPlus, X } from 'lucide-react'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'

export default function Compartir() {
  const volver = useVolver('/perfil')
  const { cuentas } = useCuentas()
  const [cuentaId, setCuentaId] = useState(cuentas[0]?.id || '')
  const [invitaciones, setInvitaciones] = useState([])
  const [compartidos, setCompartidos] = useState([])
  const [pendientesMias, setPendientesMias] = useState([])
  const [email, setEmail] = useState('')
  const [rol, setRol] = useState('viewer')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.misInvitacionesPendientes().then(setPendientesMias).catch(() => {})
  }, [])

  const cargar = useCallback(async () => {
    if (!cuentaId) return
    try {
      const [inv, comp] = await Promise.all([
        api.invitacionesDeCuenta(cuentaId),
        api.compartidaCon(cuentaId),
      ])
      setInvitaciones(inv)
      setCompartidos(comp)
    } catch {
      // si falla se conserva lo ya mostrado; las acciones de abajo muestran su propio error
    }
  }, [cuentaId])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function invitar(e) {
    e.preventDefault()
    if (!email.trim()) return
    setEnviando(true)
    setError('')
    try {
      await api.invitarACuenta(cuentaId, email.trim(), rol)
      setEmail('')
      cargar()
    } catch (err) {
      setError(err.message || 'No se pudo enviar la invitación. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setEnviando(false)
    }
  }

  async function revocar(usuarioId) {
    await api.revocarAcceso(cuentaId, usuarioId)
    cargar()
  }

  async function responderInvitacion(id, aceptar) {
    await (aceptar ? api.aceptarInvitacion(id) : api.rechazarInvitacion(id))
    setPendientesMias((prev) => prev.filter((i) => i.id !== id))
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Compartir cuentas</h1>
      </header>

      {pendientesMias.length > 0 && (
        <section className="mx-6 mt-4">
          <h2 className="text-sm font-semibold mb-2">Te invitaron a una cuenta</h2>
          <div className="flex flex-col gap-2">
            {pendientesMias.map((inv) => (
              <div key={inv.id} className="rounded-2xl bg-accent-soft p-3.5 flex items-center gap-3">
                <Mail size={16} className="text-accent shrink-0" />
                <p className="flex-1 text-sm">
                  Acceso como <b>{inv.rol === 'editor' ? 'editor' : 'solo lectura'}</b>
                </p>
                <button
                  onClick={() => responderInvitacion(inv.id, true)}
                  className="w-11 h-11 rounded-full bg-accent text-white flex items-center justify-center shrink-0"
                 aria-label="Aceptar invitación">
                  <Check size={16} />
                </button>
                <button
                  onClick={() => responderInvitacion(inv.id, false)}
                  className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center shrink-0"
                 aria-label="Rechazar invitación">
                  <X size={16} />
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {cuentas.length > 0 && (
        <>
          <section className="mx-6 mt-6">
            <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Cuenta</p>
            <select
              value={cuentaId}
              onChange={(e) => setCuentaId(e.target.value)}
              className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm"
            >
              {cuentas.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </select>
          </section>

          <section className="mx-6 mt-6">
            <div className="flex items-center gap-2 mb-3">
              <UserPlus size={16} className="text-ink-soft" />
              <h2 className="text-[15px] font-semibold">Invitar a alguien</h2>
            </div>
            <form onSubmit={invitar} className="flex flex-col gap-2">
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                type="email"
                placeholder="Correo de la persona"
                className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent"
              />
              <div className="flex gap-2">
                {[
                  { id: 'viewer', label: 'Solo ver' },
                  { id: 'editor', label: 'Puede editar' },
                ].map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setRol(r.id)}
                    className={`flex-1 rounded-2xl py-2.5 text-sm font-semibold border ${
                      rol === r.id ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
              {error && <p className="text-xs text-danger">{error}</p>}
              <button
                type="submit"
                disabled={enviando}
                className="bg-accent text-white font-semibold rounded-2xl py-3 text-sm disabled:opacity-60"
              >
                {enviando ? 'Enviando...' : 'Enviar invitación'}
              </button>
            </form>
          </section>

          {(invitaciones.length > 0 || compartidos.length > 0) && (
            <section className="mx-6 mt-6">
              <h2 className="text-[15px] font-semibold mb-3">Acceso actual</h2>
              <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
                {compartidos.map((c) => (
                  <div key={c.id} className="flex items-center gap-3 px-4 py-3.5">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">Usuario compartido</p>
                      <p className="text-xs text-ink-soft">{c.rol === 'editor' ? 'Puede editar' : 'Solo ver'}</p>
                    </div>
                    <button onClick={() => revocar(c.usuario_id)} className="w-11 h-11 -mr-1.5 flex items-center justify-center text-danger shrink-0" aria-label="Quitar acceso">
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                {invitaciones
                  .filter((i) => i.estado === 'pendiente')
                  .map((i) => (
                    <div key={i.id} className="flex items-center gap-3 px-4 py-3.5">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{i.email_invitado}</p>
                        <p className="text-xs text-ink-soft">Invitación pendiente</p>
                      </div>
                    </div>
                  ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
