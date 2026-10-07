import { ICONO } from '../lib/tokens'

// Único punto de entrada de íconos de la interfaz (familia lucide-react).
//  - tamaños con nombre: sm 16 (dentro de texto), md 20 (estándar), lg 24 (protagonista)
//  - un solo grosor de trazo, para que ningún ícono se vea más pesado que otro
//  - decorativo por defecto (aria-hidden); pasa `titulo` si el ícono es lo único que dice algo
// Los emojis quedan SOLO para lo que elige la persona (ícono de cuenta o categoría) y los logros del ahorcado.
export default function Icono({ icono: Componente, tam = 'md', titulo, trazo = 1.9, className = '', ...resto }) {
  if (!Componente) return null
  const px = typeof tam === 'number' ? tam : ICONO[tam] || ICONO.md
  return (
    <Componente
      size={px}
      strokeWidth={trazo}
      className={`shrink-0 ${className}`}
      aria-hidden={titulo ? undefined : 'true'}
      role={titulo ? 'img' : undefined}
      aria-label={titulo}
      {...resto}
    />
  )
}
