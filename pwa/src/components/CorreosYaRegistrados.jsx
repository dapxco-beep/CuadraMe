import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, CopyCheck } from 'lucide-react'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { fraseCanales } from '../lib/canales'

// «X correos ya estaban registrados y no se muestran»: los correos del banco cuyo gasto ya existe
// (lo registró el atajo, tú a mano o el extracto) no salen en «Por revisar». Aquí se pueden ver, y si
// alguno era OTRO gasto igual se puede devolver con «Mostrar de todos modos / No es duplicado».
export default function CorreosYaRegistrados({ cantidad = 0, onCambio }) {
  const [abierto, setAbierto] = useState(false)
  const [lista, setLista] = useState(null)
  const [ocupado, setOcupado] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!abierto) return
    let vivo = true
    Promise.resolve(api.correosYaRegistrados?.())
      .then((r) => vivo && setLista(Array.isArray(r) ? r : []))
      .catch((e) => vivo && setError(e.message || 'No pudimos cargar esos correos'))
    return () => {
      vivo = false
    }
  }, [abierto, cantidad])

  if (!cantidad) return null

  async function mostrar(c) {
    if (ocupado) return
    setOcupado(c.id)
    setError('')
    try {
      await api.correoNoEsDuplicado(c.id)
      setLista((l) => (l || []).filter((x) => x.id !== c.id))
      onCambio?.()
    } catch (e) {
      setError(e.message || 'No se pudo devolver el correo. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setOcupado(null)
    }
  }

  return (
    <div className="mt-3 rounded-2xl bg-paper" data-testid="correos-ya-registrados">
      <button
        onClick={() => setAbierto((a) => !a)}
        aria-expanded={abierto}
        className="w-full flex items-center gap-2.5 px-3.5 py-3 min-h-[48px] text-left"
      >
        <CopyCheck size={16} className="text-cuadra shrink-0" aria-hidden="true" />
        <span className="flex-1 text-xs text-ink-soft">
          <b className="text-ink">
            {cantidad} {cantidad === 1 ? 'correo ya estaba registrado' : 'correos ya estaban registrados'}
          </b>{' '}
          y no se {cantidad === 1 ? 'muestra' : 'muestran'}, para no repetirlos.
        </span>
        {abierto ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
      </button>

      {abierto && (
        <div className="border-t border-line/50">
          {error && <p className="text-xs text-danger px-3.5 py-2" role="alert">{error}</p>}
          {lista === null && !error && <p className="text-xs text-ink-soft px-3.5 py-3">Cargando...</p>}
          {lista && lista.length === 0 && <p className="text-xs text-ink-soft px-3.5 py-3">No hay correos escondidos.</p>}
          <ul className="divide-y divide-line">
            {(lista || []).map((c) => (
              <li key={c.id} className="px-3.5 py-3" data-testid={`ya-registrado-${c.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold truncate">{c.comercio}</p>
                    {c.registrado_como ? (
                      <p className="text-xs text-ink-soft">
                        Ya lo tenías: «{c.registrado_como.descripcion}», registrado desde {fraseCanales(c.registrado_como.canales) || 'otro canal'}.
                      </p>
                    ) : (
                      <p className="text-xs text-ink-soft">Ya lo tenías registrado.</p>
                    )}
                  </div>
                  <p className="text-sm font-bold shrink-0">{formatMoneda(c.monto)}</p>
                </div>
                <button
                  onClick={() => mostrar(c)}
                  disabled={ocupado === c.id}
                  className="mt-2 text-xs font-semibold text-accent min-h-[36px] disabled:opacity-60"
                >
                  Mostrar de todos modos: es otro gasto igual
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
