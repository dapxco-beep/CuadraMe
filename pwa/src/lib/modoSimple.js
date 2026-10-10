import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { useAuth } from './AuthContext'

// ═══ Modo simple ═══════════════════════════════════════════════════════════
// Por defecto el menú muestra solo lo esencial (Inicio, Movimientos, Presupuesto, Traer movimientos,
// Perfil y Ayuda). El interruptor «Mostrar todas las funciones» (Perfil) lo cambia.
//
// Dónde se guarda: no existe una tabla de ajustes por usuario en el backend (sería una migración),
// así que la preferencia vive en este dispositivo, separada por usuario. Si más adelante hay
// `ajustes_usuario`, solo hay que cambiar leer/guardar de este archivo.

const CLAVE_MODO = 'cuadrame:modo-completo'
const CLAVE_EN_USO = 'cuadrame:funciones-en-uso'
const EVENTO = 'cuadrame:modo-menu'

export function leerModoCompleto(uid = 'anon') {
  try {
    return localStorage.getItem(`${CLAVE_MODO}:${uid}`) === '1'
  } catch {
    return false
  }
}

export function guardarModoCompleto(uid = 'anon', completo) {
  try {
    if (completo) localStorage.setItem(`${CLAVE_MODO}:${uid}`, '1')
    else localStorage.removeItem(`${CLAVE_MODO}:${uid}`)
  } catch {
    /* sin almacenamiento: vale solo para esta sesión */
  }
  window.dispatchEvent(new Event(EVENTO))
}

export function leerFuncionesEnUso(uid = 'anon') {
  try {
    const v = JSON.parse(localStorage.getItem(`${CLAVE_EN_USO}:${uid}`) || '[]')
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

function guardarFuncionesEnUso(uid, rutas) {
  try {
    localStorage.setItem(`${CLAVE_EN_USO}:${uid}`, JSON.stringify(rutas))
  } catch {
    /* ignorar */
  }
  window.dispatchEvent(new Event(EVENTO))
}

/** Una función pasa a «Lo que ya usas» en el momento en que se estrena (p. ej. la primera meta creada desde Inicio). */
export function marcarFuncionEnUso(uid = 'anon', ruta) {
  const previas = leerFuncionesEnUso(uid)
  if (!ruta || previas.includes(ruta)) return
  guardarFuncionesEnUso(uid, [...previas, ruta])
}

/** () => (ruta) => void — para avisar al menú que la persona estrenó una función. */
export function useMarcarFuncion() {
  const { usuario } = useAuth() || {}
  const uid = usuario?.id || 'anon'
  return useCallback((ruta) => marcarFuncionEnUso(uid, ruta), [uid])
}

const hayAlgo = (v, campo) => (Array.isArray(v) ? v.length > 0 : Array.isArray(v?.[campo]) && v[campo].length > 0)
const seguro = (f) => Promise.resolve().then(f).catch(() => null)

/** Rutas de las funciones que la persona YA usa (tiene datos en ellas): aparecen solas en el menú. */
export async function detectarFuncionesEnUso(cliente = api) {
  const [metas, deudas, recurrentes, patrimonio] = await Promise.all([
    seguro(() => cliente.metas?.()),
    seguro(() => cliente.deudas?.()),
    seguro(() => cliente.recurrentes?.()),
    seguro(() => cliente.patrimonio?.()),
  ])
  const rutas = []
  if (hayAlgo(metas, 'metas')) rutas.push('/metas')
  if (hayAlgo(deudas, 'deudas')) rutas.push('/deudas')
  if (hayAlgo(recurrentes, 'recurrentes')) rutas.push('/recurrentes')
  if (hayAlgo(patrimonio, 'activos')) rutas.push('/patrimonio')
  return rutas
}

const yaDetectado = new Set()

/** { completo, enUso, setCompleto } — para los menús y para el interruptor de Perfil. */
export function useModoMenu() {
  const { usuario } = useAuth() || {}
  const uid = usuario?.id || 'anon'
  const [, repintar] = useState(0)
  const completo = leerModoCompleto(uid)
  const enUso = leerFuncionesEnUso(uid)

  useEffect(() => {
    const alCambiar = () => repintar((n) => n + 1)
    window.addEventListener(EVENTO, alCambiar)
    window.addEventListener('storage', alCambiar)
    return () => {
      window.removeEventListener(EVENTO, alCambiar)
      window.removeEventListener('storage', alCambiar)
    }
  }, [])

  // Una sola revisión por sesión y usuario; en modo completo no hace falta (todo está a la vista).
  useEffect(() => {
    if (completo || yaDetectado.has(uid)) return
    yaDetectado.add(uid)
    detectarFuncionesEnUso().then((rutas) => {
      const previas = leerFuncionesEnUso(uid)
      // Una función que ya apareció no desaparece (si borra todas sus metas, el menú no baila).
      const union = [...new Set([...previas, ...rutas])]
      if (union.length !== previas.length) guardarFuncionesEnUso(uid, union)
    })
  }, [completo, uid])

  const setCompleto = useCallback((valor) => guardarModoCompleto(uid, !!valor), [uid])
  return { completo, enUso, setCompleto }
}
