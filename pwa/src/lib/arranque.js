// Precarga del arranque: apenas hay sesión se piden EN PARALELO las lecturas que el Inicio va a
// necesitar. Antes eran tres escalones en fila (autorización -> cuentas -> datos del Inicio) y con
// 150-250 ms de ida y vuelta cada escalón costaba más de medio segundo. Las peticiones se comparten
// (api.js deduplica lecturas idénticas en vuelo y las recuerda unos segundos), así que cuando el
// Inicio las pida de nuevo ya vienen en camino o ya llegaron.
import { api } from './api'
import { fechaHace } from './inicioSimple'

export function precargarArranque() {
  const lecturas = [
    () => api.cuentas(),
    () => api.categorias(true),
    () => api.movimientos(4),
    () => api.reporteMensual(),
    () => api.movimientos(200, 0, { desde: fechaHace(6) }),
    () => api.disponibleHoy(),
    () => api.enMiBolsillo(),
    () => api.resumenCuentas(),
    () => api.gmailEstado(),
    () => api.conexionesEstado(),
    () => api.sincronizacionEstado(),
    () => api.tendencias(6),
  ]
  for (const leer of lecturas) {
    try {
      Promise.resolve(leer()).catch(() => {})
    } catch {
      /* si algo no existe (pruebas con api simulada), no pasa nada */
    }
  }
}
