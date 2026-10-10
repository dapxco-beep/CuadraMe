import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Compass, Play } from 'lucide-react'
import { useAuth } from '../lib/AuthContext'
import {
  debeAbrirseSolo, guardarRecorrido, leerRecorrido, sePuedeRetomar, TOTAL_PASOS,
} from '../lib/recorrido'
import Icono from './Icono'
import Recorrido from './Recorrido'

/**
 * Puerta de entrada al recorrido «Conoce CuadraMe en 1 minuto» (4 tarjetas). Es OPCIONAL: nunca se abre solo.
 *  - variante="inicio": una fila discreta bajo el camino de 3 pasos («Conoce CuadraMe en 1 minuto»); si lo
 *    dejó a medias dice «Seguir el recorrido». Desaparece al terminarlo o descartarlo.
 *  - variante="enlace": fila para Perfil y Ayuda: «Ver recorrido otra vez» (o «Continuar recorrido»).
 */
export default function RecorridoEntrada({ variante = 'enlace' }) {
  const { usuario } = useAuth() || {}
  const uid = usuario?.id || 'anon'
  const navegar = useNavigate()
  const [estado, setEstado] = useState(() => leerRecorrido(uid))
  const [abierto, setAbierto] = useState(() => variante === 'inicio' && debeAbrirseSolo(leerRecorrido(uid)))
  const [desde, setDesde] = useState(() => (leerRecorrido(uid).terminado ? 0 : leerRecorrido(uid).paso))

  function abrir() {
    const actual = leerRecorrido(uid)
    setDesde(actual.terminado ? 0 : actual.paso)
    setAbierto(true)
  }

  function alCerrar(motivo) {
    setAbierto(false)
    setEstado(leerRecorrido(uid))
    if (motivo === 'terminado') navegar('/')
  }

  const retomable = sePuedeRetomar(estado)

  return (
    <>
      {variante === 'inicio' ? (
        !estado.terminado &&
        !estado.saltado &&
        !abierto && (
          <section aria-label="Recorrido de CuadraMe" data-testid="recorrido-retomar" className="mx-6 mt-2">
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={abrir}
                className="min-h-11 flex items-center gap-2 text-sm font-semibold text-accent text-left"
              >
                <Icono icono={retomable ? Play : Compass} tam="sm" />
                {retomable ? 'Seguir el recorrido de 1 minuto' : 'Conoce CuadraMe en 1 minuto'}
              </button>
              <button
                type="button"
                onClick={() => setEstado(guardarRecorrido(uid, { saltado: true }))}
                className="min-h-11 px-2 text-xs font-medium text-ink-soft"
              >
                No, gracias
              </button>
            </div>
          </section>
        )
      ) : (
        <section className="mx-6 mt-6">
          <button
            type="button"
            onClick={abrir}
            data-testid="ver-recorrido"
            className="w-full flex items-center gap-3 rounded-2xl bg-paper-raised border border-line px-4 py-3.5 text-left"
          >
            <Icono icono={Compass} tam="md" className="text-accent" />
            <span className="flex-1">
              <span className="block text-sm font-medium">
                {estado.terminado || estado.saltado || !estado.empezado ? 'Conoce CuadraMe en 1 minuto' : 'Continuar el recorrido'}
              </span>
              <span className="block text-xs text-ink-soft mt-0.5">
                {TOTAL_PASOS} tarjetas cortas: qué es, cómo traer tu información y cómo se ven tus gastos.
              </span>
            </span>
          </button>
        </section>
      )}
      {abierto && <Recorrido desde={desde} onCerrar={alCerrar} />}
    </>
  )
}
