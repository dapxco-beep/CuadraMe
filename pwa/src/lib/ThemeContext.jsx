import { createContext, useContext, useEffect, useState } from 'react'

const ThemeContext = createContext(null)

export const THEMES = [
  { id: 'auto', nombre: 'Automático', desc: 'Sigue el modo claro u oscuro de tu celular' },
  { id: 'calido', nombre: 'Claro', desc: 'Crema cálido, para el día a día' },
  { id: 'dark', nombre: 'Oscuro', desc: 'Misma identidad, pensado para la noche' },
]

const STORAGE_KEY = 'findp_theme'

function esHoraNocturna() {
  const hora = new Date().getHours()
  return hora >= 19 || hora < 6
}

const CONSULTA_OSCURO = '(prefers-color-scheme: dark)'

// En «auto» manda el sistema (matchMedia); la hora solo es respaldo si el navegador no lo sabe.
export function sistemaPrefiereOscuro() {
  try {
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
      const mq = window.matchMedia(CONSULTA_OSCURO)
      if (mq && mq.media !== 'not all') return mq.matches
    }
  } catch {}
  return esHoraNocturna()
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'auto'
    } catch {
      return 'auto'
    }
  })
  const [oscuroSistema, setOscuroSistema] = useState(sistemaPrefiereOscuro)

  const temaAplicado = theme === 'auto' ? (oscuroSistema ? 'dark' : 'calido') : theme

  useEffect(() => {
    document.documentElement.dataset.theme = temaAplicado
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {}
  }, [theme, temaAplicado])

  // Sigue al sistema en vivo; sin matchMedia, revisa la hora cada 15 min.
  useEffect(() => {
    if (theme !== 'auto') return
    setOscuroSistema(sistemaPrefiereOscuro())
    const mq = typeof window !== 'undefined' && typeof window.matchMedia === 'function' ? window.matchMedia(CONSULTA_OSCURO) : null
    if (mq && typeof mq.addEventListener === 'function') {
      const alCambiar = (e) => setOscuroSistema(Boolean(e.matches))
      mq.addEventListener('change', alCambiar)
      return () => mq.removeEventListener('change', alCambiar)
    }
    const intervalo = setInterval(() => setOscuroSistema(sistemaPrefiereOscuro()), 15 * 60 * 1000)
    return () => clearInterval(intervalo)
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
