import { createContext, useContext, useEffect, useState } from 'react'

const ThemeContext = createContext(null)

export const THEMES = [
  { id: 'auto', nombre: 'Automático', desc: 'Claro de día, oscuro de noche (7pm-6am)' },
  { id: 'calido', nombre: 'Claro', desc: 'Crema cálido, para el día a día' },
  { id: 'dark', nombre: 'Oscuro', desc: 'Misma identidad, pensado para la noche' },
]

const STORAGE_KEY = 'findp_theme'

function esHoraNocturna() {
  const hora = new Date().getHours()
  return hora >= 19 || hora < 6
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'auto'
    } catch {
      return 'auto'
    }
  })

  const temaAplicado = theme === 'auto' ? (esHoraNocturna() ? 'dark' : 'calido') : theme

  useEffect(() => {
    document.documentElement.dataset.theme = temaAplicado
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {}
  }, [theme, temaAplicado])

  useEffect(() => {
    if (theme !== 'auto') return
    const intervalo = setInterval(() => {
      document.documentElement.dataset.theme = esHoraNocturna() ? 'dark' : 'calido'
    }, 15 * 60 * 1000)
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
