import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

// Atajos de teclado para escritorio / iPad con teclado:
//   N = nuevo movimiento · / = buscar (si la pantalla tiene búsqueda)
//   G y luego I / M / P = ir a Inicio / Movimientos / Presupuesto
// No se disparan escribiendo en un campo, con Ctrl/Cmd/Alt, ni con una hoja o diálogo abierto.
export const IR_A = { i: '/', m: '/movimientos', p: '/presupuesto' }
const VENTANA_G_MS = 1500

export function esCampoDeTexto(el) {
  if (!el || !el.tagName) return false
  const tag = el.tagName
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (tag === 'INPUT') return !['checkbox', 'radio', 'button', 'submit', 'range'].includes(el.type)
  return !!el.isContentEditable
}

export function useAtajosTeclado() {
  const navigate = useNavigate()
  const esperandoG = useRef(0)

  useEffect(() => {
    function alTeclear(e) {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return
      if (esCampoDeTexto(e.target)) return
      if (document.querySelector('[role="dialog"][aria-modal="true"], [role="alertdialog"]')) return
      const k = (e.key || '').toLowerCase()
      if (k.length !== 1) return

      if (esperandoG.current && Date.now() - esperandoG.current < VENTANA_G_MS) {
        esperandoG.current = 0
        if (IR_A[k]) {
          e.preventDefault()
          navigate(IR_A[k])
          return
        }
      }
      if (k === 'g') {
        esperandoG.current = Date.now()
      } else if (k === 'n') {
        e.preventDefault()
        navigate('/agregar')
      } else if (k === '/') {
        const buscador = document.querySelector('input[type="search"], input[data-atajo-buscar]')
        if (buscador) {
          e.preventDefault()
          buscador.focus()
        }
      }
    }
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  }, [navigate])
}
