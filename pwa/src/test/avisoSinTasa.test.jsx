import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'

const api = vi.hoisted(() => ({ fijarTasaManual: vi.fn() }))
vi.mock('../lib/api', () => ({ api }))

import AvisoSinTasa, { parsearTasa, textoSinTasa } from '../components/AvisoSinTasa'
import { formatCOP, formatCOPFijo } from '../lib/format'
import { _reiniciarPais, fijarPais } from '../lib/pais'

afterEach(() => {
  _reiniciarPais()
  api.fijarTasaManual.mockReset()
})

describe('aviso de moneda sin tasa', () => {
  it('no muestra nada si no falta ninguna tasa', () => {
    const { container } = render(<AvisoSinTasa monedas={[]} base="COP" />)
    expect(container).toBeEmptyDOMElement()
    expect(textoSinTasa(undefined)).toBe('')
  })

  it('dice qué moneda falta y que no está sumada', () => {
    render(<AvisoSinTasa monedas={['MXN']} base="COP" />)
    expect(screen.getByRole('status')).toHaveTextContent('No tenemos la tasa de MXN: esas cuentas no están sumadas en el total.')
    expect(textoSinTasa(['MXN', 'USD'])).toContain('MXN y USD')
  })

  it('«Poner tasa» abre la hoja, guarda por moneda y avisa para recargar', async () => {
    api.fijarTasaManual.mockResolvedValue({})
    const onResuelto = vi.fn()
    render(<AvisoSinTasa monedas={['MXN']} base="COP" onResuelto={onResuelto} />)
    await userEvent.click(screen.getByRole('button', { name: /poner tasa/i }))
    await userEvent.type(screen.getByLabelText('Tasa de MXN en COP'), '230,5')
    await userEvent.click(screen.getByRole('button', { name: /guardar tasa/i }))
    await waitFor(() => expect(api.fijarTasaManual).toHaveBeenCalledWith('MXN', 230.5))
    await waitFor(() => expect(onResuelto).toHaveBeenCalled())
  })

  it('rechaza una tasa vacía o no positiva sin llamar al servidor', async () => {
    render(<AvisoSinTasa monedas={['MXN']} base="COP" />)
    await userEvent.click(screen.getByRole('button', { name: /poner tasa/i }))
    await userEvent.type(screen.getByLabelText('Tasa de MXN en COP'), '0')
    await userEvent.click(screen.getByRole('button', { name: /guardar tasa/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('mayor que cero')
    expect(api.fijarTasaManual).not.toHaveBeenCalled()
    expect(parsearTasa('1.234,5')).toBeNull() // ambiguo: mejor pedir un número simple
    expect(parsearTasa('17,25')).toBe(17.25)
  })
})

describe('formato en la moneda base', () => {
  it('base COP en Colombia: idéntico a siempre', () => {
    fijarPais('CO', { confirmado: true, monedaBase: 'COP' })
    expect(formatCOP(1234567)).toBe(formatCOPFijo(1234567))
    expect(formatCOP(1234567)).toMatch(/1\.234\.567/)
  })

  it('base MXN: usa pesos mexicanos, no «COP»', () => {
    fijarPais('MX', { confirmado: true, monedaBase: 'MXN' })
    const t = formatCOP(1500)
    expect(t).toMatch(/1,?500/)
    expect(t).not.toMatch(/COP/)
    expect(formatCOPFijo(1500)).toMatch(/COP/) // impuestos DIAN: siempre COP
  })
})
