import {
  Activity, ArrowLeftRight, Bot, BookOpen, CalendarCheck, CreditCard, Database, Gift, GraduationCap, Home, Landmark, Lightbulb, List, PieChart, PiggyBank,
  LifeBuoy, Receipt, RefreshCw, Repeat, Scale, Settings, ShieldCheck, SlidersHorizontal, Smartphone, Sparkles, Sprout, Tag,
  TrendingUp, User, Users, Wallet,
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
      { to: '/recurrentes', icon: Repeat, label: 'Pagos fijos', palabras: 'recurrentes recurrente suscripcion fijo mensual automatico arriendo nomina' },
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
      { to: '/inversiones', icon: TrendingUp, label: 'Inversiones', corta: 'Invers.', palabras: 'acciones etf fondos broker portafolio ticker trii bolsa cripto rentabilidad' },
      { to: '/cierre-mes', icon: CalendarCheck, label: 'Cierre de mes', palabras: 'balance mes informe' },
      { to: '/resumen', icon: Gift, label: 'Resumen del mes', palabras: 'wrapped diapositivas compartir' },
    ],
  },
  {
    id: 'entender',
    titulo: 'Entender',
    icon: Lightbulb,
    items: [
      { to: '/informe', icon: PieChart, label: 'En qué gasto mi plata', palabras: 'informe en que gasto mi plata categoria comercios reporte' },
      { to: '/mi-cuenta-cuadra', icon: Scale, label: 'Mi cuenta cuadra', palabras: 'cuadre cuadra extracto banco tarjeta semaforo diferencia' },
      { to: '/traslados', icon: ArrowLeftRight, label: 'Plata que pasé entre mis cuentas', palabras: 'traslado entre mis cuentas nequi nu bancolombia no cuenta' },
      { to: '/insights', icon: Sparkles, label: 'Cosas raras en mis gastos', palabras: 'hallazgos insights consejos descubrimientos' },
      { to: '/asistente', icon: Bot, label: 'Asistente', palabras: 'cuadrame ai ia pregunta chat' },
      { to: '/ahorcado', icon: Sprout, label: 'Qué tan sana va mi plata', palabras: 'arbol financiero salud puntaje ahorcado vidas' },
    ],
  },
  {
    id: 'datos',
    titulo: 'Datos',
    icon: Database,
    items: [
      { to: '/sincronizacion', icon: RefreshCw, label: 'Traer movimientos', corta: 'Traer', palabras: 'sincronizar sincronizacion importar correo correos gmail extracto conciliar pdf excel csv archivo conexiones estado falla' },
      { to: '/categorias', icon: Tag, label: 'Categorías', palabras: 'etiquetas iconos' },
      { to: '/entrenar-categorias', icon: GraduationCap, label: 'Enseñar categorías', palabras: 'entrenar aprender clasificar' },
      { to: '/reglas-categoria', icon: SlidersHorizontal, label: 'Reglas automáticas', palabras: 'reglas automatico comercio categoria' },
    ],
  },
  {
    id: 'ajustes',
    titulo: 'Ajustes',
    icon: Settings,
    items: [
      { to: '/perfil', icon: User, label: 'Perfil', palabras: 'cuenta usuario pin seguridad tema notificaciones' },
      { to: '/aprende', icon: BookOpen, label: 'Aprende', palabras: 'lecciones glosario educacion finanzas tarjeta credito debito interes cupo presupuesto fraude que es' },
      { to: '/ayuda', icon: LifeBuoy, label: 'Ayuda', palabras: 'preguntas frecuentes dudas soporte como funciona extracto clave pdf gmail primeros pasos' },
      { to: '/legal/privacidad', icon: ShieldCheck, label: 'Privacidad', palabras: 'datos legal terminos politica' },
      { to: '/conectar-dispositivo', icon: Smartphone, label: 'Registro automático', palabras: 'conectar dispositivo atajo iphone android wallet celular' },
    ],
  },
]

export const EXTRA_BUSQUEDA = [
  { to: '/compartir', icon: Users, label: 'Compartir con mi pareja o familia', palabras: 'compartir cuenta pareja familia hogar invitar pareja esposo esposa ver anotar acceso' },
  { to: '/amigos', icon: Users, label: 'Dividir gastos con amigos', palabras: 'dividir gastos amigos cuenta compartida cena viaje deben me deben' },
  { to: '/hogares', icon: Users, label: 'Hogar o pareja', palabras: 'hogar pareja familia casa compañeros apartamento gastos juntos quien debe a quien arriendo mercado servicios' },
  { to: '/colectas', icon: Users, label: 'Colectas (vacas)', palabras: 'colecta vaca inscripcion equipo futbol torneo paseo regalo cuota aporte quien puso falta' },
]

// Destino SOLO para quien administra CuadraMe. No está en GRUPOS ni en el buscador: se agrega aparte
// cuando el correo de la sesión coincide con VITE_ADMIN_EMAIL. Es solo comodidad visual; la seguridad
// la pone el servidor (GET /metricas/panel responde 404 a cualquier otra persona).
export const DESTINO_ADMIN = { to: '/salud-negocio', icon: Activity, label: 'Salud del negocio' }

