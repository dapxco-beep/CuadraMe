import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ChevronDown, ChevronUp, EyeOff, Flag, Hand, ListChecks, Tag, Undo2, Zap } from 'lucide-react'
import { EsqueletoLista } from '../components/Esqueletos'
import { EstadoVacio } from '../brand/Marca'
import SelectorCategoria from '../components/SelectorCategoria'
import { useVolver } from '../lib/useVolver'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { fechaHoraMovimiento, fechaDeMovimiento } from '../lib/fechaMovimiento'
import { useCategorias } from '../lib/CategoriasContext'
import {
  LIMITE_VISIBLE,
  alternarComercio,
  alternarMovimiento,
  contarSeleccion,
  cuerpoAccion,
  hayAlgo,
  loQueMasPesa,
  ninguno,
  plural,
  seleccionarVisibles,
  textoResultado,
} from '../lib/porCategorizar'

// «Por categorizar» a elección. Nada es obligatorio: se puede ignorar toda la lista. Aquí la persona
// elige a qué comercios ponerles categoría, cuáles dejar como están y de cuáles no quiere más preguntas.
// Todo se puede deshacer. Lo que cuenta como pendiente lo decide el servidor (backend/app/pendientes.py).

const MOTIVO = { otros: 'Sin categoría', baja: 'Categoría dudosa', marcada: 'La marcaste tú' }

