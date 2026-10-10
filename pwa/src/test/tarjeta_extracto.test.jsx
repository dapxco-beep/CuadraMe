import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('../lib/api', () => ({ api: {} }))

import PanelTarjetaCredito from '../components/PanelTarjetaCredito'

const BASE = {
  cupo_usado: 950000, cupo_disponible: 1050000, utilizacion_pct: 47.5, nivel_utilizacion: 'ok',
  proximo_corte: '2026-11-15', proximo_pago: '2026-10-30', dias_para_corte: 26, dias_para_pago: 10,
  pago_minimo_estimado: 47500, interes_estimado: null,
  total_extracto: 1000000, pagado_desde_corte: 300000, falta_para_evitar_intereses: 700000,
  compras_despues_corte: 250000, fecha_limite_pago: '2026-10-30', fecha_ultimo_corte: '2026-10-15',
  dias_para_limite: 10, pagado_pct: 30, vencido: false,
}
const cuenta = (t) => ({
  id: 't1', nombre: 'Nu', saldo: -950000, moneda: 'COP', tipo: 'credito',
  cupo_total: 2000000, dia_corte: 15, dia_pago: 30, tasa_ea: null, tarjeta: t,
})

describe('Panel de tarjeta: pago para no pagar intereses', () => {
  it('muestra lo que falta del extracto con fecha y barra de lo pagado', () => {
    render(<PanelTarjetaCredito cuenta={cuenta(BASE)} />)
    const bloque = screen.getByTestId('bloque-extracto')
    expect(bloque).toHaveTextContent(/Para no pagar intereses:\s*\$\s?700\.000/)
    expect(bloque).toHaveTextContent('antes del 30 oct')
    expect(screen.getByRole('progressbar', { name: 'Pagado del extracto' })).toHaveAttribute('aria-valuenow', '30')
    expect(bloque).toHaveTextContent(/Total del extracto\s*\$\s?1\.000\.000/)
    expect(bloque).toHaveTextContent(/Compras después del corte:\s*\$\s?250\.000/)
  })

  it('si el extracto está pagado lo dice y no pide nada', () => {
    const t = { ...BASE, falta_para_evitar_intereses: 0, pagado_desde_corte: 1000000, pagado_pct: 100 }
    render(<PanelTarjetaCredito cuenta={cuenta(t)} />)
    expect(screen.getByTestId('bloque-extracto')).toHaveTextContent('Extracto pagado')
  })

  it('si el plazo venció avisa', () => {
    render(<PanelTarjetaCredito cuenta={cuenta({ ...BASE, vencido: true, dias_para_limite: -3 })} />)
    expect(screen.getByTestId('bloque-extracto')).toHaveTextContent(/plazo ya pasó/)
  })

  it('tarjeta nueva con saldo declarado: no habla de plazo vencido ni de extracto', () => {
    const t = { ...BASE, saldo_declarado: true, vencido: false, dias_para_limite: -5 }
    render(<PanelTarjetaCredito cuenta={cuenta(t)} />)
    const b = screen.getByTestId('bloque-extracto-declarado')
    expect(b).toHaveTextContent(/el saldo que declaraste/)
    expect(b).toHaveTextContent(/Aún no tenemos un extracto/)
    expect(screen.queryByText(/plazo ya pasó/)).not.toBeInTheDocument()
  })

  it('sin extracto (sin día de corte) mantiene el mensaje anterior', () => {
    const t = { ...BASE, total_extracto: null, falta_para_evitar_intereses: null }
    render(<PanelTarjetaCredito cuenta={cuenta(t)} />)
    expect(screen.queryByTestId('bloque-extracto')).not.toBeInTheDocument()
    expect(screen.getByText(/Paga el total antes del 30 oct/)).toBeInTheDocument()
  })
})
