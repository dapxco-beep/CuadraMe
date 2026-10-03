import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Check, ChevronDown, Mail, RefreshCw, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import { useDialogos } from '../lib/DialogosContext'

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

  useEffect(() => {
    cargar()
  }, [])

  async function cargar() {
    setCargando(true)
    try {
      const [e, p] = await Promise.all([api.gmailEstado(), api.correosPendientes()])
      setEstado(e)
      setPendientes(p)
    } catch (err) {
      setError(err.message)
    } finally {
      setCargando(false)
    }
  }

  async function conectarGmail() {
    setError('')
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

  async function sincronizar() {
    setSincronizando(true)
    setError('')
    try {
      const r = await api.sincronizarCorreos()
      if (!r.ok) {
        setError(r.error || 'No se pudo sincronizar')
      } else {
        await cargar()
      }
    } catch (err) {
      setError(err.message || 'Error al sincronizar')
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

      <section className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-4">
        {estado?.conectado ? (
          <>
            <div className="flex items-center gap-3">
              <Mail size={18} className="text-accent shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold truncate">{estado.email}</p>
                <p className="text-xs text-ink-soft">Etiqueta: {estado.etiqueta}</p>
              </div>
            </div>
            <div className="flex gap-2 mt-3">
              <button
                onClick={sincronizar}
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
              Etiqueta en Gmail los correos de notificaciones bancarias con la etiqueta{' '}
              <b>"gastos"</b>, y CuadraMe los leerá para sugerirte movimientos — nunca los crea
              automáticamente, tú apruebas cada uno.
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
      </section>

      <section className="mx-6 mt-3">
        <button
          onClick={() => setMostrarGuia((v) => !v)}
          className="w-full flex items-center justify-between text-xs text-ink-soft py-2"
        >
          <span>¿No sabes crear una etiqueta en Gmail? Aquí te explicamos</span>
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
