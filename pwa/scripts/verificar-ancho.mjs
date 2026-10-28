// Verifica en un navegador real (Chromium con emulación de móvil) que ninguna pantalla clave tenga
// scroll horizontal ni elementos que se salgan de la pantalla. Usa datos sintéticos: la API se
// intercepta, no se toca ningún servidor ni dato real.
//
// Uso (con la app corriendo, p. ej. `npm run dev -- --port 5199`):
//   node scripts/verificar-ancho.mjs [url-base] [carpeta-capturas]
// Requiere `playwright-core` (npm i -D playwright-core) y un Chromium de Playwright instalado.
// Variables: PW_CHROMIUM = ruta al ejecutable (opcional), SUPABASE_REF = host de VITE_SUPABASE_URL
// sin dominio (por defecto "x", de https://x.supabase.co).
import { mkdirSync } from 'node:fs'

const BASE = process.argv[2] || 'http://localhost:5199'
const CAPTURAS = process.argv[3] || ''
const REF = process.env.SUPABASE_REF || 'x'

const { chromium } = await import('playwright-core')

const hoy = new Date()
const iso = (d) => d.toISOString()
const dias = (n) => new Date(hoy.getTime() - n * 86400000)

const CUENTAS = [
  { id: 'c1', nombre: process.env.PW_MARKETING ? 'Cuenta de ahorros' : 'Bancolombia Ahorros con un nombre bastante largo', tipo: 'ahorro', saldo: 12345678, moneda: 'COP', icono: '\u{1F3E6}' },
  { id: 'c2', nombre: 'Nu Tarjeta', tipo: 'credito', saldo: -1850000, moneda: 'COP', icono: '\u{1F4B3}', cupo_total: 5000000, dia_corte: 10, dia_pago: 25 },
  { id: 'c3', nombre: 'Efectivo', tipo: 'efectivo', saldo: 80000, moneda: 'COP', icono: '\u{1F4B5}' },
]
const CATEGORIAS = [
  ['Comida', '\u{1F354}'], ['Transporte', '\u{1F68C}'], ['Hogar', '\u{1F3E0}'], ['Ocio', '\u{1F3AC}'], ['Otros', '\u{1F4B3}'],
].map(([nombre, icono], i) => ({ id: `k${i}`, nombre, icono, activa: true, color: null, tipo: 'ambos' }))
const MOVS = Array.from({ length: 14 }, (_, i) => ({
  id: `m${i}`, cuenta_id: CUENTAS[i % 3].id, descripcion: i % 4 === 0 ? 'COMPRA EN UN COMERCIO CON UN NOMBRE REALMENTE MUY LARGO SIN ESPACIOS_EXTRA_LARGOS_12345678901234567890' : `Compra ${i}`,
  categoria: CATEGORIAS[i % 5].nombre, tipo: i % 5 === 0 ? 'income' : 'expense', monto: 15000 + i * 123456, fecha: iso(dias(i)),
  fuente: 'manual', cat_confirmada: i % 3 !== 0, notas: '',
}))
const MESES = Array.from({ length: 6 }, (_, i) => {
  const d = new Date(hoy.getFullYear(), hoy.getMonth() - (5 - i), 1)
  return { clave: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`, etiqueta: `m${i + 1}` }
})
const ESTADO_SINC = {
  meses: MESES,
  cuentas: CUENTAS.slice(0, 2).map((c) => ({
    id: c.id, nombre: c.nombre, icono: c.icono,
    meses: MESES.map((m, i) => ({ mes: m.clave, estado: ['conciliado', 'extracto_pendiente', 'falta_clave', 'sin_extracto', 'vacio', 'conciliado'][i], movimientos: i, conciliados: 0, por_confirmar: 0, extractos: i % 2 })),
  })),
  sin_cuenta: [{ banco: 'Davivienda', correos: 2, extractos: 1 }],
  tareas: [
    { id: 'falta_clave', titulo: 'Falta la clave del PDF', detalle: '', cantidad: 2, ruta: '/sincronizacion#clave' },
    { id: 'correos_por_revisar', titulo: 'Correos por revisar', detalle: '', cantidad: 3, ruta: '/correos' },
  ],
  correos_ya_registrados: 2, ultima_sync: iso(dias(1)),
  punto_partida: { definido: false, modo: null, fecha: null, saldos: {}, anteriores: { correos: 4, extractos: 1 } },
}
const EXTRACTOS = [
  { id: 'e1', banco: 'Bancolombia', periodo: '01/09/2026 a 30/09/2026', asunto: 'Tu extracto', archivo: 'a.pdf', estado: 'falta_clave', clave_estado: 'no_abrio', cuenta_sugerida_id: 'c1' },
  { id: 'e2', banco: 'Davivienda con un nombre muy largo de banco', periodo: 'agosto 2026', asunto: 'Extracto', archivo: 'b.pdf', estado: 'nuevo', cuenta_sugerida_id: null, cuentas_candidatas: ['c1', 'c2'], pregunta_cuenta: '¿De cuál de tus cuentas Davivienda es este extracto?' },
]
const CLAVE = {
  configurada: true, cantidad_claves: 1, protegidos: 2, abrieron: 1, no_abrieron: 1, por_probar: 0,
  por_banco: [{ banco: 'Bancolombia', protegidos: 1, abrieron: 0, no_abrieron: 1, por_probar: 0 }, { banco: 'Davivienda', protegidos: 1, abrieron: 1, no_abrieron: 0, por_probar: 0 }],
  extractos: [
    { id: 'e1', nombre: 'Bancolombia 01/09/2026 a 30/09/2026', banco: 'Bancolombia', resultado: 'no_abrio', estado: 'falta_clave' },
    { id: 'e2', nombre: 'Davivienda agosto 2026', banco: 'Davivienda', resultado: 'abrio', estado: 'nuevo' },
  ],
}


const BONITO = !!process.env.PW_MARKETING
const NOM = BONITO
  ? { hogar: 'Apartamento', col: 'Inscripción del torneo', luis: 'Luis', ana: 'Ana', mercado: 'Mercado del mes', correo: 'luis@ejemplo.com' }
  : { hogar: 'Apartamento con un nombre bastante largo', col: 'Inscripción del torneo de fútbol sin espacios_extra_largos_1234567890', luis: 'Luis Fernando Rodríguez Hernández', ana: 'Ana María', mercado: 'Mercado del mes con una descripción larguísima sin espacios_extra_largos_12345678', correo: 'alguien.con.un.correo.largo@ejemplo.com' }

function responder(url, metodo) {
  const p = url.pathname
  if (process.env.PW_NUEVO) {
    if (['/cuentas', '/movimientos', '/correos/pendientes', '/correos/extractos'].includes(p)) return []
    if (p === '/cuentas/resumen') return { total: 0, disponible: 0, deuda_tarjetas: 0, cuentas: [], por_moneda: [], por_tipo: [] }
    if (p === '/correos/gmail/estado') return { conectado: false }
    if (p === '/sincronizacion/estado') return { meses: [], cuentas: [], sin_cuenta: [], tareas: [], ultima_sync: null, punto_partida: { definido: false } }
    if (p === '/conciliacion/cuadre/resumen') return { hay_problema: false, n_no_cuadran: 0, cuentas: [] }
    if (p === '/reportes/mensual') return { mes: '2026-10', ingresos: 0, gastos: 0, balance: 0, top_categorias: [], salud: { score: 0, tips: [], nivel: 'bien' }, por_categoria: {} }
  }
  if (p === '/consentimientos') return { requiere_autorizacion: false, consentimientos: [], items: [] }
  if (p === '/cuentas') return CUENTAS
  if (p === '/categorias') return CATEGORIAS
  if (p === '/movimientos') return MOVS
  if (p === '/sincronizacion/estado') return ESTADO_SINC
  if (p === '/sincronizacion/por-categorizar') return { items: [], total: 12, limite: 20, offset: 0 }
  if (p === '/cierre-mes') return []
  if (p === '/cierre-mes/preferencias') return { correo: false }
  if (p === '/cierre-mes/extractos') return { hay_datos: true, etiqueta: 'Septiembre', moneda_base: 'COP', parcial: false, meses: [], monedas_sin_tasa: [], total: {}, resumen_bancos: [{ banco: 'Nu', estado: 'cuadra' }, { banco: 'Nequi', estado: 'no_cuadra', diferencia: 39496 }], bancos: [{ banco: 'Nu', estado: 'cuadra', cuentas: [{ cuenta_id: 'c2', nombre: 'Nu', estado: 'cuadra', moneda: 'COP', diferencia: 0 }] }, { banco: 'Nequi', estado: 'no_cuadra', diferencia: 39496, cuentas: [{ cuenta_id: 'c3', nombre: 'Nequi', estado: 'no_cuadra', moneda: 'COP', diferencia: 39496 }] }] }
  if (p === '/insights/alertas-proactivas') return { comisiones: [{ descripcion: 'Cuota de manejo', total_mes: 20000, veces: 1 }], cobros_duplicados: [{ movimiento_id_1: 'm1', descripcion: 'Netflix', monto: 30000 }] }
  if (p === '/correos/gmail/estado') return { conectado: true, email: 'persona@gmail.com', etiqueta: 'gastos' }
  if (p === '/correos/extractos') return EXTRACTOS
  if (p === '/correos/clave-pdf') return CLAVE
  if (p === '/correos/pendientes') return []
  if (p === '/perfil/punto-de-partida') return ESTADO_SINC.punto_partida
  if (p === '/perfil/punto-de-partida/cobertura') return { meses: [], cuentas: [] }
  if (p === '/perfil/punto-de-partida/conciliacion') return { cuentas: [], todo_coincide: false }
  if (p === '/reportes/mensual') {
    return {
      mes: '2026-10', ingresos: 4500000, gastos: 2300000, balance: 2200000, top_categorias: [
        { categoria: 'Comida', monto: 900000 }, { categoria: 'Transporte', monto: 400000 },
      ],
      salud: { score: 72, tips: ['Vas bien: sigue así.'], nivel: 'bien' }, por_categoria: {},
    }
  }
  if (p === '/reportes/tendencias') return { meses: [] }
  if (p === '/presupuestos/en-mi-bolsillo') {
    return { saldo_total: 10575678, disponible_real: 800000, disponible_real_por_dia: 40000, compromisos: [], comprometido: 0, dias_restantes: 20 }
  }
  if (p === '/presupuestos/disponible-hoy') return { disponible_hoy: 40000, dias_restantes: 20, presupuestos: [] }
  if (p === '/cuentas/resumen') return { total: 10575678, disponible: 12425678, deuda_tarjetas: 1850000, cuentas: CUENTAS, por_moneda: [], por_tipo: [] }
  if (p === '/conexiones/estado') return { hay_falla: false }
  if (p === '/conciliacion/cuadre/resumen') return { hay_problema: true, n_no_cuadran: 1, aviso: '', cuentas: [{ cuenta_id: 'c2', cuenta: 'Nu Colombia Crédito', estado: 'no_cuadra', mes: '2026-10', diferencia: -160000, texto: 'No cuadra en octubre (dif. $160.000)' }] }
  if (/\/(conteo|por-revisar|por-confirmar)/.test(p)) return metodo === 'GET' && p.endsWith('conteo') ? { conteo: 0 } : []
  if (p.startsWith('/colectas/publico/')) return { nombre: NOM.col, descripcion: '', moneda: 'COP', estado: 'abierta', fecha_limite: null, meta: 900000, recogido: 420000, falta: 480000, datos_pago: 'Llave Bre-B: @torneo-futbol', participantes: [{ id: 'a1', nombre: 'Ana', estado: 'pagado', avisado: false }, { id: 'a2', nombre: 'Luis', estado: 'falta', avisado: false }, { id: 'a3', nombre: 'Camila', estado: 'falta', avisado: true }] }
  if (p === '/colectas') return [{ id: 'k1', nombre: NOM.col, moneda: 'COP', estado: 'abierta', meta: 900000, recogido: 420000, falta: 480000, personas: 9, pagaron: 4, compartida: true }]
  if (p === '/colectas/k1') return { id: 'k1', nombre: NOM.col, descripcion: '', modo: 'por_persona', moneda: 'COP', estado: 'abierta', fecha_limite: iso(dias(-9)), cuenta_id: 'c1', meta: 900000, recogido: 420000, falta: 480000, personas: 3, pagaron: 1, compartida: true, token_publico: 't'.repeat(32), datos_pago: 'Llave Bre-B: @torneo-futbol', participantes: [{ aporte_id: 'a1', participante_id: 'x1', nombre: NOM.luis, telefono: '3001234567', debe: 100000, pagado: 0, falta: 100000, estado: 'falta', avisado: true, pagos: [] }, { aporte_id: 'a2', participante_id: 'x2', nombre: 'Ana', telefono: '', debe: 100000, pagado: 40000, falta: 60000, estado: 'parcial', pagos: [{ id: 'p1', monto: 40000, fecha: iso(dias(2)), registrado_en_cuenta: true }] }, { aporte_id: 'a3', participante_id: 'x3', nombre: 'Camila', telefono: '', debe: 100000, pagado: 100000, falta: 0, estado: 'pagado', pagos: [{ id: 'p2', monto: 100000, fecha: iso(dias(3)), registrado_en_cuenta: false }] }] }
  if (p === '/hogares') return [{ id: 'h1', nombre: NOM.hogar, moneda: 'COP', rol: 'admin', mi_miembro_id: 'ma', miembros: 3, mi_saldo: -123456 }]
  if (p === '/hogares/invitaciones/mias') return [{ token: 'y'.repeat(30), hogar: 'Casa de los compañeros', vence_en: iso(dias(-5)) }]
  if (p === '/hogares/h1') return { id: 'h1', nombre: NOM.hogar, moneda: 'COP', rol: 'admin', mi_miembro_id: 'ma', mis_avisos: true, miembros: [{ id: 'ma', apodo: NOM.ana, rol: 'admin', activo: true, soy_yo: true, saldo: 150000 }, { id: 'mb', apodo: NOM.luis, rol: 'miembro', activo: true, soy_yo: false, saldo: -90000 }, { id: 'mc', apodo: 'Camila', rol: 'miembro', activo: true, soy_yo: false, saldo: -60000 }], simplificado: [{ de: 'mb', a: 'ma', monto: 90000, de_nombre: NOM.luis, a_nombre: NOM.ana }, { de: 'mc', a: 'ma', monto: 60000, de_nombre: 'Camila', a_nombre: NOM.ana }], invitaciones: [{ id: 'i1', token: 't'.repeat(32), email: NOM.correo, vence_en: iso(dias(-6)) }] }
  if (p === '/hogares/h1/gastos') return [{ id: 'g1', descripcion: NOM.mercado, categoria: 'Comida', total: 450000, moneda: 'COP', fecha: iso(dias(2)), pagador: NOM.ana, creado_por_id: 'ma', partes: [] }, { id: 'g2', descripcion: 'Arriendo', categoria: 'Hogar', total: 1800000, moneda: 'COP', fecha: iso(dias(9)), pagador: 'Camila', creado_por_id: 'mc', partes: [] }]
  if (p === '/hogares/h1/resumen') return { mes: '2026-10', moneda: 'COP', total: 2250000, por_miembro: [{ miembro_id: 'ma', nombre: NOM.ana, puso: 450000, consumio: 750000 }, { miembro_id: 'mc', nombre: 'Camila', puso: 1800000, consumio: 750000 }], por_categoria: [{ categoria: 'Hogar', monto: 1800000 }, { categoria: 'Comida', monto: 450000 }] }
  if (p.startsWith('/hogares/invitaciones/')) return { hogar: 'Casa de los compañeros', moneda: 'COP', vence_en: iso(dias(-5)) }
  return metodo === 'GET' ? [] : {}
}

const PANTALLAS = process.env.PW_PANTALLAS
  ? process.env.PW_PANTALLAS.split(',').map((x) => [x.slice(0, x.indexOf(':')), x.slice(x.indexOf(':') + 1)])
  : [['Inicio', '/'], ['Movimientos', '/movimientos'], ['Cuentas', '/cuentas'], ['Traer movimientos', '/sincronizacion'], ['Perfil', '/perfil']]
// PW_ANCHOS="1280x900" y PW_PANTALLAS="Tabla:/movimientos?vista=tabla" permiten revisar otros tamaños y rutas.
const ANCHOS = process.env.PW_ANCHOS ? process.env.PW_ANCHOS.split(',').map((x) => x.split('x').map(Number)) : [[360, 740], [390, 844]]

const navegador = await chromium.launch({ headless: true, executablePath: process.env.PW_CHROMIUM || undefined })
let fallos = 0
if (CAPTURAS) mkdirSync(CAPTURAS, { recursive: true })

for (const [ancho, alto] of ANCHOS) {
  const ctx = await navegador.newContext({
    viewport: { width: ancho, height: alto }, deviceScaleFactor: ancho < 800 ? 3 : 1, isMobile: ancho < 800, hasTouch: ancho < 800,
    userAgent: process.env.PW_UA || 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  })
  // Sesión sintética (supabase-js la lee de localStorage sin pedir nada a la red mientras no venza).
  await ctx.addInitScript(({ ref, tema }) => {
    const sesion = {
      access_token: 'token-falso', refresh_token: 'r', token_type: 'bearer', expires_in: 3600,
      expires_at: Math.floor(Date.now() / 1000) + 3600,
      user: { id: 'u-demo', email: 'demo@example.com', user_metadata: { nombre: 'Persona Demo' } },
    }
    localStorage.setItem(`sb-${ref}-auth-token`, JSON.stringify(sesion))
    sessionStorage.setItem('cuadrame:splash', '1')
    if (tema) localStorage.setItem('findp_theme', tema)
  }, { ref: REF, tema: process.env.PW_TEMA || '' })
  await ctx.route(/localhost:8000/, (route) => {
    if (process.env.PW_REAL) return route.continue() // PW_REAL=1: usa la API local de verdad (con los datos de la demo) en vez de los datos simulados
    const req = route.request()
    const url = new URL(req.url())
    route.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify(responder(url, req.method())),
      headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' },
    })
  })
  const pagina = await ctx.newPage()
  if (process.env.PW_DEBUG) {
    pagina.on('pageerror', (e) => console.log('  [pageerror]', e.message.slice(0, 300)))
    pagina.on('console', (m) => m.type() === 'error' && console.log('  [console]', m.text().slice(0, 300)))
  }
  for (const [nombre, ruta] of PANTALLAS) {
    await pagina.goto(`${BASE}/#${ruta}`)
    await pagina.waitForTimeout(Number(process.env.PW_ESPERA) || 1800)
    if (process.env.PW_CLICK) { // PW_CLICK='Más': abre ese botón antes de medir/capturar (p. ej. la hoja del menú)
      await pagina.getByRole('button', { name: process.env.PW_CLICK }).first().click({ timeout: 3000 }).catch(() => {})
      await pagina.waitForTimeout(700)
    }
    // Traer movimientos: se despliega también el punto de partida (formulario con saldos) y el bloque del correo.
    if (ruta === '/sincronizacion') {
      await pagina.locator('[data-testid="modo-historico"]').click({ timeout: 3000 }).catch(() => {})
      await pagina.getByRole('button', { name: 'Desde tu correo' }).click({ timeout: 3000 }).catch(() => {})
      await pagina.waitForTimeout(500)
    }
    const r = await pagina.evaluate(() => {
      const ancho = document.documentElement.clientWidth
      const fuera = []
      const anchos = [] // PW_DIAG: todo lo que pasa del borde, aunque un contenedor lo recorte
      for (const el of document.querySelectorAll('body *')) {
        const b = el.getBoundingClientRect()
        if (b.width === 0 || b.height === 0) continue
        const estilo = getComputedStyle(el)
        if (estilo.visibility === 'hidden' || estilo.display === 'none') continue
        // un contenedor con scroll propio (carruseles) puede ser más ancho por dentro: lo que cuenta es su caja
        if ((b.right > ancho + 1 || b.left < -1) && anchos.length < 8) anchos.push(`${el.tagName.toLowerCase()}.${String(el.className).slice(0, 50)} [${Math.round(b.left)},${Math.round(b.right)}] ${String(el.textContent).trim().slice(0, 25)}`)
        if (b.right > ancho + 1 || b.left < -1) {
          // se ignora si algún ancestro lo recorta (overflow distinto de visible)
          let p = el.parentElement
          let recortado = false
          while (p && p !== document.body) {
            const o = getComputedStyle(p)
            if (/(auto|scroll|hidden|clip)/.test(o.overflowX)) { recortado = true; break }
            p = p.parentElement
          }
          if (!recortado) fuera.push(`${el.tagName.toLowerCase()}.${String(el.className).slice(0, 60)} [${Math.round(b.left)},${Math.round(b.right)}]`)
        }
      }
      const doc = document.documentElement
      return { ancho, scrollW: doc.scrollWidth, bodyW: document.body.scrollWidth, fuera: fuera.slice(0, 6), anchos, texto: document.body.innerText.slice(0, 60).replace(/\n/g, ' ') }
    })
    const hayScroll = r.scrollW > r.ancho + 1 || r.bodyW > r.ancho + 1
    const ok = !hayScroll && r.fuera.length === 0
    if (!ok) fallos += 1
    if (process.env.PW_DIAG && r.anchos.length) console.log("   pasa del borde:", JSON.stringify(r.anchos))
    console.log(`${ok ? 'OK ' : 'MAL'} ${ancho}x${alto} ${nombre}: scrollW=${r.scrollW}/${r.ancho} bodyW=${r.bodyW}${r.fuera.length ? ' fuera=' + JSON.stringify(r.fuera) : ''} :: ${r.texto}`)
    // PW_SCROLL=1600: baja la pantalla antes de la captura (la app hace scroll dentro de un contenedor, no de la página)
    if (process.env.PW_SCROLL) {
      await pagina.evaluate((y) => { const el = [...document.querySelectorAll('div')].find((d) => getComputedStyle(d).overflowY === 'auto' && d.scrollHeight > d.clientHeight); if (el) el.scrollTop = y }, Number(process.env.PW_SCROLL))
      await pagina.waitForTimeout(400)
    }
    if (CAPTURAS) await pagina.screenshot({ path: `${CAPTURAS}/${ancho}-${nombre.replace(/\s+/g, '_')}.png`, fullPage: false })
  }
  await ctx.close()
}
await navegador.close()
console.log(fallos ? `\n${fallos} pantalla(s) con problemas` : '\nSin overflow horizontal ni elementos fuera de pantalla')
process.exit(fallos ? 1 : 0)