export function esAdminVisible(email) {
  const admin = String(import.meta.env.VITE_ADMIN_EMAIL || '').trim().toLowerCase()
  return Boolean(admin) && String(email || '').trim().toLowerCase() === admin
}

// Lista plana del menú «Más» (lo que antes era ITEMS_MAS)
export const ITEMS_MAS = GRUPOS.flatMap((g) => g.items.map((i) => ({ ...i, grupo: g.id })))

// ── Modo simple ──────────────────────────────────────────────────────────
// Lo esencial a la vista; el resto, en el grupo plegado «Más funciones» con una frase de qué hace
// cada una. Las rutas NO cambian: siguen abriendo por enlace directo y por el buscador.
export const MAS_FUNCIONES_ID = 'mas-funciones'
const RUTAS_ESENCIALES = ['/sincronizacion', '/perfil', '/ayuda']

export const EXPLICACION = {
  '/cuentas': 'Tus bancos, tarjetas y efectivo, cada uno con su saldo.',
  '/deudas': 'Lo que debes y cuál conviene pagar primero.',
  '/recurrentes': 'Lo que pagas o recibes cada mes: arriendo, suscripciones, nómina.',
  '/impuestos': 'Cuánto te cobran por el 4x1000 y qué te sirve para la renta.',
  '/metas': 'Guarda plata poco a poco para algo que quieres.',
  '/patrimonio': 'Tu patrimonio: todo lo que tienes menos todo lo que debes.',
  '/inversiones': 'Tus acciones, fondos o cripto con el precio al día y cuánto vas ganando (opcional).',
  '/cierre-mes': 'Un balance de cómo te fue en el mes.',
  '/resumen': 'Tu mes contado en diapositivas para compartir.',
  '/informe': 'Cuánto entra y cuánto sale, y en qué gastas más.',
  '/mi-cuenta-cuadra': 'Si cada banco y tarjeta cuadra con sus extractos, mes a mes.',
  '/traslados': 'Cuando pasas plata de una cuenta tuya a otra, no es un gasto. Aquí lo confirmas.',
  '/insights': 'Gastos que subieron, cobros repetidos y otras cosas que conviene mirar.',
  '/asistente': 'Pregúntale a CuadraMe cosas sobre tu plata.',
  '/ahorcado': 'Un puntaje de 0 a 100 de qué tan sana va tu plata.',
  '/categorias': 'Los tipos de gasto: comida, transporte, salud…',
  '/entrenar-categorias': 'Enséñale a CuadraMe en qué categoría va cada gasto.',
  '/reglas-categoria': 'Si un lugar siempre es del mismo tipo de gasto, que se ponga solo.',
  '/aprende': 'Lecciones cortas, de un minuto, sobre plata.',
  '/sincronizacion': 'Trae tus movimientos del banco: desde el correo, un extracto en PDF o un Excel.',
  '/amigos': 'Divide una cuenta con amigos y anota quién te debe y a quién le debes.',
  '/compartir': 'Lleva la plata del hogar con tu pareja o familia.',
  '/legal/privacidad': 'Qué datos usamos y cómo los cuidamos.',
  '/conectar-dispositivo': 'Anota solos los pagos que haces con tu celular (opcional).',
}

/**
 * Grupos del menú según el modo. `enUso`: rutas de funciones que la persona ya usa (tiene metas,
 * deudas…): suben solas a «Lo que ya usas». En modo completo son los GRUPOS de siempre.
 */
export function gruposSegunModo({ completo = false, enUso = [] } = {}) {
  if (completo) return GRUPOS
  const porRuta = Object.fromEntries(ITEMS_MAS.map((i) => [i.to, i]))
  const conExplica = (i) => ({ ...i, explica: EXPLICACION[i.to] })
  const esenciales = RUTAS_ESENCIALES.map((to) => porRuta[to]).filter(Boolean)
  const usadas = ITEMS_MAS.filter((i) => enUso.includes(i.to) && !RUTAS_ESENCIALES.includes(i.to)).map(conExplica)
  const resto = ITEMS_MAS.filter((i) => !RUTAS_ESENCIALES.includes(i.to) && !enUso.includes(i.to)).map(conExplica)
  return [
    { id: 'esencial', titulo: 'Lo esencial', items: esenciales },
    ...(usadas.length ? [{ id: 'en-uso', titulo: 'Lo que ya usas', items: usadas }] : []),
    { id: MAS_FUNCIONES_ID, titulo: 'Más funciones', plegado: true, items: resto },
  ]
}

/** Destinos extra del riel (iPad vertical) junto a los principales. */
export function extrasRiel({ completo = false } = {}) {
  const por = Object.fromEntries(ITEMS_MAS.map((i) => [i.to, i]))
  return completo ? [por['/patrimonio'], por['/sincronizacion']] : [por['/sincronizacion']]
}

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
