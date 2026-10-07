import { useState } from 'react'
import { Check, X } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { parsearMontoEscrito } from '../lib/centro'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import CrearCuentaBanco from './CrearCuentaBanco'
import RecordarRegla, { RECORDAR_INICIAL } from './RecordarRegla'

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
  const [procesando, setProcesando] = useState(new Set())
  const [crearCuenta, setCrearCuenta] = useState(null) // { banco }
  const [error, setError] = useState('')

  // Solo vale una cuenta que exista: la elegida a mano o la que el servidor dedujo del banco.
  const existe = (id) => (id && cuentas.some((c) => c.id === id) ? id : '')
  const cuentaElegida = (c) => existe(cuentaPorCorreo[c.id]) || existe(c.cuenta_sugerida_id)
  // Monto que se aprobaría: el del correo o, si no se pudo leer, el que escribe la persona.
  const sinMonto = (c) => !(c.monto > 0)
  const montoDe = (c) => (sinMonto(c) ? parsearMontoEscrito(montoPorCorreo[c.id]) : c.monto)

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
        ...(sinMonto(c) ? { monto } : {}),
        ...(elegida
          ? { categoria: elegida, ...(cambio && elegida !== 'Otros' ? { recordar: !!rec.recordar, aplicar_anteriores: !!rec.recordar && !!rec.anteriores } : {}) }
          : {}),
      }
      if (Object.keys(extra).length) await api.aprobarCorreo(c.id, cuentaId, extra)
      else await api.aprobarCorreo(c.id, cuentaId)
      onResuelto?.(c)
    } catch (err) {
      setError(err.message || 'No se pudo aprobar el movimiento')
    } finally {
      ocupar(c.id, false)
    }
  }

  async function descartar(c) {
    if (procesando.has(c.id)) return
    ocupar(c.id, true)
    setError('')
    try {
      await api.descartarCorreo(c.id)
      onResuelto?.(c)
    } catch (err) {
      setError(err.message || 'No se pudo descartar')
    } finally {
      ocupar(c.id, false)
    }
  }

  return (
    <div>
      {error && <p className="text-xs text-danger mb-2" role="alert">{error}</p>}
      <ul className="flex flex-col gap-3">
        {correos.map((c) => {
          const falta = sinMonto(c)
          const monto = montoDe(c)
          const cuentaId = cuentaElegida(c)
          return (
            <li key={c.id} className="rounded-2xl bg-paper border border-line p-4" data-testid={`correo-${c.id}`}>
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
                  <input
                    inputMode="decimal"
                    value={montoPorCorreo[c.id] || ''}
                    onChange={(e) => setMontoPorCorreo((p) => ({ ...p, [c.id]: e.target.value }))}
                    placeholder="Monto, ej. 25.000"
                    aria-label={`Monto de ${c.comercio}`}
                    className="w-full mt-1 rounded-xl border border-line bg-paper-raised px-3 py-2 text-sm outline-none focus:border-accent"
                  />
                </label>
              )}

              <p className="text-xs text-ink-soft mt-1">
                {c.preguntar_categoria && !categoriaPorCorreo[c.id]
                  ? 'Sin categoría clara'
                  : `${c.categoria_sugerida}${c.razon_categoria && !categoriaPorCorreo[c.id] ? ` · ${c.razon_categoria}` : ''}`}
                {c.banco_detectado ? ` · ${c.banco_detectado}` : ''}
              </p>

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

              <select
                value={cuentaId}
                onChange={(e) => setCuentaPorCorreo((prev) => ({ ...prev, [c.id]: e.target.value }))}
                aria-label={`Cuenta de ${c.comercio}`}
                className="w-full mt-3 rounded-xl border border-line bg-paper-raised px-3 py-2 text-xs"
              >
                <option value="">{c.falta_cuenta ? `No tienes cuenta ${c.banco_detectado}` : 'Elige la cuenta'}</option>
                {cuentas.map((cu) => (
                  <option key={cu.id} value={cu.id}>{cu.nombre}</option>
                ))}
              </select>
              {c.falta_cuenta && (
                <button onClick={() => setCrearCuenta({ banco: c.banco_detectado, id: c.id })} className="mt-2 text-xs font-semibold text-accent min-h-[32px]">
                  Crear cuenta {c.banco_detectado}
                </button>
              )}

              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => aprobar(c)}
                  disabled={procesando.has(c.id) || !cuentaId || !(monto > 0)}
                  className="flex-1 flex items-center justify-center gap-1.5 bg-accent text-white font-semibold rounded-xl py-2.5 text-sm disabled:opacity-50"
                >
                  <Check size={14} aria-hidden="true" /> Aprobar
                </button>
                <button
                  onClick={() => descartar(c)}
                  disabled={procesando.has(c.id)}
                  className="px-4 rounded-xl border border-line text-sm text-ink-soft flex items-center gap-1.5 disabled:opacity-50"
                >
                  <X size={14} aria-hidden="true" /> Descartar
                </button>
              </div>
            </li>
          )
        })}
      </ul>

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
