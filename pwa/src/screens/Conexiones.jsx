import { textoError } from '../lib/textoError'
import { useEffect, useRef, useState } from 'react'
import { EsqueletoLista } from '../components/Esqueletos'
import { useNavigate } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, Bell, Copy, FileCheck2, KeyRound, Mail, RefreshCw, Send, Smartphone } from 'lucide-react'
import { api } from '../lib/api'
import { useDialogos } from '../lib/DialogosContext'
import { activarPush, estadoPermiso, pushSoportado } from '../lib/push'
import { haceCuanto, resumenSync, sincronizarTodo } from '../lib/sincronizarGmail'
import { mensajeAmable } from '../lib/mensajes'
import { ATAJO_NOTIFICACIONES_URL, ATAJO_REGISTRAR_URL } from '../lib/atajosEnlaces'
import TarjetaGestoRegistro from '../components/TarjetaGestoRegistro'

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
        <Icono size={20} className="text-accent shrink-0" />
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

function TarjetaGmail({ g, ir, recargar }) {
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
      if (!r?.ok) setError(mensajeAmable(r?.error, { porDefecto: 'No pudimos traer tus correos. Intenta de nuevo.' }))
      else setResultado(resumenSync(r))
    } catch (err) {
      if (activo.current) setError(err.message || 'No pudimos traer los movimientos')
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
            {g.email} · {g.ultima_sync ? `última vez ${haceCuanto(g.ultima_sync)}` : 'todavía no se traen movimientos'}
          </p>
          <div className="grid grid-cols-3 gap-2 mt-3">
            <Dato etiqueta="correos leídos" valor={g.correos_leidos} />
            <Dato etiqueta="notificaciones" valor={g.notificaciones} />
            <Dato etiqueta="extractos" valor={g.extractos} />
          </div>
          {g.extractos_falta_clave > 0 && (
            <p className="text-xs mt-2">
              {g.extractos_falta_clave} esperan clave.{' '}
              <button className="underline text-accent font-semibold" onClick={() => ir('correo')}>
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
              className="h-full w-full bg-accent barra-fill"
              style={{ transform: `scaleX(${pct / 100})` }}
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
            <RefreshCw size={16} className={sincronizando ? 'animate-spin' : ''} />
            {sincronizando ? 'Trayendo movimientos...' : 'Traer todo ahora'}
          </Boton>
        ) : (
          <Boton onClick={() => ir('correo')} className="flex-1 bg-ink text-paper">
            Conectar Gmail
          </Boton>
        )}
        {g.conectado && (
          <Boton onClick={() => ir('correo')} className="border border-line text-ink-soft">
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
  // Clave completa: solo existe en memoria justo después de crearla (el servidor guarda su hash).
  const [claveNueva, setClaveNueva] = useState(null)

  async function copiar() {
    setError('')
    try {
      let clave = claveNueva
      if (!clave) {
        // Claves antiguas aún en claro siguen pudiéndose leer; las nuevas ya no.
        const r = await api.apiKey()
        clave = r.api_key
      }
      if (!clave) {
        setError('Tu clave es de antes de poder volver a verla. Aparecerá aquí sola en cuanto uno de tus atajos la use una vez; si no, pulsa «Clave nueva».')
        return
      }
      await navigator.clipboard.writeText(clave)
      setAviso('Clave copiada.')
    } catch {
      setError('No se pudo copiar. Inténtalo de nuevo o crea una clave nueva.')
    }
  }

  async function regenerar() {
    const ok = await confirmar('Tu Atajo del iPhone dejará de funcionar hasta que pegues la clave nueva en él.', {
      titulo: '¿Generar una clave nueva?',
      confirmarTexto: 'Generar y revocar la anterior',
      peligro: true,
    })
    if (!ok) return
    setError('')
    try {
      const r = await api.regenerarApiKey()
      setClaveNueva(r.api_key || null)
      setAviso('Clave nueva lista. Cópiala y pégala en tu Atajo; podrás volver a verla aquí. La anterior ya no sirve.')
      recargar()
    } catch (err) {
      setError(textoError(err, 'generar la clave'))
    }
  }

  async function probar() {
    setProbando(true)
    setError('')
    setAviso('')
    try {
      // Sin leer la clave guardada: con la clave recién creada prueba el camino real del Atajo;
      // si no, el servidor registra la prueba con tu sesión.
      const r = await api.pagoDePrueba(claveNueva || undefined)
      const lista = await api.movimientosPorConfirmar()
      if (!lista.some((m) => m.id === r.id)) throw new Error('Se envió pero no apareció por confirmar. Intenta de nuevo.')
      // El pago de prueba no es real: se borra para no descuadrar el saldo.
      await api.eliminarMovimiento(r.id).catch(() => {})
      setAviso('¡Llegó! La conexión funciona (el pago de prueba ya se borró).')
      window.dispatchEvent(new CustomEvent('cuadrame:movimientos-cambio'))
      recargar()
    } catch (err) {
      setError(err.status === 401 ? 'Tu clave no es válida. Genera una nueva.' : textoError(err, 'probar'))
    } finally {
      setProbando(false)
    }
  }

  return (
    <Tarjeta icono={Smartphone} titulo="Conecta tu iPhone (Apple Pay)" semaforo={a.semaforo} mensaje={a.mensaje} testid="tarjeta-atajo">
      <div className="grid grid-cols-2 gap-2 mt-3">
        <Dato etiqueta="último uso" valor={haceCuanto(a.ultimo_uso) || 'nunca'} />
        <Dato etiqueta="movimientos en 7 días" valor={a.movimientos_7d} />
      </div>
      {error && <p className="text-xs text-danger mt-2">{error}</p>}
      {aviso && !error && <p className="text-xs font-semibold mt-2" role="status">{aviso}</p>}
      {claveNueva && (
        <code data-testid="clave-nueva" className="block text-xs bg-paper rounded-xl px-3 py-2.5 mt-2 break-all select-all">{claveNueva}</code>
      )}
      <div className="grid grid-cols-3 gap-2 mt-3">
        <Boton onClick={copiar} className="border border-line">
          <Copy size={16} /> Copiar clave
        </Boton>
        <Boton onClick={regenerar} className="border border-line">
          <KeyRound size={16} /> Clave nueva
        </Boton>
        <Boton onClick={probar} disabled={probando} className="bg-accent text-paper-raised">
          <Send size={16} /> {probando ? 'Probando...' : 'Probar conexión'}
        </Boton>
      </div>
    </Tarjeta>
  )
}

// Registro automático desde las notificaciones del banco (iPhone, iOS 27): una fila por cada cuenta tuya que el atajo sabe
// leer. «Conectado» = ya llegó algún aviso de esa cuenta; si no, «Falta conectar». Sin cuentas reconocidas no se muestra.
function TarjetaAvisosBanco() {
  const [filas, setFilas] = useState(null)
  const [reglas, setReglas] = useState([])
  useEffect(() => {
    let vivo = true
    Promise.resolve()
      .then(() => api.estadoNotificaciones())
      .then((r) => vivo && setFilas(Array.isArray(r) ? r : []))
      .catch(() => vivo && setFilas([]))
    Promise.resolve()
      .then(() => api.reglasNotificacion())
      .then((r) => vivo && setReglas(Array.isArray(r) ? r : []))
      .catch(() => {})
    return () => { vivo = false }
  }, [])

  async function olvidar(id) {
    try {
      await api.borrarReglaNotificacion(id)
      setReglas((rs) => rs.filter((r) => r.id !== id))
    } catch {
      /* si falla, la regla sigue en la lista y se puede reintentar */
    }
  }
  if (!filas || filas.length === 0) return null
  const faltan = filas.filter((f) => !f.ultimo_aviso)
  const semaforo = faltan.length === 0 ? 'verde' : 'ambar'
  const mensaje = faltan.length === 0
    ? 'Tus bancos avisan solos: cada movimiento llega a CuadraMe apenas lo notifica la app del banco.'
    : `Falta conectar: ${[...new Set(faltan.map((f) => f.app))].join(', ')}. Así CuadraMe registra cada movimiento apenas el banco te avisa.`
  return (
    <Tarjeta icono={Bell} titulo="Registro automático desde el banco" semaforo={semaforo} mensaje={mensaje} testid="tarjeta-avisos-banco">
      <ul className="mt-3 space-y-1.5">
        {filas.map((f) => (
          <li key={f.cuenta_id} className="flex items-center justify-between gap-3 rounded-xl bg-paper px-3 py-2 text-sm">
            <span className="font-semibold truncate">{f.cuenta}</span>
            <span className="text-xs text-ink-soft shrink-0">
              {f.ultimo_aviso ? `Conectado · último aviso ${haceCuanto(f.ultimo_aviso) || ''}` : 'Falta conectar'}
            </span>
          </li>
        ))}
      </ul>
      <a
        href={ATAJO_NOTIFICACIONES_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center justify-center gap-1.5 rounded-xl py-2.5 px-3 text-sm font-semibold bg-accent text-paper-raised mt-3"
      >
        <Smartphone size={16} /> Instalar el atajo en mi iPhone
      </a>
      {reglas.length > 0 && (
        <details className="mt-3 text-xs text-ink-soft" data-testid="reglas-aprendidas">
          <summary className="cursor-pointer font-semibold text-ink">Lo que aprendió tu atajo ({reglas.length})</summary>
          <p className="mt-2 leading-relaxed">
            Cuando respondes una pregunta del atajo, CuadraMe recuerda la forma del aviso (sin guardar el texto, nombres ni montos) para no volver a preguntar.
          </p>
          <ul className="mt-2 space-y-1.5">
            {reglas.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-3 rounded-xl bg-paper px-3 py-2">
                <span className="min-w-0">
                  <span className="font-semibold text-ink">{r.app}</span>: {r.significado}
                </span>
                <button onClick={() => olvidar(r.id)} className="shrink-0 underline font-semibold text-ink" aria-label={`Olvidar lo aprendido de ${r.app}`}>
                  Olvidar
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
      <details className="mt-3 text-xs text-ink-soft">
        <summary className="cursor-pointer font-semibold text-ink">Cómo conectar cada banco (3 minutos)</summary>
        <ol className="list-decimal pl-5 mt-2 space-y-1.5 leading-relaxed">
          <li>Toca «Instalar el atajo», pulsa «Agregar atajo» y pega tu clave de CuadraMe. Se instala una sola vez, sirve para todos tus bancos.</li>
          <li>En la app Atajos ve a Automatización, toca + y elige «Cuando recibo una notificación».</li>
          <li>Elige la app del banco y marca «Ejecutar inmediatamente».</li>
          <li>Elige «Ejecutar atajo» y escoge CuadraMe Notificaciones. Repite estos pasos con cada banco.</li>
        </ol>
        <p className="mt-2 leading-relaxed">
          Necesitas iOS 27 y activar la automatización en tu iPhone. CuadraMe reconoce solo el banco y el valor; si el aviso
          no dice algo, te lo pregunta una vez y aprende para no volver a preguntar. Todo queda «por confirmar» hasta que lo revises.
        </p>
      </details>
    </Tarjeta>
  )
}

function TarjetaConciliacion({ c, ir }) {
  const cuentas = c.cuentas || []
  return (
    <Tarjeta icono={FileCheck2} titulo="Cuadre con el banco" semaforo={c.semaforo} mensaje={c.mensaje} testid="tarjeta-conciliacion">
      <div className="flex flex-col gap-2 mt-3">
        {cuentas.length === 0 && <p className="text-xs text-ink-soft">Crea una cuenta para poder cruzar extractos.</p>}
        {cuentas.map((f) => (
          <div key={f.cuenta_id} className="rounded-xl bg-paper p-3" data-testid="fila-conciliacion">
            <p className="text-sm font-semibold truncate">{f.icono} {f.cuenta}</p>
            {f.extracto ? (
              <>
                <p className="text-xs text-ink-soft mt-1">
                  <b>{f.cruzados}</b> ya coinciden con tu extracto · <b>{f.faltantes}</b> faltan por registrar · <b>{f.sin_extracto}</b> sin extracto
                </p>
                <p className="text-[11px] text-ink-soft">Último cruce {haceCuanto(f.ultimo_cruce)}</p>
                <Boton
                  onClick={() => ir('subir', { historialId: f.historial_id })}
                  className="w-full mt-2 border border-line"
                >
                  Revisar ahora
                </Boton>
              </>
            ) : (
              <>
                <p className="text-xs text-ink-soft mt-1">Aún sin extracto procesado.</p>
                <Boton onClick={() => ir('subir')} className="w-full mt-2 border border-line">
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
      setError(textoError(err, 'activar'))
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

// Estado de las conexiones (Gmail, Atajo, conciliación, notificaciones). Vive como hoja dentro del
// centro "Traer movimientos"; `alIr(bloque, state)` abre el bloque que corresponde.
export default function Conexiones({ embebido = false, alIr }) {
  const navigate = useNavigate()
  const ir = (bloque, state) => (alIr ? alIr(bloque, state) : navigate('/sincronizacion', { state: { abrir: bloque, ...state } }))
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
      .catch((err) => setError(textoError(err, 'cargar el estado')))
  }
  useEffect(() => {
    recargar()
  }, [])

  return (
    <div className={embebido ? '' : 'flex-1 overflow-y-auto pb-6 screen-enter'}>
      {!embebido && (
        <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
          <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-xl font-bold">Conexiones y estado</h1>
        </header>
      )}
      <p className="px-6 text-xs text-ink-soft">
        ¿Todo lo que registra tus movimientos solo está funcionando?
      </p>
      {error && (
        <p role="alert" className="mx-6 mt-3 text-xs text-danger">
          {error}{' '}
          <button className="underline font-semibold" onClick={recargar}>Reintentar</button>
        </p>
      )}
      {!estado && !error && <EsqueletoLista filas={4} className="mx-6 mt-6" etiqueta="Cargando el estado de tus conexiones" />}
      {estado && (
        <>
          <TarjetaGmail g={estado.gmail} ir={ir} recargar={recargar} />
          <TarjetaAtajo a={estado.atajo} recargar={recargar} />
          <TarjetaAvisosBanco />
          {ATAJO_REGISTRAR_URL && <TarjetaGestoRegistro url={ATAJO_REGISTRAR_URL} />}
          <TarjetaConciliacion c={estado.conciliacion} ir={ir} />
          <TarjetaPush p={estado.push} />
        </>
      )}
    </div>
  )
}
