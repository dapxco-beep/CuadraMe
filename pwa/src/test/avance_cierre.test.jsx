import { describe, it, expect } from 'vitest'
import { avanceCierre } from '../lib/cierreAsistente'

const pasos = (...estados) => estados.map((estado, i) => ({ id: `p${i}`, estado }))

describe('Avance del cierre', () => {
  it('cuenta las revisiones listas y pone a Cuadri más contento entre más avanzas', () => {
    expect(avanceCierre(pasos('atencion', 'atencion', 'atencion', 'neutro'))).toMatchObject({ listos: 0, pct: 0, estado: 'cansado' })
    expect(avanceCierre(pasos('ok', 'atencion', 'atencion', 'neutro'))).toMatchObject({ listos: 1, pct: 33, estado: 'regular', texto: '1 de 3 revisiones listas' })
    expect(avanceCierre(pasos('ok', 'ok', 'atencion', 'neutro'))).toMatchObject({ listos: 2, estado: 'bien' })
    expect(avanceCierre(pasos('ok', 'ok', 'ok', 'neutro'))).toMatchObject({ listos: 3, pct: 100, estado: 'radiante', texto: '¡Todo listo para cerrar!' })
  })

  it('mientras carga dice que está revisando', () => {
    expect(avanceCierre(pasos('cargando', 'ok', 'cargando', 'neutro')).texto).toBe('Revisando tu mes…')
  })

  it('el cuarto paso (el resumen) no cuenta para el avance', () => {
    expect(avanceCierre(pasos('ok', 'ok', 'ok', 'atencion')).listos).toBe(3)
  })
})
