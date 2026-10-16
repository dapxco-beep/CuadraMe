import { useCallback, useRef, useState } from 'react'

// Interacción común de los gráficos: tocar/arrastrar (touch y mouse) muestra la lectura de la columna más
// cercana; tocar o clic selecciona; ←/→ mueven, Enter/Espacio seleccionan, Esc limpia.
// `n` = columnas; `xDe(i)` = x de la columna i en unidades del viewBox de ancho `W`.
export function useLectura({ n, W, xDe, onElegir }) {
  const ref = useRef(null)
  const [activo, setActivo] = useState(null)
  const inicio = useRef(null)

  const indiceDe = useCallback((e) => {
    const r = ref.current?.getBoundingClientRect()
    if (!r || !r.width || n < 1) return null
    const x = ((e.clientX - r.left) / r.width) * W
    let mejor = 0
    for (let i = 1; i < n; i++) if (Math.abs(xDe(i) - x) < Math.abs(xDe(mejor) - x)) mejor = i
    return mejor
  }, [n, W, xDe])

  const manejadores = {
    onPointerDown(e) {
      inicio.current = { x: e.clientX, y: e.clientY, movido: false }
      const i = indiceDe(e)
      if (i !== null) setActivo(i)
    },
    onPointerMove(e) {
      const ini = inicio.current
      if (ini && Math.hypot(e.clientX - ini.x, e.clientY - ini.y) > 8) ini.movido = true
      if (e.pointerType === 'mouse' || ini) {
        const i = indiceDe(e)
        if (i !== null) setActivo(i)
      }
    },
    onPointerUp(e) {
      const ini = inicio.current
      inicio.current = null
      if (ini && !ini.movido) {
        const i = indiceDe(e)
        if (i !== null && onElegir) onElegir(i)
      }
    },
    onPointerCancel() { inicio.current = null },
    onPointerLeave(e) {
      if (e.pointerType === 'mouse') setActivo(null)
    },
    onBlur() { setActivo(null) },
    onKeyDown(e) {
      if (n < 1) return
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault()
        const der = e.key === 'ArrowRight'
        setActivo((a) => Math.max(0, Math.min(n - 1, (a === null ? (der ? -1 : n) : a) + (der ? 1 : -1))))
      } else if (e.key === 'Home') {
        e.preventDefault()
        setActivo(0)
      } else if (e.key === 'End') {
        e.preventDefault()
        setActivo(n - 1)
      } else if ((e.key === 'Enter' || e.key === ' ') && activo !== null) {
        e.preventDefault()
        if (onElegir) onElegir(activo)
      } else if (e.key === 'Escape') {
        setActivo(null)
      }
    },
  }
  return { ref, activo, setActivo, manejadores }
}
