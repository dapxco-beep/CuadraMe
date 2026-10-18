import { useMemo, useState } from 'react'
import { AlertTriangle, CalendarX2, CheckCircle2, ChevronDown, FileSearch, Inbox, KeyRound, Paperclip, Scale, Search } from 'lucide-react'
import Icono from './Icono'
import {
  ESTADOS_VISTA, TEXTO_ACCION, agruparPorMes, estadoVista, filtrar, opcionesCuenta, textoAccion, textoContadores,
} from '../lib/extractosVista'
import { textoSugerencia } from '../lib/cambiarCuenta'
import BotonReleer from './BotonReleer'

const ICONO_ESTADO = {
  revisado: CheckCircle2,
  por_revisar: FileSearch,
  necesita_clave: KeyRound,
  no_se_pudo_leer: AlertTriangle,
  sin_procesar: Inbox,
  anterior_al_inicio: CalendarX2,
}

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

// Los últimos 24 meses (el actual primero) para el selector «¿De qué mes es?».
export function ultimosMeses(n = 24, hoy = new Date()) {
  const salida = []
  let a = hoy.getFullYear()
  let m = hoy.getMonth()
  for (let i = 0; i < n; i += 1) {
    salida.push({ clave: `${a}-${String(m + 1).padStart(2, '0')}`, texto: `${MESES[m][0].toUpperCase()}${MESES[m].slice(1)} ${a}` })
    m -= 1
    if (m < 0) {
      m = 11
      a -= 1
    }
  }
  return salida
}

