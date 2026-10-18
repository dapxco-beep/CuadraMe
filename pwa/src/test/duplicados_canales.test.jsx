// Duplicados entre canales: insignia «Registrado desde», aviso «ya lo tienes» al registrar a mano,
// «X correos ya estaban registrados» con «Mostrar de todos modos» y la herramienta «Buscar repetidos».
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [{ id: 'c1', nombre: 'Bancolombia', saldo: 1500000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn().mockResolvedValue() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({
    categorias: [], nombres: ['Mercado', 'Otros'], cargando: false, recargar: vi.fn(), iconoDe: () => '💳',
  }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import Agregar from '../screens/Agregar'
import BuscarDuplicados from '../screens/BuscarDuplicados'
import DetalleMovimiento from '../screens/DetalleMovimiento'
import CorreosYaRegistrados from '../components/CorreosYaRegistrados'
import InsigniaCanales from '../components/InsigniaCanales'
import { fraseCanales, textoCanales } from '../lib/canales'

function montar(ui, ruta = '/') {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter initialEntries={[ruta]}>{ui}</MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.keys(api).forEach((k) => delete api[k])
})

describe('textos de canales', () => {
  it('une los canales en orden y en español llano', () => {
    expect(textoCanales(['extracto', 'atajo', 'correo'])).toBe('atajo + correo + extracto')
    expect(textoCanales(['manual'])).toBe('app')
    expect(textoCanales(null)).toBe('')
    expect(textoCanales(['raro'])).toBe('')
    expect(fraseCanales(['atajo', 'correo'])).toBe('el atajo y el correo del banco')
    expect(fraseCanales(['atajo', 'correo', 'extracto'])).toBe('el atajo, el correo del banco y el extracto')
    expect(fraseCanales([])).toBe('')
  })
})

describe('insignia «Registrado desde»', () => {
  it('muestra cada canal que confirmó el movimiento', () => {
    render(<InsigniaCanales canales={['atajo', 'correo', 'extracto']} />)
    expect(screen.getByText('Registrado desde: atajo + correo + extracto')).toBeInTheDocument()
    expect(screen.getByText(/Varios canales avisaron/)).toBeInTheDocument()
  })

  it('no dibuja nada en movimientos viejos sin canales', () => {
    const { container } = render(<InsigniaCanales canales={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('aparece en el detalle del movimiento', async () => {
    const mov = {
      id: 'm1', cuenta_id: 'c1', fecha: '2026-10-02T12:00:00', descripcion: 'Netflix', categoria: 'Mercado', tipo: 'expense',
      monto: 33000, fuente: 'wallet', notas: '', canales: ['atajo', 'correo'],
    }
    Object.assign(api, { movimiento: vi.fn().mockResolvedValue(mov) })
    montar(
      <Routes>
        <Route path="/movimientos/:id" element={<DetalleMovimiento />} />
      </Routes>,
      '/movimientos/m1'
    )
    expect(await screen.findByText('Registrado desde: atajo + correo')).toBeInTheDocument()
  })
})

describe('registrar a mano algo que ya está', () => {
  it('avisa «ya lo tienes» y deja elegir «es otro gasto igual»', async () => {
    api.crearMovimiento = vi
      .fn()
      .mockRejectedValueOnce(Object.assign(new Error('Ya tienes este gasto registrado desde el atajo'), {
        status: 409,
        detalle: { codigo: 'posible_duplicado', mensaje: 'Ya tienes este gasto registrado desde el atajo: «Netflix». ¿Es otro igual o es el mismo?' },
      }))
      .mockResolvedValueOnce({})
    api.clasificar = vi.fn().mockResolvedValue({ categoria: 'Otros' })
    api.movimientos = vi.fn().mockResolvedValue([])
    montar(<Agregar />)
    await userEvent.type(screen.getByPlaceholderText('0'), '33000')
    await userEvent.type(screen.getByPlaceholderText(/¿En qué fue/), 'Netflix')
    await userEvent.click(screen.getByText('Guardar movimiento'))
    const aviso = await screen.findByTestId('posible-duplicado')
    expect(aviso).toHaveTextContent('Ya tienes este gasto registrado desde el atajo')
    expect(api.crearMovimiento.mock.calls[0][0].confirmar_nuevo).toBeUndefined()
    await userEvent.click(screen.getByText('Es otro gasto igual, agrégalo'))
    await waitFor(() => expect(api.crearMovimiento).toHaveBeenCalledTimes(2))
    expect(api.crearMovimiento.mock.calls[1][0]).toEqual(expect.objectContaining({ confirmar_nuevo: true, monto: 33000 }))
  })
})

describe('correos que ya estaban registrados', () => {
  const YA = [{
    id: 'k1', comercio: 'Compra en Netflix', monto: 33000,
    registrado_como: { descripcion: 'Netflix', monto: 33000, canales: ['atajo', 'correo'] },
  }]

  it('no dibuja nada si no hay', () => {
    const { container } = render(<CorreosYaRegistrados cantidad={0} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('dice cuántos no se muestran y los lista al abrir', async () => {
    api.correosYaRegistrados = vi.fn().mockResolvedValue(YA)
    render(<CorreosYaRegistrados cantidad={3} />)
    expect(screen.getByText('3 correos ya estaban registrados')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /correos ya estaban registrados/ }))
    expect(await screen.findByText(/Ya lo tenías: «Netflix», registrado desde el atajo y el correo del banco/)).toBeInTheDocument()
  })

  it('«Mostrar de todos modos» devuelve el correo a «Por revisar»', async () => {
    api.correosYaRegistrados = vi.fn().mockResolvedValue(YA)
    api.correoNoEsDuplicado = vi.fn().mockResolvedValue({})
    const onCambio = vi.fn()
    render(<CorreosYaRegistrados cantidad={1} onCambio={onCambio} />)
    expect(screen.getByText('1 correo ya estaba registrado')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /correo ya estaba registrado/ }))
    await userEvent.click(await screen.findByText(/Mostrar de todos modos/))
    await waitFor(() => expect(api.correoNoEsDuplicado).toHaveBeenCalledWith('k1'))
    expect(onCambio).toHaveBeenCalled()
    expect(screen.queryByTestId('ya-registrado-k1')).toBeNull()
  })

  it('si falla muestra el mensaje y deja el correo', async () => {
    api.correosYaRegistrados = vi.fn().mockResolvedValue(YA)
    api.correoNoEsDuplicado = vi.fn().mockRejectedValue(new Error('Sin conexión'))
    render(<CorreosYaRegistrados cantidad={1} />)
    await userEvent.click(screen.getByRole('button', { name: /correo ya estaba registrado/ }))
    await userEvent.click(await screen.findByText(/Mostrar de todos modos/))
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión')
    expect(screen.getByTestId('ya-registrado-k1')).toBeInTheDocument()
  })
})

describe('Buscar movimientos repetidos', () => {
  const GRUPO = {
    id: 'g1',
    sugerido_conservar: 'b',
    movimientos: [
      { id: 'a', fecha: '2026-10-02T10:00:00', descripcion: 'Exito', monto: 45000, cuenta_id: 'c1', cuenta_nombre: 'Bancolombia', origen: 'manual', conciliado: false },
      { id: 'b', fecha: '2026-10-02T10:02:00', descripcion: 'EXITO', monto: 45000, cuenta_id: 'c1', cuenta_nombre: 'Bancolombia', origen: 'atajo', conciliado: true },
    ],
  }

  it('sin repetidos lo dice con calma', async () => {
    api.buscarDuplicados = vi.fn().mockResolvedValue({ grupos: [], total: 0 })
    montar(<BuscarDuplicados />)
    expect(await screen.findByTestId('sin-duplicados')).toHaveTextContent('No encontré movimientos repetidos')
  })

  it('propone conservar el sugerido, deja cambiar y une sin borrar nada solo', async () => {
    api.buscarDuplicados = vi.fn().mockResolvedValue({ grupos: [GRUPO], total: 1 })
    api.unirDuplicados = vi.fn().mockResolvedValue({ ok: true })
    montar(<BuscarDuplicados />)
    expect(await screen.findByText(/anotado 2 veces/)).toBeInTheDocument()
    expect(screen.getByLabelText('Conservar EXITO')).toBeChecked() // el sugerido (cruzado con el banco)
    await userEvent.click(screen.getByLabelText('Conservar Exito'))
    expect(api.unirDuplicados).not.toHaveBeenCalled() // elegir no borra
    await userEvent.click(screen.getByText('Unir en uno solo'))
    await userEvent.click(await screen.findByRole('button', { name: 'Unir' })) // confirmación
    await waitFor(() => expect(api.unirDuplicados).toHaveBeenCalledWith('a', ['b']))
    expect(await screen.findByTestId('sin-duplicados')).toBeInTheDocument()
  })

  it('«No es duplicado» saca el grupo y lo recuerda', async () => {
    api.buscarDuplicados = vi.fn().mockResolvedValue({ grupos: [GRUPO], total: 1 })
    api.noEsDuplicado = vi.fn().mockResolvedValue({ ok: true })
    montar(<BuscarDuplicados />)
    await userEvent.click(await screen.findByText(/No es duplicado/))
    await waitFor(() => expect(api.noEsDuplicado).toHaveBeenCalledWith(['a', 'b']))
    expect(await screen.findByTestId('sin-duplicados')).toBeInTheDocument()
  })

  it('si falla la búsqueda muestra un mensaje claro', async () => {
    api.buscarDuplicados = vi.fn().mockRejectedValue(new Error('Sin conexión'))
    montar(<BuscarDuplicados />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión')
  })
})

describe('borrar lo que vino del correo o de un extracto: «¿Qué pasó?»', () => {
  const base = { id: 'm1', cuenta_id: 'c1', fecha: '2026-10-02T12:00:00', descripcion: 'Netflix', categoria: 'Mercado', tipo: 'expense', monto: 33000, notas: '' }

  async function abrir(mov) {
    Object.assign(api, {
      movimiento: vi.fn().mockResolvedValue(mov),
      eliminarMovimiento: vi.fn().mockResolvedValue({ ok: true }),
    })
    montar(
      <Routes>
        <Route path="/movimientos/:id" element={<DetalleMovimiento />} />
        <Route path="/movimientos" element={<p>lista</p>} />
      </Routes>,
      '/movimientos/m1'
    )
    await userEvent.click(await screen.findByText('Eliminar movimiento'))
  }

  it('pregunta una sola vez con tres botones y manda el motivo elegido', async () => {
    await abrir({ ...base, fuente: 'wallet', origen: 'correo', canales: ['correo'] })
    expect(await screen.findByText('¿Qué pasó?')).toBeInTheDocument()
    expect(screen.getByText('Era duplicado')).toBeInTheDocument()
    expect(screen.getByText('No va en mi cuenta')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Lo borré por error'))
    await waitFor(() => expect(api.eliminarMovimiento).toHaveBeenCalledWith('m1', 'error'))
  })

  it('cancelar no borra nada', async () => {
    await abrir({ ...base, fuente: 'wallet', origen: 'extracto', canales: ['extracto'] })
    await userEvent.click(await screen.findByText('Cancelar'))
    expect(api.eliminarMovimiento).not.toHaveBeenCalled()
  })

  it('un movimiento hecho a mano sigue con la confirmación de siempre (sin pregunta extra)', async () => {
    await abrir({ ...base, fuente: 'manual', origen: 'manual', canales: ['manual'] })
    expect(screen.queryByText('¿Qué pasó?')).toBeNull()
    await userEvent.click(await screen.findByText('Eliminar', { selector: 'button' }))
    await waitFor(() => expect(api.eliminarMovimiento).toHaveBeenCalledWith('m1'))
  })
})
