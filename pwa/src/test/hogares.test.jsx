import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

const CUENTAS = [{ id: 'c1', nombre: 'Bancolombia', saldo: 1500000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn().mockResolvedValue() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ categorias: [], nombres: ['Comida', 'Hogar'], cargando: false, recargar: vi.fn(), iconoDe: () => '💳' }),
}))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => ({ usuario: { id: 'u1', email: 'b@test.com', nombre: 'Beto Pérez', nombrePila: 'Beto' } }) }))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import Hogares from '../screens/Hogares'
import DetalleHogar from '../screens/DetalleHogar'
import NuevoGastoHogar from '../screens/NuevoGastoHogar'
import UnirseHogar from '../screens/UnirseHogar'
import { enlaceCompartirInvitacion, enlaceInvitacionHogar, fraseDeuda, guardarInvitacionPendiente, tomarInvitacionPendiente } from '../lib/hogares'

function Sonda() {
  return <p data-testid="ruta">{useLocation().pathname}</p>
}

function montar(ruta) {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter initialEntries={[ruta]}>
          <Routes>
            <Route path="/hogares" element={<Hogares />} />
            <Route path="/hogares/:id" element={<DetalleHogar />} />
            <Route path="/hogares/:id/gasto" element={<NuevoGastoHogar />} />
            <Route path="/unirse/:token" element={<UnirseHogar />} />
            <Route path="*" element={<p>otra</p>} />
          </Routes>
          <Sonda />
        </MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

const DETALLE = {
  id: 'h1', nombre: 'Casa', moneda: 'COP', rol: 'admin', mi_miembro_id: 'ma', mis_avisos: true,
  miembros: [
    { id: 'ma', apodo: 'Ana', rol: 'admin', activo: true, soy_yo: true, saldo: 50000 },
    { id: 'mb', apodo: 'Beto', rol: 'miembro', activo: true, soy_yo: false, saldo: -50000 },
  ],
  simplificado: [{ de: 'mb', a: 'ma', monto: 50000, de_nombre: 'Beto', a_nombre: 'Ana' }],
  invitaciones: [{ id: 'i1', token: 'x'.repeat(30), email: null, vence_en: '2026-11-03T00:00:00' }],
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  Object.assign(api, {
    hogares: vi.fn().mockResolvedValue([{ id: 'h1', nombre: 'Casa', moneda: 'COP', rol: 'admin', mi_miembro_id: 'ma', miembros: 2, mi_saldo: 50000 }]),
    misInvitacionesHogar: vi.fn().mockResolvedValue([]),
    hogar: vi.fn().mockResolvedValue(DETALLE),
    gastosHogar: vi.fn().mockResolvedValue([
      { id: 'g1', descripcion: 'Mercado', categoria: 'Comida', total: 100000, moneda: 'COP', fecha: '2026-10-20T12:00:00', pagador: 'Ana', creado_por_id: 'ma', partes: [] },
    ]),
    crearGastoHogar: vi.fn().mockResolvedValue({ id: 'g2' }),
    pagarHogar: vi.fn().mockResolvedValue({ id: 'p1' }),
    invitarAlHogar: vi.fn().mockResolvedValue({ token: 't' }),
    verInvitacionHogar: vi.fn().mockResolvedValue({ hogar: 'Casa', moneda: 'COP' }),
    aceptarInvitacionHogar: vi.fn().mockResolvedValue({ id: 'h1' }),
  })
})

