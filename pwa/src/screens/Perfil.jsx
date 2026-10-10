import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, Flag, Mail, Receipt, Check, ChevronRight, CopyCheck, CreditCard, FileText, GraduationCap, Landmark, Link2, List, LogOut, MessageCircle, Trash2, Palette, PiggyBank, RefreshCw, Repeat, Sprout, Tag, Users, Wand2, LifeBuoy } from 'lucide-react'
import { useTheme, THEMES } from '../lib/ThemeContext'
import { useAuth } from '../lib/AuthContext'
import { api } from '../lib/api'
import { useDialogos } from '../lib/DialogosContext'
import SeccionSeguridad from '../components/SeccionSeguridad'
import SeccionPrivacidad from '../components/SeccionPrivacidad'
import AsistentePrimerUso from '../components/AsistentePrimerUso'
import RecorridoEntrada from '../components/RecorridoEntrada'
import ClaveAtajo from '../components/ClaveAtajo'
import PuntoDePartida from '../components/PuntoDePartida'
import { useClaveAtajo } from '../lib/useClaveAtajo'
import Cuadri from '../brand/Cuadri'
import { useMostrarCuadri } from '../lib/cuadri'
import { useModoMenu } from '../lib/modoSimple'
import { activarPush, desactivarPush, estadoPermiso, pushSoportado } from '../lib/push'

