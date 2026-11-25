import { describe, it, expect, beforeEach } from 'vitest'
import { ACENTOS, THEMES, aplicarAcento } from '../lib/ThemeContext'
import { PERFILES, SIEMPRE_VISIBLES, rutasDelPerfil, esPerfilValido } from '../lib/perfilesUso'
import { gruposSegunModo, ITEMS_MAS } from '../lib/navegacion'

describe('Temas y acentos', () => {
  beforeEach(() => {
    document.documentElement.removeAttribute('style')
  })

  it('cada tema trae su miniatura y los oscuros están marcados', () => {
    for (const t of THEMES) expect(t.vista, t.id).toMatchObject({ fondo: expect.any(String), tarjeta: expect.any(String), texto: expect.any(String), acento: expect.any(String) })
    expect(THEMES.filter((t) => t.oscuro).map((t) => t.id).sort()).toEqual(['dark', 'grafito', 'noche'])
    expect(new Set(THEMES.map((t) => t.id)).size).toBe(THEMES.length)
  })

  it('aplicar un acento cambia las variables y «Del tema» las quita', () => {
    const raiz = document.documentElement
    aplicarAcento('azul', false, raiz)
    expect(raiz.style.getPropertyValue('--c-accent')).toBe('#1d5fa6')
    aplicarAcento('azul', true, raiz)
    expect(raiz.style.getPropertyValue('--c-accent')).toBe('#7db4ff')
    aplicarAcento('', false, raiz)
    expect(raiz.style.getPropertyValue('--c-accent')).toBe('')
    expect(raiz.style.getPropertyValue('--c-hero-a')).toBe('')
  })

  it('cada acento tiene su versión para fondo claro y para fondo oscuro', () => {
    for (const a of ACENTOS) expect(a.claro).not.toBe(a.oscuro)
  })
})

describe('Perfiles de uso', () => {
  it('todos los perfiles tienen nombre y descripción, y «todo» no filtra nada', () => {
    for (const p of PERFILES) expect(p.nombre && p.desc, p.id).toBeTruthy()
    expect(rutasDelPerfil('todo')).toBeNull()
    expect(esPerfilValido('esencial')).toBe(true)
    expect(esPerfilValido('inventado')).toBe(false)
  })

  it('todas las rutas de los perfiles existen en el menú', () => {
    const existentes = new Set(ITEMS_MAS.map((i) => i.to))
    for (const p of PERFILES) for (const r of rutasDelPerfil(p.id) || []) expect(existentes.has(r), `${p.id}: ${r}`).toBe(true)
  })

  it('el perfil Esencial muestra solo lo básico y pliega el resto en «Más funciones»', () => {
    const grupos = gruposSegunModo({ perfil: 'esencial' })
    const visibles = grupos.filter((g) => g.id !== 'mas-funciones').flatMap((g) => g.items.map((i) => i.to))
    const plegadas = grupos.find((g) => g.id === 'mas-funciones')
    expect(plegadas.titulo).toBe('Más funciones')
    for (const r of SIEMPRE_VISIBLES) expect(visibles).toContain(r)
    expect(visibles).toContain('/informes')
    expect(visibles).not.toContain('/metas')
    expect(plegadas.items.map((i) => i.to)).toContain('/metas')
  })

  it('lo que la persona ya usa sube solo, sea cual sea el perfil', () => {
    const grupos = gruposSegunModo({ perfil: 'esencial', enUso: ['/metas'] })
    const visibles = grupos.filter((g) => g.id !== 'mas-funciones').flatMap((g) => g.items.map((i) => i.to))
    expect(visibles).toContain('/metas')
  })

  it('cada perfil agrega lo suyo a lo básico', () => {
    expect(rutasDelPerfil('gastos')).toEqual(expect.arrayContaining(['/categorias', '/asistente']))
    expect(rutasDelPerfil('ahorro')).toEqual(expect.arrayContaining(['/metas']))
    expect(rutasDelPerfil('juntos')).toEqual(expect.arrayContaining(['/otros']))
  })

  it('sin perfil rige la lista de avanzadas de siempre', () => {
    const grupos = gruposSegunModo({})
    expect(grupos.find((g) => g.id === 'mas-funciones').titulo).toBe('Avanzadas')
  })
})
