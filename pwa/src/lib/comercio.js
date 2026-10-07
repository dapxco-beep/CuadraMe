// Saca el nombre del comercio de una descripción bancaria, igual que el backend
// (autocat.patron_de_comercio): 'Compra en JUAN VALDEZ SKANDIA con tarjeta débito'
// -> 'JUAN VALDEZ SKANDIA'. Se muestra editable antes de crear la regla.
const PREFIJOS =
  /^\s*(compra|pago|retiro|abono|cargo|transferencia|consignacion|consignación|debito|débito)(\s+(en|a|de|por|desde|pse|nequi|tarjeta|tc|td))*\s+/i
const CORTES = /\s+(con\s+tarjeta|con\s+tc|con\s+td|tarjeta|ref\b|nro\b|no\.|#|cuenta\b|cta\b|\d{3,})/i

export function patronDeComercio(descripcion) {
  const texto = (descripcion || '').trim()
  let resto = texto.replace(PREFIJOS, '')
  const m = CORTES.exec(resto)
  if (m) resto = resto.slice(0, m.index)
  let patron = resto.replace(/\s+/g, ' ').replace(/^[\s\-*.,:]+|[\s\-*.,:]+$/g, '')
  if (patron.length < 2) patron = texto.replace(/\s+/g, ' ')
  return patron.slice(0, 60)
}

// --- Huella de comercio: MISMO algoritmo que backend/app/clave_comercio.py ---------------
// 'PAGO EN VENTO COLIVING 0105' y 'COMPRA VENTO COLIVING BOGOTA' -> 'vento coliving'.
// Sirve para mostrar "Recordar para «vento coliving»" y para detectar el mismo movimiento
// en varios extractos. El servidor vuelve a calcularla: esta es solo la vista previa.
const PREFIJOS_OP = new Set(
  ('pago pagos compra compras en a de del por desde pse abono retiro transferencia transf trf tarjeta tc td debito ' +
    'credito internacional nacional cargo consignacion envio giro recibiste enviaste cuota avance pos app nequi ' +
    'daviplata bancolombia davivienda bre b movimiento mov').split(' ')
)
const CORTES_OP = new Set(
  'con terminacion term ref referencia nro numero cuenta cta tarjeta autorizacion aut cod codigo'.split(' ')
)
const RUIDO = new Set(
  ('sas sa ltda ltd inc llc cia scs bog bta med cal co col com www http https cop usd dc colombia bogota medellin ' +
    'cali barranquilla cartagena bucaramanga pereira manizales cucuta ibague armenia villavicencio neiva pasto ' +
    'monteria valledupar popayan tunja envigado itagui sabaneta bello soacha chia cajica zipaquira rionegro ' +
    'floridablanca giron piedecuesta dosquebradas palmira tulua buenaventura amzn esp cundinamarca antioquia ' +
    'valle atlantico santander sucursal suc').split(' ')
)
const COLA = new Set('de del la el los las en y e a al por para and'.split(' '))
const VACIAS = new Set(
  ('otros otro pago compra transferencia banco tienda servicio servicios cliente gasto ingreso cuota valor total ' +
    'movimiento persona efectivo app web online internet el la los las una uno mi tu comercio tarjeta cuenta cobro ' +
    'debito credito abono retiro pse nomina comision intereses iva suscripcion mensual anual').split(' ')
)
const MAX_PALABRAS = 3

export function claveComercio(descripcion) {
  if (!descripcion) return ''
  let t = String(descripcion).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
  t = t.replace(/\b(s\s*\.\s*a\s*\.\s*s|s\s*\.\s*a|s\s*\.\s*en\s*c|e\s*\.\s*s\s*\.\s*p|ltda)\b\.?/gi, ' ')
  t = t.replace(/\b\d{1,4}[/\-.]\d{1,2}([/\-.]\d{1,4})?\b/g, ' ')
  t = t.replace(/['`´]/g, '').replace(/[^a-z0-9]+/g, ' ')
  const limpios = []
  let inicio = true
  for (const tok of t.split(' ').filter(Boolean)) {
    if (inicio && PREFIJOS_OP.has(tok)) continue
    inicio = false
    if (CORTES_OP.has(tok)) {
      if (limpios.length) break
      continue
    }
    limpios.push(tok)
  }
  const res = limpios.filter((tok) => {
    if (RUIDO.has(tok) || /^\d+$/.test(tok) || tok.length === 1) return false
    if (/\d/.test(tok) && tok.length > 3) return false
    return true
  })
  while (res.length && COLA.has(res[res.length - 1])) res.pop()
  while (res.length && COLA.has(res[0])) res.shift()
  return res.slice(0, MAX_PALABRAS).join(' ')
}

/** Motivo por el que una huella es demasiado amplia para guardarse sin confirmar; null si es segura. */
export function huellaPeligrosa(huella) {
  const h = (huella || '').trim()
  if (!h) return 'No se reconoció un comercio en la descripción'
  const palabras = h.split(' ')
  if (palabras.every((p) => VACIAS.has(p))) return `«${h}» es una palabra muy genérica y afectaría muchos movimientos`
  if (palabras.length === 1 && palabras[0].length < 4) return `«${h}» es demasiado corta y podría coincidir con muchos comercios`
  return null
}

export const RAZON_AUTO = {
  regla: 'por tu regla',
  comercio: 'por comercio conocido',
  similar: 'similar a movimientos tuyos',
  sugerida: 'sugerida por tu correo',
  wallet: 'por tu pago con el celular',
  atajo: 'por tu atajo',
}

// Un movimiento "espera revisión" si la app lo categorizó sola sin confirmar,
// o si quedó en 'Otros' (los traslados propios no cuentan).
export function esAuto(m) {
  return m.cat_confirmada === false
}
export function porRevisar(m) {
  return m.fuente !== 'transferencia_interna' && (esAuto(m) || m.categoria === 'Otros')
}
