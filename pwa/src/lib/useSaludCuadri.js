import { useEffect, useState } from 'react'
import { api } from './api'
import { estadoPorScore } from './saludFinanciera'

// Estado de Cuadri para la esquina de TODAS las pantallas. Una sola consulta compartida (se guarda 5 min)
// para que cambiar de pantalla no vuelva a pedirla.
const VIGENCIA_MS = 5 * 60 * 1000
let guardado = null // { score, en }
let enVuelo = null

function pedir() {
  if (enVuelo) return enVuelo
  enVuelo = api
    .saludFinanciera()
    .then((d) => {
      if (typeof d?.score === 'number') guardado = { score: d.score, en: Date.now() }
      return guardado
    })
    .catch(() => guardado)
    .finally(() => {
      enVuelo = null
    })
  return enVuelo
}

/** { estado, score } o null mientras no haya dato (o si el servidor no respondió). */
export function useSaludCuadri(activo = true) {
  const [dato, setDato] = useState(guardado)
  useEffect(() => {
    if (!activo) return undefined
    let vivo = true
    if (!guardado || Date.now() - guardado.en > VIGENCIA_MS) {
      pedir().then((d) => vivo && d && setDato(d))
    } else {
      setDato(guardado)
    }
    return () => {
      vivo = false
    }
  }, [activo])
  return dato ? { score: dato.score, estado: estadoPorScore(dato.score) } : null
}

// Solo para pruebas
export function _olvidarSaludCuadri() {
  guardado = null
  enVuelo = null
}