export default function Perfil() {
  const { theme, setTheme } = useTheme()
  const { usuario, logout } = useAuth()
  const { avisar } = useDialogos()
  const claveAtajo = useClaveAtajo()
  const { completo, setCompleto } = useModoMenu()
  const [mostrarCuadri, cambiarCuadri] = useMostrarCuadri()
  const [permisoPush, setPermisoPush] = useState('default')
  const [cargandoPush, setCargandoPush] = useState(false)
  const [recordatorio, setRecordatorio] = useState(false)
  const [resumenCorreo, setResumenCorreo] = useState({ activo: false, email: '', cargando: false })
  const [confianza, setConfianza] = useState(0.75)
  const [guardandoConfianza, setGuardandoConfianza] = useState(false)
  const [eliminandoCuenta, setEliminandoCuenta] = useState(false)

  useEffect(() => {
    estadoPermiso().then(setPermisoPush)
    api.confianzaAutoimport().then((r) => setConfianza(r.confianza_autoimport)).catch(() => {})
    Promise.resolve().then(() => api.recordatorioDiario()).then((r) => setRecordatorio(!!r.activo)).catch(() => {})
    Promise.resolve().then(() => api.resumenPreferencias?.())
      .then((r) => r && setResumenCorreo({ activo: !!r.correo, email: r.email || '', cargando: false }))
      .catch(() => {})
  }, [])

  async function toggleResumenCorreo() {
    const nuevo = !resumenCorreo.activo
    setResumenCorreo((r) => ({ ...r, activo: nuevo, cargando: true }))
    try {
      await api.guardarResumenPreferencias(nuevo)
      setResumenCorreo((r) => ({ ...r, cargando: false }))
    } catch (err) {
      setResumenCorreo((r) => ({ ...r, activo: !nuevo, cargando: false }))
      avisar(err.message || 'No pudimos cambiar el resumen por correo. Intenta de nuevo.')
    }
  }

  async function toggleRecordatorio() {
    const nuevo = !recordatorio
    setRecordatorio(nuevo)
    try {
      await api.actualizarRecordatorioDiario(nuevo)
      // El aviso viaja por push: si aún no hay permiso, se pide al activarlo.
      if (nuevo && permisoPush !== 'granted') {
        await activarPush()
        setPermisoPush('granted')
      }
    } catch (err) {
      if (err?.message && !/permiso|soporta/i.test(err.message)) {
        setRecordatorio(!nuevo)
      }
      avisar(err.message || 'No pudimos cambiar el recordatorio. Intenta de nuevo.')
    }
  }

  async function cambiarConfianza(valor) {
    setConfianza(valor)
    setGuardandoConfianza(true)
    try {
      await api.actualizarConfianzaAutoimport(valor)
    } catch {} finally {
      setGuardandoConfianza(false)
    }
  }

  async function toggleNotificaciones() {
    setCargandoPush(true)
    try {
      if (permisoPush === 'granted') {
        await desactivarPush()
        setPermisoPush('default')
      } else {
        await activarPush()
        setPermisoPush('granted')
      }
    } catch (err) {
      avisar(err.message || 'No pudimos activar las notificaciones. Revisa que tu navegador las permita.')
    } finally {
      setCargandoPush(false)
    }
  }

  // La confirmación (escribir ELIMINAR) ya la pidió la hoja de Privacidad: aquí solo se ejecuta.
  async function eliminarMiCuenta(palabra) {
    setEliminandoCuenta(true)
    try {
      await api.eliminarMiCuenta(palabra)
      await logout()
    } catch (err) {
      setEliminandoCuenta(false)
      avisar(err.message || 'No pudimos eliminar tu cuenta. Intenta de nuevo.')
    }
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pantalla-top pb-2">
        <h1 className="text-2xl font-bold">Perfil</h1>
      </header>

      <section className="px-6 mt-4 flex items-center gap-4">
        <div className="w-16 h-16 rounded-full bg-accent flex items-center justify-center text-paper-raised text-xl font-semibold">
          {usuario?.nombre?.[0]?.toUpperCase() || '?'}
        </div>
        <div>
          <p className="font-semibold">{usuario?.nombre}</p>
          <p className="text-sm text-ink-soft">{usuario?.email}</p>
        </div>
      </section>

      {/* Modo simple: por defecto el menú muestra solo lo esencial; aquí se muestran todas las funciones */}
      <section className="mx-6 mt-6" aria-label="Qué funciones ver">
        <div className="rounded-2xl bg-paper-raised border border-line p-4 flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium" id="etq-todas-funciones">Mostrar todas las funciones</p>
            <p className="text-xs text-ink-soft mt-0.5">
              {completo
                ? 'Ves todo: metas, deudas, impuestos, patrimonio y más.'
                : 'Ahora ves solo lo básico. Actívalo para ver metas, deudas, impuestos y más.'}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setCompleto(!completo)}
            role="switch"
            aria-checked={completo}
            aria-labelledby="etq-todas-funciones"
            data-testid="switch-todas-funciones"
            className="shrink-0 min-h-11 w-14 flex items-center justify-center"
          >
            <span className={`block w-12 h-7 rounded-full transition-colors relative ${completo ? 'bg-accent' : 'bg-line'}`}>
              <span className={`absolute top-0.5 left-0 w-6 h-6 rounded-full bg-white shadow transition-transform ${completo ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </span>
          </button>
        </div>
      </section>

      {/* Lo que desaparece de Inicio al completarse (u ocultarse) sigue aquí para repasarlo */}
      <RecorridoEntrada />
      <AsistentePrimerUso variante="perfil" />

      <section className="mx-6 mt-6">
        <Link to="/ayuda" className="flex items-center gap-3 rounded-2xl bg-paper-raised border border-line px-4 py-3.5">
          <LifeBuoy size={20} className="text-accent shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium">Ayuda y preguntas frecuentes</p>
            <p className="text-xs text-ink-soft mt-0.5">Extractos, clave del PDF, Gmail, borrar tus datos…</p>
          </div>
          <ChevronRight size={16} className="text-ink-soft" />
        </Link>
        <Link to="/opinion?desde=/perfil" className="mt-2 flex items-center gap-3 rounded-2xl bg-paper-raised border border-line px-4 py-3.5">
          <MessageCircle size={20} className="text-accent shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium">Tu opinión cuenta</p>
            <p className="text-xs text-ink-soft mt-0.5">Una idea, una duda o algo que no funcionó.</p>
          </div>
          <ChevronRight size={16} className="text-ink-soft" />
        </Link>
      </section>

      <section className="mx-6 mt-6">
        <h2 className="text-[15px] font-semibold mb-3">Tus cuentas</h2>
        <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
          <Link to="/cuentas" className="flex items-center gap-3 px-4 py-3.5">
            <Landmark size={20} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Ver y editar mis cuentas</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/movimientos" className="flex items-center gap-3 px-4 py-3.5">
            <List size={20} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Todos mis movimientos</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/buscar-duplicados" className="flex items-center gap-3 px-4 py-3.5">
            <CopyCheck size={20} className="text-accent shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium">Buscar movimientos repetidos</p>
              <p className="text-xs text-ink-soft mt-0.5">Si un gasto quedó anotado dos veces, lo juntamos</p>
            </div>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/compartir" className="flex items-center gap-3 px-4 py-3.5">
            <Users size={20} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Compartir una cuenta</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
        </div>
      </section>

      <section className="mx-6 mt-6">
        <h2 className="text-[15px] font-semibold mb-3">Traer tus movimientos</h2>
        <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
          <Link to="/sincronizacion" className="flex items-center gap-3 px-4 py-3.5">
            <RefreshCw size={20} className="text-accent shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium">Traer movimientos</p>
              <p className="text-xs text-ink-soft mt-0.5">Desde tu correo, el extracto del banco o un Excel</p>
            </div>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
        </div>

        <div className="rounded-2xl bg-paper-raised border border-line p-4 mt-3">
          <p className="text-sm font-medium" id="etq-confianza">¿Qué tan seguro debe estar CuadraMe para registrar solo?</p>
          <p className="text-xs text-ink-soft mt-0.5 mb-3">
            Al leer un extracto, si CuadraMe está muy seguro de la categoría, registra el movimiento sin
            preguntarte. Más estricto: te pregunta más seguido.
          </p>
          <input
            type="range"
            min="0.5"
            max="0.95"
            step="0.05"
            value={confianza}
            onChange={(e) => cambiarConfianza(Number(e.target.value))}
            aria-labelledby="etq-confianza"
            aria-valuetext={`${Math.round(confianza * 100)} por ciento`}
            className="w-full accent-accent"
          />
          <div className="flex items-center justify-between text-xs text-ink-soft mt-1">
            <span>Más permisivo</span>
            <span className="font-semibold text-ink">{Math.round(confianza * 100)}%{guardandoConfianza ? ' · guardando...' : ''}</span>
            <span>Más estricto</span>
          </div>
        </div>
      </section>

      {completo && (
      <section className="mx-6 mt-6">
        <h2 className="text-[15px] font-semibold mb-3">Planeación</h2>
        <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
          <Link to="/metas" className="flex items-center gap-3 px-4 py-3.5">
            <PiggyBank size={20} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Metas de ahorro</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/recurrentes" className="flex items-center gap-3 px-4 py-3.5">
            <Repeat size={20} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Pagos fijos</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/deudas" className="flex items-center gap-3 px-4 py-3.5">
            <CreditCard size={20} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Deudas</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/reglas-categoria" className="flex items-center gap-3 px-4 py-3.5">
            <Wand2 size={20} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Reglas automáticas</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/entrenar-categorias" className="flex items-center gap-3 px-4 py-3.5">
            <GraduationCap size={20} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Enseñar categorías</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/categorias" className="flex items-center gap-3 px-4 py-3.5">
            <Tag size={20} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Categorías</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
        </div>
      </section>
      )}

      {completo && (
      <section className="mx-6 mt-6">
        <h2 className="text-[15px] font-semibold mb-3">Más herramientas</h2>
        <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
          <Link to="/impuestos" className="flex items-center gap-3 px-4 py-3.5">
            <Receipt size={20} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Impuestos: 4x1000 y renta</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/cierre-mes" className="flex items-center gap-3 px-4 py-3.5">
            <FileText size={20} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Cierre de mes</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/ahorcado" className="flex items-center gap-3 px-4 py-3.5">
            <Sprout size={20} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Tu árbol financiero</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
        </div>
      </section>
      )}

      <section className="mx-6 mt-8">
        <div className="flex items-center gap-2 mb-3">
          <Mail size={16} className="text-ink-soft" aria-hidden="true" />
          <h2 className="text-[15px] font-semibold">Correo</h2>
        </div>
        <div className="rounded-2xl bg-paper-raised border border-line p-4 flex items-center gap-3">
          <div className="flex-1">
            <p className="text-sm font-medium" id="etq-resumen-correo">Resumen semanal por correo</p>
            <p className="text-xs text-ink-soft mt-0.5">
              Cada domingo te escribimos a {resumenCorreo.email || 'tu correo'} con lo que gastaste, en qué se fue más la
              plata y qué pagos vienen. Puedes apagarlo cuando quieras.
            </p>
          </div>
          <button
            onClick={toggleResumenCorreo}
            disabled={resumenCorreo.cargando}
            role="switch"
            aria-checked={resumenCorreo.activo}
            aria-labelledby="etq-resumen-correo"
            data-testid="switch-resumen-correo"
            className={`shrink-0 w-12 h-7 rounded-full transition-colors relative ${resumenCorreo.activo ? 'bg-accent' : 'bg-line'}`}
          >
            <span
              className={`absolute top-0.5 left-0 w-6 h-6 rounded-full bg-white shadow transition-transform ${
                resumenCorreo.activo ? 'translate-x-5' : 'translate-x-0.5'
              }`}
            />
          </button>
        </div>
      </section>

      {pushSoportado() && (
        <section className="mx-6 mt-8">
          <div className="flex items-center gap-2 mb-3">
            <Bell size={16} className="text-ink-soft" />
            <h2 className="text-[15px] font-semibold">Notificaciones</h2>
          </div>
          <div className="rounded-2xl bg-paper-raised border border-line p-4 flex items-center gap-3">
            <div className="flex-1">
              <p className="text-sm font-medium">Alertas de presupuesto</p>
              <p className="text-xs text-ink-soft mt-0.5">
                Te avisamos cuando te acerques al límite de una categoría
              </p>
            </div>
            <button
              onClick={toggleNotificaciones}
              disabled={cargandoPush}
              role="switch"
              aria-checked={permisoPush === 'granted'}
              aria-label="Alertas de presupuesto"
              className={`shrink-0 w-12 h-7 rounded-full transition-colors relative ${
                permisoPush === 'granted' ? 'bg-accent' : 'bg-ink-soft/35'
              } disabled:opacity-60`}
            >
              <span
                className={`absolute top-0.5 left-0 w-6 h-6 rounded-full bg-white shadow transition-transform ${
                  permisoPush === 'granted' ? 'translate-x-5' : 'translate-x-0.5'
                }`}
              />
            </button>
          </div>

          <div className="rounded-2xl bg-paper-raised border border-line p-4 flex items-center gap-3 mt-3">
            <div className="flex-1">
              <p className="text-sm font-medium">Recordatorio diario</p>
              <p className="text-xs text-ink-soft mt-0.5">
                A las 8 p. m. te avisamos solo si hoy no registraste nada
                {permisoPush !== 'granted' ? ' (activa primero las alertas de arriba)' : ''}
              </p>
            </div>
            <button
              onClick={toggleRecordatorio}
              role="switch"
              aria-checked={recordatorio}
              aria-label="Recordatorio diario"
              className={`shrink-0 w-12 h-7 rounded-full transition-colors relative ${recordatorio ? 'bg-accent' : 'bg-ink-soft/35'}`}
            >
              <span
                className={`absolute top-0.5 left-0 w-6 h-6 rounded-full bg-white shadow transition-transform ${
                  recordatorio ? 'translate-x-5' : 'translate-x-0.5'
                }`}
              />
            </button>
          </div>
        </section>
      )}

      <SeccionSeguridad />

      <section className="mx-6 mt-8" id="punto-de-partida" aria-labelledby="titulo-punto-de-partida">
        <div className="flex items-center gap-2 mb-3">
          <Flag size={16} className="text-ink-soft" aria-hidden="true" />
          <h2 id="titulo-punto-de-partida" className="text-[15px] font-semibold">Punto de partida</h2>
        </div>
        <PuntoDePartida variante="perfil" />
      </section>

      {completo && (
      <section className="mx-6 mt-8">
        <div className="flex items-center gap-2 mb-3">
          <Link2 size={16} className="text-ink-soft" />
          <h2 className="text-[15px] font-semibold">Registro automático al pagar</h2>
          <span className="text-[11px] font-bold text-ink-soft bg-line px-2 py-0.5 rounded-full uppercase tracking-wide">
            Avanzado
          </span>
        </div>
        <div className="rounded-2xl bg-paper-raised border border-line p-4">
          <p className="text-xs text-ink-soft mb-3">
            Anota solos tus pagos con el celular: con Atajos del iPhone, Tasker en Android o con Siri.
            Hay que configurarlo una vez. Si registras desde la app, no lo necesitas.
          </p>
          <ClaveAtajo {...claveAtajo} />
          <Link
            to="/conectar-dispositivo"
            className="flex items-center justify-center gap-1.5 mt-3 text-sm text-accent font-semibold"
          >
            Ver guía paso a paso (iPhone/Android) <ChevronRight size={16} />
          </Link>
        </div>
      </section>
      )}

      <section className="mx-6 mt-8">
        <div className="flex items-center gap-2 mb-3">
          <Palette size={16} className="text-ink-soft" />
          <h2 className="text-[15px] font-semibold">Apariencia</h2>
        </div>
        <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
          {THEMES.map((t) => (
            <button
              key={t.id}
              onClick={() => setTheme(t.id)}
              aria-pressed={theme === t.id}
              className="w-full flex items-center gap-3 px-4 py-3.5 text-left"
            >
              <span
                className="w-11 h-11 rounded-full shrink-0 border border-line"
                style={{ background: themePreview[t.id] }}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{t.nombre}</p>
                <p className="text-xs text-ink-soft">{t.desc}</p>
              </div>
              {theme === t.id && <Check size={20} className="text-accent shrink-0" />}
            </button>
          ))}
        </div>
        {/* Cuadri, la mascota: se guarda solo en este dispositivo y viene activado */}
        <div className="rounded-2xl bg-paper-raised border border-line p-4 flex items-center gap-3 mt-3">
          <Cuadri pose="feliz" size={52} siempre animar={false} />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium" id="etq-mostrar-cuadri">Mostrar a Cuadri</p>
            <p className="text-xs text-ink-soft mt-0.5">La mascota de CuadraMe acompaña el recorrido, los consejos y las celebraciones. Se guarda en este dispositivo.</p>
          </div>
          <button
            type="button"
            onClick={() => cambiarCuadri(!mostrarCuadri)}
            role="switch"
            aria-checked={mostrarCuadri}
            aria-labelledby="etq-mostrar-cuadri"
            data-testid="switch-mostrar-cuadri"
            className="shrink-0 min-h-11 w-14 flex items-center justify-center"
          >
            <span className={`block w-12 h-7 rounded-full transition-colors relative ${mostrarCuadri ? 'bg-accent' : 'bg-line'}`}>
              <span
                className={`absolute top-0.5 left-0 w-6 h-6 rounded-full bg-white shadow transition-transform ${
                  mostrarCuadri ? 'translate-x-5' : 'translate-x-0.5'
                }`}
              />
            </span>
          </button>
        </div>
      </section>

      <SeccionPrivacidad onEliminarCuenta={eliminarMiCuenta} eliminando={eliminandoCuenta} />

      <section className="mx-6 mt-6">
        <h2 className="text-[15px] font-semibold mb-3">Legal</h2>
        <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
          <Link to="/legal/terminos" className="flex items-center gap-3 px-4 py-3.5">
            <FileText size={20} className="text-ink-soft shrink-0" />
            <p className="flex-1 text-sm font-medium">Términos y Condiciones</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/legal/privacidad" className="flex items-center gap-3 px-4 py-3.5">
            <FileText size={20} className="text-ink-soft shrink-0" />
            <p className="flex-1 text-sm font-medium">Política de Privacidad</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/legal/autorizacion-datos" className="flex items-center gap-3 px-4 py-3.5">
            <FileText size={20} className="text-ink-soft shrink-0" />
            <p className="flex-1 text-sm font-medium">Autorización de datos</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
        </div>
      </section>

      <section className="mx-6 mt-6">
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 rounded-2xl bg-paper-raised border border-line px-4 py-3.5 text-danger font-medium text-sm"
        >
          <LogOut size={20} /> Cerrar sesión
        </button>
      </section>

      <footer className="flex flex-col items-center gap-1.5 mt-8 mb-2">
        <img src="/icons/icon-192.png" alt="CuadraMe" className="w-8 h-8 rounded-xl" />
        <p className="text-[11px] text-ink-soft">CuadraMe · Hecho por DAPX</p>
      </footer>
    </div>
  )
}

const themePreview = {
  auto: 'linear-gradient(135deg, #d9622b, #17140f)',
  calido: 'linear-gradient(135deg, #d9622b, #d9a441)',
  dark: 'linear-gradient(135deg, #17140f, #e8823f)',
}
