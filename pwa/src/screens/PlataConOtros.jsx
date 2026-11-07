import { Link } from 'react-router-dom'
import { ArrowLeft, ChevronRight, HandCoins, Split, UsersRound } from 'lucide-react'
import { useVolver } from '../lib/useVolver'

// Una sola puerta para la plata compartida. Antes eran cuatro entradas en el menú («Dividir», «Parche», «Vacas» y
// «Compartir») y la palabra «compartir» significaba dos cosas distintas. Cada necesidad tiene su tarjeta y un ejemplo.
export const OPCIONES = [
  {
    to: '/amigos',
    icono: Split,
    titulo: 'Dividir un gasto',
    ejemplo: 'Una cena, un paseo, un Airbnb: repartes lo que se pagó y ves quién te debe. Tu amigo no necesita CuadraMe.',
    boton: 'Ver quién me debe / a quién debo',
  },
  {
    to: '/hogares',
    icono: UsersRound,
    titulo: 'Parche',
    ejemplo: 'La casa, la pareja o los compañeros: cada quien con su cuenta y un libro común de gastos que se repiten.',
    boton: 'Ver mis parches',
  },
  {
    to: '/colectas',
    icono: HandCoins,
    titulo: 'Vaca',
    ejemplo: 'Poner plata entre varios para algo puntual: un regalo, una inscripción, un paseo. Ves quién ya puso y quién falta.',
    boton: 'Ver mis vacas',
  },
]

export default function PlataConOtros() {
  const volver = useVolver('/')
  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
        <button
          type="button"
          onClick={volver}
          className="w-11 h-11 shrink-0 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Volver"
        >
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-semibold">Plata con otros</h1>
      </header>
      <p className="mx-5 text-sm text-ink-soft">¿Qué quieres hacer?</p>

      <ul className="mx-5 mt-3 space-y-3">
        {OPCIONES.map(({ to, icono: Icono, titulo, ejemplo, boton }) => (
          <li key={to}>
            <Link to={to} className="block rounded-2xl bg-paper-raised border border-line p-4" data-testid={`opcion-${to.slice(1)}`}>
              <span className="flex items-center gap-3">
                <span className="w-10 h-10 rounded-full bg-accent-soft text-accent flex items-center justify-center shrink-0"><Icono size={20} aria-hidden="true" /></span>
                <span className="text-base font-semibold flex-1">{titulo}</span>
                <ChevronRight size={16} className="text-ink-soft" aria-hidden="true" />
              </span>
              <span className="block text-sm text-ink-soft mt-2">{ejemplo}</span>
              <span className="block text-sm font-semibold text-accent mt-2">{boton}</span>
            </Link>
          </li>
        ))}
      </ul>

      <p className="mx-5 mt-5 text-xs text-ink-soft">
        ¿Quieres que tu pareja o familia vea tus cuentas? Eso es otra cosa:{' '}
        <Link to="/compartir" className="underline font-semibold text-ink">dar acceso a mis cuentas</Link>.
      </p>
    </div>
  )
}
