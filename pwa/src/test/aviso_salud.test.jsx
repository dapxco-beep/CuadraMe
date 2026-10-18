// «Revisé tu cuenta y encontré N cosas»: un solo banner, se oculta con 0, cada hallazgo con su acción de un toque.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Nu Colombia', tipo: 'ahorro' }], recargar: vi.fn().mockResolvedValue() }),
}))

import AvisoSalud, { textoBanner } from '../components/AvisoSalud'
import { DialogosProvider } from '../lib/DialogosContext'

const TARJETA = {
  codigo: 'tarjeta_sin_cuenta', severidad: 'importante', titulo: 'Falta tu cuenta de tarjeta Nu',
  texto: 'Llegaron 2 extractos de tu tarjeta Nu.', accion: { tipo: 'crear_cuenta_tarjeta', etiqueta: 'Crear tarjeta Nu', banco: 'Nu' },
  datos: { banco: 'Nu', cantidad: 2 },
}
const CLAVE = {
  codigo: 'clave_pdf_faltante', severidad: 'importante', titulo: 'Falta la clave de tus extractos', texto: 'Guárdala una vez.',
  accion: { tipo: 'guardar_clave', etiqueta: 'Guardar clave' }, datos: { cantidad: 1 },
}

function montar() {
  return render(
    <DialogosProvider>
      <MemoryRouter><AvisoSalud /></MemoryRouter>
    </DialogosProvider>
  )
}

beforeEach(() => {
  Object.keys(api).forEach((k) => delete api[k])
})

describe('AvisoSalud', () => {
  it('con cero hallazgos no dibuja nada', async () => {
    api.salud = vi.fn().mockResolvedValue({ total: 0, hallazgos: [] })
    const { container } = montar()
    await waitFor(() => expect(api.salud).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('si el servidor falla no molesta con nada', async () => {
    api.salud = vi.fn().mockRejectedValue(new Error('x'))
    const { container } = montar()
    await waitFor(() => expect(api.salud).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('texto en singular y plural', () => {
    expect(textoBanner(1)).toBe('Revisé tu cuenta y encontré una cosa')
    expect(textoBanner(3)).toBe('Revisé tu cuenta y encontré 3 cosas')
  })

  it('muestra UN banner con el conteo y abre la lista', async () => {
    api.salud = vi.fn().mockResolvedValue({ total: 2, hallazgos: [TARJETA, CLAVE] })
    montar()
    const banner = await screen.findByTestId('aviso-salud')
    expect(banner).toHaveTextContent('Revisé tu cuenta y encontré 2 cosas')
    expect(screen.getAllByTestId('aviso-salud')).toHaveLength(1)
    await userEvent.click(banner)
    expect(await screen.findByText('Falta tu cuenta de tarjeta Nu')).toBeInTheDocument()
    expect(screen.getByText('Falta la clave de tus extractos')).toBeInTheDocument()
  })

  it('«Crear tarjeta» crea la cuenta en un toque y vuelve a revisar', async () => {
    api.salud = vi.fn().mockResolvedValueOnce({ total: 1, hallazgos: [TARJETA] }).mockResolvedValue({ total: 0, hallazgos: [] })
    api.saludCrearTarjeta = vi.fn().mockResolvedValue({ ok: true, nombre: 'Nu Tarjeta', reasignados: 2 })
    montar()
    await userEvent.click(await screen.findByTestId('aviso-salud'))
    await userEvent.click(await screen.findByText('Crear tarjeta Nu'))
    await waitFor(() => expect(api.saludCrearTarjeta).toHaveBeenCalledWith('Nu'))
    await waitFor(() => expect(api.salud).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('Todo en orden')).toBeInTheDocument()
  })
})
