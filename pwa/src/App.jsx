import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { MotionConfig } from 'framer-motion'
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
import ShellApp from './components/ShellApp'
import BandejaPorConfirmar from './components/BandejaPorConfirmar'
import RedirigirAlCentro from './components/RedirigirAlCentro'
import SplashMarca, { splashPendiente } from './brand/SplashMarca'
import { CargandoMarca } from './brand/Marca'
import ErrorAmable from './brand/ErrorAmable'
import { MSG_SIN_CONEXION } from './lib/mensajesBase'
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
const Ahorcado = lazy(() => import('./screens/Ahorcado'))
const Compartir = lazy(() => import('./screens/Compartir'))
const ConectarDispositivo = lazy(() => import('./screens/ConectarDispositivo'))
const Sincronizacion = lazy(() => import('./screens/Sincronizacion'))
const Insights = lazy(() => import('./screens/Insights'))
const Asistente = lazy(() => import('./screens/Asistente'))
const ReglasCategoria = lazy(() => import('./screens/ReglasCategoria'))
const EntrenarCategorias = lazy(() => import('./screens/EntrenarCategorias'))
const Categorias = lazy(() => import('./screens/Categorias'))
const Impuestos = lazy(() => import('./screens/Impuestos'))
const CierreMes = lazy(() => import('./screens/CierreMes'))
const Wrapped = lazy(() => import('./screens/Wrapped'))
const Informe = lazy(() => import('./screens/Informe'))
const Perfil = lazy(() => import('./screens/Perfil'))
const BuscarDuplicados = lazy(() => import('./screens/BuscarDuplicados'))
const Ayuda = lazy(() => import('./screens/Ayuda'))
const Aprende = lazy(() => import('./screens/Aprende'))
const SaludNegocio = lazy(() => import('./screens/SaludNegocio'))
const Opinion = lazy(() => import('./screens/Opinion'))
const ComentariosAdmin = lazy(() => import('./screens/ComentariosAdmin'))
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
    // /opinion sigue abierta aunque las cuentas no carguen: quien no puede entrar también puede contarnos qué pasó.
    return (
      <Suspense fallback={<Cargando />}>
        <Routes>
          <Route path="/opinion" element={<Opinion />} />
          <Route path="*" element={<ErrorAmable sinConexion={error === MSG_SIN_CONEXION} detalle={error} onAccion={recargar} reportar />} />
        </Routes>
      </Suspense>
    )
  }

  if (cuentas.length === 0) {
    return <CrearCuenta onCreada={recargar} />
  }

  return (
    <>
      <ShellApp>
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
        <Route path="/conciliacion" element={<RedirigirAlCentro ruta="/conciliacion" />} />
        <Route path="/correos" element={<RedirigirAlCentro ruta="/correos" />} />
        <Route path="/conexiones" element={<RedirigirAlCentro ruta="/conexiones" />} />
        <Route path="/sincronizacion" element={<Sincronizacion />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/asistente" element={<Asistente />} />
        <Route path="/compartir" element={<Compartir />} />
        <Route path="/conectar-dispositivo" element={<ConectarDispositivo />} />
        <Route path="/ahorcado" element={<Ahorcado />} />
        <Route path="/reglas-categoria" element={<ReglasCategoria />} />
        <Route path="/entrenar-categorias" element={<EntrenarCategorias />} />
        <Route path="/categorias" element={<Categorias />} />
        <Route path="/resumen" element={<Wrapped />} />
        <Route path="/informe" element={<Informe />} />
        <Route path="/importar" element={<RedirigirAlCentro ruta="/importar" />} />
        <Route path="/impuestos" element={<Impuestos />} />
        <Route path="/cierre-mes" element={<CierreMes />} />
        <Route path="/perfil" element={<Perfil />} />
        <Route path="/buscar-duplicados" element={<BuscarDuplicados />} />
        <Route path="/ayuda" element={<Ayuda />} />
        <Route path="/aprende" element={<Aprende />} />
        <Route path="/salud-negocio" element={<SaludNegocio />} />
        <Route path="/opinion" element={<Opinion />} />
        <Route path="/comentarios-admin" element={<ComentariosAdmin />} />
        <Route path="/legal/terminos" element={<TerminosCondiciones />} />
        <Route path="/legal/privacidad" element={<PoliticaPrivacidad />} />
        <Route path="/legal/autorizacion-datos" element={<AutorizacionDatos />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
      </ShellApp>
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

  const arbol = (
    <PuertaAutorizacion>
      <CuentasProvider>
        <CategoriasProvider>
          <AppGate />
        </CategoriasProvider>
      </CuentasProvider>
      <ConsentimientoGlobal />
    </PuertaAutorizacion>
  )
  return <ArbolConBloqueo bloqueado={bloqueado}>{arbol}</ArbolConBloqueo>
}

// Con PIN activo, la pantalla de bloqueo va ENCIMA del árbol ya montado en vez de reemplazarlo:
// así un formulario a medias (Agregar, factura, una hoja abierta) sobrevive al bloqueo
// automático cuando la app vuelve de segundo plano. El resto queda inerte (sin foco, sin
// lectores de pantalla) mientras está bloqueada.
// La PRIMERA vez que se abre la app bloqueada no se monta nada detrás: así no se hacen llamadas
// al backend ni se renderizan saldos detrás del candado antes de que el usuario ponga su PIN.
export function ArbolConBloqueo({ bloqueado, children }) {
  const [montado, setMontado] = useState(!bloqueado)
  useEffect(() => {
    if (!bloqueado) setMontado(true)
  }, [bloqueado])

  // Las hojas viven en document.body (portal), fuera del árbol inerte: el CSS las oculta
  // mientras haya bloqueo y Hoja ignora Escape.
  useEffect(() => {
    document.body.toggleAttribute('data-bloqueado', !!bloqueado)
    return () => document.body.removeAttribute('data-bloqueado')
  }, [bloqueado])

  if (bloqueado && !montado) return <PantallaBloqueo />
  return (
    <>
      <div className="contents" inert={bloqueado} aria-hidden={bloqueado || undefined} data-testid="arbol-app">
        {children}
      </div>
      {bloqueado && <PantallaBloqueo />}
    </>
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
      <ErrorAmable
        sinConexion
        texto="No pudimos verificar tu autorización de datos. Revisa tu conexión y vuelve a intentarlo."
        onAccion={cargar}
      />
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
    // reducedMotion="user": con "reducir movimiento" del sistema, framer-motion desactiva
    // los desplazamientos/escalas (conserva solo fundidos de opacidad)
    <MotionConfig reducedMotion="user">
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
    </MotionConfig>
  )
}
