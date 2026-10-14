import { useState } from 'react'
import { CalendarDays, Check, CheckCheck, Mail, Pencil, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { parsearMontoEscrito } from '../lib/centro'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import CrearCuentaBanco from './CrearCuentaBanco'
import InputMonto from './InputMonto'
import SelectorCuentaBanco from './SelectorCuentaBanco'
import { cuentaRecordada } from '../lib/cuentasBanco'
import RecordarRegla, { RECORDAR_INICIAL } from './RecordarRegla'
import { agruparPorDia, etiquetaFechaHora, fechaParaEnviar, fechasDistintas, valorInputFecha } from '../lib/fechaCorreo'

/**
 * Movimientos que CuadraMe leyó en tus correos: tú apruebas o descartas cada uno.
 * Un correo sin monto legible no se puede aprobar: la tarjeta pide el monto.
 *   correos: GET /correos/pendientes   ·   onResuelto(correo): ya se aprobó o descartó
 */
export default function CorreosPorRevisar({ correos, onResuelto, onCuentaCreada }) {
  const { cuentas } = useCuentas()
  const { nombres = [], iconoDe = () => '' } = useCategorias() || {}
  const [categoriaPorCorreo, setCategoriaPorCorreo] = useState({}) // id -> categoría elegida
  const [recordarPorCorreo, setRecordarPorCorreo] = useState({}) // id -> { recordar, anteriores }
  const [cuentaPorCorreo, setCuentaPorCorreo] = useState({})
  const [montoPorCorreo, setMontoPorCorreo] = useState({}) // id -> texto escrito
  const [editando, setEditando] = useState(new Set()) // ids con el panel «Editar» abierto
  const [fechaPorCorreo, setFechaPorCorreo] = useState({}) // id -> 'AAAA-MM-DD' elegido
  const [procesando, setProcesando] = useState(new Set())
  const [crearCuenta, setCrearCuenta] = useState(null) // { banco }
  const [error, setError] = useState('')

  // Solo vale una cuenta que exista: la elegida a mano o la que el servidor dedujo del banco.
  const existe = (id) => (id && cuentas.some((c) => c.id === id) ? id : '')
  // Si el banco tiene varias cuentas y no hay ganadora, se usa la que la persona eligió antes
  // para ese banco + tipo (solo entre las candidatas: nunca una de otro banco).
  const recordada = (c) => {
    const id = cuentaRecordada(c.banco_detectado, c.producto_detectado, cuentas)
    return id && (!c.cuentas_candidatas?.length || c.cuentas_candidatas.includes(id)) ? id : ''
  }
  const cuentaElegida = (c) => existe(cuentaPorCorreo[c.id]) || existe(c.cuenta_sugerida_id) || (c.pregunta_cuenta ? recordada(c) : '')
  // Monto que se aprobaría: el del correo o, si no se pudo leer, el que escribe la persona.
  const sinMonto = (c) => !(c.monto > 0)
  // Con «Editar» abierto y un monto escrito, vale ese; si no, el del correo.
  const montoEscrito = (c) => (montoPorCorreo[c.id] ? parsearMontoEscrito(montoPorCorreo[c.id]) : 0)
  const montoDe = (c) => (sinMonto(c) ? montoEscrito(c) : montoEscrito(c) > 0 ? montoEscrito(c) : c.monto)
  const fechaElegida = (c) => fechaPorCorreo[c.id] || valorInputFecha(c.fecha_movimiento)
  const fechaCambio = (c) => Boolean(c.fecha_movimiento) && fechaElegida(c) !== valorInputFecha(c.fecha_movimiento)
  const hoyISO = new Date().toISOString().slice(0, 10)
  const alternarEdicion = (id) =>
    setEditando((prev) => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })

  function ocupar(id, si) {
    setProcesando((prev) => {
      const next = new Set(prev)
      if (si) next.add(id)
      else next.delete(id)
      return next
    })
  }

  async function aprobar(c) {
    if (procesando.has(c.id)) return
    const cuentaId = cuentaElegida(c) // nunca se asume una cuenta
    const monto = montoDe(c)
    if (!cuentaId || !(monto > 0)) return
    ocupar(c.id, true)
    setError('')
    try {
      // Si cambió la categoría, esa manda y (con «Recordar» marcado, por defecto) se guarda la regla.
      const elegida = categoriaPorCorreo[c.id]
      const cambio = elegida && elegida !== c.categoria_sugerida
      const rec = recordarPorCorreo[c.id] || RECORDAR_INICIAL
      const extra = {
        ...(sinMonto(c) || monto !== c.monto ? { monto } : {}),
        ...(fechaCambio(c) ? { fecha: fechaParaEnviar(fechaElegida(c), c.fecha_movimiento) } : {}),
        ...(elegida
          ? { categoria: elegida, ...(cambio && elegida !== 'Otros' ? { recordar: !!rec.recordar, aplicar_anteriores: !!rec.recordar && !!rec.anteriores } : {}) }
          : {}),
      }
      if (Object.keys(extra).length) await api.aprobarCorreo(c.id, cuentaId, extra)
      else await api.aprobarCorreo(c.id, cuentaId)
      onResuelto?.(c)
    } catch (err) {
      setError(err.message || 'No se pudo aprobar el movimiento. Revisa tu conexión e intenta de nuevo.')
    } finally {
      ocupar(c.id, false)
    }
  }

  // «Parecen correctos»: ya traen cuenta, monto y categoría clara (nada que el usuario tenga que elegir).
  const correctos = correos.filter(
    (c) => cuentaElegida(c) && c.monto > 0 && !c.preguntar_categoria && !c.falta_cuenta && !categoriaPorCorreo[c.id] && !editando.has(c.id) && !procesando.has(c.id),
  )
  const [aprobandoTodos, setAprobandoTodos] = useState(false)

  async function aprobarCorrectos() {
    if (aprobandoTodos || correctos.length === 0) return
    setAprobandoTodos(true)
    setError('')
    let fallaron = 0
    for (const c of correctos) {
      try {
        await api.aprobarCorreo(c.id, cuentaElegida(c))
        onResuelto?.(c)
      } catch {
        fallaron += 1
      }
    }
    if (fallaron) setError(`No pude aprobar ${fallaron === 1 ? '1 movimiento' : `${fallaron} movimientos`}. Revisa tu conexión e intenta de nuevo.`)
    setAprobandoTodos(false)
  }

  async function descartar(c) {
    if (procesando.has(c.id)) return
    ocupar(c.id, true)
    setError('')
    try {
      await api.descartarCorreo(c.id)
      onResuelto?.(c)
    } catch (err) {
      setError(err.message || 'No se pudo descartar. Revisa tu conexión e intenta de nuevo.')
    } finally {
      ocupar(c.id, false)
    }
  }

  return (
    <div>
      {error && <p className="text-xs text-danger mb-2" role="alert">{error}</p>}
      {correctos.length >= 2 && (
        <button
          type="button"
          onClick={aprobarCorrectos}
          disabled={aprobandoTodos}
          className="w-full flex items-center justify-center gap-2 bg-accent text-paper-raised font-semibold rounded-xl min-h-[44px] text-sm mb-3 disabled:opacity-60"
          data-testid="aprobar-correctos"
        >
          <CheckCheck size={16} aria-hidden="true" />
          {aprobandoTodos ? 'Aprobando...' : `Aprobar los ${correctos.length} que parecen correctos`}
        </button>
      )}
      {agruparPorDia(correos).map((g) => (
      <div key={g.clave} className="mb-3" data-testid={`dia-${g.clave}`}>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-soft mb-1.5 px-1">{g.etiqueta}</h4>
      <ul className="flex flex-col gap-3">
        {g.items.map((c) => {
          const falta = sinMonto(c)
          const monto = montoDe(c)
          const cuentaId = cuentaElegida(c)
          return (
            <li key={c.id} className="rounded-2xl bg-paper border border-line p-4" data-testid={`correo-${c.id}`}>
              {c.fecha_movimiento && (
                <div className="mb-2" data-testid={`fecha-${c.id}`}>
                  <p className="flex items-center gap-1.5 text-[13px] font-semibold text-ink">
                    <CalendarDays size={16} className="text-accent shrink-0" aria-hidden="true" />
                    {etiquetaFechaHora(fechaCambio(c) ? fechaParaEnviar(fechaElegida(c), c.fecha_movimiento) : c.fecha_movimiento, c.fecha_movimiento_con_hora)}
                  </p>
                  {c.fecha_del_texto && fechasDistintas(c.fecha_movimiento, c.recibido_en_co) && (
                    <p className="text-[11px] text-ink-soft mt-0.5 ml-[22px]">
                      Fecha del movimiento (la que usaré) · Llegó el correo el {etiquetaFechaHora(c.recibido_en_co)}
                    </p>
                  )}
                </div>
              )}
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold truncate">{c.comercio}</p>
                  <p className="text-xs text-ink-soft truncate">{c.asunto}</p>
                </div>
                {!falta && (
                  <p className={`text-sm font-bold shrink-0 ${c.tipo_sugerido === 'income' ? 'text-accent' : 'text-ink'}`}>
                    {c.tipo_sugerido === 'income' ? '+' : '-'}
                    {formatCOP(c.monto)}
                  </p>
                )}
              </div>

              {falta && (
                <label className="block mt-2">
                  <span className="text-xs font-medium text-accent">No pude leer el monto. Escríbelo para aprobar.</span>
                  <InputMonto
                    value={montoPorCorreo[c.id] || ''}
                    onValor={(v) => setMontoPorCorreo((p) => ({ ...p, [c.id]: v }))}
                    placeholder="Monto, ej. 25.000"
                    aria-label={`Monto de ${c.comercio}`}
                    className="w-full mt-1 rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm outline-none focus:border-accent"
                  />
                </label>
              )}

              <p className="text-xs text-ink-soft mt-1">
                {c.preguntar_categoria && !categoriaPorCorreo[c.id]
                  ? 'Sin categoría clara'
                  : `${iconoDe(c.categoria_sugerida) ? `${iconoDe(c.categoria_sugerida)} ` : ''}${c.categoria_sugerida}${c.razon_categoria && !categoriaPorCorreo[c.id] ? ` · ${c.razon_categoria}` : ''}`}
                {c.banco_detectado ? ` · ${c.banco_detectado}` : ''}
              </p>
              <p className="flex items-center gap-1 text-[11px] text-ink-soft mt-0.5"><Mail size={16} className="shrink-0" aria-hidden="true" /> Leído de tu correo</p>

              {c.preguntar_categoria && !categoriaPorCorreo[c.id] && (
                <p className="text-xs font-medium text-accent mt-1" data-testid={`pregunta-cat-${c.id}`}>
                  No supe qué categoría es. ¿Cuál es? La recuerdo para la próxima.
                </p>
              )}
              <select
                value={categoriaPorCorreo[c.id] || (c.preguntar_categoria ? '' : c.categoria_sugerida)}
                onChange={(e) => {
                  const v = e.target.value
                  setCategoriaPorCorreo((prev) => ({ ...prev, [c.id]: v }))
                  setRecordarPorCorreo((prev) => ({ ...prev, [c.id]: prev[c.id] || RECORDAR_INICIAL }))
                }}
                aria-label={`Categoría de ${c.comercio}`}
                className="w-full mt-2 rounded-xl border border-line bg-paper-raised px-3 py-2 text-xs"
              >
                <option value="">{c.preguntar_categoria ? 'Elige la categoría' : `Categoría (${c.categoria_sugerida})`}</option>
                {!c.preguntar_categoria && !nombres.includes(c.categoria_sugerida) && (
                  <option value={c.categoria_sugerida}>{c.categoria_sugerida}</option>
                )}
                {nombres.map((n) => (
                  <option key={n} value={n}>{iconoDe(n)} {n}</option>
                ))}
              </select>
              {categoriaPorCorreo[c.id] && categoriaPorCorreo[c.id] !== c.categoria_sugerida && categoriaPorCorreo[c.id] !== 'Otros' && (
                <RecordarRegla
                  descripcion={c.comercio}
                  valor={recordarPorCorreo[c.id]}
                  onChange={(v) => setRecordarPorCorreo((prev) => ({ ...prev, [c.id]: v }))}
                  className="mt-2"
                />
              )}

              <SelectorCuentaBanco
                className="mt-3"
                cuentas={cuentas}
                value={cuentaId}
                onChange={(id) => setCuentaPorCorreo((prev) => ({ ...prev, [c.id]: id }))}
                ariaLabel={`Cuenta de ${c.comercio}`}
                vacio={c.falta_cuenta ? `No tienes cuenta ${c.banco_detectado}` : 'Elige la cuenta'}
                banco={c.banco_detectado}
                producto={c.producto_detectado}
                pregunta={c.pregunta_cuenta}
                sugeridaId={c.cuenta_sugerida_id}
                candidatas={c.cuentas_candidatas}
              />
              {c.falta_cuenta && (
                <button onClick={() => setCrearCuenta({ banco: c.banco_detectado, id: c.id })} className="mt-2 text-xs font-semibold text-accent min-h-[32px]">
                  Crear cuenta {c.banco_detectado}
                </button>
              )}

              {editando.has(c.id) && (
                <div className="grid grid-cols-2 gap-2 mt-3" data-testid={`editar-${c.id}`}>
                  <label className="block">
                    <span className="text-xs font-medium text-ink-soft">Fecha del movimiento</span>
                    <input
                      type="date"
                      value={fechaElegida(c)}
                      max={hoyISO}
                      onChange={(e) => e.target.value && setFechaPorCorreo((p) => ({ ...p, [c.id]: e.target.value }))}
                      aria-label={`Fecha de ${c.comercio}`}
                      className="w-full mt-1 rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm"
                    />
                  </label>
                  {!falta && (
                    <label className="block">
                      <span className="text-xs font-medium text-ink-soft">Monto</span>
                      <InputMonto
                        value={montoPorCorreo[c.id] || ''}
                        onValor={(v) => setMontoPorCorreo((p) => ({ ...p, [c.id]: v }))}
                        placeholder={String(c.monto)}
                        aria-label={`Corregir monto de ${c.comercio}`}
                        className="w-full mt-1 rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm outline-none focus:border-accent"
                      />
                    </label>
                  )}
                </div>
              )}

              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => aprobar(c)}
                  disabled={procesando.has(c.id) || !cuentaId || !(monto > 0)}
                  className="flex-1 flex items-center justify-center gap-1.5 bg-accent text-paper-raised font-semibold rounded-xl py-2.5 text-sm disabled:opacity-50"
                >
                  <Check size={16} aria-hidden="true" /> Aprobar
                </button>
                <button
                  onClick={() => descartar(c)}
                  disabled={procesando.has(c.id)}
                  className="px-4 rounded-xl border border-line text-sm text-ink-soft flex items-center gap-1.5 disabled:opacity-50"
                >
                  <X size={16} aria-hidden="true" /> Descartar
                </button>
                <button
                  onClick={() => alternarEdicion(c.id)}
                  aria-expanded={editando.has(c.id)}
                  className="px-3 rounded-xl border border-line text-sm text-ink-soft flex items-center gap-1.5 min-h-[44px]"
                >
                  <Pencil size={16} aria-hidden="true" /> Editar
                </button>
              </div>
            </li>
          )
        })}
      </ul>
      </div>
      ))}

      {crearCuenta && (
        <CrearCuentaBanco
          banco={crearCuenta.banco}
          onClose={() => setCrearCuenta(null)}
          onCreada={(cuenta) => {
            // La cuenta nueva queda elegida para los correos de ese banco que no tenían cuenta.
            setCuentaPorCorreo((prev) => {
              const sig = { ...prev }
              for (const p of correos) if (p.banco_detectado === crearCuenta.banco && p.falta_cuenta) sig[p.id] = cuenta?.id
              return sig
            })
            setCrearCuenta(null)
            onCuentaCreada?.(cuenta)
          }}
        />
      )}
    </div>
  )
}
