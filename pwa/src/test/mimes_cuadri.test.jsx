import { describe, it, expect } from 'vitest'
import { reaccionCuadri } from '../lib/wrappedImagen'

describe('Cuadri reacciona en «Mi mes»', () => {
  it('se pone radiante si ahorraste mucho y mal si gastaste más de lo que entró', () => {
    expect(reaccionCuadri('ahorro', { ahorro: 500, tasa_ahorro: 35 })).toEqual({ estado: 'radiante' })
    expect(reaccionCuadri('ahorro', { ahorro: 100, tasa_ahorro: 8 })).toEqual({ estado: 'bien' })
    expect(reaccionCuadri('ahorro', { ahorro: -50, tasa_ahorro: -5 })).toEqual({ estado: 'mal' })
  })

  it('se preocupa si el gasto subió y se alegra si bajó', () => {
    expect(reaccionCuadri('gasto', { variacion_gasto_pct: 40 })).toEqual({ pose: 'preocupado' })
    expect(reaccionCuadri('gasto', { variacion_gasto_pct: -10 })).toEqual({ pose: 'feliz' })
    expect(reaccionCuadri('comparacion', { variacion_gasto_pct: -20 })).toEqual({ estado: 'bien' })
    expect(reaccionCuadri('comparacion', { variacion_gasto_pct: 30 })).toEqual({ estado: 'cansado' })
  })

  it('celebra una buena racha y siempre devuelve algo', () => {
    expect(reaccionCuadri('racha', { mejor_racha: 9 })).toEqual({ pose: 'celebrando' })
    expect(reaccionCuadri('categoria', {})).toEqual({ pose: 'senalando' })
    expect(reaccionCuadri('desconocida', {})).toEqual({ pose: 'feliz' })
  })
})
