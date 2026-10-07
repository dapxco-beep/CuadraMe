// Traductor de mensajes técnicos a lenguaje llano. La mayoría de personas que usan CuadraMe
// no saben qué es un «token», un «endpoint» ni un «error 404»: cualquier texto que llegue de
// afuera (el servidor, Supabase, el navegador) pasa por aquí antes de mostrarse.
import { MSG_ERROR_SERVIDOR, MSG_SESION_VENCIDA, MSG_SIN_CONEXION } from './mensajesBase'

// Por código HTTP, cuando el servidor no dijo nada entendible.
export function mensajePorEstado(status) {
  if (status >= 500) return MSG_ERROR_SERVIDOR
  switch (status) {
    case 400:
    case 422:
      return 'Revisa los datos que escribiste e intenta de nuevo.'
    case 401:
      return MSG_SESION_VENCIDA
    case 403:
      return 'No tienes permiso para hacer esto.'
    case 404:
      return 'No encontramos lo que buscas. Puede que ya no exista.'
    case 409:
      return 'Algo cambió mientras tanto. Actualiza la pantalla e intenta de nuevo.'
    case 413:
      return 'El archivo es demasiado grande. Prueba con uno más liviano.'
    case 429:
      return 'Hiciste muchas solicitudes seguidas. Espera un momento e intenta de nuevo.'
    default:
      return 'Algo no salió bien. Intenta de nuevo.'
  }
}

// [patrón del texto técnico, lo que se le dice a la persona]
const TRADUCCIONES = [
  // Errores internos del navegador al leer una respuesta rota: van primero porque mencionan «token» sin ser de sesión.
  [/unexpected token|syntaxerror|typeerror|\[object|\b(undefined|null|nan)\b|\bjson\b/i, MSG_ERROR_SERVIDOR],
  [/failed to fetch|load failed|networkerror|network request failed|fetch failed/i, MSG_SIN_CONEXION],
  [/invalid login credentials|invalid credentials/i, 'El correo o la contraseña no coinciden. Revísalos e intenta de nuevo.'],
  [/email not confirmed/i, 'Todavía no confirmas tu correo. Abre el mensaje que te enviamos (revisa también spam).'],
  [/user already registered|already been registered/i, 'Ya existe una cuenta con ese correo. Prueba iniciar sesión.'],
  [/password should be at least|password is too short|weak password/i, 'La contraseña es muy corta. Usa al menos 6 caracteres.'],
  [/same password|different from the old/i, 'La contraseña nueva debe ser distinta a la anterior.'],
  [/rate limit|too many requests|over_email_send_rate_limit|for security purposes/i, 'Intentaste muchas veces seguidas. Espera unos minutos e inténtalo de nuevo.'],
  [/unable to validate email|invalid email|invalid format/i, 'Ese correo no parece válido. Revisa que esté bien escrito.'],
  [/jwt|token|unauthorized|not authenticated|could not validate credentials/i, MSG_SESION_VENCIDA],
  [/forbidden/i, 'No tienes permiso para hacer esto.'],
  [/not found/i, 'No encontramos lo que buscas. Puede que ya no exista.'],
  [/method not allowed|bad request|internal server error|bad gateway|service unavailable|gateway timeout|timeout|timed out/i, MSG_ERROR_SERVIDOR],
]

/**
 * Devuelve un texto apto para mostrar. Si `texto` ya está en lenguaje llano se deja igual
 * (solo se cambia «API key» por «clave»). `porDefecto` se usa cuando no hay texto; `status`
 * ayuda a resolver un «Error 404» pelado.
 */
export function mensajeAmable(texto, { porDefecto = MSG_ERROR_SERVIDOR, status } = {}) {
  const t = String(texto ?? '').trim()
  if (!t) return porDefecto
  const codigo = /^error (\d{3})$/i.exec(t)
  if (codigo) return mensajePorEstado(status ?? Number(codigo[1]))
  for (const [patron, respuesta] of TRADUCCIONES) {
    if (patron.test(t)) return respuesta
  }
  return t.replace(/\bAPI key\b/gi, 'clave').replace(/\bapi_key\b/gi, 'clave')
}

/** Para un `catch (err)`: el mensaje de la excepción en lenguaje llano. */
export function mensajeDeError(err, porDefecto) {
  return mensajeAmable(err?.message, { porDefecto, status: err?.status })
}
