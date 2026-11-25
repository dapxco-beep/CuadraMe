// Perfiles de uso: «cómo quieres usar CuadraMe». Cada perfil decide qué funciones se ven en el menú; el resto no se borra,
// queda plegado en «Más funciones» y sigue apareciendo en el buscador. Lo que la persona ya usa (tiene metas, deudas…) sube solo.
// Se guarda solo en este dispositivo (ver modoSimple.js).

// Lo que siempre se ve, sea cual sea el perfil.
export const SIEMPRE_VISIBLES = ['/perfil', '/ayuda', '/legal/privacidad']

const BASE = ['/cuentas', '/sincronizacion', '/informes', '/ahorcado']

export const PERFILES = [
  {
    id: 'esencial',
    nombre: 'Esencial',
    desc: 'Lo básico: anotar, ver cuánto tienes y cómo vas. Lo demás, cuando lo pidas.',
    rutas: BASE,
  },
  {
    id: 'gastos',
    nombre: 'Controlo mis gastos',
    desc: 'Para saber en qué se va la plata: avisos del banco, categorías y el asistente.',
    rutas: [...BASE, '/categorias', '/asistente'],
  },
  {
    id: 'ahorro',
    nombre: 'Quiero ahorrar',
    desc: 'Metas e inversiones para llegar a lo que quieres.',
    rutas: [...BASE, '/metas', '/asistente'],
  },
  {
    id: 'juntos',
    nombre: 'En pareja o familia',
    desc: 'Gastos compartidos, vacas y parches, además de lo básico.',
    rutas: [...BASE, '/otros', '/categorias'],
  },
  {
    id: 'todo',
    nombre: 'Todo',
    desc: 'Todas las funciones a la vista, ordenadas por tema.',
    rutas: null,
  },
]

export const PERFIL_POR_DEFECTO = 'esencial'

export const esPerfilValido = (id) => PERFILES.some((p) => p.id === id)

/** Rutas visibles para un perfil (null = todas). */
export function rutasDelPerfil(id) {
  const p = PERFILES.find((x) => x.id === id)
  if (!p || p.rutas === null) return null
  return [...new Set([...SIEMPRE_VISIBLES, ...p.rutas])]
}
