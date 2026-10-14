// Cuadre mes a mes: tabla, mes culpable, acciones con confirmación y saldo a mano. Datos inventados.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  cuadreEncadenado: vi.fn(), importarFaltantes: vi.fn(), cuadreSaldoInicial: vi.fn(), cuadreAjuste: vi.fn(),
  cuadreDeshacer: vi.fn(), cuadreSaldos: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))

import CuadreEncadenado from '../components/CuadreEncadenado'
import { firmado } from '../lib/cuadreEncadenado'

const montar = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>)

const fila = (extra) => ({ historial_id: 'h', causas: [], acciones: [], arrastre: 0, diferencia: 0, banco_cambio: 0, app_cambio: 0, ...extra })
const DATOS = {
  cuenta_id: 'c1', cuenta: 'Banco', moneda: 'COP', cuadra: false, sin_saldo: [],
  resumen: '1 línea de junio por $800.000 sin importar: eso es lo que descuadra tu saldo.',
  impacto: 'Corrige junio y todos los meses siguientes quedan cuadrados.',
  saldo_corregido: { texto: 'Con esas correcciones tu saldo sería $1.700.000 y el último extracto dice $1.700.000.' },
  meses: [
    fila({ mes: '2026-05', etiqueta: 'Mayo 2026', estado: 'cuadra', banco_cambio: 200000, app_cambio: 200000 }),
    fila({
      mes: '2026-06', etiqueta: 'Junio 2026', historial_id: 'hj', estado: 'diferencia', diferencia: 800000, banco_cambio: 1050000, app_cambio: 250000,
      texto: 'Junio no cuadra: el banco registró $800.000 más que tu app. Falta importar 1 línea del extracto: ingreso de $800.000 del 16 jun.',
      causas: [{ codigo: 'falta_importar', probable: true, texto: 'Falta importar 1 línea del extracto: ingreso de $800.000 del 16 jun.' }],
      acciones: [{ tipo: 'importar_lineas', historial_id: 'hj', fingerprints: ['fp'], texto: 'Importar la línea que falta', confirmacion: 'Se agregará a tus movimientos.' }],
    }),
    fila({ mes: '2026-07', etiqueta: 'Julio 2026', estado: 'arrastra', arrastre: 800000, banco_cambio: -50000, app_cambio: -50000 }),
  ],
}

beforeEach(() => Object.values(api).forEach((f) => f.mockReset()))

describe('CuadreEncadenado', () => {
  it('marca el mes culpable, dice la frase llana y el impacto', async () => {
    montar(<CuadreEncadenado cuentaId="c1" datos={DATOS} />)
    expect(screen.getByTestId('cuadre-resumen')).toHaveTextContent('1 línea de junio por $800.000 sin importar')
    const filas = screen.getAllByRole('row')
    const junio = filas.find((r) => r.getAttribute('data-estado') === 'diferencia')
    expect(junio).toHaveAttribute('data-culpable', '1')
    expect(within(junio).getByText('No cuadra')).toBeInTheDocument()
    expect(filas.find((r) => r.getAttribute('data-estado') === 'cuadra')).not.toHaveAttribute('data-culpable')
    expect(screen.getByTestId('cuadre-impacto')).toHaveTextContent('Corrige junio y todos los meses siguientes quedan cuadrados')
    expect(screen.getByText(/Junio no cuadra: el banco registró \$800\.000 más/)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/libro|conciliado/i)
  })

  it('importar la línea pide confirmación y no toca nada hasta decir sí; luego recarga', async () => {
    const u = userEvent.setup()
    api.importarFaltantes.mockResolvedValue({ ok: true, importados: 1 })
    api.cuadreEncadenado.mockResolvedValue({ ...DATOS, cuadra: true, resumen: null, impacto: null, meses: DATOS.meses.map((m) => ({ ...m, estado: 'cuadra', acciones: [] })) })
    const onCambio = vi.fn()
    montar(<CuadreEncadenado cuentaId="c1" datos={DATOS} onCambio={onCambio} />)
    await u.click(screen.getByRole('button', { name: 'Importar la línea que falta' }))
    expect(api.importarFaltantes).not.toHaveBeenCalled()
    expect(screen.getByText('Se agregará a tus movimientos.')).toBeInTheDocument()
    await u.click(screen.getByRole('button', { name: 'Sí, hacerlo' }))
    await waitFor(() => expect(api.importarFaltantes).toHaveBeenCalledWith('hj', ['fp'], {}, null))
    await waitFor(() => expect(onCambio).toHaveBeenCalled())
  })

  it('el ajuste es último recurso: exige entender el riesgo antes de habilitar el botón', async () => {
    const u = userEvent.setup()
    const datos = { ...DATOS, meses: [fila({ mes: '2026-08', etiqueta: 'Agosto 2026', estado: 'diferencia', diferencia: 5000, texto: 'Agosto no cuadra.',
      acciones: [{ tipo: 'ajuste', cuenta_id: 'c1', historial_id: 'h', monto: 5000, texto: 'Crear ajuste de saldo (último recurso)', confirmacion: 'Un ajuste tapa la diferencia.' }] })] }
    montar(<CuadreEncadenado cuentaId="c1" datos={datos} />)
    await u.click(screen.getByRole('button', { name: /Crear ajuste de saldo/ }))
    const si = screen.getByRole('button', { name: 'Sí, hacerlo' })
    expect(si).toBeDisabled()
    await u.click(screen.getByRole('checkbox'))
    expect(si).toBeEnabled()
  })

  it('un extracto sin saldo (Nu) pide escribirlo y lo guarda sin inventar', async () => {
    const u = userEvent.setup()
    api.cuadreSaldos.mockResolvedValue({ ok: true })
    api.cuadreEncadenado.mockResolvedValue({ ...DATOS, meses: [], sin_saldo: [] })
    const datos = { ...DATOS, meses: [], resumen: null, impacto: null, saldo_corregido: null,
      sin_saldo: [{ historial_id: 'hn', fecha_sugerida: '2026-09-30', texto: 'Este extracto no trae el saldo y no lo invento. Escribe el saldo que dice tu extracto al 30 sep 2026 y puedo verificar el mes.' }] }
    montar(<CuadreEncadenado cuentaId="c1" datos={datos} />)
    expect(screen.getByText(/no lo invento/)).toBeInTheDocument()
    await u.type(screen.getByLabelText(/Saldo del extracto/), '1250000')
    await u.click(screen.getByRole('button', { name: 'Guardar saldo' }))
    await waitFor(() => expect(api.cuadreSaldos).toHaveBeenCalledWith({ historial_id: 'hn', saldo_final: 1250000, fecha_corte: '2026-09-30', confirmar: true }))
  })

  it('formatea el cambio del mes con signo', () => {
    expect(firmado(1050000)).toContain('+')
    expect(firmado(-50000)).toContain('−')
    expect(firmado(0)).toBe('$0')
  })
})
