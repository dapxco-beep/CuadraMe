// Regla contable en el cliente: ESPEJO de backend/app/contabilidad.py (misma regla, mismos casos:
// backend/tests/fixtures/contabilidad_casos.json lo prueban los dos lados).
//
// Qué NO es ingreso ni gasto (neutral = 'transfer'): traslados entre tus cuentas, pagos de tarjeta
// (y su abono), ajustes de saldo y aportes a meta. Un traslado propio se reconoce por su PAREJA
// (egreso e ingreso del mismo monto en cuentas distintas, <= 2 días), por una decisión de la persona
// o por una regla que ella pidió recordar; NO por la categoría «Transferencias» ni por el tipo guardado.
//
// El servidor es la fuente de verdad de los reportes. Esto solo evita que los totales que se calculan
// en pantalla (Movimientos, gastos de la semana en Inicio) cuenten distinto.

export const CATEGORIA_PAGO_TARJETA = 'Pago de tarjeta'
export const MARCA_TRASLADO_PROPIO = 'posible_traslado_propio'
export const MARCA_NO_TRASLADO = 'no_es_traslado'
export const MARCA_ES_TRASLADO = 'es_traslado_propio'
export const TOLERANCIA_COMISION = 2000
const VENTANA_SEG = 2 * 86400
// Puentes festivos: 4 días solo con pistas fuertes (suma >= 3). Espejo de VENTANA_FESTIVO_SEG.
const VENTANA_FESTIVO_SEG = 4 * 86400

const CATEGORIAS_NEUTRAS = ['transferencia', 'pago de tarjeta', 'ajuste de saldo', 'aporte a meta']
const NOMBRES_SISTEMA = ['Intereses de tarjeta', 'Cuota de manejo', 'Comisiones y seguros', '4x1000 (GMF)', 'Rendimientos']

