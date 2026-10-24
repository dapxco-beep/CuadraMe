import { useCallback, useEffect, useRef, useState } from 'react'
import { RefreshCw } from 'lucide-react'

// ═══ Jalar para refrescar ═════════════════════════════════════════════════
// Con el dedo arriba del todo de una lista, jalar hacia abajo y soltar vuelve a pedir los datos. Sirve en la
// app instalada (donde no hay botón de recargar del navegador). Solo con el dedo (touch), nunca con el mouse.
//
// Uso:  const jalar = useJalarParaRefrescar(() => recargar())
//       <div ref={jalar.ref} ...>{jalar.indicador} ...</div>
// `onRefrescar` puede devolver una promesa: el círculo gira hasta que termine.

const UMBRAL = 72 // px de jalón para que cuente
const MAX = 110 // lo más que baja el indicador

export function vibrar(ms = 12) {
  try {
    navigator.vibrate?.(ms) // donde el celular lo soporta; en iPhone/Safari no hace nada
  } catch {
    /* sin vibración */
  }
}

export function useJalarParaRefrescar(onRefrescar, { activo = true } = {}) {
  const [el, setEl] = useState(null)
  const [jalon, setJalon] = useState(0)
  const [refrescando, setRefrescando] = useState(false)
  const accion = useRef(onRefrescar)
  accion.current = onRefrescar
  const ocupado = useRef(false)

  const ref = useCallback((nodo) => setEl(nodo), [])

  useEffect(() => {
    if (!el || !activo) return undefined
    let y0 = null
    let distancia = 0

    const inicio = (e) => {
      if (ocupado.current || e.touches.length !== 1 || el.scrollTop > 0) return
      y0 = e.touches[0].clientY
      distancia = 0
    }
    const mueve = (e) => {
      if (y0 == null) return
      const dy = e.touches[0].clientY - y0
      if (dy <= 0 || el.scrollTop > 0) {
        y0 = null
        setJalon(0)
        return
      }
      distancia = Math.min(MAX, dy * 0.5) // resistencia: el dedo baja el doble de lo que baja el círculo
      setJalon(distancia)
    }
    const suelta = async () => {
      if (y0 == null) return
      y0 = null
      if (distancia >= UMBRAL * 0.5 && !ocupado.current) {
        ocupado.current = true
        vibrar(12)
        setRefrescando(true)
        setJalon(UMBRAL * 0.5)
        try {
          await accion.current?.()
        } catch {
          /* la pantalla ya muestra su propio error */
        }
        setTimeout(() => {
          ocupado.current = false
          setRefrescando(false)
          setJalon(0)
        }, 450)
      } else {
        setJalon(0)
      }
    }

    el.addEventListener('touchstart', inicio, { passive: true })
    el.addEventListener('touchmove', mueve, { passive: true })
    el.addEventListener('touchend', suelta, { passive: true })
    el.addEventListener('touchcancel', suelta, { passive: true })
    return () => {
      el.removeEventListener('touchstart', inicio)
      el.removeEventListener('touchmove', mueve)
      el.removeEventListener('touchend', suelta)
      el.removeEventListener('touchcancel', suelta)
    }
  }, [el, activo])

  const progreso = Math.min(1, jalon / (UMBRAL * 0.5))
  const indicador =
    jalon > 0 || refrescando ? (
      <div
        className="pointer-events-none flex justify-center overflow-visible"
        style={{ height: jalon, transition: jalon === 0 || refrescando ? 'height 0.25s ease' : 'none' }}
        data-testid="jalar-indicador"
        role="status"
        aria-label={refrescando ? 'Actualizando' : 'Suelta para actualizar'}
      >
        <span
          className="mt-1 w-9 h-9 rounded-full bg-paper-raised border border-line shadow flex items-center justify-center text-accent"
          style={{ opacity: Math.max(0.25, progreso), transform: `rotate(${progreso * 270}deg)` }}
        >
          <RefreshCw size={18} className={refrescando ? 'animate-spin' : ''} aria-hidden="true" />
        </span>
      </div>
    ) : null

  return { ref, indicador, refrescando }
}
