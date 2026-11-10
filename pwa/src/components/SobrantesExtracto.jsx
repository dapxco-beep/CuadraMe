import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useDialogos } from '../lib/DialogosContext'
import { useCuentas } from '../lib/CuentasContext'

// Movimientos TUYOS que el extracto no trae. Antes solo se listaban y no había cómo arreglarlos. Ahora cada uno se
// puede «dejar» (es real, p. ej. cae en otro extracto) o «borrar» (no existe o lo anotaste dos veces), y la decisión
// queda guardada en el servidor, así que no vuelve a avisar.
export default function SobrantesExtracto({ historialId, cuentaId = null, sobrantes, onCambio }) {
  const { confirmar, avisar } = useDialogos() || {}
  const { cuentas = [] } = useCuentas() || {}
  const otras = cuentas.filter((c) => c.id !== cuentaId)
  const [ocupado, setOcupado] = useState('')
  const [moviendo, setMoviendo] = useState(null) // id del movimiento al que se le está eligiendo otra cuenta
  const [destino, setDestino] = useState('')
  const pendientes = sobrantes.filter((s) => !s.resuelto)
  if (sobrantes.length === 0) return null

  // «Deshacer» una unión automática: el movimiento vuelve tal como estaba.
  async function deshacerUnion(s) {
    setOcupado('deshacer')
    try {
      await api.resolverSobrante(historialId, s.id, 'restaurar')
      onCambio(sobrantes.map((x) => (x.id === s.id ? { ...x, resuelto: 'dejado' } : x)))
    } catch (e) {
      avisar?.(e.message || 'No se pudo deshacer. Intenta de nuevo.')
    }
    setOcupado('')
  }

  async function resolver(s, accion) {
    return api.resolverSobrante(historialId, s.id, accion, 'no_va').then((r) => r?.resuelto || (accion === 'borrar' ? 'borrado' : 'dejado'))
  }

  async function actuar(lista, accion) {
    if (lista.length === 0) return
    if (accion === 'borrar' && confirmar) {
      const ok = await confirmar(
        lista.length === 1 ? `¿Borrar «${lista[0].descripcion}» (${formatCOP(lista[0].monto)})?` : `¿Borrar estos ${lista.length} movimientos?`,
        { confirmarTexto: 'Borrar', peligro: true },
      )
      if (!ok) return
    }
    setOcupado(accion)
    const hechos = new Map()
    try {
      for (const s of lista) hechos.set(s.id, await resolver(s, accion))
    } catch (e) {
      avisar?.(e.message || 'No se pudo guardar. Intenta de nuevo.')
    }
    setOcupado('')
    if (hechos.size) onCambio(sobrantes.map((s) => (hechos.has(s.id) ? { ...s, resuelto: hechos.get(s.id) } : s)))
  }

  // Lo más común con Apple Pay o el atajo: se anotó en la cuenta equivocada. Se pasa a la correcta y deja de sobrar aquí.
  async function mover(s) {
    if (!destino) return
    setOcupado('mover')
    try {
      await api.editarMovimiento(s.id, { cuenta_id: destino })
      await api.resolverSobrante(historialId, s.id, 'dejar', 'no_va').catch(() => {})
      const nombre = otras.find((c) => c.id === destino)?.nombre || 'la otra cuenta'
      onCambio(sobrantes.map((x) => (x.id === s.id ? { ...x, resuelto: `movido a ${nombre}` } : x)))
      setMoviendo(null)
      setDestino('')
    } catch (e) {
      avisar?.(e.message || 'No se pudo mover. Intenta de nuevo.')
    }
    setOcupado('')
  }

  const n = pendientes.length
  return (
    <details className="mt-2 rounded-2xl border border-line bg-paper px-3.5 py-2.5" open={n > 0 || sobrantes.some((s) => s.resuelto === 'unido')} data-testid="sobrantes-extracto">
      <summary className="text-xs font-semibold cursor-pointer min-h-[32px] flex items-center">
        {n === 0
          ? (sobrantes.some((s) => s.resuelto === 'unido') ? 'Unimos un movimiento repetido' : 'Revisaste los movimientos que el extracto no trae')
          : `${n} ${n === 1 ? 'movimiento tuyo no está' : 'movimientos tuyos no están'} en el extracto`}
      </summary>
      {n > 0 && (
        <p className="text-xs text-ink-soft mt-2">
          <b>Dejar</b> si es real (puede salir en otro extracto). <b>Borrar</b> si no existe o lo anotaste dos veces.
        </p>
      )}
      <ul className="mt-2 divide-y divide-line">
        {sobrantes.map((s) => (
          <li key={s.id || `${s.fecha}-${s.descripcion}-${s.monto}`} className="py-2.5" data-testid="sobrante">
            <div className="flex justify-between gap-2 text-xs">
              <span className="truncate">
                {s.id ? <Link to={`/movimientos/${s.id}`} className="underline">{s.fecha} · {s.descripcion}</Link> : `${s.fecha} · ${s.descripcion}`}
              </span>
              <span className="shrink-0 font-semibold">{formatCOP(s.monto)}</span>
            </div>
            {s.resuelto === 'unido' ? (
              <p className="mt-1 text-xs text-ink-soft flex items-center gap-1 flex-wrap">
                <Check size={16} aria-hidden="true" /> Estaba repetido: lo unimos con el del banco.
                <button type="button" disabled={!!ocupado} onClick={() => deshacerUnion(s)} className="min-h-11 px-2 font-semibold text-accent underline disabled:opacity-50">Deshacer</button>
              </p>
            ) : s.resuelto ? (
              <p className="mt-1 text-xs text-ink-soft flex items-center gap-1"><Check size={16} aria-hidden="true" /> {s.resuelto === 'borrado' ? 'Borrado' : s.resuelto?.startsWith('movido') ? `Movido a ${s.resuelto.slice("movido a ".length)}` : 'Se queda como está'}</p>
            ) : s.id ? (
              <div className="mt-1.5 flex gap-2">
                <button type="button" disabled={!!ocupado} onClick={() => actuar([s], 'dejar')} className="flex-1 min-h-11 rounded-xl border border-line text-sm font-semibold disabled:opacity-50">Dejar</button>
                <button type="button" disabled={!!ocupado} onClick={() => actuar([s], 'borrar')} className="flex-1 min-h-11 rounded-xl border border-line text-sm font-semibold text-danger disabled:opacity-50">Borrar</button>
                {otras.length > 0 && (
                  <button type="button" disabled={!!ocupado} onClick={() => { setMoviendo(moviendo === s.id ? null : s.id); setDestino('') }} className="flex-1 min-h-11 rounded-xl border border-line text-sm font-semibold disabled:opacity-50" aria-expanded={moviendo === s.id}>Otra cuenta</button>
                )}
              </div>
            ) : null}
            {moviendo === s.id && !s.resuelto && (
              <div className="mt-1.5 flex gap-2">
                <select value={destino} onChange={(e) => setDestino(e.target.value)} aria-label={`¿En qué cuenta fue ${s.descripcion}?`} className="flex-1 min-h-11 rounded-xl border border-line bg-paper px-3 text-sm">
                  <option value="">¿En qué cuenta fue?</option>
                  {otras.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                </select>
                <button type="button" disabled={!destino || !!ocupado} onClick={() => mover(s)} className="min-h-11 px-4 rounded-xl bg-ink text-paper text-sm font-semibold disabled:opacity-50">Mover</button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {n > 1 && (
        <div className="mt-1 flex gap-2">
          <button type="button" disabled={!!ocupado} onClick={() => actuar(pendientes.filter((s) => s.id), 'dejar')} className="flex-1 min-h-11 rounded-xl bg-ink text-paper text-sm font-semibold disabled:opacity-50">Dejar todos</button>
          <button type="button" disabled={!!ocupado} onClick={() => actuar(pendientes.filter((s) => s.id), 'borrar')} className="flex-1 min-h-11 rounded-xl border border-danger text-danger text-sm font-semibold disabled:opacity-50">Borrar todos</button>
        </div>
      )}
    </details>
  )
}
