import { formatMoneda } from './format'
import { telefonoParaWhatsApp } from './gastosCompartidos'

// Enlace de solo lectura que se comparte con el grupo. Va con # porque la app usa HashRouter.
export function enlacePublicoColecta(token, origen = typeof window !== 'undefined' ? window.location.origin : '') {
  return `${origen}/#/c/${token}`
}

// Recordatorio amable por WhatsApp a quien falta. Sin teléfono válido, abre WhatsApp para elegir el contacto.
export function enlaceRecordatorioColecta({ nombre, telefono, falta, moneda = 'COP', colecta, enlace = '' }) {
  const primerNombre = String(nombre || '').trim().split(/\s+/)[0]
  const texto =
    `Hola${primerNombre ? ` ${primerNombre}` : ''}! 😊 Te recuerdo la vaca "${colecta}": ` +
    `te faltan ${formatMoneda(falta, moneda)}. ` +
    `${enlace ? `Aquí ves cómo va: ${enlace} ` : ''}¡Gracias!`
  return `https://wa.me/${telefonoParaWhatsApp(telefono)}?text=${encodeURIComponent(texto)}`
}

// Mensaje para invitar al grupo a ver el avance (se manda por el grupo de WhatsApp).
export function enlaceCompartirColecta({ colecta, enlace }) {
  return `https://wa.me/?text=${encodeURIComponent(`Así va la vaca "${colecta}": ${enlace}`)}`
}

export const ETIQUETA_ESTADO = { pagado: 'Pagó', parcial: 'Parcial', falta: 'Falta' }

export function porcentaje(recogido, meta) {
  return meta > 0 ? Math.min(100, Math.round((recogido / meta) * 100)) : 0
}
