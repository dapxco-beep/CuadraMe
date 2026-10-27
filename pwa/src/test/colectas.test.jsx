import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [{ id: 'c1', nombre: 'Bancolombia', saldo: 1500000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn().mockResolvedValue() }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import Colectas from '../screens/Colectas'
import DetalleColecta from '../screens/DetalleColecta'
import ColectaPublica from '../screens/ColectaPublica'
import { enlaceCompartirColecta, enlacePublicoColecta, enlaceRecordatorioColecta, porcentaje } from '../lib/colectas'

function montar(ruta) {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter initialEntries={[ruta]}>
          <Routes>
            <Route path="/colectas" element={<Colectas />} />
            <Route path="/colectas/:id" element={<DetalleColecta />} />
            <Route path="/c/:token" element={<ColectaPublica />} />
            <Route path="*" element={<p>otra</p>} />
          </Routes>
        </MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

const DETALLE = {
  id: 'k1', nombre: 'Inscripción torneo', descripcion: '', modo: 'por_persona', moneda: 'COP', estado: 'abierta',
  fecha_limite: null, cuenta_id: 'c1', meta: 100000, recogido: 50000, falta: 50000, personas: 2, pagaron: 1,
  compartida: false, token_publico: null,
  participantes: [
    { aporte_id: 'a2', participante_id: 'x2', nombre: 'Luis Pérez', telefono: '3001234567', debe: 50000, pagado: 0, falta: 50000, estado: 'falta', pagos: [] },
    { aporte_id: 'a1', participante_id: 'x1', nombre: 'Ana Gómez', telefono: '', debe: 50000, pagado: 50000, falta: 0, estado: 'pagado',
      pagos: [{ id: 'p1', monto: 50000, fecha: '2026-10-20T12:00:00', registrado_en_cuenta: true }] },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    colectas: vi.fn().mockResolvedValue([{ ...DETALLE, participantes: undefined }]),
    colecta: vi.fn().mockResolvedValue(DETALLE),
    contactosGasto: vi.fn().mockResolvedValue([]),
    pagarColecta: vi.fn().mockResolvedValue({ id: 'p9' }),
    compartirColecta: vi.fn().mockResolvedValue({ token: 'tokenlargo' }),
    colectaPublica: vi.fn(),
  })
})

describe('ayudantes de colectas', () => {
  it('el enlace público usa # porque la app es HashRouter', () => {
    expect(enlacePublicoColecta('abc', 'https://cuadrame.dapx.shop')).toBe('https://cuadrame.dapx.shop/#/c/abc')
  })

  it('el recordatorio por WhatsApp lleva el nombre de pila, lo que falta y el enlace', () => {
    const url = decodeURIComponent(
      enlaceRecordatorioColecta({ nombre: 'Luis Pérez', telefono: '3001234567', falta: 50000, colecta: 'Torneo', enlace: 'https://x/#/c/t' })
    )
    expect(url).toContain('wa.me/573001234567')
    expect(url).toContain('Hola Luis!')
    expect(url).toContain('Torneo')
    expect(url).toContain('https://x/#/c/t')
  })

  it('compartir y porcentaje', () => {
    expect(decodeURIComponent(enlaceCompartirColecta({ colecta: 'Torneo', enlace: 'https://x' }))).toContain('Torneo')
    expect(porcentaje(50, 200)).toBe(25)
    expect(porcentaje(500, 200)).toBe(100)
    expect(porcentaje(5, 0)).toBe(0)
  })
})

describe('lista de colectas', () => {
  it('muestra el avance de cada colecta', async () => {
    montar('/colectas')
    expect(await screen.findByText('Inscripción torneo')).toBeTruthy()
    expect(screen.getByText(/1 de 2 pagaron/)).toBeTruthy()
    expect(screen.getByRole('progressbar', { name: /Inscripción torneo/ }).getAttribute('aria-valuenow')).toBe('50')
  })

  it('sin colectas invita a crear la primera', async () => {
    api.colectas.mockResolvedValue([])
    montar('/colectas')
    expect(await screen.findByText('Crear mi primera colecta')).toBeTruthy()
  })
})

describe('detalle de colecta', () => {
  it('pone primero a quien falta y marca el pago completo registrándolo como ingreso en la cuenta', async () => {
    const user = userEvent.setup()
    montar('/colectas/k1')
    expect(await screen.findByText('Luis Pérez')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: /Pagó/ }))
    await waitFor(() => expect(api.pagarColecta).toHaveBeenCalledWith('k1', 'a2', { monto: undefined, registrar_ingreso: true }))
  })

  it('crear el enlace público lo pide al servidor', async () => {
    const user = userEvent.setup()
    montar('/colectas/k1')
    await user.click(await screen.findByRole('button', { name: /Crear enlace/ }))
    await waitFor(() => expect(api.compartirColecta).toHaveBeenCalledWith('k1'))
  })

  it('quien falta tiene botón de recordar por WhatsApp', async () => {
    montar('/colectas/k1')
    const enlace = await screen.findByRole('link', { name: /Recordar/ })
    expect(enlace.getAttribute('href')).toContain('wa.me/573001234567')
  })
})

describe('página pública (sin sesión)', () => {
  it('muestra el avance y solo nombres de pila', async () => {
    api.colectaPublica.mockResolvedValue({
      nombre: 'Torneo', descripcion: '', moneda: 'COP', estado: 'abierta', fecha_limite: null, meta: 100000, recogido: 50000, falta: 50000,
      participantes: [{ nombre: 'Ana', estado: 'pagado' }, { nombre: 'Luis', estado: 'falta' }],
    })
    montar('/c/tokenlargo')
    expect(await screen.findByText('Torneo')).toBeTruthy()
    expect(screen.getByText('Ana')).toBeTruthy()
    expect(screen.getByText('Falta')).toBeTruthy()
    expect(api.colectaPublica).toHaveBeenCalledWith('tokenlargo')
  })

  it('un enlace apagado dice que ya no se comparte', async () => {
    api.colectaPublica.mockRejectedValue(Object.assign(new Error('x'), { status: 404 }))
    montar('/c/muerto')
    expect(await screen.findByText(/ya no se comparte/)).toBeTruthy()
  })
})
