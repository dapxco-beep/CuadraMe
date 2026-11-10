// Lupa del Inicio (abre «Más» con el buscador enfocado) y tarjeta «¿Sabías que…?».
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
const auth = vi.hoisted(() => ({ usuario: { id: 'u1', email: 'l@test.com', nombre: 'Laura' } }))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => auth }))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ iconoDe: () => 'x' }) }))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import { HojaMas } from '../components/MenuMas'
import InicioSimple from '../components/InicioSimple'
import SabiasQue, { SABIAS, elegirSabias } from '../components/SabiasQue'
import { marcarFuncionEnUso } from '../lib/modoSimple'
import Inicio from '../screens/Inicio'

let n = 0
beforeEach(() => {
  localStorage.clear()
  n += 1
  auth.usuario = { id: `ls${n}`, email: 'l@test.com', nombre: 'Laura' }
  Object.assign(api, {
    metas: vi.fn().mockResolvedValue([]),
    deudas: vi.fn().mockResolvedValue([]),
    recurrentes: vi.fn().mockResolvedValue([]),
    patrimonio: vi.fn().mockResolvedValue({ activos: [] }),
  })
})

const envolver = (ui) => (
  <ThemeProvider>
    <DialogosProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </DialogosProvider>
  </ThemeProvider>
)

describe('elegirSabias', () => {
  it('sin metas ofrece Metas; con metas pasa a Pagos fijos', () => {
    expect(elegirSabias({ enUso: [] }).id).toBe('metas')
    expect(elegirSabias({ enUso: ['/metas'] }).id).toBe('fijos')
  })
  it('sin Gmail conectado ofrece correos; la voz queda para cuando ya usa lo demás', () => {
    expect(elegirSabias({ enUso: ['/metas', '/recurrentes'], gmailConectado: false }).id).toBe('correos')
    expect(elegirSabias({ enUso: ['/metas', '/recurrentes'], gmailConectado: true }).id).toBe('voz')
  })
  it('salta lo descartado y devuelve null si ya no queda nada', () => {
    expect(elegirSabias({ enUso: [], descartados: ['metas'] }).id).toBe('fijos')
    expect(elegirSabias({ enUso: ['/metas', '/recurrentes', '/deudas'], descartados: SABIAS.map((s) => s.id) })).toBeNull()
  })
  it('la tarjeta de voz habla del asistente de voz del celular', () => {
    const voz = SABIAS.find((s) => s.id === 'voz')
    expect(voz.texto).toMatch(/asistente de voz de tu celular/)
  })
})

describe('SabiasQue', () => {
  it('muestra una sola tarjeta, se descarta y no vuelve a salir (se guarda por id)', async () => {
    const { unmount } = render(envolver(<SabiasQue />))
    const tarjeta = screen.getByTestId('sabias-que')
    expect(tarjeta).toHaveAttribute('data-sabias', 'metas')
    expect(screen.getAllByTestId('sabias-que')).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: /Descartar/ }))
    expect(screen.getByTestId('sabias-que')).toHaveAttribute('data-sabias', 'fijos')
    expect(JSON.parse(localStorage.getItem('cuadrame:sabias-descartados'))).toEqual(['metas'])
    unmount()
    render(envolver(<SabiasQue />))
    expect(screen.getByTestId('sabias-que')).toHaveAttribute('data-sabias', 'fijos')
  })

  it('si la persona ya usa Metas (en uso), no se la ofrece', () => {
    marcarFuncionEnUso(auth.usuario.id, '/metas')
    render(envolver(<SabiasQue />))
    expect(screen.getByTestId('sabias-que')).toHaveAttribute('data-sabias', 'fijos')
  })

  it('InicioSimple la pone entre las acciones y «Este mes», y no aparece con el camino de 3 pasos', () => {
    const props = { saldo: 1000, gastosSemana: 0, recientes: [], siguiente: null, fmt: String, iconoDe: () => '' }
    const { unmount } = render(envolver(<InicioSimple {...props} enCamino={false} />))
    expect(screen.getByTestId('sabias-que')).toBeInTheDocument()
    unmount()
    render(envolver(<InicioSimple {...props} enCamino />))
    expect(screen.queryByTestId('sabias-que')).toBeNull()
  })
})

describe('Lupa', () => {
  it('HojaMas con enfocarBuscador deja el buscador enfocado', async () => {
    render(envolver(<HojaMas onCerrar={() => {}} pathname="/" enfocarBuscador />))
    await waitFor(() => expect(screen.getByRole('searchbox', { name: 'Buscar en el menú' })).toHaveFocus())
  })

  it('la lupa del Inicio abre «Más» con el buscador enfocado', async () => {
    Object.assign(api, {
      cuentas: vi.fn().mockResolvedValue([]),
      movimientos: vi.fn().mockResolvedValue([]),
      reporteMensual: vi.fn().mockResolvedValue(null),
    })
    render(envolver(<Inicio />))
    await userEvent.click(await screen.findByTestId('lupa-inicio'))
    await waitFor(() => expect(screen.getByRole('searchbox', { name: 'Buscar en el menú' })).toHaveFocus())
  })
})
