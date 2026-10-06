import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Bell, Copy, FileCheck2, KeyRound, Mail, RefreshCw, Send, Smartphone } from 'lucide-react'
import { api } from '../lib/api'
import { useDialogos } from '../lib/DialogosContext'
import { activarPush, estadoPermiso, pushSoportado } from '../lib/push'
import { haceCuanto, resumenSync, sincronizarTodo } from '../lib/sincronizarGmail'

// Semáforo: color + texto (no solo color, para que se entienda sin distinguirlos).
const SEMAFORO = {
  verde: { punto: 'bg-cuadra', texto: 'Funciona' },
  ambar: { punto: 'bg-accent-2', texto: 'Revisar' },
  rojo: { punto: 'bg-danger', texto: 'Falla' },
}

function Tarjeta({ icono: Icono, titulo, semaforo, mensaje, children, testid }) {
  const s = SEMAFORO[semaforo] || SEMAFORO.ambar
  return (
    <section className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-4" data-testid={testid} aria-label={titulo}>
      <div className="flex items-center gap-3">
        <Icono size={18} className="text-accent shrink-0" />
        <h2 className="text-[15px] font-semibold flex-1">{titulo}</h2>
        <span className="flex items-center gap-1.5 text-[11px] font-semibold text-ink-soft" data-semaforo={semaforo}>
          <span className={`w-2.5 h-2.5 rounded-full ${s.punto}`} aria-hidden="true" />
          {s.texto}
        </span>
      </div>
      <p className="text-xs text-ink-soft mt-2 leading-relaxed">{mensaje}</p>
      {children}
    </section>
  )
}

function Dato({ etiqueta, valor }) {
  return (
    <div className="rounded-xl bg-paper px-3 py-2 min-w-0">
      <p className="text-sm font-bold truncate">{valor}</p>
      <p className="text-[11px] text-ink-soft">{etiqueta}</p>
    </div>
  )
}

const Boton = ({ className = '', ...p }) => (
  <button
    {...p}
    className={`flex items-center justify-center gap-1.5 rounded-xl py-2.5 px-3 text-sm font-semibold disabled:opacity-60 ${className}`}
  />
)

function esIphoneSinInstalar() {
  if (typeof navigator === 'undefined') return false
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent)
  const instalada = navigator.standalone === true || window.matchMedia?.('(display-mode: standalone)')?.matches
  return ios && !instalada
}

function TarjetaGmail({ g, navigate, recargar }) {
  const [progreso, setProgreso] = useState(null)
  const [resultado, setResultado] = useState('')
  const [error, setError] = useState('')
  const activo = useRef(true)
  useEffect(() => () => { activo.current = false }, [])

  async function sincronizar() {
    setError('')
    setResultado('')
    setProgreso({ leidos: 0, total_estimado: 0 })
    try {
      const r = await sincronizarTodo({
        onProgreso: (p) => activo.current && setProgreso({ leidos: p.leidos, total_estimado: p.total_estimado }),
      })
      if (!activo.current) return
      if (!r?.ok) setError(r?.error || 'No se pudo sincronizar')
      else setResultado(resumenSync(r))
    } catch (err) {
      if (activo.current) setError(err.message || 'No se pudo sincronizar')
    } finally {
      if (activo.current) {
        setProgreso(null)
        recargar()
      }
    }
  }

  const sincronizando = Boolean(progreso)
  const total = progreso?.total_estimado || 0
  const pct = total ? Math.min(100, Math.round((progreso.leidos / total) * 100)) : 0

  return (
    <Tarjeta icono={Mail} titulo="Gmail" semaforo={g.semaforo} mensaje={g.mensaje} testid="tarjeta-gmail">
      {g.conectado && (
        <>
          <p className="text-xs mt-2 truncate">
            {g.email} · {g.ultima_sync ? `última sincronización ${haceCuanto(g.ultima_sync)}` : 'sin sincronizar todavía'}
          </p>
          <div className="grid grid-cols-3 gap-2 mt-3">
            <Dato etiqueta="correos leídos" valor={g.correos_leidos} />
            <Dato etiqueta="notificaciones" valor={g.notificaciones} />
            <Dato etiqueta="extractos" valor={g.extractos} />
          </div>
          {g.extractos_falta_clave > 0 && (
            <p className="text-xs mt-2">
              {g.extractos_falta_clave} esperan clave.{' '}
              <button className="underline text-accent font-semibold" onClick={() => navigate('/correos')}>
                Guardar la clave del PDF
              </button>
            </p>
          )}
        </>
      )}
      {sincronizando && (
        <div className="mt-3" role="status">
          <div className="h-2 rounded-full bg-line overflow-hidden">
            <div
              className="h-full bg-accent transition-all duration-300"
              style={{ width: `${pct}%` }}
              role="progressbar"
              aria-valuenow={pct}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          <p className="text-xs text-ink-soft mt-1.5">
            {total ? `Leí ${progreso.leidos} de ${total}` : 'Empezando...'} · puedes seguir usando la app
          </p>
        </div>
      )}
      {error && <p className="text-xs text-danger mt-2">{error}</p>}
      {resultado && !error && <p className="text-xs font-semibold mt-2">{resultado}</p>}
      <div className="flex gap-2 mt-3">
        {g.conectado ? (
          <Boton onClick={sincronizar} disabled={sincronizando} className="flex-1 bg-ink text-paper">
            <RefreshCw size={14} className={sincronizando ? 'animate-spin' : ''} />
            {sincronizando ? 'Sincronizando...' : 'Sincronizar todo'}
          </Boton>
        ) : (
          <Boton onClick={() => navigate('/correos')} className="flex-1 bg-ink text-paper">
            Conectar Gmail
          </Boton>
        )}
        {g.conectado && (
          <Boton onClick={() => navigate('/correos')} className="border border-line text-ink-soft">
            Ver correos
          </Boton>
        )}
      </div>
    </Tarjeta>
  )
}

