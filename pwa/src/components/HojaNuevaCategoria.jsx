import { useState } from 'react'
import { X } from 'lucide-react'
import { api } from '../lib/api'
import { useCategorias } from '../lib/CategoriasContext'
import Hoja from './Hoja'

/** Valor especial de los <select> de categoría: abre esta hoja en vez de cambiar la categoría. */
export const OPCION_NUEVA_CATEGORIA = '__nueva_categoria__'
export const TEXTO_NUEVA_CATEGORIA = '＋ Crear categoría nueva…'

/**
 * Crea una categoría SIN salir de donde estás (la revisión de un extracto, por ejemplo): es una hoja
 * encima de la pantalla, no una ruta. Al crearla llama onCreada(nombre) para que quien la abrió la deje
 * ya elegida; la revisión (selección, categorías puestas) no se toca.
 */
export default function HojaNuevaCategoria({ onCreada, onCerrar }) {
  const { nombres = [], recargar } = useCategorias() || {}
  const [nombre, setNombre] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [aviso, setAviso] = useState('')

  async function crear(cerrar) {
    const limpio = nombre.trim()
    if (!limpio) {
      setAviso('Escribe el nombre de la categoría.')
      return
    }
    const igual = nombres.find((n) => n.toLowerCase() === limpio.toLowerCase())
    if (igual) {
      onCreada(igual) // ya existe: se elige tal cual, sin duplicarla
      cerrar()
      return
    }
    setGuardando(true)
    setAviso('')
    try {
      await api.crearCategoria({ nombre: limpio, icono: '🏷️', tipo: 'ambos', color: null })
      await recargar?.()
      onCreada(limpio)
      cerrar()
    } catch (err) {
      setAviso(err.message || 'No se pudo crear la categoría. Revisa tu conexión e intenta de nuevo.')
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onCerrar} titulo="Nueva categoría">
      {({ cerrar }) => (
        <form onSubmit={(e) => { e.preventDefault(); crear(cerrar) }}>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold">Nueva categoría</h2>
            <button type="button" onClick={cerrar} className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center" aria-label="Cerrar">
              <X size={16} />
            </button>
          </div>
          <p className="text-xs text-ink-soft mb-3">Se queda elegida y sigues donde estabas: tu revisión no se pierde.</p>
          <label className="block">
            <span className="text-xs font-semibold">Nombre</span>
            <input
              autoFocus
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              maxLength={40}
              className="mt-1 w-full rounded-xl border border-line bg-paper-raised px-3 py-2.5 text-sm"
            />
          </label>
          {aviso && <p className="text-xs text-danger mt-2" role="alert">{aviso}</p>}
          <button
            type="submit"
            disabled={guardando}
            className="mt-4 w-full min-h-[44px] rounded-xl bg-accent text-paper-raised text-sm font-semibold disabled:opacity-50"
          >
            {guardando ? 'Creando...' : 'Crear y elegir'}
          </button>
        </form>
      )}
    </Hoja>
  )
}
