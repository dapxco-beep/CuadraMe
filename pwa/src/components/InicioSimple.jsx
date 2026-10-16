import { fechaHoraMovimiento, fechaDeMovimiento } from '../lib/fechaMovimiento'
import { Link } from 'react-router-dom'
import { ArrowLeftRight, ChevronRight, Footprints } from 'lucide-react'
import { IlustracionVacia, Isotipo, Monto } from '../brand/Marca'
import ConsejoParaTi from './ConsejoParaTi'
import { OfrecerPrimeraMeta } from './FormMeta'
import Icono from './Icono'
import { RenglonTuPlata } from './TuPlataTrabajando'
import { Boton } from './ui'

// Inicio para quien llega sin saber de finanzas: tres bloques y nada más.
//   1. Cuánto tienes y qué pasó esta semana (saldo, gastos de la semana, 3 últimos movimientos)
//   2. UN siguiente paso claro (si el camino de 3 pasos está en pantalla, él ya cumple ese papel)
//   3. Un consejo para ti
export default function InicioSimple({ saldo, gastosSemana, recientes, siguiente, fmt, iconoDe, cuadra = true, enCamino = false }) {
  return (
    <div data-testid="inicio-simple">
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
            <p className="text-[11px] opacity-90">Gastaste esta semana</p>
            <p className="text-lg font-bold t-cifra mt-0.5" data-testid="gastos-semana">
              {gastosSemana === null ? '—' : fmt(gastosSemana)}
            </p>
          </div>
        </div>
      </section>

      {/* Cuenta nueva con el camino de 3 pasos a la vista: el paso 2 ya dice «trae tus movimientos»; no repetirlo en otra tarjeta vacía */}
      {!(enCamino && recientes.length === 0) && (
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
                  <p className="t-cuerpo font-medium break-words line-clamp-4">{m.descripcion}</p>
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

      {/* Solo si ya tienes cajitas: cuánto ganó tu plata este mes */}
      <RenglonTuPlata />

      {/* BLOQUE 3 */}
      <ConsejoParaTi max={1} />
      {!enCamino && <OfrecerPrimeraMeta className="mx-6 mt-2 flex justify-center" />}
    </div>
  )
}
