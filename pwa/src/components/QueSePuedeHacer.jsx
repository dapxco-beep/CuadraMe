import { useState } from 'react'
import { Link } from 'react-router-dom'
import { X } from 'lucide-react'
import Icono from './Icono'
import { useAuth } from '../lib/AuthContext'
import { CATALOGO_ACCESOS } from '../lib/accesosInicio'

// «¿Qué puedes hacer en CuadraMe?»: las cinco cosas principales, cada una con una frase de qué gana la persona.
// En el Inicio se puede cerrar (se recuerda en este dispositivo); en Ayuda sale siempre (`fija`).

const CLAVE = 'cuadrame:que-se-puede-hacer-oculta'

export const COSAS = [
  { id: 'gasto', frase: 'Anota un gasto o ingreso en segundos' },
  { id: 'traer', frase: 'Trae tus movimientos del banco sin escribirlos uno por uno' },
  { id: 'dividir', frase: 'Divide una cuenta con amigos y mira quién te debe' },
  { id: 'metas', frase: 'Guarda plata poco a poco para algo que quieres' },
  { id: 'asistente', frase: 'Pregúntale a la IA cosas sobre tu plata' },
]

const leerOculta = (uid) => {
  try {
    return localStorage.getItem(`${CLAVE}:${uid}`) === '1'
  } catch {
    return false
  }
}

export default function QueSePuedeHacer({ fija = false, className = 'mx-6 mt-3' }) {
  const { usuario } = useAuth() || {}
  const uid = usuario?.id || 'anon'
  const [oculta, setOculta] = useState(() => !fija && leerOculta(uid))
  if (oculta) return null

  function cerrar() {
    try {
      localStorage.setItem(`${CLAVE}:${uid}`, '1')
    } catch {
      /* sin almacenamiento: se oculta solo en esta sesión */
    }
    setOculta(true)
  }

  const porId = Object.fromEntries(CATALOGO_ACCESOS.map((a) => [a.id, a]))
  return (
    <section className={`${className} tarjeta p-4`} aria-label="Qué puedes hacer en CuadraMe" data-testid="que-se-puede-hacer">
      <div className="flex items-start justify-between gap-2">
        <h2 className="t-h2">¿Qué puedes hacer en CuadraMe?</h2>
        {!fija && (
          <button type="button" onClick={cerrar} aria-label="Ocultar" className="min-w-11 min-h-11 -mt-3 -mr-3 flex items-center justify-center text-ink-soft">
            <Icono icono={X} tam="sm" />
          </button>
        )}
      </div>
      <ul className="mt-1 divide-y divide-line">
        {COSAS.map(({ id, frase }) => (
          <li key={id}>
            <Link to={porId[id].ruta} className="flex items-center gap-3 py-2.5 min-h-[48px]">
              <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
                <Icono icono={porId[id].icono} tam="md" />
              </span>
              <span className="t-cuerpo">{frase}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
