import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Gauge, TriangleAlert } from 'lucide-react'
import BarraProgreso from '../BarraProgreso'
import { Panel, conSigno, pctSimple } from './comun'

// Presupuesto contra lo que de verdad gastaste en el periodo. El presupuesto del periodo es el límite mensual repartido
// por días (informe_resumen.presupuesto_vs_real). Cada estado lleva icono y palabra: el color nunca va solo.
const ESTADOS = {
  dentro: { Icono: CheckCircle2, texto: 'Dentro del límite', clase: 'text-cuadra', barra: 'var(--color-cuadra)' },
  cerca: { Icono: TriangleAlert, texto: 'Cerca del límite', clase: 'text-gold', barra: 'var(--color-accent-2)' },
  excedido: { Icono: AlertTriangle, texto: 'Superado', clase: 'text-danger', barra: 'var(--color-danger)' },
  sin_limite: { Icono: CheckCircle2, texto: 'Sin límite', clase: 'text-ink-soft', barra: 'var(--color-line)' },
}
const AYUDA =
  'Comparamos lo que gastaste en cada categoría con su presupuesto. El presupuesto de un periodo es el límite de cada mes ' +
  'repartido por días: un mes completo es un límite entero, tres meses son tres límites y medio mes es medio límite. Los ' +
  'presupuestos quincenales o semanales se pasan a su equivalente mensual. «Disponible» es lo que te queda (negativo si te pasaste). Se usa el límite actual de cada presupuesto aunque lo hayas cambiado o creado hace poco, y meses de calendario (no tu periodo de pago).'

export default function PresupuestoReal({ datos, fmt, parametrosMov = '' }) {
  return (
    <Panel icono={Gauge} titulo="Presupuesto vs. gasto real" pregunta="¿Estás gastando lo que planeaste?" info={AYUDA}>
      {!datos.hay_presupuestos ? (
        <div>
          <p className="text-sm text-ink-soft">Todavía no tienes presupuestos. Con uno por categoría verás aquí si te estás pasando.</p>
          <Link to="/presupuesto" className="inline-flex items-center min-h-11 text-sm font-semibold text-accent">Crear un presupuesto</Link>
        </div>
      ) : (
        <>
          <div>
            <div className="flex items-end justify-between gap-3">
              <p className="text-sm">
                <span className="text-xl font-bold t-cifra t-display">{fmt(datos.gastado_total)}</span>
                <span className="text-xs text-ink-soft"> de {fmt(datos.presupuesto_total)}</span>
              </p>
              <p className={`text-xs font-semibold ${datos.disponible_total < 0 ? 'text-danger' : 'text-ink-soft'}`}>
                {datos.disponible_total < 0 ? `Te pasaste ${fmt(-datos.disponible_total)}` : `Te quedan ${fmt(datos.disponible_total)}`}
              </p>
            </div>
            {datos.pct_total !== null && (
              <BarraProgreso
                pct={Math.min(datos.pct_total, 100)}
                label={`Presupuesto total usado: ${pctSimple(datos.pct_total)}`}
                className="h-2 rounded-full bg-line mt-2 overflow-hidden"
                fillClass="rounded-full"
                color={datos.pct_total >= 100 ? 'var(--color-danger)' : 'var(--color-brand)'}
              />
            )}
            <p className="text-[11px] text-ink-soft mt-1">{pctSimple(datos.pct_total)} del presupuesto del periodo</p>
          </div>

          <ul className="mt-2 divide-y divide-line border-t border-line">
            {datos.categorias.map((c) => {
              const e = ESTADOS[c.estado] || ESTADOS.dentro
              return (
                <li key={c.categoria}>
                  <Link
                    to={`/movimientos?cat=${encodeURIComponent(c.categoria)}&tipo=expense&${parametrosMov}`}
                    className="block py-3 min-h-[56px]"
                    aria-label={`${c.categoria}: gastaste ${fmt(c.gastado)} de ${fmt(c.presupuesto)}, ${e.texto}. Ver movimientos`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium truncate">{c.categoria}</p>
                      <p className="text-sm font-semibold t-cifra shrink-0">{fmt(c.gastado)} <span className="text-xs font-normal text-ink-soft">de {fmt(c.presupuesto)}</span></p>
                    </div>
                    <BarraProgreso
                      pct={Math.min(c.pct ?? 0, 100)}
                      label={`${c.categoria}: ${pctSimple(c.pct)} del presupuesto`}
                      className="h-1.5 rounded-full bg-line mt-1.5 overflow-hidden"
                      fillClass="rounded-full"
                      color={e.barra}
                    />
                    <div className="mt-1 flex items-center justify-between gap-2 text-[11px]">
                      <span className={`inline-flex items-center gap-1 font-semibold ${e.clase}`}>
                        <e.Icono size={13} aria-hidden="true" />{e.texto} · {pctSimple(c.pct)}
                      </span>
                      <span className="text-ink-soft">{c.disponible >= 0 ? 'Disponible' : 'Excedido'} {conSigno(c.disponible, fmt).replace(/^[+−]/, '')}</span>
                    </div>
                  </Link>
                </li>
              )
            })}
          </ul>
          <p className="text-xs text-ink-soft mt-2 leading-relaxed">
            {datos.gasto_sin_presupuesto > 0 && `Además gastaste ${fmt(datos.gasto_sin_presupuesto)} en categorías sin presupuesto. `}
            Presupuesto del periodo = {String(datos.meses_equivalentes).replace('.', ',')} {datos.meses_equivalentes === 1 ? 'mes' : 'meses'} de límite
            (meses de calendario, con el límite que tienes hoy en cada categoría: no guardamos la historia de tus cambios).
          </p>
        </>
      )}
    </Panel>
  )
}
