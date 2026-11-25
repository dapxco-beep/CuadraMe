import { Check, Heart, LayoutGrid, Leaf, PiggyBank, Wallet } from 'lucide-react'
import { PERFILES } from '../lib/perfilesUso'
import { useModoMenu } from '../lib/modoSimple'

const ICONOS = { esencial: Leaf, gastos: Wallet, ahorro: PiggyBank, juntos: Heart, todo: LayoutGrid }

/** «¿Cómo quieres usar CuadraMe?»: elige un perfil ya armado y el menú se acomoda solo. Se puede cambiar cuando quieras. */
export default function SelectorPerfilUso({ className = '' }) {
  const { perfil, setPerfil } = useModoMenu()
  return (
    <section className={className} aria-label="Cómo quieres usar CuadraMe" data-testid="selector-perfil-uso">
      <p className="text-sm font-medium">¿Cómo quieres usar CuadraMe?</p>
      <p className="text-xs text-ink-soft mt-0.5">Elige uno y el menú muestra solo lo que te sirve. No se borra nada: lo demás queda en «Más funciones».</p>
      <div role="radiogroup" aria-label="Perfil de uso" className="mt-3 grid gap-2">
        {PERFILES.map((p) => {
          const Icono = ICONOS[p.id] || LayoutGrid
          const activo = perfil === p.id
          return (
            <button
              key={p.id}
              type="button"
              role="radio"
              aria-checked={activo}
              onClick={() => setPerfil(p.id)}
              className={`w-full text-left flex items-start gap-3 rounded-2xl border p-3 min-h-[64px] ${activo ? 'border-accent bg-accent-soft' : 'border-line bg-paper-raised'}`}
            >
              <span className="w-9 h-9 rounded-xl bg-paper flex items-center justify-center shrink-0 text-accent" aria-hidden="true">
                <Icono size={20} />
              </span>
              <span className="flex-1 min-w-0">
                <span className="block text-sm font-semibold">{p.nombre}</span>
                <span className="block text-xs text-ink-soft leading-snug mt-0.5">{p.desc}</span>
              </span>
              {activo && <Check size={20} className="text-accent shrink-0 mt-1" aria-hidden="true" />}
            </button>
          )
        })}
      </div>
    </section>
  )
}
