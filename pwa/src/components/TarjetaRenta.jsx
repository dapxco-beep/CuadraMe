import { useEffect, useState } from 'react'
import { AlertTriangle, CalendarClock, CheckCircle2, CircleHelp, Download, ExternalLink } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { ENLACE_DIAN, ESTADO_RENTA, cuentaAtras, pctBarra } from '../lib/renta'
import { useDialogos } from '../lib/DialogosContext'
import BarraProgreso from './BarraProgreso'
import Ayudita from './Ayudita'
import Icono from './Icono'

const ICONO_RESULTADO = { si: AlertTriangle, cerca: AlertTriangle, no: CheckCircle2, no_se_sabe: CircleHelp }
const AYUDITA = { patrimonio_bruto: 'patrimonio-bruto', consignaciones: 'consignaciones' }

/**
 * «¿Tengo que declarar renta?»: los cinco topes de la DIAN frente a lo que la persona cargó.
 * Informativo (no es asesoría tributaria). Si el servidor falla, muestra un aviso corto y la pantalla sigue.
 */
export default function TarjetaRenta() {
  const { avisar } = useDialogos()
  const [r, setR] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let activo = true
    Promise.resolve()
      .then(() => api.rentaEstimada())
      .then((d) => activo && setR(d))
      .catch(() => activo && setError(true))
    return () => {
      activo = false
    }
  }, [])

  async function descargar() {
    try {
      await api.rentaResumenCsv(r.anio)
    } catch {
      avisar('No pudimos descargar el resumen. Revisa tu conexión e intenta de nuevo.')
    }
  }

  if (error) return <p className="px-5 mt-5 text-sm text-ink-soft">No pudimos calcular si te toca declarar. Intenta de nuevo en un rato.</p>
  if (!r) return null
  const res = r.resultado
  const IconoRes = ICONO_RESULTADO[res.clave] || CircleHelp

  return (
    <section className="px-5 mt-5" aria-label="¿Tengo que declarar renta?" data-testid="tarjeta-renta">
      <h2 className="text-[15px] font-semibold mb-1">¿Tengo que declarar renta?</h2>
      <p className="text-xs text-ink-soft mb-3">Renta del año {r.anio}: lo que la DIAN revisa para saber si te toca.</p>
      <div className="rounded-2xl bg-paper-raised border border-line p-4">
        <div className="flex items-start gap-3">
          <span className="w-10 h-10 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
            <Icono icono={IconoRes} tam="lg" />
          </span>
          <div className="min-w-0">
            <p className="text-base font-semibold" role="status">{res.titulo}</p>
            <p className="text-xs text-ink-soft mt-0.5">{res.detalle}</p>
          </div>
        </div>

        {r.plazo && (
          <p className="mt-3 text-sm font-medium flex items-center gap-2" data-testid="renta-plazo">
            <Icono icono={CalendarClock} tam="sm" className="text-accent" />
            {cuentaAtras(r.plazo)}
          </p>
        )}

        <ul className="mt-4 space-y-3.5" aria-label="Topes para declarar renta">
          {r.criterios.map((c) => {
            const e = ESTADO_RENTA[c.estado] || ESTADO_RENTA.sin_datos
            return (
              <li key={c.id}>
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className="font-medium inline-flex items-center">
                    {c.nombre}
                    {AYUDITA[c.id] && <Ayudita termino={AYUDITA[c.id]} />}
                  </span>
                  <span className="text-xs font-semibold shrink-0">{e.etiqueta}</span>
                </div>
                <BarraProgreso
                  pct={c.estado === 'sin_datos' && !c.valor ? 0 : pctBarra(c)}
                  color={e.color}
                  label={`${c.nombre}: ${c.pct} % del tope`}
                  texto={`${c.pct} % del tope, ${e.etiqueta}`}
                  className="h-2 rounded-full bg-line overflow-hidden mt-1.5"
                />
                <p className="text-xs text-ink-soft mt-1">
                  {formatCOP(c.valor)} de {formatCOP(c.tope)} ({String(c.pct).replace('.', ',')} %)
                </p>
                {c.nota && <p className="text-[11px] text-ink-soft mt-0.5">{c.nota}</p>}
              </li>
            )
          })}
        </ul>

        <details className="mt-4 text-xs text-ink-soft">
          <summary className="min-h-11 flex items-center cursor-pointer font-medium text-ink">Qué cuenta y qué no ve CuadraMe</summary>
          <p className="mb-1.5">
            Los topes son en UVT (la medida de la DIAN; en {r.anio} una UVT vale {formatCOP(r.uvt)}). Si superas <b>cualquiera</b> de los cinco,
            probablemente te toca declarar. Las consignaciones incluyen la plata que pasas entre tus propias cuentas, por eso
            pueden ser más que tus ingresos.
          </p>
          <ul className="list-disc pl-4 space-y-0.5">
            {r.limites.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </details>

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 no-print">
          <button
            type="button"
            onClick={descargar}
            className="min-h-11 rounded-xl border border-line bg-paper px-3.5 text-sm font-semibold inline-flex items-center gap-2"
          >
            <Icono icono={Download} tam="sm" /> Descargar resumen para mi declaración
          </button>
          <a
            href={ENLACE_DIAN}
            target="_blank"
            rel="noopener noreferrer"
            className="min-h-11 inline-flex items-center gap-1.5 text-sm text-accent font-medium"
          >
            Ir a la DIAN <Icono icono={ExternalLink} tam="sm" />
          </a>
        </div>
        <p className="text-[11px] text-ink-soft mt-1">{r.aviso} Orientación educativa, no es asesoría tributaria.</p>
      </div>
    </section>
  )
}
