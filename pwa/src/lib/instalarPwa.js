import { useSyncExternalStore } from 'react'

// ═══ Instalar CuadraMe con un toque (Android / Chrome) ════════════════════
// Chrome avisa con el evento `beforeinstallprompt` cuando la app se puede instalar. Lo guardamos para mostrar un
// botón «Instalar» que abre el cuadro nativo de Chrome: la instala como una app más (la crea Chrome mismo), sin
// descargar ningún APK, sin tiendas ni terceros. En iPhone (Safari) ese evento no existe: ahí se siguen los pasos.

let evento = null
const oyentes = new Set()
const avisar = () => oyentes.forEach((f) => f())

let iniciado = false
/** Se llama una sola vez al arrancar la app (main.jsx): el evento llega pronto y no se puede perder. */
export function iniciarInstalacion() {
  if (iniciado || typeof window === 'undefined') return
  iniciado = true
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault() // evita el aviso automático de Chrome; lo mostramos nosotros, en el momento útil
    evento = e
    avisar()
  })
  window.addEventListener('appinstalled', () => {
    evento = null
    avisar()
  })
}

export const puedeInstalar = () => !!evento

/** Abre el cuadro de instalación de Chrome. Devuelve 'accepted' | 'dismissed' | 'no-disponible'. */
export async function instalar() {
  if (!evento) return 'no-disponible'
  const e = evento
  evento = null // un evento solo se puede usar una vez
  avisar()
  try {
    await e.prompt()
    const r = await e.userChoice
    return r?.outcome || 'dismissed'
  } catch {
    return 'dismissed'
  }
}

const suscribir = (f) => {
  oyentes.add(f)
  return () => oyentes.delete(f)
}

/** true cuando Chrome ya dejó instalar la app (muestra el botón). */
export function useInstalable() {
  return useSyncExternalStore(suscribir, puedeInstalar, () => false)
}

// Solo para pruebas
export function _simularEvento(e) {
  evento = e
  avisar()
}
