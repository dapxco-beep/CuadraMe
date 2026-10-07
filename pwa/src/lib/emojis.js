// Emojis por grupos, con palabras clave en español para la búsqueda.
// Es una lista práctica (no el estándar Unicode completo, que pesaría cientos
// de KB): para cualquier otro emoji, el selector tiene un campo donde se puede
// escribir con el teclado emoji del teléfono.
export const GRUPOS_EMOJI = [
  {
    id: 'comida', titulo: 'Comida', icono: '🍔',
    items: [
      ['🍔', 'hamburguesa comida'], ['🍕', 'pizza'], ['🌮', 'taco'], ['🥪', 'sandwich almuerzo'], ['🍗', 'pollo'],
      ['🥩', 'carne'], ['🍣', 'sushi'], ['🍜', 'sopa fideos ramen'], ['🥗', 'ensalada saludable'], ['🍳', 'huevo desayuno'],
      ['🥐', 'panaderia pan'], ['🍞', 'pan'], ['🧀', 'queso'], ['🍟', 'papas fritas'], ['🍿', 'crispetas cine'],
      ['🍰', 'torta postre'], ['🍩', 'dona'], ['🍦', 'helado'], ['🍫', 'chocolate dulce'], ['🍎', 'manzana fruta'],
      ['🍌', 'banano fruta'], ['🥑', 'aguacate'], ['🥕', 'verdura zanahoria'], ['🛒', 'mercado supermercado compras'],
      ['☕', 'cafe'], ['🍺', 'cerveza'], ['🍷', 'vino'], ['🥤', 'gaseosa bebida'], ['🧃', 'jugo'], ['🍽️', 'restaurante'],
    ],
  },
  {
    id: 'transporte', titulo: 'Transporte', icono: '🚗',
    items: [
      ['🚗', 'carro auto'], ['🚕', 'taxi'], ['🚌', 'bus'], ['🚇', 'metro'], ['🚲', 'bicicleta'], ['🛵', 'moto scooter'],
      ['🏍️', 'moto'], ['✈️', 'avion vuelo viaje'], ['🚆', 'tren'], ['🚢', 'barco'], ['⛽', 'gasolina combustible'],
      ['🅿️', 'parqueadero'], ['🛣️', 'peaje carretera'], ['🚦', 'semaforo multa'], ['🧳', 'maleta viaje'], ['🗺️', 'mapa'],
      ['🏨', 'hotel'], ['🏖️', 'playa vacaciones'], ['⛺', 'camping'], ['🎫', 'tiquete boleta'],
    ],
  },
  {
    id: 'hogar', titulo: 'Hogar', icono: '🏠',
    items: [
      ['🏠', 'casa hogar'], ['🏢', 'edificio apartamento'], ['🛋️', 'sofa muebles'], ['🛏️', 'cama'], ['🚿', 'ducha agua'],
      ['💡', 'luz energia'], ['🔌', 'electricidad'], ['📶', 'internet wifi'], ['📺', 'televisor tv'], ['🧹', 'aseo limpieza'],
      ['🧺', 'lavanderia ropa'], ['🔧', 'reparacion herramienta'], ['🔨', 'martillo arreglo'], ['🪴', 'planta'], ['🔑', 'llave arriendo'],
      ['🧯', 'seguro'], ['🗑️', 'basura'], ['🔥', 'gas'], ['💧', 'agua'], ['📦', 'paquete domicilio'],
    ],
  },
  {
    id: 'salud', titulo: 'Salud y cuidado', icono: '💊',
    items: [
      ['💊', 'medicina pastillas farmacia'], ['🩺', 'doctor medico'], ['🏥', 'hospital clinica'], ['🦷', 'dentista odontologia'],
      ['👓', 'gafas optica'], ['💉', 'vacuna inyeccion'], ['🩹', 'curita'], ['🧘', 'yoga meditacion'], ['🏋️', 'gimnasio pesas'],
      ['🏃', 'correr ejercicio'], ['⚽', 'futbol deporte'], ['🏀', 'baloncesto'], ['🎾', 'tenis'], ['🏊', 'natacion'],
      ['💅', 'unas manicure'], ['💇', 'peluqueria corte'], ['🧴', 'crema cosmeticos'], ['🪥', 'cepillo dientes'], ['🧠', 'psicologia terapia'],
    ],
  },
  {
    id: 'ocio', titulo: 'Ocio', icono: '🎬',
    items: [
      ['🎬', 'cine pelicula'], ['🎮', 'videojuegos'], ['🎧', 'musica audifonos'], ['🎵', 'musica'], ['🎤', 'concierto karaoke'],
      ['🎸', 'guitarra'], ['🎹', 'piano'], ['🎨', 'arte pintura'], ['📚', 'libros lectura'], ['📖', 'libro'], ['🎲', 'juegos mesa'],
      ['🎯', 'meta objetivo'], ['🎉', 'fiesta celebracion'], ['🎂', 'cumpleanos'], ['🎁', 'regalo'], ['🍿', 'cine crispetas'],
      ['📷', 'camara fotos'], ['🎟️', 'entrada evento'], ['🧩', 'rompecabezas'], ['📱', 'celular suscripcion'], ['📺', 'streaming'],
    ],
  },
  {
    id: 'dinero', titulo: 'Dinero y trabajo', icono: '💰',
    items: [
      ['💰', 'dinero ingresos'], ['💵', 'billete efectivo'], ['💳', 'tarjeta credito'], ['🏦', 'banco'], ['🪙', 'moneda'],
      ['💸', 'gasto plata'], ['📈', 'inversion sube'], ['📉', 'baja perdida'], ['🧾', 'factura recibo'], ['💼', 'trabajo empleo'],
      ['🧮', 'calculo cuentas'], ['🏷️', 'etiqueta otros'], ['↔️', 'transferencia'], ['🤝', 'acuerdo negocio'], ['🧑‍💻', 'freelance programador'],
      ['🏛️', 'impuestos gobierno'], ['📊', 'grafico'], ['🔐', 'ahorro seguro'], ['🐷', 'alcancia ahorro'], ['💎', 'lujo diamante'],
      ['🎓', 'educacion universidad'], ['📝', 'matricula curso'], ['💻', 'computador tecnologia'], ['🖨️', 'impresion'],
    ],
  },
  {
    id: 'familia', titulo: 'Familia y mascotas', icono: '👨‍👩‍👧',
    items: [
      ['👨‍👩‍👧', 'familia'], ['👶', 'bebe hijo'], ['🧒', 'nino'], ['🍼', 'biberon pañales'], ['🧸', 'juguetes'], ['👵', 'abuela'],
      ['❤️', 'amor pareja'], ['💍', 'matrimonio anillo'], ['🐶', 'perro mascota'], ['🐱', 'gato mascota'], ['🐾', 'mascota veterinaria'],
      ['🐟', 'pez'], ['🐦', 'ave'], ['🦴', 'hueso comida perro'], ['🎒', 'colegio mochila'], ['✏️', 'utiles escolares'],
      ['👕', 'ropa camisa'], ['👟', 'zapatos tenis'], ['👗', 'vestido'], ['🧥', 'chaqueta'], ['👜', 'bolso'], ['⌚', 'reloj'],
    ],
  },
  {
    id: 'naturaleza', titulo: 'Naturaleza y más', icono: '🌳',
    items: [
      ['🌳', 'arbol'], ['🌸', 'flores'], ['🌞', 'sol'], ['🌧️', 'lluvia'], ['⭐', 'estrella favorito'], ['🔥', 'fuego'],
      ['🌍', 'mundo'], ['🐎', 'caballo'], ['🦄', 'unicornio'], ['🌈', 'arcoiris'], ['🍀', 'suerte'], ['🪐', 'planeta'],
      ['🚀', 'cohete proyecto'], ['⚡', 'rayo'], ['🙏', 'donacion gracias'], ['🕯️', 'vela'], ['⛪', 'iglesia diezmo'],
      ['✅', 'listo'], ['❓', 'duda'], ['🔔', 'alerta'], ['🛠️', 'herramientas'], ['🧾', 'cuentas'],
    ],
  },
]

