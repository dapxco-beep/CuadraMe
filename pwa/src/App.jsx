import { HashRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './lib/ThemeContext'
import { AuthProvider, useAuth } from './lib/AuthContext'
import { CuentasProvider, useCuentas } from './lib/CuentasContext'
import BottomNav from './components/BottomNav'
import Login from './screens/Login'
import CrearCuenta from './screens/CrearCuenta'
import Inicio from './screens/Inicio'
import Movimientos from './screens/Movimientos'
import DetalleMovimiento from './screens/DetalleMovimiento'
import Agregar from './screens/Agregar'
import Presupuesto from './screens/Presupuesto'
import Metas from './screens/Metas'
import Recurrentes from './screens/Recurrentes'
import Deudas from './screens/Deudas'
import Conciliacion from './screens/Conciliacion'
import Perfil from './screens/Perfil'

function AppGate() {
  const { cuentas, cargando, error, recargar } = useCuentas()

  if (cargando) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-ink-soft">Cargando...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 px-8 text-center">
        <p className="text-sm text-danger">{error}</p>
        <button onClick={recargar} className="text-sm text-accent font-medium">
          Reintentar
        </button>
      </div>
    )
  }

  if (cuentas.length === 0) {
    return <CrearCuenta onCreada={recargar} />
  }

  return (
    <>
      <Routes>
        <Route path="/" element={<Inicio />} />
        <Route path="/movimientos" element={<Movimientos />} />
        <Route path="/movimientos/:id" element={<DetalleMovimiento />} />
        <Route path="/agregar" element={<Agregar />} />
        <Route path="/presupuesto" element={<Presupuesto />} />
        <Route path="/metas" element={<Metas />} />
        <Route path="/recurrentes" element={<Recurrentes />} />
        <Route path="/deudas" element={<Deudas />} />
        <Route path="/conciliacion" element={<Conciliacion />} />
        <Route path="/perfil" element={<Perfil />} />
      </Routes>
      <BottomNav />
    </>
  )
}

function AppRoutes() {
  const { usuario, cargando } = useAuth()

  if (cargando) return null
  if (!usuario) return <Login />

  return (
    <CuentasProvider>
      <AppGate />
    </CuentasProvider>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <HashRouter>
          <AppRoutes />
        </HashRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}
