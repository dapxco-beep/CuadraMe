import { fechaHoraMovimiento, fechaDeMovimiento } from '../lib/fechaMovimiento'
import { Link } from 'react-router-dom'
import { ArrowLeftRight, ChevronRight, Footprints } from 'lucide-react'
import { IlustracionVacia, Isotipo, Monto } from '../brand/Marca'
import ConsejoParaTi from './ConsejoParaTi'
import { OfrecerPrimeraMeta } from './FormMeta'
import Icono from './Icono'
import SemanaMini from './SemanaMini'
import { RenglonTuPlata } from './TuPlataTrabajando'
import { Boton } from './ui'
import { nombreDe } from '../lib/tituloMovimiento'
import { AccionesRapidas, AvisoNegativo, EsteMes, NoCargo } from './InicioExtras'
import QueSePuedeHacer from './QueSePuedeHacer'

// Inicio para quien llega sin saber de finanzas. A la vista: el saldo, los accesos y «Este mes».
//   - UNA sola guía a la vez: el camino de 3 pasos (lo pinta Inicio) o, sin camino, el siguiente paso o «¿Qué puedes hacer?».
//   - Con `mas` (el «Ver más» de Inicio) se suman lo reciente, el gasto por día, el consejo y las tarjetas informativas.
//   - `conAviso`: Inicio ya pinta los avisos (solo el más importante); sin él, esta pantalla muestra el de saldo negativo.
export default function InicioSimple({ saldo, gastosSemana, recientes, siguiente, fmt, iconoDe, cuadra = true, enCamino = false, cuentas = [], reporte = null, porDia = null, falloSaldo = false, onReintentar, mas = true, conAviso = true }) {
  const nuevo = recientes.length === 0
  const hayGuia = enCamino || !!siguiente
  return (
    <div data-testid="inicio-simple" className="dos-col dos-col-5-6">
     {/* En pantallas anchas: izquierda = saldo y acciones; derecha = el mes y lo reciente. En celular siguen en una sola columna, en el mismo orden. */}
     <div className="col">
      {/* BLOQUE 1 */}
      <section
        className="mx-6 mt-3 hero-marca card-marca relative overflow-hidden p-5 stagger-item"
        style={{ '--stagger-i': 0 }}
        aria-label="Cuánto tienes y qué pasó esta semana"
      >
        <Isotipo mono cuadra={cuadra} size={130} className="absolute -right-6 -bottom-8 opacity-[0.1]" />
        <div className="relative">
          <p className="t-kicker">Tienes disponible</p>
          <p className="text-[40px] t-display mt-2">
            <Monto texto={fmt(saldo)} />
          </p>
          <div className="mt-3 pt-3 border-t border-white/20">
            {porDia > 0 && (
              <p className="text-[11px] opacity-90 mb-2" data-testid="por-dia">
                Puedes gastar unos <b>{fmt(porDia)}</b> al día lo que queda del mes
              </p>
            )}
            <p className="text-[11px] opacity-90">Gastaste esta semana</p>
            <p className="text-lg font-bold t-cifra mt-0.5" data-testid="gastos-semana">
              {gastosSemana === null ? '—' : fmt(gastosSemana)}
            </p>
            {mas && <SemanaMini />}
          </div>
        </div>
      </section>

      {falloSaldo && <NoCargo onReintentar={onReintentar} className="mx-6 mt-2" />}
      {conAviso && <AvisoNegativo saldo={saldo} cuentas={cuentas} fmt={fmt} />}
      <AccionesRapidas />
     </div>
     <div className="col">
      <EsteMes reporte={reporte} fmt={fmt} iconoDe={iconoDe} />

      {/* Cuenta nueva con el camino de 3 pasos a la vista: el paso 2 ya dice «trae tus movimientos»; no repetirlo en otra tarjeta vacía */}
      {mas && !(enCamino && recientes.length === 0) && (
      <section className="mx-6 mt-3 tarjeta-lista" aria-label="Últimos movimientos">
        {recientes.length === 0 ? (
          <div className="px-4 py-4 text-center">
            <IlustracionVacia icono={ArrowLeftRight} size={80} />
            <p className="t-cuerpo font-semibold mt-3">Aún no tienes movimientos</p>
            <p className="t-apoyo mt-1">Cuando traigas o anotes alguno, lo verás aquí.</p>
          </div>
        ) : (
          <div className="divide-y divide-line">
            {recientes.map((m) => (
              <Link key={m.id} to={`/movimientos/${m.id}`} className="flex items-start gap-3 px-4 py-3 min-h-[56px]">
                <span className="w-10 h-10 rounded-full bg-accent-soft flex items-center justify-center text-lg shrink-0 text-accent" aria-hidden="true">
                  {m.tipo === 'transfer' ? <Icono icono={ArrowLeftRight} tam="md" /> : iconoDe(m.categoria)}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="t-cuerpo font-medium break-words line-clamp-4">{nombreDe(m)}</p>
                  <p className="t-apoyo break-words">{[fechaHoraMovimiento(fechaDeMovimiento(m)), m.tipo === 'transfer' ? 'Entre tus cuentas' : m.categoria].filter(Boolean).join(' · ')}</p>
                </div>
                <span className={`t-cuerpo font-semibold t-cifra shrink-0 whitespace-nowrap whitespace-nowrap ${m.tipo === 'income' ? 'text-accent' : 'text-ink'}`}>
                  {m.tipo === 'income' ? '+' : m.tipo === 'expense' ? '-' : ''}
                  {fmt(m.monto)}
                </span>
              </Link>
            ))}
          </div>
        )}
        {recientes.length > 0 && (
          <Link to="/movimientos" className="flex items-center justify-center gap-1 text-sm text-accent font-semibold py-2 min-h-11">
            Ver todos <Icono icono={ChevronRight} tam="sm" />
          </Link>
        )}
      </section>
      )}

      {/* BLOQUE 2 */}
      {siguiente && (
        <section className="mx-6 mt-3 tarjeta p-4" aria-label="Tu siguiente paso" data-testid="siguiente-paso" data-paso={siguiente.id}>
          <div className="flex items-start gap-3">
            <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
              <Icono icono={Footprints} tam="md" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="t-kicker text-ink-soft">Tu siguiente paso</p>
              <h2 className="t-h2 leading-snug">{siguiente.titulo}</h2>
              <p className="t-apoyo mt-0.5">{siguiente.apoyo}</p>
            </div>
          </div>
          <div className="mt-3">
            <Boton to={siguiente.ruta} state={siguiente.state} bloque>
              {siguiente.accion}
            </Boton>
          </div>
        </section>
      )}

      {/* «¿Qué puedes hacer?» solo cuando no hay otra guía a la vista */}
      {!hayGuia && <QueSePuedeHacer />}

      {/* Detrás de «Ver más»: cuánto ganó tu plata este mes, un consejo y la invitación a la primera meta */}
      {mas && !nuevo && <RenglonTuPlata />}
      {mas && !nuevo && <ConsejoParaTi max={1} />}
      {mas && !enCamino && <OfrecerPrimeraMeta className="mx-6 mt-2 flex justify-center" />}
     </div>
    </div>
  )
}
