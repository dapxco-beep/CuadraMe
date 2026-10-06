import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, Receipt, Check, ChevronRight, Copy, CreditCard, FileText, FileUp, GraduationCap, Landmark, Link2, List, LogOut, Mail, Trash2, Palette, PiggyBank, RefreshCw, Repeat, Sprout, Tag, Users, Wand2 } from 'lucide-react'
import { useTheme, THEMES } from '../lib/ThemeContext'
import { useAuth } from '../lib/AuthContext'
import { api } from '../lib/api'
import { useDialogos } from '../lib/DialogosContext'
import SeccionSeguridad from '../components/SeccionSeguridad'
import SeccionPrivacidad from '../components/SeccionPrivacidad'
import { activarPush, desactivarPush, estadoPermiso, pushSoportado } from '../lib/push'

export default function Perfil() {
  const { theme, setTheme } = useTheme()
  const { usuario, logout } = useAuth()
  const { confirmar, avisar } = useDialogos()
  const [apiKey, setApiKey] = useState(null)
  const [copiado, setCopiado] = useState(false)
  const [permisoPush, setPermisoPush] = useState('default')
  const [cargandoPush, setCargandoPush] = useState(false)
  const [recordatorio, setRecordatorio] = useState(false)
  const [confianza, setConfianza] = useState(0.75)
  const [guardandoConfianza, setGuardandoConfianza] = useState(false)
  const [eliminandoCuenta, setEliminandoCuenta] = useState(false)

  useEffect(() => {
    api.apiKey().then((r) => setApiKey(r.api_key)).catch(() => {})
    estadoPermiso().then(setPermisoPush)
    api.confianzaAutoimport().then((r) => setConfianza(r.confianza_autoimport)).catch(() => {})
    Promise.resolve().then(() => api.recordatorioDiario()).then((r) => setRecordatorio(!!r.activo)).catch(() => {})
  }, [])

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
      avisar(err.message || 'No se pudo cambiar el recordatorio')
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
      avisar(err.message || 'No se pudo activar las notificaciones')
    } finally {
      setCargandoPush(false)
    }
  }

  async function copiarApiKey() {
    if (!apiKey) return
    await navigator.clipboard.writeText(apiKey)
    setCopiado(true)
    setTimeout(() => setCopiado(false), 2000)
  }

  async function regenerarApiKey() {
    const ok = await confirmar(
      'Los atajos que ya configuraste dejarán de funcionar hasta que actualices la clave ahí.',
      { titulo: 'Esto invalida la API key anterior', confirmarTexto: 'Regenerar', peligro: true }
    )
    if (!ok) return
    try {
      const { api_key } = await api.regenerarApiKey()
      setApiKey(api_key)
    } catch (err) {
      avisar(err.message || 'No se pudo regenerar la API key')
    }
  }

  async function eliminarMiCuenta() {
    const ok = await confirmar(
      'Se borrarán para siempre tus cuentas, movimientos, presupuestos, metas y todo lo demás. No se puede deshacer. Si quieres conservar tus datos, primero expórtalos desde Movimientos.',
      { titulo: '¿Eliminar tu cuenta y todos tus datos?', confirmarTexto: 'Sí, eliminar todo', peligro: true }
    )
    if (!ok) return
    setEliminandoCuenta(true)
    try {
      await api.eliminarMiCuenta()
      await logout()
    } catch (err) {
      setEliminandoCuenta(false)
      avisar(err.message || 'No se pudo eliminar la cuenta')
    }
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pantalla-top pb-2">
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

      <section className="mx-6 mt-6">
        <h2 className="text-[15px] font-semibold mb-3">Tus cuentas</h2>
        <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
          <Link to="/cuentas" className="flex items-center gap-3 px-4 py-3.5">
            <Landmark size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Ver y editar mis cuentas</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/movimientos" className="flex items-center gap-3 px-4 py-3.5">
            <List size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Todos mis movimientos</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/compartir" className="flex items-center gap-3 px-4 py-3.5">
            <Users size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Compartir una cuenta</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
        </div>
      </section>

      <section className="mx-6 mt-6">
        <h2 className="text-[15px] font-semibold mb-3">Registro automático</h2>
        <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
          <Link to="/sincronizacion" className="flex items-center gap-3 px-4 py-3.5">
            <RefreshCw size={18} className="text-accent shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium">Sincronización</p>
              <p className="text-xs text-ink-soft mt-0.5">Qué falta conciliar, subir o categorizar</p>
            </div>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/conexiones" className="flex items-center gap-3 px-4 py-3.5">
            <RefreshCw size={18} className="text-accent shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium">Conexiones y estado</p>
              <p className="text-xs text-ink-soft mt-0.5">Mira si Gmail, el Atajo y las notificaciones funcionan</p>
            </div>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/correos" className="flex items-center gap-3 px-4 py-3.5">
            <Mail size={18} className="text-accent shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium">Leer correos bancarios</p>
              <p className="text-xs text-ink-soft mt-0.5">Conecta tu Gmail y sugerimos movimientos por ti</p>
            </div>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/conciliacion" className="flex items-center gap-3 px-4 py-3.5">
            <FileUp size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Subir extracto (PDF)</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/importar" className="flex items-center gap-3 px-4 py-3.5">
            <FileUp size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Importar Excel o CSV</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
        </div>

        <div className="rounded-2xl bg-paper-raised border border-line p-4 mt-3">
          <p className="text-sm font-medium">Qué tan seguro debe estar para auto-importar</p>
          <p className="text-xs text-ink-soft mt-0.5 mb-3">
            Al conciliar un extracto, un movimiento se registra solo (sin pedirte que lo revises)
            cuando la categoría detectada supera este nivel de seguridad.
          </p>
          <input
            type="range"
            min="0.5"
            max="0.95"
            step="0.05"
            value={confianza}
            onChange={(e) => cambiarConfianza(Number(e.target.value))}
            className="w-full accent-accent"
          />
          <div className="flex items-center justify-between text-xs text-ink-soft mt-1">
            <span>Más permisivo</span>
            <span className="font-semibold text-ink">{Math.round(confianza * 100)}%{guardandoConfianza ? ' · guardando...' : ''}</span>
            <span>Más estricto</span>
          </div>
        </div>
      </section>

      <section className="mx-6 mt-6">
        <h2 className="text-[15px] font-semibold mb-3">Planeación</h2>
        <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
          <Link to="/metas" className="flex items-center gap-3 px-4 py-3.5">
            <PiggyBank size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Metas de ahorro</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/recurrentes" className="flex items-center gap-3 px-4 py-3.5">
            <Repeat size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Gastos recurrentes</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/deudas" className="flex items-center gap-3 px-4 py-3.5">
            <CreditCard size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Deudas</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/reglas-categoria" className="flex items-center gap-3 px-4 py-3.5">
            <Wand2 size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Reglas de categorización</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/entrenar-categorias" className="flex items-center gap-3 px-4 py-3.5">
            <GraduationCap size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Entrenar categorías</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/categorias" className="flex items-center gap-3 px-4 py-3.5">
            <Tag size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Categorías</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
        </div>
      </section>

      <section className="mx-6 mt-6">
        <h2 className="text-[15px] font-semibold mb-3">Extra</h2>
        <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
          <Link to="/impuestos" className="flex items-center gap-3 px-4 py-3.5">
            <Receipt size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Impuestos (4x1000 y renta)</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/cierre-mes" className="flex items-center gap-3 px-4 py-3.5">
            <FileText size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Cierre de mes</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/ahorcado" className="flex items-center gap-3 px-4 py-3.5">
            <Sprout size={18} className="text-accent shrink-0" />
            <p className="flex-1 text-sm font-medium">Tu árbol financiero</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
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
                permisoPush === 'granted' ? 'bg-accent' : 'bg-line'
              } disabled:opacity-60`}
            >
              <span
                className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform ${
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
              className={`shrink-0 w-12 h-7 rounded-full transition-colors relative ${recordatorio ? 'bg-accent' : 'bg-line'}`}
            >
              <span
                className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform ${
                  recordatorio ? 'translate-x-5' : 'translate-x-0.5'
                }`}
              />
            </button>
          </div>
        </section>
      )}

      <SeccionSeguridad />

      <section className="mx-6 mt-8">
        <div className="flex items-center gap-2 mb-3">
          <Link2 size={16} className="text-ink-soft" />
          <h2 className="text-[15px] font-semibold">Conectar dispositivos</h2>
          <span className="text-[11px] font-bold text-ink-soft bg-line px-2 py-0.5 rounded-full uppercase tracking-wide">
            Avanzado
          </span>
        </div>
        <div className="rounded-2xl bg-paper-raised border border-line p-4">
          <p className="text-xs text-ink-soft mb-3">
            Para quienes quieren automatizar el registro con apps de terceros (Atajos de iOS,
            Tasker en Android) o por voz con Siri. Requiere algo de configuración manual — si solo
            quieres registrar rápido desde la app, no necesitas esto.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs bg-paper rounded-xl px-3 py-2.5 truncate">
              {apiKey || 'Cargando...'}
            </code>
            <button
              onClick={copiarApiKey}
              disabled={!apiKey}
              className="shrink-0 w-11 h-11 rounded-xl bg-paper flex items-center justify-center disabled:opacity-50"
              aria-label="Copiar"
            >
              <Copy size={15} className={copiado ? 'text-accent' : 'text-ink-soft'} />
            </button>
            <button
              onClick={regenerarApiKey}
              disabled={!apiKey}
              className="shrink-0 w-11 h-11 rounded-xl bg-paper flex items-center justify-center disabled:opacity-50"
              aria-label="Regenerar"
            >
              <RefreshCw size={15} className="text-ink-soft" />
            </button>
          </div>
          {copiado && <p className="text-xs text-accent mt-2">Copiada al portapapeles</p>}
          <Link
            to="/conectar-dispositivo"
            className="flex items-center justify-center gap-1.5 mt-3 text-sm text-accent font-semibold"
          >
            Ver guía paso a paso (iPhone/Android) <ChevronRight size={15} />
          </Link>
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
              {theme === t.id && <Check size={18} className="text-accent shrink-0" />}
            </button>
          ))}
        </div>
      </section>

      <SeccionPrivacidad onEliminarCuenta={eliminarMiCuenta} eliminando={eliminandoCuenta} />

      <section className="mx-6 mt-6">
        <h2 className="text-[15px] font-semibold mb-3">Legal</h2>
        <div className="rounded-2xl bg-paper-raised border border-line overflow-hidden divide-y divide-line">
          <Link to="/legal/terminos" className="flex items-center gap-3 px-4 py-3.5">
            <FileText size={18} className="text-ink-soft shrink-0" />
            <p className="flex-1 text-sm font-medium">Términos y Condiciones</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/legal/privacidad" className="flex items-center gap-3 px-4 py-3.5">
            <FileText size={18} className="text-ink-soft shrink-0" />
            <p className="flex-1 text-sm font-medium">Política de Privacidad</p>
            <ChevronRight size={16} className="text-ink-soft" />
          </Link>
          <Link to="/legal/autorizacion-datos" className="flex items-center gap-3 px-4 py-3.5">
            <FileText size={18} className="text-ink-soft shrink-0" />
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
          <LogOut size={18} /> Cerrar sesión
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