function FilaComercio({ g, marcado, ids, onComercio, onMovimiento, onVer }) {
  const [abierto, setAbierto] = useState(false)
  const [movs, setMovs] = useState(null)
  const nombre = g.nombre || g.ejemplo

  async function alternar() {
    const siguiente = !abierto
    setAbierto(siguiente)
    if (siguiente && !movs) {
      try {
        const r = await api.movimientos(100, 0, { porRevisar: true, q: g.ejemplo?.slice(0, 40) })
        const propios = new Set(g.movimiento_ids)
        setMovs((r || []).filter((m) => propios.has(m.id)))
      } catch {
        setMovs([])
      }
    }
    onVer?.(siguiente)
  }

  return (
    <li className="px-4 py-3" data-testid="fila-pendiente">
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={marcado}
          onChange={() => onComercio(g.huella)}
          aria-label={`Seleccionar ${nombre}, ${plural(g.conteo, 'movimiento', 'movimientos')}, ${formatCOP(g.monto_total)}`}
          className="mt-1 w-5 h-5 accent-[var(--c-accent)] shrink-0"
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold break-words line-clamp-2 capitalize">{nombre}</p>
          <p className="text-xs text-ink-soft">
            {plural(g.conteo, 'movimiento', 'movimientos')} · {formatCOP(g.monto_total)}
            {g.categoria_actual && g.categoria_actual !== 'Otros' ? ` · hoy en ${g.categoria_actual}` : ''}
          </p>
          <p className="text-[11px] text-ink-soft mt-0.5">{g.motivos.map((m) => MOTIVO[m]).join(' · ')}</p>
        </div>
        {g.conteo > 1 && (
          <button
            type="button"
            onClick={alternar}
            aria-expanded={abierto}
            aria-label={`${abierto ? 'Ocultar' : 'Ver'} los ${g.conteo} movimientos de ${nombre}`}
            className="w-11 h-11 -mr-2 -mt-2 flex items-center justify-center text-ink-soft shrink-0"
          >
            {abierto ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </button>
        )}
      </div>
      {abierto && (
        <ul className="mt-2 ml-8 space-y-1" aria-label={`Movimientos de ${nombre}`}>
          {movs === null && <li className="text-xs text-ink-soft">Cargando…</li>}
          {(movs || []).map((m) => (
            <li key={m.id} className="flex items-start gap-2 text-xs min-h-[44px] py-1">
              <input
                type="checkbox"
                checked={marcado || ids.has(m.id)}
                disabled={marcado}
                onChange={() => onMovimiento(m.id)}
                aria-label={`Seleccionar ${m.descripcion} del ${String(m.fecha).slice(0, 10)}, ${formatCOP(m.monto)}`}
                className="w-4 h-4 accent-[var(--c-accent)] shrink-0"
              />
              <span className="flex-1 min-w-0">
                <span className="block font-medium break-words line-clamp-3">{m.descripcion}</span>
                <span className="block text-ink-soft">{fechaHoraMovimiento(fechaDeMovimiento(m))}</span>
              </span>
              <span className="shrink-0 whitespace-nowrap tabular-nums font-semibold">{formatCOP(m.monto)}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

export default function PorCategorizar() {
  const volver = useVolver('/movimientos')
  const { nombres } = useCategorias()
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [verTodos, setVerTodos] = useState(false)
  const [sel, setSel] = useState(ninguno())
  const [aviso, setAviso] = useState(null) // { texto, deshacer }
  const [ocupado, setOcupado] = useState(false)
  const [eligiendo, setEligiendo] = useState(false)
  const [rapido, setRapido] = useState(null) // { lista, i, hechos }
  const [silencios, setSilencios] = useState([])
  const [verSilencios, setVerSilencios] = useState(false)

  const cargar = useCallback(
    async (todos = verTodos) => {
      setError('')
      try {
        setDatos(await api.porCategorizar(LIMITE_VISIBLE, todos))
        setSilencios((await api.silenciosPorCategorizar())?.silencios || [])
      } catch (err) {
        setError(err.message || 'No se pudo cargar. Revisa tu conexión e intenta de nuevo.')
      }
    },
    [verTodos]
  )

  useEffect(() => {
    cargar()
  }, [cargar])

  const grupos = datos?.grupos || []
  const nSel = contarSeleccion(sel, grupos)
  const comercioUnico = useMemo(() => {
    if (sel.huellas.size === 1 && sel.ids.size === 0) return grupos.find((g) => sel.huellas.has(g.huella)) || null
    return null
  }, [sel, grupos])

  async function ejecutar(accion, extra = {}, seleccion = sel) {
    setOcupado(true)
    setAviso(null)
    try {
      const r = await api.accionPorCategorizar(cuerpoAccion(accion, seleccion, extra))
      const deshacer = {
        previos: r.previos || [],
        huellas: r.huellas_nuevas || [],
        tipo_silencio: accion === 'no_preguntar' || accion === 'ocultar' ? accion : undefined,
        reglas_creadas: r.reglas_creadas || [],
      }
      setAviso({ texto: textoResultado(accion, r), deshacer })
      setSel(ninguno())
      await cargar()
      return r
    } catch (err) {
      setAviso({ texto: err.message || 'No se pudo. Revisa tu conexión e intenta de nuevo.', error: true })
      return null
    } finally {
      setOcupado(false)
    }
  }

  async function deshacer() {
    if (!aviso?.deshacer) return
    setOcupado(true)
    try {
      await api.deshacerPorCategorizar(aviso.deshacer)
      setAviso({ texto: 'Listo, volví todo como estaba.' })
      await cargar()
    } catch (err) {
      setAviso({ texto: err.message || 'No se pudo deshacer.', error: true })
    } finally {
      setOcupado(false)
    }
  }

  async function elegirCategoria(categoria, { recordar, anteriores }) {
    await ejecutar('categoria', { categoria, recordar: !!recordar && !!comercioUnico, aplicar_anteriores: !!anteriores })
  }

  function empezarRapido() {
    const lista = loQueMasPesa(grupos)
    if (!lista.length) return
    setRapido({ lista, i: 0, hechos: 0 })
  }

  async function elegirRapido(categoria, { recordar, anteriores }) {
    const g = rapido.lista[rapido.i]
    const r = await ejecutar('categoria', { categoria, recordar: !!recordar, aplicar_anteriores: !!anteriores }, { huellas: new Set([g.huella]), ids: new Set() })
    avanzarRapido(r ? 1 : 0)
  }

  function avanzarRapido(suma = 0) {
    setRapido((r) => (r.i + 1 >= r.lista.length ? { ...r, i: r.lista.length, hechos: r.hechos + suma } : { ...r, i: r.i + 1, hechos: r.hechos + suma }))
  }

  const sinPendientes = datos && datos.total_grupos === 0
  const soloSueltos = datos && datos.total_grupos > 0 && datos.relevantes === 0

  return (
    <div className="flex-1 overflow-y-auto pb-28 screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Por categorizar</h1>
      </header>

      <p className="mx-6 mt-1 text-sm text-ink-soft">
        Lo importante son los comercios que se repiten o pesan; el resto puede quedarse como está. Nada es obligatorio.
      </p>

      {!datos && !error && <EsqueletoLista filas={5} className="mx-6 mt-6" etiqueta="Cargando lo que falta por categorizar" />}

      {error && (
        <div className="mx-6 mt-6 rounded-2xl bg-danger-soft p-6 text-center" role="alert">
          <p className="text-sm text-danger mb-3">{error}</p>
          <button onClick={() => cargar()} className="text-sm font-semibold text-danger underline">
            Reintentar
          </button>
        </div>
      )}

      <div aria-live="polite" className="mx-6">
        {aviso && (
          <p className={`mt-3 rounded-2xl px-4 py-3 text-sm flex items-center gap-3 ${aviso.error ? 'bg-danger-soft text-danger' : 'bg-accent-soft text-ink'}`} role="status">
            <span className="flex-1">{aviso.texto}</span>
            {aviso.deshacer && !aviso.error && (
              <button onClick={deshacer} disabled={ocupado} className="font-semibold underline flex items-center gap-1 min-h-[44px]">
                <Undo2 size={16} /> Deshacer
              </button>
            )}
          </p>
        )}
      </div>

      {rapido && (
        <section className="mx-6 mt-4 rounded-2xl border border-line bg-paper-raised p-4" aria-label="Categorizar lo que más pesa">
          {rapido.i >= rapido.lista.length ? (
            <div className="text-center py-3">
              <p className="text-sm font-semibold">¡Listo! Categorizaste {plural(rapido.hechos, 'comercio', 'comercios')}.</p>
              <p className="text-xs text-ink-soft mt-1">Lo demás puede quedarse como está.</p>
              <button onClick={() => setRapido(null)} className="mt-3 rounded-xl bg-ink text-paper px-4 py-2.5 text-sm font-semibold min-h-[44px]">
                Terminar
              </button>
            </div>
          ) : (
            (() => {
              const g = rapido.lista[rapido.i]
              return (
                <>
                  <p className="text-xs text-ink-soft">
                    {rapido.i + 1} de {rapido.lista.length}
                  </p>
                  <p className="text-base font-semibold mt-1 capitalize">{g.nombre || g.ejemplo}</p>
                  <p className="text-xs text-ink-soft">
                    {plural(g.conteo, 'movimiento', 'movimientos')} · {formatCOP(g.monto_total)}
                  </p>
                  <div className="flex flex-wrap gap-2 mt-3">
                    <button onClick={() => setEligiendo('rapido')} disabled={ocupado} className="rounded-xl bg-accent text-paper-raised px-4 py-2.5 text-sm font-semibold min-h-[44px] flex items-center gap-2">
                      <Tag size={16} /> Elegir categoría
                    </button>
                    <button onClick={() => avanzarRapido(0)} className="rounded-xl border border-line px-4 py-2.5 text-sm font-semibold min-h-[44px]">
                      Saltar
                    </button>
                    <button onClick={() => setRapido(null)} className="rounded-xl px-3 py-2.5 text-sm text-ink-soft underline min-h-[44px]">
                      Salir
                    </button>
                  </div>
                </>
              )
            })()
          )}
        </section>
      )}

      {sinPendientes && (
        <EstadoVacio
          icono={ListChecks}
          pose="celebrando"
          titulo="Todo en orden"
          texto="No tienes nada por categorizar. Cuando lleguen movimientos nuevos y dudosos, te aviso aquí, sin afán."
          className="mx-6 mt-6"
        />
      )}

      {datos && !sinPendientes && (
        <>
          {soloSueltos && (
            <EstadoVacio
              icono={ListChecks}
              pose="celebrando"
              titulo="Lo importante ya está categorizado"
              texto={`Lo que queda son ${plural(datos.conteo.total, 'compra suelta', 'compras sueltas')}: ninguna se repite ni pesa mucho. Pueden quedarse como están.`}
              className="mx-6 mt-4"
            />
          )}
          {!soloSueltos && !rapido && (
            <div className="mx-6 mt-4 rounded-2xl bg-paper-raised border border-line p-4">
              <p className="text-sm">
                Tienes <b>{plural(datos.conteo.total, 'movimiento', 'movimientos')}</b> en {plural(datos.total_grupos, 'comercio', 'comercios')}.{' '}
                {datos.relevantes > 0 && (
                  <>
                    {plural(datos.relevantes, 'comercio se repite', 'comercios se repiten')} 4 veces o más (o los que marcaste tú).
                  </>
                )}
              </p>
              <button
                onClick={empezarRapido}
                className="mt-3 w-full rounded-xl bg-accent text-paper-raised px-4 py-3 text-sm font-semibold flex items-center justify-center gap-2 min-h-[44px]"
              >
                <Zap size={16} /> Categorizar lo que más pesa en 1 minuto
              </button>
            </div>
          )}

          <section className="mx-6 mt-5" aria-label="Comercios por categorizar">
            <div className="flex items-center justify-between gap-2 mb-2">
              <h2 className="text-sm font-semibold">{verTodos ? 'Todos los comercios' : `Los ${Math.min(LIMITE_VISIBLE, datos.total_grupos)} que más pesan`}</h2>
              <div className="flex gap-1">
                <button onClick={() => setSel(seleccionarVisibles(grupos))} className="text-xs font-medium underline min-h-[44px] px-2">
                  Seleccionar los visibles
                </button>
                <button onClick={() => setSel(ninguno())} disabled={!hayAlgo(sel)} className="text-xs font-medium underline min-h-[44px] px-2 disabled:opacity-40">
                  Ninguno
                </button>
              </div>
            </div>
            <ul className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
              {grupos.map((g) => (
                <FilaComercio
                  key={g.huella}
                  g={g}
                  marcado={sel.huellas.has(g.huella)}
                  ids={sel.ids}
                  onComercio={(h) => setSel((s) => alternarComercio(s, h))}
                  onMovimiento={(id) => setSel((s) => alternarMovimiento(s, id))}
                />
              ))}
            </ul>
            {datos.hay_mas && !verTodos && (
              <button
                onClick={() => {
                  setVerTodos(true)
                  cargar(true)
                }}
                className="mt-3 w-full rounded-xl border border-line px-4 py-3 text-sm font-semibold min-h-[44px]"
              >
                Ver todos ({datos.total_grupos})
              </button>
            )}
            {verTodos && datos.total_grupos > LIMITE_VISIBLE && (
              <button
                onClick={() => {
                  setVerTodos(false)
                  cargar(false)
                }}
                className="mt-3 w-full rounded-xl border border-line px-4 py-3 text-sm font-semibold min-h-[44px]"
              >
                Ver solo los {LIMITE_VISIBLE} que más pesan
              </button>
            )}
          </section>
        </>
      )}

      {silencios.length > 0 && (
        <section className="mx-6 mt-6" aria-label="Comercios que silenciaste">
          <button onClick={() => setVerSilencios((v) => !v)} aria-expanded={verSilencios} className="text-sm font-semibold flex items-center gap-2 min-h-[44px]">
            <EyeOff size={16} /> Comercios que no quieres ver ({silencios.length})
            {verSilencios ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          {verSilencios && (
            <ul className="rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden mt-1">
              {silencios.map((s) => (
                <li key={s.huella} className="flex items-center gap-3 px-4 py-2">
                  <span className="flex-1 text-sm break-words line-clamp-2 capitalize">{s.huella}</span>
                  <button
                    onClick={async () => {
                      await api.quitarSilencios([s.huella])
                      await cargar()
                    }}
                    className="text-xs font-semibold underline min-h-[44px]"
                    aria-label={`Volver a preguntarme por ${s.huella}`}
                  >
                    Volver a preguntar
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {hayAlgo(sel) && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-paper-raised px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]" role="region" aria-label="Acciones sobre lo seleccionado">
          <p className="text-xs text-ink-soft mb-2">Seleccionaste {plural(nSel, 'movimiento', 'movimientos')}</p>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => setEligiendo('seleccion')} disabled={ocupado} className="rounded-xl bg-accent text-paper-raised px-3.5 py-2.5 text-sm font-semibold min-h-[44px] flex items-center gap-1.5">
              <Tag size={16} /> Ponerles categoría…
            </button>
            <button onClick={() => ejecutar('dejar')} disabled={ocupado} className="rounded-xl border border-line px-3.5 py-2.5 text-sm font-semibold min-h-[44px] flex items-center gap-1.5">
              <Hand size={16} /> Dejar como están
            </button>
            <button onClick={() => ejecutar('no_preguntar')} disabled={ocupado} className="rounded-xl border border-line px-3.5 py-2.5 text-sm font-semibold min-h-[44px] flex items-center gap-1.5">
              <EyeOff size={16} /> No volver a preguntarme por este comercio
            </button>
            <button onClick={() => ejecutar('ocultar')} disabled={ocupado} className="rounded-xl border border-line px-3.5 py-2.5 text-sm font-semibold min-h-[44px] flex items-center gap-1.5">
              <Flag size={16} /> Ocultar de esta lista
            </button>
          </div>
        </div>
      )}

      {eligiendo === 'seleccion' && (
        <SelectorCategoria
          titulo={`Categoría para ${plural(nSel, 'movimiento', 'movimientos')}`}
          subtitulo={comercioUnico ? comercioUnico.nombre : undefined}
          movimiento={comercioUnico ? { id: comercioUnico.movimiento_id, descripcion: comercioUnico.ejemplo } : undefined}
          recientes={nombres.slice(0, 5)}
          conSubcategorias={false}
          onElegir={elegirCategoria}
          onCerrar={() => setEligiendo(false)}
        />
      )}
      {eligiendo === 'rapido' && rapido && rapido.i < rapido.lista.length && (
        <SelectorCategoria
          titulo="¿Qué es?"
          subtitulo={rapido.lista[rapido.i].nombre}
          movimiento={{ id: rapido.lista[rapido.i].movimiento_id, descripcion: rapido.lista[rapido.i].ejemplo }}
          recientes={nombres.slice(0, 5)}
          conSubcategorias={false}
          onElegir={elegirRapido}
          onCerrar={() => setEligiendo(false)}
        />
      )}
    </div>
  )
}
