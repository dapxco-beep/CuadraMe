import { describe, expect, it } from 'vitest'
import { construirPasos, estadoGeneral, obligatorios, progresoPasos, textoBusqueda } from '../lib/siguientePaso'

const t = (id, cantidad = 1, extra = {}) => ({ id, cantidad, titulo: id, detalle: '', ...extra })

describe('construirPasos: prioridad', () => {
  it('ordena clave → cuenta → a medias → conciliar → correos → cuadre → categorizar (opcional)', () => {
    const tareas = [
      t('cuadre_no_cuadra'), t('movimientos_por_categorizar', 4, { opcional: true }), t('correos_por_revisar', 2),
      t('extractos_por_conciliar'), t('sin_cuenta'), t('falta_clave'),
    ]
    const aMedias = [{ historialId: 'h1', cuenta: 'Nu', mes: 'agosto 2026', faltan: 3 }]
    const ids = construirPasos({ tareas, aMedias }).map((p) => p.id)
    expect(ids).toEqual(['falta_clave', 'sin_cuenta', 'a_medias', 'extractos_por_conciliar', 'correos_por_revisar', 'cuadre_no_cuadra', 'movimientos_por_categorizar'])
  })

  it('lo opcional nunca va antes de lo obligatorio y no cuenta', () => {
    const pasos = construirPasos({ tareas: [t('movimientos_por_categorizar', 3, { opcional: true }), t('correos_por_revisar')] })
    expect(pasos.map((p) => p.id)).toEqual(['correos_por_revisar', 'movimientos_por_categorizar'])
    expect(obligatorios(pasos)).toHaveLength(1)
    // Solo queda algo opcional: no es «Todo al día» sino «Casi todo al día».
    expect(estadoGeneral(construirPasos({ tareas: [t('movimientos_por_categorizar', 3, { opcional: true })] })).casi).toBe(true)
  })

  it('conectar solo aparece en el primer uso', () => {
    expect(construirPasos({ conectado: false, primerUso: true })[0].id).toBe('conectar')
    expect(construirPasos({ conectado: false, primerUso: false })).toEqual([])
  })

  it('el punto de partida pendiente va después de conectar y antes de todo lo demás', () => {
    const ids = construirPasos({ conectado: false, primerUso: true, puntoPendiente: true, tareas: [t('falta_clave')] }).map((p) => p.id)
    expect(ids).toEqual(['conectar', 'punto_partida', 'falta_clave'])
  })

  it('fuera del primer uso la fecha de inicio es opcional y va al final', () => {
    const pasos = construirPasos({ conectado: true, puntoPendiente: true, tareas: [t('falta_clave')] })
    expect(pasos.map((p) => p.id)).toEqual(['falta_clave', 'punto_partida'])
    expect(obligatorios(pasos)).toHaveLength(1)
  })

  it('textos claros y sin jerga', () => {
    const [p] = construirPasos({ tareas: [t('falta_clave')], claveConfigurada: false })
    expect(p.titulo).toBe('Falta la clave de tu PDF')
    expect(p.boton).toBe('Ponerla ahora')
    const [q] = construirPasos({ tareas: [t('falta_clave')], claveConfigurada: true })
    expect(q.titulo).toMatch(/no abrió/)
    const [m] = construirPasos({ aMedias: [{ historialId: 'h', cuenta: 'Nu', mes: 'Agosto 2026', faltan: 1 }] })
    expect(m.titulo).toBe('Sigue con tu extracto de agosto')
    expect(m.detalle).toBe('Nu: faltan importar 1 movimiento.')
    const [c] = construirPasos({ tareas: [t('correos_por_revisar', 2)] })
    expect(c.titulo).toBe('Revisa 2 movimientos')
  })

  it('una tarea desconocida del servidor no se pierde', () => {
    const [p] = construirPasos({ tareas: [{ id: 'rara', cantidad: 1, titulo: 'Algo nuevo', detalle: 'ojo', ruta: '/x' }] })
    expect(p.titulo).toBe('Algo nuevo')
  })
})

