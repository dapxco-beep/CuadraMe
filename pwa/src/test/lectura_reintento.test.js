import { describe, expect, it, vi } from 'vitest'
import { leerConReintento } from '../lib/sincronizarGmail'

describe('leerConReintento', () => {
  it('reintenta una vez y, si la segunda sale bien, no hay error', async () => {
    const leer = vi.fn().mockRejectedValueOnce(new Error('cayó')).mockResolvedValueOnce({ ok: true, leidos: 3 })
    const r = await leerConReintento(leer, 0)
    expect(leer).toHaveBeenCalledTimes(2)
    expect(r.r.leidos).toBe(3)
  })
  it('si persiste, devuelve el error tras exactamente 2 intentos', async () => {
    const leer = vi.fn().mockResolvedValue({ ok: false, error: 'Gmail no responde' })
    const r = await leerConReintento(leer, 0)
    expect(leer).toHaveBeenCalledTimes(2)
    expect(r.error).toBe('Gmail no responde')
  })
  it('a la primera no reintenta', async () => {
    const leer = vi.fn().mockResolvedValue({ ok: true })
    await leerConReintento(leer, 0)
    expect(leer).toHaveBeenCalledTimes(1)
  })
})
