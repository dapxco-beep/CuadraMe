import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { useAuth } from '../lib/AuthContext'
import ModalConsentimiento from '../components/ModalConsentimiento'
import CrearCuentaBanco from '../components/CrearCuentaBanco'
import { ArrowLeft, Check, ChevronDown, FileText, KeyRound, Mail, RefreshCw, ShieldCheck, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { resumenSync, sincronizarTodo } from '../lib/sincronizarGmail'
import { conciliarExtracto } from '../lib/sincronizacion'
import { useCuentas } from '../lib/CuentasContext'
import { useDialogos } from '../lib/DialogosContext'
import BarraProgreso from '../components/BarraProgreso'

const ESTADOS = {
  nuevo: { texto: 'Nuevo', clase: 'bg-accent-soft text-accent' },
  procesado: { texto: 'Procesado', clase: 'bg-line text-ink-soft' },
  falta_clave: { texto: 'Falta clave', clase: 'bg-danger/10 text-danger' },
  error: { texto: 'No se pudo leer', clase: 'bg-danger/10 text-danger' },
}

function EtiquetaEstado({ estado }) {
  const e = ESTADOS[estado] || ESTADOS.nuevo
  return <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 shrink-0 ${e.clase}`}>{e.texto}</span>
}

const POR_PAGINA = 30
const POR_PAGINA_EXT = 50 // el backend devuelve 50 extractos por página
const FILTROS = [
  { id: 'todo', texto: 'Todo' },
  { id: 'nuevos', texto: 'Nuevos' },
  { id: 'extractos', texto: 'Extractos' },
  { id: 'falta_clave', texto: 'Falta clave' },
  { id: 'ignorados', texto: 'Ignorados' },
]

function Pasos({ paso }) {
  const items = ['Conecta Gmail', 'Sincroniza', 'Revisa']
  return (
    <ol className="flex items-center gap-2 mx-6 mt-3 text-xs" aria-label="Pasos" data-testid="pasos">
      {items.map((t, i) => {
        const n = i + 1
        const hecho = n < paso
        const actual = n === paso
        return (
          <li key={t} className="flex items-center gap-1.5 min-w-0" aria-current={actual ? 'step' : undefined}>
            <span
              className={`w-5 h-5 rounded-full text-[11px] font-bold flex items-center justify-center shrink-0 ${
                hecho ? 'bg-cuadra text-white' : actual ? 'bg-accent text-white' : 'bg-line text-ink-soft'
              }`}
            >
              {hecho ? <Check size={11} /> : n}
            </span>
            <span className={`truncate ${actual ? 'font-semibold' : 'text-ink-soft'}`}>{t}</span>
            {n < items.length && <span className="text-ink-soft" aria-hidden="true">·</span>}
          </li>
        )
      })}
    </ol>
  )
}

const CLAVE_SYNC = 'cuadrame_gmail_sync'
const SEIS_HORAS = 6 * 60 * 60 * 1000

function tocaSincronizar() {
  try {
    return Date.now() - Number(localStorage.getItem(CLAVE_SYNC) || 0) > SEIS_HORAS
  } catch {
    return false
  }
}

function marcarSincronizado() {
  try {
    localStorage.setItem(CLAVE_SYNC, String(Date.now()))
  } catch {
    /* sin almacenamiento: se sincroniza solo a mano */
  }
}

export default function Correos() {
  const navigate = useNavigate()
  const volver = useVolver('/')
  const { cuentas } = useCuentas()
  const { confirmar } = useDialogos()
  const [estado, setEstado] = useState(null)
  const [pendientes, setPendientes] = useState([])
  const [cargando, setCargando] = useState(true)
  const [sincronizando, setSincronizando] = useState(false)
  const [error, setError] = useState('')
  const [mostrarGuia, setMostrarGuia] = useState(false)
  const [cuentaPorCorreo, setCuentaPorCorreo] = useState({})
  const [procesando, setProcesando] = useState(new Set())
  const [extractos, setExtractos] = useState([])
  const [cuentaPorExtracto, setCuentaPorExtracto] = useState({})
  const [claveConfigurada, setClaveConfigurada] = useState(false)
  const [claveInput, setClaveInput] = useState('')
  const [mostrarAjustes, setMostrarAjustes] = useState(false)
  const [aviso, setAviso] = useState('')
  const [pedirConsentimiento, setPedirConsentimiento] = useState(false)
  const [crearCuenta, setCrearCuenta] = useState(null) // { banco, correoId }
  const [progreso, setProgreso] = useState(null)
  const [filtro, setFiltro] = useState('todo')
  const [ignorados, setIgnorados] = useState([])
  const [hayMasIgn, setHayMasIgn] = useState(false)
  const [hayMasExt, setHayMasExt] = useState(false)
  const [params] = useSearchParams()
  const usuario = useAuth()?.usuario
  // Google devuelve a la app con ?gmail=sin_acceso cuando el correo no está autorizado (modo Pruebas).
  const sinAcceso = params.get('gmail') === 'sin_acceso'
  const [copiado, setCopiado] = useState(false)

  async function copiarCorreo() {
    try {
      await navigator.clipboard.writeText(usuario?.email || '')
      setCopiado(true)
    } catch {
      /* sin portapapeles: queda el botón de correo */
    }
  }

  useEffect(() => {
    cargar().then((e) => {
      // Sincronización automática al abrir la pantalla (como máximo cada 6 horas):
      // reutiliza el mismo endpoint del botón, no hay cron nuevo.
      if (e?.conectado && tocaSincronizar()) sincronizar(true)
    })
  }, [])

  async function cargar() {
    setCargando(true)
    try {
      const [e, p] = await Promise.all([api.gmailEstado(), api.correosPendientes()])
      setEstado(e)
      setPendientes(p)
      if (e?.conectado) {
        const [ex, clave] = await Promise.all([
          api.extractosCorreo().catch(() => []),
          api.clavePdfEstado().catch(() => ({})),
        ])
        setExtractos(Array.isArray(ex) ? ex : [])
        setHayMasExt(Array.isArray(ex) && ex.length >= POR_PAGINA_EXT)
        setClaveConfigurada(Boolean(clave?.configurada))
      }
      return e
    } catch (err) {
      setError(err.message)
    } finally {
      setCargando(false)
    }
  }

  async function conectarGmail() {
    setError('')
    // Ley 1581: sin la autorización específica de lectura de correo no se conecta.
    if (estado?.consentimiento === false) {
      setPedirConsentimiento(true)
      return
    }
    try {
      const { url } = await api.gmailConectar()
      window.location.href = url
    } catch (err) {
      setError(err.message || 'No se pudo iniciar la conexión con Gmail')
    }
  }

  async function desconectarGmail() {
    const ok = await confirmar('Se dejarán de sincronizar tus correos bancarios.', {
      titulo: '¿Desconectar Gmail?',
      confirmarTexto: 'Desconectar',
      peligro: true,
    })
    if (!ok) return
    await api.gmailDesconectar()
    cargar()
  }

  async function sincronizar(silencioso = false) {
    setSincronizando(true)
    setError('')
    setAviso('')
    setProgreso({ leidos: 0, total_estimado: 0 })
    try {
      // Por lotes: repite la llamada hasta terminar, mostrando "Leí X de Y".
      const r = await sincronizarTodo({
        onProgreso: (p) => setProgreso({ leidos: p.leidos, total_estimado: p.total_estimado }),
      })
      if (!r?.ok) {
        if (!silencioso) setError(r?.error || 'No se pudo sincronizar')
      } else {
        marcarSincronizado()
        await cargar()
        if (!silencioso) setAviso(resumenSync(r))
      }
    } catch (err) {
      if (!silencioso) setError(err.message || 'Error al sincronizar')
    } finally {
      setSincronizando(false)
      setProgreso(null)
    }
  }

  const MOSTRAR_EXTRACTOS = ['todo', 'extractos', 'falta_clave']

  async function cambiarFiltro(f) {
    setFiltro(f)
    try {
      if (f === 'ignorados') {
        const lista = await api.correosLista('ignorados', 0, POR_PAGINA)
        setIgnorados(lista)
        setHayMasIgn(lista.length >= POR_PAGINA)
      } else if (MOSTRAR_EXTRACTOS.includes(f)) {
        const ex = await api.extractosCorreo(f === 'falta_clave' ? 'falta_clave' : undefined)
        setExtractos(Array.isArray(ex) ? ex : [])
        setHayMasExt((ex || []).length >= POR_PAGINA_EXT)
      }
    } catch (err) {
      setError(err.message || 'No se pudo cargar la lista')
    }
  }

  async function cargarMasIgnorados() {
    const mas = await api.correosLista('ignorados', ignorados.length, POR_PAGINA)
    setIgnorados((prev) => [...prev, ...mas])
    setHayMasIgn(mas.length >= POR_PAGINA)
  }

  async function cargarMasExtractos() {
    const mas = await api.extractosCorreo(filtro === 'falta_clave' ? 'falta_clave' : undefined, extractos.length)
    setExtractos((prev) => [...prev, ...mas])
    setHayMasExt(mas.length >= POR_PAGINA_EXT)
  }

  async function aprobar(correo) {
    if (procesando.has(correo.id)) return
    // Nunca se asume una cuenta (antes caía en la primera): sale de quién envió el
    // correo o de lo que elija el usuario.
    const cuentaId = cuentaElegidaCorreo(correo)
    if (!cuentaId) return
    setProcesando((prev) => new Set(prev).add(correo.id))
    setError('')
    try {
      await api.aprobarCorreo(correo.id, cuentaId)
      setPendientes((prev) => prev.filter((c) => c.id !== correo.id))
    } catch (err) {
      setError(err.message || 'No se pudo aprobar el movimiento')
    } finally {
      setProcesando((prev) => {
        const next = new Set(prev)
        next.delete(correo.id)
        return next
      })
    }
  }

  async function descartar(correo) {
    if (procesando.has(correo.id)) return
    setProcesando((prev) => new Set(prev).add(correo.id))
    try {
      await api.descartarCorreo(correo.id)
      setPendientes((prev) => prev.filter((c) => c.id !== correo.id))
    } finally {
      setProcesando((prev) => {
        const next = new Set(prev)
        next.delete(correo.id)
        return next
      })
    }
  }

  // Solo vale una cuenta que exista: la elegida a mano o la que el servidor dedujo del banco.
  const existe = (id) => (id && cuentas.some((c) => c.id === id) ? id : '')
  function cuentaElegidaCorreo(c) {
    return existe(cuentaPorCorreo[c.id]) || existe(c.cuenta_sugerida_id)
  }

  function cuentaElegida(ex) {
    return existe(cuentaPorExtracto[ex.id]) || existe(ex.cuenta_sugerida_id)
  }

  async function conciliar(ex) {
    if (procesando.has(ex.id)) return
    const cuentaId = cuentaElegida(ex)
    if (!cuentaId) return
    setProcesando((prev) => new Set(prev).add(ex.id))
    setError('')
    try {
      const r = await conciliarExtracto(ex, cuentaId)
      if (!r.ok) {
        setError(r.error)
        await cargar()
      } else {
        navigate('/conciliacion', { state: { historialId: r.historialId } })
      }
    } catch (err) {
      setError(err.message || 'No se pudo conciliar el extracto')
    } finally {
      setProcesando((prev) => {
        const next = new Set(prev)
        next.delete(ex.id)
        return next
      })
    }
  }

  async function descartarExtracto(ex) {
    await api.descartarExtractoCorreo(ex.id)
    setExtractos((prev) => prev.filter((x) => x.id !== ex.id))
  }

  async function guardarClave() {
    if (!claveInput.trim()) return
    setError('')
    try {
      await api.guardarClavePdf(claveInput.trim())
      setClaveInput('')
      setClaveConfigurada(true)
      setAviso('Clave guardada. Sincroniza para abrir los extractos que estaban pendientes.')
    } catch (err) {
      setError(err.message || 'No se pudo guardar la clave')
    }
  }

  async function borrarClave() {
    await api.borrarClavePdf()
    setClaveConfigurada(false)
  }

  let yaSincronizo = pendientes.length > 0 || extractos.length > 0
  try {
    yaSincronizo = yaSincronizo || Number(localStorage.getItem(CLAVE_SYNC) || 0) > 0
  } catch {
    /* sin almacenamiento */
  }
  const verExtractos = MOSTRAR_EXTRACTOS.includes(filtro)
  const verNuevos = filtro === 'todo' || filtro === 'nuevos'

  if (cargando) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-ink-soft">Cargando...</p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold flex-1">Correos bancarios</h1>
        <button onClick={() => navigate('/sincronizacion')} className="text-xs font-semibold text-accent">
          Qué falta
        </button>
        <button onClick={() => navigate('/conexiones')} className="text-xs font-semibold text-accent">
          Ver estado
        </button>
      </header>

      <Pasos paso={!estado?.conectado ? 1 : yaSincronizo ? 3 : 2} />

      {!estado?.conectado && (sinAcceso || estado?.modo_pruebas) && (
        <section role="status" className="mx-6 mt-4 rounded-2xl bg-accent-soft border border-accent/30 p-4" data-testid="aviso-invitacion">
          <p className="text-sm font-semibold">Gmail aún está en acceso por invitación</p>
          <p className="text-xs text-ink-soft mt-1 leading-relaxed">
            {sinAcceso
              ? 'Google no te dejó entrar porque tu correo todavía no está en la lista. '
              : 'Estamos esperando la verificación de Google, así que por ahora solo entran correos que agregamos a mano. '}
            Pídenos que agreguemos tu correo{usuario?.email ? ` (${usuario.email})` : ''} y te avisamos cuando esté listo.
          </p>
          <div className="flex gap-2 mt-3">
            <a
              href={`mailto:${estado?.soporte_email || 'dapxco@gmail.com'}?subject=${encodeURIComponent('Quiero conectar Gmail en CuadraMe')}&body=${encodeURIComponent(`Hola, por favor agreguen mi correo de Gmail para probar CuadraMe: ${usuario?.email || ''}`)}`}
              className="flex-1 text-center bg-ink text-paper font-semibold rounded-xl py-2.5 text-sm"
            >
              Pedir acceso
            </a>
            <button onClick={copiarCorreo} className="px-4 rounded-xl border border-line bg-paper text-sm font-medium">
              {copiado ? 'Copiado' : 'Copiar mi correo'}
            </button>
          </div>
        </section>
      )}

      {crearCuenta && (
        <CrearCuentaBanco
          banco={crearCuenta.banco}
          onClose={() => setCrearCuenta(null)}
          onCreada={(cuenta) => {
            // La cuenta nueva queda elegida para ese correo y para los demás del mismo banco.
            setCuentaPorCorreo((prev) => {
              const sig = { ...prev }
              for (const p of pendientes) if (p.banco_detectado === crearCuenta.banco && p.falta_cuenta) sig[p.id] = cuenta?.id
              return sig
            })
            setCrearCuenta(null)
            cargar()
          }}
        />
      )}

      {pedirConsentimiento && (
        <ModalConsentimiento
          finalidad="lectura_correo"
          origen="flujo_gmail"
          onCancelar={() => setPedirConsentimiento(false)}
          onAceptado={() => {
            setPedirConsentimiento(false)
            setEstado((e) => ({ ...e, consentimiento: true }))
            conectarGmail()
          }}
        />
      )}

      <section className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-4">
        {estado?.conectado ? (
          <>
            <div className="flex items-center gap-3">
              <Mail size={18} className="text-accent shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold truncate">{estado.email}</p>
                <p className="text-xs text-ink-soft">Etiqueta opcional: {estado.etiqueta}</p>
              </div>
            </div>
            <div className="flex gap-2 mt-3">
              <button
                onClick={() => sincronizar()}
                disabled={sincronizando}
                className="flex-1 flex items-center justify-center gap-1.5 bg-ink text-paper font-semibold rounded-xl py-2.5 text-sm disabled:opacity-60"
              >
                <RefreshCw size={14} className={sincronizando ? 'animate-spin' : ''} />
                {sincronizando ? 'Sincronizando...' : 'Sincronizar ahora'}
              </button>
              <button
                onClick={desconectarGmail}
                className="px-4 rounded-xl border border-line text-sm text-ink-soft"
              >
                Desconectar
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="text-sm font-semibold mb-1">Conecta tu Gmail</p>
            <p className="text-xs text-ink-soft mb-3">
              CuadraMe busca solo los correos de tus bancos y billeteras (notificaciones y
              extractos en PDF), sin que tengas que etiquetar nada. Te sugiere movimientos y
              extractos para conciliar — nunca crea nada automáticamente, tú apruebas cada uno.
            </p>
            <button
              onClick={conectarGmail}
              className="w-full bg-ink text-paper font-semibold rounded-xl py-3 text-sm"
            >
              Conectar Gmail
            </button>
          </>
        )}
        {progreso && (
          <div className="mt-3" role="status">
            <BarraProgreso
              pct={progreso.total_estimado ? Math.min(100, Math.round((progreso.leidos / progreso.total_estimado) * 100)) : 0}
              label="Lectura de correos"
              className="h-2 rounded-full bg-line overflow-hidden"
              fillClass=""
            />
            <p className="text-xs text-ink-soft mt-1.5">
              {progreso.total_estimado ? `Leí ${progreso.leidos} de ${progreso.total_estimado}` : 'Empezando...'}
            </p>
          </div>
        )}
        {error && <p className="text-xs text-danger mt-2">{error}</p>}
        {aviso && !error && <p className="text-sm font-semibold mt-2" role="status">{aviso}</p>}
        <p className="flex items-start gap-1.5 text-[11px] text-ink-soft mt-3">
          <ShieldCheck size={13} className="shrink-0 mt-0.5 text-accent" />
          <span>
            Privacidad: CuadraMe solo tiene permiso de <b>lectura</b> en Gmail; no puede enviar,
            borrar ni modificar correos. No guardamos tus correos ni los PDF: solo el banco, el
            periodo y el estado de cada extracto, y los datos de los movimientos que tú apruebas.
            Puedes desconectar Gmail cuando quieras.
          </span>
        </p>
      </section>

      <section className="mx-6 mt-3">
        <button
          onClick={() => setMostrarGuia((v) => !v)}
          className="w-full flex items-center justify-between text-xs text-ink-soft py-2"
        >
          <span>(Opcional) Etiqueta 'gastos' para correos que no detectamos solos</span>
          <ChevronDown size={14} className={`shrink-0 transition-transform ${mostrarGuia ? 'rotate-180' : ''}`} />
        </button>
        {mostrarGuia && (
          <ol className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
            {[
              'Abre Gmail y busca un correo de tu banco (ej. de Bancolombia o Nequi).',
              'Ábrelo y toca el ícono de etiqueta (🏷️) arriba, o los tres puntos "Más".',
              'Elige "Crear nueva" y escribe exactamente: gastos',
              'Listo — a partir de ahora, cada vez que quieras que CuadraMe lea un correo, solo etiquétalo igual.',
            ].map((paso, i) => (
              <li key={i} className="flex items-start gap-3 px-4 py-3">
                <span className="w-5 h-5 rounded-full bg-accent-soft text-accent text-[11px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <p className="text-xs">{paso}</p>
              </li>
            ))}
          </ol>
        )}
      </section>

      {estado?.conectado && (
        <div className="mx-6 mt-5 flex gap-2 overflow-x-auto" role="group" aria-label="Filtrar correos">
          {FILTROS.map((f) => (
            <button
              key={f.id}
              onClick={() => cambiarFiltro(f.id)}
              aria-pressed={filtro === f.id}
              className={`shrink-0 rounded-full px-3.5 py-1.5 text-xs font-semibold border ${
                filtro === f.id ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
              }`}
            >
              {f.texto}
            </button>
          ))}
        </div>
      )}

      {estado?.conectado && filtro === 'ignorados' && (
        <section className="mx-6 mt-6" aria-label="Correos ignorados">
          <h2 className="text-[15px] font-semibold mb-1">Ignorados ({ignorados.length}{hayMasIgn ? '+' : ''})</h2>
          <p className="text-xs text-ink-soft mb-3">
            Correos de tus bancos que no parecían una transacción (publicidad, avisos). No los volvemos a leer.
          </p>
          {ignorados.length === 0 ? (
            <div className="rounded-2xl bg-paper-raised border border-line p-6 text-center">
              <p className="text-sm text-ink-soft">No hay correos ignorados</p>
            </div>
          ) : (
            <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
              {ignorados.map((c) => (
                <div key={c.id} className="px-4 py-3">
                  <p className="text-sm font-medium truncate">{c.asunto || c.comercio}</p>
                  <p className="text-xs text-ink-soft truncate">{c.remitente}</p>
                </div>
              ))}
            </div>
          )}
          {hayMasIgn && (
            <button onClick={cargarMasIgnorados} className="w-full mt-3 border border-line rounded-xl py-2.5 text-sm font-semibold">
              Cargar más
            </button>
          )}
        </section>
      )}

      {estado?.conectado && verExtractos && (
        <section className="mx-6 mt-6" aria-label="Extractos encontrados">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[15px] font-semibold">
              Extractos encontrados {extractos.length > 0 && `(${extractos.length})`}
            </h2>
            <button
              onClick={() => setMostrarAjustes((v) => !v)}
              className="flex items-center gap-1 text-xs text-ink-soft"
              aria-expanded={mostrarAjustes}
            >
              <KeyRound size={13} /> Clave del PDF
            </button>
          </div>

          {mostrarAjustes && (
            <div className="rounded-2xl bg-paper-raised border border-line p-4 mb-3">
              <p className="text-xs text-ink-soft mb-2">
                Muchos bancos cifran el extracto con tu cédula. Guárdala aquí y CuadraMe abrirá
                esos PDF sola. Se guarda cifrada en el servidor y nunca se muestra de nuevo. Si
                usas más de una, sepáralas con coma.
              </p>
              <p className="text-xs font-medium mb-2">
                {claveConfigurada ? 'Hay una clave guardada.' : 'Aún no hay clave guardada.'}
              </p>
              <div className="flex gap-2">
                <input
                  type="password"
                  autoComplete="off"
                  value={claveInput}
                  onChange={(e) => setClaveInput(e.target.value)}
                  placeholder={claveConfigurada ? 'Nueva clave' : 'Clave (ej. tu cédula)'}
                  aria-label="Clave del PDF"
                  className="flex-1 rounded-xl border border-line bg-paper px-3 py-2 text-sm outline-none focus:border-accent"
                />
                <button
                  onClick={guardarClave}
                  disabled={!claveInput.trim()}
                  className="px-4 rounded-xl bg-ink text-paper text-sm font-semibold disabled:opacity-50"
                >
                  Guardar
                </button>
              </div>
              {claveConfigurada && (
                <button onClick={borrarClave} className="text-xs text-danger mt-2">
                  Borrar la clave guardada
                </button>
              )}
            </div>
          )}

          {extractos.length === 0 ? (
            <div className="rounded-2xl bg-paper-raised border border-line p-6 text-center">
              <p className="text-sm text-ink-soft">Aún no encontramos extractos en tu correo</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {extractos.map((ex) => (
                <div key={ex.id} className="rounded-2xl bg-paper-raised border border-line p-4">
                  <div className="flex items-start gap-3">
                    <FileText size={18} className="text-accent shrink-0 mt-0.5" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold truncate">{ex.banco || 'Banco sin identificar'}</p>
                      <p className="text-xs text-ink-soft truncate">{ex.periodo || ex.asunto}</p>
                    </div>
                    <EtiquetaEstado estado={ex.estado} />
                  </div>

                  {ex.estado === 'falta_clave' && (
                    <p className="text-xs text-ink-soft mt-2">
                      Pendiente: falta la clave del PDF. Guárdala en "Clave del PDF" y sincroniza.
                    </p>
                  )}

                  {ex.estado !== 'falta_clave' && ex.estado !== 'error' && cuentas.length > 0 && (
                    <select
                      value={cuentaElegida(ex)}
                      onChange={(e) => setCuentaPorExtracto((prev) => ({ ...prev, [ex.id]: e.target.value }))}
                      aria-label="Cuenta del extracto"
                      className="w-full mt-3 rounded-xl border border-line bg-paper px-3 py-2 text-xs"
                    >
                      <option value="">Elige la cuenta</option>
                      {cuentas.map((cu) => (
                        <option key={cu.id} value={cu.id}>
                          {cu.nombre}
                          {cu.id === ex.cuenta_sugerida_id ? ' (sugerida)' : ''}
                        </option>
                      ))}
                    </select>
                  )}

                  <div className="flex gap-2 mt-3">
                    {ex.estado === 'procesado' && ex.historial_id ? (
                      <button
                        onClick={() => navigate('/conciliacion', { state: { historialId: ex.historial_id } })}
                        className="flex-1 border border-line rounded-xl py-2.5 text-sm font-semibold"
                      >
                        Ver conciliación
                      </button>
                    ) : (
                      <button
                        onClick={() => conciliar(ex)}
                        disabled={procesando.has(ex.id) || ex.estado === 'falta_clave' || ex.estado === 'error' || !cuentaElegida(ex)}
                        className="flex-1 bg-accent text-white font-semibold rounded-xl py-2.5 text-sm disabled:opacity-50"
                      >
                        {procesando.has(ex.id) ? 'Conciliando...' : 'Conciliar'}
                      </button>
                    )}
                    <button
                      onClick={() => descartarExtracto(ex)}
                      className="px-4 rounded-xl border border-line text-sm text-ink-soft flex items-center gap-1.5"
                      aria-label="Descartar extracto"
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {hayMasExt && (
            <button onClick={cargarMasExtractos} className="w-full mt-3 border border-line rounded-xl py-2.5 text-sm font-semibold">
              Cargar más extractos
            </button>
          )}
        </section>
      )}

      {estado?.conectado && verNuevos && (
        <section className="mx-6 mt-6">
          <h2 className="text-[15px] font-semibold mb-3">
            Pendientes de revisar {pendientes.length > 0 && `(${pendientes.length})`}
          </h2>
          {pendientes.length === 0 ? (
            <div className="rounded-2xl bg-paper-raised border border-line p-6 text-center">
              <p className="text-sm text-ink-soft">No hay correos pendientes</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {pendientes.map((c) => (
                <div key={c.id} className="rounded-2xl bg-paper-raised border border-line p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold truncate">{c.comercio}</p>
                      <p className="text-xs text-ink-soft truncate">{c.asunto}</p>
                    </div>
                    <p className={`text-sm font-bold shrink-0 ${c.tipo_sugerido === 'income' ? 'text-accent' : 'text-ink'}`}>
                      {c.tipo_sugerido === 'income' ? '+' : '-'}
                      {formatCOP(c.monto)}
                    </p>
                  </div>
                  <p className="text-xs text-ink-soft mt-1">
                    {c.categoria_sugerida}
                    {c.banco_detectado ? ` · ${c.banco_detectado}` : ''}
                  </p>

                  <select
                    value={cuentaElegidaCorreo(c)}
                    onChange={(e) => setCuentaPorCorreo((prev) => ({ ...prev, [c.id]: e.target.value }))}
                    aria-label={`Cuenta de ${c.comercio}`}
                    className="w-full mt-3 rounded-xl border border-line bg-paper px-3 py-2 text-xs"
                  >
                    <option value="">
                      {c.falta_cuenta ? `No tienes cuenta ${c.banco_detectado}` : 'Elige la cuenta'}
                    </option>
                    {cuentas.map((cu) => (
                      <option key={cu.id} value={cu.id}>{cu.nombre}</option>
                    ))}
                  </select>
                  {c.falta_cuenta && (
                    <button
                      onClick={() => setCrearCuenta({ banco: c.banco_detectado, correoId: c.id })}
                      className="mt-2 text-xs font-semibold text-accent"
                    >
                      Crear cuenta {c.banco_detectado}
                    </button>
                  )}

                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => aprobar(c)}
                      disabled={procesando.has(c.id) || !cuentaElegidaCorreo(c)}
                      className="flex-1 flex items-center justify-center gap-1.5 bg-accent text-white font-semibold rounded-xl py-2.5 text-sm disabled:opacity-50"
                    >
                      <Check size={14} /> Aprobar
                    </button>
                    <button
                      onClick={() => descartar(c)}
                      disabled={procesando.has(c.id)}
                      className="px-4 rounded-xl border border-line text-sm text-ink-soft flex items-center gap-1.5 disabled:opacity-50"
                    >
                      <X size={14} /> Descartar
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}
