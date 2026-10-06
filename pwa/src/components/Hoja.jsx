import { useCallback, useEffect, useId, useRef, useState } from 'react'

// Hoja inferior / modal único de la app (antes había 20+ copias de
// `fixed inset-0 ... items-end`). Qué resuelve:
//  - Atrás del teléfono o del navegador CIERRA la hoja en vez de sacar al usuario
//    de la pantalla: al abrir se agrega una entrada al historial (con un marcador)
//    y al recibir popstate la hoja se cierra.
//  - Escape cierra; tocar fuera cierra; el foco queda atrapado dentro mientras
//    está abierta y vuelve al botón que la abrió al cerrar.
//  - Animación de entrada y de salida; en pantallas >= 768 px es un modal centrado.
//
// Uso (montada de forma condicional, lo más común):
//   {abrir && (
//     <Hoja onCerrar={() => setAbrir(false)} titulo="Nueva meta">
//       {({ cerrar }) => (...)}   // `cerrar` anima la salida y luego llama a onCerrar
//     </Hoja>
//   )}
// o controlada con `abierta` (la salida se anima y los hijos se conservan mientras tanto).

export const DURACION_SALIDA = 180 // ms; debe coincidir con las animaciones .hoja-saliendo de index.css

const FOCUSABLES =
  'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'

// Hojas abiertas, de abajo hacia arriba: Escape y la trampa de foco solo aplican a la de arriba.
const pila = []
// Retirada diferida del marcador de historial (así React StrictMode, que monta, desmonta
// y vuelve a montar, no deja entradas duplicadas).
const retiradas = new Map()

// Entradas-marcador "huérfanas": si el historial cae en una entrada con marcador cuya hoja
// ya no está abierta (p. ej. se navegó con la hoja abierta y luego se volvió), se salta
// hacia atrás para que el usuario no tenga que pulsar "atrás" dos veces.
if (typeof window !== 'undefined') {
  // Recarga con una hoja abierta: el marcador sobrevive en history.state pero la hoja no
  if (window.history.state?.__hoja) {
    const { __hoja, ...resto } = window.history.state
    window.history.replaceState(resto, '')
  }
  window.addEventListener('popstate', () => {
    const marca = window.history.state?.__hoja
    if (marca && !pila.includes(marca)) window.history.back()
  })
}

