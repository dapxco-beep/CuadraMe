import { useState } from 'react'
import { EsqueletoLista } from '../components/Esqueletos'
import { useVolver } from '../lib/useVolver'
import { ArrowDown, ArrowLeft, ArrowUp, Check, ChevronDown, ChevronRight, Eye, EyeOff, Plus, Trash2, X } from 'lucide-react'
import { api } from '../lib/api'
import { useCategorias } from '../lib/CategoriasContext'
import { useDialogos } from '../lib/DialogosContext'
import SelectorEmoji from '../components/SelectorEmoji'
import Hoja from '../components/Hoja'
import SubcategoriasDeCategoria from '../components/SubcategoriasDeCategoria'

const TIPOS = [
  { id: 'gasto', etiqueta: 'Gasto' },
  { id: 'ingreso', etiqueta: 'Ingreso' },
  { id: 'ambos', etiqueta: 'Ambos' },
]
const ETIQUETA_TIPO = { gasto: 'Gasto', ingreso: 'Ingreso', ambos: 'Gasto e ingreso' }
// Paleta corta y apagada, coherente con la marca; el color es opcional.
const COLORES = ['#d9622b', '#d9a441', '#2f6b3f', '#2f7f9a', '#6a5acd', '#b0447a', '#7a6a55']

