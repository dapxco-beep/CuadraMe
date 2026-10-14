// Cómo le decimos a la persona. Sin React salvo el hook `useNombre`.
//
// Google entrega el nombre completo («DANIEL ALFONSO PARRADO CARDENAS»); de ahí sale un nombre de
// pila sugerido que la persona confirma o corrige. Las reglas espejan backend/app/nombre.py
// (el servidor es quien manda: aquí solo se prellena y se avisa pronto de un error).
// Regla de oro: si no hay nombre, TODO debe leerse bien sin él (nunca «Hola, !»).

import { useEffect, useState } from 'react'
import { api } from './api'
import { useAuth } from './AuthContext'

export const MAX_NOMBRE = 40
const SEPARADORES = "-'’"

const normalizar = (t) => String(t ?? '').normalize('NFC').replace(/\s+/g, ' ').trim()
const esLetra = (c) => /[\p{L}\p{M}]/u.test(c)

function capitalizarToken(token) {
  return token
    .split(/([-'’])/)
    .map((p) => (p && !SEPARADORES.includes(p) ? p.charAt(0).toUpperCase() + p.slice(1).toLowerCase() : p))
    .join('')
}

function embellecer(texto) {
  const todoMayus = texto === texto.toUpperCase() && texto !== texto.toLowerCase()
  const todoMinus = texto === texto.toLowerCase() && texto !== texto.toUpperCase()
  return todoMayus || todoMinus ? texto.split(' ').map(capitalizarToken).join(' ') : texto
}

// Mensaje amable si no sirve, o '' si está bien.
export function errorNombre(texto) {
  const t = normalizar(texto)
  if (!t) return 'Escribe cómo quieres que te llamemos.'
  if ([...t].length > MAX_NOMBRE) return `Que sea más corto, por favor (máximo ${MAX_NOMBRE} letras).`
  if (![...t].every((c) => esLetra(c) || SEPARADORES.includes(c) || c === ' ')) {
    return 'Usa solo letras, espacios, guion o apóstrofo (sin números, emojis ni símbolos).'
  }
  if (!/\p{L}/u.test(t)) return 'Escribe al menos una letra.'
  return ''
}

export function limpiarNombre(texto) {
  return errorNombre(texto) ? '' : embellecer(normalizar(texto))
}

// Nombre de pila sugerido: given_name de Google si es compuesto (hasta 2 palabras), si no la primera palabra.
export function nombreDePila(completo, pilaGoogle) {
  for (const [fuente, max] of [[pilaGoogle, 2], [completo, 1]]) {
    const t = normalizar(fuente)
    if (!t || t.includes('@')) continue
    const tokens = t
      .split(' ')
      .map((x) => [...x].filter((c) => esLetra(c) || SEPARADORES.includes(c)).join('').replace(/^[-'’]+|[-'’]+$/g, ''))
      .filter(Boolean)
    if (!tokens.length) continue
    const candidato = limpiarNombre(embellecer(tokens.slice(0, max).join(' ')))
    if (candidato) return candidato
  }
  return ''
}

// ── Estado compartido (una sola petición por sesión; se reinicia al cambiar de persona) ──
const EVENTO = 'cuadrame:nombre-cambio'
let almacen = { uid: null, datos: null, promesa: null }

function avisar() {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(EVENTO))
}

export function reiniciarNombre() {
  almacen = { uid: null, datos: null, promesa: null }
}

function cargar(uid) {
  if (almacen.uid !== uid) almacen = { uid, datos: null, promesa: null }
  if (!almacen.promesa) {
    const mio = almacen
    mio.promesa = Promise.resolve()
      .then(() => api.nombrePerfil?.())
      .then((r) => {
        if (r && typeof r === 'object' && !Array.isArray(r) && 'confirmado' in r) mio.datos = r
        else mio.datos = { nombre: null, sugerido: null, confirmado: true } // respuesta rara: no molestar
      })
      .catch(() => {
        mio.datos = { nombre: null, sugerido: null, confirmado: true, sinDatos: true } // sin red: no molestar
      })
      .finally(avisar)
  }
  return almacen.promesa
}

async function guardar(cuerpo) {
  const r = await api.guardarNombrePerfil(cuerpo)
  almacen.datos = r
  avisar()
  return r
}

// { nombre, sugerido, confirmado, cargando, guardar(nombre), omitir() }
//  - `nombre` = el que eligió la persona ('' si no hay)
export function useNombre() {
  const { usuario } = useAuth() || {}
  const uid = usuario?.id || null
  const [, forzar] = useState(0)
  useEffect(() => {
    const f = () => forzar((n) => n + 1)
    window.addEventListener(EVENTO, f)
    if (uid) cargar(uid)
    return () => window.removeEventListener(EVENTO, f)
  }, [uid])
  const datos = uid && almacen.uid === uid ? almacen.datos : null
  return {
    cargando: !!uid && !datos,
    nombre: datos?.nombre || '',
    sugerido: datos?.sugerido || '',
    confirmado: !!datos?.confirmado,
    guardar: (nombre) => guardar({ nombre }),
    omitir: () => guardar({ omitir: true }),
  }
}

// Nombre para saludar: el elegido; si aún no hay, el de pila que viene de la cuenta; si no, ''.
export function useNombreParaSaludar() {
  const { usuario } = useAuth() || {}
  const { nombre } = useNombre()
  return nombre || nombreDePila(usuario?.nombre, usuario?.nombrePila)
}
