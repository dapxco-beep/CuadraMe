import { useState } from 'react'
import { AlertTriangle, Check, Copy, KeyRound } from 'lucide-react'
import { useDialogos } from '../lib/DialogosContext'

// Caja de la clave del Atajo, pensada para personas no técnicas. Tres casos:
//  1) Hay clave visible (recién creada o clave antigua en claro): se muestra con botón Copiar;
//     si es nueva, aviso de que no se vuelve a mostrar.
//  2) Ya existe pero guardada de forma segura: solo «empieza por cdm_ab12…» + «Crear una clave nueva».
//  3) Aún no hay estado (cargando) o no hay clave.
export default function ClaveAtajo({ clave, cargando, tieneClave, prefijo, recienCreada, crearNueva, grande = false }) {
  const { confirmar, avisar } = useDialogos()
  const [copiado, setCopiado] = useState(false)
  const [creando, setCreando] = useState(false)

  async function copiar() {
    try {
      await navigator.clipboard.writeText(clave)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2500)
    } catch {
      avisar('No pudimos copiarla sola. Mantén presionada la clave para seleccionarla y copiarla.')
    }
  }

  async function nueva() {
    if (tieneClave) {
      const ok = await confirmar(
        'Tu Atajo del iPhone dejará de funcionar hasta que pegues la clave nueva en él. Te mostraremos la clave nueva una sola vez para que la copies.',
        { titulo: '¿Crear una clave nueva?', confirmarTexto: 'Sí, crear clave nueva', peligro: true }
      )
      if (!ok) return
    }
    setCreando(true)
    try {
      await crearNueva()
    } catch (err) {
      avisar(err.message || 'No pudimos crear la clave nueva. Intenta de nuevo.')
    } finally {
      setCreando(false)
    }
  }

  if (cargando) {
    return <span className="skeleton inline-block h-3.5 w-40 align-middle" role="status" aria-label="Cargando tu clave" />
  }

  if (clave) {
    return (
      <div data-testid="clave-visible">
        {recienCreada && (
          <div role="alert" className="rounded-xl bg-warn-soft px-3 py-2.5 mb-2 flex items-start gap-2">
            <AlertTriangle size={16} className="shrink-0 mt-0.5" />
            <p className="text-xs leading-relaxed">
              <strong>Cópiala ahora.</strong> Por tu seguridad, esta clave no se vuelve a mostrar. Si la pierdes,
              podrás crear otra.
            </p>
          </div>
        )}
        {grande ? (
          <>
            <code className="block text-xs bg-paper rounded-xl px-3 py-2.5 break-all select-all mb-3">{clave}</code>
            <button
              onClick={copiar}
              className="btn btn-primario btn-bloque inline-flex items-center justify-center gap-2"
              aria-label="Copiar clave"
            >
              {copiado ? <Check size={20} /> : <Copy size={20} />} {copiado ? 'Clave copiada' : 'Copiar mi clave'}
            </button>
            {copiado && (
              <p role="status" className="text-sm text-cuadra mt-2 font-semibold">
                Listo, ya la tienes copiada. Toca «Siguiente».
              </p>
            )}
          </>
        ) : (
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs bg-paper rounded-xl px-3 py-2.5 break-all select-all">{clave}</code>
            <button
              onClick={copiar}
              className="shrink-0 h-11 px-3 rounded-xl bg-accent text-paper-raised text-sm font-semibold flex items-center gap-1.5"
              aria-label="Copiar clave"
            >
              {copiado ? <Check size={16} /> : <Copy size={16} />} {copiado ? 'Copiada' : 'Copiar'}
            </button>
          </div>
        )}
        {!recienCreada && (
          <button onClick={nueva} disabled={creando} className="text-xs text-ink-soft underline mt-2">
            {creando ? 'Creando...' : 'Crear una clave nueva'}
          </button>
        )}
      </div>
    )
  }

  return (
    <div data-testid="clave-guardada">
      {tieneClave ? (
        <p className="text-sm">
          Tu clave empieza por <strong>{prefijo || 'cdm_…'}</strong>. Por seguridad ya no se puede mostrar completa.
        </p>
      ) : (
        <p className="text-sm">Aún no tienes una clave para conectar tu Atajo.</p>
      )}
      <button
        onClick={nueva}
        disabled={creando}
        className="w-full mt-2 flex items-center justify-center gap-2 border border-line rounded-2xl py-3 text-sm font-semibold disabled:opacity-50"
      >
        <KeyRound size={16} /> {creando ? 'Creando...' : tieneClave ? 'Crear una clave nueva' : 'Crear mi clave'}
      </button>
      {tieneClave && (
        <p className="text-xs text-ink-soft mt-2">
          Si ya conectaste tu Atajo, no necesitas hacer nada. Crea una nueva solo si la perdiste o quieres cortar el acceso.
        </p>
      )}
    </div>
  )
}
