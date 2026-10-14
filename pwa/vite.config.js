import { execSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// Versión de la app: número de package.json, momento del build y commit corto. Se inyectan como
// constantes (ver src/lib/version.js) y también se publican en /version.json para que una app
// abierta pueda saber si ya hay una compilación más nueva.
const paquete = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8'))
function commitCorto() {
  const v = process.env.VERCEL_GIT_COMMIT_SHA || process.env.COMMIT_SHA
  if (v) return v.slice(0, 7)
  try {
    return execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim() || 'dev'
  } catch {
    return 'dev'
  }
}
const INFO_VERSION = { version: paquete.version, build: new Date().toISOString(), commit: commitCorto() }

function emitirVersionJson() {
  return {
    name: 'cuadrame-version-json',
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'version.json', source: JSON.stringify(INFO_VERSION) })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), emitirVersionJson()],
  define: {
    __APP_VERSION__: JSON.stringify(INFO_VERSION.version),
    __APP_BUILD__: JSON.stringify(INFO_VERSION.build),
    __APP_COMMIT__: JSON.stringify(INFO_VERSION.commit),
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    globals: false,
    pool: 'vmThreads',
    testTimeout: 20000,
    hookTimeout: 20000,
  },
  build: {
    rollupOptions: {
      output: {
        // Las librerías cambian poco y la app cambia en cada despliegue: separarlas hace que,
        // tras una actualización, el celular solo baje el código propio y reutilice del caché
        // (service worker, cache-first por hash) React, el router y el motor de animación.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (/node_modules[\/](react|react-dom|scheduler|react-router|react-router-dom|@remix-run)[\/]/.test(id)) return 'vendor-react'
          if (/node_modules[\/]@supabase[\/]/.test(id)) return 'vendor-auth'
          return undefined
        },
      },
    },
  },
  server: {
    host: true,
  },
})
