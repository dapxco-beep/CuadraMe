import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  conexionesEstado: vi.fn(),
  estadoNotificaciones: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/push', () => ({ pushSoportado: () => false, estadoPermiso: async () => 'default', activarPush: vi.fn() }))

import Conexiones from '../screens/Conexiones'
import { ATAJO_NOTIFICACIONES_URL } from '../screens/ConectarDispositivo'
import { DialogosProvider } from '../lib/DialogosContext'

const ESTADO = {
  gmail: { semaforo: 'verde', mensaje: 'ok' },
  atajo: { semaforo: 'verde', mensaje: 'ok', ultimo_uso: null, movimientos_7d: 0 },
  conciliacion: { semaforo: 'verde', mensaje: 'ok', cuentas: [] },
  push: { semaforo: 'verde', mensaje: 'ok' },
}

function montar() {
  return render(
    <MemoryRouter>
      <DialogosProvider>
        <Conexiones embebido />
      </DialogosProvider>
    </MemoryRouter>
  )
}

describe('Tarjeta «Registro automático desde el banco»', () => {
  it('marca qué bancos faltan por conectar y enlaza el atajo', async () => {
    api.conexionesEstado.mockResolvedValue(ESTADO)
    api.estadoNotificaciones.mockResolvedValue([
      { cuenta_id: 'a', cuenta: 'Nequi', app: 'Nequi', ultimo_aviso: new Date().toISOString(), avisos_30d: 3 },
      { cuenta_id: 'b', cuenta: 'Nu Colombia', app: 'Nu', ultimo_aviso: null, avisos_30d: 0 },
    ])
    montar()
    const tarjeta = await screen.findByTestId('tarjeta-avisos-banco')
    expect(tarjeta).toHaveTextContent('Falta conectar: Nu')
    expect(tarjeta).toHaveTextContent(/Nequi/)
    expect(tarjeta).toHaveTextContent(/Conectado · último aviso/)
    expect(screen.getByRole('link', { name: /Instalar el atajo/ })).toHaveAttribute('href', ATAJO_NOTIFICACIONES_URL)
    expect(tarjeta.querySelector('[data-semaforo="ambar"]')).not.toBeNull()
  })

  it('con todos conectados queda en verde', async () => {
    api.conexionesEstado.mockResolvedValue(ESTADO)
    api.estadoNotificaciones.mockResolvedValue([
      { cuenta_id: 'a', cuenta: 'Nequi', app: 'Nequi', ultimo_aviso: new Date().toISOString(), avisos_30d: 1 },
    ])
    montar()
    const tarjeta = await screen.findByTestId('tarjeta-avisos-banco')
    expect(tarjeta.querySelector('[data-semaforo="verde"]')).not.toBeNull()
  })

  it('sin cuentas que el atajo sepa leer, o si el servidor falla, no muestra nada', async () => {
    api.conexionesEstado.mockResolvedValue(ESTADO)
    api.estadoNotificaciones.mockResolvedValue([])
    const { unmount } = montar()
    await screen.findByTestId('tarjeta-atajo')
    await waitFor(() => expect(api.estadoNotificaciones).toHaveBeenCalled())
    expect(screen.queryByTestId('tarjeta-avisos-banco')).toBeNull()
    unmount()
    api.estadoNotificaciones.mockRejectedValue(new Error('x'))
    montar()
    await screen.findByTestId('tarjeta-atajo')
    expect(screen.queryByTestId('tarjeta-avisos-banco')).toBeNull()
  })
})
