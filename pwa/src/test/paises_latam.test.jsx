// País: registro, formato de dinero, gating de impuestos, bancos por país y sugerencia.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../lib/api', () => ({
  api: {
    paisPerfil: vi.fn(),
    guardarPaisPerfil: vi.fn(),
    impuestosResumen: vi.fn(async () => ({ gmf: { meses: [], tope_exento_mensual: 1, total_estimado: 0, promedio_mensual: 0, total_registrado: 0 }, deducibles: { total: 0, items: [], categorias: [] }, cuentas_ahorro: [], aviso: '' })),
    rentaEstimada: vi.fn(async () => null),
  },
}))
vi.mock('../lib/BloqueoContext', () => ({ useBloqueo: () => ({ fmt: (v) => `$${v}` }) }))
vi.mock('../components/TarjetaRenta', () => ({ default: () => <div data-testid="tarjeta-renta" /> }))
vi.mock('../components/TarjetaGmfMes', () => ({ default: () => <div data-testid="tarjeta-gmf" /> }))

import { api } from '../lib/api'
import { PAISES, ORDEN, sugerirPais, tieneFuncion, configPais, bancosDePais } from '../lib/paises'
import { _reiniciarPais, cargarPais, fijarPais } from '../lib/pais'
import { formatMoneda, formatCOP } from '../lib/format'
import { t } from '../lib/textosPais'
import Impuestos from '../screens/Impuestos'
import { DialogosProvider } from '../lib/DialogosContext'
import SelectorCuenta from '../components/SelectorCuenta'
import { marcaDeEntidad } from '../lib/entidadesFinancierasCO'

beforeEach(() => {
  _reiniciarPais()
  vi.clearAllMocks()
  api.paisPerfil.mockResolvedValue({ pais: 'CO', confirmado: false, moneda_base: 'COP' })
})

describe('registro de países', () => {
  it('cada país tiene moneda, formato y bancos únicos', () => {
    for (const c of ORDEN) {
      const p = PAISES[c]
      expect(p.moneda).toBeTruthy()
      const n = p.bancos.map((b) => b.nombre)
      expect(new Set(n).size).toBe(n.length)
    }
  })
  it('renta DIAN y 4x1000 solo en Colombia; desconocido no cae a CO', () => {
    expect(tieneFuncion('CO', 'renta_dian')).toBe(true)
    expect(tieneFuncion('MX', 'renta_dian')).toBe(false)
    expect(tieneFuncion('ZZ', 'renta_dian')).toBe(false)
    expect(configPais('ZZ')).toBeNull()
  })
  it('sugerencia por zona horaria o idioma, sin IP', () => {
    expect(sugerirPais('es', 'America/Lima')).toBe('PE')
    expect(sugerirPais('es-MX', null)).toBe('MX')
    expect(sugerirPais('es-ES', null)).toBeNull()
  })
  it('textos por país con respaldo neutro', () => {
    expect(t('impuestos.declaracion', 'MX')).toMatch(/SAT/)
    expect(t('impuestos.declaracion', 'UY')).toBe('Declaración anual de impuestos')
    expect(t('impuestos.recordatorio', 'UY')).toMatch(/la DGI/)
  })
})

describe('formato de dinero por país', () => {
  it('Colombia queda igual y México usa su separador y 2 decimales', () => {
    fijarPais('CO')
    expect(formatCOP(1234567)).toBe(new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(1234567))
    fijarPais('MX')
    const mx = formatMoneda(1234.5, 'MXN')
    expect(mx).toMatch(/1,234\.50/)
    expect(formatMoneda(1234.5, 'CLP')).toMatch(/1\.?,?235|1.235/)
    expect(formatCOP(1000)).toMatch(/COP/) // fuera de Colombia no se hace pasar por pesos locales
  })
})

describe('Impuestos por país', () => {
  const montar = () => render(<DialogosProvider><MemoryRouter><Impuestos /></MemoryRouter></DialogosProvider>)
  it('en Colombia muestra renta y 4x1000', async () => {
    fijarPais('CO')
    montar()
    expect(await screen.findByTestId('tarjeta-renta')).toBeInTheDocument()
    expect(screen.queryByTestId('impuestos-informativo')).not.toBeInTheDocument()
  })
  it('en México solo el recordatorio informativo, sin tarjetas de Colombia', async () => {
    api.paisPerfil.mockResolvedValue({ pais: 'MX', confirmado: true, moneda_base: 'MXN' })
    montar()
    expect(await screen.findByTestId('impuestos-informativo')).toBeInTheDocument()
    expect(screen.getAllByText(/SAT/).length).toBeGreaterThan(0)
    expect(screen.queryByTestId('tarjeta-renta')).not.toBeInTheDocument()
    expect(screen.queryByTestId('tarjeta-gmf')).not.toBeInTheDocument()
    expect(api.impuestosResumen).not.toHaveBeenCalled()
  })
})

describe('bancos por país en el selector de cuentas', () => {
  const props = { nombre: '', setNombre: vi.fn(), tipo: 'ahorro', setTipo: vi.fn(), moneda: 'COP', setMoneda: vi.fn() }
  it('México ofrece bancos mexicanos y no colombianos', async () => {
    fijarPais('MX')
    render(<MemoryRouter><SelectorCuenta {...props} /></MemoryRouter>)
    expect(screen.getByRole('button', { name: /Banorte/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Nu México/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Bancolombia/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'MXN' })).toBeInTheDocument()
  })
  it('Colombia conserva su lista de siempre', () => {
    fijarPais('CO')
    render(<MemoryRouter><SelectorCuenta {...props} /></MemoryRouter>)
    expect(screen.getByRole('button', { name: /Bancolombia/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Banorte/ })).not.toBeInTheDocument()
  })
  it('marca de un banco de otro país sale del registro', () => {
    expect(marcaDeEntidad('Banorte Ahorros').bg).toBe('#EB0029')
    expect(bancosDePais('PE').some((b) => b.nombre === 'Yape')).toBe(true)
  })
})

describe('carga del país', () => {
  it('toma el país guardado del backend', async () => {
    api.paisPerfil.mockResolvedValue({ pais: 'CL', confirmado: true, moneda_base: 'CLP' })
    await cargarPais(true)
    await waitFor(() => expect(formatMoneda(1000, 'CLP')).toMatch(/1\.000/))
  })
})