export function sinAcentos(t) {
  return (t || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
}

const ENTIDAD_TARJETA =
  'nu|nubank|nu\\s+colombia|bancolombia|davivienda|bbva|banco\\s+de\\s+bogota|bogota|falabella|rappi|rappicard|' +
  'lulo|scotiabank|colpatria|itau|av\\s+villas|banco\\s+popular|occidente|santander|citibank|tuya|exito'
const CONECTORES = '(?:(?:de|a|la|mi|tu|total|minimo|del)\\s+)*'
const PAGO_TARJETA = new RegExp(
  '\\b(?:pagos?|abonos?|pagaste|abonaste)\\s+' + CONECTORES +
    '(?:tarjeta|tarj\\.?|tc|tdc|t\\.c\\.?|visa|master\\s?card|amex|american\\s+express|diners)\\b' +
    '|\\b(?:pagos?|abonos?|pagaste|abonaste)\\s+' + CONECTORES +
    '(?:' + ENTIDAD_TARJETA + ')\\s+(?:tarjeta|tarj\\.?|tc|tdc|t\\.c\\.?|credito)\\b',
  'i'
)

export function esPagoTarjeta(descripcion) {
  return PAGO_TARJETA.test(sinAcentos(descripcion))
}

const PATRON_TRASLADO = new RegExp(
  'transfer|traslado|\\btrasl\\b|entre\\s+cuentas|nequi|daviplata|\\bdale\\b|movii|' +
    '\\benvi[oa]|enviaste|recibiste|bre-?b|a\\s+mi\\s+cuenta|desde\\s+mi\\s+cuenta|' +
    'a\\s+tu\\s+cuenta|de\\s+tu\\s+cuenta|^\\s*para\\s+\\S|' +
    '\\benviad[oa]\\b|\\brecibid[oa]\\b|\\bavances?\\b(?!\\s+de\\s+obra)',
  'i'
)
const BANCOS_PROPIOS = 'nu|nequi|bancolombia|davivienda|daviplata|dale|bbva|movii|bre-?b|lulo|rappipay'
const PATRON_PROPIO_FUERTE = new RegExp(
  'entre\\s+(?:tus|mis)\\s+cuentas|\\b(?:a|de|desde|hacia)\\s+(?:tu|mi)\\s+(?:propia\\s+)?cuenta\\b|\\bcajita\\b|\\bbolsillo\\b|' +
    '\\brecarga\\s+(?:de\\s+|a\\s+|en\\s+|desde\\s+)?(?:mi\\s+|tu\\s+)?(?:' + BANCOS_PROPIOS + ')\\b|' +
    '\\b(?:' + BANCOS_PROPIOS + ')\\s*(?:→|->|=>|\\ba\\b|\\bhacia\\b)\\s*(?:' + BANCOS_PROPIOS + ')\\b',
  'i'
)

// Frases de «es mío» sin nombre (espejo de PATRON_PROPIO_FRASES): «Envío a mi Nequi», «Bre-B a mi llave»,
// «Consignación a cuenta propia», «Movimiento entre cuentas», «Traslado a ahorro», «Avance en efectivo».
const PROPIOS_DESTINO =
  'cuenta|nequi|nu|nubank|bancolombia|davivienda|daviplata|dale|bbva|movii|lulo|rappipay|llave|bre-?b|ahorros?|cajita|bolsillo|meta|alcancia|vault'
const PATRON_PROPIO_FRASES = new RegExp(
  '\\b(?:a|de|desde|hacia|para)\\s+(?:mi|tu)\\s+(?:propia\\s+)?(?:' + PROPIOS_DESTINO + ')\\b|' +
    '\\bcuentas?\\s+propias?\\b|\\bpropias?\\s+cuentas?\\b|\\bmismo\\s+titular\\b|' +
    '\\b(?:movimientos?|traslados?)\\s+entre\\s+cuentas\\b|' +
    '\\btraslados?\\s+(?:a|hacia|de)\\s+(?:mi\\s+)?(?:cajita|bolsillo|ahorros?|meta|alcancia|vault)\\b|' +
    '\\bavances?\\s+(?:en\\s+)?(?:efectivo|cajero|tarjeta|tc|tdc|credito|cupo)\\b',
  'i'
)
function esPropioPorFrase(desc) {
  const d = sinAcentos(desc || '')
  return PATRON_PROPIO_FUERTE.test(d) || PATRON_PROPIO_FRASES.test(d)
}

// ── Costos y rendimientos del banco (nunca son un traslado). Espejo reducido de costos_financieros.py.
const PREFIJOS_COSTO = new Set(['pago', 'pagos', 'cargo', 'cargos', 'abono', 'cobro', 'valor', 'debito', 'credito', 'de', 'por', 'del', 'la', 'el', 'los', 'las', 'mensual', 'automatico', 'automatica', 'tc', 'tdc', 'tarjeta', 'nu', 'bancolombia', 'davivienda', 'bbva', 'nequi', 'daviplata', 'iva', 'impuesto', 'total', 'tu', 'su', 'mi', 'aplicado', 'aplicada', 'nuevo', 'nueva', 'devolucion', 'reverso', 'reversion', 'reintegro'])
const CONCEPTOS_COSTO = [
  'intereses de corriente', 'intereses de corrientes', 'intereses corrientes', 'intereses corriente', 'interes corriente',
  'interes corrientes', 'intereses de mora', 'interes de mora', 'intereses mora', 'interes mora', 'intereses moratorios',
  'intereses de compras', 'intereses compras', 'intereses de avances', 'intereses avances', 'intereses de financiacion',
  'intereses por financiacion', 'intereses financiacion', 'intereses sobregiro', 'intereses de sobregiro',
  'cuota de manejo', 'cuota manejo', 'gmf', 'gravamen', 'gravamen movimientos financieros',
  'gravamen a los movimientos financieros', 'gravamen al movimiento', 'gravamen al movimiento financiero',
  'gravamen movimiento financiero', '4x1000', '4 x 1000', '4 por mil', '4 por 1000', 'cuatro por mil',
  'comision', 'comisiones', 'seguro deudores', 'seguro de deudores', 'seguro deudor', 'seguro de deudor',
  'seguro desempleo', 'seguro de desempleo', 'seguro tarjeta', 'cobro seguro', 'costo transaccion',
  'costo de transaccion', 'costo transferencia', 'cobro por transferencia', 'retiro cajero ajeno',
  'retiro en cajero ajeno', 'retiro cajero otra red', 'retiro otra red', 'cobro',
  'intereses ganados', 'interes ganado', 'intereses ganado', 'abono intereses', 'abono de intereses',
  'intereses abonados', 'pago de intereses', 'intereses cajita', 'intereses cajitas', 'intereses bolsillo',
  'intereses bolsillos', 'intereses de ahorro', 'intereses de ahorros', 'interes cuenta de ahorros',
  'interes cuenta de ahorro', 'intereses cuenta de ahorros', 'intereses cuenta ahorros', 'interes cuenta ahorros',
  'interes cdt', 'intereses cdt', 'rendimientos', 'rendimiento',
].map((c) => c.split(' ')).sort((a, b) => b.length - a.length)
const NO_ES_COBRO_TRAS_COMISION = new Set(['express', 'ventas', 'inmobiliaria', 'corredores', 'y', 'ganadas', 'ganada', 'recibidas', 'recibida'])

function palabrasCosto(d) {
  const t = sinAcentos((d || '').toLowerCase()).replace(/[^a-z0-9]+/g, ' ').trim()
  return t ? t.split(/\s+/) : []
}

export function esCostoORendimiento(descripcion) {
  const p = palabrasCosto(descripcion)
  if (!p.length) return false
  for (const frase of CONCEPTOS_COSTO) {
    const n = frase.length
    for (let i = 0; i <= Math.min(4, p.length - n); i++) {
      if (p.slice(i, i + n).join(' ') !== frase.join(' ') || !p.slice(0, i).every((x) => PREFIJOS_COSTO.has(x))) continue
      const resto = p.slice(i + n)
      const f = frase.join(' ')
      if ((f === 'comision' || f === 'comisiones') && resto.length && NO_ES_COBRO_TRAS_COMISION.has(resto[0])) continue
      if (f === 'cobro' && resto.length && ['en', 'tienda', 'pedido'].includes(resto[0])) continue
      const devolucion = p.slice(0, i).some((x) => ['devolucion', 'reverso', 'reversion', 'reintegro'].includes(x))
      if ((f.startsWith('rendimiento') || f.includes('intereses ganado') || f.includes('interes ganado')) && devolucion) continue
      return true
    }
  }
  return false
}

function sinCosto(m) {
  return !(NOMBRES_SISTEMA.includes(m.categoria) || esCostoORendimiento(m.descripcion || ''))
}

// ── Decisiones, nombres y huellas ────────────────────────────────────────────────────────────
const NOMBRE_VACIAS = new Set(['de', 'del', 'la', 'las', 'los', 'el', 'y', 'san', 'da', 'van'])
function listaTokens(t) {
  return (sinAcentos(t || '').toLowerCase().match(/[a-z]{3,}/g) || []).filter((x) => !NOMBRE_VACIAS.has(x))
}
function tokensNombre(t) {
  return new Set(listaTokens(t))
}

// Cuántas palabras del nombre de la persona aparecen en la descripción (sin tildes ni mayúsculas).
// La última palabra puede ser un nombre truncado por el banco (prefijo de >= 4 letras).
export function mencionesPropias(descripcion, nombres = []) {
  const toks = listaTokens(descripcion)
  const d = new Set(toks)
  if (!d.size) return 0
  const ult = toks[toks.length - 1]
  let mejor = 0
  for (const n of nombres || []) {
    const nt = tokensNombre(n)
    let c = 0
    for (const x of nt) if (d.has(x)) c++
    if (ult.length >= 4 && !nt.has(ult) && [...nt].some((x) => x.startsWith(ult) && !d.has(x))) c++
    mejor = Math.max(mejor, c)
  }
  return mejor
}

const STOP_HUELLA = new Set(['de', 'del', 'la', 'el', 'los', 'las', 'a', 'para', 'por', 'en', 'con', 'y', 'mi', 'tu', 'su', 'enviaste', 'envio', 'envia', 'recibiste', 'recibi', 'transferencia', 'transferiste', 'transf', 'trf', 'traslado', 'pago', 'abono', 'deposito', 'giro', 'nequi', 'daviplata', 'bre', 'bancolombia', 'davivienda', 'nu', 'movimiento', 'cuenta', 'ahorros', 'desde', 'hacia', 'pse', 'llave'])

// Huella para recordar decisiones: la contraparte sin números ni verbos bancarios ('' si no sirve).
export function huellaTraslado(descripcion) {
  const t = sinAcentos(descripcion || '').toLowerCase().replace(/\d+/g, ' ')
  const toks = (t.match(/[a-z]{2,}/g) || []).filter((x) => !STOP_HUELLA.has(x))
  const h = toks.slice(0, 4).join(' ')
  return h.length >= 4 ? h : ''
}

function notasDe(m) {
  return m.notas || ''
}

function decision(m, reglas) {
  const n = notasDe(m)
  if (n.includes(MARCA_NO_TRASLADO)) return 'real'
  if (n.includes(MARCA_ES_TRASLADO)) return 'traslado'
  if (reglas) return reglas[huellaTraslado(m.descripcion || '')] || null
  return null
}

function fuerzaPista(m, nombres) {
  if (!sinCosto(m)) return 0
  const desc = m.descripcion || ''
  const n = notasDe(m)
  let f = 0
  if (PATRON_TRASLADO.test(sinAcentos(desc))) f += 1
  if (n.includes(MARCA_TRASLADO_PROPIO)) f += 2
  if (n.includes(MARCA_ES_TRASLADO)) f += 2
  if (esPropioPorFrase(desc)) f += 2
  const menc = mencionesPropias(desc, nombres)
  return f + (menc >= 2 ? 2 : menc)
}

function pistaFuerte(m, nombres) {
  if (!sinCosto(m)) return false
  const desc = m.descripcion || ''
  return notasDe(m).includes(MARCA_TRASLADO_PROPIO) || esPropioPorFrase(desc) || mencionesPropias(desc, nombres) >= 2
}

// Motivo por el que UN movimiento es neutral mirándolo solo a él, o null.
function razonDura(m, tipos = {}) {
  if (m.tipo !== 'income' && m.tipo !== 'expense') return 'traslado_app'
  if (m.fuente === 'transferencia_interna') return 'traslado_app'
  if (m.fuente === 'ajuste_saldo') return 'ajuste'
  if (m.fuente === 'aporte_meta') return 'aporte_meta'
  const cat = sinAcentos(m.categoria || '').trim().toLowerCase()
  if (CATEGORIAS_NEUTRAS.includes(cat) && !notasDe(m).includes(MARCA_NO_TRASLADO)) {
    return { 'pago de tarjeta': 'pago_tarjeta', 'ajuste de saldo': 'ajuste', 'aporte a meta': 'aporte_meta' }[cat] || 'categoria'
  }
  if (m.tipo === 'expense' && esPagoTarjeta(m.descripcion || '')) return 'pago_tarjeta'
  if (m.tipo === 'income' && tipos[m.cuenta_id] === 'credito') return 'abono_tarjeta'
  return null
}

function redondeoPar(x) {
  // round() de Python (mitades al par) para que el índice por monto coincida con el servidor.
  const f = Math.floor(x)
  const d = x - f
  if (d < 0.5) return f
  if (d > 0.5) return f + 1
  return f % 2 === 0 ? f : f + 1
}

const tiempo = (m) => new Date(m.fecha).getTime() / 1000
const montoDe = (m) => Number(m.monto) || 0

function lowerBound(arr, x) {
  let lo = 0
  let hi = arr.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (arr[mid] < x) lo = mid + 1
    else hi = mid
  }
  return lo
}
function upperBound(arr, x) {
  let lo = 0
  let hi = arr.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (arr[mid] <= x) lo = mid + 1
    else hi = mid
  }
  return lo
}
const cmpClave = (a, b) => {
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1
  return 0
}

