// País de la persona: estado en memoria + hook. La fuente de la configuración es lib/paises.js.
//
// - El país viene del backend (/perfil/pais). Perfiles anteriores sin país = Colombia.
// - La SUGERENCIA sale del idioma del navegador y la zona horaria. Nunca de la IP ni de
//   geolocalización, y nunca se aplica sola: la persona confirma.
// - `formatoActual()` lo usa lib/format.js para dar formato de dinero y fecha del país.
import { useEffect, useSyncExternalStore } from 'react'
import { api } from './api'
import { configPais, paisValido, sugerirPais, tieneFuncion, PAIS_POR_DEFECTO_LEGADO } from './paises'

let estado = { pais: PAIS_POR_DEFECTO_LEGADO, confirmado: false, monedaBase: null, cargado: false }
const oyentes = new Set()

function emitir(nuevo) {
  estado = { ...estado, ...nuevo }
  oyentes.forEach((f) => f())
}

export function paisActual() {
  return estado.pais
}

// { locale, moneda, decimales } del país activo, para formatear dinero y fechas.
export function formatoActual() {
  const c = configPais(estado.pais) || configPais(PAIS_POR_DEFECTO_LEGADO)
  return { locale: c.locale, moneda: estado.monedaBase || c.moneda, decimales: c.decimales }
}

export function fijarPais(codigo, { confirmado = true, monedaBase = null } = {}) {
  if (!paisValido(codigo)) return
  emitir({ pais: codigo, confirmado, monedaBase, cargado: true })
}

export function sugerenciaDelNavegador() {
  let zona = null
  try {
    zona = Intl.DateTimeFormat().resolvedOptions().timeZone
  } catch {
    zona = null
  }
  const idioma = typeof navigator !== 'undefined' ? navigator.language : null
  return sugerirPais(idioma, zona)
}

let cargando = null
export function cargarPais(forzar = false) {
  if (cargando && !forzar) return cargando
  cargando = Promise.resolve()
    .then(() => api.paisPerfil())
    .then((r) => fijarPais(r.pais, { confirmado: !!r.confirmado, monedaBase: r.moneda_base }))
    .catch(() => emitir({ cargado: true })) // sin red: se queda con Colombia (lo de siempre)
  return cargando
}

export function usePais() {
  const e = useSyncExternalStore(
    (f) => {
      oyentes.add(f)
      return () => oyentes.delete(f)
    },
    () => estado
  )
  useEffect(() => {
    cargarPais()
  }, [])
  const config = configPais(e.pais) || configPais(PAIS_POR_DEFECTO_LEGADO)
  return {
    pais: e.pais,
    config,
    moneda: e.monedaBase || config.moneda,
    confirmado: e.confirmado,
    cargado: e.cargado,
    tiene: (funcion) => tieneFuncion(e.pais, funcion),
    sugerido: sugerenciaDelNavegador(),
  }
}

export async function guardarPais(codigo) {
  const r = await api.guardarPaisPerfil({ pais: codigo })
  fijarPais(r.pais, { confirmado: true, monedaBase: r.moneda_base })
  return r
}

// Solo para pruebas.
export function _reiniciarPais() {
  cargando = null
  estado = { pais: PAIS_POR_DEFECTO_LEGADO, confirmado: false, monedaBase: null, cargado: false }
}

