import { useState } from 'react'
import { Trash2, X } from 'lucide-react'
import Hoja from './Hoja'

// Palabra que la persona debe escribir para confirmar. El backend exige la misma.
export const PALABRA_CONFIRMAR = 'ELIMINAR'

// Borrar la cuenta es irreversible, así que el botón solo se habilita cuando la persona
// ESCRIBE la palabra (un toque accidental no alcanza). Lenguaje simple: qué se borra, qué
// pasa con Gmail, y que antes puede descargar una copia.
export default function BorrarMiCuenta({ onConfirmar, onCancelar, onDescargar, eliminando }) {
  const [texto, setTexto] = useState('')
  const listo = texto.trim().toUpperCase() === PALABRA_CONFIRMAR

  return (
    <Hoja onCerrar={onCancelar} capa="z-[60]" titulo="Borrar mi cuenta y todos mis datos">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold flex items-center gap-2 text-danger">
          <Trash2 size={20} /> Borrar mi cuenta
        </h2>
        <button
          onClick={onCancelar}
          className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Cerrar"
        >
          <X size={16} />
        </button>
      </div>

      <p className="text-sm leading-relaxed">
        Vamos a borrar <strong>para siempre</strong> todo lo tuyo: tus cuentas, movimientos, presupuestos, metas, deudas,
        correos y extractos leídos, reglas y preferencias.
      </p>
      <ul className="text-sm text-ink-soft mt-3 space-y-1.5 list-disc pl-5 leading-relaxed">
        <li>Si conectaste Gmail, también le quitamos el permiso a CuadraMe.</li>
        <li>Se cierra tu acceso: tendrás que registrarte de nuevo si algún día vuelves.</li>
        <li>No se puede deshacer, y nosotros tampoco podremos recuperarlo.</li>
      </ul>
      <button onClick={onDescargar} className="text-sm text-accent font-medium mt-3 min-h-11">
        Primero quiero descargar una copia de mis datos
      </button>

      <label className="block mt-3 text-sm font-medium" htmlFor="confirmar-borrado">
        Para confirmar, escribe {PALABRA_CONFIRMAR}
      </label>
      <input
        id="confirmar-borrado"
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        autoComplete="off"
        autoCapitalize="characters"
        placeholder={PALABRA_CONFIRMAR}
        className="mt-1.5 w-full rounded-xl bg-paper-raised border border-line px-3.5 py-3 text-base"
      />

      <div className="flex gap-3 mt-4">
        <button
          onClick={onCancelar}
          className="flex-1 min-h-12 rounded-xl border border-line bg-paper-raised text-sm font-medium"
        >
          Cancelar
        </button>
        <button
          onClick={() => onConfirmar(texto.trim().toUpperCase())}
          disabled={!listo || eliminando}
          className="flex-1 min-h-12 rounded-xl bg-danger text-paper-raised text-sm font-semibold disabled:opacity-40"
        >
          {eliminando ? 'Borrando...' : 'Borrar todo'}
        </button>
      </div>
    </Hoja>
  )
}
