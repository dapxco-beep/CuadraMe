import { PAISES } from './paises'

// Entidades financieras vigiladas por la Superfinanciera + billeteras digitales
// más comunes en Colombia. Usado como sugerencia de autocompletado, no es una
// lista cerrada — el campo sigue siendo texto libre.
export const ENTIDADES_FINANCIERAS_CO = [
  'Bancolombia',
  'Davivienda',
  'BBVA Colombia',
  'Banco de Bogotá',
  'Banco de Occidente',
  'Banco Popular',
  'Banco Caja Social',
  'Banco AV Villas',
  'Scotiabank Colpatria',
  'Itaú',
  'Banco Falabella',
  'Banco Pichincha',
  'Banco Agrario',
  'Banco W',
  'Bancamía',
  'Mibanco',
  'Coltefinanciera',
  'Finandina',
  'Banco Serfinanza',
  'Bancoomeva',
  'Confiar',
  'Cotrafá',
  'Tuya',
  'Nequi',
  'Daviplata',
  'Nu Colombia',
  'Lulo Bank',
  'Movii',
  'RappiPay',
  'RappiCard',
  'Ualá',
  'Tpaga',
  'Dale!',
]

// Identidad visual por entidad: no son los logos oficiales (son marca registrada,
// sin licencia de uso), sino un monograma propio con el color real de cada marca —
// mismo lenguaje que usan Nequi/Nu en sus propios widgets. bg/fg en hex para que
// tanto CSS como el theme de la app los puedan leer igual.
const MARCA_DEFAULT = { mono: '$', bg: '#6b5b45', fg: '#ffffff' }

export const MARCAS_FINANCIERAS_CO = {
  'Bancolombia': { mono: 'BC', bg: '#FFDD00', fg: '#0033A0' },
  'Davivienda': { mono: 'DV', bg: '#EE3831', fg: '#ffffff' },
  'BBVA Colombia': { mono: 'BBVA', bg: '#072146', fg: '#ffffff' },
  'Banco de Bogotá': { mono: 'BB', bg: '#FFC20E', fg: '#002856' },
  'Banco de Occidente': { mono: 'BO', bg: '#00A84F', fg: '#ffffff' },
  'Banco Popular': { mono: 'BP', bg: '#E30613', fg: '#ffffff' },
  'Banco Caja Social': { mono: 'CS', bg: '#F58220', fg: '#ffffff' },
  'Banco AV Villas': { mono: 'AV', bg: '#EC1C24', fg: '#ffffff' },
  'Scotiabank Colpatria': { mono: 'SC', bg: '#EC111A', fg: '#ffffff' },
  'Itaú': { mono: 'IT', bg: '#FF6200', fg: '#ffffff' },
  'Banco Falabella': { mono: 'F', bg: '#00B14F', fg: '#ffffff' },
  'Banco Pichincha': { mono: 'BP', bg: '#FFD100', fg: '#003DA5' },
  'Banco Agrario': { mono: 'BA', bg: '#FBB034', fg: '#1B5E20' },
  'Banco W': { mono: 'W', bg: '#EE3124', fg: '#ffffff' },
  'Bancamía': { mono: 'BM', bg: '#F7941D', fg: '#ffffff' },
  'Mibanco': { mono: 'MB', bg: '#D91F5C', fg: '#ffffff' },
  'Coltefinanciera': { mono: 'CF', bg: '#004B87', fg: '#ffffff' },
  'Finandina': { mono: 'FN', bg: '#00529B', fg: '#ffffff' },
  'Banco Serfinanza': { mono: 'SF', bg: '#0072BC', fg: '#ffffff' },
  'Bancoomeva': { mono: 'BO', bg: '#00A651', fg: '#ffffff' },
  'Confiar': { mono: 'CN', bg: '#006B3C', fg: '#ffffff' },
  'Cotrafá': { mono: 'CT', bg: '#005A9C', fg: '#ffffff' },
  'Tuya': { mono: 'TY', bg: '#E4032E', fg: '#ffffff' },
  'Nequi': { mono: 'N', bg: '#1A0B33', fg: '#FF0FA8' },
  'Daviplata': { mono: 'DP', bg: '#EE3831', fg: '#ffffff' },
  'Nu Colombia': { mono: 'Nu', bg: '#820AD1', fg: '#ffffff' },
  'Lulo Bank': { mono: 'L', bg: '#0A0F2C', fg: '#6EE7F0' },
  'Movii': { mono: 'M', bg: '#00D3AB', fg: '#0A0F2C' },
  'RappiPay': { mono: 'RP', bg: '#FF441F', fg: '#ffffff' },
  'RappiCard': { mono: 'RC', bg: '#FF441F', fg: '#ffffff' },
  'Ualá': { mono: 'U', bg: '#2D2D2D', fg: '#B6FF4D' },
  'Tpaga': { mono: 'TP', bg: '#5B2A86', fg: '#ffffff' },
  'Dale!': { mono: 'D!', bg: '#FFCC00', fg: '#1A1A1A' },
}

export function marcaDeEntidad(nombreCuenta) {
  if (!nombreCuenta) return MARCA_DEFAULT
  const nombreLower = nombreCuenta.toLowerCase()
  const match = Object.keys(MARCAS_FINANCIERAS_CO).find((entidad) =>
    nombreLower.includes(entidad.toLowerCase())
  )
  if (match) return MARCAS_FINANCIERAS_CO[match]
  // Bancos de otros países (registro lib/paises.js): mismo criterio, por nombre.
  for (const c of Object.values(PAISES)) {
    const b = c.bancos.find((x) => x.bg && nombreLower.includes(x.nombre.toLowerCase()))
    if (b) return { mono: b.mono, bg: b.bg, fg: b.fg }
  }
  return MARCA_DEFAULT
}
