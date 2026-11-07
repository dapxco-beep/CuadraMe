import { createContext, useContext } from 'react'

// «Informes» muestra otras pantallas dentro de sus pestañas. Esas pantallas, cuando van embebidas, no pintan su
// propio encabezado (flecha de volver + título): lo pone Informes una sola vez. Fuera de Informes todo sigue igual.
const EmbebidoContext = createContext(false)

export const EmbebidoProvider = EmbebidoContext.Provider
export const useEmbebido = () => useContext(EmbebidoContext)