// ctx: { tipos: {cuentaId: 'ahorro'|'credito'|...}, monedas: {cuentaId: 'COP'}, reglas: {huella: 'traslado'|'real'},
//        nombres: [..], toleranciaComision }.  Devuelve { [id]: { tipo, razon, par } }.
export function clasificar(movs, ctx = {}) {
  const tipos = ctx.tipos || {}
  const reglas = ctx.reglas || {}
  const nombres = ctx.nombres || []
  const monedas = ctx.monedas || {}
  const tol = ctx.toleranciaComision ?? TOLERANCIA_COMISION
  const res = {}
  const gastos = []
  const ingresos = []
  for (const m of movs) {
    const razon = razonDura(m, tipos)
    if (razon) {
      res[m.id] = { tipo: 'transfer', razon, par: null }
      continue
    }
    res[m.id] = { tipo: m.tipo, razon: 'normal', par: null }
    const dec = decision(m, reglas)
    if (dec === 'real') continue
    if (dec === 'traslado') res[m.id] = { tipo: 'transfer', razon: notasDe(m).includes(MARCA_ES_TRASLADO) ? 'decision' : 'regla', par: null }
    ;(m.tipo === 'expense' ? gastos : ingresos).push(m)
  }
  const moneda = (m) => monedas[m.cuenta_id] || m.moneda
  const usados = new Set()
  const emparejar = (g, i, razon) => {
    usados.add(i.id)
    usados.add(g.id)
    res[g.id] = { tipo: 'transfer', razon, par: i.id }
    res[i.id] = { tipo: 'transfer', razon, par: g.id }
  }
  const pg = gastos.filter((x) => x.fecha)
  const pi = ingresos.filter((x) => x.fecha)
  if (pg.length && pi.length) {
    const fuerza = {}
    for (const x of [...pg, ...pi]) fuerza[x.id] = fuerzaPista(x, nombres)
    const porMonto = new Map()
    for (const i of pi) {
      const k = redondeoPar(Math.abs(montoDe(i)))
      if (!porMonto.has(k)) porMonto.set(k, [])
      porMonto.get(k).push(i)
    }
    const claves = new Map()
    for (const [k, lista] of porMonto) {
      lista.sort((a, b) => tiempo(a) - tiempo(b))
      claves.set(k, lista.map(tiempo))
    }
    const orden = [...pg].sort((a, b) => tiempo(a) - tiempo(b) || (String(a.id) < String(b.id) ? -1 : 1))
    for (const g of orden) {
      const k = redondeoPar(Math.abs(montoDe(g)))
      const lista = porMonto.get(k)
      if (!lista) continue
      const t = tiempo(g)
      const ks = claves.get(k)
      const desde = lowerBound(ks, t - VENTANA_FESTIVO_SEG)
      const hasta = upperBound(ks, t + VENTANA_FESTIVO_SEG)
      let mejor = null
      for (const i of lista.slice(desde, hasta)) {
        if (usados.has(i.id) || i.cuenta_id === g.cuenta_id) continue
        if (Math.abs(montoDe(i) - montoDe(g)) >= 1) continue
        const mg = moneda(g)
        const mi = moneda(i)
        if (mg && mi && mg !== mi) continue
        const f = fuerza[g.id] + fuerza[i.id]
        if (!f) continue
        const dt = Math.abs(tiempo(i) - t)
        if (dt > VENTANA_SEG && f < 3) continue // puente festivo: solo con pistas fuertes
        const clave = [-f, dt, String(i.id)]
        if (!mejor || cmpClave(clave, mejor.clave) < 0) mejor = { clave, i }
      }
      if (mejor) emparejar(g, mejor.i, 'par')
    }
    if (tol > 0) {
      const libres = pi.filter((i) => !usados.has(i.id)).sort((a, b) => tiempo(a) - tiempo(b))
      const tiempos = libres.map(tiempo)
      for (const g of orden) {
        if (usados.has(g.id)) continue
        const t = tiempo(g)
        let mejor = null
        for (const i of libres.slice(lowerBound(tiempos, t - VENTANA_SEG), upperBound(tiempos, t + VENTANA_SEG))) {
          const dif = montoDe(g) - montoDe(i)
          if (usados.has(i.id) || i.cuenta_id === g.cuenta_id || !(dif > 0 && dif <= tol)) continue
          const mg = moneda(g)
          const mi = moneda(i)
          if (mg && mi && mg !== mi) continue
          if (fuerza[g.id] + fuerza[i.id] < 3) continue
          const clave = [dif, Math.abs(tiempo(i) - t), String(i.id)]
          if (!mejor || cmpClave(clave, mejor.clave) < 0) mejor = { clave, i }
        }
        if (mejor) emparejar(g, mejor.i, 'par_comision')
      }
    }
  }
  for (const m of [...gastos, ...ingresos]) {
    if (res[m.id].razon === 'normal' && pistaFuerte(m, nombres)) res[m.id] = { tipo: 'transfer', razon: 'posible', par: null }
  }
  return res
}