describe('ayudantes de hogares', () => {
  it('la invitación usa # (HashRouter) y se comparte por WhatsApp', () => {
    expect(enlaceInvitacionHogar('abc', 'https://cuadrame.dapx.shop')).toBe('https://cuadrame.dapx.shop/#/unirse/abc')
    expect(decodeURIComponent(enlaceCompartirInvitacion({ hogar: 'Casa', enlace: 'https://x' }))).toContain('Casa')
  })

  it('las frases de deuda se leen según quién las mira', () => {
    const p = { de: 'mb', a: 'ma', monto: 50000, de_nombre: 'Beto', a_nombre: 'Ana' }
    expect(fraseDeuda(p, 'ma', 'COP')).toMatch(/Beto te debe/)
    expect(fraseDeuda(p, 'mb', 'COP')).toMatch(/Le debes .* a Ana/)
    expect(fraseDeuda(p, 'zz', 'COP')).toMatch(/Beto le debe .* a Ana/)
  })

  it('la invitación pendiente se guarda una vez y se consume', () => {
    guardarInvitacionPendiente('tok')
    expect(tomarInvitacionPendiente()).toBe('tok')
    expect(tomarInvitacionPendiente()).toBe('')
  })
})

describe('lista de parches', () => {
  it('muestra cada hogar con tu saldo', async () => {
    montar('/hogares')
    expect(await screen.findByText('Casa')).toBeTruthy()
    expect(screen.getByText(/Te deben/)).toBeTruthy()
  })

  it('avisa de una invitación pendiente a tu correo', async () => {
    api.misInvitacionesHogar.mockResolvedValue([{ token: 'y'.repeat(30), hogar: 'Apto 301', vence_en: '2026-11-03' }])
    montar('/hogares')
    expect(await screen.findByText(/Te invitaron a “Apto 301”/)).toBeTruthy()
  })

  it('sin hogares invita a crear el primero', async () => {
    api.hogares.mockResolvedValue([])
    montar('/hogares')
    expect(await screen.findByText('Crear mi primer parche')).toBeTruthy()
  })
})

describe('detalle del hogar', () => {
  it('muestra quién le debe a quién, los gastos y las personas', async () => {
    montar('/hogares/h1')
    expect(await screen.findByText(/Beto te debe/)).toBeTruthy()
    expect(screen.getByText('Mercado')).toBeTruthy()
    expect(screen.getByText(/Ana \(tú\)/)).toBeTruthy()
  })

  it('«Me pagó» registra el pago entre los dos miembros', async () => {
    const user = userEvent.setup()
    montar('/hogares/h1')
    await user.click(await screen.findByRole('button', { name: 'Me pagó' }))
    await user.click(await screen.findByRole('button', { name: 'Sí, registrar' }))
    await waitFor(() => expect(api.pagarHogar).toHaveBeenCalledWith('h1', { de_id: 'mb', a_id: 'ma', monto: 50000 }))
  })

  it('«Invitar con un enlace» crea la invitación sin correo y abre el menú de compartir', async () => {
    const compartir = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'share', { value: compartir, configurable: true })
    const user = userEvent.setup()
    montar('/hogares/h1')
    await user.click(await screen.findByTestId('invitar-enlace'))
    await waitFor(() => expect(api.invitarAlHogar).toHaveBeenCalledWith('h1', ''))
    await waitFor(() => expect(compartir).toHaveBeenCalled())
    expect(compartir.mock.calls[0][0].url).toBe('http://localhost:3000/#/unirse/t')
    delete navigator.share
  })

  it('invitar por correo sin escribir el correo no crea nada', async () => {
    const user = userEvent.setup()
    montar('/hogares/h1')
    await user.click(await screen.findByRole('button', { name: 'Invitar' }))
    expect(api.invitarAlHogar).not.toHaveBeenCalled()
  })

  it('si estás solo en el parche, un aviso arriba invita con enlace; con más personas no sale', async () => {
    api.hogar.mockResolvedValue({ ...DETALLE, miembros: DETALLE.miembros.slice(0, 1) })
    const { unmount } = montar('/hogares/h1')
    expect(await screen.findByTestId('parche-solo')).toBeTruthy()
    unmount()
    api.hogar.mockResolvedValue(DETALLE)
    montar('/hogares/h1')
    await screen.findByText('Mercado')
    expect(screen.queryByTestId('parche-solo')).toBeNull()
  })

  it('una invitación pendiente se puede volver a compartir', async () => {
    const compartir = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'share', { value: compartir, configurable: true })
    const user = userEvent.setup()
    montar('/hogares/h1')
    await user.click(await screen.findByRole('button', { name: /Compartir/ }))
    await waitFor(() => expect(compartir).toHaveBeenCalled())
    expect(compartir.mock.calls[0][0].text).toMatch(/gratis/)
    delete navigator.share
  })

  it('cada gasto dice si tu parte ya está en tus gastos o deja pasarla (una sola vez)', async () => {
    api.gastosHogar.mockResolvedValue([
      { id: 'g1', descripcion: 'Mercado', categoria: 'Comida', total: 100000, moneda: 'COP', fecha: '2026-10-20T12:00:00', pagador: 'Ana', creado_por_id: 'ma', partes: [], mi_parte: 50000, en_mis_gastos: false },
      { id: 'g2', descripcion: 'Internet', categoria: null, total: 80000, moneda: 'COP', fecha: '2026-10-21T12:00:00', pagador: 'Ana', creado_por_id: 'ma', partes: [], mi_parte: 40000, en_mis_gastos: true },
    ])
    api.pasarGastoHogarAMisGastos = vi.fn().mockResolvedValue({ ok: true })
    const user = userEvent.setup()
    montar('/hogares/h1')
    expect(await screen.findByTestId('en-mis-gastos')).toHaveTextContent('ya está en tus gastos')
    const botones = screen.getAllByTestId('pasar-a-mis-gastos')
    expect(botones).toHaveLength(1)
    await user.click(botones[0])
    // con una sola cuenta de la misma moneda se pasa directo; con varias, pide elegir
    await waitFor(() => expect(api.pasarGastoHogarAMisGastos.mock.calls.length + (screen.queryByTestId('hoja-cuentas-pasar') ? 1 : 0)).toBe(1))
  })

  it('solo administración ve las invitaciones; un miembro común no', async () => {
    api.hogar.mockResolvedValue({ ...DETALLE, rol: 'miembro', invitaciones: [] })
    montar('/hogares/h1')
    await screen.findByText('Mercado')
    expect(screen.queryByText('Invitar')).toBeNull()
  })
})