function TarjetaAtajo({ a, recargar }) {
  const { confirmar } = useDialogos()
  const [aviso, setAviso] = useState('')
  const [error, setError] = useState('')
  const [probando, setProbando] = useState(false)

  async function copiar() {
    setError('')
    try {
      const { api_key } = await api.apiKey()
      await navigator.clipboard.writeText(api_key)
      setAviso('Clave copiada.')
    } catch {
      setError('No se pudo copiar. Cópiala desde Perfil > Registro automático.')
    }
  }

  async function regenerar() {
    const ok = await confirmar('La clave actual dejará de funcionar: tendrás que pegar la nueva en tu Atajo.', {
      titulo: '¿Generar una clave nueva?',
      confirmarTexto: 'Generar y revocar la anterior',
      peligro: true,
    })
    if (!ok) return
    setError('')
    try {
      await api.regenerarApiKey()
      setAviso('Clave nueva generada. La anterior ya no sirve; cópiala y pégala en tu Atajo.')
      recargar()
    } catch (err) {
      setError(err.message || 'No se pudo generar la clave')
    }
  }

  async function probar() {
    setProbando(true)
    setError('')
    setAviso('')
    try {
      const { api_key } = await api.apiKey()
      const r = await api.pagoDePrueba(api_key)
      const lista = await api.movimientosPorConfirmar()
      if (!lista.some((m) => m.id === r.id)) throw new Error('Se envió pero no apareció por confirmar. Intenta de nuevo.')
      // El pago de prueba no es real: se borra para no descuadrar el saldo.
      await api.eliminarMovimiento(r.id).catch(() => {})
      setAviso('¡Llegó! La conexión funciona (el pago de prueba ya se borró).')
      window.dispatchEvent(new CustomEvent('cuadrame:movimientos-cambio'))
      recargar()
    } catch (err) {
      setError(err.status === 401 ? 'Tu clave no es válida. Genera una nueva.' : err.message || 'No se pudo probar')
    } finally {
      setProbando(false)
    }
  }

  return (
    <Tarjeta icono={Smartphone} titulo="Atajo de iPhone y clave API" semaforo={a.semaforo} mensaje={a.mensaje} testid="tarjeta-atajo">
      <div className="grid grid-cols-2 gap-2 mt-3">
        <Dato etiqueta="último uso" valor={haceCuanto(a.ultimo_uso) || 'nunca'} />
        <Dato etiqueta="movimientos en 7 días" valor={a.movimientos_7d} />
      </div>
      {error && <p className="text-xs text-danger mt-2">{error}</p>}
      {aviso && !error && <p className="text-xs font-semibold mt-2" role="status">{aviso}</p>}
      <div className="grid grid-cols-3 gap-2 mt-3">
        <Boton onClick={copiar} className="border border-line">
          <Copy size={13} /> Copiar clave
        </Boton>
        <Boton onClick={regenerar} className="border border-line">
          <KeyRound size={13} /> Clave nueva
        </Boton>
        <Boton onClick={probar} disabled={probando} className="bg-accent text-white">
          <Send size={13} /> {probando ? 'Probando...' : 'Probar conexión'}
        </Boton>
      </div>
    </Tarjeta>
  )
}

