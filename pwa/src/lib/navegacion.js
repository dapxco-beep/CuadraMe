import {
  Bot, CalendarCheck, CreditCard, Database, Gift, GraduationCap, Home, Landmark, Lightbulb, List, PieChart, PiggyBank,
  Receipt, RefreshCw, Repeat, Settings, ShieldCheck, SlidersHorizontal, Smartphone, Sparkles, Sprout, Tag,
  TrendingUp, User, Wallet,
} from 'lucide-react'

// ═══ Única fuente de verdad de la navegación ═══════════════════════════════
// La usan la barra inferior (teléfono), el riel (iPad vertical) y la barra lateral
// (iPad horizontal / PC): agregar o renombrar un destino se hace SOLO aquí.
//
//  - PRINCIPALES: lo que se abre a diario; viven siempre a la vista (con atajo G+letra).
//  - GRUPOS: el resto, ordenado por tema (menú «Más» y barra lateral con grupos plegables).
//  - EXTRA_BUSQUEDA: destinos que no estorban en el menú (se llega a ellos desde otra
//    pantalla) pero que el buscador sí debe encontrar.

export const PRINCIPALES = [
  { to: '/', icon: Home, label: 'Inicio', corta: 'Inicio', atajo: 'G I' },
  { to: '/movimientos', icon: List, label: 'Movimientos', corta: 'Movim.', atajo: 'G M' },
  { to: '/presupuesto', icon: PieChart, label: 'Presupuesto', corta: 'Presup.', atajo: 'G P' },
]

export const GRUPOS = [
  {
    id: 'dinero',
    titulo: 'Dinero',
    icon: Wallet,
    items: [
      { to: '/cuentas', icon: Wallet, label: 'Cuentas', palabras: 'saldo banco tarjeta efectivo ajustar' },
      { to: '/deudas', icon: CreditCard, label: 'Deudas', palabras: 'prestamo credito cuotas pagar' },
      { to: '/recurrentes', icon: Repeat, label: 'Recurrentes', palabras: 'suscripcion fijo mensual automatico' },
      { to: '/impuestos', icon: Receipt, label: 'Impuestos', palabras: '4x1000 renta dian deducible' },
    ],
  },
  {
    id: 'ahorro',
    titulo: 'Ahorro e inversión',
    icon: TrendingUp,
    items: [
      { to: '/metas', icon: PiggyBank, label: 'Metas', palabras: 'ahorro objetivo meta' },
      { to: '/patrimonio', icon: Landmark, label: 'Patrimonio', corta: 'Patrim.', palabras: 'inversion activos neto cdt acciones' },
      { to: '/cierre-mes', icon: CalendarCheck, label: 'Cierre de mes', palabras: 'balance mes informe' },
      { to: '/resumen', icon: Gift, label: 'Resumen del mes', palabras: 'wrapped diapositivas compartir' },
    ],
  },
  {
    id: 'entender',
    titulo: 'Entender',
    icon: Lightbulb,
    items: [
      { to: '/informe', icon: PieChart, label: 'Informe', palabras: 'en que gasto categoria comercios reporte' },
      { to: '/insights', icon: Sparkles, label: 'Insights', palabras: 'consejos hallazgos' },
      { to: '/asistente', icon: Bot, label: 'Asistente', palabras: 'cuadrame ai ia pregunta chat' },
      { to: '/ahorcado', icon: Sprout, label: 'Árbol financiero', palabras: 'salud puntaje ahorcado vidas' },
    ],
  },
  {
    id: 'datos',
    titulo: 'Datos',
    icon: Database,
    items: [
      { to: '/sincronizacion', icon: RefreshCw, label: 'Traer movimientos', corta: 'Traer', palabras: 'sincronizar sincronizacion importar correo correos gmail extracto conciliar pdf excel csv archivo conexiones estado falla' },
      { to: '/categorias', icon: Tag, label: 'Categorías', palabras: 'etiquetas iconos' },
      { to: '/entrenar-categorias', icon: GraduationCap, label: 'Entrenar categorías', palabras: 'aprender clasificar' },
      { to: '/reglas-categoria', icon: SlidersHorizontal, label: 'Reglas', palabras: 'automatico comercio categoria' },
    ],
  },
  {
    id: 'ajustes',
    titulo: 'Ajustes',
    icon: Settings,
    items: [
      { to: '/perfil', icon: User, label: 'Perfil', palabras: 'cuenta usuario pin seguridad tema notificaciones' },
      { to: '/legal/privacidad', icon: ShieldCheck, label: 'Privacidad', palabras: 'datos legal terminos politica' },
      { to: '/conectar-dispositivo', icon: Smartphone, label: 'Conectar dispositivo', palabras: 'atajo iphone android wallet celular' },
    ],
  },
]

