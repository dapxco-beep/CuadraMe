import { aFecha } from '../lib/fechaLocal'
import { textoError } from '../lib/textoError'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Check, Copy, MessageCircle, Share2, Undo2 } from 'lucide-react'
import { EsqueletoLista } from '../components/Esqueletos'
import InputMonto from '../components/InputMonto'
import { api } from '../lib/api'
import { formatMoneda } from '../lib/format'
import { useCuentas } from '../lib/CuentasContext'
import { useDialogos } from '../lib/DialogosContext'
import {
  enlaceCompartirColecta,
  enlacePublicoColecta,
  enlaceRecordatorioColecta,
  ETIQUETA_ESTADO,
  porcentaje,
} from '../lib/colectas'

const COLOR_ESTADO = {
  pagado: 'bg-accent-soft text-accent',
  parcial: 'bg-paper text-ink border border-line',
  falta: 'bg-paper text-ink-soft border border-line',
}

// Una vaca: quién ya puso, quién falta, recordarle por WhatsApp y compartir el avance en un enlace.
export default function DetalleColecta() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { confirmar, avisar } = useDialogos()
  const { cuentas, recargar } = useCuentas()
  const [c, setC] = useState(null)
  const [contactos, setContactos] = useState([])
  const [error, setError] = useState('')
  const [parcial, setParcial] = useState(null) // { aporte_id, monto }
  const [alCuenta, setAlCuenta] = useState(true)
  const [agregando, setAgregando] = useState(false)
  const [datosPago, setDatosPago] = useState('')

  const cargar = useCallback(async () => {
    setError('')
    try {
      setC(await api.colecta(id))
    } catch (e) {
      setError(e.status === 404 ? 'Esta vaca ya no existe.' : textoError(e, 'cargar la vaca'))
    }
  }, [id])
  useEffect(() => {
    cargar()
  }, [cargar])
  useEffect(() => {
    api.contactosGasto().then(setContactos).catch(() => {})
  }, [])
  // Otras personas cambian esto (un «ya pagué» desde el enlace, un gasto nuevo): al volver a la app se pone al día solo.
  useEffect(() => {
    const alVolver = () => document.visibilityState === 'visible' && cargar()
    document.addEventListener('visibilitychange', alVolver)
    return () => document.removeEventListener('visibilitychange', alVolver)
  }, [cargar])
  useEffect(() => {
    if (c) setDatosPago(c.datos_pago || '')
  }, [c?.datos_pago]) // eslint-disable-line react-hooks/exhaustive-deps

  const cuentaDestino = cuentas.find((x) => x.id === c?.cuenta_id)

  async function pagar(p, monto) {
    try {
      await api.pagarColecta(id, p.aporte_id, {
        monto: monto || undefined,
        registrar_ingreso: Boolean(cuentaDestino) && alCuenta,
      })
      setParcial(null)
      await cargar()
      if (cuentaDestino && alCuenta) recargar?.()
      avisar(`Pago de ${p.nombre} registrado`, 'ok')
    } catch (e) {
      avisar(e.message || 'No se pudo registrar el pago. Intenta de nuevo.')
    }
  }

  async function deshacer(p, pago) {
    const ok = await confirmar(
      `¿Deshacer el pago de ${formatMoneda(pago.monto, c.moneda)} de ${p.nombre}?${pago.registrado_en_cuenta ? ' También se quita el ingreso de tu cuenta.' : ''}`,
      { confirmarTexto: 'Deshacer' }
    )
    if (!ok) return
    try {
      await api.deshacerPagoColecta(id, pago.id)
      await cargar()
      if (pago.registrado_en_cuenta) recargar?.()
    } catch (e) {
      avisar(e.message || 'No se pudo deshacer el pago. Intenta de nuevo.')
    }
  }

  async function guardarDatosPago() {
    try {
      await api.editarColecta(id, { datos_pago: datosPago.trim() })
      avisar('Guardado', 'ok')
      await cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo guardar. Intenta de nuevo.')
    }
  }

  async function descartarAviso(p) {
    try {
      await api.descartarAvisoColecta(id, p.aporte_id)
      await cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo descartar el aviso. Intenta de nuevo.')
    }
  }

  async function compartir() {
    try {
      await api.compartirColecta(id)
      await cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo crear el enlace. Intenta de nuevo.')
    }
  }

  async function dejarDeCompartir() {
    const ok = await confirmar('El enlace dejará de funcionar para quienes lo tengan.', { confirmarTexto: 'Dejar de compartir' })
    if (!ok) return
    try {
      await api.dejarDeCompartirColecta(id)
      await cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo apagar el enlace. Intenta de nuevo.')
    }
  }

  async function copiar(enlace) {
    try {
      await navigator.clipboard.writeText(enlace)
      avisar('Enlace copiado', 'ok')
    } catch {
      avisar('No se pudo copiar. Mantén presionado el enlace para copiarlo.')
    }
  }

  async function cambiarEstado() {
    try {
      await api.editarColecta(id, { estado: c.estado === 'abierta' ? 'cerrada' : 'abierta' })
      await cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo cambiar el estado. Intenta de nuevo.')
    }
  }

  async function borrar() {
    const ok = await confirmar(
      `¿Borrar la vaca "${c.nombre}"? Los ingresos que ya registraste en tus cuentas no se tocan.`,
      { confirmarTexto: 'Borrar', peligro: true }
    )
    if (!ok) return
    try {
      await api.eliminarColecta(id)
      navigate('/colectas', { replace: true })
    } catch (e) {
      avisar(e.message || 'No se pudo borrar la vaca. Intenta de nuevo.')
    }
  }

  async function agregar(contactoId) {
    try {
      await api.agregarParticipanteColecta(id, { contacto_id: contactoId })
      setAgregando(false)
      await cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo agregar a la persona. Intenta de nuevo.')
    }
  }

  async function quitar(p) {
    const ok = await confirmar(`¿Quitar a ${p.nombre} de la vaca?`, { confirmarTexto: 'Quitar' })
    if (!ok) return
    try {
      await api.quitarParticipanteColecta(id, p.aporte_id)
      await cargar()
    } catch (e) {
      avisar(e.message || 'No se pudo quitar a la persona. Intenta de nuevo.')
    }
  }

  const Cabecera = (
    <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
      <button
        onClick={() => navigate('/colectas')}
        className="w-11 h-11 shrink-0 rounded-full bg-paper-raised border border-line flex items-center justify-center"
        aria-label="Volver"
      >
        <ArrowLeft size={20} />
      </button>
      <h1 className="text-2xl font-semibold truncate">{c?.nombre || 'Vaca'}</h1>
    </header>
  )

  if (error) {
    return (
      <div className="flex-1 overflow-y-auto pb-8 screen-enter">
        {Cabecera}
        <p className="px-5 mt-6 text-sm text-danger" role="alert">{error}</p>
        <button onClick={cargar} className="px-5 text-sm text-accent font-medium mt-1">Reintentar</button>
      </div>
    )
  }
  if (!c) {
    return (
      <div className="flex-1 overflow-y-auto pb-8 screen-enter">
        {Cabecera}
        <EsqueletoLista filas={3} className="mx-5 mt-6" etiqueta="Cargando vaca" />
      </div>
    )
  }

  const pct = porcentaje(c.recogido, c.meta)
  const enlace = c.token_publico ? enlacePublicoColecta(c.token_publico) : ''
  const disponibles = contactos.filter((x) => !c.participantes.some((p) => p.participante_id === x.id))

  return (
    <div className="flex-1 overflow-y-auto pb-10 screen-enter">
      {Cabecera}

      <section className="px-5 mt-2">
        <div className="rounded-2xl border border-line bg-paper-raised p-4">
          <p className="text-2xl font-semibold tabular-nums">{formatMoneda(c.recogido, c.moneda)}</p>
          <p className="text-xs text-ink-soft tabular-nums">de {formatMoneda(c.meta, c.moneda)} · faltan {formatMoneda(c.falta, c.moneda)}</p>
          <div className="mt-3 h-2.5 rounded-full bg-line overflow-hidden" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Avance">
            <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
          </div>
          <p className="text-xs text-ink-soft mt-2">
            {c.pagaron} de {c.personas} pagaron
            {c.fecha_limite ? ` · límite ${new Date(c.fecha_limite).toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })}` : ''}
            {c.estado === 'cerrada' ? ' · cerrada' : ''}
          </p>
        </div>
        {cuentaDestino && (
          <label className="mt-3 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={alCuenta} onChange={(e) => setAlCuenta(e.target.checked)} className="w-5 h-5" />
            Registrar cada pago como ingreso en {cuentaDestino.nombre}
          </label>
        )}
      </section>

      <ul className="px-5 mt-4 flex flex-col gap-2">
        {c.participantes.map((p) => (
          <li key={p.aporte_id} className="rounded-2xl border border-line bg-paper-raised px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold truncate">{p.nombre}</p>
                <p className="text-xs text-ink-soft tabular-nums">
                  {formatMoneda(p.pagado, c.moneda)} de {formatMoneda(p.debe, c.moneda)}
                </p>
              </div>
              <span className={`shrink-0 text-xs font-semibold rounded-full px-2.5 py-1 ${COLOR_ESTADO[p.estado]}`}>
                {ETIQUETA_ESTADO[p.estado]}
              </span>
            </div>

            {p.avisado && p.estado !== 'pagado' && (
              <div className="mt-2 rounded-xl bg-accent-soft px-3 py-2 flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-accent">Dice que ya pagó</span>
                <div className="flex gap-3 text-xs">
                  <button onClick={() => pagar(p)} className="min-h-9 font-semibold text-accent underline">Confirmar</button>
                  <button onClick={() => descartarAviso(p)} className="min-h-9 text-ink-soft underline">No fue</button>
                </div>
              </div>
            )}

            {p.estado !== 'pagado' && (
              <div className="flex flex-wrap gap-2 mt-2">
                <button onClick={() => pagar(p)} className="flex-1 min-w-[7rem] rounded-xl bg-ink text-paper text-xs font-semibold py-2 flex items-center justify-center gap-1.5">
                  <Check size={16} /> Pagó {formatMoneda(p.falta, c.moneda)}
                </button>
                <button
                  onClick={() => setParcial(parcial?.aporte_id === p.aporte_id ? null : { aporte_id: p.aporte_id, monto: '' })}
                  className="rounded-xl border border-line text-xs font-semibold px-3 py-2"
                >
                  Otro monto
                </button>
                <a
                  href={enlaceRecordatorioColecta({ nombre: p.nombre, telefono: p.telefono, falta: p.falta, moneda: c.moneda, colecta: c.nombre, enlace })}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-xl bg-accent-soft text-accent text-xs font-semibold px-3 py-2 flex items-center gap-1.5"
                >
                  <MessageCircle size={16} /> Recordar
                </a>
              </div>
            )}

            {parcial?.aporte_id === p.aporte_id && (
              <div className="flex gap-2 mt-2">
                <InputMonto
                  entero
                  aria-label={`Monto que pagó ${p.nombre}`}
                  value={parcial.monto}
                  onValor={(v) => setParcial({ ...parcial, monto: v })}
                  placeholder="Monto"
                  className="flex-1 rounded-xl border border-line bg-paper px-3 py-2 text-sm text-right tabular-nums outline-none focus:border-accent"
                />
                <button
                  onClick={() => Number(parcial.monto) > 0 && pagar(p, Number(parcial.monto))}
                  disabled={!(Number(parcial.monto) > 0)}
                  className="rounded-xl bg-ink text-paper text-xs font-semibold px-4 disabled:opacity-40"
                >
                  Guardar
                </button>
              </div>
            )}

            {p.pagos.length > 0 && (
              <ul className="mt-2 flex flex-col gap-1">
                {p.pagos.map((pg) => (
                  <li key={pg.id} className="flex items-center justify-between text-xs text-ink-soft">
                    <span className="tabular-nums">
                      {formatMoneda(pg.monto, c.moneda)} · {aFecha(pg.fecha)?.toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })}
                      {pg.registrado_en_cuenta ? ' · en tu cuenta' : ''}
                    </span>
                    <button onClick={() => deshacer(p, pg)} className="min-h-9 px-2 flex items-center gap-1 text-ink-soft" aria-label={`Deshacer pago de ${p.nombre}`}>
                      <Undo2 size={16} /> Deshacer
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {p.pagos.length === 0 && (
              <button onClick={() => quitar(p)} className="mt-1 text-[11px] text-ink-soft underline">
                Quitar de la vaca
              </button>
            )}
          </li>
        ))}
      </ul>

      <section className="px-5 mt-3">
        {!agregando ? (
          <button onClick={() => setAgregando(true)} className="text-sm text-accent font-medium">
            + Agregar a alguien
          </button>
        ) : (
          <div className="rounded-2xl border border-line bg-paper-raised p-3">
            {disponibles.length === 0 ? (
              <p className="text-sm text-ink-soft">Todos tus contactos ya están. Crea más desde “Nueva vaca”.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {disponibles.map((x) => (
                  <button key={x.id} onClick={() => agregar(x.id)} className="rounded-2xl border border-line px-3.5 py-2 text-sm font-medium">
                    {x.nombre}
                  </button>
                ))}
              </div>
            )}
            <button onClick={() => setAgregando(false)} className="mt-2 text-xs text-ink-soft">Cerrar</button>
          </div>
        )}
      </section>

      <section className="px-5 mt-6">
        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">¿Cómo te pagan?</p>
        <div className="flex gap-2">
          <input aria-label="Datos para pagarte" value={datosPago} onChange={(e) => setDatosPago(e.target.value)} maxLength={200} placeholder="Ej. Llave Bre-B @torneo · Nequi 300 123 4567" className="flex-1 min-w-0 rounded-2xl border border-line bg-paper-raised px-4 py-3 text-sm outline-none focus:border-accent" />
          <button onClick={guardarDatosPago} disabled={datosPago.trim() === (c.datos_pago || '')} className="shrink-0 bg-ink text-paper rounded-2xl px-4 text-sm font-semibold disabled:opacity-40">Guardar</button>
        </div>
        <p className="text-[11px] text-ink-soft mt-1">Lo verá quien tenga el enlace. Los pagos se hacen por fuera (Bre-B, Nequi, efectivo); CuadraMe solo lleva la cuenta.</p>
      </section>

      <section className="px-5 mt-6">
        <p className="text-xs text-ink-soft mb-2 font-medium uppercase tracking-wide">Compartir el avance</p>
        {!c.token_publico ? (
          <>
            <button onClick={compartir} className="w-full rounded-2xl border border-line bg-paper-raised py-3 text-sm font-semibold flex items-center justify-center gap-2">
              <Share2 size={16} /> Crear enlace para ver el avance
            </button>
            <p className="text-[11px] text-ink-soft mt-1">Solo lectura: nombre de la vaca, avance y quién pagó (solo nombre de pila). Sin tus cuentas ni movimientos.</p>
          </>
        ) : (
          <div className="rounded-2xl border border-line bg-paper-raised p-3">
            <p className="text-xs break-all text-ink-soft select-all">{enlace}</p>
            <div className="flex gap-2 mt-2">
              <button onClick={() => copiar(enlace)} className="flex-1 rounded-xl border border-line text-xs font-semibold py-2 flex items-center justify-center gap-1.5">
                <Copy size={16} /> Copiar
              </button>
              <a href={enlaceCompartirColecta({ colecta: c.nombre, enlace })} target="_blank" rel="noopener noreferrer" className="flex-1 rounded-xl bg-accent-soft text-accent text-xs font-semibold py-2 flex items-center justify-center gap-1.5">
                <MessageCircle size={16} /> Enviar por WhatsApp
              </a>
            </div>
            <button onClick={dejarDeCompartir} className="mt-2 text-xs text-ink-soft underline">Dejar de compartir</button>
          </div>
        )}
      </section>

      <div className="px-5 mt-8 flex items-center justify-between">
        <button onClick={cambiarEstado} className="text-sm text-ink-soft underline">
          {c.estado === 'abierta' ? 'Cerrar vaca' : 'Reabrir vaca'}
        </button>
        <button onClick={borrar} className="text-sm text-danger underline">Borrar vaca</button>
      </div>
    </div>
  )
}
