// Genera TODOS los activos de marca (íconos PWA/iOS, favicon, splash nativo y
// SVG de marca) a partir de la geometría única de src/brand/geometria.js.
// Reproducible y sin imágenes de origen: `npm run icons` (usa sharp, que es
// solo devDependency; no entra al paquete que se despliega).
import sharp from 'sharp'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { CUERPO, FICHA, CHECK, COLORES, svgIsotipo } from '../src/brand/geometria.js'

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const ICONOS = path.join(RAIZ, 'public/icons')
const MARCA = path.join(RAIZ, 'public/brand')
const IOS = path.join(RAIZ, 'ios/App/App/Assets.xcassets')
for (const d of [ICONOS, MARCA]) fs.mkdirSync(d, { recursive: true })

// Colores del ícono de la app: fondo terracota con la marca en crema y dorado.
const ICONO = { fondoA: '#e4742f', fondoB: '#b9461a', cuerpo: '#fbf6ec', ficha: '#f4c25a', check: '#221f19' }

// Ícono cuadrado a pantalla completa. `escala` = ancho visual de la marca / lienzo.
// Los maskable usan menos escala para quedar dentro de la zona segura (80 %).
function svgIcono(S, { escala = 0.6, retícula = true, check = true } = {}) {
  const k = (escala * S) / 52 // 52 = ancho visual del isotipo en su viewBox
  const t = S / 2 - 32 * k
  const paso = S / 8
  let lineas = ''
  if (retícula) {
    for (let i = 1; i < 8; i++) {
      lineas += `<path d="M${i * paso} 0V${S}M0 ${i * paso}H${S}" />`
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${S}" height="${S}" viewBox="0 0 ${S} ${S}">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${ICONO.fondoA}"/><stop offset="1" stop-color="${ICONO.fondoB}"/></linearGradient></defs>
  <rect width="${S}" height="${S}" fill="url(#g)"/>
  <g stroke="#fff" stroke-opacity="0.07" stroke-width="${Math.max(1, S / 512)}" fill="none">${lineas}</g>
  <g transform="translate(${t} ${t}) scale(${k})">
    <path d="${CUERPO}" fill="#000" fill-opacity="0.16" transform="translate(0 1.6)"/>
    <path d="${CUERPO}" fill="${ICONO.cuerpo}"/>
    <path d="${FICHA}" fill="${ICONO.ficha}"/>
    ${check ? `<path d="${CHECK}" fill="none" stroke="${ICONO.check}" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>` : ''}
  </g>
</svg>`
}

// Solo la marca (monocroma, fondo transparente) para el ícono "monochrome" de Android.
function svgMonocromo(S) {
  const k = (0.5 * S) / 52
  const t = S / 2 - 32 * k
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${S}" height="${S}" viewBox="0 0 ${S} ${S}"><g transform="translate(${t} ${t}) scale(${k})">${svgIsotipo({ variante: 'mono', size: 64 })
    .replace(/^<svg[^>]*>/, '')
    .replace(/<\/svg>$/, '')}</g></svg>`
}

async function png(svg, destino, tam, { plano = false } = {}) {
  let img = sharp(Buffer.from(svg), { density: 300 }).resize(tam, tam)
  if (plano) img = img.flatten({ background: '#e4742f' }) // iOS no admite transparencia
  await img.png({ compressionLevel: 9 }).toFile(destino)
}

// ── Íconos de la app ──────────────────────────────────────────────────
const maestro = svgIcono(1024)
await png(maestro, `${ICONOS}/master-1024.png`, 1024, { plano: true })
await png(maestro, `${ICONOS}/icon-512.png`, 512)
await png(maestro, `${ICONOS}/icon-192.png`, 192)
await png(svgIcono(1024), `${ICONOS}/apple-touch-icon.png`, 180, { plano: true })
await png(svgIcono(1024, { escala: 0.5 }), `${ICONOS}/icon-maskable-512.png`, 512, { plano: true })
await png(svgMonocromo(1024), `${ICONOS}/icon-monochrome-512.png`, 512)
// Favicons: sin retícula ni check (a 32 px solo estorban)
await png(svgIcono(1024, { retícula: false, check: false, escala: 0.66 }), `${ICONOS}/favicon-64.png`, 64)
await png(svgIcono(1024, { retícula: false, check: false, escala: 0.66 }), `${ICONOS}/favicon-32.png`, 32)
await png(maestro, path.join(IOS, 'AppIcon.appiconset/AppIcon-512@2x.png'), 1024, { plano: true })

// ── SVG de marca (favicon vectorial y variantes del isotipo) ────────────
fs.writeFileSync(
  `${ICONOS}/favicon.svg`,
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="${ICONO.fondoB}"/><g transform="translate(5.4 5.4) scale(0.83)"><path d="${CUERPO}" fill="${ICONO.cuerpo}"/><path d="${FICHA}" fill="${ICONO.ficha}"/></g></svg>`
)
fs.writeFileSync(`${MARCA}/isotipo-claro.svg`, svgIsotipo({ variante: 'claro', size: 256 }))
fs.writeFileSync(`${MARCA}/isotipo-oscuro.svg`, svgIsotipo({ variante: 'oscuro', size: 256 }))
fs.writeFileSync(`${MARCA}/isotipo-mono.svg`, svgIsotipo({ variante: 'mono', size: 256 }))
// Lockup horizontal: el wordmark usa Sora (la fuente de la app). Si Sora no está
// instalada el navegador cae a una sans-serif; para impresión, convertir a curvas.
const lockup = (variante) => {
  const c = COLORES[variante]
  const inner = svgIsotipo({ variante, size: 64 }).replace(/^<svg[^>]*>/, '').replace(/<\/svg>$/, '')
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 64" width="300" height="64" role="img" aria-label="CuadraMe">${inner}<text x="76" y="43" font-family="Sora, system-ui, sans-serif" font-size="34" font-weight="700" letter-spacing="-1.2" fill="${c.tinta}">Cuadra<tspan fill="${c.cuerpo}">Me</tspan></text></svg>`
}
fs.writeFileSync(`${MARCA}/lockup-claro.svg`, lockup('claro'))
fs.writeFileSync(`${MARCA}/lockup-oscuro.svg`, lockup('oscuro'))

// ── Splash nativo ─────────────────────────────────────────────────────
// Fondo liso + isotipo centrado. Sin texto: sharp no tiene la fuente Sora.
async function splash(ancho, alto, variante, destino) {
  const c = COLORES[variante]
  const lado = Math.round(Math.min(ancho, alto) * 0.3)
  const marca = Buffer.from(svgIsotipo({ variante, size: lado }))
  await sharp({ create: { width: ancho, height: alto, channels: 3, background: c.fondo } })
    .composite([{ input: await sharp(marca, { density: 300 }).resize(lado, lado).png().toBuffer(), gravity: 'center' }])
    .png({ compressionLevel: 9, palette: true })
    .toFile(destino)
}

// [ancho, alto, ancho CSS, alto CSS, ratio] — iPhone y iPad vigentes
export const DISPOSITIVOS = [
  [1320, 2868, 440, 956, 3],
  [1206, 2622, 402, 874, 3],
  [1290, 2796, 430, 932, 3],
  [1179, 2556, 393, 852, 3],
  [1284, 2778, 428, 926, 3],
  [1170, 2532, 390, 844, 3],
  [1125, 2436, 375, 812, 3],
  [1242, 2688, 414, 896, 3],
  [828, 1792, 414, 896, 2],
  [750, 1334, 375, 667, 2],
  [2048, 2732, 1024, 1366, 2],
  [1668, 2388, 834, 1194, 2],
  [1640, 2360, 820, 1180, 2],
]
fs.mkdirSync(`${ICONOS}/splash`, { recursive: true })
for (const [w, h] of DISPOSITIVOS) {
  await splash(w, h, 'claro', `${ICONOS}/splash/splash-${w}x${h}.png`)
  await splash(w, h, 'oscuro', `${ICONOS}/splash/splash-${w}x${h}-oscuro.png`)
}
// Splash de la app empaquetada con Capacitor (iOS)
for (const f of ['splash-2732x2732.png', 'splash-2732x2732-1.png', 'splash-2732x2732-2.png']) {
  await splash(2732, 2732, 'claro', path.join(IOS, 'Splash.imageset', f))
}

// Etiquetas <link rel="apple-touch-startup-image"> para index.html
const etiquetas = DISPOSITIVOS.flatMap(([w, h, cw, ch, r]) =>
  ['claro', 'oscuro'].map((v) => {
    const arch = `/icons/splash/splash-${w}x${h}${v === 'oscuro' ? '-oscuro' : ''}.png`
    const esquema = v === 'oscuro' ? 'dark' : 'light'
    return `    <link rel="apple-touch-startup-image" href="${arch}" media="(device-width: ${cw}px) and (device-height: ${ch}px) and (-webkit-device-pixel-ratio: ${r}) and (orientation: portrait) and (prefers-color-scheme: ${esquema})" />`
  })
)
// Se inyectan entre los marcadores de index.html (así el script es idempotente)
const htmlPath = path.join(RAIZ, 'index.html')
const html = fs.readFileSync(htmlPath, 'utf8')
const re = /(<!-- splash:inicio -->)[\s\S]*?(<!-- splash:fin -->)/
if (re.test(html)) {
  fs.writeFileSync(htmlPath, html.replace(re, `$1\n${etiquetas.join('\n')}\n    $2`))
}

console.log('Marca generada: íconos, favicon, splash y SVG.')
