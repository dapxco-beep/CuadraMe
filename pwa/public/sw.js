// Service worker de CuadraMe: notificaciones push + caché del "shell" de la app
// para que abra aunque no haya conexión. Los datos (API, Supabase) NUNCA se
// cachean aquí: un saldo viejo mostrado como si fuera actual es peor que un error.
const VERSION = 'v3'
const CACHE_SHELL = `cuadrame-shell-${VERSION}`
const CACHE_ASSETS = `cuadrame-assets-${VERSION}`

self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const nombres = await caches.keys()
      await Promise.all(
        nombres
          .filter((n) => n.startsWith('cuadrame-') && n !== CACHE_SHELL && n !== CACHE_ASSETS)
          .map((n) => caches.delete(n))
      )
      await self.clients.claim()
    })()
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return

  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return // API, Supabase, fuentes: directo a la red

  // Navegación (abrir la app): red primero para recibir siempre la versión
  // nueva; si no hay conexión, el último index.html guardado.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((resp) => {
          // Solo la app (/) alimenta el caché del shell: otras páginas estáticas, como
          // /bienvenida.html, no deben pisarlo.
          if (url.pathname === '/') {
            const copia = resp.clone()
            caches.open(CACHE_SHELL).then((c) => c.put('/', copia))
          }
          return resp
        })
        .catch(async () => (await caches.match('/')) || Response.error())
    )
    return
  }

  // Archivos con hash en el nombre (/assets/index-abc123.js) nunca cambian:
  // se sirven del caché y solo se bajan la primera vez.
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/')) {
    event.respondWith(
      caches.match(request).then(
        (guardado) =>
          guardado ||
          fetch(request).then((resp) => {
            if (resp.ok) {
              const copia = resp.clone()
              caches.open(CACHE_ASSETS).then((c) => c.put(request, copia))
            }
            return resp
          })
      )
    )
  }
})

self.addEventListener('push', (event) => {
  let data = { title: 'CuadraMe', body: '', url: '/#/' }
  try {
    data = { ...data, ...event.data.json() }
  } catch {
    data.body = event.data ? event.data.text() : ''
  }

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      data: { url: data.url },
    })
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  // El servidor manda rutas ya listas para HashRouter (ej. "/#/presupuesto").
  const destino = new URL(event.notification.data?.url || '/#/', self.location.origin).href

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async (ventanas) => {
      // Si la app ya está abierta, se lleva esa ventana a la pantalla correcta
      // en vez de solo enfocarla (antes la notificación ignoraba el destino).
      for (const ventana of ventanas) {
        if (new URL(ventana.url).origin === self.location.origin) {
          try {
            await ventana.navigate(destino)
          } catch {
            // algunos navegadores no permiten navigate(); basta con enfocar
          }
          return ventana.focus()
        }
      }
      return self.clients.openWindow(destino)
    })
  )
})
