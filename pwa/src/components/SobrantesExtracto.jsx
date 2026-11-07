import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { useDialogos } from '../lib/DialogosContext'

// Movimientos TUYOS que el extracto no trae. Antes solo se listaban y no había cómo arreglarlos. Ahora cada uno se
// puede «dejar» (es real, p. ej. cae en otro extracto) o «borrar» (no existe o lo anotaste dos veces), y la decisión
// queda guardada en el servidor, así que no vuelve a avisar.
export default function SobrantesExtracto({ historialId, sobrantes, onCambio }) {
  const { confirmar, avisar } = useDialogos() || {}
  const [ocupado, setOcupado] = useState('')
  const pendientes = sobrantes.filter((s) => !s.resuelto)
  if (sobrantes.length === 0) return null

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

  const n = pendientes.length
  return (
    <details className="mt-2 rounded-2xl border border-line bg-paper px-3.5 py-2.5" open={n > 0} data-testid="sobrantes-extracto">
      <summary className="text-xs font-semibold cursor-pointer min-h-[32px] flex items-center">
        {n === 0
          ? 'Revisaste los movimientos que el extracto no trae'
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
            {s.resuelto ? (
              <p className="mt-1 text-xs text-ink-soft flex items-center gap-1"><Check size={16} aria-hidden="true" /> {s.resuelto === 'borrado' ? 'Borrado' : 'Se queda como está'}</p>
            ) : s.id ? (
              <div className="mt-1.5 flex gap-2">
                <button type="button" disabled={!!ocupado} onClick={() => actuar([s], 'dejar')} className="flex-1 min-h-11 rounded-xl border border-line text-sm font-semibold disabled:opacity-50">Dejar</button>
                <button type="button" disabled={!!ocupado} onClick={() => actuar([s], 'borrar')} className="flex-1 min-h-11 rounded-xl border border-line text-sm font-semibold text-danger disabled:opacity-50">Borrar</button>
              </div>
            ) : null}
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
