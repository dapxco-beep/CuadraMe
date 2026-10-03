import { lazy, Suspense } from 'react'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './lib/ThemeContext'
import { AuthProvider, useAuth } from './lib/AuthContext'
import { CuentasProvider, useCuentas } from './lib/CuentasContext'
import { CategoriasProvider } from './lib/CategoriasContext'
import { DialogosProvider } from './lib/DialogosContext'
import BottomNav from './components/BottomNav'
import Login from './screens/Login'
import CrearCuenta from './screens/CrearCuenta'
import Inicio from './screens/Inicio'
import NuevaPassword from './screens/NuevaPassword'

// Cada pantalla se descarga solo cuando se abre (antes todo viajaba en un único
// archivo de ~680KB). Login, Inicio y CrearCuenta quedan en el paquete principal
// porque son lo primero que se ve.
const Cuentas = lazy(() => import('./screens/Cuentas'))
const Movimientos = lazy(() => import('./screens/Movimientos'))
const DetalleMovimiento = lazy(() => import('./screens/DetalleMovimiento'))
const Agregar = lazy(() => import('./screens/Agregar'))
const Presupuesto = lazy(() => import('./screens/Presupuesto'))
const Metas = lazy(() => import('./screens/Metas'))
const Recurrentes = lazy(() => import('./screens/Recurrentes'))
const Deudas = lazy(() => import('./screens/Deudas'))
const Conciliacion = lazy(() => import('./screens/Conciliacion'))
const Ahorcado = lazy(() => import('./screens/Ahorcado'))
const Compartir = lazy(() => import('./screens/Compartir'))
const ConectarDispositivo = lazy(() => import('./screens/ConectarDispositivo'))
const Correos = lazy(() => import('./screens/Correos'))
const Insights = lazy(() => import('./screens/Insights'))
const ReglasCategoria = lazy(() => import('./screens/ReglasCategoria'))
const Categorias = lazy(() => import('./screens/Categorias'))
const Perfil = lazy(() => import('./screens/Perfil'))
const TerminosCondiciones = lazy(() => import('./screens/legal/TerminosCondiciones'))
const PoliticaPrivacidad = lazy(() => import('./screens/legal/PoliticaPrivacidad'))
const AutorizacionDatos = lazy(() => import('./screens/legal/AutorizacionDatos'))

function Cargando() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <p className="text-sm text-ink-soft">Cargando...</p>
    </div>
  )
}

function AppGate() {
  const { cuentas, cargando, error, recargar } = useCuentas()

  // Solo la primera carga bloquea la pantalla. Las recargas posteriores (por ejemplo
  // al guardar un movimiento) se hacen en segundo plano; antes parpadeaba toda la app.
  if (cargando && cuentas.length === 0) {
    return <Cargando />
  }

  if (error && cuentas.length === 0) {
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
      <Suspense fallback={<Cargando />}>
      <Routes>
        <Route path="/" element={<Inicio />} />
        <Route path="/cuentas" element={<Cuentas />} />
        <Route path="/movimientos" element={<Movimientos />} />
        <Route path="/movimientos/:id" element={<DetalleMovimiento />} />
        <Route path="/agregar" element={<Agregar />} />
        <Route path="/presupuesto" element={<Presupuesto />} />
        <Route path="/metas" element={<Metas />} />
        <Route path="/recurrentes" element={<Recurrentes />} />
        <Route path="/deudas" element={<Deudas />} />
        <Route path="/conciliacion" element={<Conciliacion />} />
        <Route path="/correos" element={<Correos />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/compartir" element={<Compartir />} />
        <Route path="/conectar-dispositivo" element={<ConectarDispositivo />} />
        <Route path="/ahorcado" element={<Ahorcado />} />
        <Route path="/reglas-categoria" element={<ReglasCategoria />} />
        <Route path="/categorias" element={<Categorias />} />
        <Route path="/perfil" element={<Perfil />} />
        <Route path="/legal/terminos" element={<TerminosCondiciones />} />
        <Route path="/legal/privacidad" element={<PoliticaPrivacidad />} />
        <Route path="/legal/autorizacion-datos" element={<AutorizacionDatos />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
      <BottomNav />
    </>
  )
}

function AppRoutes() {
  const { usuario, cargando, recuperando } = useAuth()

  if (cargando) return null

  if (usuario && recuperando) return <NuevaPassword />

  if (!usuario) {
    return (
      <Suspense fallback={<Cargando />}>
      <Routes>
        <Route path="/legal/terminos" element={<TerminosCondiciones />} />
        <Route path="/legal/privacidad" element={<PoliticaPrivacidad />} />
        <Route path="/legal/autorizacion-datos" element={<AutorizacionDatos />} />
        <Route path="*" element={<Login />} />
      </Routes>
      </Suspense>
    )
  }

  return (
    <CuentasProvider>
      <CategoriasProvider>
        <AppGate />
      </CategoriasProvider>
    </CuentasProvider>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <DialogosProvider>
          <HashRouter>
            <AppRoutes />
          </HashRouter>
        </DialogosProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
