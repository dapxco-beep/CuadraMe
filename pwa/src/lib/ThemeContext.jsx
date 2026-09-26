import { createContext, useContext, useEffect, useState } from 'react'

const ThemeContext = createContext(null)

export const THEMES = [
  { id: 'wallet', nombre: 'Wallet cálido', desc: 'Tarjeta física, cálido y táctil' },
  { id: 'editorial', nombre: 'Editorial elegante', desc: 'Serif, sombras suaves, premium' },
  { id: 'dark', nombre: 'Oscuro vibrante', desc: 'Dark mode con acentos con glow' },
]

const STORAGE_KEY = 'findp_theme'

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'wallet'
    } catch {
      return 'wallet'
    }
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {}
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
