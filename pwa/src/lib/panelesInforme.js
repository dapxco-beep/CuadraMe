import { useCallback, useState } from 'react'

// Paneles de Informes > Gastos: cada persona elige cuáles ve y en qué orden. Se guarda solo en este dispositivo.
export const PANELES = [
  { id: 'resumen', nombre: 'Resumen del periodo', ancho: true },
  { id: 'atencion', nombre: 'Lo que llama la atención', ancho: true },
  { id: 'categorias', nombre: 'Gasto por categoría' },
  { id: 'dia', nombre: 'Día a día' },
  { id: 'comercios', nombre: 'Dónde más gastas' },
  { id: 'ingresos', nombre: 'Ingresos, gastos y evolución', ocultoPorDefecto: true },
  { id: 'costos', nombre: 'Lo que te cuesta tu plata' },
  { id: 'mes_a_mes', nombre: 'Categorías mes a mes' },
  { id: 'cosas_raras', nombre: 'Resumen y cosas raras' },
]

// Antes eran cinco paneles; ahora dos (cada uno con su interruptor de vista). Lo que la persona ya había guardado se traduce.
const ANTIGUOS = { historial: 'mes_a_mes', evolucion: 'mes_a_mes', mi_evolucion: 'ingresos' }

// Paneles de Informes > Resumen (se guardan aparte de los de Gastos).
export const PANELES_RESUMEN = [
  { id: 'cifras', nombre: '¿Me alcanzó la plata?', ancho: true },
  { id: 'hallazgos', nombre: 'Lo que dicen tus números', ancho: true },
  { id: 'flujo', nombre: 'Flujo neto', ancho: true },
  { id: 'tasa', nombre: 'Tasa de ahorro' },
  { id: 'fuentes', nombre: 'Ingresos por fuente' },
  { id: 'presupuesto', nombre: 'Presupuesto vs. gasto real', ancho: true },
]

const CLAVE = 'cuadrame:informe-paneles'
const CLAVE_RESUMEN = 'cuadrame:informe-paneles-resumen'
const IDS = PANELES.map((p) => p.id)

/** Normaliza lo guardado: quita ids que ya no existen y agrega al final los nuevos. */
export function normalizarPaneles(guardado, ids = IDS, antiguosDe = ANTIGUOS) {
  const IDS = ids
  const ANTIGUOS = antiguosDe
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
  // Sin nada guardado: los paneles que ahora repite la pestaña Resumen empiezan ocultos
  if (!guardado) return { orden: [...new Set(orden)], ocultos: PANELES.filter((p) => p.ocultoPorDefecto).map((p) => p.id) }
  return { orden: [...new Set(orden)], ocultos }
}

function leer(clave, ids, antiguos) {
  try {
    return normalizarPaneles(JSON.parse(localStorage.getItem(clave) || 'null'), ids, antiguos)
  } catch {
    return normalizarPaneles(null, ids, antiguos)
  }
}

/** Paneles personalizables de una pantalla de Informes. Sin argumentos: los de «Gastos». */
export function usePanelesInforme(lista = PANELES, clave = lista === PANELES ? CLAVE : CLAVE_RESUMEN) {
  const ids = lista.map((p) => p.id)
  const antiguos = lista === PANELES ? ANTIGUOS : {}
  const [estado, setEstado] = useState(() => leer(clave, ids, antiguos))
  const guardar = useCallback((nuevo) => {
    setEstado(nuevo)
    try {
      localStorage.setItem(clave, JSON.stringify(nuevo))
    } catch {
      /* sin almacenamiento: se queda en memoria */
    }
  }, [clave])
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
  const restaurar = () => guardar(normalizarPaneles(null, ids, antiguos))
  return { ...estado, mover, alternar, restaurar, visible: (id) => !estado.ocultos.includes(id) }
}
