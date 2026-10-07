import { useEffect, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { CUERPO, FICHA, CHECK, FICHA_FUERA } from './geometria'

const CLAVE = 'cuadrame_splash_visto'

// El splash se muestra una vez por sesión (al abrir la app), no en cada recarga
// interna: repetirlo cansa. Si el almacenamiento falla, se muestra igual.
export function splashPendiente() {
  try {
    return sessionStorage.getItem(CLAVE) !== '1'
  } catch {
    return true
  }
}

// Pantalla de arranque: el cuerpo ya está (continúa el splash estático de
// index.html, sin parpadeo), la ficha cae en la muesca y "encaja", se dibuja
// el ✓ y asoma el nombre. Dura ~1.2 s en total. Con "reducir movimiento" se
// muestra el logo ya armado un instante y sale sin animación.
export default function SplashMarca({ onFin }) {
  const reducir = useReducedMotion()
  const [saliendo, setSaliendo] = useState(false)

  useEffect(() => {
    try {
      sessionStorage.setItem(CLAVE, '1')
    } catch {
      // sin almacenamiento: el splash volverá a salir en la próxima apertura
    }
    const t1 = setTimeout(() => setSaliendo(true), reducir ? 450 : 1050)
    const t2 = setTimeout(() => onFin?.(), reducir ? 470 : 1280)
    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
    }
  }, [reducir, onFin])

  const f = reducir ? { duration: 0 } : null

  return (
    <div
      role="presentation"
      className={`fixed inset-0 z-[100] flex flex-col items-center justify-center bg-paper ${saliendo ? 'splash-salida' : ''}`}
      style={{
        backgroundImage:
          'linear-gradient(to right, color-mix(in srgb, var(--color-ink) 5%, transparent) 1px, transparent 1px), linear-gradient(to bottom, color-mix(in srgb, var(--color-ink) 5%, transparent) 1px, transparent 1px)',
        backgroundSize: '22px 22px',
      }}
    >
      <svg viewBox="0 0 64 64" width="112" height="112" aria-hidden="true" focusable="false" style={{ overflow: 'visible' }}>
        <path d={CUERPO} fill="var(--c-brand)" />
        <motion.g
          initial={reducir ? false : { x: FICHA_FUERA.x, y: FICHA_FUERA.y, opacity: 0 }}
          animate={{ x: 0, y: 0, opacity: 1 }}
          transition={f || { type: 'spring', stiffness: 380, damping: 17, delay: 0.18 }}
        >
          <path d={FICHA} fill="var(--c-brand-2)" />
          <motion.path
            d={CHECK}
            fill="none"
            stroke="var(--c-brand-ink)"
            strokeWidth="3.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={reducir ? false : { pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={f || { duration: 0.28, delay: 0.55, ease: 'easeOut' }}
          />
        </motion.g>
      </svg>
      {/* El isotipo queda en el centro exacto (igual que el splash estático); el texto cuelga debajo */}
      <div className="absolute inset-x-0 text-center" style={{ top: 'calc(50% + 74px)' }}>
      <motion.p
        className="wordmark text-[34px] text-ink"
        initial={reducir ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={f || { duration: 0.3, delay: 0.7 }}
      >
        Cuadra<b>Me</b>
      </motion.p>
      <motion.p
        className="text-xs text-ink-soft mt-2"
        initial={reducir ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={f || { duration: 0.3, delay: 0.85 }}
      >
        Cuadra tus cuentas, simple y al día
      </motion.p>
      </div>
    </div>
  )
}
