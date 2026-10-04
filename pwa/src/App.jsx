import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { api } from './lib/api'
import AutorizacionTratamiento from './screens/AutorizacionTratamiento'
import ConsentimientoGlobal from './components/ConsentimientoGlobal'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './lib/ThemeContext'
import { AuthProvider, useAuth } from './lib/AuthContext'
import { CuentasProvider, useCuentas } from './lib/CuentasContext'
import { CategoriasProvider } from './lib/CategoriasContext'
import { DialogosProvider } from './lib/DialogosContext'
import { BloqueoProvider, useBloqueo } from './lib/BloqueoContext'
import PantallaBloqueo from './components/PantallaBloqueo'
import BottomNav from './components/BottomNav'
import BandejaPorConfirmar from './components/BandejaPorConfirmar'
import SplashMarca, { splashPendiente } from './brand/SplashMarca'
import { CargandoMarca } from './brand/Marca'
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
const Patrimonio = lazy(() => import('./screens/Patrimonio'))
const Metas = lazy(() => import('./screens/Metas'))
const Recurrentes = lazy(() => import('./screens/Recurrentes'))
const Deudas = lazy(() => import('./screens/Deudas'))
const Conciliacion = lazy(() => import('./screens/Conciliacion'))
const Ahorcado = lazy(() => import('./screens/Ahorcado'))
const Compartir = lazy(() => import('./screens/Compartir'))
const ConectarDispositivo = lazy(() => import('./screens/ConectarDispositivo'))
const Correos = lazy(() => import('./screens/Correos'))
const Insights = lazy(() => import('./screens/Insights'))
const Asistente = lazy(() => import('./screens/Asistente'))
const ReglasCategoria = lazy(() => import('./screens/ReglasCategoria'))
const Categorias = lazy(() => import('./screens/Categorias'))
const ImportarArchivo = lazy(() => import('./screens/ImportarArchivo'))
const Impuestos = lazy(() => import('./screens/Impuestos'))
const CierreMes = lazy(() => import('./screens/CierreMes'))
const Wrapped = lazy(() => import('./screens/Wrapped'))
const Informe = lazy(() => import('./screens/Informe'))
const Perfil = lazy(() => import('./screens/Perfil'))
const TerminosCondiciones = lazy(() => import('./screens/legal/TerminosCondiciones'))
const PoliticaPrivacidad = lazy(() => import('./screens/legal/PoliticaPrivacidad'))
const AutorizacionDatos = lazy(() => import('./screens/legal/AutorizacionDatos'))

// Gastos compartidos (bloque aislado para minimizar conflictos al integrar)
const DividirGasto = lazy(() => import('./screens/DividirGasto'))
const CuentasAmigos = lazy(() => import('./screens/CuentasAmigos'))

function Cargando() {
  return <CargandoMarca />
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
        <Route path="/dividir" element={<DividirGasto />} />
        <Route path="/amigos" element={<CuentasAmigos />} />
        <Route path="/presupuesto" element={<Presupuesto />} />
        <Route path="/patrimonio" element={<Patrimonio />} />
        <Route path="/metas" element={<Metas />} />
        <Route path="/recurrentes" element={<Recurrentes />} />
        <Route path="/deudas" element={<Deudas />} />
        <Route path="/conciliacion" element={<Conciliacion />} />
        <Route path="/correos" element={<Correos />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/asistente" element={<Asistente />} />
        <Route path="/compartir" element={<Compartir />} />
        <Route path="/conectar-dispositivo" element={<ConectarDispositivo />} />
        <Route path="/ahorcado" element={<Ahorcado />} />
        <Route path="/reglas-categoria" element={<ReglasCategoria />} />
        <Route path="/categorias" element={<Categorias />} />
        <Route path="/resumen" element={<Wrapped />} />
        <Route path="/informe" element={<Informe />} />
        <Route path="/importar" element={<ImportarArchivo />} />
        <Route path="/impuestos" element={<Impuestos />} />
        <Route path="/cierre-mes" element={<CierreMes />} />
        <Route path="/perfil" element={<Perfil />} />
        <Route path="/legal/terminos" element={<TerminosCondiciones />} />
        <Route path="/legal/privacidad" element={<PoliticaPrivacidad />} />
        <Route path="/legal/autorizacion-datos" element={<AutorizacionDatos />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
      <BottomNav />
      {/* "¿Son tuyos?": al abrir y al volver a primer plano, movimientos que llegaron solos */}
      <BandejaPorConfirmar />
    </>
  )
}

function AppRoutes() {
  const { usuario, cargando, recuperando } = useAuth()
  const { bloqueado } = useBloqueo()

  if (cargando) return <CargandoMarca />

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

  // Con PIN activo y la app bloqueada no se monta nada de las pantallas: así
  // tampoco se hacen llamadas al backend ni se renderizan saldos detrás del candado.
  if (bloqueado) return <PantallaBloqueo />

  return (
    <PuertaAutorizacion>
      <CuentasProvider>
        <CategoriasProvider>
          <AppGate />
        </CategoriasProvider>
      </CuentasProvider>
      <ConsentimientoGlobal />
    </PuertaAutorizacion>
  )
}

// Tras iniciar sesión (y cuando cambia la versión de los textos legales) exige la
// autorización de tratamiento de datos antes de mostrar nada de la app. Los textos
// legales siguen siendo legibles desde la pantalla de autorización.
function PuertaAutorizacion({ children }) {
  const [estado, setEstado] = useState('cargando') // cargando | requiere | ok | error
  const cargar = useCallback(() => {
    setEstado('cargando')
    Promise.resolve()
      .then(() => api.consentimientos())
      .then((r) => setEstado(r.requiere_autorizacion ? 'requiere' : 'ok'))
      .catch(() => setEstado('error'))
  }, [])
  useEffect(cargar, [cargar])

  if (estado === 'cargando') return <CargandoMarca />
  if (estado === 'error') {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 px-8 text-center">
        <p className="text-sm text-danger">No pudimos verificar tu autorización de datos. Revisa tu conexión.</p>
        <button onClick={cargar} className="text-sm text-accent font-medium">Reintentar</button>
      </div>
    )
  }
  if (estado === 'requiere') {
    return (
      <Suspense fallback={<Cargando />}>
        <Routes>
          <Route path="/legal/terminos" element={<TerminosCondiciones />} />
          <Route path="/legal/privacidad" element={<PoliticaPrivacidad />} />
          <Route path="/legal/autorizacion-datos" element={<AutorizacionDatos />} />
          <Route path="*" element={<AutorizacionTratamiento onListo={() => setEstado('ok')} />} />
        </Routes>
      </Suspense>
    )
  }
  return children
}

export default function App() {
  // Splash de marca al abrir la app (una vez por sesión)
  const [splash, setSplash] = useState(splashPendiente)
  const terminarSplash = useCallback(() => setSplash(false), [])
  return (
    <ThemeProvider>
      {splash && <SplashMarca onFin={terminarSplash} />}
      <AuthProvider>
        <BloqueoProvider>
          <DialogosProvider>
            <HashRouter>
              <AppRoutes />
            </HashRouter>
          </DialogosProvider>
        </BloqueoProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
