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

// Poses de salud financiera (aparte de las seis de la marca): de «normal» a «muy mal». Los brazos van cayendo y la cara se apaga.
const POSES_SALUD = {
  neutral: { ojos: 'abiertos', boca: 'plana', cejas: 0, bi: 14, bd: 14 },
  cansado: { ojos: 'caidos', boca: 'plana', cejas: -1, bi: 4, bd: 4 },
  mal: { ojos: 'abiertos', boca: 'triste', cejas: -1, bi: 0, bd: 0 },
  critico: { ojos: 'x', boca: 'ondulada', cejas: -1, bi: -6, bd: -6 },
}

// Estados de salud financiera (ver lib/saludFinanciera.js). Cada uno elige pose, qué tan apagado se ve y qué lleva puesto.
export const ESTADOS_SALUD = {
  radiante: { pose: 'celebrando', filtro: 'none', extras: ['aura', 'brillos'] },
  bien: { pose: 'feliz', filtro: 'none', extras: ['brillo'] },
  regular: { pose: 'neutral', filtro: 'saturate(.9)', extras: [] },
  cansado: { pose: 'cansado', filtro: 'saturate(.68) brightness(.97)', extras: ['gota'] },
  mal: { pose: 'mal', filtro: 'saturate(.46) brightness(.95)', extras: ['gota', 'curita'] },
  critico: { pose: 'critico', filtro: 'saturate(.25) brightness(.9)', extras: ['curita', 'grieta', 'gota'], giro: -5 },
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
    if (tipo === 'x') {
      return (
        <g key={ex} strokeWidth="1.8" {...TRAZO}>
          <line x1={ex - 3} y1="38.8" x2={ex + 3} y2="44.4" />
          <line x1={ex + 3} y1="38.8" x2={ex - 3} y2="44.4" />
        </g>
      )
    }
    if (tipo === 'caidos') {
      return (
        <g key={ex} className="cu-ojos">
          <circle cx={ex} cy="42" r="3.9" fill="#fff" />
          <circle cx={ex} cy="43" r="2" fill={TINTA} />
          <rect x={ex - 4.4} y="37" width="8.8" height="4.2" className="cu-relleno-cuerpo" />
          <line x1={ex - 4} y1="41.2" x2={ex + 4} y2="41.2" strokeWidth="1.4" {...TRAZO} />
        </g>
      )
    }
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
    case 'plana':
      return <line x1="25.4" y1="52" x2="32.6" y2="52" strokeWidth="1.8" {...TRAZO} />
    case 'ondulada':
      return <path d="M23.6 52.6Q26.3 49.6 29 52.6T34.4 52.6" strokeWidth="1.8" {...TRAZO} />
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
export default function Cuadri({ pose = 'feliz', estado, size = 64, animar = true, className = '', titulo, siempre = false }) {
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
  const E = ESTADOS_SALUD[estado]
  const poseFinal = E ? E.pose : pose
  const P = POSES_SALUD[poseFinal] || POSES_CUADRI[poseFinal] || POSES_CUADRI.feliz

  return (
    <svg
      ref={ref}
      viewBox="-10 0 84 72"
      width={size}
      height={Math.round((size * 72) / 84)}
      className={`cuadri ${!quieto && visible ? 'cuadri-anima' : ''} ${className}`}
      data-pose={poseFinal in POSES_CUADRI || poseFinal in POSES_SALUD ? poseFinal : 'feliz'}
      data-estado={E ? estado : undefined}
      style={E ? { filter: E.filtro, transform: E.giro ? `rotate(${E.giro}deg)` : undefined, transition: 'filter .4s' } : undefined}
      role={titulo ? 'img' : undefined}
      aria-label={titulo}
      aria-hidden={titulo ? undefined : true}
      focusable="false"
    >
      {E?.extras.includes('aura') && <circle cx="32" cy="36" r="34" className="cu-relleno-ficha" opacity=".2" />}
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
        {E?.extras.includes('curita') && (
          <g transform="rotate(-32 17 17)">
            <rect x="8" y="13.5" width="18" height="7" rx="3.4" fill="#f1d3a8" stroke={TINTA} strokeWidth="0.9" />
            <rect x="14.5" y="13.5" width="5" height="7" fill="#e3b985" />
          </g>
        )}
        {E?.extras.includes('grieta') && <path d="M32 6L28.4 14L33.4 19.2L27.6 27.5" strokeWidth="1.5" {...TRAZO} />}
      </g>
      {E?.extras.includes('gota') && <path d="M50 26C50 26 46.4 30.6 46.4 33.2a3.6 3.6 0 0 0 7.2 0C53.6 30.6 50 26 50 26Z" fill="#7fc4ff" stroke="#3b8fd4" strokeWidth=".8" />}
      {E?.extras.includes('brillos') && [[-3, 14], [64, 26], [60, 3]].map(([x, y], i) => (
        <path key={i} d={`M${x} ${y - 3.4}L${x + 1} ${y - 1}L${x + 3.4} ${y}L${x + 1} ${y + 1}L${x} ${y + 3.4}L${x - 1} ${y + 1}L${x - 3.4} ${y}L${x - 1} ${y - 1}Z`} className="cu-relleno-ficha" />
      ))}
      {E?.extras.includes('brillo') && <path d="M62 4L63.2 7L66.2 8.2L63.2 9.4L62 12.4L60.8 9.4L57.8 8.2L60.8 7Z" className="cu-relleno-ficha" />}
    </svg>
  )
}

export { POSES }
