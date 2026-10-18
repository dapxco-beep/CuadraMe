import { useState } from 'react'
import { GraduationCap, Loader2, Search } from 'lucide-react'
import { api } from '../lib/api'
import { mensajeDeError } from '../lib/mensajes'
import HojaEnsenarCorreo from './HojaEnsenarCorreo'

// Modo «movimiento»: igual pero sin exigir PDF (una notificación del banco); al agregar, queda en «Por revisar».
// «¿No ves un extracto?»: la persona escribe el asunto (o parte) del correo; se busca en SU Gmail (solo
// lectura, 365 días, solo con PDF adjunto) y elige cuáles pasar a la lista de extractos. No guarda nada
// hasta que pulsa «Agregar».
export function textoAgregadoMov(r) {
  const n = r?.movimientos_nuevos || 0
  if (n) return `Listo: ${n} movimiento${n === 1 ? '' : 's'} en «Por revisar».`
  if (r?.descartados) return 'Ese correo no parece un movimiento (sin monto o es un aviso), no lo agregué.'
  return 'Ese correo ya estaba registrado.'
}

export default function BuscarExtractoPorAsunto({ onAgregado, modo = 'extracto' }) {
  const mov = modo === 'movimiento'
  const [asunto, setAsunto] = useState('')
  const [buscando, setBuscando] = useState(false)
  const [agregando, setAgregando] = useState(false)
  const [hallados, setHallados] = useState(null)
  const [elegidos, setElegidos] = useState({})
  const [error, setError] = useState('')
  const [listo, setListo] = useState('')
  const [ensenando, setEnsenando] = useState(null)

  async function buscar(e) {
    e?.preventDefault()
    if (asunto.trim().length < 3 || buscando) return
    setBuscando(true)
    setError('')
    setListo('')
    try {
      const r = await api.buscarExtractosPorAsunto(asunto.trim(), modo)
      const lista = Array.isArray(r) ? r : []
      setHallados(lista)
      setElegidos(Object.fromEntries(lista.filter((x) => !x.ya_en_lista).map((x) => [x.gmail_msg_id, true])))
    } catch (err) {
      setHallados(null)
      setError(mensajeDeError(err))
    } finally {
      setBuscando(false)
    }
  }

  async function agregar() {
    const ids = Object.keys(elegidos).filter((k) => elegidos[k])
    if (!ids.length || agregando) return
    setAgregando(true)
    setError('')
    try {
      const r = await api.procesarExtractosPorAsunto(ids, modo)
      setListo(mov ? textoAgregadoMov(r) : r?.extractos_nuevos ? `Listo: ${r.extractos_nuevos} extracto${r.extractos_nuevos === 1 ? '' : 's'} agregado${r.extractos_nuevos === 1 ? '' : 's'} a tu lista.` : 'Esos correos ya estaban en tu lista.')
      setHallados(null)
      onAgregado?.()
    } catch (err) {
      setError(mensajeDeError(err))
    } finally {
      setAgregando(false)
    }
  }

  // Ya aprendió a leer ese correo: se pasa por la misma tubería para que quede en «Por revisar» con lo que enseñó.
  async function alEnsenar(h, correo) {
    if (correo?.estado === 'pendiente') {
      setListo(textoAgregadoMov({ movimientos_nuevos: 1 }))
      setHallados((lista) => (lista || []).filter((x) => x.gmail_msg_id !== h.gmail_msg_id))
      return onAgregado?.()
    }
    if (h.ya_en_lista) return onAgregado?.()
    try {
      const r = await api.procesarExtractosPorAsunto([h.gmail_msg_id], modo)
      setListo(textoAgregadoMov(r))
      setHallados((lista) => (lista || []).filter((x) => x.gmail_msg_id !== h.gmail_msg_id))
      onAgregado?.()
    } catch (err) {
      setError(mensajeDeError(err))
    }
  }

  const fecha = (iso) => (iso ? new Date(iso).toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }) : '')
  const nElegidos = Object.values(elegidos).filter(Boolean).length

  return (
    <section className="mt-4 rounded-2xl border border-line p-3.5" aria-label={mov ? 'Buscar un movimiento por asunto' : 'Buscar un extracto por asunto'} data-testid="buscar-asunto">
      <form onSubmit={buscar}>
        <label htmlFor="buscar-asunto-input" className="text-sm font-semibold">{mov ? '¿Falta un movimiento?' : '¿No ves un extracto?'}</label>
        <p className="text-xs text-ink-soft mt-0.5">Escribe el asunto del correo (o parte de él) y lo busco en tu Gmail.</p>
        <div className="flex gap-2 mt-2">
          <input
            id="buscar-asunto-input"
            value={asunto}
            onChange={(e) => setAsunto(e.target.value)}
            maxLength={80}
            placeholder={mov ? 'Ej.: Pagaste con tu Cuenta de ahorros' : 'Ej.: Llegó el extracto de tu tarjeta de crédito'}
            className="flex-1 min-w-0 bg-paper rounded-xl px-3 min-h-[44px] text-sm"
          />
          <button
            type="submit"
            disabled={buscando || asunto.trim().length < 3}
            className="bg-accent text-paper-raised font-semibold rounded-xl px-4 min-h-[44px] text-sm disabled:opacity-50 flex items-center gap-1.5"
          >
            {buscando ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <Search size={16} aria-hidden="true" />}
            Buscar
          </button>
        </div>
      </form>

      {error && <p className="text-xs text-danger mt-2" role="alert">{error}</p>}
      {listo && <p className="text-xs text-cuadra mt-2" role="status">{listo}</p>}

      {hallados && hallados.length === 0 && (
        <p className="text-xs text-ink-soft mt-2">{mov ? 'No encontré correos con ese asunto en el último año.' : 'No encontré correos con PDF adjunto y ese asunto en el último año.'}</p>
      )}
      {hallados && hallados.length > 0 && (
        <div className="mt-3">
          <ul className="flex flex-col gap-2">
            {hallados.map((h) => (
              <li key={h.gmail_msg_id} className="rounded-xl bg-paper p-2.5">
                <label className="flex items-start gap-2.5 min-h-[44px]">
                  <input
                    type="checkbox"
                    className="mt-1"
                    disabled={h.ya_en_lista}
                    checked={Boolean(elegidos[h.gmail_msg_id])}
                    onChange={(e) => setElegidos((p) => ({ ...p, [h.gmail_msg_id]: e.target.checked }))}
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium truncate">{h.asunto || '(sin asunto)'}</span>
                    <span className="block text-xs text-ink-soft truncate">{h.remitente} · {fecha(h.fecha)}</span>
                    {h.ya_en_lista && <span className="block text-xs text-ink-soft">Ya está en tu lista</span>}
                  </span>
                </label>
                {mov && (
                  <button
                    type="button"
                    onClick={() => setEnsenando(h)}
                    className="mt-1 ml-6 min-h-[44px] px-3 rounded-xl border border-line text-xs font-medium text-ink-soft flex items-center gap-1.5"
                    data-testid={`ensenar-${h.gmail_msg_id}`}
                  >
                    <GraduationCap size={16} aria-hidden="true" /> Enseñarle a leer este correo
                  </button>
                )}
              </li>
            ))}
          </ul>
          <button
            onClick={agregar}
            disabled={!nElegidos || agregando}
            className="mt-2 w-full bg-accent text-paper-raised font-semibold rounded-xl min-h-[44px] text-sm disabled:opacity-50"
          >
            {agregando ? 'Agregando…' : `Agregar ${nElegidos || ''} ${mov ? 'a Por revisar' : 'a mis extractos'}`.replace('  ', ' ')}
          </button>
        </div>
      )}
      {ensenando && (
        <HojaEnsenarCorreo
          gmailMsgId={ensenando.gmail_msg_id}
          onCerrar={() => setEnsenando(null)}
          onListo={(r) => alEnsenar(ensenando, r?.correo)}
        />
      )}
    </section>
  )
}