// Emoji de una sola "letra" visual: la ZWJ, tonos de piel, banderas y teclas
// cuentan como UN carácter para el usuario aunque en Unicode sean varios.
export function primerGrafema(texto) {
  if (!texto) return ''
  if (typeof Intl !== 'undefined' && Intl.Segmenter) {
    const seg = new Intl.Segmenter('es', { granularity: 'grapheme' })
    const partes = [...seg.segment(texto)].map((s) => s.segment)
    return partes[partes.length - 1] || ''
  }
  const arr = [...texto]
  return arr[arr.length - 1] || ''
}

// ¿Es un emoji (y no letras/números)? Misma idea que el backend (autocat.es_emoji).
export function esEmoji(texto) {
  if (!texto || texto.length > 16) return false
  if (/[\p{L}\p{N}\s]/u.test(texto)) return false
  return /\p{Extended_Pictographic}|\p{Regional_Indicator}/u.test(texto)
}

export function buscarEmojis(consulta) {
  const q = consulta
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .trim()
  if (!q) return []
  const vistos = new Set()
  const salida = []
  for (const g of GRUPOS_EMOJI) {
    for (const [e, palabras] of g.items) {
      if (!vistos.has(e) && (palabras.includes(q) || palabras.split(' ').some((p) => p.startsWith(q)))) {
        vistos.add(e)
        salida.push(e)
      }
    }
  }
  return salida
}
