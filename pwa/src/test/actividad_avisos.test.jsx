// «Actividad reciente» de Salud del negocio: lista, contadores, filtro, registros por día y preferencias.
// Datos sintéticos; la API y el push se reemplazan.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'

const api = vi.hoisted(() => ({
  actividadAvisos: vi.fn(),
  preferenciasAvisos: vi.fn(),
  guardarPreferenciasAvisos: vi.fn(),
  probarAvisos: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
const push = vi.hoisted(() => ({ activarPush: vi.fn(), pushSoportado: vi.fn(() => true) }))
vi.mock('../lib/push', () => push)

import ActividadAvisos from '../components/ActividadAvisos'

const TIPOS = [
  { id: 'nuevo_registro', etiqueta: 'Nuevo registro' },
  { id: 'gmail_conectado', etiqueta: 'Gmail conectado' },
]
const ITEMS = [
  { id: 'e1', tipo: 'nuevo_registro', etiqueta: 'Nuevo registro', resumen: 'd***@gmail.com se registró en CuadraMe',
    email: 'daniela@gmail.com', creado_en: '2026-10-10T14:00:00', aviso: 'enviado' },
  { id: 'e2', tipo: 'gmail_conectado', etiqueta: 'Gmail conectado', resumen: 'm***@test.com conectó su Gmail',
    email: 'mario@test.com', creado_en: '2026-10-10T15:00:00', aviso: 'silenciado' },
]
const respuesta = (items = ITEMS) => ({
  items, total: items.length, pagina: 1, por_pagina: 30, tipos: TIPOS,
  contadores: { total_hoy: 2, total_7d: 5, por_tipo: { nuevo_registro: { hoy: 1, dias7: 3 }, gmail_conectado: { hoy: 1, dias7: 2 } } },
  registros_por_dia: Array.from({ length: 30 }, (_, i) => ({ dia: `2026-09-${String((i % 30) + 1).padStart(2, '0')}`, registros: i === 29 ? 3 : 0 })),
})
const PREFS = {
  tipos: [
    { id: 'nuevo_registro', etiqueta: 'Nuevo registro', push: true, correo: true },
    { id: 'gmail_conectado', etiqueta: 'Gmail conectado', push: true, correo: false },
  ],
  silenciado_hasta: null, resumen_diario: false, max_por_hora: 20,
  canales: { push_activo: false, correo_configurado: true, correo_error: 'Resend rechazó el correo. Define RESEND_FROM.' },
}

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  push.activarPush.mockReset()
  api.actividadAvisos.mockResolvedValue(respuesta())
  api.preferenciasAvisos.mockResolvedValue(PREFS)
  api.guardarPreferenciasAvisos.mockResolvedValue({ ...PREFS, resumen_diario: true })
})

describe('Actividad reciente', () => {
  it('muestra contadores, registros por día y la lista con el correo completo (solo admin)', async () => {
    render(<ActividadAvisos />)
    expect(await screen.findByTestId('actividad-hoy')).toHaveTextContent('2')
    expect(screen.getByTestId('actividad-7d')).toHaveTextContent('5')
    const lista = screen.getByTestId('actividad-lista')
    expect(within(lista).getByText('d***@gmail.com se registró en CuadraMe')).toBeInTheDocument()
    expect(within(lista).getByText('daniela@gmail.com')).toBeInTheDocument()
    expect(within(lista).getByText(/No se avisó \(silencio\)/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Registros por día en los últimos 30 días: 3 en total/ })).toBeInTheDocument()
  })

  it('filtra por tipo pidiéndolo al servidor', async () => {
    render(<ActividadAvisos />)
    await screen.findByTestId('actividad-lista')
    api.actividadAvisos.mockResolvedValue(respuesta([ITEMS[1]]))
    fireEvent.change(screen.getByLabelText('Filtrar por tipo'), { target: { value: 'gmail_conectado' } })
    await waitFor(() => expect(api.actividadAvisos).toHaveBeenLastCalledWith({ tipo: 'gmail_conectado', por_pagina: 30 }))
    await waitFor(() => expect(screen.queryByText('daniela@gmail.com')).toBeNull())
  })

  it('sin actividad dice qué esperar, sin inventar datos', async () => {
    api.actividadAvisos.mockResolvedValue(respuesta([]))
    render(<ActividadAvisos />)
    expect(await screen.findByTestId('actividad-vacia')).toHaveTextContent('Todavía no hay actividad')
  })

  it('si el servidor falla, no muestra nada (el resto del panel sigue)', async () => {
    api.actividadAvisos.mockRejectedValue(new Error('x'))
    const { container } = render(<ActividadAvisos />)
    await waitFor(() => expect(screen.queryByText('Cargando actividad…')).toBeNull())
    expect(container).toBeEmptyDOMElement()
  })
})

describe('Preferencias de avisos', () => {
  const abrir = async () => {
    render(<ActividadAvisos />)
    fireEvent.click(await screen.findByRole('button', { name: /Qué te avisa y cuándo/ }))
    return screen.findByTestId('preferencias-avisos')
  }

  it('muestra el estado de los canales y el motivo si el correo no llega', async () => {
    await abrir()
    expect(screen.getByTestId('canal-push')).toHaveTextContent('sin activar')
    expect(screen.getByTestId('error-correo')).toHaveTextContent('RESEND_FROM')
  })

  it('apagar un tipo guarda solo ese cambio', async () => {
    await abrir()
    const fila = screen.getByTestId('pref-gmail_conectado')
    fireEvent.click(within(fila).getByRole('switch', { name: /Gmail conectado: avisar al celular/ }))
    await waitFor(() =>
      expect(api.guardarPreferenciasAvisos).toHaveBeenCalledWith({ tipos: { gmail_conectado: { push: false, correo: false } } }),
    )
  })

  it('resumen diario y silencio por horas', async () => {
    await abrir()
    fireEvent.click(screen.getByRole('switch', { name: /Resumen diario/ }))
    await waitFor(() => expect(api.guardarPreferenciasAvisos).toHaveBeenCalledWith({ resumen_diario: true }))
    fireEvent.click(screen.getByRole('button', { name: '8 horas' }))
    await waitFor(() => expect(api.guardarPreferenciasAvisos).toHaveBeenCalledWith({ silenciar_horas: 8 }))
  })

  it('el aviso de prueba cuenta qué canal funcionó', async () => {
    api.probarAvisos.mockResolvedValue({ ok: true, push: 0, correo: true })
    await abrir()
    fireEvent.click(screen.getByRole('button', { name: 'Enviar aviso de prueba' }))
    expect(await screen.findByRole('status')).toHaveTextContent('No hay celular con avisos activados. Salió el correo.')
  })

  it('activar en este celular usa la suscripción push existente', async () => {
    push.activarPush.mockResolvedValue(true)
    await abrir()
    fireEvent.click(screen.getByRole('button', { name: 'Activar en este celular' }))
    await waitFor(() => expect(push.activarPush).toHaveBeenCalled())
  })
})
