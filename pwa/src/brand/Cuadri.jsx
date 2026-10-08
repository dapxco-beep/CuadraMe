// Cuadri, la mascota de CuadraMe: el isotipo con vida (cuadrado terracota con su ficha dorada ✓),
// con ojos, brazos y seis poses. Portado de la fuente de marca (marketing/.../marca.js) a React.
//
// Decisiones clave:
//  - SVG inline y ligero (~20 elementos), sin imágenes. La geometría de cada pose son datos (POSES_CUADRI).
//  - Los colores salen de las variables del tema (--c-brand, --c-brand-2, --c-brand-ink), así que en
//    modo oscuro cambia solo. Cara y manos usan tinta fija oscura porque el cuerpo es siempre vivo.
//  - La animación vive en CSS (brand/estilos.css, clase .cuadri-anima). El componente solo enciende
//    esa clase mientras está visible en pantalla (IntersectionObserver) y no hay "ahorro de datos";
//    con "reducir movimiento" el CSS la apaga. No hay temporizadores ni re-render en bucle.
//  - Decorativo por defecto (aria-hidden). Pasa `titulo` solo cuando Cuadri comunica algo por sí solo.
//  - Respeta «Mostrar a Cuadri» (Perfil → Apariencia): si la persona lo apagó, no pinta nada.
import { useEffect, useRef, useState } from 'react'
import { ahorroDeDatos, POSES, useMostrarCuadri } from '../lib/cuadri'

// Cada pose: ojos, boca, cejas (0 ninguna, 2 levantadas, -1 inclinadas de preocupación),
// ángulo de brazo izquierdo/derecho, si el brazo derecho saluda y si la ficha "salta".
export const POSES_CUADRI = {
  feliz: { ojos: 'abiertos', boca: 'sonrisa', cejas: 0, bi: 20, bd: 20, saluda: true },
  hablando: { ojos: 'abiertos', boca: 'habla', cejas: 0, bi: 25, bd: 25, saluda: true },
  sorprendido: { ojos: 'grandes', boca: 'o', cejas: 2, bi: 60, bd: 60 },
  preocupado: { ojos: 'abiertos', boca: 'triste', cejas: -1, bi: 10, bd: 10 },
  senalando: { ojos: 'abiertos', boca: 'sonrisa', cejas: 0, bi: 15, bd: 125 },
  celebrando: { ojos: 'felices', boca: 'grande', cejas: 0, bi: 150, bd: 150, pop: true },
}

const TINTA = '#221f19'
const TRAZO = { fill: 'none', stroke: TINTA, strokeLinecap: 'round' }

const Brazo = ({ x, ang, clase }) => (
  <g className={clase} transform={`rotate(${ang} ${x} 44)`}>
    <line x1={x} y1="44" x2={x} y2="57" className="cu-trazo-cuerpo" strokeWidth="4.6" strokeLinecap="round" />
  </g>
)

function Ojos({ tipo }) {
  return [19, 39].map((ex) => {
    if (tipo === 'felices') return <path key={ex} d={`M${ex - 3.6} 42.5Q${ex} 37.5 ${ex + 3.6} 42.5`} strokeWidth="1.8" {...TRAZO} />
    const r = tipo === 'grandes' ? 4.6 : 3.9
    const pr = r * 0.52
    return (
      <g key={ex} className="cu-ojos">
        <circle cx={ex} cy="41.5" r={r} fill="#fff" />
        <circle cx={ex} cy="41.8" r={pr} fill={TINTA} />
        <circle cx={ex + 0.9} cy="40.6" r={pr * 0.38} fill="#fff" />
      </g>
    )
  })
}

function Cejas({ tipo }) {
  if (!tipo) return null
  if (tipo === 2) return [19, 39].map((ex) => <line key={ex} x1={ex - 3.6} y1="32" x2={ex + 3.6} y2="32" strokeWidth="1.5" {...TRAZO} />)
  return [[19, -1], [39, 1]].map(([ex, lado]) => (
    <line key={ex} x1={ex - 3.6} y1={34.5 + lado * tipo * 1.6} x2={ex + 3.6} y2={34.5 - lado * tipo * 1.6} strokeWidth="1.5" {...TRAZO} />
  ))
}

