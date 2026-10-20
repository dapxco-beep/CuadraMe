import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, Loader2, ShieldCheck, Undo2, X } from 'lucide-react'
import Hoja from './Hoja'
import Icono from './Icono'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { useCuentas } from '../lib/CuentasContext'
import { mensajeAmable } from '../lib/mensajes'
import {
  descartarAviso, etiquetaDetalle, iniciar, lineasConteo, textoListo, textoProgreso, textoSaldoCuenta, useAutoarreglo,
} from '../lib/autoarreglo'

/**
 * Aviso discreto (Inicio y Traer movimientos). La app ordena sola las cuentas; aquí se ve:
 *  - mientras trabaja: «Estoy ordenando tus cuentas… (2 de 6)» (no bloquea nada);
 *  - al terminar: lo que hizo, con «Ver qué hice» y «Deshacer»;
 *  - lo que necesita decisión de la persona (dudosas, varias tarjetas, clave del PDF), con una acción de un toque.
 * Se oculta solo cuando no hay nada que decir. Los botones manuales de siempre siguen existiendo como respaldo.
 */
export default function AvisoAutoarreglo({ className = '' }) {
  const navigate = useNavigate()
  const { recargar: recargarCuentas } = useCuentas() || {}
  const a = useAutoarreglo()
  const [hoja, setHoja] = useState(null) // null | { modo: 'detalle' | 'deshacer', lote } (el lote se guarda aquí: al deshacer el aviso se va, la hoja no)

  useEffect(() => { iniciar() }, [])

  const decisiones = a.decisiones || []
  if (a.fase === 'trabajando') {
    return (
      <p className={`mx-6 flex items-center gap-2 text-sm text-ink-soft ${className}`} role="status" data-testid="autoarreglo-trabajando">
        <Icono icono={Loader2} tam="sm" className="animate-spin" />
        <span>{textoProgreso(a.progreso)}</span>
      </p>
    )
  }
  const laHoja = hoja && (
    <DetalleAutoarreglo
      lote={hoja.lote} confirmando={hoja.modo === 'deshacer'} onCerrar={() => setHoja(null)}
      onDeshecho={async () => { descartarAviso(); await recargarCuentas?.(); window.dispatchEvent(new Event('cuadrame:movimientos-cambio')) }}
    />
  )
  const hayAviso = a.resultado || decisiones.length > 0

  // Un solo árbol estable: al deshacer el aviso se va y la hoja debe quedarse (con su mensaje) sin volver a montarse.
  return (
    <>
      {hayAviso && (
      <div className={`mx-6 flex flex-col gap-2 ${className}`} data-testid="autoarreglo">
        {a.resultado && (
          <div className="rounded-2xl bg-accent-soft p-3 text-sm" data-testid="autoarreglo-listo">
            <div className="flex items-start gap-2">
              <Icono icono={ShieldCheck} tam="md" className="mt-0.5 text-accent" />
              <p className="flex-1 font-semibold leading-snug text-accent">{textoListo(a.resultado)}</p>
              <button
                type="button" onClick={descartarAviso} aria-label="Cerrar aviso"
                className="-mr-1 -mt-1 flex min-h-11 min-w-11 items-center justify-center rounded-xl text-ink-soft"
              >
                <Icono icono={X} tam="sm" />
              </button>
            </div>
            <div className="mt-1 flex flex-wrap gap-2">
              <button
                type="button" onClick={() => setHoja({ modo: 'detalle', lote: a.resultado })}
                className="min-h-11 rounded-xl bg-accent px-4 text-sm font-semibold text-paper-raised"
              >
                Ver qué hice
              </button>
              <button
                type="button" onClick={() => setHoja({ modo: 'deshacer', lote: a.resultado })}
                className="flex min-h-11 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-ink-soft ring-1 ring-line/60"
              >
                <Icono icono={Undo2} tam="sm" />
                Deshacer
              </button>
            </div>
          </div>
        )}

        {decisiones.map((d) => (
          <button
            key={d.clave} type="button" onClick={() => navigate(d.ruta || '/sincronizacion')} data-testid={`autoarreglo-decision-${d.clave}`}
            className="flex min-h-11 w-full items-center gap-2 rounded-2xl bg-paper-raised p-3 text-left text-sm ring-1 ring-line/60"
          >
            <span className="flex-1 leading-snug">{d.texto}</span>
            <span className="flex items-center gap-1 font-semibold text-accent">
              {d.accion}
              <Icono icono={ChevronRight} tam="sm" />
            </span>
          </button>
        ))}

      </div>
      )}
      {laHoja}
    </>
  )
}

