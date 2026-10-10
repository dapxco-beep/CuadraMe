import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
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
