import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Undo2 } from 'lucide-react'
import { api } from '../lib/api'
import { useDialogos } from '../lib/DialogosContext'
import { formatMoneda } from '../lib/format'
import { etiquetaFechaHora } from '../lib/fechaCorreo'

// Una fila de correo que se puede recuperar: fecha y hora, comercio, monto, motivo y «Recuperar».
// La usan «Correos descartados» y «Correos ignorados» (estos solo si traen monto).
export function FilaRecuperable({ c, ocupado, onRecuperar }) {
  const fecha = etiquetaFechaHora(c.fecha_movimiento || c.recibido_en_co, c.fecha_movimiento_con_hora)
  return (
    <li className="px-3.5 py-3" data-testid={`descartado-${c.id}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold break-words line-clamp-2">{c.comercio || c.asunto}</p>
          {fecha && <p className="text-xs text-ink-soft">{fecha}</p>}
          {c.motivo_descarte && <p className="text-xs text-ink-soft">{c.motivo_descarte}.</p>}
        </div>
        <p className="text-sm font-bold shrink-0">{formatMoneda(c.monto, c.moneda || 'COP')}</p>
      </div>
      <button
        onClick={() => onRecuperar(c)}
        disabled={ocupado === c.id}
        className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-accent min-h-[44px] disabled:opacity-60"
      >
        <Undo2 size={16} aria-hidden="true" /> Recuperar
      </button>
    </li>
  )
}

// Recupera un correo y dice en una frase a dónde fue: «Por revisar» o «ya lo tenías registrado».
export async function recuperarCorreo(id) {
  const r = await api.recuperarCorreo(id)
  return r?.estado === 'ya_registrado'
    ? 'Ya tenías ese movimiento registrado, así que no lo repetí.'
    : 'Listo: lo encuentras en «Por revisar».'
}

// «Correos descartados»: los que no llegaron a Movimientos porque borraste uno parecido, o los descartaste tú.
export default function CorreosDescartados({ cantidad = 0, abierto: abiertoInicial = false, onCambio }) {
  const [abierto, setAbierto] = useState(abiertoInicial)
  const [lista, setLista] = useState(null)
  const [ocupado, setOcupado] = useState(null)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const { confirmar } = useDialogos() || {}

  useEffect(() => {
    if (abiertoInicial) setAbierto(true)
  }, [abiertoInicial])

  useEffect(() => {
    if (!abierto) return
    let vivo = true
    Promise.resolve(api.correosDescartados?.(100))
      .then((r) => vivo && setLista(Array.isArray(r) ? r : []))
      .catch((e) => vivo && setError(e.message || 'No pudimos cargar esos correos. Revisa tu conexión e intenta de nuevo.'))
    return () => {
      vivo = false
    }
  }, [abierto, cantidad])

  if (!cantidad && !(lista && lista.length) && !aviso) return null

  async function recuperar(c) {
    if (ocupado) return
    setOcupado(c.id)
    setError('')
    try {
      setAviso(await recuperarCorreo(c.id))
      setLista((l) => (l || []).filter((x) => x.id !== c.id))
      onCambio?.()
    } catch (e) {
      setError(e.message || 'No se pudo recuperar el correo. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setOcupado(null)
    }
  }

  // «Recuperar todos»: con confirmación y el conteo; un correo que ya tiene su movimiento no se repite.
  async function recuperarTodos() {
    const pendientes = lista || []
    if (ocupado || !pendientes.length) return
    const n = pendientes.length
    if (confirmar) {
      const ok = await confirmar(
        `Paso ${n === 1 ? 'el correo' : `los ${n} correos`} a «Por revisar» para que apruebes lo que sí era tuyo. Si alguno ya está registrado, no lo repito.`,
        { titulo: n === 1 ? '¿Recuperar este correo?' : `¿Recuperar los ${n} correos?`, confirmarTexto: n === 1 ? 'Recuperar' : 'Recuperar todos' },
      )
      if (!ok) return
    }
    setOcupado('todos')
    setError('')
    setAviso('')
    let aRevisar = 0
    let yaEstaban = 0
    let fallaron = 0
    for (const c of pendientes) {
      try {
        const r = await api.recuperarCorreo(c.id)
        if (r?.estado === 'ya_registrado') yaEstaban += 1
        else aRevisar += 1
        setLista((l) => (l || []).filter((x) => x.id !== c.id))
      } catch {
        fallaron += 1
      }
    }
    setOcupado(null)
    const partes = []
    if (aRevisar) partes.push(`${aRevisar} ${aRevisar === 1 ? 'quedó' : 'quedaron'} en «Por revisar»`)
    if (yaEstaban) partes.push(`${yaEstaban} ya ${yaEstaban === 1 ? 'estaba registrado' : 'estaban registrados'}`)
    setAviso(partes.length ? `Listo: ${partes.join(' y ')}.` : '')
    if (fallaron) setError(`No pude recuperar ${fallaron} ${fallaron === 1 ? 'correo' : 'correos'}. Revisa tu conexión e intenta de nuevo.`)
    onCambio?.()
  }

  return (
    <div className="mt-3 rounded-2xl bg-paper" data-testid="correos-descartados">
      <button
        onClick={() => setAbierto((a) => !a)}
        aria-expanded={abierto}
        className="w-full flex items-center gap-2.5 px-3.5 py-3 min-h-[48px] text-left"
      >
        <Undo2 size={16} className="text-ink-soft shrink-0" aria-hidden="true" />
        <span className="flex-1 text-xs text-ink-soft">
          <b className="text-ink">Correos descartados{cantidad ? ` (${cantidad})` : ''}</b>
        </span>
        {abierto ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
      </button>

      {abierto && (
        <div className="border-t border-line/50">
          <p className="text-xs text-ink-soft px-3.5 py-2.5">
            Los descartaste al borrar un movimiento parecido, o no eran una compra.
          </p>
          {aviso && <p className="text-xs text-cuadra px-3.5 pb-2" role="status">{aviso}</p>}
          {error && <p className="text-xs text-danger px-3.5 py-2" role="alert">{error}</p>}
          {lista === null && !error && <p className="text-xs text-ink-soft px-3.5 py-3">Cargando...</p>}
          {lista && lista.length === 0 && <p className="text-xs text-ink-soft px-3.5 py-3">No hay correos descartados.</p>}
          {lista && lista.length > 1 && (
            <div className="px-3.5 pb-2.5">
              <button
                type="button"
                onClick={recuperarTodos}
                disabled={Boolean(ocupado)}
                data-testid="recuperar-todos"
                className="w-full min-h-[44px] flex items-center justify-center gap-2 rounded-xl bg-accent text-paper-raised text-sm font-semibold disabled:opacity-60"
              >
                <Undo2 size={16} aria-hidden="true" /> {ocupado === 'todos' ? 'Recuperando...' : `Recuperar todos (${lista.length})`}
              </button>
            </div>
          )}
          <ul className="divide-y divide-line">
            {(lista || []).map((c) => (
              <FilaRecuperable key={c.id} c={c} ocupado={ocupado} onRecuperar={recuperar} />
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
