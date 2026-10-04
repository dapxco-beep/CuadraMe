import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'
import ModalConsentimiento from '../components/ModalConsentimiento'
import { ArrowLeft, Check, ChevronDown, FileText, KeyRound, Mail, RefreshCw, ShieldCheck, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import { useDialogos } from '../lib/DialogosContext'

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
    try {
      const r = await api.sincronizarCorreos()
      if (!r.ok) {
        if (!silencioso) setError(r.error || 'No se pudo sincronizar')
      } else {
        marcarSincronizado()
        await cargar()
        if (!silencioso) {
          setAviso(
            r.nuevos || r.extractos_nuevos
              ? `Encontramos ${r.nuevos} movimiento(s) por revisar y ${r.extractos_nuevos} extracto(s).`
              : 'No hay nada nuevo en tu correo.'
          )
        }
      }
    } catch (err) {
      if (!silencioso) setError(err.message || 'Error al sincronizar')
    } finally {
      setSincronizando(false)
    }
  }

  async function aprobar(correo) {
    if (procesando.has(correo.id)) return
    const cuentaId = cuentaPorCorreo[correo.id] || cuentas[0]?.id
    if (!cuentaId) return
    setProcesando((prev) => new Set(prev).add(correo.id))
    try {
      await api.aprobarCorreo(correo.id, cuentaId)
      setPendientes((prev) => prev.filter((c) => c.id !== correo.id))
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

  function cuentaElegida(ex) {
    return cuentaPorExtracto[ex.id] || ex.cuenta_sugerida_id || cuentas[0]?.id
  }

  async function conciliar(ex) {
    if (procesando.has(ex.id)) return
    const cuentaId = cuentaElegida(ex)
    if (!cuentaId) return
    setProcesando((prev) => new Set(prev).add(ex.id))
    setError('')
    try {
      const r = await api.conciliarExtractoCorreo(ex.id, cuentaId)
      if (!r.ok) {
        setError(r.error || 'No se pudo conciliar el extracto')
        await cargar()
      } else {
        navigate('/conciliacion', { state: { historialId: r.historial_id } })
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

  if (cargando) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-ink-soft">Cargando...</p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pt-14 pb-2 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="w-9 h-9 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Correos bancarios</h1>
      </header>

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
        {error && <p className="text-xs text-danger mt-2">{error}</p>}
        {aviso && !error && <p className="text-xs text-ink-soft mt-2">{aviso}</p>}
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
                      <p className="text-sm font-semibold truncate">{ex.banco || 'Extracto'}</p>
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
                        disabled={procesando.has(ex.id) || ex.estado === 'falta_clave' || ex.estado === 'error'}
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
        </section>
      )}

      {estado?.conectado && (
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
                  <p className="text-xs text-ink-soft mt-1">{c.categoria_sugerida}</p>

                  {cuentas.length > 1 && (
                    <select
                      value={cuentaPorCorreo[c.id] || cuentas[0]?.id}
                      onChange={(e) => setCuentaPorCorreo((prev) => ({ ...prev, [c.id]: e.target.value }))}
                      className="w-full mt-3 rounded-xl border border-line bg-paper px-3 py-2 text-xs"
                    >
                      {cuentas.map((cu) => (
                        <option key={cu.id} value={cu.id}>{cu.nombre}</option>
                      ))}
                    </select>
                  )}

                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => aprobar(c)}
                      disabled={procesando.has(c.id)}
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
