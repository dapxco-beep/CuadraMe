import { useEffect, useState } from 'react'
import { EsqueletoPantalla } from '../components/Esqueletos'
import { useParams } from 'react-router-dom'
import { useVolver } from '../lib/useVolver'
import { ArrowLeft, ArrowLeftRight, Pencil, Trash2, X } from 'lucide-react'
import Icono from '../components/Icono'
import { formatMoneda } from '../lib/format'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'
import { useCategorias } from '../lib/CategoriasContext'
import { useDialogos } from '../lib/DialogosContext'
import { esAuto } from '../lib/comercio'
import { HojaCambiarCategoria, InsigniaAuto } from '../components/CategorizacionAuto'
import { parchearEnCaches, quitarDeCaches } from '../lib/useEstadoLista'

const ETIQUETA_TIPO = { income: 'Ingreso', expense: 'Gasto', transfer: 'Transferencia' }

function fechaParaInput(fechaISO) {
  return fechaISO.slice(0, 10)
}

// Como pantalla (ruta /movimientos/:id) o, en pantallas anchas, como panel dentro de la lista
// (`embebido`): ahí no cambia de ruta, la lista sigue montada y `onCambio(actualizado | null,
// idEliminado)` le avisa de lo que se guardó o eliminó.
export default function DetalleMovimiento({ id: idProp, embebido = false, onCerrar, onCambio } = {}) {
  const params = useParams()
  const id = idProp ?? params.id
  const volver = useVolver('/movimientos')
  const { cuentas, recargar: recargarCuentas } = useCuentas()
  const { nombres: categorias, iconoDe } = useCategorias()
  const { confirmar, avisar } = useDialogos()
  const [movimiento, setMovimiento] = useState(null)
  const [noEncontrado, setNoEncontrado] = useState(false)
  const [eliminando, setEliminando] = useState(false)
  const [editando, setEditando] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [form, setForm] = useState(null)

  useEffect(() => {
    api
      .movimiento(id)
      .then(setMovimiento)
      .catch(() => setNoEncontrado(true))
  }, [id])

  const [cambiandoCategoria, setCambiandoCategoria] = useState(false)

  async function confirmarCategoria() {
    try {
      await api.confirmarCategorias([id])
      const nuevo = { ...movimiento, cat_confirmada: true, cat_origen: null }
      setMovimiento(nuevo)
      parchearEnCaches(nuevo)
      onCambio?.(nuevo)
    } catch (err) {
      avisar(err.message || 'No se pudo confirmar')
    }
  }

  const cuenta = cuentas.find((c) => c.id === movimiento?.cuenta_id)
  const esTransferencia = movimiento?.fuente === 'transferencia_interna'

  function empezarEdicion() {
    setForm({
      descripcion: movimiento.descripcion,
      monto: String(Math.round(movimiento.monto * 100) / 100),
      tipo: movimiento.tipo,
      categoria: movimiento.categoria,
      fecha: fechaParaInput(movimiento.fecha),
      cuenta_id: movimiento.cuenta_id,
      notas: movimiento.notas || '',
    })
    setEditando(true)
  }

  async function guardar() {
    const monto = Number(form.monto)
    if (!monto || monto <= 0) return avisar('Ingresa un monto válido')
    if (!form.descripcion.trim()) return avisar('Ingresa una descripción')

    setGuardando(true)
    try {
      const cambios = {
        descripcion: form.descripcion.trim(),
        monto,
        categoria: form.categoria,
        cuenta_id: form.cuenta_id,
        notas: form.notas,
      }
      // Importados de un extracto pueden venir como "transfer": ese tipo se respeta.
      if (movimiento.tipo !== 'transfer') cambios.tipo = form.tipo
      // La fecha solo se manda si el usuario la cambió, para no pisar la hora original.
      if (form.fecha !== fechaParaInput(movimiento.fecha)) cambios.fecha = `${form.fecha}T12:00:00`

      const actualizado = await api.editarMovimiento(id, cambios)
      setMovimiento(actualizado)
      parchearEnCaches(actualizado) // la lista, al volver, ya muestra el cambio sin recargarse
      onCambio?.(actualizado)
      await recargarCuentas()
      setEditando(false)
      avisar('Movimiento actualizado', 'ok')
    } catch (err) {
      avisar(err.message || 'No se pudo guardar')
    } finally {
      setGuardando(false)
    }
  }

  async function eliminar() {
    const ok = await confirmar(
      esTransferencia
        ? 'Se eliminarán las dos partes de la transferencia y el dinero volverá a la cuenta de origen.'
        : 'El saldo de la cuenta se ajustará como si este movimiento nunca hubiera existido.',
      { titulo: '¿Eliminar este movimiento?', confirmarTexto: 'Eliminar', peligro: true }
    )
    if (!ok) return

    setEliminando(true)
    try {
      await api.eliminarMovimiento(id)
      quitarDeCaches(id)
      onCambio?.(null, id)
      await recargarCuentas()
      // Volver a la lista tal como estaba (filtros y scroll), no a una lista nueva
      if (embebido) onCerrar?.()
      else volver()
    } catch (err) {
      setEliminando(false)
      avisar(err.message || 'No se pudo eliminar')
    }
  }

  if (noEncontrado) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 px-8 text-center">
        <p className="text-sm text-ink-soft">No encontramos este movimiento.</p>
        <button onClick={embebido ? onCerrar : volver} className="text-sm text-accent font-medium">
          Volver a movimientos
        </button>
      </div>
    )
  }

  if (!movimiento) {
    return <EsqueletoPantalla variante="texto" etiqueta="Cargando el movimiento" />
  }

  const signo = movimiento.tipo === 'income' ? '+' : movimiento.tipo === 'expense' ? '-' : ''
  const campo =
    'w-full rounded-xl border border-line bg-paper px-3 py-2.5 text-sm outline-none focus:border-accent'

  return (
    <div className={embebido ? 'flex flex-col pb-4' : 'flex-1 overflow-y-auto flex flex-col pb-6 screen-enter'}>
      <header className={`px-5 pb-2 flex items-center gap-3 ${embebido ? 'pt-1' : 'pantalla-top'}`}>
        <button
          onClick={embebido ? onCerrar : volver}
          aria-label={embebido ? 'Cerrar detalle' : 'Volver'}
          className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
        >
          {embebido ? <X size={20} /> : <ArrowLeft size={20} />}
        </button>
        <h1 className="text-lg font-semibold flex-1">Detalle del movimiento</h1>
        {!esTransferencia && !editando && (
          <button
            onClick={empezarEdicion}
            aria-label="Editar movimiento"
            className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          >
            <Pencil size={16} />
          </button>
        )}
      </header>

      <div className="flex flex-col items-center justify-center py-8">
        <span
          className="w-16 h-16 rounded-full bg-accent-soft flex items-center justify-center text-2xl mb-4"
          aria-hidden="true"
        >
          {esTransferencia ? <Icono icono={ArrowLeftRight} tam="lg" /> : iconoDe(movimiento.categoria)}
        </span>
        <p className={`text-4xl font-bold ${movimiento.tipo === 'income' ? 'text-accent' : 'text-ink'}`}>
          {signo}
          {formatMoneda(movimiento.monto, cuenta?.moneda)}
        </p>
        <p className="text-sm text-ink-soft mt-2 text-center px-6">{movimiento.descripcion}</p>
      </div>

      {editando ? (
        <div className="mx-5 rounded-2xl bg-paper-raised border border-line p-4 space-y-3 pop-in">
          <label className="block">
            <span className="text-xs text-ink-soft">Descripción</span>
            <input
              className={`${campo} mt-1`}
              value={form.descripcion}
              onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-xs text-ink-soft">Monto</span>
            <input
              className={`${campo} mt-1`}
              inputMode="decimal"
              value={form.monto}
              onChange={(e) => setForm({ ...form, monto: e.target.value.replace(/[^\d.]/g, '') })}
            />
          </label>
          {movimiento.tipo !== 'transfer' && (
            <div className="flex gap-2" role="group" aria-label="Tipo de movimiento">
              {['expense', 'income'].map((t) => (
                <button
                  key={t}
                  type="button"
                  aria-pressed={form.tipo === t}
                  onClick={() => setForm({ ...form, tipo: t })}
                  className={`flex-1 rounded-xl py-2.5 text-sm font-semibold border ${
                    form.tipo === t ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
                  }`}
                >
                  {ETIQUETA_TIPO[t]}
                </button>
              ))}
            </div>
          )}
          <label className="block">
            <span className="text-xs text-ink-soft">Categoría</span>
            <select
              className={`${campo} mt-1`}
              value={form.categoria}
              onChange={(e) => setForm({ ...form, categoria: e.target.value })}
            >
              {[...new Set([form.categoria, ...categorias])].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
          {cuentas.length > 1 && (
            <label className="block">
              <span className="text-xs text-ink-soft">Cuenta</span>
              <select
                className={`${campo} mt-1`}
                value={form.cuenta_id}
                onChange={(e) => setForm({ ...form, cuenta_id: e.target.value })}
              >
                {cuentas.map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre}</option>
                ))}
              </select>
            </label>
          )}
          <label className="block">
            <span className="text-xs text-ink-soft">Fecha</span>
            <input
              type="date"
              className={`${campo} mt-1`}
              value={form.fecha}
              onChange={(e) => setForm({ ...form, fecha: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-xs text-ink-soft">Notas</span>
            <input
              className={`${campo} mt-1`}
              value={form.notas}
              onChange={(e) => setForm({ ...form, notas: e.target.value })}
            />
          </label>
          <div className="flex gap-3 pt-1">
            <button
              onClick={() => setEditando(false)}
              disabled={guardando}
              className="flex-1 rounded-2xl border border-line py-3 text-sm font-semibold"
            >
              Cancelar
            </button>
            <button
              onClick={guardar}
              disabled={guardando}
              className="flex-1 rounded-2xl bg-ink text-paper py-3 text-sm font-semibold disabled:opacity-60"
            >
              {guardando ? 'Guardando...' : 'Guardar cambios'}
            </button>
          </div>
        </div>
      ) : (
        <div className="mx-5 rounded-2xl bg-paper-raised border border-line divide-y divide-line">
          <Fila label="Categoría" valor={movimiento.categoria} />
          {esAuto(movimiento) && (
            <div className="px-4 py-3.5">
              <p className="text-sm">
                La app puso esta categoría sola <InsigniaAuto movimiento={movimiento} />
              </p>
              <div className="flex gap-2 mt-3">
                <button
                  onClick={confirmarCategoria}
                  className="flex-1 rounded-xl bg-accent text-white py-2.5 text-sm font-semibold"
                >
                  Está bien
                </button>
                <button
                  onClick={() => setCambiandoCategoria(true)}
                  className="flex-1 rounded-xl border border-line py-2.5 text-sm font-semibold"
                >
                  Cambiar
                </button>
              </div>
            </div>
          )}
          {cuenta && <Fila label="Cuenta" valor={cuenta.nombre} />}
          <Fila label="Fecha" valor={new Date(movimiento.fecha).toLocaleString('es-CO')} />
          <Fila label="Tipo" valor={ETIQUETA_TIPO[movimiento.tipo] || movimiento.tipo} />
          <Fila label="Origen" valor={movimiento.fuente} />
          {movimiento.notas && !esTransferencia && <Fila label="Notas" valor={movimiento.notas} />}
        </div>
      )}

      {cambiandoCategoria && (
        <HojaCambiarCategoria
          movimiento={movimiento}
          onClose={() => setCambiandoCategoria(false)}
          onHecho={(r, categoria) => {
            setCambiandoCategoria(false)
            const nuevo = { ...movimiento, categoria, cat_confirmada: true, cat_origen: null }
            setMovimiento(nuevo)
            parchearEnCaches(nuevo)
            onCambio?.(nuevo)
            avisar(
              r.actualizados > 1 ? `Listo: ${r.actualizados} movimientos movidos y regla creada` : 'Categoría actualizada',
              'ok'
            )
          }}
        />
      )}

      {!editando && (
        <div className="px-5 mt-6">
          <button
            onClick={eliminar}
            disabled={eliminando}
            className="w-full flex items-center justify-center gap-2 rounded-2xl border border-danger/30 bg-danger-soft text-danger font-semibold py-4 text-[15px] disabled:opacity-60"
          >
            <Trash2 size={16} /> {eliminando ? 'Eliminando...' : 'Eliminar movimiento'}
          </button>
        </div>
      )}
    </div>
  )
}

function Fila({ label, valor }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3.5">
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="text-sm font-medium text-right">{valor}</p>
    </div>
  )
}