function Boca({ tipo }) {
  switch (tipo) {
    case 'habla':
      return (
        <g className="cu-habla">
          <rect x="25.6" y="49" width="6.8" height="5.6" rx="3" fill={TINTA} />
          <ellipse cx="29" cy="53.2" rx="2" ry="1" fill="#e8823f" />
        </g>
      )
    case 'o':
      return <ellipse cx="29" cy="52" rx="2.4" ry="2.7" fill={TINTA} />
    case 'triste':
      return <path d="M24.8 53.5Q29 49.5 33.2 53.5" strokeWidth="1.8" {...TRAZO} />
    case 'grande':
      return (
        <>
          <path d="M24 49.5H34A5 5 0 0 1 24 49.5Z" fill={TINTA} />
          <path d="M26.4 52.4Q29 50.6 31.6 52.4A3 3 0 0 1 26.4 52.4Z" fill="#e8823f" />
        </>
      )
    default:
      return <path d="M24.8 50Q29 54 33.2 50" strokeWidth="1.8" {...TRAZO} />
  }
}

/**
 * Props:
 *  - pose: 'feliz' | 'hablando' | 'sorprendido' | 'preocupado' | 'senalando' | 'celebrando'
 *  - size: ancho en px (el alto se calcula; la proporción del dibujo es 84×72)
 *  - animar: false lo deja quieto; true (por defecto) anima solo cuando está a la vista
 *  - titulo: texto accesible si Cuadri comunica algo por sí solo; sin él es decorativo (aria-hidden)
 *  - siempre: ignora la preferencia «Mostrar a Cuadri» (solo para su propia vista previa)
 */
export default function Cuadri({ pose = 'feliz', size = 64, animar = true, className = '', titulo, siempre = false }) {
  const [mostrar] = useMostrarCuadri()
  const ref = useRef(null)
  const [visible, setVisible] = useState(true)
  const quieto = !animar || ahorroDeDatos()

  // Anima solo mientras se ve: un cambio de estado al entrar/salir, nunca en bucle.
  useEffect(() => {
    const el = ref.current
    if (quieto || !el || typeof IntersectionObserver === 'undefined') return undefined
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { threshold: 0.1 })
    io.observe(el)
    return () => io.disconnect()
  }, [quieto, mostrar])

  if (!mostrar && !siempre) return null
  const P = POSES_CUADRI[pose] || POSES_CUADRI.feliz

  return (
    <svg
      ref={ref}
      viewBox="-10 0 84 72"
      width={size}
      height={Math.round((size * 72) / 84)}
      className={`cuadri ${!quieto && visible ? 'cuadri-anima' : ''} ${className}`}
      data-pose={pose in POSES_CUADRI ? pose : 'feliz'}
      role={titulo ? 'img' : undefined}
      aria-label={titulo}
      aria-hidden={titulo ? undefined : true}
      focusable="false"
    >
      <ellipse className="cu-sombra" cx="32" cy="64" rx="19" ry="2.4" fill={TINTA} opacity=".25" />
      <g className="cu-cuerpo">
        <rect x="19" y="55" width="6" height="8" rx="3" className="cu-relleno-pie" />
        <rect x="39" y="55" width="6" height="8" rx="3" className="cu-relleno-pie" />
        <Brazo x={6} ang={P.bi} />
        <Brazo x={58} ang={-P.bd} clase={P.saluda ? 'cu-saluda' : ''} />
        <rect x="6" y="6" width="26" height="52" rx="10" className="cu-relleno-cuerpo" />
        <rect x="6" y="32" width="52" height="26" rx="10" className="cu-relleno-cuerpo" />
        <rect x="14" y="26" width="18" height="14" className="cu-relleno-cuerpo" />
        <g className={P.pop ? 'cu-pop' : ''}>
          <rect x="35" y="6" width="23" height="23" rx="7" className="cu-relleno-ficha" />
          <path d="M41.5 17.5L45 21L52 13.5" fill="none" className="cu-trazo-check" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
        </g>
        <Cejas tipo={P.cejas} />
        <Ojos tipo={P.ojos} />
        <ellipse cx="14" cy="48" rx="2.6" ry="1.8" className="cu-relleno-mejilla" />
        <ellipse cx="44" cy="48" rx="2.6" ry="1.8" className="cu-relleno-mejilla" />
        <Boca tipo={P.boca} />
      </g>
    </svg>
  )
}

export { POSES }
