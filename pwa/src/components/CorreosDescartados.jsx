import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Undo2 } from 'lucide-react'
import { api } from '../lib/api'
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
        className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-accent min-h-[36px] disabled:opacity-60"
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

  useEffect(() => {
    if (abiertoInicial) setAbierto(true)
  }, [abiertoInicial])

  useEffect(() => {
    if (!abierto) return
    let vivo = true
    Promise.resolve(api.correosDescartados?.())
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
