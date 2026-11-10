import { useEffect, useRef, useState } from 'react'

// Fila que se desliza a la izquierda y muestra hasta 2 acciones de 72 px (p. ej. «Categoría» y «Borrar»).
// Solo con dedo o lápiz (el ratón ya tiene los botones de siempre). Pointer Events, sin librerías.
//  - touch-action: pan-y deja que el navegador siga haciendo el scroll vertical; solo tomamos el gesto
//    cuando el movimiento es claramente horizontal.
//  - Se cierra al tocar fuera, al deslizar de vuelta o con Escape.
//  - Accesibilidad: las acciones son las mismas que ya existen como botones en la fila, así que el panel
//    queda fuera del árbol de accesibilidad (aria-hidden + sin foco) mientras está cerrado.
//  - Una acción con `confirmar` pide un segundo toque («¿Seguro?») y vuelve a su texto a los 4 s.
// acciones: [{ id, texto, icono?, tono?: 'normal' | 'peligro', confirmar?: boolean, onClick }]
export const ANCHO_ACCION = 72
const UMBRAL_GESTO = 8 // px antes de decidir si el gesto es horizontal
const TIEMPO_CONFIRMAR_MS = 4000

export default function FilaDeslizable({ acciones = [], desactivada = false, children, className = '' }) {
  const lista = acciones.slice(0, 2)
  const total = lista.length * ANCHO_ACCION
  const [abierta, setAbierta] = useState(false)
  const [desplaz, setDesplaz] = useState(0) // px visibles de las acciones (0 = cerrada)
  const [arrastrando, setArrastrando] = useState(false)
  const [confirmando, setConfirmando] = useState(null) // id de la acción esperando el segundo toque
  const raiz = useRef(null)
  const gesto = useRef(null) // { x, y, base, decidido }
  const huboArrastre = useRef(false)

  const cerrar = () => {
    setAbierta(false)
    setDesplaz(0)
    setConfirmando(null)
  }

  // Tocar fuera cierra la fila abierta
  useEffect(() => {
    if (!abierta) return undefined
    const fuera = (e) => {
      if (raiz.current && !raiz.current.contains(e.target)) cerrar()
    }
    document.addEventListener('pointerdown', fuera, true)
    return () => document.removeEventListener('pointerdown', fuera, true)
  }, [abierta])

  // La confirmación del segundo toque caduca sola
  useEffect(() => {
    if (!confirmando) return undefined
    const t = setTimeout(() => setConfirmando(null), TIEMPO_CONFIRMAR_MS)
    return () => clearTimeout(t)
  }, [confirmando])

  if (!total || desactivada) return <div className={className}>{children}</div>

  function alBajar(e) {
    if (e.pointerType === 'mouse') return
    gesto.current = { x: e.clientX, y: e.clientY, base: abierta ? total : 0, decidido: false }
    huboArrastre.current = false
  }
  function alMover(e) {
    const g = gesto.current
    if (!g) return
    const dx = e.clientX - g.x
    const dy = e.clientY - g.y
    if (!g.decidido) {
      if (Math.abs(dx) < UMBRAL_GESTO && Math.abs(dy) < UMBRAL_GESTO) return
      if (Math.abs(dy) > Math.abs(dx)) {
        gesto.current = null // es scroll vertical: no se toca
        return
      }
      g.decidido = true
      huboArrastre.current = true
      setArrastrando(true)
      try {
        e.currentTarget.setPointerCapture?.(e.pointerId)
      } catch {
        // sin captura el gesto funciona igual mientras el dedo siga encima
      }
    }
    setDesplaz(Math.min(total, Math.max(0, g.base - dx)))
  }
  function alSoltar() {
    const g = gesto.current
    gesto.current = null
    if (!g || !g.decidido) return
    setArrastrando(false)
    // el clic que sigue al arrastre se ignora; si no llega, la marca caduca sola
    setTimeout(() => { huboArrastre.current = false }, 60)
    const abrir = desplaz > total / 2
    setAbierta(abrir)
    setDesplaz(abrir ? total : 0)
    if (!abrir) setConfirmando(null)
  }
  function tocar(a) {
    if (a.confirmar && confirmando !== a.id) {
      setConfirmando(a.id)
      return
    }
    cerrar()
    a.onClick?.()
  }

  return (
    <div
      ref={raiz}
      className={`relative overflow-hidden ${className}`}
      onKeyDown={(e) => e.key === 'Escape' && abierta && cerrar()}
      // Si hubo arrastre, el clic que sigue no debe abrir el detalle
      onClickCapture={(e) => {
        if (huboArrastre.current) {
          e.preventDefault()
          e.stopPropagation()
          huboArrastre.current = false
        } else if (abierta && !e.target.closest('[data-accion-fila]')) {
          // tocar la fila abierta solo la cierra
          e.preventDefault()
          e.stopPropagation()
          cerrar()
        }
      }}
    >
      <div
        data-testid="acciones-fila"
        aria-hidden={!abierta}
        className="absolute inset-y-0 right-0 flex"
        style={{ width: total }}
      >
        {lista.map((a) => {
          const esperando = confirmando === a.id
          return (
            <button
              key={a.id}
              type="button"
              data-accion-fila={a.id}
              tabIndex={abierta ? 0 : -1}
              onClick={() => tocar(a)}
              style={{ width: ANCHO_ACCION }}
              className={`flex flex-col items-center justify-center gap-1 text-[12px] font-semibold px-1 ${
                a.tono === 'peligro' || esperando ? 'bg-danger text-paper-raised' : 'bg-accent text-paper-raised'
              }`}
            >
              {!esperando && a.icono}
              <span>{esperando ? '¿Seguro?' : a.texto}</span>
            </button>
          )
        })}
      </div>
      <div
        data-testid="contenido-fila"
        onPointerDown={alBajar}
        onPointerMove={alMover}
        onPointerUp={alSoltar}
        onPointerCancel={alSoltar}
        className="relative bg-paper"
        style={{
          touchAction: 'pan-y',
          transform: desplaz ? `translateX(-${desplaz}px)` : undefined,
          transition: arrastrando ? 'none' : 'transform 160ms ease-out',
        }}
      >
        {children}
      </div>
    </div>
  )
}
