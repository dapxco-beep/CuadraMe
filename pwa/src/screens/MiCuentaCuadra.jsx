import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, Check, ChevronRight, Scale } from 'lucide-react'
import { EsqueletoLista } from '../components/Esqueletos'
import Icono from '../components/Icono'
import { EstadoVacio } from '../brand/Marca'
import { useVolver } from '../lib/useVolver'
import { iniciar, textoProgreso, useAutoarreglo } from '../lib/autoarreglo'
import { resumenCuadre, vistasCuadre } from '../lib/miCuentaCuadra'

// «Mi cuenta cuadra»: un semáforo por cuenta con lo que dejó el autoarreglo (no calcula nada aquí).
// Verde = cuadra todos los meses; ámbar = el mes en que deja de cuadrar y el motivo en una frase. Tocar abre el detalle.
// El color nunca va solo: cada fila lleva ícono y palabras.
const ESTILO = {
  cuadra: { icono: Check, caja: 'bg-cuadra-soft text-cuadra', etiqueta: 'Cuadra' },
  no_cuadra: { icono: AlertTriangle, caja: 'bg-accent-soft text-accent', etiqueta: 'No cuadra' },
}

export default function MiCuentaCuadra() {
  const volver = useVolver('/')
  const navigate = useNavigate()
  const a = useAutoarreglo()
  const [intento, setIntento] = useState(0) // sube al reintentar
  const [fallo, setFallo] = useState(false)

  useEffect(() => {
    let vivo = true
    setFallo(false)
    iniciar({ forzar: intento > 0 }).then((e) => { if (vivo && e.fase !== 'listo') setFallo(true) })
    return () => { vivo = false }
  }, [intento])

  const vistas = vistasCuadre(a.cuadre)
  const cargando = a.fase !== 'listo' && !fallo

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter pantalla-ancha">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button type="button" onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Mi cuenta cuadra</h1>
      </header>
      <p className="px-6 text-sm text-ink-soft">Así van tus bancos y tarjetas frente a sus extractos, mes a mes.</p>

      {cargando && (
        <div className="mx-6 mt-4">
          {a.fase === 'trabajando' && <p role="status" className="mb-3 text-sm text-ink-soft">{textoProgreso(a.progreso)}</p>}
          <EsqueletoLista filas={3} etiqueta="Revisando tus cuentas" />
        </div>
      )}

      {fallo && (
        <div className="mx-6 mt-4 text-sm" role="alert">
          <p className="text-danger">No pude revisar tus cuentas ahora. No cambié nada.</p>
          <button type="button" onClick={() => setIntento((n) => n + 1)} className="mt-2 min-h-11 rounded-xl px-4 font-semibold ring-1 ring-line/60">
            Intentar de nuevo
          </button>
        </div>
      )}

      {!cargando && !fallo && vistas.length === 0 && (
        <EstadoVacio
          icono={Scale}
          titulo="Aún no hay nada que comparar"
          texto="Cuando traigas el extracto de un banco o una tarjeta, aquí verás si tu cuenta cuadra mes a mes."
          className="mx-6 mt-6"
        >
          <button type="button" onClick={() => navigate('/sincronizacion')} className="mt-3 min-h-11 rounded-xl bg-accent px-4 text-sm font-semibold text-paper-raised">
            Traer extractos
          </button>
        </EstadoVacio>
      )}

      {!cargando && vistas.length > 0 && (
        <>
          <p className="mx-6 mt-4 text-sm font-semibold" role="status" data-testid="resumen-cuadre">{resumenCuadre(vistas)}</p>
          <ul className="mx-6 mt-2 flex flex-col gap-2.5">
            {vistas.map((v) => {
              const e = ESTILO[v.estado]
              return (
                <li key={v.id || v.nombre}>
                  <button
                    type="button" onClick={() => navigate(v.ruta)} data-testid={`cuadre-${v.id}`} data-estado={v.estado}
                    className="card-marca flex min-h-14 w-full items-center gap-3 border border-line bg-paper-raised p-3 text-left"
                  >
                    <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${e.caja}`}>
                      <Icono icono={e.icono} tam="sm" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold">{v.nombre}</span>
                      <span className={`block text-sm font-semibold ${v.estado === 'cuadra' ? 'text-cuadra' : 'text-accent'}`}>
                        <span className="sr-only">{e.etiqueta}: </span>{v.titulo}
                      </span>
                      {v.detalle && <span className="mt-0.5 block text-xs leading-snug text-ink-soft">{v.detalle}</span>}
                    </span>
                    <Icono icono={ChevronRight} tam="sm" className="shrink-0 text-ink-soft" />
                  </button>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </div>
  )
}
