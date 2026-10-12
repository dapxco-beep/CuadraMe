// «¿Tengo que declarar renta?» y «4x1000 este mes»: tarjetas de Impuestos, cuenta atrás y glosario.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({ rentaEstimada: vi.fn(), gmfEstimado: vi.fn(), rentaResumenCsv: vi.fn() }))
vi.mock('../lib/api', () => ({ api }))

import { DialogosProvider } from '../lib/DialogosContext'
import TarjetaRenta from '../components/TarjetaRenta'
import TarjetaGmfMes from '../components/TarjetaGmfMes'
import { GLOSARIO, terminoPorId } from '../lib/aprende'
import { cuentaAtras, pctBarra } from '../lib/renta'

const montar = (ui) => render(<DialogosProvider><MemoryRouter>{ui}</MemoryRouter></DialogosProvider>)

const criterio = (id, nombre, pct, estado, valor = 1000) => ({ id, nombre, glosa: '', valor, tope: 69718600, tope_uvt: 1400, pct, estado, nota: '' })
const RENTA = {
  anio: 2025, uvt: 49799,
  resultado: { clave: 'cerca', titulo: 'Estás cerca', detalle: 'Vas cerca del tope de: ingresos.', faltan: [] },
  plazo: { dias_restantes: 14, vencido: false, abierto: true, texto: 'Vence el 26 de octubre' },
  criterios: [
    criterio('patrimonio_bruto', 'Patrimonio bruto', 20, 'lejos'),
    criterio('ingresos_brutos', 'Ingresos', 75.5, 'cerca'),
    criterio('consumos_tarjeta', 'Compras con tarjeta de crédito', 120, 'superado'),
    criterio('compras_consumos', 'Compras y consumos', 0, 'sin_datos', 0),
    criterio('consignaciones', 'Consignaciones y depósitos', 61, 'cerca'),
  ],
  limites: ['Solo ve las cuentas y movimientos que cargaste (no ve cuentas que no agregaste).'],
  aviso: 'Es una ayuda informativa.', enlaces: { dian: 'https://www.dian.gov.co' },
}

beforeEach(() => Object.values(api).forEach((f) => f.mockReset()))

describe('lib/renta', () => {
  it('cuenta atrás en lenguaje llano', () => {
    expect(cuentaAtras(RENTA.plazo)).toBe('Vence el 26 de octubre · faltan 14 días')
    expect(cuentaAtras({ ...RENTA.plazo, dias_restantes: 1 })).toContain('falta 1 día')
    expect(cuentaAtras({ ...RENTA.plazo, dias_restantes: 0 })).toContain('es hoy')
    expect(cuentaAtras({ texto: 'El plazo venció el 26 de octubre', dias_restantes: -2 })).toBe('El plazo venció el 26 de octubre')
    expect(cuentaAtras(null)).toBe('')
  })
  it('la barra nunca pasa del 100 %', () => {
    expect(pctBarra({ pct: 250 })).toBe(100)
    expect(pctBarra({ pct: -3 })).toBe(0)
  })
})

describe('TarjetaRenta', () => {
  it('muestra resultado, 5 barras, plazo, enlace a la DIAN y aviso', async () => {
    api.rentaEstimada.mockResolvedValue(RENTA)
    montar(<TarjetaRenta />)
    expect(await screen.findByText('Estás cerca')).toBeTruthy()
    expect(screen.getAllByRole('progressbar')).toHaveLength(5)
    expect(screen.getByTestId('renta-plazo').textContent).toContain('Vence el 26 de octubre')
    expect(screen.getByTestId('renta-plazo').textContent).toContain('faltan 14 días')
    expect(screen.getByText('Superaste el tope')).toBeTruthy()
    expect(screen.getByText('Faltan datos')).toBeTruthy()
    const dian = screen.getByRole('link', { name: /Ir a la DIAN/ })
    expect(dian.getAttribute('href')).toBe('https://www.dian.gov.co')
    expect(screen.getByText(/no es asesoría tributaria/i)).toBeTruthy()
  })
  it('descarga el resumen del año gravable', async () => {
    api.rentaEstimada.mockResolvedValue(RENTA)
    api.rentaResumenCsv.mockResolvedValue()
    montar(<TarjetaRenta />)
    fireEvent.click(await screen.findByRole('button', { name: /Descargar resumen para mi declaración/ }))
    await waitFor(() => expect(api.rentaResumenCsv).toHaveBeenCalledWith(2025))
  })
  it('si el servidor falla no rompe la pantalla', async () => {
    api.rentaEstimada.mockRejectedValue(new Error('x'))
    montar(<TarjetaRenta />)
    expect(await screen.findByText(/No pudimos calcular si te toca declarar/)).toBeTruthy()
  })
})

describe('TarjetaGmfMes', () => {
  const GMF = {
    mes: '2026-10', gmf_pagado: 4200, debitos_total: 16000000, debitos_cuenta_exenta: null, tiene_cuenta_exenta: false,
    tope_exento_mensual: 18330900, uso_pct: 87.2, alerta: true, mensaje: 'Te acercas al tope de tu cuenta exenta',
    recordatorio: ['Puedes pedir en tu banco que marquen UNA cuenta de ahorros como exenta del 4x1000.'], nota: 'Estimado.',
  }
  it('avisa al 80 % y recuerda marcar la cuenta exenta', async () => {
    api.gmfEstimado.mockResolvedValue(GMF)
    montar(<TarjetaGmfMes />)
    expect(await screen.findByText('Te acercas al tope de tu cuenta exenta')).toBeTruthy()
    expect(screen.getByText(/pedir en tu banco/)).toBeTruthy()
    expect(screen.getByText(/Aún no marcas tu cuenta exenta/)).toBeTruthy()
  })
  it('sin alerta no muestra el aviso', async () => {
    api.gmfEstimado.mockResolvedValue({ ...GMF, alerta: false, uso_pct: 10, tiene_cuenta_exenta: true, debitos_cuenta_exenta: 1000 })
    montar(<TarjetaGmfMes />)
    await screen.findByTestId('tarjeta-gmf-mes')
    expect(screen.queryByText('Te acercas al tope de tu cuenta exenta')).toBeNull()
  })
})

describe('glosario de renta', () => {
  it.each(['uvt', 'patrimonio-bruto', '4x1000', 'cuenta-exenta', 'consignaciones'])('define «%s»', (id) => {
    const t = terminoPorId(id)
    expect(t && t.definicion.length > 20).toBe(true)
  })
  it('los ids del glosario son únicos', () => {
    expect(new Set(GLOSARIO.map((g) => g.id)).size).toBe(GLOSARIO.length)
  })
})
