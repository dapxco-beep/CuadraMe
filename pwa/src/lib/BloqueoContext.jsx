import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from './AuthContext'
import { formatMoneda } from './format'
import {
  borrarSeguridad,
  guardarOcultarSaldos,
  guardarPin,
  leerOcultarSaldos,
  minutosBloqueo,
  tienePin as hayPin,
} from './seguridad'

export const MASCARA = '••••'

// Valor por defecto sin proveedor (pruebas de pantallas sueltas): nada oculto ni bloqueado.
const porDefecto = {
  bloqueado: false,
  tienePin: false,
  ocultarSaldos: false,
  alternarOcultar: () => {},
  fmt: (valor, moneda) => formatMoneda(valor, moneda),
  bloquear: () => {},
  desbloquear: () => {},
  definirPin: async () => {},
  quitarPin: () => {},
}

const BloqueoContext = createContext(porDefecto)

export function BloqueoProvider({ children }) {
  const { usuario } = useAuth()
  const [tienePin, setTienePin] = useState(() => hayPin())
  // Si hay PIN, la app arranca bloqueada: abrirla es justo lo que protegemos.
  const [bloqueado, setBloqueado] = useState(() => hayPin())
  const [ocultarSaldos, setOcultarSaldos] = useState(() => leerOcultarSaldos())
  const ocultoDesde = useRef(null)

  // Al cerrar sesión (logout() ya borró el PIN) se reinicia el estado en memoria.
  useEffect(() => {
    if (!usuario) {
      setTienePin(false)
      setBloqueado(false)
    }
  }, [usuario])

  // Bloqueo automático: se mide cuánto tiempo estuvo la app en segundo plano.
  useEffect(() => {
    function alCambiarVisibilidad() {
      if (document.visibilityState === 'hidden') {
        ocultoDesde.current = Date.now()
        return
      }
      const desde = ocultoDesde.current
      ocultoDesde.current = null
      if (desde && hayPin() && Date.now() - desde >= minutosBloqueo() * 60_000) {
        setBloqueado(true)
      }
    }
    document.addEventListener('visibilitychange', alCambiarVisibilidad)
    return () => document.removeEventListener('visibilitychange', alCambiarVisibilidad)
  }, [])

  const alternarOcultar = useCallback(() => {
    setOcultarSaldos((v) => {
      guardarOcultarSaldos(!v)
      return !v
    })
  }, [])

  const definirPin = useCallback(async (pin) => {
    await guardarPin(pin)
    setTienePin(true)
  }, [])

  const quitarPin = useCallback(() => {
    borrarSeguridad()
    setTienePin(false)
    setBloqueado(false)
  }, [])

  const valor = useMemo(
    () => ({
      bloqueado: bloqueado && tienePin,
      tienePin,
      ocultarSaldos,
      alternarOcultar,
      // Formatea un monto, o lo enmascara si el usuario eligió ocultar saldos.
      fmt: (monto, moneda) => (ocultarSaldos ? MASCARA : formatMoneda(monto, moneda)),
      bloquear: () => hayPin() && setBloqueado(true),
      desbloquear: () => setBloqueado(false),
      definirPin,
      quitarPin,
    }),
    [bloqueado, tienePin, ocultarSaldos, alternarOcultar, definirPin, quitarPin]
  )

  return <BloqueoContext.Provider value={valor}>{children}</BloqueoContext.Provider>
}

export function useBloqueo() {
  return useContext(BloqueoContext)
}
