// Componentes de identidad CuadraMe. La geometría vive en ./geometria.js (compartida
// con el script de íconos y el canvas del Wrapped).
import { CUERPO, FICHA, CHECK } from './geometria'
import Cuadri from './Cuadri'
import { useMostrarCuadri } from '../lib/cuadri'

// Isotipo: el cuadrado al que le falta una pieza + la ficha que lo completa.
//  - cuadra=true  → la ficha dorada con ✓ está en su sitio ("tus cuentas cuadran")
//  - cuadra=false → solo queda el hueco punteado ("falta una pieza por cuadrar")
//  - mono         → una sola tinta (currentColor), para sobre fondos de color
// Es decorativo por defecto (aria-hidden); pasa `titulo` si va solo, sin texto al lado.
export function Isotipo({ size = 32, cuadra = true, mono = false, titulo, className = '', fichaClassName = '' }) {
  const cuerpo = mono ? 'currentColor' : 'var(--c-brand)'
  const ficha = mono ? 'currentColor' : 'var(--c-brand-2)'
  const check = mono ? 'var(--c-hero-b)' : 'var(--c-brand-ink)'
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={className}
      role={titulo ? 'img' : undefined}
      aria-label={titulo}
      aria-hidden={titulo ? undefined : true}
      focusable="false"
    >
      <path d={CUERPO} fill={cuerpo} />
      {cuadra ? (
        <g className={fichaClassName}>
          <path d={FICHA} fill={ficha} />
          <path d={CHECK} fill="none" stroke={check} strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      ) : (
        <path
          d={FICHA}
          fill="none"
          stroke={cuerpo}
          strokeWidth="2"
          strokeDasharray="3.5 3.5"
          strokeLinecap="round"
          opacity="0.9"
        />
      )}
    </svg>
  )
}

// Wordmark: "Cuadra" en tinta y "Me" en terracota, tipografía Sora apretada.
export function Wordmark({ className = '', mono = false }) {
  return (
    <span className={`wordmark ${className}`}>
      Cuadra{mono ? 'Me' : <b>Me</b>}
    </span>
  )
}

export function Logo({ size = 40, className = '', vertical = false }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${vertical ? 'flex-col' : ''} ${className}`}>
      <Isotipo size={size} />
      <Wordmark className="" />
    </span>
  )
}

// Sello de cuadre: la ficha dorada con ✓. Es la señal que dice "todo cuadra".
export function SelloCuadre({ size = 24, animar = true, className = '' }) {
  return (
    <span
      className={`inline-flex items-center justify-center shrink-0 ${animar ? 'sello-pop' : ''} ${className}`}
      style={{
        width: size,
        height: size,
        background: 'var(--c-brand-2)',
        borderRadius: `${size * 0.16}px ${size * 0.4}px ${size * 0.16}px ${size * 0.16}px`,
        color: 'var(--c-brand-ink)',
      }}
      aria-hidden="true"
    >
      <svg viewBox="0 0 24 24" width={size * 0.62} height={size * 0.62} fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 12.5l4.5 4.5L19 7" />
      </svg>
    </span>
  )
}

// Loader de marca: reemplaza los "Cargando..." de texto plano.
// Con «Mostrar a Cuadri» activado, quien espera ve a Cuadri contento; si no, el isotipo de siempre.
export function CargandoMarca({ texto = 'Cargando', className = '' }) {
  const [conCuadri] = useMostrarCuadri()
  return (
    <div role="status" className={`flex-1 flex flex-col items-center justify-center gap-3 ${className}`}>
      {conCuadri ? <Cuadri pose="feliz" size={72} /> : <Isotipo size={52} fichaClassName="ficha-loop" />}
      <p className="text-xs text-ink-soft">{texto}…</p>
    </div>
  )
}

// Ilustración de estado vacío: el cuadrado con su hueco punteado y, dentro del
// hueco, el ícono de lo que falta. Una sola idea, con variantes por contexto.
export function IlustracionVacia({ icono: Icono, size = 104, className = '' }) {
  return (
    <div className={`relative mx-auto ${className}`} style={{ width: size, height: size }} aria-hidden="true">
      <Isotipo size={size} cuadra={false} />
      {Icono && (
        <span
          className="absolute flex items-center justify-center text-accent"
          style={{ left: '55%', top: '9%', width: '36%', height: '36%' }}
        >
          <Icono size={size * 0.2} strokeWidth={2} />
        </span>
      )}
    </div>
  )
}

// Estado vacío de marca: Cuadri (o, si la persona lo apagó, la ilustración del hueco) + mensaje
// (+ acción opcional como children). `pose` por defecto señala hacia lo que falta; usa 'feliz'
// para vacíos buenos ("nada pendiente") y 'preocupado' solo si de verdad algo salió mal.
export function EstadoVacio({ icono, titulo, texto, className = 'mx-5 mt-6', pose = 'senalando', children }) {
  const [conCuadri] = useMostrarCuadri()
  return (
    <div className={`card-marca bg-paper-raised border border-line px-6 py-7 text-center ${className}`}>
      {conCuadri ? <Cuadri pose={pose} size={96} className="mx-auto" /> : <IlustracionVacia icono={icono} size={92} />}
      <p className="text-sm font-semibold mt-3">{titulo}</p>
      {texto && <p className="text-xs text-ink-soft mt-1">{texto}</p>}
      {children}
    </div>
  )
}

// Encabezado de marca para Login, registro y onboarding: papel cuadriculado,
// isotipo, wordmark y lema. `titulo` es el h1 (solo para lectores de pantalla,
// porque el wordmark ya es el título visual).
export function EncabezadoMarca({ titulo = 'CuadraMe', lema = 'Cuadra tus cuentas, simple y al día' }) {
  const [conCuadri] = useMostrarCuadri()
  return (
    <div className="patron-libro-suave card-marca bg-paper-raised border border-line text-center px-6 py-8 mb-7">
      {conCuadri ? (
        <Cuadri pose="feliz" size={96} className="mx-auto" />
      ) : (
        <Isotipo size={68} titulo="CuadraMe" className="mx-auto" fichaClassName="sello-pop" />
      )}
      <h1 className="sr-only">{titulo}</h1>
      <p className="wordmark text-[32px] mt-4 text-ink" aria-hidden="true">
        Cuadra<b>Me</b>
      </p>
      {lema && <p className="text-sm text-ink-soft mt-1.5">{lema}</p>}
    </div>
  )
}

// Cifra grande con símbolo de moneda pequeño y elevado. Recibe el texto ya
// formateado (y ya enmascarado si "ocultar saldos" está activo).
export function Monto({ texto, className = '' }) {
  const m = /^(-?\D*?)(\d.*)$/.exec(String(texto))
  if (!m) return <span className={className}>{texto}</span>
  // El lector de pantalla oye el monto completo ("$ 1.750.000"); lo visual va aparte.
  return (
    <span className={`tabular ${className}`}>
      <span className="sr-only">{texto}</span>
      <span aria-hidden="true">
        <span className="monto-simbolo">{m[1].replace(/\s/g, '')}</span>
        {m[2]}
      </span>
    </span>
  )
}