function TarjetaConciliacion({ c, navigate }) {
  const cuentas = c.cuentas || []
  return (
    <Tarjeta icono={FileCheck2} titulo="Conciliación con el banco" semaforo={c.semaforo} mensaje={c.mensaje} testid="tarjeta-conciliacion">
      <div className="flex flex-col gap-2 mt-3">
        {cuentas.length === 0 && <p className="text-xs text-ink-soft">Crea una cuenta para poder cruzar extractos.</p>}
        {cuentas.map((f) => (
          <div key={f.cuenta_id} className="rounded-xl bg-paper p-3" data-testid="fila-conciliacion">
            <p className="text-sm font-semibold truncate">{f.icono} {f.cuenta}</p>
            {f.extracto ? (
              <>
                <p className="text-xs text-ink-soft mt-1">
                  <b>{f.cruzados}</b> cruzados con el banco · <b>{f.faltantes}</b> faltantes · <b>{f.sin_extracto}</b> registrados sin extracto
                </p>
                <p className="text-[11px] text-ink-soft">Último cruce {haceCuanto(f.ultimo_cruce)}</p>
                <Boton
                  onClick={() => navigate('/conciliacion', { state: { historialId: f.historial_id } })}
                  className="w-full mt-2 border border-line"
                >
                  Conciliar ahora
                </Boton>
              </>
            ) : (
              <>
                <p className="text-xs text-ink-soft mt-1">Aún sin extracto procesado.</p>
                <Boton onClick={() => navigate('/conciliacion')} className="w-full mt-2 border border-line">
                  Importar extracto
                </Boton>
              </>
            )}
          </div>
        ))}
      </div>
    </Tarjeta>
  )
}

function TarjetaPush({ p }) {
  const [permiso, setPermiso] = useState(null)
  const [activa, setActiva] = useState(null)
  const [error, setError] = useState('')
  const sinInstalar = esIphoneSinInstalar()

  async function leerEstadoLocal() {
    try {
      setPermiso(await estadoPermiso())
      const reg = await navigator.serviceWorker?.getRegistration?.()
      setActiva(Boolean(await reg?.pushManager?.getSubscription()))
    } catch {
      setActiva(false)
    }
  }
  useEffect(() => {
    if (pushSoportado()) leerEstadoLocal()
  }, [])

  async function activar() {
    setError('')
    try {
      await activarPush()
      await leerEstadoLocal()
    } catch (err) {
      setError(err.message || 'No se pudieron activar')
    }
  }

  let semaforo = p.semaforo
  let mensaje = p.mensaje
  if (activa) {
    semaforo = 'verde'
    mensaje = 'Las notificaciones están activas en este dispositivo.'
  } else if (permiso === 'denied') {
    semaforo = 'rojo'
    mensaje = 'Bloqueaste las notificaciones. Actívalas en los ajustes del navegador o del teléfono.'
  } else if (p.suscripciones > 0) {
    mensaje = 'Están activas en otro dispositivo, pero no en este.'
  }

  return (
    <Tarjeta icono={Bell} titulo="Notificaciones" semaforo={semaforo} mensaje={mensaje} testid="tarjeta-push">
      {sinInstalar ? (
        <div className="mt-3 rounded-xl bg-accent-soft p-3" data-testid="pasos-instalar">
          <p className="text-sm font-semibold">Primero añade la app a tu pantalla de inicio</p>
          <ol className="text-xs mt-1.5 list-decimal pl-4 space-y-0.5">
            <li>En Safari toca Compartir (el cuadro con la flecha).</li>
            <li>Elige «Añadir a pantalla de inicio».</li>
            <li>Abre CuadraMe desde ese ícono y vuelve aquí.</li>
          </ol>
        </div>
      ) : !pushSoportado() ? (
        <p className="text-xs text-ink-soft mt-2">Este navegador no admite notificaciones.</p>
      ) : (
        !activa && permiso !== 'denied' && (
          <Boton onClick={activar} className="w-full mt-3 bg-ink text-paper">
            Activar notificaciones
          </Boton>
        )
      )}
      {error && <p className="text-xs text-danger mt-2">{error}</p>}
    </Tarjeta>
  )
}

export default function Conexiones() {
  const navigate = useNavigate()
  const volver = useVolver('/perfil')
  const [estado, setEstado] = useState(null)
  const [error, setError] = useState('')

  function recargar() {
    return api
      .conexionesEstado()
      .then((e) => {
        setEstado(e)
        setError('')
      })
      .catch((err) => setError(err.message || 'No se pudo cargar el estado'))
  }
  useEffect(() => {
    recargar()
  }, [])

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Conexiones y estado</h1>
      </header>
      <p className="px-6 text-xs text-ink-soft">
        Aquí ves de un vistazo si todo lo que te registra los movimientos solo está funcionando.
      </p>
      {error && (
        <p role="alert" className="mx-6 mt-3 text-xs text-danger">
          {error}{' '}
          <button className="underline font-semibold" onClick={recargar}>Reintentar</button>
        </p>
      )}
      {!estado && !error && <p className="px-6 mt-6 text-sm text-ink-soft">Cargando...</p>}
      {estado && (
        <>
          <TarjetaGmail g={estado.gmail} navigate={navigate} recargar={recargar} />
          <TarjetaAtajo a={estado.atajo} recargar={recargar} />
          <TarjetaConciliacion c={estado.conciliacion} navigate={navigate} />
          <TarjetaPush p={estado.push} />
        </>
      )}
    </div>
  )
}
