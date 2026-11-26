import { useCallback, useState } from 'react'

// Paneles de Informes > Gastos: cada persona elige cuáles ve y en qué orden. Se guarda solo en este dispositivo.
export const PANELES = [
  { id: 'resumen', nombre: 'Resumen del periodo', ancho: true },
  { id: 'atencion', nombre: 'Lo que llama la atención', ancho: true },
  { id: 'categorias', nombre: 'Gasto por categoría' },
  { id: 'dia', nombre: 'Día a día' },
  { id: 'comercios', nombre: 'Dónde más gastas' },
  { id: 'ingresos', nombre: 'Ingresos, gastos y evolución' },
  { id: 'costos', nombre: 'Lo que te cuesta tu plata' },
  { id: 'mes_a_mes', nombre: 'Categorías mes a mes' },
]

// Antes eran cinco paneles; ahora dos (cada uno con su interruptor de vista). Lo que la persona ya había guardado se traduce.
const ANTIGUOS = { historial: 'mes_a_mes', evolucion: 'mes_a_mes', mi_evolucion: 'ingresos' }

const CLAVE = 'cuadrame:informe-paneles'
const IDS = PANELES.map((p) => p.id)

/** Normaliza lo guardado: quita ids que ya no existen y agrega al final los nuevos. */
export function normalizarPaneles(guardado) {
  const traducir = (id) => ANTIGUOS[id] || id
  const orden = Array.isArray(guardado?.orden) ? guardado.orden.map(traducir).filter((id) => IDS.includes(id)) : []
  for (const id of IDS) if (!orden.includes(id)) orden.push(id)
  const viejos = Array.isArray(guardado?.ocultos) ? guardado.ocultos : []
  const ordenViejo = Array.isArray(guardado?.orden) ? guardado.orden : []
  // Un panel unido se oculta solo si TODAS las partes que la persona tenía estaban ocultas
  const ocultos = IDS.filter((id) => {
    const antiguos = Object.keys(ANTIGUOS).filter((k) => ANTIGUOS[k] === id)
    if (antiguos.length === 0) return viejos.includes(id)
    const partes = [...(ordenViejo.includes(id) ? [id] : []), ...antiguos.filter((k) => ordenViejo.includes(k))]
    return partes.length > 0 && partes.every((p) => viejos.includes(p))
  })
  return { orden: [...new Set(orden)], ocultos }
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
