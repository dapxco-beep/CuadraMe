import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import Hoja from '../components/Hoja'

// Reemplaza alert() y confirm() del navegador, que se ven ajenos al diseño,
// bloquean el hilo y en PWAs instaladas a veces ni aparecen. Dos piezas:
//   confirmar(mensaje, opciones) -> Promise<boolean>   (hoja inferior)
//   avisar(mensaje, tipo)        -> toast que se cierra solo
const DialogosContext = createContext(null)

export function DialogosProvider({ children }) {
  const [confirmacion, setConfirmacion] = useState(null)
  const [toast, setToast] = useState(null)
  const temporizador = useRef(null)

  const confirmar = useCallback((mensaje, opciones = {}) => {
    return new Promise((resolve) => {
      setConfirmacion({ mensaje, ...opciones, resolve })
    })
  }, [])

  const avisar = useCallback((mensaje, tipo = 'error') => {
    clearTimeout(temporizador.current)
    setToast({ mensaje, tipo })
    temporizador.current = setTimeout(() => setToast(null), 4000)
  }, [])

  useEffect(() => () => clearTimeout(temporizador.current), [])

  // api.js avisa cuando la sesión venció y se cerró sola: mensaje amable en vez de una pantalla rota
  useEffect(() => {
    const alVencer = (e) => avisar(e.detail?.mensaje || 'Tu sesión venció. Vuelve a iniciar sesión.', 'info')
    window.addEventListener('cuadrame:sesion-vencida', alVencer)
    return () => window.removeEventListener('cuadrame:sesion-vencida', alVencer)
  }, [avisar])

  function responder(valor) {
    confirmacion?.resolve(valor)
    setConfirmacion(null)
  }

  return (
    <DialogosContext.Provider value={{ confirmar, avisar }}>
      {children}

      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="fixed top-4 inset-x-0 z-[60] flex justify-center px-4 pointer-events-none"
        >
          <div
            className={`pop-in max-w-[440px] w-full rounded-2xl px-4 py-3 text-sm font-medium shadow-lg pointer-events-auto ${
              toast.tipo === 'error' ? 'bg-danger text-white' : 'bg-ink text-paper'
            }`}
          >
            {toast.mensaje}
          </div>
        </div>
      )}

      {confirmacion && (
        // Atrás, Escape o tocar fuera = cancelar (el mismo "false" que el botón Cancelar)
        <Hoja
          role="alertdialog"
          ariaLabel={confirmacion.titulo || 'Confirmar'}
          clasePanel="p-6 pb-[calc(1.5rem+env(safe-area-inset-bottom))]"
          onCerrar={() => responder(false)}
        >
          {confirmacion.titulo && <p className="text-base font-bold mb-1">{confirmacion.titulo}</p>}
          <p className="text-sm text-ink-soft">{confirmacion.mensaje}</p>
          <div className="flex gap-3 mt-5">
            <button
              autoFocus
              onClick={() => responder(false)}
              className="flex-1 rounded-2xl border border-line py-3.5 text-sm font-semibold"
            >
              Cancelar
            </button>
            <button
              onClick={() => responder(true)}
              className={`flex-1 rounded-2xl py-3.5 text-sm font-semibold ${
                confirmacion.peligro ? 'bg-danger text-white' : 'bg-ink text-paper'
              }`}
            >
              {confirmacion.confirmarTexto || 'Continuar'}
            </button>
          </div>
        </Hoja>
      )}
    </DialogosContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useDialogos() {
  return useContext(DialogosContext)
}
