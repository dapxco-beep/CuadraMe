import { CalendarCheck, Info } from 'lucide-react'
import { usePais } from '../lib/pais'
import { t } from '../lib/textosPais'

// Impuestos fuera de Colombia: solo información y un recordatorio. NO calculamos renta, 4x1000 ni
// deducibles de otro país (no hay un cálculo verificado con un contador local).
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

export default function ImpuestosInformativo() {
  const { pais, config } = usePais()
  const decl = config.impuestos.find((i) => i.id === 'declaracion_anual_informativa')
  const otros = config.impuestos.filter((i) => i.id !== 'declaracion_anual_informativa')
  const unidad = config.unidad_tributaria?.sigla ? config.unidad_tributaria : null
  return (
    <div className="px-5 mt-3 space-y-3" data-testid="impuestos-informativo">
      <div className="rounded-2xl bg-accent-soft p-3.5 flex gap-2.5" role="note">
        <Info size={16} className="text-accent shrink-0 mt-0.5" aria-hidden="true" />
        <p className="text-xs text-ink">{t('impuestos.aviso', pais)}</p>
      </div>
      <section className="rounded-2xl bg-paper-raised border border-line p-4" aria-label={t('impuestos.declaracion', pais)}>
        <h2 className="text-[15px] font-semibold flex items-center gap-2">
          <CalendarCheck size={20} aria-hidden="true" /> {t('impuestos.declaracion', pais)}
        </h2>
        <p className="text-sm mt-1.5">{t('impuestos.recordatorio', pais)}</p>
        {decl?.mes && <p className="text-xs text-ink-soft mt-1.5">Mes habitual: {MESES[decl.mes - 1]}.</p>}
      </section>
      {(otros.length > 0 || unidad) && (
        <section className="rounded-2xl bg-paper-raised border border-line p-4" aria-label="Otros datos">
          <h2 className="text-[15px] font-semibold">Para tener en cuenta</h2>
          <ul className="mt-1.5 space-y-1 text-sm">
            {unidad && <li>Unidad de referencia: {unidad.nombre} ({unidad.sigla}).</li>}
            {otros.map((i) => (
              <li key={i.id}>{i.nombre}</li>
            ))}
          </ul>
        </section>
      )}
      <p className="text-xs text-ink-soft">
        Calculadoras de renta y deducibles de {config.nombre}: todavía no. Por ahora te recordamos las fechas.
      </p>
    </div>
  )
}
