// Genera public/privacidad.html y public/terminos.html (páginas estáticas, sin JS) a partir
// del MISMO texto de las pantallas React, para que el revisor de Google (y cualquiera sin
// sesión) lea la política y no se desincronicen.
//
// Fuente única: src/screens/legal/PoliticaPrivacidad.jsx y TerminosCondiciones.jsx.
// El texto vive solo ahí; este script lo convierte (etiquetas simples: section, h2, p, ul, li,
// b, code, a, div del aviso) a HTML. Regenerar tras editar un texto legal:
//     npm run legales
// (la prueba src/test/legalesEstaticos.test.js falla si los HTML quedaron desactualizados).
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const raiz = resolve(dirname(fileURLToPath(import.meta.url)), '..')

const PAGINAS = [
  { fuente: 'PoliticaPrivacidad.jsx', salida: 'privacidad.html', titulo: 'Política de Privacidad', otra: ['terminos.html', 'Términos y Condiciones'] },
  { fuente: 'TerminosCondiciones.jsx', salida: 'terminos.html', titulo: 'Términos y Condiciones', otra: ['privacidad.html', 'Política de Privacidad'] },
]

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

// Convierte el cuerpo JSX (entre el <div ...space-y-5> y su cierre) a HTML.
export function jsxAHtml(jsx) {
  const ini = jsx.indexOf('space-y-5">')
  if (ini < 0) throw new Error('No se encontró el cuerpo del texto legal')
  let cuerpo = jsx.slice(ini + 'space-y-5">'.length)
  cuerpo = cuerpo.slice(0, cuerpo.lastIndexOf('</div>\n    </div>')) // cierre del cuerpo
  return cuerpo
    .replace(/\{' '\}/g, ' ')
    .replace(/<p className="text-xs text-ink-soft">/, '<p class="version">')
    .replace(/<div className="rounded-2xl[^"]*">/g, '<aside class="aviso">')
    .replace(/<\/div>/g, '</aside>')
    .replace(/<a\s+href="([^"]+)"[^>]*>/g, '<a href="$1" rel="noopener noreferrer">')
    .replace(/<section id="([^"]+)">/g, '<section id="$1">')
    .replace(/<h2 className="[^"]*">/g, '<h2>')
    .replace(/<(ul|p) className="[^"]*">/g, '<$1>')
    .replace(/<li>/g, '<li>')
    .replace(/&/g, '&amp;')
    .replace(/&amp;(amp|lt|gt);/g, '&$1;')
    .replace(/[ \t]*\n[ \t]*/g, '\n')
    .replace(/\n{2,}/g, '\n')
    .trim()
}

function pagina({ titulo, salida, otra }, cuerpo) {
  const otraPag = `<a href="/${otra[0]}">${otra[1]}</a>`
  return `<!doctype html>
<!-- GENERADO por scripts/generar-legales-estaticos.mjs desde src/screens/legal. No editar a mano: npm run legales -->
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(titulo)} · CuadraMe</title>
<meta name="description" content="${esc(titulo)} de CuadraMe, la app de finanzas personales de DAPX.">
<meta name="color-scheme" content="light dark">
<link rel="canonical" href="https://cuadrame.dapx.shop/${salida}">
<style>
:root{--ink:#221f19;--soft:#5d5748;--paper:#f6efe2;--line:#e3d6bf;--accent:#a83f0d;--aviso:#fbe4d3}
@media (prefers-color-scheme:dark){:root{--ink:#f5f1e8;--soft:#b8b09c;--paper:#17140f;--line:#332e24;--accent:#e8823f;--aviso:#332615}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.envoltura{max-width:46rem;margin:0 auto;padding:0 20px}
header{border-bottom:1px solid var(--line);padding:14px 0}
header .envoltura{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:center;justify-content:space-between}
a{color:var(--accent);text-underline-offset:2px}
a:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
h1{font-size:1.7rem;line-height:1.25;margin:28px 0 6px}
h2{font-size:1.1rem;margin:0 0 6px}
section{margin:26px 0}
ul{padding-left:1.3rem}li{margin:6px 0}
.version{color:var(--soft);font-size:.9rem}
.aviso{background:var(--aviso);border-radius:14px;padding:16px;font-size:.92rem;margin:32px 0}
footer{border-top:1px solid var(--line);padding:18px 0 40px;color:var(--soft);font-size:.92rem}
code{font-size:.92em}
</style>
</head>
<body>
<header><div class="envoltura">
<a href="/"><b>CuadraMe</b> · volver a la app</a>
<nav aria-label="Otras páginas legales">${otraPag} · <a href="/bienvenida.html">Qué es CuadraMe</a></nav>
</div></header>
<main class="envoltura">
<h1>${esc(titulo)}</h1>
${cuerpo}
</main>
<footer><div class="envoltura">
<p>Contacto: <a href="mailto:dapxco@gmail.com">dapxco@gmail.com</a> · CuadraMe es una herramienta de organización personal; no es asesoría financiera ni tributaria. Hecha en Colombia por DAPX.</p>
</div></footer>
</body>
</html>
`
}

export function generar() {
  const out = {}
  for (const p of PAGINAS) {
    const jsx = readFileSync(resolve(raiz, 'src/screens/legal', p.fuente), 'utf8')
    out[p.salida] = pagina(p, jsxAHtml(jsx))
  }
  return out
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  for (const [nombre, html] of Object.entries(generar())) {
    writeFileSync(resolve(raiz, 'public', nombre), html)
    console.log('escrito public/' + nombre)
  }
}
