import { useCallback, useEffect, useState } from 'react'
import { EsqueletoLista } from '../components/Esqueletos'
import { useNavigate } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, MessageCircle, Plus } from 'lucide-react'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { enlaceCobroWhatsApp } from '../lib/gastosCompartidos'
import { useDialogos } from '../lib/DialogosContext'

export default function CuentasAmigos() {
  const navigate = useNavigate()
  const volver = useVolver('/')
  const { confirmar, avisar } = useDialogos()
  const [grupos, setGrupos] = useState([])
  const [grupoId, setGrupoId] = useState('')
  const [monedas, setMonedas] = useState([])
  const [gastos, setGastos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  const cargar = useCallback(async () => {
    setError('')
    try {
      const [s, g] = await Promise.all([api.saldosGasto(grupoId || undefined), api.gastosCompartidos(grupoId || undefined)])
      setMonedas(s.monedas)
      setGastos(g)
    } catch (e) {
      setError(e.message || 'No se pudieron cargar las cuentas con amigos')
    }
    setCargando(false)
  }, [grupoId])

  useEffect(() => {
    api.gruposGasto().then(setGrupos).catch(() => {})
  }, [])
  useEffect(() => {
    cargar()
  }, [cargar])

  async function registrarPago({ de_id, a_id, monto, moneda }, mensaje) {
    const ok = await confirmar(mensaje, { confirmarTexto: 'Sí, registrar' })
    if (!ok) return
    try {
      await api.registrarPagoGasto({ de_id, a_id, monto, moneda, grupo_id: grupoId || undefined })
      avisar('Pago registrado', 'ok')
      cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo registrar el pago')
    }
  }

  async function borrarGasto(g) {
    const ok = await confirmar(`¿Quitar "${g.descripcion}" de las cuentas con amigos? Tu movimiento no se borra.`, {
      confirmarTexto: 'Quitar',
    })
    if (!ok) return
    try {
      await api.eliminarGastoCompartido(g.id)
      cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo quitar el gasto')
    }
  }

  const vacio = !cargando && !error && monedas.length === 0 && gastos.length === 0

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/agregar')}
            className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
            aria-label="Volver"
          >
            <ArrowLeft size={18} />
          </button>
          <h1 className="text-2xl font-semibold">Cuentas con amigos</h1>
        </div>
        <button
          onClick={() => navigate('/dividir')}
          className="w-11 h-11 rounded-full bg-ink text-paper flex items-center justify-center"
          aria-label="Nuevo gasto dividido"
        >
          <Plus size={18} />
        </button>
      </header>

      {grupos.length > 0 && (
        <div className="px-5 mt-2 flex gap-2 overflow-x-auto no-scrollbar">
          {[{ id: '', nombre: 'Todo' }, ...grupos].map((g) => (
            <button
              key={g.id || 'todo'}
              onClick={() => setGrupoId(g.id)}
              aria-pressed={grupoId === g.id}
              className={`shrink-0 rounded-2xl border px-3.5 py-2 text-xs font-semibold ${
                grupoId === g.id ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
              }`}
            >
              {g.nombre}
            </button>
          ))}
        </div>
      )}

      {cargando && <EsqueletoLista filas={3} className="mx-5 mt-6" etiqueta="Cargando cuentas compartidas" />}
      {error && (
        <div className="px-5 mt-6" role="alert">
          <p className="text-sm text-danger">{error}</p>
          <button onClick={cargar} className="text-sm text-accent font-medium mt-1">
            Reintentar
          </button>
        </div>
      )}
      {vacio && (
        <div className="px-8 mt-16 text-center">
          <p className="font-semibold">Aún no hay cuentas con amigos</p>
          <p className="text-sm text-ink-soft mt-1">
            Al registrar un gasto toca "Dividir" y reparte la cuenta con quien quieras.
          </p>
          <button onClick={() => navigate('/agregar')} className="mt-4 text-sm text-accent font-medium">
            Ir a registrar un gasto
          </button>
        </div>
      )}

      {monedas.map((m) => (
        <section key={m.moneda} className="px-5 mt-5">
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-2xl border border-line bg-paper-raised p-3">
              <p className="text-[11px] text-ink-soft uppercase tracking-wide">Te deben</p>
              <p className="text-lg font-semibold tabular-nums text-accent">{formatMoneda(m.total_me_deben, m.moneda)}</p>
            </div>
            <div className="rounded-2xl border border-line bg-paper-raised p-3">
              <p className="text-[11px] text-ink-soft uppercase tracking-wide">Debes</p>
              <p className="text-lg font-semibold tabular-nums text-danger">{formatMoneda(m.total_debo, m.moneda)}</p>
            </div>
          </div>

          {m.personas.length > 0 && (
            <ul className="mt-3 flex flex-col gap-2">
              {m.personas.map((p) => {
                const meDebe = p.saldo > 0
                const monto = Math.abs(p.saldo)
                return (
                  <li key={p.contacto_id} className="rounded-2xl border border-line bg-paper-raised px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold truncate">{p.nombre}</p>
                        <p className="text-xs text-ink-soft">{meDebe ? 'Te debe' : 'Le debes'}</p>
                      </div>
                      <p className={`text-base font-semibold tabular-nums ${meDebe ? 'text-accent' : 'text-danger'}`}>
                        {formatMoneda(monto, m.moneda)}
                      </p>
                    </div>
                    <div className="flex gap-2 mt-2">
                      {meDebe ? (
                        <>
                          <a
                            href={enlaceCobroWhatsApp({ nombre: p.nombre, telefono: p.telefono, monto, moneda: m.moneda })}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex-1 rounded-xl bg-accent-soft text-accent text-xs font-semibold py-2 flex items-center justify-center gap-1.5"
                          >
                            <MessageCircle size={14} /> Cobrar por WhatsApp
                          </a>
                          <button
                            onClick={() =>
                              registrarPago(
                                { de_id: p.contacto_id, a_id: 'yo', monto, moneda: m.moneda },
                                `¿${p.nombre} te pagó ${formatMoneda(monto, m.moneda)}?`
                              )
                            }
                            className="flex-1 rounded-xl border border-line text-xs font-semibold py-2"
                          >
                            Me pagó
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() =>
                            registrarPago(
                              { de_id: 'yo', a_id: p.contacto_id, monto, moneda: m.moneda },
                              `¿Le pagaste ${formatMoneda(monto, m.moneda)} a ${p.nombre}?`
                            )
                          }
                          className="flex-1 rounded-xl border border-line text-xs font-semibold py-2"
                        >
                          Le pagué
                        </button>
                      )}
                    </div>
                  </li>
                )
              })}
            </ul>
          )}

          {m.simplificado.length > 0 && (
            <div className="mt-4">
              <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Para dejar todo en paz</p>
              <ul className="flex flex-col gap-1.5">
                {m.simplificado.map((p, i) => (
                  <li key={i} className="text-sm flex justify-between gap-2 rounded-xl bg-paper-raised border border-line px-3 py-2">
                    <span>
                      {p.de_nombre === 'Tú' ? (
                        <>
                          <strong>Tú</strong> le pagas a <strong>{p.a_nombre}</strong>
                        </>
                      ) : (
                        <>
                          <strong>{p.de_nombre}</strong> le paga a <strong>{p.a_nombre === 'Tú' ? 'ti' : p.a_nombre}</strong>
                        </>
                      )}
                    </span>
                    <span className="tabular-nums font-medium">{formatMoneda(p.monto, m.moneda)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      ))}

      {gastos.length > 0 && (
        <section className="px-5 mt-6">
          <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Gastos compartidos</p>
          <ul className="flex flex-col gap-2">
            {gastos.map((g) => (
              <li key={g.id} className="rounded-2xl border border-line bg-paper-raised px-4 py-3">
                <div className="flex justify-between gap-2">
                  <p className="text-sm font-semibold truncate">{g.descripcion}</p>
                  <p className="text-sm tabular-nums">{formatMoneda(g.total, g.moneda)}</p>
                </div>
                <p className="text-xs text-ink-soft mt-0.5">
                  Pagó {g.pagador} · {g.partes.map((p) => `${p.nombre} ${formatMoneda(p.monto, g.moneda)}`).join(' · ')}
                </p>
                <button onClick={() => borrarGasto(g)} className="text-xs text-danger mt-1.5">
                  Quitar
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