export const EXTRA_BUSQUEDA = [
  { to: '/compartir', icon: Gift, label: 'Compartir resumen', palabras: 'imagen' },
]

// Lista plana del menú «Más» (lo que antes era ITEMS_MAS)
export const ITEMS_MAS = GRUPOS.flatMap((g) => g.items.map((i) => ({ ...i, grupo: g.id })))

// Todo lo que el buscador puede encontrar (incluye las pantallas principales)
export const TODOS_LOS_DESTINOS = [...PRINCIPALES, ...ITEMS_MAS, ...EXTRA_BUSQUEDA]

// "Más" se ve activo en cualquiera de sus pantallas (o parientes)
const RUTAS_MAS = [...ITEMS_MAS.map((i) => i.to), ...EXTRA_BUSQUEDA.map((i) => i.to), '/legal']

export function rutaCoincide(pathname, to) {
  return to === '/' ? pathname === '/' : pathname === to || pathname.startsWith(`${to}/`)
}

export function estaEnMas(pathname) {
  return RUTAS_MAS.some((r) => rutaCoincide(pathname, r))
}

// ── Búsqueda: sin mayúsculas ni acentos («categorias» encuentra «Categorías») ──
export function normalizar(texto) {
  return String(texto || '')
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .trim()
}

export function buscarDestinos(consulta, lista = TODOS_LOS_DESTINOS) {
  const palabras = normalizar(consulta).split(/\s+/).filter(Boolean)
  if (palabras.length === 0) return []
  const resultados = lista
    .map((d) => {
      const nombre = normalizar(d.label)
      const heno = `${nombre} ${normalizar(d.palabras)}`
      if (!palabras.every((p) => heno.includes(p))) return null
      // Coincidencia en el nombre pesa más que en las palabras clave
      const peso = palabras.every((p) => nombre.includes(p)) ? (nombre.startsWith(palabras[0]) ? 0 : 1) : 2
      return { d, peso }
    })
    .filter(Boolean)
  resultados.sort((a, b) => a.peso - b.peso)
  return resultados.map((r) => r.d)
}

// ── Recientes: los últimos 4 destinos del menú que se usaron ──
const CLAVE_RECIENTES = 'cuadrame:nav-recientes'
const MAX_RECIENTES = 4
const DESTINOS_RECIENTES = [...ITEMS_MAS, ...EXTRA_BUSQUEDA]

export function leerRecientes() {
  try {
    const crudo = JSON.parse(localStorage.getItem(CLAVE_RECIENTES) || '[]')
    return (Array.isArray(crudo) ? crudo : [])
      .map((to) => DESTINOS_RECIENTES.find((d) => d.to === to))
      .filter(Boolean)
      .slice(0, MAX_RECIENTES)
  } catch {
    return []
  }
}

// Registra la ruta actual si es un destino del menú (las principales no cuentan: ya están a la vista)
export function registrarReciente(pathname) {
  const destino = DESTINOS_RECIENTES.find((d) => rutaCoincide(pathname, d.to))
  if (!destino) return
  try {
    const actuales = JSON.parse(localStorage.getItem(CLAVE_RECIENTES) || '[]')
    const lista = [destino.to, ...(Array.isArray(actuales) ? actuales : []).filter((t) => t !== destino.to)].slice(0, MAX_RECIENTES)
    localStorage.setItem(CLAVE_RECIENTES, JSON.stringify(lista))
  } catch {
    /* sin almacenamiento (modo privado): simplemente no hay recientes */
  }
}

// ── Grupos plegados de la barra lateral (se recuerdan) ──
const CLAVE_GRUPOS = 'cuadrame:nav-grupos-cerrados'
export function leerGruposCerrados() {
  try {
    const v = JSON.parse(localStorage.getItem(CLAVE_GRUPOS) || '[]')
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}
export function guardarGruposCerrados(ids) {
  try {
    localStorage.setItem(CLAVE_GRUPOS, JSON.stringify(ids))
  } catch {
    /* ignorar */
  }
}
