import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Compass, Play } from 'lucide-react'
import { useAuth } from '../lib/AuthContext'
import {
  debeAbrirseSolo, guardarRecorrido, leerRecorrido, sePuedeRetomar, TOTAL_PASOS,
} from '../lib/recorrido'
import Icono from './Icono'
import Recorrido from './Recorrido'
import { Boton } from './ui'

/**
 * Puerta de entrada al recorrido guiado.
 *  - variante="inicio": lo abre solo la primera vez que una cuenta NUEVA entra a Inicio; si la persona
 *    lo dejó a medias (o fue a «Probar ahora») muestra una tarjeta «Sigue con tu recorrido».
 *  - variante="enlace": fila para Perfil y Ayuda: «Ver recorrido otra vez» (o «Continuar recorrido»).
 * Al terminar, vuelve a Inicio, donde sigue la lista de «Primeros pasos».
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
        retomable &&
        !abierto && (
          <section aria-label="Recorrido de CuadraMe" data-testid="recorrido-retomar" className="mx-6 mt-3 tarjeta p-4">
            <div className="flex items-center gap-2">
              <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
                <Icono icono={Compass} tam="md" />
              </span>
              <div className="flex-1 min-w-0">
                <h2 className="t-h2">Sigue con tu recorrido</h2>
                <p className="t-apoyo">Vas en el paso {estado.paso + 1} de {TOTAL_PASOS}.</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-3">
              <Boton tam="sm" icono={Play} onClick={abrir}>Continuar</Boton>
              <button
                type="button"
                onClick={() => setEstado(guardarRecorrido(uid, { saltado: true }))}
                className="min-h-11 px-2 text-xs font-medium text-ink-soft"
              >
                Ahora no
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
                {estado.terminado || !estado.empezado ? 'Ver recorrido otra vez' : 'Continuar el recorrido'}
              </span>
              <span className="block text-xs text-ink-soft mt-0.5">
                Un paseo de {TOTAL_PASOS} pasos por todo lo que puedes hacer en CuadraMe.
              </span>
            </span>
          </button>
        </section>
      )}
      {abierto && <Recorrido desde={desde} onCerrar={alCerrar} />}
    </>
  )
}
