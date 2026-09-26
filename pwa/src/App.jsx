import { useEffect, useState } from 'react'
import { HashRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './lib/ThemeContext'
import { AuthProvider, useAuth } from './lib/AuthContext'
import { api } from './lib/api'
import BottomNav from './components/BottomNav'
import Login from './screens/Login'
import CrearCuenta from './screens/CrearCuenta'
import Inicio from './screens/Inicio'
import Movimientos from './screens/Movimientos'
import DetalleMovimiento from './screens/DetalleMovimiento'
import Agregar from './screens/Agregar'
import Presupuesto from './screens/Presupuesto'
import Perfil from './screens/Perfil'

function AppRoutes() {
  const { usuario, cargando } = useAuth()
  const [tieneCuentas, setTieneCuentas] = useState(null)

  useEffect(() => {
    if (!usuario) return
    api
      .cuentas()
      .then((cs) => setTieneCuentas(cs.length > 0))
      .catch(() => setTieneCuentas(true))
  }, [usuario])

  if (cargando) return null
  if (!usuario) return <Login />
  if (tieneCuentas === null) return null
  if (!tieneCuentas) return <CrearCuenta onCreada={() => setTieneCuentas(true)} />

  return (
    <>
      <Routes>
        <Route path="/" element={<Inicio />} />
        <Route path="/movimientos" element={<Movimientos />} />
        <Route path="/movimientos/:id" element={<DetalleMovimiento />} />
        <Route path="/agregar" element={<Agregar />} />
        <Route path="/presupuesto" element={<Presupuesto />} />
        <Route path="/perfil" element={<Perfil />} />
      </Routes>
      <BottomNav />
    </>
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
