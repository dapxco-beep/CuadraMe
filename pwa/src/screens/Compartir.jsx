import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Check, Eye, EyeOff, Mail, Pencil, UserMinus, UserPlus, Users, X } from 'lucide-react'
import { EstadoVacio } from '../brand/Marca'
import Icono from '../components/Icono'
import { Boton, CampoTexto } from '../components/ui'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'
import { useDialogos } from '../lib/DialogosContext'
import { useVolver } from '../lib/useVolver'

// «Compartir con mi pareja o familia»: tres pasos en una sola pantalla.
//   1. qué cuentas  ·  2. a quién (correo)  ·  3. qué puede hacer.
// Solo cambia la experiencia: las reglas de permisos son las del servidor (rol «viewer» = solo ver,
// «editor» = ver y anotar; el editor nunca administra la cuenta ni invita a otras personas).

export const ROLES = [
  {
    id: 'viewer',
    titulo: 'Solo ver',
    icono: Eye,
    ve: 'Verá los saldos y los movimientos de las cuentas que elijas.',
    noVe: 'No podrá anotar ni cambiar nada, y no ve tus otras cuentas, metas ni presupuestos.',
  },
  {
    id: 'editor',
    titulo: 'Ver y anotar',
    icono: Pencil,
    ve: 'Verá los movimientos y podrá anotar y corregir gastos en esas cuentas.',
    noVe: 'No puede borrar la cuenta, invitar a otras personas ni ver tus otras cuentas, metas o presupuestos.',
  },
]

const etiquetaRol = (rol) => (rol === 'editor' ? 'Ver y anotar' : 'Solo ver')

function Paso({ numero, titulo, children }) {
  return (
    <section className="mx-6 mt-6" aria-label={`Paso ${numero}: ${titulo}`}>
      <h2 className="text-[15px] font-semibold mb-3 flex items-center gap-2.5">
        <span className="w-6 h-6 rounded-full bg-accent text-paper-raised text-xs font-bold flex items-center justify-center shrink-0" aria-hidden="true">
          {numero}
        </span>
        <span>{titulo}</span>
      </h2>
      {children}
    </section>
  )
}

