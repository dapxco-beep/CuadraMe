import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

const CUENTAS = [{ id: 'c1', nombre: 'Bancolombia', saldo: 1500000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]

const api = vi.hoisted(() => ({}))
const imagen = vi.hoisted(() => ({ prepararImagen: vi.fn() }))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/imagen', () => imagen)
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn().mockResolvedValue() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ categorias: [], nombres: ['Comida', 'Transporte'], cargando: false, recargar: vi.fn(), iconoDe: () => '💳' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import Agregar from '../screens/Agregar'
import DividirGasto from '../screens/DividirGasto'
import CuentasAmigos from '../screens/CuentasAmigos'
import { enlaceCobroWhatsApp, telefonoParaWhatsApp } from '../lib/gastosCompartidos'

function Sonda() {
  const l = useLocation()
  return <p data-testid="ruta">{l.pathname}</p>
}

function montar(ruta = '/agregar', state) {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter initialEntries={[{ pathname: ruta, state }]}>
          <Routes>
            <Route path="/agregar" element={<Agregar />} />
            <Route path="/dividir" element={<DividirGasto />} />
            <Route path="/amigos" element={<CuentasAmigos />} />
            <Route path="*" element={<p>otra</p>} />
          </Routes>
          <Sonda />
        </MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

const SALDOS = {
  monedas: [{
    moneda: 'COP', total_me_deben: 50000, total_debo: 0,
    personas: [{ contacto_id: 'k1', nombre: 'Ana Gómez', telefono: '3001234567', saldo: 50000 }],
    simplificado: [{ de: 'k1', a: 'yo', de_nombre: 'Ana Gómez', a_nombre: 'Tú', monto: 50000 }],
  }],
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(api, {
    movimientos: vi.fn().mockResolvedValue([]),
    clasificar: vi.fn().mockResolvedValue({ categoria: 'Otros' }),
    crearMovimiento: vi.fn().mockResolvedValue({}),
    escanearFactura: vi.fn(),
    contactosGasto: vi.fn().mockResolvedValue([{ id: 'k1', nombre: 'Ana Gómez', telefono: '3001234567' }]),
    gruposGasto: vi.fn().mockResolvedValue([]),
    crearContactoGasto: vi.fn(),
    calcularDivision: vi.fn().mockResolvedValue({ partes: { yo: 50000, k1: 50000 } }),
    crearGastoCompartido: vi.fn().mockResolvedValue({ id: 'g1' }),
    saldosGasto: vi.fn().mockResolvedValue(SALDOS),
    gastosCompartidos: vi.fn().mockResolvedValue([]),
    registrarPagoGasto: vi.fn().mockResolvedValue({ id: 'p1' }),
    eliminarGastoCompartido: vi.fn(),
  })
})

describe('WhatsApp', () => {
  it('normaliza el celular colombiano y arma un mensaje amable con pesos', () => {
    expect(telefonoParaWhatsApp('300 123 4567')).toBe('573001234567')
    expect(telefonoParaWhatsApp('+57 300 123 4567')).toBe('573001234567')
    expect(telefonoParaWhatsApp('12345')).toBe('')
    const url = enlaceCobroWhatsApp({ nombre: 'Ana Gómez', telefono: '3001234567', monto: 50000, descripcion: 'Cena' })
    expect(url.startsWith('https://wa.me/573001234567?text=')).toBe(true)
    const texto = decodeURIComponent(url.split('text=')[1])
    expect(texto).toContain('Hola Ana')
    expect(texto).toMatch(/\$\s?50\.000/)
    expect(texto).toContain('"Cena"')
  })
})

describe('Foto de factura en Agregar', () => {
  const foto = () => new File(['x'], 'f.jpg', { type: 'image/jpeg' })

  it('rellena el formulario pero NO guarda por sí sola', async () => {
    imagen.prepararImagen.mockResolvedValue({ base64: 'AAAA', mime: 'image/jpeg' })
    api.escanearFactura.mockResolvedValue({
      comercio: 'Restaurante El Cielo', fecha: '2026-09-20', total: 145900, impuestos: 13264, propina: 10000,
      moneda: 'COP', categoria: 'Comida',
    })
    montar()
    fireEvent.change(screen.getByLabelText('Tomar foto de factura'), { target: { files: [foto()] } })
    expect(await screen.findByText('Revisa los datos antes de guardar')).toBeInTheDocument()
    expect(api.escanearFactura).toHaveBeenCalledWith('AAAA', 'image/jpeg')
    expect(screen.getByPlaceholderText('0')).toHaveValue('145.900')
    expect(screen.getByPlaceholderText(/¿En qué fue/)).toHaveValue('Restaurante El Cielo')
    expect(screen.getByText(/Propina/)).toBeInTheDocument()
    expect(api.crearMovimiento).not.toHaveBeenCalled()
    await userEvent.click(screen.getByText('Guardar movimiento'))
    await waitFor(() =>
      expect(api.crearMovimiento).toHaveBeenCalledWith(
        expect.objectContaining({ monto: 145900, descripcion: 'Restaurante El Cielo', categoria: 'Comida' })
      )
    )
  })

  it('muestra el mensaje claro cuando la foto no sirve y deja escribir a mano', async () => {
    imagen.prepararImagen.mockResolvedValue({ base64: 'AAAA', mime: 'image/jpeg' })
    api.escanearFactura.mockRejectedValue(new Error('La foto no se ve clara. Intenta con más luz.'))
    montar()
    fireEvent.change(screen.getByLabelText('Elegir factura de la galería'), { target: { files: [foto()] } })
    expect(await screen.findByRole('alert')).toHaveTextContent('no se ve clara')
    expect(screen.getByPlaceholderText('0')).toHaveValue('')
  })

  it('avisa si la imagen no se puede preparar (sin llamar a la IA)', async () => {
    imagen.prepararImagen.mockRejectedValue(new Error('Esa foto es muy pesada.'))
    montar()
    fireEvent.change(screen.getByLabelText('Tomar foto de factura'), { target: { files: [foto()] } })
    expect(await screen.findByRole('alert')).toHaveTextContent('muy pesada')
    expect(api.escanearFactura).not.toHaveBeenCalled()
  })
})

describe('Dividir gasto', () => {
  it('desde Agregar exige un monto y lleva a Dividir con los datos', async () => {
    montar()
    await userEvent.click(screen.getByText('Dividir'))
    expect(await screen.findByText(/escribe cuánto fue, arriba/i)).toBeInTheDocument()
    await userEvent.type(screen.getByPlaceholderText('0'), '100000')
    await userEvent.click(screen.getByText('Dividir'))
    expect(await screen.findByText('Dividir gasto')).toBeInTheDocument()
    expect(screen.getByLabelText('Total')).toHaveValue('100.000')
  })

  it('divide en partes iguales y guarda mostrando la parte propia', async () => {
    montar('/dividir', { monto: 100000, descripcion: 'Cena', cuentaId: 'c1' })
    await userEvent.click(await screen.findByRole('button', { name: 'Ana Gómez' }))
    await waitFor(() => expect(api.calcularDivision).toHaveBeenLastCalledWith(
      expect.objectContaining({ total: 100000, modo: 'iguales', participantes: [{ id: 'yo', valor: 0 }, { id: 'k1', valor: 0 }] })
    ))
    expect(await screen.findByText(/Mi gasto:\s*\$\s?50\.000/)).toBeInTheDocument()
    await userEvent.click(screen.getByText('Guardar gasto dividido'))
    await waitFor(() =>
      expect(api.crearGastoCompartido).toHaveBeenCalledWith(
        expect.objectContaining({ total: 100000, modo: 'iguales', pagador_id: 'yo', registro: 'mi_parte', cuenta_id: 'c1' })
      )
    )
    // La navegación ocurre después de que responde la API: se espera, no se comprueba una sola vez.
    await waitFor(() => expect(screen.getByTestId('ruta')).toHaveTextContent('/amigos'))
  })

  it('muestra el error del servidor si los porcentajes no suman 100 y no guarda', async () => {
    api.calcularDivision.mockRejectedValue(new Error('Los porcentajes deben sumar 100 (suman 70)'))
    montar('/dividir', { monto: 100000, descripcion: 'Cena', cuentaId: 'c1' })
    await userEvent.click(await screen.findByRole('button', { name: 'Ana Gómez' }))
    await userEvent.click(screen.getByRole('button', { name: '%' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('deben sumar 100')
    await userEvent.click(screen.getByText('Guardar gasto dividido'))
    expect(api.crearGastoCompartido).not.toHaveBeenCalled()
  })

  it('permite registrar el total pagado', async () => {
    montar('/dividir', { monto: 100000, descripcion: 'Cena', cuentaId: 'c1' })
    await userEvent.click(await screen.findByRole('button', { name: 'Ana Gómez' }))
    await userEvent.click(screen.getByText('Registrar el total que pagué'))
    await userEvent.click(screen.getByText('Guardar gasto dividido'))
    await waitFor(() => expect(api.crearGastoCompartido).toHaveBeenCalledWith(expect.objectContaining({ registro: 'total' })))
  })
})

describe('Cuentas con amigos', () => {
  it('muestra el saldo, el enlace de WhatsApp y registra un pago', async () => {
    montar('/amigos')
    expect(await screen.findByText('Te debe')).toBeInTheDocument()
    // gramática: "Ana Gómez le paga a ti", no "a Tú"
    const fila = screen.getByText('ti', { selector: 'strong' }).closest('li')
    expect(fila.textContent).toContain('Ana Gómez le paga a ti')
    const enlace = screen.getByRole('link', { name: /Cobrar por WhatsApp/ })
    expect(enlace.getAttribute('href')).toContain('https://wa.me/573001234567?text=')
    await userEvent.click(screen.getByText('Me pagó'))
    await userEvent.click(await screen.findByText('Sí, registrar'))
    await waitFor(() =>
      expect(api.registrarPagoGasto).toHaveBeenCalledWith(
        expect.objectContaining({ de_id: 'k1', a_id: 'yo', monto: 50000, moneda: 'COP' })
      )
    )
  })

  it('muestra un estado vacío claro', async () => {
    api.saldosGasto.mockResolvedValue({ monedas: [] })
    montar('/amigos')
    expect(await screen.findByText('Aún no hay cuentas con amigos')).toBeInTheDocument()
  })
})
