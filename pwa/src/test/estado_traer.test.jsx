import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BOTON_TAREA, separarEstados, textoDetalleCelda, textoOrigenes } from '../lib/estadoTraer'
import { etiquetaOrigen, textoConfirmado } from '../lib/canales'
import { resumenPrevio, textoPrevio, normalizarPdf } from '../lib/subidaMultiple'
import EtiquetaOrigen from '../components/EtiquetaOrigen'

describe('estado de Traer movimientos', () => {
  it('separa lo que pide acción de lo que está al día', () => {
    const { alDia, porHacer } = separarEstados([
      { id: 1, estado: 'al_dia' }, { id: 2, estado: 'por_revisar' }, { id: 3, estado: 'necesita_clave' },
      { id: 4, estado: 'no_se_pudo_leer' }, { id: 5, estado: 'anterior_al_inicio' }, { id: 6, estado: 'sin_movimientos_reales' },
    ])
    expect(alDia.map((x) => x.id)).toEqual([1, 5, 6])
    expect(porHacer.map((x) => x.id)).toEqual([2, 3, 4])
  })

  it('cada tarea tiene un botón principal con verbo', () => {
    for (const id of ['correos_por_revisar', 'falta_clave', 'extractos_por_conciliar', 'extractos_sin_leer', 'posibles_duplicados']) {
      expect(BOTON_TAREA[id]).toBeTruthy()
    }
  })

  it('el detalle de la celda cuenta la historia completa, no solo los nuevos', () => {
    expect(textoDetalleCelda({ estado: 'conciliado', leidas: 37, ya_estaban: 37, nuevas_agregadas: 0, por_revisar: 0, por_confirmar: 0 }))
      .toBe('37 movimientos leídos del extracto · 37 ya estaban · 0 nuevos')
    expect(textoDetalleCelda({ estado: 'anterior' })).toMatch(/anterior a tu fecha de inicio/)
  })

  it('dice por qué vía llegó', () => {
    expect(textoOrigenes(['correo', 'archivo'])).toBe('correo + archivo')
  })
})

describe('etiquetas de origen', () => {
  it('usa las palabras de la gente', () => {
    expect(etiquetaOrigen('manual')).toBe('a mano')
    expect(etiquetaOrigen('importacion')).toBe('archivo')
  })
  it('dice «confirmado por correo + extracto» sin repetir la vía de origen', () => {
    expect(textoConfirmado('manual', ['manual', 'correo', 'extracto'])).toBe('confirmado por correo + extracto')
    expect(textoConfirmado('correo', ['correo'])).toBe('')
    expect(textoConfirmado('atajo', ['atajo', 'extracto'])).toBe('confirmado por extracto')
  })
  it('se pinta en la fila', () => {
    render(<EtiquetaOrigen origen="manual" canales={['manual', 'correo', 'extracto']} />)
    expect(screen.getByText('a mano')).toBeTruthy()
    expect(screen.getByText('confirmado por correo + extracto')).toBeTruthy()
  })
})

describe('previsualización anti-duplicados', () => {
  it('cuenta lo que coincide, lo nuevo y lo dudoso', () => {
    const r = resumenPrevio([{ estado: 'ya' }, { estado: 'ya' }, { estado: 'nuevo' }, { estado: 'dudoso' }, { estado: 'anterior' }])
    expect(r).toEqual({ coinciden: 2, nuevos: 1, dudosos: 1, anteriores: 1 })
    expect(textoPrevio(r)).toEqual(['2 coinciden con lo que ya tienes (no se duplican)', '1 es nuevo', '1 parece repetido y necesita tu ayuda'])
  })
  it('un aproximado del extracto llega como dudoso con las dos filas', () => {
    const n = normalizarPdf({ review: [{ estado: 'aproximado', fingerprint: 'a', fecha: '2026-10-01', descripcion: 'EXITO', monto: 45900, tipo: 'expense',
      descripcion_registrada: 'Exito', monto_registrado: 45000, fecha_registrada: '2026-10-01', match_id: 'm1' }] })
    expect(n.items[0]).toMatchObject({ estado: 'dudoso', matchId: 'm1', registrado: { descripcion: 'Exito', monto: 45000 } })
  })
})
