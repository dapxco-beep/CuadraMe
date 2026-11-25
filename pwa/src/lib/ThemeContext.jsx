import { createContext, useContext, useEffect, useState } from 'react'

const ThemeContext = createContext(null)

// `vista`: colores de la miniatura (fondo, tarjeta, texto, acento). `oscuro`: para elegir la variante de acento adecuada.
export const THEMES = [
  { id: 'auto', nombre: 'Automático', desc: 'Sigue el modo claro u oscuro de tu celular', vista: { fondo: '#f7f4ee', tarjeta: '#17140f', texto: '#221f19', acento: '#d9622b' } },
  { id: 'calido', nombre: 'Claro', desc: 'Crema cálido, para el día a día', vista: { fondo: '#f7f4ee', tarjeta: '#ffffff', texto: '#221f19', acento: '#d9622b' } },
  { id: 'dark', nombre: 'Oscuro', desc: 'Misma identidad, pensado para la noche', oscuro: true, vista: { fondo: '#17140f', tarjeta: '#221f19', texto: '#f5f1e8', acento: '#e8823f' } },
  { id: 'menta', nombre: 'Menta', desc: 'Verde fresco y tranquilo', vista: { fondo: '#f1f7f3', tarjeta: '#ffffff', texto: '#17261e', acento: '#2e9a6b' } },
  { id: 'oceano', nombre: 'Océano', desc: 'Azul sereno, muy legible', vista: { fondo: '#f1f6fb', tarjeta: '#ffffff', texto: '#14212e', acento: '#2f80d1' } },
  { id: 'ciruela', nombre: 'Ciruela', desc: 'Morado cálido y elegante', vista: { fondo: '#f8f4fb', tarjeta: '#ffffff', texto: '#241a2e', acento: '#9b59c9' } },
  { id: 'noche', nombre: 'Noche', desc: 'Azul profundo para usar de noche', oscuro: true, vista: { fondo: '#0f1624', tarjeta: '#18223a', texto: '#eaf0fb', acento: '#6fa8ff' } },
  { id: 'grafito', nombre: 'Grafito', desc: 'Negro puro con verde; cuida la batería', oscuro: true, vista: { fondo: '#0b0b0c', tarjeta: '#161618', texto: '#f2f2f3', acento: '#3ddc97' } },
]

// Color de acento a elección (opcional): cambia botones, enlaces y resaltados sin tocar el resto del tema.
// Cada color trae su versión para fondo claro (más oscura, con buen contraste) y para fondo oscuro (más clara).
export const ACENTOS = [
  { id: 'bosque', nombre: 'Verde', claro: '#1f6b4a', oscuro: '#6fdca0' },
  { id: 'azul', nombre: 'Azul', claro: '#1d5fa6', oscuro: '#7db4ff' },
  { id: 'morado', nombre: 'Morado', claro: '#6b3fa0', oscuro: '#c59bf0' },
  { id: 'rosa', nombre: 'Rosa', claro: '#b02a5b', oscuro: '#f59ab9' },
  { id: 'turquesa', nombre: 'Turquesa', claro: '#0f766e', oscuro: '#5eead4' },
  { id: 'dorado', nombre: 'Dorado', claro: '#8a5a00', oscuro: '#f0c05a' },
]

const CLAVE_ACENTO = 'findp_accent'
const VARIABLES_ACENTO = ['--c-accent', '--c-brand', '--c-accent-soft', '--c-hero-a', '--c-hero-b']

/** Aplica (o quita) el acento elegido sobre el tema actual. Se calcula con color-mix para no repetir cada tema. */
export function aplicarAcento(id, oscuro, raiz = document.documentElement) {
  const a = ACENTOS.find((x) => x.id === id)
  for (const v of VARIABLES_ACENTO) raiz.style.removeProperty(v)
  if (!a) return
  const c = oscuro ? a.oscuro : a.claro
  raiz.style.setProperty('--c-accent', c)
  raiz.style.setProperty('--c-brand', c)
  raiz.style.setProperty('--c-accent-soft', `color-mix(in srgb, ${c} ${oscuro ? 22 : 16}%, var(--c-paper-raised))`)
  raiz.style.setProperty('--c-hero-a', `color-mix(in srgb, ${c} ${oscuro ? 45 : 85}%, black)`)
  raiz.style.setProperty('--c-hero-b', `color-mix(in srgb, ${c} ${oscuro ? 25 : 58}%, black)`)
}

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
  const [acento, setAcentoEstado] = useState(() => {
    try {
      return localStorage.getItem(CLAVE_ACENTO) || ''
    } catch {
      return ''
    }
  })
  const setAcento = (id) => {
    setAcentoEstado(id || '')
    try {
      if (id) localStorage.setItem(CLAVE_ACENTO, id)
      else localStorage.removeItem(CLAVE_ACENTO)
    } catch {}
  }
  const esOscuro = Boolean(THEMES.find((x) => x.id === temaAplicado)?.oscuro)

  useEffect(() => {
    document.documentElement.dataset.theme = temaAplicado
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {}
  }, [theme, temaAplicado])

  useEffect(() => {
    aplicarAcento(acento, esOscuro)
  }, [acento, esOscuro])

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
    <ThemeContext.Provider value={{ theme, setTheme, acento, setAcento, esOscuro }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