export default function Hoja({
  onCerrar,
  abierta = true,
  titulo,
  ariaLabel,
  role = 'dialog',
  claseFondo = '',
  clasePanel = 'p-6 pb-[max(2rem,env(safe-area-inset-bottom))]',
  children,
}) {
  const id = useId()
  const panel = useRef(null)
  const [fase, setFase] = useState(abierta ? 'abierta' : 'cerrada') // abierta | saliendo | cerrada

  const onCerrarRef = useRef(onCerrar)
  const abiertaRef = useRef(abierta)
  const montada = useRef(true)
  const cerrando = useRef(false)
  const desdeHistorial = useRef(false)
  const ultimosHijos = useRef(children)
  onCerrarRef.current = onCerrar
  abiertaRef.current = abierta
  if (abierta) ultimosHijos.current = children

  useEffect(() => {
    montada.current = true
    return () => {
      montada.current = false
    }
  }, [])

  // Control por prop: al pasar a abierta=false se anima la salida y luego se desmonta
  useEffect(() => {
    if (abierta) {
      setFase('abierta')
      return undefined
    }
    setFase((f) => (f === 'cerrada' ? f : 'saliendo'))
    const t = setTimeout(() => setFase('cerrada'), DURACION_SALIDA)
    return () => clearTimeout(t)
  }, [abierta])

  // Cierre iniciado por el usuario (Escape, tocar fuera, botón X, atrás): anima y avisa al padre.
  const cerrar = useCallback(() => {
    if (cerrando.current) return
    cerrando.current = true
    setFase('saliendo')
    setTimeout(() => {
      cerrando.current = false
      onCerrarRef.current?.()
      // Si el padre decidió no cerrarla, vuelve a mostrarse
      setTimeout(() => {
        if (montada.current && abiertaRef.current) setFase('abierta')
      }, 50)
    }, DURACION_SALIDA)
  }, [])

  // Historial: una entrada por hoja abierta
  useEffect(() => {
    if (!abierta) return undefined
    clearTimeout(retiradas.get(id))
    retiradas.delete(id)
    if (window.history.state?.__hoja !== id) {
      window.history.pushState({ ...(window.history.state || {}), __hoja: id }, '')
    }
    if (!pila.includes(id)) pila.push(id)

    function alRetroceder() {
      if (window.history.state?.__hoja !== id) {
        desdeHistorial.current = true
        cerrar()
      }
    }
    window.addEventListener('popstate', alRetroceder)

    return () => {
      window.removeEventListener('popstate', alRetroceder)
      const i = pila.indexOf(id)
      if (i >= 0) pila.splice(i, 1)
      if (desdeHistorial.current) {
        desdeHistorial.current = false
        return
      }
      // Cerrada por la app (guardar, X...): se retira su entrada del historial para que
      // "atrás" no tenga que pasar dos veces por la misma pantalla. Si ya se navegó a
      // otra ruta encima, no se toca el historial.
      retiradas.set(
        id,
        setTimeout(() => {
          retiradas.delete(id)
          if (window.history.state?.__hoja === id) window.history.back()
        }, 0)
      )
    }
  }, [abierta, id, cerrar])

  // Escape: solo la hoja de más arriba
  useEffect(() => {
    if (!abierta) return undefined
    function alTeclear(e) {
      if (e.key === 'Escape' && pila[pila.length - 1] === id && !e.defaultPrevented) {
        e.preventDefault()
        cerrar()
      }
    }
    document.addEventListener('keydown', alTeclear)
    return () => document.removeEventListener('keydown', alTeclear)
  }, [abierta, id, cerrar])

  // Foco: entra a la hoja al abrir y vuelve a quien la abrió al cerrar
  useEffect(() => {
    if (!abierta) return undefined
    const previo = document.activeElement
    if (panel.current && !panel.current.contains(document.activeElement)) panel.current.focus({ preventScroll: true })
    return () => {
      if (previo && previo.isConnected && typeof previo.focus === 'function') previo.focus({ preventScroll: true })
    }
  }, [abierta])

  // Trampa de foco: Tab y Shift+Tab no salen de la hoja
  function alTeclearPanel(e) {
    if (e.key !== 'Tab' || !panel.current) return
    const items = [...panel.current.querySelectorAll(FOCUSABLES)].filter((el) => !el.hasAttribute('disabled') && el.tabIndex !== -1)
    if (items.length === 0) {
      e.preventDefault()
      panel.current.focus()
      return
    }
    const primero = items[0]
    const ultimo = items[items.length - 1]
    const activo = document.activeElement
    if (e.shiftKey && (activo === primero || activo === panel.current)) {
      e.preventDefault()
      ultimo.focus()
    } else if (!e.shiftKey && activo === ultimo) {
      e.preventDefault()
      primero.focus()
    }
  }

  // Tocar fuera cierra, pero solo si el toque EMPEZÓ fuera (arrastrar para seleccionar texto
  // dentro de un campo y soltar afuera no debe cerrar la hoja).
  const empezoFuera = useRef(false)

  if (fase === 'cerrada') return null
  const contenido = abierta ? children : ultimosHijos.current

  return (
    <div
      className={`fixed inset-0 z-50 flex items-end md:items-center justify-center bg-ink/40 sheet-backdrop ${
        fase === 'saliendo' ? 'hoja-saliendo' : ''
      } ${claseFondo}`}
      onPointerDown={(e) => {
        empezoFuera.current = e.target === e.currentTarget
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && empezoFuera.current) cerrar()
      }}
    >
      <div
        ref={panel}
        role={role}
        aria-modal="true"
        aria-label={ariaLabel || titulo}
        tabIndex={-1}
        onKeyDown={alTeclearPanel}
        className={`hoja-panel sheet-content w-full max-w-[480px] bg-paper rounded-t-[28px] md:rounded-[28px] max-h-[90dvh] overflow-y-auto outline-none ${clasePanel}`}
      >
        {typeof contenido === 'function' ? contenido({ cerrar }) : contenido}
      </div>
    </div>
  )
}
