import { describe, expect, it, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ExtractosAMedias from '../components/ExtractosAMedias'
import { borrarBorrador, extractosAMedias, guardarBorrador, leerBorrador, resumenLote, textoFaltan, tituloAMedias } from '../lib/retomar'

const fila = (o) => ({ historial_id: 'h1', cuenta_id: 'c1', cuenta: 'Nu Colombia', mes_etiqueta: 'Octubre 2025', estado_vista: 'por_revisar', por_revisar: 52, ...o })

describe('extractos a medio conciliar', () => {
  it('toma solo los por revisar con revisión guardada y movimientos por importar', () => {
    const estado = { todos_extractos: { items: [
      fila({}),
      fila({ historial_id: 'h2', por_revisar: 0 }),
      fila({ historial_id: null }),
      fila({ historial_id: 'h4', estado_vista: 'revisado' }),
      fila({ historial_id: 'h5', por_revisar: 1, cuenta: 'Nu Crédito', mes_etiqueta: 'Junio 2026' }),
    ] } }
    const l = extractosAMedias(estado)
    expect(l.map((x) => x.historialId)).toEqual(['h1', 'h5'])
    expect(l[0]).toMatchObject({ cuenta: 'Nu Colombia', mes: 'Octubre 2025', faltan: 52 })
  })

  it('textos', () => {
    expect(tituloAMedias(1)).toBe('Tienes 1 extracto a medio conciliar')
    expect(tituloAMedias(3)).toBe('Tienes 3 extractos a medio conciliar')
    expect(textoFaltan(1)).toBe('faltan importar 1 movimiento')
  })

  it('la tarjeta lista cada extracto y «Seguir» abre exactamente ese', () => {
    const abiertos = []
    render(<ExtractosAMedias lista={extractosAMedias({ todos_extractos: { items: [fila({}), fila({ historial_id: 'h5', por_revisar: 51, mes_etiqueta: 'Abril 2026' })] } })} onSeguir={(x) => abiertos.push(x.historialId)} />)
    expect(screen.getByText('Tienes 2 extractos a medio conciliar')).toBeTruthy()
    expect(screen.getByText('faltan importar 51 movimientos')).toBeTruthy()
    fireEvent.click(screen.getByLabelText('Seguir con Nu Colombia Abril 2026'))
    expect(abiertos).toEqual(['h5'])
  })

  it('sin extractos a medias no pinta nada', () => {
    const { container } = render(<ExtractosAMedias lista={[]} onSeguir={() => {}} />)
    expect(container.innerHTML).toBe('')
  })
})

describe('resumen del lote', () => {
  it('cuenta conciliados, por importar y sin clave', () => {
    const nuevo = { items: [{ estado: 'nuevo' }] }
    const ya = { items: [{ estado: 'ya' }] }
    const lote = [{ estado: 'listo', ...ya }, { estado: 'listo', ...ya }, { estado: 'listo', ...ya }, { estado: 'listo', ...nuevo }, { estado: 'listo', ...nuevo }, { estado: 'falta_clave' }]
    expect(resumenLote(lote)).toBe('Subiste 6: 3 conciliados, 2 por importar, 1 sin clave')
  })
  it('con un solo archivo no hace falta resumen', () => {
    expect(resumenLote([{ estado: 'listo', items: [] }])).toBe('')
  })
})

describe('borrador de la revisión', () => {
  beforeEach(() => sessionStorage.clear())
  it('guarda y recupera marcas, categorías y reglas; se borra', () => {
    guardarBorrador('h1', { seleccion: new Set(['a', 'b']), categorias: { a: 'Comida' }, aprender: { a: { recordar: true } } })
    const b = leerBorrador('h1')
    expect([...b.seleccion]).toEqual(['a', 'b'])
    expect(b.categorias).toEqual({ a: 'Comida' })
    expect(b.aprender.a.recordar).toBe(true)
    borrarBorrador('h1')
    expect(leerBorrador('h1')).toBeNull()
  })
})