/** La hoja «Qué hice»: cuenta por cuenta, con los saldos de antes y de después, y «Deshacer». */
export function DetalleAutoarreglo({ lote: inicial, confirmando: pideConfirmar = false, onCerrar, onDeshecho }) {
  const bloqueo = useBloqueo() || {}
  const fmt = bloqueo.fmt || ((n) => `$${n}`)
  const [lote, setLote] = useState(inicial)
  const [confirmando, setConfirmando] = useState(pideConfirmar)
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState('')
  const [hecho, setHecho] = useState('')

  useEffect(() => {
    let vivo = true
    Promise.resolve(api.lotesAutoarreglo?.())
      .then((r) => { const l = (r?.lotes || []).find((x) => x.lote_id === inicial.lote_id); if (vivo && l) setLote(l) })
      .catch(() => {}) // con lo que ya traíamos alcanza
    return () => { vivo = false }
  }, [inicial.lote_id])

  async function deshacer() {
    setOcupado(true)
    setError('')
    try {
      const r = await api.deshacerLoteAutoarreglo(lote.lote_id)
      setHecho(r?.texto || 'Listo, tus cuentas quedaron como estaban.')
      setConfirmando(false)
      await onDeshecho?.()
    } catch (err) {
      setError(mensajeAmable(err?.message, { porDefecto: 'No pude deshacerlo ahora. No cambié nada; intenta de nuevo en un rato.' }))
    } finally {
      setOcupado(false)
    }
  }

  const lineas = lineasConteo(lote.contadores)
  return (
    <Hoja onCerrar={onCerrar} titulo="Qué hice">
      {({ cerrar }) => (
        <div data-testid="hoja-autoarreglo">
          <h2 className="text-lg font-bold">Qué hice</h2>
          <p className="mt-1 text-sm text-ink-soft">{hecho || textoListo(lote)}</p>

          {lineas.length > 0 && (
            <ul className="mt-3 flex flex-col gap-1 text-sm" data-testid="autoarreglo-conteo">
              {lineas.map((t) => <li key={t}>{t}</li>)}
            </ul>
          )}

          {(lote.cuentas || []).length > 0 && (
            <div className="mt-3 rounded-2xl bg-paper p-3 text-sm" data-testid="autoarreglo-saldos">
              <p className="font-semibold">Así cambiaron tus saldos</p>
              <ul className="mt-1 flex flex-col gap-0.5 text-ink-soft">
                {lote.cuentas.map((c) => <li key={c.cuenta_id}>{textoSaldoCuenta(c, fmt)}</li>)}
              </ul>
            </div>
          )}

          {(lote.detalle || []).length > 0 && (
            <details className="mt-3 text-sm">
              <summary className="min-h-11 cursor-pointer py-2.5 font-semibold">Ver cada cambio</summary>
              <ul className="flex flex-col gap-1.5" data-testid="autoarreglo-detalle">
                {lote.detalle.slice(0, 30).map((d, i) => (
                  <li key={`${d.tipo}-${i}`} className="flex justify-between gap-3">
                    <span className="min-w-0 truncate">{etiquetaDetalle(d)} · {d.descripcion}</span>
                    <span className="shrink-0 text-ink-soft">{fmt(Math.abs(d.monto || 0))}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}

          {error && <p className="mt-3 text-sm text-danger" role="alert">{error}</p>}

          {!hecho && confirmando && (
            <div className="mt-4 rounded-2xl bg-paper p-3 text-sm" data-testid="autoarreglo-confirmar">
              <p className="font-semibold">¿Deshacer todo lo que ordené?</p>
              <p className="mt-1 text-ink-soft">Tus cuentas quedan como estaban antes. Si ya cambiaste algo a mano, no toco nada y te lo digo.</p>
              <button
                type="button" disabled={ocupado} onClick={deshacer}
                className="mt-3 min-h-11 w-full rounded-xl bg-accent text-sm font-semibold text-paper-raised disabled:opacity-60"
              >
                {ocupado ? 'Un momento...' : 'Sí, deshacer'}
              </button>
              <button type="button" disabled={ocupado} onClick={() => setConfirmando(false)} className="mt-1 min-h-11 w-full text-sm font-semibold text-ink-soft">
                No, dejarlo así
              </button>
            </div>
          )}

          {!hecho && !confirmando && lote.deshacible !== false && (
            <button
              type="button" onClick={() => setConfirmando(true)}
              className="mt-4 flex min-h-11 w-full items-center justify-center gap-1.5 rounded-xl text-sm font-semibold text-ink-soft ring-1 ring-line/60"
            >
              <Icono icono={Undo2} tam="sm" />
              Deshacer
            </button>
          )}
          <button type="button" onClick={cerrar} className="mt-1 min-h-11 w-full text-sm font-semibold text-ink-soft">Cerrar</button>
        </div>
      )}
    </Hoja>
  )
}
