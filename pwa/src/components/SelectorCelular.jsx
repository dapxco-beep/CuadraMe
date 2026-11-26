import { Chip } from './ui'

/** «¿Qué celular usas?»: dos (o tres) opciones grandes. El valor es 'ios' | 'android' | 'ninguno'. */
export default function SelectorCelular({ valor, onElegir, conNinguno = false, className = '' }) {
  const opciones = [
    { id: 'ios', texto: 'iPhone' },
    { id: 'android', texto: 'Android' },
    ...(conNinguno ? [{ id: 'ninguno', texto: 'Solo computador' }] : []),
  ]
  return (
    <div role="radiogroup" aria-label="¿Qué celular usas?" className={`flex flex-wrap gap-2 ${className}`}>
      {opciones.map((o) => (
        <Chip key={o.id} rol="radio" activo={valor === o.id} onClick={() => onElegir(o.id)} data-testid={`celular-${o.id}`}>
          {o.texto}
        </Chip>
      ))}
    </div>
  )
}
