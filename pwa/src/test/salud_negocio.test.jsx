// «Salud del negocio»: pantalla solo para la administración. Datos sintéticos.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({ panelNegocio: vi.fn() }))
vi.mock('../lib/api', () => ({ api }))
const auth = vi.hoisted(() => ({ usuario: { id: 'u', email: 'dueno@cuadrame.test' } }))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => auth }))

import SaludNegocio from '../screens/SaludNegocio'
import { HojaMas } from '../components/MenuMas'
import { DESTINO_ADMIN, GRUPOS, esAdminVisible } from '../lib/navegacion'

const cap = (id, nombre, actual, limite, pct, nivel, unidad = 'usuarios') => ({
  id, nombre, unidad, actual, limite, pct, nivel, significa: 'x', accion: `Haz algo con ${id}`, umbrales: [60, 80],
})
const PANEL = {
  generado_en: '2026-10-07T08:00:00',
  usuarios: { usuarios_total: 42, activos_7d: 17, activos_30d: 30, nuevos_7d: 5, nuevos_30d: 12 },
  capacidades: [
    cap('gmail', 'usuarios con Gmail conectado', 82, 100, 82, 'alto'),
    cap('base', 'la base de datos', 120, 500, 24, 'ok', 'MB'),
    cap('resend_mes', 'los correos de este mes (Resend)', null, 3000, null, 'sin_dato', 'correos'),
  ],
  senales: [{ id: 'errores_5xx', nombre: 'errores del servidor (últimas 24 h)', actual: 31, alerta: true, accion: 'Abre Sentry.' }],
  volumen: { movimientos: 1200, correos_procesados: 300, extractos_procesados: 20, ia_mes: 88 },
  tendencia: Array.from({ length: 30 }, (_, i) => ({ dia: `2026-09-${i + 1}`, nuevos: i % 3 === 0 ? 1 : 0, total: 30 + i })),
}

beforeEach(() => {
  api.panelNegocio.mockReset()
  auth.usuario = { id: 'u', email: 'dueno@cuadrame.test' }
  vi.unstubAllEnvs()
})

const montar = () => render(<MemoryRouter><SaludNegocio /></MemoryRouter>)

describe('Pantalla «Salud del negocio»', () => {
  it('muestra usuarios, barras de capacidad con su porcentaje y qué hacer cuando se acerca el límite', async () => {
    api.panelNegocio.mockResolvedValue(PANEL)
    montar()
    expect(await screen.findByTestId('usuarios-total')).toHaveTextContent('42')
    const gmail = screen.getByTestId('cap-gmail')
    const barra = within(gmail).getByRole('progressbar')
    expect(barra).toHaveAttribute('aria-valuenow', '82')
    expect(within(gmail).getByText(/Haz algo con gmail/)).toBeInTheDocument()
    // holgado: sin recomendación; sin dato: no inventa porcentaje
    expect(within(screen.getByTestId('cap-base')).queryByText(/Qué hacer/)).toBeNull()
    expect(within(screen.getByTestId('cap-resend_mes')).getAllByText(/Sin dato/).length).toBeGreaterThan(0)
    expect(screen.getByRole('alert')).toHaveTextContent('errores del servidor')
    expect(screen.getByTestId('sparkline')).toBeInTheDocument() // tendencia 30 días
  })

  it('si el servidor responde 404 (no es admin) no muestra datos', async () => {
    api.panelNegocio.mockRejectedValue(Object.assign(new Error('x'), { status: 404 }))
    montar()
    expect(await screen.findByText('Esta pantalla no está disponible')).toBeInTheDocument()
    expect(screen.queryByTestId('usuarios-total')).toBeNull()
  })

  it('un error cualquiera muestra un mensaje amable', async () => {
    api.panelNegocio.mockRejectedValue(new Error('caído'))
    montar()
    expect(await screen.findByText('No se pudo cargar')).toBeInTheDocument()
  })
})

describe('Acceso desde el menú', () => {
  it('el correo de administración se compara sin importar mayúsculas y solo si hay VITE_ADMIN_EMAIL', () => {
    expect(esAdminVisible('dueno@cuadrame.test')).toBe(false) // sin variable: nadie
    vi.stubEnv('VITE_ADMIN_EMAIL', 'Dueno@CuadraMe.test')
    expect(esAdminVisible('dueno@cuadrame.test')).toBe(true)
    expect(esAdminVisible('otro@test.com')).toBe(false)
    expect(esAdminVisible('')).toBe(false)
    // nunca está entre los destinos comunes (ni en el buscador)
    expect(GRUPOS.flatMap((g) => g.items).some((i) => i.to === DESTINO_ADMIN.to)).toBe(false)
  })

  it('el menú «Más» muestra el acceso solo al administrador', async () => {
    vi.stubEnv('VITE_ADMIN_EMAIL', 'dueno@cuadrame.test')
    const { unmount } = render(<MemoryRouter><HojaMas onCerrar={() => {}} pathname="/" /></MemoryRouter>)
    await waitFor(() => expect(screen.getByRole('link', { name: /Salud del negocio/ })).toBeInTheDocument())
    unmount()

    auth.usuario = { id: 'c', email: 'cliente@test.com' }
    render(<MemoryRouter><HojaMas onCerrar={() => {}} pathname="/" /></MemoryRouter>)
    await waitFor(() => expect(screen.getByRole('link', { name: /Perfil/ })).toBeInTheDocument())
    expect(screen.queryByRole('link', { name: /Salud del negocio/ })).toBeNull()
  })
})
