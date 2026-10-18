// «Releer este extracto»: botón con explicación, progreso y resultado, en la tarjeta «a medio conciliar»
// y en la lista de extractos.
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import BotonReleer from '../components/BotonReleer'
import ExtractosAMedias from '../components/ExtractosAMedias'
import TodosLosExtractos from '../components/TodosLosExtractos'

const medias = [{ historialId: 'h1', cuentaId: 'c1', cuenta: 'Tarjeta Nu', mes: 'Octubre 2026', faltan: 2, titulo: 'Tarjeta Nu · corte 15 oct 2026' }]

describe('BotonReleer', () => {
  it('explica, avisa el progreso y dice el resultado', () => {
    const onReleer = vi.fn()
    const { rerender } = render(<BotonReleer onReleer={onReleer} nombre="Tarjeta Nu" />)
    expect(screen.getByText('Lo vuelvo a leer con las mejoras. No pierdes lo que ya importaste.')).toBeTruthy()
    fireEvent.click(screen.getByLabelText('Releer este extracto: Tarjeta Nu'))
    expect(onReleer).toHaveBeenCalledTimes(1)
    rerender(<BotonReleer onReleer={onReleer} ocupado nombre="Tarjeta Nu" />)
    expect(screen.getByText('Leyendo...')).toBeTruthy()
    expect(screen.getByLabelText('Releer este extracto: Tarjeta Nu').disabled).toBe(true)
    rerender(<BotonReleer onReleer={onReleer} resultado={{ ok: true, texto: 'Cambié 1 línea, agregué 0, conservé 2' }} />)
    expect(screen.getByRole('status').textContent).toBe('Cambié 1 línea, agregué 0, conservé 2')
  })
})

describe('Releer en las pantallas', () => {
  it('la tarjeta «a medio conciliar» ofrece releer ese extracto', () => {
    const onReleer = vi.fn()
    render(<ExtractosAMedias lista={medias} onSeguir={() => {}} onReleer={onReleer} releyendo={new Set()} resultadosReleer={{ h1: { ok: true, texto: 'Cambié 1 línea, agregué 0, conservé 2' } }} />)
    fireEvent.click(screen.getByLabelText('Releer este extracto: Tarjeta Nu · corte 15 oct 2026'))
    expect(onReleer).toHaveBeenCalledWith(expect.objectContaining({ historialId: 'h1' }))
    expect(screen.getByText('Cambié 1 línea, agregué 0, conservé 2')).toBeTruthy()
  })

  it('«Ver todo → Extractos» muestra el botón solo si la fila trae la acción', () => {
    const item = (id, acciones) => ({
      id, historial_id: `h-${id}`, extracto_id: `e-${id}`, mes: '2026-10', mes_etiqueta: 'Octubre 2026', titulo: `Tarjeta Nu ${id}`,
      cuenta_id: 'tj', cuenta: 'Tarjeta Nu', banco: 'Nu', tipo: 'tarjeta', estado_vista: 'por_revisar', estado_etiqueta: 'Por revisar',
      resultado: 'Faltan 2.', acciones, copias: 1, por_revisar: 2,
    })
    const onAccion = vi.fn()
    render(<TodosLosExtractos datos={{ items: [item('a', ['revisar', 'releer']), item('b', ['revisar'])], contadores: {}, sin_adjunto: [] }}
      filtro={{ estados: [], cuenta: '', mes: '', texto: '' }} onFiltro={() => {}} onAccion={onAccion} onFijarMes={() => {}} ocupados={new Set()} releyendo={new Set()} resultadosReleer={{}} />)
    expect(screen.getAllByText('Releer este extracto')).toHaveLength(1)
    fireEvent.click(screen.getByLabelText('Releer este extracto: Tarjeta Nu a'))
    expect(onAccion).toHaveBeenCalledWith('releer', expect.objectContaining({ historial_id: 'h-a' }))
  })
})
