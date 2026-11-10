// Inicio pide cada cosa una sola vez: /recordatorios y /consejos una petición diferida repartida por props,
// y el estado de Gmail sale de /conexiones/estado (ya no se pide /correos/gmail/estado aparte).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({
  useAuth: () => ({ usuario: { id: 'u1', email: 'l@test.com', nombre: 'Laura Gómez' } }),
}))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ iconoDe: () => '💳' }) }))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import Inicio from '../screens/Inicio'
import Recordatorios from '../components/Recordatorios'

function montar() {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter>
          <Inicio />
        </MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  localStorage.setItem('cuadrame:modo-completo:u1', '1')
  Object.assign(api, {
    cuentas: vi.fn().mockResolvedValue([{ id: 'c1', nombre: 'Bancolombia', saldo: 1_000_000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]),
    movimientos: vi.fn().mockResolvedValue([{ id: 'm1', fecha: '2026-10-02T12:00:00', descripcion: 'Éxito', categoria: 'Mercado', tipo: 'expense', monto: 80000 }]),
    reporteMensual: vi.fn().mockResolvedValue({ salud: { score: 80, tips: ['ok'] }, top_categorias: [] }),
    disponibleHoy: vi.fn().mockResolvedValue({ categorias: [] }),
    enMiBolsillo: vi.fn().mockResolvedValue({ saldo_total: 1_000_000, recurrentes_pendientes_mes: 0, aportes_comprometidos_mes: 0, disponible_real: 400_000, disponible_real_por_dia: 25_000 }),
    gmailEstado: vi.fn().mockResolvedValue({ conectado: true }),
    conexionesEstado: vi.fn().mockResolvedValue({ hay_falla: false, gmail: { conectado: true } }),
    sincronizacionEstado: vi.fn().mockResolvedValue({ tareas: [] }),
    saludFinanciera: vi.fn().mockResolvedValue(null),
    tendencias: vi.fn().mockResolvedValue({ meses: [] }),
    recordatorios: vi.fn().mockResolvedValue([
      { clave: 'tarjeta:1', tipo: 'tarjeta', titulo: 'Paga tu tarjeta', texto: 'Vence pronto', ruta: '/cuentas' },
    ]),
    consejos: vi.fn().mockResolvedValue({ consejos: [], aviso: 'x' }),
  })
})

afterEach(() => vi.useRealTimers())

describe('Inicio — una sola petición por dato', () => {
  it('pide /recordatorios y /consejos una vez, sin pedir gmailEstado, y los recordatorios se pintan', async () => {
    montar()
    expect(await screen.findByText('Puedes gastar hoy')).toBeInTheDocument()
    await waitFor(() => expect(api.recordatorios).toHaveBeenCalledTimes(1), { timeout: 4000 })
    await waitFor(() => expect(api.consejos).toHaveBeenCalledTimes(1), { timeout: 4000 })
    await waitFor(() => expect(api.conexionesEstado).toHaveBeenCalled(), { timeout: 4000 })
    expect(await screen.findByText('Paga tu tarjeta')).toBeInTheDocument()
    expect(api.gmailEstado).not.toHaveBeenCalled()
    expect(api.recordatorios).toHaveBeenCalledTimes(1)
  })

  it('Recordatorios con `datos` del padre no pide nada; sin `datos` los pide solo', async () => {
    const lista = [{ clave: 'k1', tipo: 'tarjeta', titulo: 'Del padre', texto: 't', ruta: '/x' }]
    const { unmount } = render(<MemoryRouter><Recordatorios datos={lista} /></MemoryRouter>)
    expect(screen.getByText('Del padre')).toBeInTheDocument()
    expect(api.recordatorios).not.toHaveBeenCalled()
    unmount()
    render(<MemoryRouter><Recordatorios /></MemoryRouter>)
    expect(await screen.findByText('Paga tu tarjeta')).toBeInTheDocument()
    expect(api.recordatorios).toHaveBeenCalledTimes(1)
  })
})
