import { NavLink } from 'react-router-dom'
import { Home, List, Plus, PieChart, User } from 'lucide-react'

const tabs = [
  { to: '/', icon: Home, label: 'Inicio' },
  { to: '/movimientos', icon: List, label: 'Movimientos' },
  { to: '/agregar', icon: Plus, label: '', primary: true },
  { to: '/presupuesto', icon: PieChart, label: 'Presupuesto' },
  { to: '/perfil', icon: User, label: 'Perfil' },
]

export default function BottomNav() {
  return (
    <nav className="sticky bottom-0 inset-x-0 bg-paper/90 backdrop-blur-xl border-t border-line pb-[env(safe-area-inset-bottom)]">
      <div className="flex items-center justify-between px-4 pt-2 pb-2">
        {tabs.map(({ to, icon: Icon, label, primary }) =>
          primary ? (
            <NavLink
              key={to}
              to={to}
              className="flex flex-col items-center justify-center -mt-6"
            >
              <span className="w-14 h-14 rounded-full bg-accent text-paper-raised flex items-center justify-center shadow-lg shadow-accent/30 active:scale-95 transition-transform">
                <Icon size={26} strokeWidth={2.5} />
              </span>
            </NavLink>
          ) : (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 px-2 py-1 min-w-[56px] ${
                  isActive ? 'text-accent' : 'text-ink-soft'
                }`
              }
            >
              <Icon size={22} strokeWidth={2} />
              <span className="text-[11px] font-medium">{label}</span>
            </NavLink>
          )
        )}
      </div>
    </nav>
  )
}
