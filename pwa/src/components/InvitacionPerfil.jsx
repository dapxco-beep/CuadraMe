import { useState } from 'react'
import { X } from 'lucide-react'
import { PERFILES } from '../lib/perfilesUso'
import { useModoMenu } from '../lib/modoSimple'
import { useAuth } from '../lib/AuthContext'

const CLAVE = 'cuadrame:perfil-invitacion'
const OPCIONES = PERFILES.filter((p) => p.id !== 'todo')

function descartada(uid) {
  try {
    return localStorage.getItem(`${CLAVE}:${uid}`) === '1'
  } catch {
    return false
  }
}

/** Una sola vez, en el Inicio: «¿Cómo quieres usar CuadraMe?». Elegir acomoda el menú; «Ahora no» no vuelve a insistir.
 *  No aparece si la persona ya eligió (en Perfil o aquí) o ya la descartó. */
export default function InvitacionPerfil({ className = '' }) {
  const { usuario } = useAuth() || {}
  const uid = usuario?.id || 'anon'
  const { elegido, setPerfil } = useModoMenu()
  const [oculta, setOculta] = useState(() => descartada(uid))
  if (elegido || oculta) return null

  const cerrar = () => {
    try {
      localStorage.setItem(`${CLAVE}:${uid}`, '1')
    } catch {
      /* sin almacenamiento: se oculta solo en esta sesión */
    }
    setOculta(true)
  }

  return (
    <section className={`card-marca bg-paper-raised border border-line p-4 ${className}`} aria-label="Cómo quieres usar CuadraMe" data-testid="invitacion-perfil">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">¿Cómo quieres usar CuadraMe?</p>
          <p className="text-xs text-ink-soft mt-0.5">Elige uno y te muestro solo lo que te sirve. Lo puedes cambiar en Perfil.</p>
        </div>
        <button type="button" onClick={cerrar} aria-label="Ahora no" className="min-h-11 min-w-11 -mr-2 -mt-2 flex items-center justify-center text-ink-soft">
          <X size={20} aria-hidden="true" />
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {OPCIONES.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => setPerfil(p.id)}
            className="min-h-11 px-3.5 rounded-full border border-line bg-paper text-sm font-semibold hover:border-accent"
          >
            {p.nombre}
          </button>
        ))}
      </div>
    </section>
  )
}
