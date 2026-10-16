import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, ArrowLeftRight } from 'lucide-react'
import { EsqueletoLista } from '../components/Esqueletos'
import { EstadoVacio } from '../brand/Marca'
import Ayudita from '../components/Ayudita'
import { useVolver } from '../lib/useVolver'
import { fechaHoraMovimiento, fechaDeMovimiento } from '../lib/fechaMovimiento'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'

// «Revisar posibles traslados»: la app NO aplica nada sola. Aquí la persona marca las sugerencias
// que sí son plata entre sus cuentas (no cuenta como ingreso ni gasto) o dice que no lo son.
export default function RevisarTraslados() {
  const volver = useVolver('/movimientos')
  const { fmt } = useBloqueo()
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [elegidas, setElegidas] = useState(new Set())
  const [guardando, setGuardando] = useState(false)
  const [aviso, setAviso] = useState('')

  const cargar = useCallback(() => {
    setError('')
    return api.sugerenciasTraslado()
      .then((r) => {
        setItems(r.sugerencias)
        setElegidas(new Set(r.sugerencias.filter((s) => s.tipo === 'par').map((s) => s.ids.join('|'))))
      })
      .catch(() => setError('No pudimos cargar las sugerencias. Revisa tu conexión e intenta de nuevo.'))
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  function alternar(k) {
    setElegidas((p) => {
      const n = new Set(p)
      if (n.has(k)) n.delete(k)
      else n.add(k)
      return n
    })
  }

  async function decidir(decision, lista) {
    const ids = lista.flatMap((s) => s.ids)
    if (!ids.length) return
    setGuardando(true)
    setAviso('')
    try {
      await api.decidirTraslado({ ids, decision, recordar: true })
      setAviso(decision === 'traslado'
        ? `Listo: ${lista.length} ya no cuentan como ingreso ni gasto.`
        : `Listo: ${lista.length} cuentan como ingreso o gasto real.`)
      await cargar()
    } catch {
      setError('No pudimos guardarlo. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setGuardando(false)
    }
  }

  const seleccion = (items || []).filter((s) => elegidas.has(s.ids.join('|')))

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter pantalla-ancha">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Revisar posibles traslados</h1>
      </header>
      <p className="px-6 text-sm text-ink-soft">
        Un traslado es plata que pasas entre tus cuentas: no cuenta como ingreso ni gasto. <Ayudita termino="traslado" /> Tú decides; no cambiamos nada solos.
      </p>

      {error && <p role="alert" className="mx-6 mt-4 text-sm text-danger">{error}</p>}
      {aviso && <p role="status" className="mx-6 mt-4 text-sm text-cuadra">{aviso}</p>}
      {!items && !error && <div className="mx-6 mt-4"><EsqueletoLista filas={4} /></div>}

      {items && items.length === 0 && (
        <EstadoVacio
          icono={ArrowLeftRight}
          titulo="No hay nada por revisar"
          texto="Cuando aparezcan movimientos que parezcan pasar plata entre tus cuentas, los verás aquí."
          className="mx-6 mt-6"
        />
      )}

      {items && items.length > 0 && (
        <>
          <ul className="mx-6 mt-4 space-y-3">
            {items.map((s) => {
              const k = s.ids.join('|')
              return (
                <li key={k} className="card-marca bg-paper-raised border border-line p-3">
                  <label className="flex items-start gap-3 min-h-[44px]">
                    <input
                      type="checkbox"
                      checked={elegidas.has(k)}
                      onChange={() => alternar(k)}
                      className="mt-1 w-5 h-5 accent-[var(--color-accent)]"
                      aria-label={s.tipo === 'par' ? 'Es un traslado entre mis cuentas' : '¿Fue entre tus cuentas?'}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[11px] font-semibold text-ink-soft">
                        {s.tipo === 'par' ? 'Sale de una cuenta y entra a otra' : 'Posible traslado: ¿Fue entre tus cuentas?'}
                      </span>
                      {s.movimientos.map((m) => (
                        <span key={m.id} className="flex items-start justify-between gap-3 text-sm mt-1.5">
                          <span className="min-w-0">
                            <span className="block font-semibold break-words line-clamp-3">{m.descripcion}</span>
                            <span className="block text-xs text-ink-soft break-words">{[fechaHoraMovimiento(fechaDeMovimiento(m)), m.cuenta].filter(Boolean).join(' · ')}</span>
                          </span>
                          <span className={`font-semibold shrink-0 whitespace-nowrap tabular-nums ${m.tipo === 'income' ? 'text-accent' : ''}`}>
                            {m.tipo === 'income' ? '+' : '-'}{fmt(m.monto)}
                          </span>
                        </span>
                      ))}
                      {s.diferencia > 0 && <span className="block text-[11px] text-ink-soft mt-1">Diferencia de {fmt(s.diferencia)}: parece una comisión.</span>}
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>
          <div className="mx-6 mt-4 flex flex-col gap-2">
            <button
              onClick={() => decidir('traslado', seleccion)}
              disabled={guardando || seleccion.length === 0}
              className="rounded-xl bg-accent text-paper-raised py-2.5 min-h-[44px] text-sm font-semibold disabled:opacity-60"
            >
              Es un traslado entre mis cuentas ({seleccion.length})
            </button>
            <button
              onClick={() => decidir('real', seleccion)}
              disabled={guardando || seleccion.length === 0}
              className="rounded-xl border border-line py-2.5 min-h-[44px] text-sm font-semibold disabled:opacity-60"
            >
              No es un traslado
            </button>
          </div>
        </>
      )}
    </div>
  )
}
