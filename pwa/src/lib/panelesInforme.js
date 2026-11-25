import { useCallback, useState } from 'react'

// Paneles de Informes > Gastos: cada persona elige cuáles ve y en qué orden. Se guarda solo en este dispositivo.
export const PANELES = [
  { id: 'resumen', nombre: 'Resumen del periodo', ancho: true },
  { id: 'atencion', nombre: 'Lo que llama la atención', ancho: true },
  { id: 'categorias', nombre: 'Gasto por categoría' },
  { id: 'dia', nombre: 'Día a día' },
  { id: 'comercios', nombre: 'Dónde más gastas' },
  { id: 'ingresos', nombre: 'Ingresos y gastos' },
  { id: 'historial', nombre: 'Historial por categoría', ancho: true },
  { id: 'evolucion', nombre: 'Evolución por categoría' },
  { id: 'mi_evolucion', nombre: 'Mi evolución' },
]

const CLAVE = 'cuadrame:informe-paneles'
const IDS = PANELES.map((p) => p.id)

/** Normaliza lo guardado: quita ids que ya no existen y agrega al final los nuevos. */
export function normalizarPaneles(guardado) {
  const orden = Array.isArray(guardado?.orden) ? guardado.orden.filter((id) => IDS.includes(id)) : []
  for (const id of IDS) if (!orden.includes(id)) orden.push(id)
  const ocultos = Array.isArray(guardado?.ocultos) ? guardado.ocultos.filter((id) => IDS.includes(id)) : []
  return { orden: [...new Set(orden)], ocultos: [...new Set(ocultos)] }
}

function leer() {
  try {
    return normalizarPaneles(JSON.parse(localStorage.getItem(CLAVE) || 'null'))
  } catch {
    return normalizarPaneles(null)
  }
}

export function usePanelesInforme() {
  const [estado, setEstado] = useState(leer)
  const guardar = useCallback((nuevo) => {
    setEstado(nuevo)
    try {
      localStorage.setItem(CLAVE, JSON.stringify(nuevo))
    } catch {
      /* sin almacenamiento: se queda en memoria */
    }
  }, [])
  const mover = (id, delta) => {
    const i = estado.orden.indexOf(id)
    const j = i + delta
    if (i < 0 || j < 0 || j >= estado.orden.length) return
    const orden = [...estado.orden]
    ;[orden[i], orden[j]] = [orden[j], orden[i]]
    guardar({ ...estado, orden })
  }
  const alternar = (id) =>
    guardar({ ...estado, ocultos: estado.ocultos.includes(id) ? estado.ocultos.filter((x) => x !== id) : [...estado.ocultos, id] })
  const restaurar = () => guardar(normalizarPaneles(null))
  return { ...estado, mover, alternar, restaurar, visible: (id) => !estado.ocultos.includes(id) }
}
