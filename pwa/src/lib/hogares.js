import { formatMoneda } from './format'

// Enlace de invitación (HashRouter, por eso lleva #). Se manda por WhatsApp o se copia.
export function enlaceInvitacionHogar(token, origen = typeof window !== 'undefined' ? window.location.origin : '') {
  return `${origen}/#/unirse/${token}`
}

// Texto que acompaña al enlace: dice qué es, que es gratis y que quien no tiene cuenta la crea en un minuto.
export function textoInvitacion(hogar) {
  return `Te invito a "${hogar}" en CuadraMe para llevar los gastos juntos. Es gratis: si no tienes cuenta, la creas en un minuto.`
}

export function enlaceCompartirInvitacion({ hogar, enlace }) {
  return `https://wa.me/?text=${encodeURIComponent(`${textoInvitacion(hogar)} ${enlace}`)}`
}

// Frase de una deuda del libro: «Beto le debe $50.000 a Ana» (o «Tú le debes…» / «Ana te debe…»).
export function fraseDeuda(p, miMiembroId, moneda) {
  const monto = formatMoneda(p.monto, moneda)
  if (p.de === miMiembroId) return `Le debes ${monto} a ${p.a_nombre}`
  if (p.a === miMiembroId) return `${p.de_nombre} te debe ${monto}`
  return `${p.de_nombre} le debe ${monto} a ${p.a_nombre}`
}

// Recordatorio por WhatsApp a quien debe (abre el mensaje armado; no se envía solo).
export function enlaceCobroHogar({ hogar, deudor, monto, moneda = 'COP' }) {
  const nombre = String(deudor || '').trim().split(/\s+/)[0]
  const texto = `Hola ${nombre}! 😊 En "${hogar}" quedó pendiente ${formatMoneda(monto, moneda)}. Cuando puedas, me avisas. ¡Gracias!`
  return `https://wa.me/?text=${encodeURIComponent(texto)}`
}

const PENDIENTE = 'cuadrame:unirse'
// Quien llega por una invitación sin sesión (o vuelve de Google, que pierde el #) no pierde la invitación.
export function guardarInvitacionPendiente(token) {
  try { localStorage.setItem(PENDIENTE, token) } catch { /* sin almacenamiento: se sigue sin guardar */ }
}
export function tomarInvitacionPendiente() {
  try {
    const t = localStorage.getItem(PENDIENTE)
    if (t) localStorage.removeItem(PENDIENTE)
    return t || ''
  } catch {
    return ''
  }
}
