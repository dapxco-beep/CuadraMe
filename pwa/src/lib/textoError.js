// Texto para mostrar cuando algo falla. Antes casi todo error decía «Revisa tu conexión», aunque el
// problema fuera otro (un dato inválido, el servidor...). Aquí se distingue:
//  - sin internet (api.js marca `err.sinConexion`, o el navegador dice «Failed to fetch») -> aviso de conexión
//  - el servidor explicó qué pasó (`err.message`) -> se muestra ese mensaje
//  - cualquier otro caso -> «No pudimos {accion}. Intenta de nuevo en un momento.»
export const MSG_SIN_INTERNET = 'Parece que no tienes internet. Revisa tu conexión e intenta de nuevo.'

const MENSAJES_DE_RED = /^(failed to fetch|load failed|networkerror|network request failed)/i

export function textoError(e, accion = 'hacerlo') {
  const msg = typeof e?.message === 'string' ? e.message.trim() : ''
  if (e?.sinConexion || MENSAJES_DE_RED.test(msg)) return MSG_SIN_INTERNET
  if (msg) return msg
  return `No pudimos ${accion}. Intenta de nuevo en un momento.`
}
