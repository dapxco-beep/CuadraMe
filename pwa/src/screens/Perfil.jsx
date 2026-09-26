import { Check, LogOut, Palette } from 'lucide-react'
import { useTheme, THEMES } from '../lib/ThemeContext'
import { useAuth } from '../lib/AuthContext'

export default function Perfil() {
  const { theme, setTheme } = useTheme()
  const { usuario, logout } = useAuth()

  return (
    <div className="flex-1 overflow-y-auto pb-6">
      <header className="px-6 pt-14 pb-2">
        <h1 className="text-2xl font-bold">Perfil</h1>
      </header>

      <section className="px-6 mt-4 flex items-center gap-4">
        <div className="w-16 h-16 rounded-full bg-accent flex items-center justify-center text-white text-xl font-semibold">
          {usuario?.nombre?.[0]?.toUpperCase() || '?'}
        </div>
        <div>
          <p className="font-semibold">{usuario?.nombre}</p>
          <p className="text-sm text-ink-soft">{usuario?.email}</p>
        </div>
      </section>

      <section className="mx-6 mt-8">
        <div className="flex items-center gap-2 mb-3">
          <Palette size={16} className="text-ink-soft" />
          <h2 className="text-[15px] font-semibold">Tema y diseño</h2>
        </div>
        <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
          {THEMES.map((t) => (
            <button
              key={t.id}
              onClick={() => setTheme(t.id)}
              className="w-full flex items-center gap-3 px-4 py-3.5 text-left"
            >
              <span
                className="w-9 h-9 rounded-full shrink-0 border border-line"
                style={{ background: themePreview[t.id] }}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{t.nombre}</p>
                <p className="text-xs text-ink-soft">{t.desc}</p>
              </div>
              {theme === t.id && <Check size={18} className="text-accent shrink-0" />}
            </button>
          ))}
        </div>
      </section>

      <section className="mx-6 mt-6">
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 rounded-2xl bg-paper-raised border border-line px-4 py-3.5 text-danger font-medium text-sm"
        >
          <LogOut size={18} /> Cerrar sesión
        </button>
      </section>
    </div>
  )
}

const themePreview = {
  wallet: 'linear-gradient(135deg, #0d5c43, #d9a441)',
  editorial: 'linear-gradient(135deg, #f6f4ef, #0d5c43)',
  dark: 'linear-gradient(135deg, #0b0d0c, #3ddc9a)',
}