describe('estado y progreso', () => {
  it('estado general', () => {
    expect(estadoGeneral([])).toEqual({ alDia: true, titulo: 'Todo al día' })
    expect(estadoGeneral(construirPasos({ tareas: [t('falta_clave'), t('correos_por_revisar')] })).titulo).toBe('Tienes 2 cosas por hacer')
    expect(estadoGeneral(construirPasos({ tareas: [t('falta_clave')] })).titulo).toBe('Tienes 1 cosa por hacer')
  })
  it('el contador avanza al resolver pasos', () => {
    expect(progresoPasos(3, 0)).toEqual({ n: 1, de: 3, pct: 0 })
    expect(progresoPasos(2, 3)).toEqual({ n: 2, de: 3, pct: 33 })
    expect(progresoPasos(1, 3).n).toBe(3)
    expect(progresoPasos(0, 3)).toBeNull()
  })
  it('texto de búsqueda en línea', () => {
    expect(textoBusqueda({ fase: 'extractos', leidos: 3, total: 6 })).toBe('Leyendo tus extractos… 3 de 6')
    expect(textoBusqueda({})).toBe('Leyendo tu correo…')
  })
})

describe('«Todo al día» es honesto', () => {
  it('con algo opcional pendiente dice «Casi todo al día» y lo nombra', () => {
    const e = estadoGeneral(construirPasos({ tareas: [t('correos_descartados', 16, { opcional: true })] }))
    expect(e).toMatchObject({ alDia: false, casi: true, titulo: 'Casi todo al día', pendiente: 'mirar 16 correos descartados' })
    const dos = estadoGeneral(construirPasos({ tareas: [t('correos_descartados', 1, { opcional: true }), t('movimientos_por_categorizar', 4, { opcional: true })] }))
    expect(dos.pendiente).toBe('ponerle categoría a 4 comercios y mirar 1 correo descartado')
  })

  it('cada cosa de la lista impide el «Todo al día»', () => {
    const obligatorias = ['falta_clave', 'extractos_por_conciliar', 'extractos_sin_leer', 'correos_por_revisar', 'extracto_cuenta_dudosa', 'posibles_duplicados', 'cuadre_no_cuadra']
    for (const id of obligatorias) {
      const e = estadoGeneral(construirPasos({ tareas: [t(id)] }))
      expect(e.alDia, id).toBe(false)
      expect(e.titulo, id).toBe('Tienes 1 cosa por hacer')
    }
    expect(estadoGeneral(construirPasos({ aMedias: [{ historialId: 'h', cuenta: 'Nu', mes: 'Octubre 2026', faltan: 1 }] })).alDia).toBe(false)
    expect(estadoGeneral(construirPasos({ tareas: [] }))).toEqual({ alDia: true, titulo: 'Todo al día' })
  })

  it('un extracto en otra cuenta va antes de seguir con él', () => {
    const aMedias = [{ historialId: 'h', cuenta: 'Nu', mes: 'Octubre 2026', faltan: 1 }]
    const ids = construirPasos({ tareas: [t('extractos_por_conciliar'), t('extracto_cuenta_dudosa', 2)], aMedias }).map((p) => p.id)
    expect(ids).toEqual(['extracto_cuenta_dudosa', 'a_medias', 'extractos_por_conciliar'])
    const [p] = construirPasos({ tareas: [t('extracto_cuenta_dudosa', 4)] })
    expect(p.titulo).toBe('4 extractos están en otra cuenta')
  })

  it('«no hay nada nuevo en tu correo» habla solo del correo, nunca de todo', async () => {
    const { resumenSync, resumenActualizacion } = await import('../lib/sincronizarGmail')
    expect(resumenSync({ nuevos: 0, extractos_nuevos: 0 })).toBe('No hay nada nuevo en tu correo.')
    expect(resumenActualizacion({ nuevos: 0 })).toBe('No hay nada nuevo en tu correo.')
    expect(resumenSync({ nuevos: 0 })).not.toMatch(/Todo al día/)
  })
})
