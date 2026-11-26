import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, HandCoins } from 'lucide-react'
import { api } from '../../lib/api'
import { nombreDe } from '../../lib/tituloMovimiento'
import BarraProgreso from '../BarraProgreso'
import { Cambio, Panel, pctSimple } from './comun'

// De dónde entra tu plata: ingresos del periodo agrupados por quien/qué los paga (el texto del banco), con su peso y su
// cambio contra el periodo anterior. Tocar una fuente muestra los movimientos que la componen (con enlace al detalle).
const AYUDA =
  'Agrupamos tus ingresos por el nombre con el que llegan (por ejemplo «Nómina Empresa»). Las seis fuentes más grandes se ' +
  'muestran aparte y el resto se junta en «Otras fuentes». El cambio compara cada fuente con el periodo anterior; si antes ' +
  'no existía, dice «sin base». No incluye traslados entre tus cuentas.'

export default function IngresosFuente({ datos, fmt, paramsPeriodo }) {
  const [abierta, setAbierta] = useState(null)
  const [detalles, setDetalles] = useState({})

  function alternar(f) {
    if (abierta === f.clave) return setAbierta(null)
    setAbierta(f.clave)
    if (!detalles[f.clave]) {
      api.informeMovimientos({ ...paramsPeriodo, tipo: 'ingreso', fuente: f.clave })
        .then((d) => setDetalles((p) => ({ ...p, [f.clave]: d })))
        .catch(() => setDetalles((p) => ({ ...p, [f.clave]: { error: true, movimientos: [] } })))
    }
  }

  return (
    <Panel icono={HandCoins} titulo="Ingresos por fuente" pregunta="¿De dónde entra tu plata y de quién depende?" info={AYUDA}>
      {!datos.hay_datos ? (
        <p className="text-sm text-ink-soft">No registraste ingresos en este periodo.</p>
      ) : (
        <>
          <p className="text-sm">
            <span className="text-xl font-bold t-cifra t-display">{fmt(datos.total)}</span>
            <span className="text-xs text-ink-soft"> en total, de {datos.fuentes.length + (datos.otras?.cantidad || 0)} {datos.fuentes.length + (datos.otras?.cantidad || 0) === 1 ? 'fuente' : 'fuentes'}</span>
          </p>
          <ul className="mt-2 divide-y divide-line border-t border-line">
            {datos.fuentes.map((f) => {
              const det = detalles[f.clave]
              const abiertaAhora = abierta === f.clave
              return (
                <li key={f.clave}>
                  <button type="button" onClick={() => alternar(f)} aria-expanded={abiertaAhora} className="w-full text-left py-3 min-h-[56px]">
                    <div className="flex items-center gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium leading-tight break-words">{f.nombre}</p>
                        <BarraProgreso
                          pct={Math.max(f.pct, 1.5)}
                          label={`Peso de ${f.nombre}`}
                          className="h-1.5 rounded-full bg-line mt-1.5 overflow-hidden"
                          fillClass="rounded-full bg-cuadra"
                          color="var(--color-cuadra)"
                        />
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-sm font-semibold t-cifra">{fmt(f.monto)}</p>
                        <p className="text-[11px] text-ink-soft">{pctSimple(f.pct)} · <Cambio pct={f.variacion_pct} actual={f.monto} mejorSube /></p>
                      </div>
                      <ChevronDown size={16} className={`text-ink-soft shrink-0 transition-transform ${abiertaAhora ? 'rotate-180' : ''}`} aria-hidden="true" />
                    </div>
                  </button>
                  {abiertaAhora && (
                    <div className="pb-3">
                      {!det && <p className="text-xs text-ink-soft py-2">Cargando movimientos…</p>}
                      {det?.error && <p role="alert" className="text-xs text-danger py-2">No se pudieron cargar los movimientos.</p>}
                      {det && !det.error && (
                        <ul className="space-y-1" aria-label={`Movimientos de ${f.nombre}`}>
                          {det.movimientos.map((m) => (
                            <li key={m.id}>
                              <Link to={`/movimientos/${m.id}`} className="flex items-center justify-between gap-3 py-1.5 text-xs min-h-[44px]">
                                <span className="min-w-0">
                                  <span className="block font-medium truncate">{nombreDe(m)}</span>
                                  <span className="text-ink-soft">{m.fecha.slice(0, 10)}</span>
                                </span>
                                <span className="font-semibold shrink-0">{fmt(m.monto)}</span>
                              </Link>
                            </li>
                          ))}
                          {det.truncado && <li className="text-[11px] text-ink-soft">Se muestran los {det.movimientos.length} más recientes.</li>}
                        </ul>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
            {datos.otras && (
              <li className="py-3 min-h-[56px] flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">Otras fuentes ({datos.otras.cantidad})</p>
                  <p className="text-[11px] text-ink-soft">{datos.otras.num} {datos.otras.num === 1 ? 'movimiento' : 'movimientos'}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-sm font-semibold t-cifra">{fmt(datos.otras.monto)}</p>
                  <p className="text-[11px] text-ink-soft">{pctSimple(datos.otras.pct)}</p>
                </div>
                <span className="w-4 shrink-0" aria-hidden="true" />
              </li>
            )}
          </ul>
        </>
      )}
    </Panel>
  )
}