describe('nuevo gasto del hogar', () => {
  it('reparte entre todos por defecto y guarda con quien pagó', async () => {
    const user = userEvent.setup()
    montar('/hogares/h1/gasto')
    await user.type(await screen.findByLabelText('Descripción'), 'Arriendo')
    await user.type(screen.getByLabelText('Total'), '900000')
    await user.click(screen.getByRole('button', { name: 'Guardar gasto' }))
    await waitFor(() => expect(api.crearGastoHogar).toHaveBeenCalled())
    const [id, cuerpo] = api.crearGastoHogar.mock.calls[0]
    expect(id).toBe('h1')
    expect(cuerpo).toMatchObject({ descripcion: 'Arriendo', total: 900000, modo: 'iguales', pagador_id: 'ma', registrar_en_mi_cuenta: false })
    expect(cuerpo.participantes.map((p) => p.id)).toEqual(['ma', 'mb'])
  })
})

describe('unirse con la invitación', () => {
  it('muestra el hogar y acepta con el apodo', async () => {
    const user = userEvent.setup()
    montar('/unirse/' + 'z'.repeat(30))
    expect(await screen.findByText('Casa')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Unirme al parche' }))
    await waitFor(() => expect(api.aceptarInvitacionHogar).toHaveBeenCalledWith('z'.repeat(30), 'Beto'))
    await waitFor(() => expect(screen.getByTestId('ruta').textContent).toBe('/hogares/h1'))
  })

  it('una invitación vencida o usada lo dice claro', async () => {
    api.verInvitacionHogar.mockRejectedValue(Object.assign(new Error('x'), { status: 404 }))
    montar('/unirse/muerta')
    expect(await screen.findByText(/ya se usó o venció/)).toBeTruthy()
  })
})