export default function Categorias() {
  const volver = useVolver('/perfil')
  const { categorias, cargando, recargar } = useCategorias()
  const [mostrarOcultas, setMostrarOcultas] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [editando, setEditando] = useState(null)
  const { avisar } = useDialogos()

  const activas = categorias.filter((c) => c.activa).sort((a, b) => a.orden - b.orden)
  const ocultas = categorias.filter((c) => !c.activa).sort((a, b) => a.orden - b.orden)

  async function toggleActiva(cat) {
    try {
      await api.editarCategoria(cat.id, { activa: !cat.activa })
      recargar()
    } catch (err) {
      avisar(err.message || 'No se pudo cambiar. Revisa tu conexión e intenta de nuevo.')
    }
  }

  async function mover(cat, delta) {
    const ids = activas.map((c) => c.id)
    const i = ids.indexOf(cat.id)
    const j = i + delta
    if (j < 0 || j >= ids.length) return
    ;[ids[i], ids[j]] = [ids[j], ids[i]]
    try {
      await api.reordenarCategorias(ids)
      recargar()
    } catch (err) {
      avisar(err.message || 'No se pudo reordenar. Revisa tu conexión e intenta de nuevo.')
    }
  }

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-6 pantalla-top pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-xl font-bold">Categorías</h1>
        </div>
        <button
          onClick={() => setMostrarForm(true)}
          className="w-11 h-11 rounded-full bg-accent text-paper-raised flex items-center justify-center"
          aria-label="Nueva categoría"
        >
          <Plus size={20} />
        </button>
      </header>

      <p className="mx-6 mt-2 text-xs text-ink-soft">
        Crea las tuyas con el nombre y el emoji que quieras, cámbialas de orden o escóndelas si no las usas.
        Ocultar no borra nada: tus movimientos conservan su categoría y puedes reactivarla cuando quieras.
      </p>

      <div className="mx-6 mt-4 flex items-center justify-between gap-3">
        <p className="text-xs text-ink-soft font-medium uppercase tracking-wide" data-testid="contador-categorias">
          {activas.length} {activas.length === 1 ? 'activa' : 'activas'} · {ocultas.length}{' '}
          {ocultas.length === 1 ? 'oculta' : 'ocultas'}
        </p>
        <label className="flex items-center gap-2 text-xs font-medium text-ink cursor-pointer">
          Mostrar ocultas
          <button
            type="button"
            role="switch"
            aria-checked={mostrarOcultas}
            aria-label="Mostrar ocultas"
            onClick={() => setMostrarOcultas((v) => !v)}
            className={`relative w-10 h-6 rounded-full transition-colors ${mostrarOcultas ? 'bg-accent' : 'bg-ink-soft/35'}`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                mostrarOcultas ? 'translate-x-4' : ''
              }`}
            />
          </button>
        </label>
      </div>

      {cargando && categorias.length === 0 ? (
        <EsqueletoLista filas={6} className="mx-6 mt-6" etiqueta="Cargando categorías" />
      ) : (
        <>
          <div className="mx-6 mt-3 rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
            {activas.map((c, i) => (
              <FilaCategoria
                key={c.id}
                c={c}
                onEditar={() => setEditando(c)}
                onToggle={() => toggleActiva(c)}
                onSubir={i > 0 ? () => mover(c, -1) : null}
                onBajar={i < activas.length - 1 ? () => mover(c, 1) : null}
              />
            ))}
            {activas.length === 0 && (
              <p className="px-4 py-5 text-sm text-ink-soft text-center">
                No tienes categorías activas. Reactiva una de las ocultas o crea una nueva.
              </p>
            )}
          </div>

          {ocultas.length > 0 && mostrarOcultas && (
            <section aria-label="Categorías ocultas">
              <p className="mx-6 mt-5 text-xs text-ink-soft font-medium uppercase tracking-wide">
                Ocultas ({ocultas.length})
              </p>
              <div className="mx-6 mt-2 rounded-2xl bg-paper-raised border border-line divide-y divide-line overflow-hidden">
                {ocultas.map((c) => (
                  <FilaCategoria key={c.id} c={c} onEditar={() => setEditando(c)} onToggle={() => toggleActiva(c)} />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {mostrarForm && (
        <FormCategoria
          onClose={() => setMostrarForm(false)}
          onGuardada={() => {
            setMostrarForm(false)
            recargar()
          }}
        />
      )}

      {editando && (
        <FormCategoria
          categoria={editando}
          activas={activas}
          onClose={() => setEditando(null)}
          onGuardada={() => {
            setEditando(null)
            recargar()
          }}
          onEliminada={() => {
            setEditando(null)
            recargar()
          }}
        />
      )}
    </div>
  )
}

function FilaCategoria({ c, onEditar, onToggle, onSubir, onBajar }) {
  const { subsDe } = useCategorias()
  const [abierta, setAbierta] = useState(false)
  // Las categorías que la app maneja sola (intereses, 4x1000...) no admiten subcategorías.
  const admite = c.activa && !c.es_sistema
  const nSubs = subsDe ? subsDe(c.nombre).length : 0
  return (
    <>
    <div className={`flex flex-wrap items-center gap-x-1 pl-4 pr-2 py-3 ${!c.activa ? 'opacity-70' : ''}`}>
      <button onClick={onEditar} className="flex items-center gap-3 flex-1 min-w-[10rem] text-left" aria-label={`Editar ${c.nombre}`}>
        <span
          className="w-10 h-10 shrink-0 rounded-xl flex items-center justify-center text-xl bg-accent-soft"
          style={c.color ? { backgroundColor: `${c.color}26`, boxShadow: `inset 0 0 0 1.5px ${c.color}` } : undefined}
          aria-hidden="true"
        >
          {c.icono}
        </span>
        <div className="min-w-0">
          <p className="text-sm font-medium line-clamp-2">{c.nombre}</p>
          <p className="text-[11px] text-ink-soft line-clamp-2">
            {[c.es_base ? 'Base' : null, ETIQUETA_TIPO[c.tipo] || null, `${c.movimientos || 0} mov.`]
              .filter(Boolean)
              .join(' · ')}
          </p>
        </div>
      </button>
      {/* Los botones de la derecha bajan a su propia línea cuando el nombre no cabe (celulares angostos) */}
      <div className="ml-auto flex items-center shrink-0">
      {admite && (
        <button
          onClick={() => setAbierta((v) => !v)}
          aria-expanded={abierta}
          className="shrink-0 h-11 min-w-[44px] px-1 flex items-center justify-center gap-0.5 text-xs text-ink-soft"
          aria-label={`Subcategorías de ${c.nombre}`}
        >
          {nSubs > 0 && <span>{nSubs}</span>}
          {abierta ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>
      )}
      {onSubir !== undefined && (
        <div className="flex shrink-0">
          <button
            onClick={onSubir || undefined}
            disabled={!onSubir}
            className="w-11 h-11 flex items-center justify-center text-ink-soft disabled:opacity-25"
            aria-label={`Subir ${c.nombre}`}
          >
            <ArrowUp size={16} />
          </button>
          <button
            onClick={onBajar || undefined}
            disabled={!onBajar}
            className="w-11 h-11 flex items-center justify-center text-ink-soft disabled:opacity-25"
            aria-label={`Bajar ${c.nombre}`}
          >
            <ArrowDown size={16} />
          </button>
        </div>
      )}
      {c.activa ? (
        <button
          onClick={onToggle}
          className="w-11 h-11 shrink-0 flex items-center justify-center text-ink-soft"
          aria-label={`Ocultar ${c.nombre}`}
        >
          <Eye size={16} />
        </button>
      ) : (
        <button
          onClick={onToggle}
          className="shrink-0 flex items-center gap-1 text-xs font-semibold text-accent px-3 h-9"
          aria-label={`Reactivar ${c.nombre}`}
        >
          <EyeOff size={16} /> Reactivar
        </button>
      )}
      </div>
    </div>
    {admite && abierta && <SubcategoriasDeCategoria categoria={c} />}
    </>
  )
}

function FormCategoria({ categoria, activas = [], onClose, onGuardada, onEliminada }) {
  const esEdicion = !!categoria
  const [nombre, setNombre] = useState(categoria?.nombre || '')
  const [icono, setIcono] = useState(categoria?.icono || '🏷️')
  const [tipo, setTipo] = useState(categoria?.tipo || 'ambos')
  const [color, setColor] = useState(categoria?.color || '')
  const [guardando, setGuardando] = useState(false)
  const [eliminando, setEliminando] = useState(false)
  const [error, setError] = useState('')
  // Si la categoría tiene movimientos, para eliminarla hay que elegir a dónde pasarlos.
  const [moverDe, setMoverDe] = useState(null)
  const [destino, setDestino] = useState('')
  const { confirmar } = useDialogos()

  async function guardar() {
    setError('')
    if (!nombre.trim()) return setError('Ponle un nombre a la categoría')

    setGuardando(true)
    try {
      if (esEdicion) {
        await api.editarCategoria(categoria.id, { nombre: nombre.trim(), icono, tipo, color })
      } else {
        await api.crearCategoria({ nombre: nombre.trim(), icono, tipo, color: color || null })
      }
      onGuardada()
    } catch (err) {
      setError(err.message || 'No se pudo guardar. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setGuardando(false)
    }
  }

  async function eliminar() {
    const ok = await confirmar('Si tiene movimientos, te preguntaremos a qué categoría pasarlos.', {
      titulo: `¿Eliminar "${categoria.nombre}"?`,
      confirmarTexto: 'Eliminar',
      peligro: true,
    })
    if (!ok) return
    setEliminando(true)
    setError('')
    try {
      await api.eliminarCategoria(categoria.id)
      onEliminada()
    } catch (err) {
      if (err.status === 409) {
        // En uso: se ofrece mover sus movimientos a otra categoría.
        setMoverDe(err.detalle)
        setDestino(activas.find((c) => c.id !== categoria.id)?.nombre || '')
      } else {
        setError(err.message || 'No se pudo eliminar. Revisa tu conexión e intenta de nuevo.')
      }
      setEliminando(false)
    }
  }

  async function eliminarMoviendo() {
    if (!destino) return setError('Elige a qué categoría pasar los movimientos')
    setEliminando(true)
    setError('')
    try {
      await api.eliminarCategoria(categoria.id, destino)
      onEliminada()
    } catch (err) {
      setError(err.message || 'No se pudo eliminar. Revisa tu conexión e intenta de nuevo.')
      setEliminando(false)
    }
  }

  const opcionesDestino = activas.filter((c) => c.id !== categoria?.id)

  return (
    <Hoja onCerrar={onClose}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">{esEdicion ? 'Editar categoría' : 'Nueva categoría'}</h2>
        <button onClick={onClose} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>

      {moverDe ? (
        <div role="alert" className="rounded-2xl bg-accent-soft border border-line p-4">
          <p className="text-sm font-semibold">Esta categoría está en uso</p>
          <p className="text-xs text-ink-soft mt-1">
            {[
              moverDe.movimientos ? `${moverDe.movimientos} movimientos` : null,
              moverDe.reglas ? `${moverDe.reglas} reglas` : null,
              moverDe.presupuestos ? `${moverDe.presupuestos} presupuesto` : null,
              moverDe.recurrentes ? `${moverDe.recurrentes} ${moverDe.recurrentes === 1 ? 'pago fijo' : 'pagos fijos'}` : null,
            ]
              .filter(Boolean)
              .join(', ')}
            . Elige a qué categoría pasarlos antes de eliminarla:
          </p>
          <select
            value={destino}
            onChange={(e) => setDestino(e.target.value)}
            aria-label="Pasar los movimientos a"
            className="w-full mt-3 rounded-xl border border-line bg-paper px-3 py-2.5 text-sm outline-none focus:border-accent"
          >
            {opcionesDestino.map((c) => (
              <option key={c.id} value={c.nombre}>
                {c.icono} {c.nombre}
              </option>
            ))}
          </select>
          {error && <p className="text-sm text-danger mt-2">{error}</p>}
          <div className="flex gap-2 mt-3">
            <button onClick={() => setMoverDe(null)} className="flex-1 rounded-xl border border-line py-3 text-sm font-semibold">
              Cancelar
            </button>
            <button
              onClick={eliminarMoviendo}
              disabled={eliminando}
              className="flex-1 rounded-xl bg-danger text-paper-raised py-3 text-sm font-semibold disabled:opacity-60"
            >
              {eliminando ? 'Moviendo...' : 'Mover y eliminar'}
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="mb-4">
            <SelectorEmoji valor={icono} onChange={setIcono} />
          </div>

          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Nombre (ej. Mascotas, Freelance)"
            aria-label="Nombre de la categoría"
            maxLength={40}
            className="w-full rounded-2xl border border-line bg-paper-raised px-4 py-3.5 text-sm outline-none focus:border-accent mb-4"
          />

          <p className="text-xs text-ink-soft mb-1.5">Para qué la usarás</p>
          <div className="flex gap-2 mb-4" role="group" aria-label="Tipo de categoría">
            {TIPOS.map((t) => (
              <button
                key={t.id}
                type="button"
                aria-pressed={tipo === t.id}
                onClick={() => setTipo(t.id)}
                className={`flex-1 rounded-xl py-2.5 text-sm font-semibold border ${
                  tipo === t.id ? 'bg-ink text-paper border-ink' : 'border-line text-ink-soft'
                }`}
              >
                {t.etiqueta}
              </button>
            ))}
          </div>

          <p className="text-xs text-ink-soft mb-1.5">Color (opcional)</p>
          <div className="flex gap-2 mb-5 flex-wrap" role="group" aria-label="Color de la categoría">
            <button
              type="button"
              onClick={() => setColor('')}
              aria-pressed={!color}
              aria-label="Sin color"
              className={`w-8 h-8 rounded-full border-2 text-[11px] text-ink-soft ${!color ? 'border-accent' : 'border-line'}`}
            >
              ∅
            </button>
            {COLORES.map((col) => (
              <button
                key={col}
                type="button"
                onClick={() => setColor(col)}
                aria-pressed={color === col}
                aria-label={`Color ${col}`}
                className={`w-8 h-8 rounded-full border-2 ${color === col ? 'border-ink' : 'border-transparent'}`}
                style={{ backgroundColor: col }}
              />
            ))}
          </div>

          {esEdicion && categoria.es_base && (
            <p className="text-xs text-ink-soft mb-4">
              Esta es una categoría base de la app — puedes cambiarle el nombre, el emoji o el color, o
              esconderla, pero no eliminarla del todo.
            </p>
          )}

          {error && <p className="text-sm text-danger mb-3">{error}</p>}

          <button
            onClick={guardar}
            disabled={guardando}
            className="w-full bg-ink text-paper font-semibold rounded-2xl py-4 text-[15px] disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {guardando ? 'Guardando...' : (
              <>
                <Check size={16} /> {esEdicion ? 'Guardar cambios' : 'Crear categoría'}
              </>
            )}
          </button>

          {esEdicion && !categoria.es_base && (
            <button
              onClick={eliminar}
              disabled={eliminando}
              className="w-full flex items-center justify-center gap-1.5 mt-3 text-sm text-danger font-medium disabled:opacity-60"
            >
              <Trash2 size={16} /> {eliminando ? 'Eliminando...' : 'Eliminar categoría'}
            </button>
          )}
        </>
      )}
    </Hoja>
  )
}
