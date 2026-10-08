import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({ useCuentas: () => ({ recargar: api.recargar }) }))

import PropuestaTarjeta from '../components/PropuestaTarjeta'
import PanelTarjetaCredito from '../components/PanelTarjetaCredito'

const PROPUESTA = {
  cambios: { cupo_total: 5000000, dia_pago: 30, tasa_ea: 27.86 },
  datos: {
    cupo_total: 5000000, cupo_disponible: 3120500, pago_total: 1879500, pago_minimo: 187950,
    fecha_limite_pago: '2026-10-30', dia_pago: 30, fecha_corte: '2026-10-15', dia_corte: 15, tasa_ea: 27.86,
  },
  texto: 'Tu extracto dice: cupo $5.000.000, pago total $1.879.500, pago mínimo $187.950, vence el 30. ¿Actualizar tu tarjeta?',
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    recargar: vi.fn(),
    aplicarExtractoTarjeta: vi.fn().mockResolvedValue({ ok: true }),
  })
})

describe('Propuesta "Tu extracto dice..."', () => {
  it('muestra el texto y NO aplica nada hasta que se pulsa Aplicar', async () => {
    render(<PropuestaTarjeta propuesta={PROPUESTA} cuentaId="t1" />)
    expect(screen.getByText(/Tu extracto dice: cupo \$5\.000\.000/)).toBeInTheDocument()
    expect(api.aplicarExtractoTarjeta).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Aplicar' }))
    await waitFor(() => expect(api.aplicarExtractoTarjeta).toHaveBeenCalledWith('t1', {
      cupo_total: 5000000, dia_pago: 30, tasa_ea: 27.86,
      cupo_disponible: 3120500, pago_total: 1879500, pago_minimo: 187950,
      fecha_limite_pago: '2026-10-30', fecha_corte: '2026-10-15',
    }))
    expect(api.recargar).toHaveBeenCalled()
    expect(await screen.findByText(/actualizamos tu tarjeta/)).toBeInTheDocument()
  })

  it('"Ahora no" la oculta sin llamar al backend', async () => {
    render(<PropuestaTarjeta propuesta={PROPUESTA} cuentaId="t1" />)
    await userEvent.click(screen.getByRole('button', { name: 'Ahora no' }))
    expect(screen.queryByTestId('propuesta-tarjeta')).not.toBeInTheDocument()
    expect(api.aplicarExtractoTarjeta).not.toHaveBeenCalled()
  })

  it('si falla muestra el error y deja reintentar; sin propuesta no pinta nada', async () => {
    api.aplicarExtractoTarjeta.mockRejectedValue(new Error('Sin conexión'))
    const { container, rerender } = render(<PropuestaTarjeta propuesta={PROPUESTA} cuentaId="t1" />)
    await userEvent.click(screen.getByRole('button', { name: 'Aplicar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión')
    expect(screen.getByRole('button', { name: 'Aplicar' })).toBeEnabled()
    rerender(<PropuestaTarjeta propuesta={null} cuentaId="t1" />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('Panel de tarjeta con el extracto real', () => {
  const t = {
    cupo_usado: 1879500, cupo_disponible: 3120500, utilizacion_pct: 37.6, nivel_utilizacion: 'alerta',
    proximo_corte: '2026-11-15', proximo_pago: '2026-10-30', dias_para_corte: 26, dias_para_pago: 2,
    pago_minimo_estimado: 93975, pago_minimo: 187950, pago_minimo_del_extracto: true, interes_estimado: null,
    total_extracto: 1879500, pagado_desde_corte: 500000, falta_para_evitar_intereses: 1379500, compras_despues_corte: 0,
    fecha_limite_pago: '2026-10-30', dias_para_limite: 2, pagado_pct: 26.6, vencido: false, total_del_banco: true,
  }
  const cuenta = { id: 't1', nombre: 'Nu', saldo: -1879500, moneda: 'COP', tipo: 'credito', cupo_total: 5000000, dia_corte: 15, dia_pago: 30, tarjeta: t }

  it('usa el pago mínimo del extracto, avisa los días que quedan y marca que el total es del banco', () => {
    api.cuotasTarjeta = vi.fn().mockResolvedValue({ comprometido_mes: 0, planes: [] })
    render(<PanelTarjetaCredito cuenta={cuenta} />)
    expect(screen.getByText('Pago mínimo (de tu extracto):')).toBeInTheDocument()
    expect(screen.getByTestId('aviso-dias-pago')).toHaveTextContent(/Te quedan 2 días para el pago\./)
    expect(screen.getByTestId('aviso-dias-pago')).toHaveTextContent(/Pago mínimo de tu extracto: \$\s?187\.950/)
    expect(screen.getByText(/Total tomado de tu extracto del banco/)).toBeInTheDocument()
    expect(screen.getByText(/Debes/)).toBeInTheDocument()
    expect(screen.getByText(/Disponible del cupo:/)).toBeInTheDocument()
  })
})
