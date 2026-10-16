import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, Pencil, Smartphone, Trash2, X } from 'lucide-react'
import { api } from '../lib/api'
import { fechaHoraMovimiento, fechaDeMovimiento } from '../lib/fechaMovimiento'
import { useBloqueo } from '../lib/BloqueoContext'
import { useCategorias } from '../lib/CategoriasContext'
import { useCuentas } from '../lib/CuentasContext'
import { useDialogos } from '../lib/DialogosContext'
import Hoja from './Hoja'
import RecordarRegla, { RECORDAR_INICIAL } from './RecordarRegla'
import {
  debeMostrarBandeja,
  estadoBandejaGuardado,
  marcarBandejaAbierta,
  recordarBandejaCerrada,
} from '../lib/bandeja'
import InputMonto from './InputMonto'


/**
 * Hoja inferior "Detectamos N movimientos: ¿son tuyos?". Aparece al abrir la app
 * y al volver a primer plano si hay movimientos que llegaron solos (Wallet,
 * atajos) sin confirmar. Esos movimientos YA cuentan en los saldos:
 *   - Confirmar los deja como están.
 *   - Editar cambia monto/categoría/cuenta (y los confirma).
 *   - Descartar los elimina y devuelve el saldo.
 * Si la cierras, no vuelve a salir durante una hora salvo que lleguen nuevos.
 */
