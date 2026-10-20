import { AlertTriangle, ArrowRightLeft, CalendarClock, Check, CircleDashed, CreditCard, Landmark, PencilLine, Wallet } from 'lucide-react'
import Icono from './Icono'
import { cuentasConExtracto, mesDeHoy, nombreCompleto, resumenMeses, tipoDeCuenta, vistaCelda } from '../lib/estadoPorCuenta'
import { nombreMes } from '../lib/sincronizacion'
import { textoCorte, textoFechasTarjeta } from '../lib/fechasTarjeta'
import DeudaTarjeta from './DeudaTarjeta'

// «Estado por cuenta y mes»: una tarjeta por cuenta con su nombre completo, qué tipo de cuenta es, cuántos meses
// están completos y una fila de meses (los últimos 6, con scroll hacia los anteriores). Cada mes dice su estado con
// ícono + palabras (el color nunca va solo) y, al tocarlo, abre la acción lógica: revisar, poner la clave, subir...
// Presentacional: la pantalla decide qué hace cada acción (`onMes(cuenta, celda, vista)`).

const ESTILO = {
  conciliado: { icono: Check, caja: 'bg-cuadra-soft border-cuadra/30 text-cuadra' },
  falta_importar: { icono: PencilLine, caja: 'bg-accent-soft border-accent/40 text-accent' },
  no_se_pudo_leer: { icono: AlertTriangle, caja: 'bg-danger-soft border-danger/40 text-danger' },
  falta_extracto: { icono: CircleDashed, caja: 'bg-paper border-line text-ink-soft' },
  otra_cuenta: { icono: ArrowRightLeft, caja: 'bg-accent-soft border-accent/40 text-accent' },
  en_curso: { icono: CalendarClock, caja: 'bg-transparent border-line text-ink-soft' },
  anterior: { icono: CircleDashed, caja: 'bg-transparent border-line/60 text-ink-soft/70' },
}

const ICONO_CUENTA = { credito: CreditCard, efectivo: Wallet }

function ChipMes({ cuenta, mes, celda, etiqueta, onMes }) {
  const v = vistaCelda(celda, { esMesActual: mes === mesDeHoy() })
  const e = ESTILO[v.clave] || ESTILO.falta_extracto
  const interactivo = v.accion !== 'ninguna'
  const corte = textoCorte(celda?.tarjeta_fechas)
  const Etiqueta = interactivo ? 'button' : 'div'
  return (
    <Etiqueta
      {...(interactivo ? { type: 'button', onClick: () => onMes?.(cuenta, celda, v) } : {})}
      aria-label={`${nombreCompleto(cuenta)}, ${nombreMes(mes)}: ${v.texto}${v.detalle ? `, ${v.detalle}` : ''}${corte ? `, ${corte}` : ''}`}
      data-testid={`mes-${cuenta.id}-${mes}`}
      data-estado={v.clave}
      className={`snap-start shrink-0 w-[104px] min-h-[76px] rounded-xl border px-2.5 py-2 text-left flex flex-col gap-0.5 ${e.caja}`}
    >
      <span className="text-[11px] font-semibold capitalize text-ink-soft">{etiqueta}</span>
      <span className="flex items-start gap-1 text-xs font-semibold leading-tight">
        <Icono icono={e.icono} tam="sm" className="mt-px" />
        <span>{v.texto}</span>
      </span>
      {v.detalle && <span className="text-[11px] leading-tight text-ink-soft">{v.detalle}</span>}
      {corte && <span className="text-[11px] leading-tight text-ink-soft">{corte}</span>}
    </Etiqueta>
  )
}

export default function EstadoPorCuenta({ cuentas = [], meses = [], onMes, pieCredito = null, deudas = null, className = '' }) {
  const lista = cuentasConExtracto(cuentas)
  if (!lista.length || !meses.length) return null
  const primeraTarjeta = lista.find((c) => c.tipo === 'credito')?.id // «Arreglar mis extractos de la tarjeta» va en la primera tarjeta
  return (
    <section aria-label="Estado por cuenta y mes" className={className} data-testid="estado-por-cuenta">
      <h2 className="text-sm font-semibold px-1">Tus cuentas, mes a mes</h2>
      <div className="mt-2 flex flex-col gap-2.5">
        {lista.map((c) => {
          const vistas = (c.meses || []).map((celda) => vistaCelda(celda, { esMesActual: celda.mes === mesDeHoy() }))
          const Cuenta = ICONO_CUENTA[c.tipo] || Landmark
          // Tarjeta: el corte y el límite de pago del extracto más reciente, bajo sus meses.
          const ultimaConFechas = c.tipo === 'credito' ? [...(c.meses || [])].reverse().find((x) => x.tarjeta_fechas) : null
          return (
            <article key={c.id} className="rounded-2xl bg-paper-raised ring-1 ring-line/60 p-3.5" aria-label={nombreCompleto(c)} data-testid={`cuenta-${c.id}`}>
              <header className="flex items-start gap-2.5">
                <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
                  <Icono icono={Cuenta} tam="md" />
                </span>
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold leading-snug break-words">
                    {c.nombre}<span className="font-normal text-ink-soft"> · {tipoDeCuenta(c)}</span>
                  </h3>
                </div>
                <p className="text-xs font-semibold text-ink-soft text-right shrink-0 max-w-[40%]" data-testid={`resumen-${c.id}`}>{resumenMeses(vistas)}</p>
              </header>
              <div
                role="list"
                aria-label={`Meses de ${nombreCompleto(c)}`}
                className="mt-3 flex gap-2 overflow-x-auto no-scrollbar snap-x pb-0.5"
                ref={(el) => {
                  // Se abre mirando lo más reciente; los meses anteriores quedan a la izquierda.
                  if (el && !el.dataset.listo) {
                    el.scrollLeft = el.scrollWidth
                    el.dataset.listo = '1'
                  }
                }}
              >
                {(c.meses || []).map((celda, i) => (
                  <div role="listitem" key={celda.mes} className="contents">
                    <ChipMes cuenta={c} mes={celda.mes} celda={celda} etiqueta={meses[i]?.etiqueta || celda.mes} onMes={onMes} />
                  </div>
                ))}
              </div>
              {c.tipo === 'credito' && deudas?.[c.id] && (
                <DeudaTarjeta vista={deudas[c.id]} moneda={c.moneda} className="mt-3 rounded-xl bg-paper p-3" />
              )}
              {ultimaConFechas && !deudas?.[c.id]?.corte && (
                <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-soft" data-testid={`fechas-tarjeta-${c.id}`}>
                  <Icono icono={CalendarClock} tam="sm" />
                  <span>{textoFechasTarjeta(ultimaConFechas.tarjeta_fechas)}</span>
                </p>
              )}
              {pieCredito && c.id === primeraTarjeta && <div className="mt-3">{pieCredito}</div>}
            </article>
          )
        })}
      </div>
    </section>
  )
}
