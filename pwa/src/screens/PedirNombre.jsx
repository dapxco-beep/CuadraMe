import { useEffect, useRef, useState } from 'react'
import { UserRound } from 'lucide-react'
import Icono from '../components/Icono'
import { Boton } from '../components/ui'
import Cuadri from '../brand/Cuadri'
import { errorNombre, limpiarNombre, useNombre } from '../lib/nombre'
import { useMostrarCuadri } from '../lib/cuadri'
import { mensajeDeError } from '../lib/mensajes'

// «¿Cómo te llamamos?»: aparece UNA vez, antes del primer uso (y a quien ya tenía cuenta y no lo ha
// respondido). Pide solo el nombre —nada de teléfono ni cédula— y se puede dejar para después.
// Prellenado con el nombre de pila que viene de Google ("Daniel", no "DANIEL ALFONSO PARRADO").
export default function PedirNombre({ onListo }) {
  const { sugerido, guardar, omitir } = useNombre()
  const [conCuadri] = useMostrarCuadri()
  const [texto, setTexto] = useState(sugerido)
  const [tocado, setTocado] = useState(false)
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const campo = useRef(null)
  const editado = useRef(false)

  // Si el nombre sugerido llega después de abrir, se prellena (salvo que la persona ya escribió).
  useEffect(() => {
    if (!editado.current) setTexto(sugerido)
  }, [sugerido])

  useEffect(() => {
    campo.current?.focus() // foco inicial: se puede escribir de una
  }, [])

  async function enviar(e) {
    e.preventDefault()
    const problema = errorNombre(texto)
    if (problema) {
      setError(problema)
      setTocado(true)
      campo.current?.focus()
      return
    }
    setGuardando(true)
    setError('')
    try {
      await guardar(limpiarNombre(texto))
      onListo()
    } catch (err) {
      setError(mensajeDeError(err, 'No pudimos guardar tu nombre. Intenta de nuevo.'))
      setGuardando(false)
    }
  }

  async function ahoraNo() {
    setGuardando(true)
    try {
      await omitir()
    } catch {
      // sin red: igual se continúa; la próxima vez se vuelve a preguntar
    }
    onListo()
  }

  return (
    <div className="flex-1 flex flex-col justify-center px-8 py-10 pantalla-centrada screen-enter">
      <form onSubmit={enviar} className="flex flex-col gap-3 max-w-sm w-full mx-auto" noValidate>
        <div className="text-center mb-2">
          {conCuadri ? <Cuadri pose="hablando" size={88} className="mx-auto" /> : <Icono icono={UserRound} tam="lg" className="mx-auto text-accent" />}
          <h1 className="t-title text-xl mt-3">¿Cómo te llamamos?</h1>
        </div>
        <label htmlFor="nombre-preferido" className="sr-only">Cómo te llamamos</label>
        <input
          id="nombre-preferido"
          ref={campo}
          value={texto}
          onChange={(e) => {
            editado.current = true
            setTexto(e.target.value)
            if (tocado) setError(errorNombre(e.target.value))
          }}
          onBlur={() => {
            setTocado(true)
            if (texto) setError(errorNombre(texto))
          }}
          placeholder="Tu nombre"
          autoComplete="given-name"
          maxLength={80}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={error ? 'nombre-ayuda nombre-error' : 'nombre-ayuda'}
          className="rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-base outline-none focus:border-accent"
        />
        <p id="nombre-ayuda" className="text-xs text-ink-soft text-center">
          Así te saludamos en la app, los avisos y los correos.
        </p>
        {error && (
          <p id="nombre-error" role="alert" className="text-sm text-danger text-center">
            {error}
          </p>
        )}
        <Boton type="submit" bloque cargando={guardando} className="mt-2">
          Listo
        </Boton>
        <button type="button" onClick={ahoraNo} disabled={guardando} className="text-sm text-accent font-medium py-2 min-h-11">
          Ahora no
        </button>
      </form>
    </div>
  )
}