export default function BandejaPorConfirmar() {
  const [pendientes, setPendientes] = useState([])
  const [abierta, setAbierta] = useState(false)
  const [editandoId, setEditandoId] = useState(null)
  const [ocupado, setOcupado] = useState(false)
  const { fmt } = useBloqueo()
  const { cuentas, recargar } = useCuentas()
  const { confirmar, avisar } = useDialogos()
  const abiertaRef = useRef(false)
  abiertaRef.current = abierta

  const revisar = useCallback(async () => {
    try {
      const lista = await api.movimientosPorConfirmar()
      if (abiertaRef.current) {
        // Ya está abierta: solo se actualiza la lista (puede haber llegado uno nuevo).
        setPendientes(lista)
        if (lista.length === 0) cerrar(lista)
        return
      }
      if (debeMostrarBandeja(lista, estadoBandejaGuardado())) {
        setPendientes(lista)
        setAbierta(true)
        marcarBandejaAbierta(true)
      }
    } catch {
      /* sin red o sin sesión: la bandeja simplemente no aparece */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    revisar()
    const alVolver = () => {
      if (document.visibilityState === 'visible') revisar()
    }
    document.addEventListener('visibilitychange', alVolver)
    return () => {
      document.removeEventListener('visibilitychange', alVolver)
      marcarBandejaAbierta(false)
    }
  }, [revisar])

  function cerrar(lista = pendientes) {
    recordarBandejaCerrada(lista)
    setAbierta(false)
    setEditandoId(null)
    marcarBandejaAbierta(false)
  }

  function avisarCambio() {
    recargar()
    window.dispatchEvent(new CustomEvent('cuadrame:movimientos-cambio'))
  }

  function quitar(ids) {
    const resto = pendientes.filter((m) => !ids.includes(m.id))
    setPendientes(resto)
    if (resto.length === 0) cerrar(resto)
  }

  async function confirmarUno(m) {
    setOcupado(true)
    try {
      await api.confirmarCategorias([m.id])
      quitar([m.id])
      avisarCambio()
    } catch (err) {
      avisar(err.message || 'No se pudo confirmar. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setOcupado(false)
    }
  }

  async function confirmarTodos() {
    setOcupado(true)
    try {
      await api.confirmarCategorias(pendientes.map((m) => m.id))
      quitar(pendientes.map((m) => m.id))
      avisarCambio()
    } catch (err) {
      avisar(err.message || 'No se pudieron confirmar. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setOcupado(false)
    }
  }

  async function descartarUno(m) {
    const ok = await confirmar('Lo eliminamos y el saldo de tu cuenta vuelve a como estaba.', {
      titulo: `¿Descartar "${m.descripcion}"?`,
      confirmarTexto: 'Descartar',
      peligro: true,
    })
    if (!ok) return
    setOcupado(true)
    try {
      await api.eliminarMovimiento(m.id)
      quitar([m.id])
      avisarCambio()
    } catch (err) {
      avisar(err.message || 'No se pudo descartar. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setOcupado(false)
    }
  }

  async function descartarTodos() {
    const ok = await confirmar(
      `Eliminamos los ${pendientes.length} movimientos y los saldos vuelven a como estaban.`,
      { titulo: '¿Descartar todos?', confirmarTexto: 'Descartar todos', peligro: true }
    )
    if (!ok) return
    setOcupado(true)
    const hechos = []
    try {
      for (const m of pendientes) {
        await api.eliminarMovimiento(m.id)
        hechos.push(m.id)
      }
    } catch (err) {
      avisar(err.message || 'No se pudieron descartar todos. Revisa tu conexión e intenta de nuevo.')
    } finally {
      if (hechos.length) {
        quitar(hechos)
        avisarCambio()
      }
      setOcupado(false)
    }
  }

  async function guardarEdicion(m, cambios, aprender) {
    setOcupado(true)
    try {
      await api.editarMovimiento(m.id, cambios) // al enviar categoría, el backend lo da por confirmado
      if (aprender?.recordar) {
        // Aprende el comercio: la próxima vez ya sabrá la categoría. Si falla, no se pierde la edición.
        try {
          await api.aprenderRegla({
            descripcion: m.descripcion, categoria: cambios.categoria, aplicar_anteriores: !!aprender.anteriores,
          })
        } catch {
          /* la regla es un extra: el movimiento ya quedó guardado */
        }
      }
      setEditandoId(null)
      quitar([m.id])
      avisarCambio()
    } catch (err) {
      avisar(err.message || 'No se pudo guardar. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setOcupado(false)
    }
  }

  if (!abierta || pendientes.length === 0) return null

  const n = pendientes.length
  return (
    <Hoja onCerrar={() => cerrar()} capa="z-[45]" testId="bandeja-por-confirmar" ariaLabel="Movimientos por confirmar">
      <div className="flex items-start justify-between gap-3 mb-1">
        <div className="flex items-center gap-2.5">
          <span className="w-9 h-9 rounded-xl bg-accent-soft flex items-center justify-center shrink-0">
            <Smartphone size={20} className="text-accent" />
          </span>
          <h2 className="text-lg font-semibold leading-tight">
            Detectamos {n} {n === 1 ? 'movimiento' : 'movimientos'}: ¿son tuyos?
          </h2>
        </div>
        <button
          onClick={() => cerrar()}
          className="w-11 h-11 shrink-0 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Cerrar"
        >
          <X size={16} />
        </button>
      </div>
      <p className="text-xs text-ink-soft mb-4">
        Ya los sumamos a tus saldos. Confírmalos, corrígelos o descártalos si no los reconoces.
      </p>

      <ul className="space-y-2.5">
        {pendientes.map((m) =>
          editandoId === m.id ? (
            <FormEdicion
              key={m.id}
              m={m}
              cuentas={cuentas}
              ocupado={ocupado}
              onCancelar={() => setEditandoId(null)}
              onGuardar={(cambios, aprender) => guardarEdicion(m, cambios, aprender)}
            />
          ) : (
            <li key={m.id} className="rounded-2xl border border-line bg-paper-raised p-3.5" data-testid="tarjeta-por-confirmar">
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold break-words line-clamp-3">{m.descripcion}</p>
                  <p className="text-xs text-ink-soft mt-0.5 break-words">
                    {[fechaHoraMovimiento(fechaDeMovimiento(m)), cuentas.find((c) => c.id === m.cuenta_id)?.nombre || 'Cuenta', m.categoria].filter(Boolean).join(' · ')}
                  </p>
                </div>
                <p className="text-sm font-bold shrink-0 whitespace-nowrap tabular-nums">
                  {m.tipo === 'income' ? '+' : '-'}
                  {fmt(m.monto)}
                </p>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-3">
                <button
                  onClick={() => confirmarUno(m)}
                  disabled={ocupado}
                  className="flex items-center justify-center gap-1.5 rounded-xl bg-accent text-paper-raised text-xs font-semibold py-2.5 disabled:opacity-60"
                >
                  <Check size={16} /> Es mío
                </button>
                <button
                  onClick={() => setEditandoId(m.id)}
                  disabled={ocupado}
                  className="flex items-center justify-center gap-1.5 rounded-xl border border-line text-xs font-semibold py-2.5 disabled:opacity-60"
                >
                  <Pencil size={16} /> Editar
                </button>
                <button
                  onClick={() => descartarUno(m)}
                  disabled={ocupado}
                  className="flex items-center justify-center gap-1.5 rounded-xl border border-line text-danger text-xs font-semibold py-2.5 disabled:opacity-60"
                >
                  <Trash2 size={16} /> No es mío
                </button>
              </div>
            </li>
          )
        )}
      </ul>

      {n > 1 && (
        <div className="flex gap-2 mt-4">
          <button
            onClick={confirmarTodos}
            disabled={ocupado}
            className="flex-1 bg-ink text-paper font-semibold rounded-2xl py-3.5 text-sm disabled:opacity-60"
          >
            Confirmar todos ({n})
          </button>
          <button
            onClick={descartarTodos}
            disabled={ocupado}
            className="rounded-2xl border border-line text-danger font-semibold px-4 text-sm disabled:opacity-60"
          >
            Descartar todos
          </button>
        </div>
      )}
      <button onClick={() => cerrar()} className="w-full mt-3 text-sm text-ink-soft font-medium py-2">
        Ahora no
      </button>
    </Hoja>
  )
}

function FormEdicion({ m, cuentas, ocupado, onCancelar, onGuardar }) {
  const { nombres } = useCategorias()
  const [monto, setMonto] = useState(String(Math.round(m.monto * 100) / 100))
  const [categoria, setCategoria] = useState(m.categoria)
  const [cuentaId, setCuentaId] = useState(m.cuenta_id)
  const [aprender, setAprender] = useState(RECORDAR_INICIAL) // «Recordar» va marcado si cambia la categoría
  const [error, setError] = useState('')
  const opciones = [...new Set([...nombres, m.categoria])].filter((c) => c !== 'Transferencias')

  function guardar() {
    const valor = Number(String(monto).replace(',', '.'))
    if (!valor || valor <= 0) return setError('Escribe un monto válido')
    onGuardar({ monto: valor, categoria, cuenta_id: cuentaId }, categoria !== m.categoria ? aprender : null)
  }

  const campo = 'w-full rounded-xl border border-line bg-paper px-3 py-2.5 text-sm outline-none focus:border-accent'
  return (
    <li className="rounded-2xl border border-accent/40 bg-paper-raised p-3.5 space-y-2.5" data-testid="edicion-por-confirmar">
      <p className="text-sm font-semibold break-words line-clamp-3">{m.descripcion}</p>
      <label className="block">
        <span className="text-[11px] text-ink-soft">Monto</span>
        <InputMonto
          value={monto}
          onValor={setMonto}
          aria-label="Monto"
          className={campo}
        />
      </label>
      <label className="block">
        <span className="text-[11px] text-ink-soft">Categoría</span>
        <select value={categoria} onChange={(e) => setCategoria(e.target.value)} aria-label="Categoría" className={campo}>
          {opciones.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </label>
      {categoria !== m.categoria && <RecordarRegla descripcion={m.descripcion} valor={aprender} onChange={setAprender} />}
      <label className="block">
        <span className="text-[11px] text-ink-soft">Cuenta</span>
        <select value={cuentaId} onChange={(e) => setCuentaId(e.target.value)} aria-label="Cuenta" className={campo}>
          {cuentas.map((c) => (
            <option key={c.id} value={c.id}>{c.nombre}</option>
          ))}
        </select>
      </label>
      {error && <p className="text-xs text-danger">{error}</p>}
      <div className="flex gap-2">
        <button onClick={guardar} disabled={ocupado} className="flex-1 bg-ink text-paper font-semibold rounded-xl py-2.5 text-sm disabled:opacity-60">
          Guardar y confirmar
        </button>
        <button onClick={onCancelar} className="px-4 rounded-xl border border-line text-sm font-medium">
          Cancelar
        </button>
      </div>
    </li>
  )
}
