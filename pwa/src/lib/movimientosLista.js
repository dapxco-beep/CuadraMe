import { claveComercio, patronDeComercio, esAuto, porRevisar } from './comercio'

// Lógica pura de la lista de Movimientos (sin React): los filtros viven en la URL y se
// aplican igual en el servidor (lo que se pide) y en el cliente (lo que se muestra, para que
// una categoría recién cambiada salga o entre del filtro al instante).

export const PARAMS_FILTRO = ['q', 'cuenta', 'cat', 'tipo', 'origen', 'desde', 'hasta', 'revisar', 'conf', 'vista', 'orden']

// Por dónde llegó un movimiento (filtro «Origen» de la lista).
export const ORIGENES_FILTRO = [
  { id: 'correo', texto: 'Del correo' },
  { id: 'extracto', texto: 'Del extracto' },
  { id: 'manual', texto: 'A mano' },
  { id: 'atajo', texto: 'Del atajo' },
]
const ORIGEN_VALIDO = new Set(ORIGENES_FILTRO.map((o) => o.id))

export function leerFiltros(params) {
  return {
    origen: ORIGEN_VALIDO.has(params.get('origen')) ? params.get('origen') : '',
    q: params.get('q') || '',
    cuenta: params.get('cuenta') || '',
    cat: params.get('cat') || '',
    tipo: params.get('tipo') || '',
    desde: params.get('desde') || '',
    hasta: params.get('hasta') || '',
    revisar: params.get('revisar') === '1',
    conf: params.get('conf') === '1', // "Por confirmar": las que la app puso sola
    comercio: params.get('vista') === 'comercio',
    tabla: params.get('vista') === 'tabla', // solo se aplica en escritorio (≥1024 px)
    orden: params.get('orden') === 'monto' ? 'monto' : 'cantidad',
  }
}

/** Filtros que cambian lo que se pide al servidor (el resto solo cambia la vista). */
export function consultaServidor(f) {
  const c = {}
  if (f.revisar || f.conf) c.porRevisar = true
  if (f.q) c.q = f.q
  if (f.cat) c.categoria = f.cat
  if (f.tipo) c.tipo = f.tipo
  if (f.origen) c.origen = f.origen
  if (f.cuenta) c.cuentaId = f.cuenta
  if (f.desde) c.desde = f.desde
  if (f.hasta) c.hasta = f.hasta
  return c
}

export function coincideFiltros(m, f) {
  if (f.q && !`${m.titulo || ''} ${m.descripcion || ''}`.toLowerCase().includes(f.q.toLowerCase())) return false
  if (f.cat && m.categoria !== f.cat) return false
  if (f.cuenta && m.cuenta_id !== f.cuenta) return false
  if (f.tipo && m.tipo !== f.tipo) return false
  if (f.origen && m.origen && m.origen !== f.origen) return false // sin `origen` (viejo) manda lo que dijo el servidor
  if (f.desde && m.fecha.slice(0, 10) < f.desde) return false
  if (f.hasta && m.fecha.slice(0, 10) > f.hasta) return false
  if (f.revisar && !porRevisar(m)) return false
  if (f.conf && !esAuto(m)) return false
  return true
}

export function hayFiltros(f) {
  return !!(f.q || f.cuenta || f.cat || f.tipo || f.origen || f.desde || f.hasta || f.revisar || f.conf)
}

/** Huella de comercio de un movimiento; si no se reconoce, la descripción en minúsculas. */
export function huellaDe(m) {
  return claveComercio(patronDeComercio(m.descripcion)) || (m.descripcion || '').trim().toLowerCase()
}

/**
 * Agrupa por comercio: { huella, nombre, items, total (gasto neto), conteo, categoria (la más
 * frecuente), mixta (hay más de una categoría) }. Los traslados propios no se agrupan.
 */
export function agruparPorComercio(items, orden = 'cantidad') {
  const mapa = new Map()
  for (const m of items) {
    if (m.fuente === 'transferencia_interna') continue
    const h = huellaDe(m)
    let g = mapa.get(h)
    if (!g) {
      g = { huella: h, nombre: patronDeComercio(m.descripcion), items: [], neto: 0, cats: new Map() }
      mapa.set(h, g)
    }
    g.items.push(m)
    g.neto += m.tipo === 'income' ? m.monto : m.tipo === 'expense' ? -m.monto : 0
    g.cats.set(m.categoria, (g.cats.get(m.categoria) || 0) + 1)
  }
  const grupos = [...mapa.values()].map((g) => {
    const orde = [...g.cats.entries()].sort((a, b) => b[1] - a[1])
    return {
      huella: g.huella,
      nombre: g.nombre,
      items: g.items,
      conteo: g.items.length,
      neto: g.neto,
      total: Math.abs(g.neto),
      categoria: orde[0][0],
      mixta: orde.length > 1,
    }
  })
  grupos.sort((a, b) => (orden === 'monto' ? b.total - a.total : b.conteo - a.conteo || b.total - a.total))
  return grupos
}

/** Las categorías que más se usaron en los últimos movimientos cargados (para ponerlas arriba). */
export function categoriasRecientes(items, nombresValidos, max = 5) {
  const cuenta = new Map()
  for (const m of items.slice(0, 150)) {
    if (m.categoria === 'Otros' || m.fuente === 'transferencia_interna') continue
    if (!nombresValidos.includes(m.categoria)) continue
    cuenta.set(m.categoria, (cuenta.get(m.categoria) || 0) + 1)
  }
  return [...cuenta.entries()].sort((a, b) => b[1] - a[1]).slice(0, max).map(([n]) => n)
}

// Vista de tabla (>= 1024 px): orden por columna sobre lo ya cargado.
// El monto ordena con signo (los gastos cuentan como negativos).
export const COLUMNAS_TABLA = [
  { id: 'fecha', titulo: 'Fecha', fija: true },
  { id: 'descripcion', titulo: 'Descripción', fija: true },
  { id: 'categoria', titulo: 'Categoría' },
  { id: 'cuenta', titulo: 'Cuenta' },
  { id: 'monto', titulo: 'Monto', fija: true },
]

export function ordenarMovimientos(items, { col = 'fecha', dir = 'desc' } = {}, { nombreCuenta = () => '', firmado = (m) => Number(m.monto) || 0 } = {}) {
  const k = {
    fecha: (m) => m.fecha || '',
    descripcion: (m) => (m.descripcion || '').toLowerCase(),
    categoria: (m) => (m.categoria || '').toLowerCase(),
    cuenta: (m) => String(nombreCuenta(m.cuenta_id) || '').toLowerCase(),
    monto: firmado,
  }[col] || ((m) => m.fecha || '')
  const signo = dir === 'asc' ? 1 : -1
  return [...items].sort((a, b) => {
    const x = k(a)
    const y = k(b)
    if (x < y) return -signo
    if (x > y) return signo
    return 0
  })
}