// { [id]: 'income'|'expense'|'transfer' } para toda la lista.
export function tiposEfectivos(movs, ctx = {}) {
  const c = clasificar(movs, ctx)
  return Object.fromEntries(Object.entries(c).map(([id, v]) => [id, v.tipo]))
}

// Contexto para clasificar a partir de la lista de cuentas de la app (`/cuentas`).
export function contextoDeCuentas(cuentas = [], extra = {}) {
  return {
    tipos: Object.fromEntries(cuentas.map((c) => [c.id, c.tipo])),
    monedas: Object.fromEntries(cuentas.map((c) => [c.id, c.moneda])),
    ...extra,
  }
}

// Tipo efectivo de UN movimiento mirándolo solo a él (sin emparejar). Para totales usa `tiposEfectivos`.
export function tipoEfectivo(m, tiposCuenta = {}) {
  return razonDura(m, tiposCuenta) ? 'transfer' : m.tipo
}

// Ingresos, gastos y balance de una lista: ÚNICO lugar del cliente donde se suman.
export function totalesIngresosGastos(movs, ctx = {}, filtro = () => true) {
  const te = tiposEfectivos(movs, ctx)
  let ingresos = 0
  let gastos = 0
  for (const m of movs) {
    if (!filtro(m)) continue
    if (te[m.id] === 'income') ingresos += montoDe(m)
    else if (te[m.id] === 'expense') gastos += montoDe(m)
  }
  return { ingresos, gastos, balance: ingresos - gastos, tasaAhorro: ingresos > 0 ? ((ingresos - gastos) / ingresos) * 100 : null }
}

// Suma ingresos/gastos de `items` con tipos efectivos ya calculados (`te` = tiposEfectivos de TODA la lista, así un
// traslado cuya otra pata está fuera del grupo sigue siendo neutral). Sirve para subtotales por día o por selección.
export function totalesConTipos(items, te) {
  let ingresos = 0
  let gastos = 0
  for (const m of items) {
    if (te[m.id] === 'income') ingresos += montoDe(m)
    else if (te[m.id] === 'expense') gastos += montoDe(m)
  }
  return { ingresos, gastos, neto: ingresos - gastos }
}

// Moneda base: espejo de a_base() en backend/app/contabilidad.py. `tasas` = {MONEDA: unidades de base
// por 1 de esa moneda}. Devuelve [valor, convertido]; sin tasa NO se suma a ciegas (convertido=false).
export function aBase(monto, origen, base, tasas = {}) {
  const b = String(base || 'COP').toUpperCase()
  const o = String(origen || b).toUpperCase()
  const v = Number(monto) || 0
  if (o === b) return [v, true]
  const t = tasas[o]
  if (!t || t <= 0) return [v, false]
  return [v * t, true]
}
