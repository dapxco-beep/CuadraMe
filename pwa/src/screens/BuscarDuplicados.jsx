import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, CheckCircle2, CopyCheck } from 'lucide-react'
import { api } from '../lib/api'
import { useVolver } from '../lib/useVolver'
import { useCuentas } from '../lib/CuentasContext'
import { formatMoneda } from '../lib/format'
import { fechaHoraMovimiento, fechaDeMovimiento } from '../lib/fechaMovimiento'
import { ETIQUETA_CANAL } from '../lib/canales'
import { nombreDe } from '../lib/tituloMovimiento'
import { useDialogos } from '../lib/DialogosContext'

// «Buscar movimientos repetidos»: la app SUGIERE grupos de movimientos que parecen el mismo gasto
// llegado por canales distintos (a mano, atajo, correo, extracto). Tú eliges cuál conservar y se
// unen; nada se borra solo. Si eran compras iguales de verdad, «No es duplicado» y no vuelven a salir.
export default function BuscarDuplicados() {
  const volver = useVolver('/perfil')
  const { cuentas = [], recargar } = useCuentas() || {}
  const { confirmar, avisar } = useDialogos()
  const [grupos, setGrupos] = useState(null)
  const [error, setError] = useState('')
  const [elegido, setElegido] = useState({}) // id de grupo -> id del movimiento a conservar
  const [ocupado, setOcupado] = useState(null)

  const cargar = useCallback(async () => {
    setError('')
    try {
      const r = await api.buscarDuplicados()
      const lista = r?.grupos || []
      setGrupos(lista)
      setElegido((prev) => {
        const sig = { ...prev }
        lista.forEach((g) => {
          if (!sig[g.id]) sig[g.id] = g.sugerido_conservar
        })
        return sig
      })
    } catch (e) {
      setError(e.message || 'No pudimos buscar repetidos. Intenta de nuevo.')
      setGrupos([])
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function unir(g) {
    const conservar = elegido[g.id] || g.sugerido_conservar
    const otros = g.movimientos.filter((m) => m.id !== conservar).map((m) => m.id)
    const ok = await confirmar?.(
      `Se queda el que elegiste y ${otros.length === 1 ? 'el otro se elimina' : 'los otros se eliminan'}. El saldo de la cuenta se corrige solo.`,
      { titulo: 'Unir estos movimientos', confirmarTexto: 'Unir' },
    )
    if (ok === false) return
    setOcupado(g.id)
    try {
      await api.unirDuplicados(conservar, otros)
      setGrupos((l) => l.filter((x) => x.id !== g.id))
      recargar?.()
      avisar?.('Listo: quedó un solo movimiento', 'ok')
    } catch (e) {
      setError(e.message || 'No se pudo unir. Intenta de nuevo.')
    } finally {
      setOcupado(null)
    }
  }

  async function noEsDuplicado(g) {
    setOcupado(g.id)
    try {
      await api.noEsDuplicado(g.movimientos.map((m) => m.id))
      setGrupos((l) => l.filter((x) => x.id !== g.id))
    } catch (e) {
      setError(e.message || 'No se pudo guardar. Intenta de nuevo.')
    } finally {
      setOcupado(null)
    }
  }

  const nombreCuenta = (id, respaldo) => cuentas.find((c) => c.id === id)?.nombre || respaldo || ''

  return (
    <div className="flex-1 flex flex-col pb-10">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
        <button
          onClick={volver}
          className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Volver"
        >
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-semibold">Movimientos repetidos</h1>
      </header>

      <p className="px-5 text-sm text-ink-soft mt-1">
        A veces el mismo gasto entra por varios caminos (el atajo, el correo del banco, el extracto o lo que escribiste).
        Aquí te muestro los que parecen repetidos. Tú decides: no se borra nada solo.
      </p>

      {error && <p className="px-5 mt-3 text-sm text-danger" role="alert">{error}</p>}
      {grupos === null && <p className="px-5 mt-6 text-sm text-ink-soft">Buscando...</p>}

      {grupos && grupos.length === 0 && !error && (
        <p className="mx-5 mt-6 flex items-center gap-2 text-sm rounded-2xl bg-paper-raised border border-line px-4 py-4" data-testid="sin-duplicados">
          <CheckCircle2 size={20} className="text-cuadra shrink-0" aria-hidden="true" />
          No encontré movimientos repetidos. Todo en orden.
        </p>
      )}

      <ul className="px-5 mt-4 flex flex-col gap-4">
        {(grupos || []).map((g) => {
          const conservar = elegido[g.id] || g.sugerido_conservar
          return (
            <li key={g.id} className="rounded-2xl bg-paper-raised border border-line p-4" data-testid={`grupo-${g.id}`}>
              <p className="text-sm font-semibold flex items-center gap-1.5">
                <CopyCheck size={16} className="text-accent" aria-hidden="true" />
                Parece el mismo gasto, anotado {g.movimientos.length} veces
              </p>
              <fieldset className="mt-3">
                <legend className="text-xs text-ink-soft mb-2">¿Cuál quieres conservar?</legend>
                <div className="flex flex-col gap-2">
                  {g.movimientos.map((m) => (
                    <label
                      key={m.id}
                      className={`flex items-start gap-3 rounded-xl border px-3 py-2.5 cursor-pointer ${
                        conservar === m.id ? 'border-accent bg-accent-soft' : 'border-line'
                      }`}
                    >
                      <input
                        type="radio"
                        name={`g-${g.id}`}
                        checked={conservar === m.id}
                        onChange={() => setElegido((p) => ({ ...p, [g.id]: m.id }))}
                        className="mt-1"
                        aria-label={`Conservar ${m.descripcion}`}
                      />
                      <span className="flex-1 min-w-0">
                        <span className="block text-sm font-semibold break-words line-clamp-3">{nombreDe(m)}</span>
                        <span className="block text-xs text-ink-soft break-words">
                          {fechaHoraMovimiento(fechaDeMovimiento(m), { anio: true })}
                          {' · '}
                          {nombreCuenta(m.cuenta_id, m.cuenta_nombre)}
                          {' · '}
                          desde {ETIQUETA_CANAL[m.origen] || 'otro canal'}
                          {m.conciliado ? ' · cruzado con el banco' : ''}
                        </span>
                      </span>
                      <span className="text-sm font-bold shrink-0 whitespace-nowrap tabular-nums">{formatMoneda(m.monto)}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <div className="flex flex-col gap-2 mt-3">
                <button
                  onClick={() => unir(g)}
                  disabled={ocupado === g.id}
                  className="rounded-xl bg-ink text-paper py-2.5 min-h-[44px] text-sm font-semibold disabled:opacity-60"
                >
                  Unir en uno solo
                </button>
                <button
                  onClick={() => noEsDuplicado(g)}
                  disabled={ocupado === g.id}
                  className="rounded-xl border border-line py-2.5 min-h-[44px] text-sm font-semibold disabled:opacity-60"
                >
                  No es duplicado: son compras distintas
                </button>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
