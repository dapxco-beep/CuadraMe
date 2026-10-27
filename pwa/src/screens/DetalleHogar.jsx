import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Bell, BellOff, Copy, MessageCircle, Plus, Share2 } from 'lucide-react'
import { EsqueletoLista } from '../components/Esqueletos'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { useDialogos } from '../lib/DialogosContext'
import { enlaceCobroHogar, enlaceCompartirInvitacion, enlaceInvitacionHogar, fraseDeuda } from '../lib/hogares'

// Un parche: quién le debe a quién, los gastos del libro común, las personas y las invitaciones.
export default function DetalleHogar() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { confirmar, avisar } = useDialogos()
  const [h, setH] = useState(null)
  const [gastos, setGastos] = useState([])
  const [error, setError] = useState('')
  const [correo, setCorreo] = useState('')

  const cargar = useCallback(async () => {
    setError('')
    try {
      const [d, g] = await Promise.all([api.hogar(id), api.gastosHogar(id)])
      setH(d)
      setGastos(g)
    } catch (e) {
      setError(e.status === 404 ? 'Este parche no existe o ya no haces parte de él.' : e.message || 'No se pudo cargar el parche. Revisa tu conexión.')
    }
  }, [id])
  useEffect(() => {
    cargar()
  }, [cargar])

  const esAdmin = h?.rol === 'admin'

  async function registrarPago(p) {
    const ok = await confirmar(`¿Registrar que ${p.de_nombre} le pagó ${formatMoneda(p.monto, h.moneda)} a ${p.a_nombre}?`, { confirmarTexto: 'Sí, registrar' })
    if (!ok) return
    try {
      await api.pagarHogar(id, { de_id: p.de, a_id: p.a, monto: p.monto })
      avisar('Pago registrado', 'ok')
      cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo registrar el pago. Intenta de nuevo.')
    }
  }

  async function borrarGasto(g) {
    const ok = await confirmar(`¿Quitar “${g.descripcion}” del parche? Si lo copiaste a tu cuenta, ese movimiento no se borra.`, { confirmarTexto: 'Quitar' })
    if (!ok) return
    try {
      await api.borrarGastoHogar(id, g.id)
      cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo quitar el gasto. Intenta de nuevo.')
    }
  }

  async function invitar() {
    try {
      await api.invitarAlHogar(id, correo.trim())
      setCorreo('')
      cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo crear la invitación. Intenta de nuevo.')
    }
  }

  async function copiar(enlace) {
    try {
      await navigator.clipboard.writeText(enlace)
      avisar('Enlace copiado', 'ok')
    } catch {
      avisar('No se pudo copiar. Mantén presionado el enlace para copiarlo.')
    }
  }

  async function cancelar(inv) {
    try {
      await api.cancelarInvitacionHogar(id, inv.id)
      cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo cancelar la invitación. Intenta de nuevo.')
    }
  }

  async function cambiarRol(m) {
    try {
      await api.rolMiembroHogar(id, m.id, m.rol === 'admin' ? 'miembro' : 'admin')
      cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo cambiar el rol. Intenta de nuevo.')
    }
  }

  async function quitar(m) {
    const yo = m.soy_yo
    const ok = await confirmar(
      yo ? `¿Salir de “${h.nombre}”? Ya no verás nada del parche; lo que aportaste se conserva para los demás.` : `¿Sacar a ${m.apodo} del parche?`,
      { confirmarTexto: yo ? 'Salir' : 'Sacar', peligro: true }
    )
    if (!ok) return
    try {
      const r = await api.quitarMiembroHogar(id, m.id)
      if (yo || r?.hogar_borrado) navigate('/hogares', { replace: true })
      else cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo completar. Intenta de nuevo.')
    }
  }

  async function borrarHogar() {
    const ok = await confirmar(`¿Borrar “${h.nombre}” para TODOS? Se pierde el libro completo.`, { confirmarTexto: 'Borrar para todos', peligro: true })
    if (!ok) return
    try {
      await api.borrarHogar(id)
      navigate('/hogares', { replace: true })
    } catch (e) {
      avisar(e.message || 'No se pudo borrar el parche. Intenta de nuevo.')
    }
  }

  async function alternarAvisos() {
    try {
      await api.ajustesHogar(id, { avisos: !h.mis_avisos })
      cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo cambiar el ajuste. Intenta de nuevo.')
    }
  }

  const Cabecera = (
    <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
      <button onClick={() => navigate('/hogares')} className="w-11 h-11 shrink-0 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Volver">
        <ArrowLeft size={20} />
      </button>
      <h1 className="text-2xl font-semibold truncate">{h?.nombre || 'Parche'}</h1>
    </header>
  )

  if (error) {
    return (
      <div className="flex-1 overflow-y-auto pb-8 screen-enter">
        {Cabecera}
        <p className="px-5 mt-6 text-sm text-danger" role="alert">{error}</p>
        <button onClick={cargar} className="px-5 text-sm text-accent font-medium mt-1">Reintentar</button>
      </div>
    )
  }
  if (!h) {
    return (
      <div className="flex-1 overflow-y-auto pb-8 screen-enter">
        {Cabecera}
        <EsqueletoLista filas={3} className="mx-5 mt-6" etiqueta="Cargando parche" />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto pb-10 screen-enter">
      {Cabecera}

      <section className="px-5 mt-2">
        <div className="rounded-2xl border border-line bg-paper-raised p-4">
          <p className="text-xs text-ink-soft uppercase tracking-wide font-medium">Quién le debe a quién</p>
          {h.simplificado.length === 0 ? (
            <p className="text-sm mt-2">Están a mano.</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-3">
              {h.simplificado.map((p) => (
                <li key={`${p.de}-${p.a}`}>
                  <p className="text-sm font-semibold tabular-nums">{fraseDeuda(p, h.mi_miembro_id, h.moneda)}</p>
                  <div className="flex gap-2 mt-1.5">
                    <button onClick={() => registrarPago(p)} className="rounded-xl border border-line text-xs font-semibold px-3 py-2">
                      {p.de === h.mi_miembro_id ? 'Ya le pagué' : p.a === h.mi_miembro_id ? 'Me pagó' : 'Registrar pago'}
                    </button>
                    {p.a === h.mi_miembro_id && (
                      <a href={enlaceCobroHogar({ hogar: h.nombre, deudor: p.de_nombre, monto: p.monto, moneda: h.moneda })} target="_blank" rel="noopener noreferrer" className="rounded-xl bg-accent-soft text-accent text-xs font-semibold px-3 py-2 flex items-center gap-1.5">
                        <MessageCircle size={16} /> Recordar
                      </a>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex gap-2 mt-3">
          <button onClick={() => navigate(`/hogares/${id}/gasto`)} className="flex-1 bg-ink text-paper rounded-2xl py-3 text-sm font-semibold flex items-center justify-center gap-2">
            <Plus size={16} /> Nuevo gasto
          </button>
          <button onClick={() => navigate(`/hogares/${id}/resumen`)} className="rounded-2xl border border-line bg-paper-raised px-4 text-sm font-semibold">
            Resumen del mes
          </button>
        </div>
      </section>

      <section className="px-5 mt-6">
        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Gastos</p>
        {gastos.length === 0 && <p className="text-sm text-ink-soft">Aún no hay gastos. Registra el primero con “Nuevo gasto”.</p>}
        <ul className="flex flex-col gap-2">
          {gastos.map((g) => (
            <li key={g.id} className="rounded-2xl border border-line bg-paper-raised px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold break-words">{g.descripcion}</p>
                  <p className="text-xs text-ink-soft">
                    Pagó {g.pagador} · {new Date(g.fecha).toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })}
                    {g.categoria ? ` · ${g.categoria}` : ''}
                  </p>
                </div>
                <p className="text-sm font-semibold tabular-nums shrink-0">{formatMoneda(g.total, g.moneda)}</p>
              </div>
              {(esAdmin || g.creado_por_id === h.mi_miembro_id) && (
                <button onClick={() => borrarGasto(g)} className="mt-1 text-[11px] text-ink-soft underline">Quitar</button>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="px-5 mt-6">
        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Personas</p>
        <ul className="flex flex-col gap-2">
          {h.miembros.filter((m) => m.activo || m.saldo !== 0).map((m) => (
            <li key={m.id} className="rounded-2xl border border-line bg-paper-raised px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold truncate">
                    {m.apodo}{m.soy_yo ? ' (tú)' : ''}{m.rol === 'admin' && m.activo ? ' · administra' : ''}{!m.activo ? ' · ya no está' : ''}
                  </p>
                  <p className={`text-xs tabular-nums ${m.saldo > 0 ? 'text-accent' : m.saldo < 0 ? 'text-danger' : 'text-ink-soft'}`}>
                    {m.saldo > 0 ? `Le deben ${formatMoneda(m.saldo, h.moneda)}` : m.saldo < 0 ? `Debe ${formatMoneda(-m.saldo, h.moneda)}` : 'A mano'}
                  </p>
                </div>
                {m.activo && (
                  <div className="flex gap-3 shrink-0 text-xs">
                    {esAdmin && !m.soy_yo && <button onClick={() => cambiarRol(m)} className="min-h-9 text-ink-soft underline">{m.rol === 'admin' ? 'Quitar admin' : 'Hacer admin'}</button>}
                    {(m.soy_yo || esAdmin) && <button onClick={() => quitar(m)} className="min-h-9 text-danger underline">{m.soy_yo ? 'Salir' : 'Sacar'}</button>}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      {esAdmin && (
        <section className="px-5 mt-6">
          <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Invitar</p>
          <div className="flex gap-2">
            <input aria-label="Correo de la persona (opcional)" value={correo} onChange={(e) => setCorreo(e.target.value)} placeholder="Correo (opcional)" inputMode="email" className="flex-1 min-w-0 rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm outline-none focus:border-accent" />
            <button onClick={invitar} className="shrink-0 bg-ink text-paper rounded-2xl px-4 text-sm font-semibold flex items-center gap-1.5">
              <Share2 size={16} /> Crear
            </button>
          </div>
          <p className="text-[11px] text-ink-soft mt-1">Con correo, solo esa cuenta puede unirse. Sin correo, quien tenga el enlace (una sola vez, por 7 días).</p>
          <ul className="mt-2 flex flex-col gap-2">
            {h.invitaciones.map((i) => {
              const enlace = enlaceInvitacionHogar(i.token)
              return (
                <li key={i.id} className="rounded-2xl border border-line bg-paper-raised p-3">
                  <p className="text-xs text-ink-soft">{i.email ? `Para ${i.email}` : 'Para quien tenga el enlace'}</p>
                  <p className="text-xs break-all mt-1 select-all">{enlace}</p>
                  <div className="flex gap-2 mt-2">
                    <button onClick={() => copiar(enlace)} className="flex-1 rounded-xl border border-line text-xs font-semibold py-2 flex items-center justify-center gap-1.5"><Copy size={16} /> Copiar</button>
                    <a href={enlaceCompartirInvitacion({ hogar: h.nombre, enlace })} target="_blank" rel="noopener noreferrer" className="flex-1 rounded-xl bg-accent-soft text-accent text-xs font-semibold py-2 flex items-center justify-center gap-1.5"><MessageCircle size={16} /> WhatsApp</a>
                    <button onClick={() => cancelar(i)} className="px-3 text-xs text-ink-soft underline">Cancelar</button>
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      )}

      <section className="px-5 mt-6 flex flex-col gap-2">
        <button onClick={alternarAvisos} className="rounded-2xl border border-line bg-paper-raised py-3 text-sm font-semibold flex items-center justify-center gap-2">
          {h.mis_avisos ? <Bell size={16} /> : <BellOff size={16} />}
          {h.mis_avisos ? 'Avisarme cuando alguien registre un gasto' : 'Avisos apagados'}
        </button>
        {esAdmin && <button onClick={borrarHogar} className="text-sm text-danger underline mt-3">Borrar parche para todos</button>}
      </section>
    </div>
  )
}