function EtiquetaEstado({ id, texto }) {
  const e = estadoVista(id)
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${e.fondo} ${e.clase}`} data-estado={id}>
      <Icono icono={ICONO_ESTADO[id]} tam="sm" />
      {texto || e.texto}
    </span>
  )
}

function SelectorMes({ it, onFijarMes, ocupado }) {
  const [valor, setValor] = useState('')
  const meses = useMemo(() => ultimosMeses(), [])
  return (
    <div className="mt-2 flex flex-wrap items-end gap-2">
      <label className="text-xs text-ink-soft flex flex-col gap-1">
        ¿De qué mes es este extracto?
        <select
          value={valor}
          onChange={(e) => setValor(e.target.value)}
          className="min-h-11 rounded-xl border border-line bg-paper px-3 text-sm text-ink"
        >
          <option value="">Elige el mes</option>
          {meses.map((m) => <option key={m.clave} value={m.clave}>{m.texto}</option>)}
        </select>
      </label>
      <button
        type="button"
        disabled={!valor || ocupado}
        onClick={() => onFijarMes(it, valor)}
        aria-label={`Guardar el mes de ${it.titulo}`}
        className="min-h-11 rounded-xl bg-accent text-paper-raised text-xs font-semibold px-3.5 disabled:opacity-50"
      >
        Guardar mes
      </button>
    </div>
  )
}

function FilaExtractoVista({ it, onAccion, onFijarMes, ocupado, releyendo = false, resultadoReleer = null }) {
  const [cambiandoMes, setCambiandoMes] = useState(false)
  const esError = it.estado_vista === 'no_se_pudo_leer'
  // Los subidos a mano sin nombre guardado no aportan («Subido a mano» ya sale en el origen): solo se listan nombres reales.
  const nombresEjemplo = [...new Set((it.ejemplos || []).map((x) => x.nombre).filter((n) => n && n !== 'Subido a mano'))]
  return (
    <li className="px-4 py-3.5" data-testid={`ext-${it.id}`} data-estado={it.estado_vista}>
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-base font-semibold leading-snug break-words">{it.titulo}</h4>
        {it.copias_texto && (
          <span className="shrink-0 rounded-full bg-paper border border-line px-2 py-0.5 text-[11px] font-semibold text-ink-soft" title="Es el mismo extracto: se cuenta una sola vez">
            {it.copias_texto}
          </span>
        )}
      </div>
      <p className="mt-1.5 flex flex-wrap items-center gap-1.5">
        <EtiquetaEstado id={it.estado_vista} texto={it.estado_etiqueta} />
        {it.cuadre && (
          <span data-testid="insignia-cuadre" data-cuadre={it.cuadre.estado}
            className={`inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs font-semibold ${it.cuadre.estado === 'cuadra' ? 'text-cuadra' : it.cuadre.estado === 'sin_saldo' ? 'text-ink-soft' : 'text-accent'}`}>
            <Icono icono={it.cuadre.estado === 'cuadra' ? CheckCircle2 : it.cuadre.estado === 'sin_saldo' ? Scale : AlertTriangle} tam="sm" />
            {it.cuadre.texto}
          </span>
        )}
      </p>
      {/* Nada sin nombre ni origen: de dónde salió y a qué cuenta quedó. */}
      {(it.origen_texto || it.cuenta_asignada) && (
        <p className="text-xs text-ink-soft mt-1.5 break-words" data-testid="origen-extracto">
          {it.origen_texto}{it.origen_texto && it.cuenta_asignada ? ' · ' : ''}{it.cuenta_asignada ? `En la cuenta ${it.cuenta_asignada}` : ''}
        </p>
      )}
      {esError && nombresEjemplo.length > 0 && (it.copias > 1 || it.banco_sin_identificar) && (
        <p className="text-xs text-ink-soft mt-1 break-words" data-testid="ejemplos-extracto">
          {it.copias > 1 ? 'Por ejemplo: ' : 'Archivo: '}{nombresEjemplo.join(' · ')}
        </p>
      )}
      {it.estado_corto && !(esError && it.mes_por_confirmar && it.copias > 1) && <p className={`text-sm font-semibold mt-1.5 ${esError ? 'text-danger' : ''}`} data-testid="estado-corto">{it.estado_corto}</p>}
      {it.lectura_dudosa > 0 && (
        <p className="text-sm mt-1.5 text-accent font-semibold" data-testid="aviso-lectura-dudosa">
          {it.lectura_dudosa === 1 ? '1 línea trae dos montos: elige el correcto al revisarla.' : `${it.lectura_dudosa} líneas traen dos montos: elige el correcto al revisarlas.`}
        </p>
      )}
      <p className={`text-sm mt-1.5 leading-snug ${esError ? 'text-danger' : 'text-ink-soft'}`} role={esError ? 'alert' : undefined}>{it.resultado}</p>
      {it.mes_deducido && !it.mes_por_confirmar && (
        <p className="text-xs text-ink-soft mt-1">
          Mes deducido de la fecha del correo.
          {it.puede_fijar_mes && (
            <button type="button" onClick={() => setCambiandoMes((v) => !v)} className="ml-1 underline font-semibold text-accent min-h-8">
              {cambiandoMes ? 'Dejarlo así' : 'Cambiar mes'}
            </button>
          )}
        </p>
      )}
      {it.mes_por_confirmar && !it.puede_fijar_mes && (
        <p className="text-xs text-ink-soft mt-1">No encontramos de qué mes es. Si lo subes de nuevo, lo deducimos de sus movimientos.</p>
      )}
      {((it.mes_por_confirmar && it.puede_fijar_mes) || cambiandoMes) && <SelectorMes it={it} onFijarMes={onFijarMes} ocupado={ocupado} />}
      {textoSugerencia(it) && (
        <div className="mt-2 rounded-xl bg-accent-soft px-3 py-2.5" data-testid="sugerencia-cuenta">
          <p className="text-sm leading-snug">{textoSugerencia(it)}</p>
          <button
            type="button"
            disabled={ocupado}
            onClick={() => onAccion('cambiar_cuenta', it, it.sugerencia_cuenta.cuenta_id)}
            aria-label={`Pasar a ${it.sugerencia_cuenta.nombre}: ${it.titulo}`}
            className="min-h-11 text-xs font-semibold text-accent"
          >
            Pasarlo a {it.sugerencia_cuenta.nombre}
          </button>
        </div>
      )}
      {it.acciones?.includes('releer') && (
        <BotonReleer onReleer={() => onAccion('releer', it)} ocupado={releyendo} resultado={resultadoReleer} nombre={it.titulo} />
      )}
      {(it.acciones?.length > 0 || it.puede_cambiar_cuenta) && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
          {(it.acciones || []).filter((a) => a !== 'releer').map((a, i) => (
            <button
              key={a}
              type="button"
              disabled={ocupado && a !== 'mi_banco_no_esta'}
              onClick={() => onAccion(a, it)}
              aria-label={`${textoAccion(a, it)}: ${it.titulo}`}
              className={`min-h-11 text-xs font-semibold disabled:opacity-50 ${i === 0 && a !== 'ver' ? 'text-accent' : 'text-ink-soft'}`}
            >
              {ocupado && (a === 'revisar_de_nuevo' || a === 'intentar_de_nuevo' || a === 'revisar' || a === 'reintentar')
                ? 'Un momento...'
                : textoAccion(a, it)}
            </button>
          ))}
          {it.puede_cambiar_cuenta && (
            <button
              type="button"
              disabled={ocupado}
              onClick={() => onAccion('cambiar_cuenta', it)}
              aria-label={`${TEXTO_ACCION.cambiar_cuenta}: ${it.titulo}`}
              className="min-h-11 text-xs font-semibold text-ink-soft disabled:opacity-50"
            >
              {TEXTO_ACCION.cambiar_cuenta}
            </button>
          )}
        </div>
      )}
    </li>
  )
}

/**
 * «Todos los extractos»: TODOS, de todos los estados, del más reciente al más antiguo y agrupados por mes.
 * Cada fila dice banco + tipo + mes en grande, su estado (ícono + texto) y una frase honesta de lo que pasó.
 * Filtros por estado y por cuenta/banco, buscador por mes y contador por estado.
 * `filtro` y `onFiltro` los maneja la pantalla (así «Por hacer» y la cobertura pueden abrir un grupo).
 */
export default function TodosLosExtractos({ datos, filtro, onFiltro, onAccion, onFijarMes, ocupados, releyendo, resultadosReleer, id = 'sinc-todos-extractos' }) {
  const [sinAdjuntoAbierto, setSinAdjuntoAbierto] = useState(false)
  const items = useMemo(() => datos?.items || [], [datos])
  const sinAdjunto = datos?.sin_adjunto || []
  const contadores = datos?.contadores || {}
  const visibles = useMemo(() => filtrar(items, filtro), [items, filtro])
  const grupos = useMemo(() => agruparPorMes(visibles), [visibles])
  const cuentas = useMemo(() => opcionesCuenta(items), [items])
  const hayFiltro = Boolean(filtro.estados?.length || filtro.cuenta || filtro.mes || filtro.texto)

  if (!datos || (items.length === 0 && sinAdjunto.length === 0)) return null

  const alternarEstado = (e) => {
    const ya = filtro.estados.includes(e)
    onFiltro({ ...filtro, estados: ya ? filtro.estados.filter((x) => x !== e) : [e] })
  }

  return (
    <div id={id} className="mt-5 scroll-mt-4" data-testid="todos-extractos">
      <h3 className="text-[13px] font-semibold">Todos los extractos{items.length ? ` (${items.length})` : ''}</h3>
      {items.length > 0 && (
        <p className="text-sm text-ink mt-1" data-testid="resumen-extractos">{datos.resumen || textoContadores(contadores)}</p>
      )}

      {items.length > 0 && (
        <div className="mt-3 flex flex-col gap-2.5">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar por estado">
            <button
              type="button"
              aria-pressed={!filtro.estados.length}
              onClick={() => onFiltro({ ...filtro, estados: [] })}
              className={`min-h-11 rounded-full border px-3.5 text-xs font-semibold ${!filtro.estados.length ? 'bg-ink text-paper-raised border-ink' : 'border-line text-ink-soft'}`}
            >
              Todos ({items.length})
            </button>
            {ESTADOS_VISTA.filter((e) => contadores[e.id] > 0).map((e) => {
              const activo = filtro.estados.includes(e.id)
              return (
                <button
                  key={e.id}
                  type="button"
                  aria-pressed={activo}
                  onClick={() => alternarEstado(e.id)}
                  className={`min-h-11 inline-flex items-center gap-1.5 rounded-full border px-3.5 text-xs font-semibold ${activo ? 'bg-ink text-paper-raised border-ink' : `border-line ${e.clase}`}`}
                >
                  <Icono icono={ICONO_ESTADO[e.id]} tam="sm" />
                  {e.texto} ({contadores[e.id]})
                </button>
              )
            })}
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <label className="flex-1 text-xs text-ink-soft flex flex-col gap-1">
              Buscar por mes
              <span className="relative">
                <Icono icono={Search} tam="sm" className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft" />
                <input
                  type="search"
                  value={filtro.texto}
                  onChange={(e) => onFiltro({ ...filtro, texto: e.target.value })}
                  placeholder="Ej. julio"
                  className="w-full min-h-11 rounded-xl border border-line bg-paper pl-9 pr-3 text-sm text-ink"
                />
              </span>
            </label>
            {cuentas.length > 1 && (
              <label className="flex-1 text-xs text-ink-soft flex flex-col gap-1">
                Cuenta o banco
                <select
                  value={filtro.cuenta}
                  onChange={(e) => onFiltro({ ...filtro, cuenta: e.target.value })}
                  className="min-h-11 rounded-xl border border-line bg-paper px-3 text-sm text-ink"
                >
                  <option value="">Todas</option>
                  {cuentas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                </select>
              </label>
            )}
          </div>

          {filtro.mes && (
            <p className="text-xs text-ink-soft">
              Solo se ven los de {visibles[0]?.mes_etiqueta || filtro.mes}.{' '}
              <button type="button" onClick={() => onFiltro({ ...filtro, mes: '' })} className="underline font-semibold text-accent min-h-8">Ver todos los meses</button>
            </p>
          )}
          <p className="text-xs text-ink-soft" role="status" aria-live="polite">
            {hayFiltro ? `Mostrando ${visibles.length} de ${items.length}` : `${items.length} ${items.length === 1 ? 'extracto' : 'extractos'}`}
            {hayFiltro && (
              <button type="button" onClick={() => onFiltro({ estados: [], cuenta: '', mes: '', texto: '' })} className="ml-2 underline font-semibold text-accent min-h-8">Quitar filtros</button>
            )}
          </p>
        </div>
      )}

      {items.length > 0 && visibles.length === 0 && (
        <p className="mt-3 text-sm text-ink-soft rounded-2xl bg-paper border border-line px-4 py-3">No hay extractos con esos filtros. Quita alguno para ver más.</p>
      )}

      <div className="mt-3 flex flex-col gap-4">
        {grupos.map((g) => (
          <section key={g.mes || 'sin-mes'} aria-label={g.etiqueta} data-testid={`mes-${g.mes || 'sin-mes'}`}>
            <h4 className="text-[11px] font-semibold uppercase tracking-wide text-ink-soft mb-1.5">{g.etiqueta} · {g.items.length}</h4>
            <ul className="rounded-2xl bg-paper divide-y divide-line/50 overflow-hidden">
              {g.items.map((it) => (
                <FilaExtractoVista key={it.id} it={it} onAccion={onAccion} onFijarMes={onFijarMes} ocupado={Boolean(ocupados?.has(it.id))}
                  releyendo={Boolean(it.historial_id && releyendo?.has(it.historial_id))} resultadoReleer={it.historial_id ? resultadosReleer?.[it.historial_id] : null} />
              ))}
            </ul>
          </section>
        ))}
      </div>

      {sinAdjunto.length > 0 && (
        <div className="mt-4" data-testid="sin-adjunto">
          <button
            type="button"
            onClick={() => setSinAdjuntoAbierto((v) => !v)}
            aria-expanded={sinAdjuntoAbierto}
            className="w-full min-h-11 flex items-center justify-between text-sm font-semibold text-ink-soft"
          >
            <span className="flex items-center gap-1.5">
              <Icono icono={Paperclip} tam="sm" /> Correos sin archivo adjunto ({sinAdjunto.length})
            </span>
            <Icono icono={ChevronDown} tam="sm" className={`transition-transform ${sinAdjuntoAbierto ? 'rotate-180' : ''}`} />
          </button>
          {sinAdjuntoAbierto && (
            <div>
              <p className="text-xs text-ink-soft mb-2">{datos.razon_sin_adjunto || 'Estos correos no traían el PDF del extracto.'}</p>
              <ul className="rounded-2xl bg-paper divide-y divide-line/50 overflow-hidden">
                {sinAdjunto.map((c) => (
                  <li key={c.id} className="px-4 py-2.5">
                    <p className="text-sm font-medium break-words">{c.asunto || 'Correo sin asunto'}</p>
                    <p className="text-xs text-ink-soft">
                      {[c.banco, c.recibido_en ? new Date(c.recibido_en).toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }) : ''].filter(Boolean).join(' · ')}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
