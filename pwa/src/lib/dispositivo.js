import { useCallback, useEffect, useState } from 'react'
import { detectarDispositivo } from './primerUso'

// «¿Qué celular usas?»: la persona lo dice una vez y toda la app muestra SOLO las indicaciones de ese celular
// (instalar el ícono, registro automático…), sin mezclar las del otro. Si no lo ha dicho, se usa lo que detecta
// el navegador. Valores: 'ios' | 'android' | 'ninguno' (solo usa computador).
const CLAVE = 'cuadrame_celular'
const EVENTO = 'cuadrame:celular'
const VALIDOS = ['ios', 'android', 'ninguno']

export function leerCelularElegido() {
  try {
    const v = window.localStorage.getItem(CLAVE)
    return VALIDOS.includes(v) ? v : null
  } catch {
    return null
  }
}

export function guardarCelularElegido(valor) {
  try {
    if (VALIDOS.includes(valor)) window.localStorage.setItem(CLAVE, valor)
    else window.localStorage.removeItem(CLAVE)
  } catch {
    /* sin almacenamiento: queda solo en memoria hasta cerrar */
  }
  window.dispatchEvent(new Event(EVENTO))
}

/**
 * [dispositivo, elegir, yaPreguntado]
 *  - dispositivo: 'ios' | 'android' | 'otro' (lo elegido o, si no, lo detectado; 'ninguno' cuenta como 'otro')
 *  - yaPreguntado: true si la persona ya eligió (no se le vuelve a preguntar)
 */
export function useDispositivo() {
  const [elegido, setElegido] = useState(leerCelularElegido)
  useEffect(() => {
    const sync = () => setElegido(leerCelularElegido())
    window.addEventListener(EVENTO, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(EVENTO, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])
  const elegir = useCallback((v) => guardarCelularElegido(v), [])
  const dispositivo = elegido ? (elegido === 'ninguno' ? 'otro' : elegido) : detectarDispositivo()
  return [dispositivo, elegir, !!elegido]
}
