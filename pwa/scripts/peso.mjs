// Peso de arranque de la PWA: suma lo que el navegador baja ANTES de poder mostrar algo (los archivos que
// index.html pide: scripts, módulos precargados y estilos), ya comprimido con gzip, que es lo que viaja por la red.
// Uso: npm run build && npm run peso. Falla si pasa del tope (pensado para 4G: ~1 s por cada 400 KB).
import { readFileSync, existsSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import { join } from 'node:path'

const TOPE_KB = Number(process.env.PESO_TOPE_KB || 450)
const dist = new URL('../dist/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const html = readFileSync(join(dist, 'index.html'), 'utf8')
const archivos = [...html.matchAll(/(?:src|href)="\/(assets\/[^"]+\.(?:js|css))"/g)].map((m) => m[1])
let total = 0
for (const a of [...new Set(archivos)]) {
  const ruta = join(dist, a)
  if (!existsSync(ruta)) continue
  const kb = gzipSync(readFileSync(ruta)).length / 1024
  total += kb
  console.log(`${kb.toFixed(1).padStart(7)} KB  ${a}`)
}
console.log(`${total.toFixed(1).padStart(7)} KB  TOTAL de arranque (gzip) · tope ${TOPE_KB} KB`)
if (total > TOPE_KB) {
  console.error('La app pesa más del tope al arrancar: revisa qué se agregó al paquete principal.')
  process.exit(1)
}
