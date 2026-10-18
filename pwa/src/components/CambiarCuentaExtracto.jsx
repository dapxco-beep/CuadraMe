import { useEffect, useState } from 'react'
import Hoja from './Hoja'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { formatCOP } from '../lib/format'
import { mensajeAmable } from '../lib/mensajes'
import { cuentasDestino, textoListo, textoPrevia } from '../lib/cambiarCuenta'

/**
 * Hoja «Cambiar de cuenta». Con `destinoInicial` (la sugerencia) abre directo la vista previa;
 * sin él, la persona elige la cuenta. Nunca cambia nada sin la vista previa y el botón de confirmar.
 */
export default function CambiarCuentaExtracto({ historialId, titulo, cuentaActualId, cuentas = [], destinoInicial = '', onCerrar, onListo }) {
  const bloqueo = useBloqueo() || {}
  const fmt = bloqueo.fmt || formatCOP
  const [destino, setDestino] = useState(destinoInicial)
  const [previa, setPrevia] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const opciones = cuentasDestino(cuentas, cuentaActualId)

  useEffect(() => {
    setPrevia(null)
    setError('')
    if (!destino) return undefined
    let vivo = true
    setCargando(true)
    api.previaCambiarCuentaExtracto(historialId, destino)
      .then((p) => { if (vivo) setPrevia(p) })
      .catch((err) => { if (vivo) setError(mensajeAmable(err?.message, { porDefecto: 'No pudimos calcular el cambio. Intenta de nuevo.' })) })
      .finally(() => { if (vivo) setCargando(false) })
    return () => { vivo = false }
  }, [historialId, destino])

  async function confirmar(cerrar) {
    setGuardando(true)
    setError('')
    try {
      const r = await api.cambiarCuentaExtracto(historialId, destino)
      onListo?.(textoListo(r), r)
      cerrar()
    } catch (err) {
      setError(mensajeAmable(err?.message, { porDefecto: 'No pudimos cambiar la cuenta. Intenta de nuevo.' }))
      setGuardando(false)
    }
  }

  return (
    <Hoja onCerrar={onCerrar} titulo="Cambiar de cuenta">
      {({ cerrar }) => (
        <div data-testid="cambiar-cuenta">
          <h2 className="text-lg font-bold">Cambiar de cuenta</h2>
          {titulo && <p className="text-sm text-ink-soft mt-1">{titulo}</p>}
          <label className="mt-3 flex flex-col gap-1 text-xs text-ink-soft">
            ¿A qué cuenta pertenece este extracto?
            <select
              value={destino}
              onChange={(e) => setDestino(e.target.value)}
              className="min-h-11 rounded-xl border border-line bg-paper px-3 text-sm text-ink"
            >
              <option value="">Elige la cuenta</option>
              {opciones.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
          </label>
          {cargando && <p className="text-sm text-ink-soft mt-3" role="status">Calculando...</p>}
          {previa && <p className="text-sm mt-3 leading-snug" data-testid="previa-cambio">{textoPrevia(previa, fmt)}</p>}
          {error && <p className="text-sm text-danger mt-3" role="alert">{error}</p>}
          <button
            type="button"
            disabled={!previa || previa.ya_en_esa_cuenta || guardando}
            onClick={() => confirmar(cerrar)}
            className="mt-4 w-full min-h-11 rounded-xl bg-accent text-paper-raised text-sm font-semibold disabled:opacity-50"
          >
            {guardando ? 'Un momento...' : 'Sí, cambiar de cuenta'}
          </button>
          <button type="button" onClick={cerrar} className="mt-1 w-full min-h-11 text-sm font-semibold text-ink-soft">Dejarlo así</button>
        </div>
      )}
    </Hoja>
  )
}
