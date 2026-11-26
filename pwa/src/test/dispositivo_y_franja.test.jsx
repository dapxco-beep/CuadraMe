import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({ saludFinanciera: vi.fn() }))
vi.mock('../lib/api', () => ({ api }))

import GuiaInstalar from '../components/GuiaInstalar'
import CuadriEsquina from '../components/CuadriEsquina'
import { guardarCelularElegido, leerCelularElegido } from '../lib/dispositivo'
import { _olvidarSaludCuadri } from '../lib/useSaludCuadri'

afterEach(() => {
  guardarCelularElegido(null)
  _olvidarSaludCuadri()
  api.saludFinanciera.mockReset()
})

describe('«¿Qué celular usas?»', () => {
  it('lo elegido manda sobre lo detectado y se recuerda', () => {
    render(<GuiaInstalar dispositivo="android" onCerrar={() => {}} />)
    expect(screen.getByRole('list', { name: 'Pasos para Android' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: 'iPhone' }))
    expect(screen.getByRole('list', { name: 'Pasos para iPhone' })).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Pasos para Android' })).toBeNull()
    expect(leerCelularElegido()).toBe('ios')
  })

  it('nunca muestra las dos listas a la vez', () => {
    render(<GuiaInstalar dispositivo="otro" onCerrar={() => {}} />)
    expect(screen.queryAllByRole('list').length).toBe(0)
    expect(screen.getByTestId('elige-celular')).toBeInTheDocument()
  })
})

describe('Cuadri en la esquina', () => {
  it('muestra el estado según el puntaje y enlaza a «Cómo está Cuadri»', async () => {
    api.saludFinanciera.mockResolvedValue({ score: 90, componentes: [] })
    render(<MemoryRouter><CuadriEsquina /></MemoryRouter>)
    const enlace = await screen.findByRole('link', { name: /radiante/i })
    expect(enlace).toHaveAttribute('href', '/ahorcado')
    expect(enlace).toHaveTextContent('Radiante')
  })

  it('si el servidor no responde reserva el sitio pero no muestra nada raro', async () => {
    api.saludFinanciera.mockRejectedValue(new Error('x'))
    render(<MemoryRouter><CuadriEsquina /></MemoryRouter>)
    await waitFor(() => expect(api.saludFinanciera).toHaveBeenCalled())
    expect(screen.getByTestId('cuadri-esquina')).toBeInTheDocument()
    expect(screen.queryByRole('link')).toBeNull()
  })
})