export default function Compartir() {
  const volver = useVolver('/perfil')
  const { cuentas } = useCuentas()
  const { avisar, confirmar } = useDialogos() || {}
  const [propias, setPropias] = useState(null) // [{ cuenta, compartidas, invitaciones }] solo cuentas de las que eres dueño
  const [pendientesMias, setPendientesMias] = useState([])
  const [elegidas, setElegidas] = useState([])
  const [email, setEmail] = useState('')
  const [rol, setRol] = useState('viewer')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.misInvitacionesPendientes().then(setPendientesMias).catch(() => {})
  }, [])

  // Solo el dueño puede ver quién tiene acceso: las cuentas ajenas responden «no encontrada» y se descartan.
  const cargar = useCallback(async () => {
    const filas = await Promise.all(
      cuentas.map(async (cuenta) => {
        try {
          const [compartidas, invitaciones] = await Promise.all([api.compartidaCon(cuenta.id), api.invitacionesDeCuenta(cuenta.id)])
          return { cuenta, compartidas, invitaciones }
        } catch {
          return null
        }
      })
    )
    setPropias(filas.filter(Boolean))
  }, [cuentas])

  useEffect(() => {
    cargar()
  }, [cargar])

  const rolElegido = ROLES.find((r) => r.id === rol)

  function alternar(id) {
    setElegidas((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  async function invitar(e) {
    e.preventDefault()
    setError('')
    if (elegidas.length === 0) return setError('Elige al menos una cuenta para compartir.')
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError('Escribe el correo completo de la persona. Por ejemplo ana@correo.com.')
    setEnviando(true)
    const resultados = await Promise.allSettled(elegidas.map((id) => api.invitarACuenta(id, email.trim(), rol)))
    setEnviando(false)
    const fallos = resultados.filter((r) => r.status === 'rejected')
    // «Ya existe una invitación pendiente» no es un problema: la persona ya fue invitada a esa cuenta.
    const reales = fallos.filter((r) => !/pendiente/i.test(r.reason?.message || ''))
    if (reales.length === resultados.length) {
      return setError(reales[0].reason?.message || 'No pudimos enviar la invitación. Revisa tu conexión e intenta de nuevo.')
    }
    avisar?.(
      reales.length
        ? `Listo: invitamos a ${email.trim()} a ${resultados.length - reales.length} de ${resultados.length} cuentas. Intenta de nuevo con las demás.`
        : `Listo: le enviamos la invitación a ${email.trim()}. Podrá verla cuando entre a CuadraMe.`,
      'ok'
    )
    setEmail('')
    setElegidas([])
    cargar()
  }

  // Filas del estado: invitaciones esperando respuesta y personas con acceso, por cuenta.
  const filas = useMemo(() => {
    const out = []
    for (const { cuenta, compartidas, invitaciones } of propias || []) {
      const aceptadas = invitaciones.filter((i) => i.estado === 'aceptada')
      const usadas = new Set()
      for (const c of compartidas) {
        // El servidor solo devuelve el id de la persona: se le pone el correo si la invitación aceptada lo identifica sin dudas.
        const candidatas = aceptadas.filter((i) => i.rol === c.rol && !usadas.has(i.id))
        const hermanas = compartidas.filter((x) => x.rol === c.rol).length
        const inv = candidatas.length === 1 && hermanas === 1 ? candidatas[0] : null
        if (inv) usadas.add(inv.id)
        out.push({ clave: `c-${c.id}`, estado: 'activo', cuenta, rol: c.rol, correo: inv?.email_invitado || null, usuarioId: c.usuario_id })
      }
      for (const i of invitaciones.filter((x) => x.estado === 'pendiente')) {
        out.push({ clave: `i-${i.id}`, estado: 'pendiente', cuenta, rol: i.rol, correo: i.email_invitado })
      }
      for (const i of invitaciones.filter((x) => x.estado === 'rechazada')) {
        out.push({ clave: `r-${i.id}`, estado: 'rechazada', cuenta, rol: i.rol, correo: i.email_invitado })
      }
    }
    return out
  }, [propias])

  async function dejarDeCompartir(fila) {
    const quien = fila.correo || 'esta persona'
    const ok = await confirmar?.(`¿Dejar de compartir «${fila.cuenta.nombre}» con ${quien}? Ya no verá esta cuenta. Tus datos no se borran.`, {
      confirmarTexto: 'Sí, dejar de compartir',
    })
    if (confirmar && !ok) return
    try {
      await api.revocarAcceso(fila.cuenta.id, fila.usuarioId)
      avisar?.(`Listo: dejaste de compartir «${fila.cuenta.nombre}».`, 'ok')
      cargar()
    } catch (err) {
      avisar?.(err.message || 'No pudimos quitar el acceso. Revisa tu conexión e intenta de nuevo.')
    }
  }

  async function responderInvitacion(id, aceptar) {
    try {
      await (aceptar ? api.aceptarInvitacion(id) : api.rechazarInvitacion(id))
      setPendientesMias((prev) => prev.filter((i) => i.id !== id))
      if (aceptar) avisar?.('Listo: ya puedes ver esa cuenta en CuadraMe.', 'ok')
    } catch (err) {
      avisar?.(err.message || 'No pudimos responder la invitación. Intenta de nuevo.')
    }
  }

  const puedeCompartir = propias === null || propias.length > 0

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      <header className="px-6 pantalla-top pb-1 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Compartir con mi pareja o familia</h1>
      </header>
      <p className="px-6 text-sm text-ink-soft">Lleven las cuentas del hogar juntos. Tú decides qué cuentas y qué puede hacer cada persona.</p>

      <div className="max-w-2xl md:mx-auto">
        {pendientesMias.length > 0 && (
          <section className="mx-6 mt-5" aria-label="Invitaciones que recibiste">
            <h2 className="text-sm font-semibold mb-2">Te invitaron a compartir una cuenta</h2>
            <div className="flex flex-col gap-2">
              {pendientesMias.map((inv) => (
                <div key={inv.id} className="rounded-2xl bg-accent-soft p-3.5 flex items-center gap-3">
                  <Icono icono={Mail} tam="sm" className="text-accent shrink-0" />
                  <p className="flex-1 text-sm">
                    Podrás <b>{inv.rol === 'editor' ? 'ver y anotar' : 'solo ver'}</b> esa cuenta
                  </p>
                  <button
                    onClick={() => responderInvitacion(inv.id, true)}
                    className="w-11 h-11 rounded-full bg-accent text-paper-raised flex items-center justify-center shrink-0"
                    aria-label="Aceptar invitación"
                  >
                    <Check size={16} />
                  </button>
                  <button
                    onClick={() => responderInvitacion(inv.id, false)}
                    className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center shrink-0"
                    aria-label="Rechazar invitación"
                  >
                    <X size={16} />
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}

        {cuentas.length === 0 ? (
          <EstadoVacio
            icono={Users}
            titulo="Aún no tienes cuentas para compartir"
            texto="Primero agrega una cuenta (tu banco, tu billetera o efectivo). Después podrás compartirla."
            className="mx-6 mt-6"
          >
            <Boton to="/cuentas" tam="sm" className="mt-4">Agregar una cuenta</Boton>
          </EstadoVacio>
        ) : !puedeCompartir ? (
          <p className="mx-6 mt-6 text-sm text-ink-soft">Las cuentas que ves son de otra persona: solo su dueño puede compartirlas.</p>
        ) : (
          <form onSubmit={invitar}>
            <Paso numero={1} titulo="¿Qué cuentas quieres compartir?">
              <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden" role="group" aria-label="Cuentas para compartir">
                {(propias || cuentas.map((cuenta) => ({ cuenta }))).map(({ cuenta }) => {
                  const marcada = elegidas.includes(cuenta.id)
                  return (
                    <label key={cuenta.id} className="flex items-center gap-3 px-4 py-3 min-h-[52px] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={marcada}
                        onChange={() => alternar(cuenta.id)}
                        className="w-5 h-5 accent-[var(--c-accent)] shrink-0"
                      />
                      <span className="flex-1 min-w-0 text-sm font-medium truncate">{cuenta.nombre}</span>
                    </label>
                  )
                })}
              </div>
            </Paso>

            <Paso numero={2} titulo="¿Con quién? Escribe su correo">
              <CampoTexto
                etiqueta="Correo de la persona"
                type="email"
                inputMode="email"
                autoComplete="off"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Ej. ana@correo.com"
                ayuda="Le llegará la invitación cuando entre a CuadraMe con ese correo."
              />
            </Paso>

            <Paso numero={3} titulo="¿Qué podrá hacer?">
              <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Qué podrá hacer la otra persona">
                {ROLES.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    role="radio"
                    aria-checked={rol === r.id}
                    onClick={() => setRol(r.id)}
                    className={`rounded-2xl border px-3 py-3 min-h-[52px] text-sm font-semibold flex items-center justify-center gap-2 ${
                      rol === r.id ? 'bg-ink text-paper border-ink' : 'border-line bg-paper-raised text-ink-soft'
                    }`}
                  >
                    <Icono icono={r.icono} tam="sm" /> {r.titulo}
                  </button>
                ))}
              </div>
              <div className="mt-3 rounded-2xl bg-accent-soft p-3.5 space-y-1.5" data-testid="que-ve" role="note">
                <p className="text-xs flex gap-2"><Icono icono={Eye} tam="sm" className="text-accent shrink-0" /> <span><b>Sí ve:</b> {rolElegido.ve}</span></p>
                <p className="text-xs flex gap-2"><Icono icono={EyeOff} tam="sm" className="text-ink-soft shrink-0" /> <span><b>No:</b> {rolElegido.noVe}</span></p>
              </div>
            </Paso>

            <div className="mx-6 mt-6">
              {error && <p role="alert" className="text-sm text-danger mb-3">{error}</p>}
              <Boton type="submit" bloque cargando={enviando} icono={UserPlus}>
                {enviando ? 'Enviando...' : 'Enviar invitación'}
              </Boton>
            </div>
          </form>
        )}

        {filas.length > 0 && (
          <section className="mx-6 mt-8" aria-label="Quién tiene acceso">
            <h2 className="text-[15px] font-semibold mb-3">Quién tiene acceso</h2>
            <div className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden" data-testid="estado-compartido">
              {filas.map((f) => (
                <div key={f.clave} className="flex items-center gap-3 px-4 py-3 min-h-[56px]" data-estado={f.estado}>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{f.correo || 'Una persona con acceso'}</p>
                    <p className="text-xs text-ink-soft truncate">{f.cuenta.nombre} · {etiquetaRol(f.rol)}</p>
                  </div>
                  {f.estado === 'activo' && (
                    <>
                      <span className="text-xs font-semibold text-accent shrink-0">Ya tiene acceso</span>
                      <button
                        type="button"
                        onClick={() => dejarDeCompartir(f)}
                        className="w-11 h-11 -mr-2 flex items-center justify-center text-danger shrink-0"
                        aria-label={`Dejar de compartir ${f.cuenta.nombre}${f.correo ? ` con ${f.correo}` : ''}`}
                      >
                        <UserMinus size={16} />
                      </button>
                    </>
                  )}
                  {f.estado === 'pendiente' && <span className="text-xs font-semibold text-gold shrink-0">Esperando respuesta</span>}
                  {f.estado === 'rechazada' && <span className="text-xs font-semibold text-ink-soft shrink-0">No aceptó</span>}
                </div>
              ))}
            </div>
            <p className="text-xs text-ink-soft mt-2">«Dejar de compartir» quita el acceso al instante. No borra tus cuentas ni tus movimientos.</p>
          </section>
        )}

        <p className="mx-6 mt-8 text-xs text-ink-soft">
          ¿Quieres repartir un gasto con amigos? Eso es otra cosa: <Link to="/amigos" className="text-accent font-semibold underline">Dividir gastos con amigos</Link>.
        </p>
      </div>
    </div>
  )
}
