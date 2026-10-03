import { formatMoneda } from './format'

// Deja solo los dígitos y agrega el indicativo de Colombia (57) a los celulares
// de 10 dígitos que empiezan por 3. Si ya trae indicativo o es de otro país
// (más de 10 dígitos) se respeta tal cual. Devuelve '' si no hay número usable.
export function telefonoParaWhatsApp(telefono) {
  let d = String(telefono || '').replace(/\D/g, '')
  if (d.startsWith('00')) d = d.slice(2)
  if (d.length === 10 && d.startsWith('3')) return `57${d}`
  return d.length >= 11 ? d : ''
}

// Enlace wa.me con un mensaje amable. Si no hay teléfono válido el enlace abre
// WhatsApp para elegir el contacto (wa.me/?text=...).
export function enlaceCobroWhatsApp({ nombre, telefono, monto, moneda = 'COP', descripcion = '' }) {
  const primerNombre = String(nombre || '').trim().split(/\s+/)[0]
  const motivo = descripcion ? ` por "${descripcion}"` : ''
  const texto =
    `Hola${primerNombre ? ` ${primerNombre}` : ''}! 😊 Te escribo para recordarte, sin afán, ` +
    `lo que quedó pendiente${motivo}: ${formatMoneda(monto, moneda)}. ` +
    `Cuando puedas me lo envías. ¡Mil gracias!`
  const num = telefonoParaWhatsApp(telefono)
  return `https://wa.me/${num}?text=${encodeURIComponent(texto)}`
}
