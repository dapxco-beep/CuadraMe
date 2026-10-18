// «Cambiar la cuenta de este extracto»: textos, sugerencia (solo cuando corresponde), vista previa y confirmación.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

const api = vi.hoisted(() => ({
  previaCambiarCuentaExtracto: vi.fn(),
  cambiarCuentaExtracto: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))

import CambiarCuentaExtracto from '../components/CambiarCuentaExtracto'
import ExtractosAMedias from '../components/ExtractosAMedias'
import TodosLosExtractos from '../components/TodosLosExtractos'
import { cuentasDestino, textoListo, textoPrevia, textoSugerencia } from '../lib/cambiarCuenta'
import { extractosAMedias } from '../lib/retomar'

const fmt = (n) => `$${n}`
const PREVIA = {
  movera: 3, duplicados: 0, estado: 'conciliado', ya_en_esa_cuenta: false,
  origen: { id: 'nu', nombre: 'Nu Colombia', saldo_antes: 880000, saldo_despues: 1000000 },
  destino: { id: 'tj', nombre: 'Nu Colombia Crédito', saldo_antes: -300000, saldo_despues: -420000 },
}
const CUENTAS = [
  { id: 'nu', nombre: 'Nu Colombia', tipo: 'ahorro' },
  { id: 'tj', nombre: 'Nu Colombia Crédito', tipo: 'credito' },
]

const fila = (extra) => ({
  id: 'c:1', extracto_id: 'e1', historial_id: 'h1', cuenta_id: 'nu', cuenta: 'Nu Colombia', mes: '2026-08', mes_etiqueta: 'Agosto 2026',
  titulo: 'Tarjeta Nu · Agosto 2026', tipo: 'cuenta', estado_vista: 'revisado', estado_etiqueta: 'Revisado', acciones: ['ver'],
  resultado: 'Leímos 18 movimientos.', leidas: 18, ya_estaban: 0, nuevas_agregadas: 18, por_revisar: 0, puede_cambiar_cuenta: true, ...extra,
})
const SUG = { cuenta_id: 'tj', nombre: 'Nu Colombia Crédito' }
const datos = (items) => ({ items, contadores: { revisado: items.length }, resumen: '', sin_adjunto: [] })
const SIN_FILTRO = { estados: [], cuenta: '', mes: '', texto: '' }

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('textos', () => {
  it('la vista previa dice cuántos movimientos y cómo quedan los saldos', () => {
    expect(textoPrevia(PREVIA, fmt)).toBe(
      'Moverá 3 movimientos de Nu Colombia a Nu Colombia Crédito. El saldo de Nu Colombia pasará de $880000 a $1000000 y el de Nu Colombia Crédito de $-300000 a $-420000.')
    expect(textoPrevia({ ...PREVIA, movera: 0 }, fmt)).toContain('No hay movimientos importados que mover.')
    expect(textoPrevia({ ...PREVIA, ya_en_esa_cuenta: true }, fmt)).toBe('Este extracto ya está en esa cuenta.')
    expect(textoPrevia({ ...PREVIA, movera: 2, duplicados: 1 }, fmt)).toContain('1 movimiento ya estaba en Nu Colombia Crédito: no se repite.')
  })

  it('textoListo e idempotencia', () => {
    expect(textoListo({ movidos: 3, destino: { nombre: 'Tarjeta' } })).toBe('Listo: pasamos 3 movimientos a Tarjeta.')
    expect(textoListo({ movidos: 0, destino: { nombre: 'Tarjeta' } })).toBe('Listo: el extracto ahora es de Tarjeta.')
    expect(textoListo({ sin_cambios: true })).toBe('Ese extracto ya estaba en esa cuenta.')
  })

  it('cuentasDestino quita la cuenta actual', () => {
    expect(cuentasDestino(CUENTAS, 'nu').map((c) => c.id)).toEqual(['tj'])
  })
})

describe('sugerencia', () => {
  it('solo aparece cuando el servidor la manda y se puede cambiar', () => {
    expect(textoSugerencia(fila({ sugerencia_cuenta: SUG }))).toBe('Parece de tu tarjeta de crédito. ¿Pasarlo a Nu Colombia Crédito?')
    expect(textoSugerencia(fila({ sugerencia_cuenta: null }))).toBe('')
    expect(textoSugerencia(fila({ sugerencia_cuenta: SUG, puede_cambiar_cuenta: false }))).toBe('')
  })

  it('la fila de «Todos los extractos» muestra la sugerencia con su botón y el acceso manual', () => {
    const onAccion = vi.fn()
    render(<TodosLosExtractos datos={datos([fila({ sugerencia_cuenta: SUG })])} filtro={SIN_FILTRO} onFiltro={vi.fn()} onAccion={onAccion} onFijarMes={vi.fn()} />)
    expect(screen.getByText('Parece de tu tarjeta de crédito. ¿Pasarlo a Nu Colombia Crédito?')).toBeTruthy()
    fireEvent.click(screen.getByLabelText('Pasar a Nu Colombia Crédito: Tarjeta Nu · Agosto 2026'))
    expect(onAccion).toHaveBeenCalledWith('cambiar_cuenta', expect.objectContaining({ historial_id: 'h1' }), 'tj')
    fireEvent.click(screen.getByLabelText('Cambiar de cuenta: Tarjeta Nu · Agosto 2026'))
    expect(onAccion).toHaveBeenLastCalledWith('cambiar_cuenta', expect.objectContaining({ historial_id: 'h1' }))
  })

  it('sin sugerencia no hay aviso, pero el acceso manual sigue; sin permiso no hay ninguno', () => {
    const { rerender } = render(<TodosLosExtractos datos={datos([fila({ sugerencia_cuenta: null })])} filtro={SIN_FILTRO} onFiltro={vi.fn()} onAccion={vi.fn()} onFijarMes={vi.fn()} />)
    expect(screen.queryByTestId('sugerencia-cuenta')).toBeNull()
    expect(screen.getByLabelText('Cambiar de cuenta: Tarjeta Nu · Agosto 2026')).toBeTruthy()
    rerender(<TodosLosExtractos datos={datos([fila({ puede_cambiar_cuenta: false })])} filtro={SIN_FILTRO} onFiltro={vi.fn()} onAccion={vi.fn()} onFijarMes={vi.fn()} />)
    expect(screen.queryByLabelText(/^Cambiar de cuenta/)).toBeNull()
  })

  it('en los extractos a medias también se sugiere', () => {
    const lista = extractosAMedias({ todos_extractos: { items: [fila({ estado_vista: 'por_revisar', por_revisar: 1, sugerencia_cuenta: SUG })] } })
    const onCambiarCuenta = vi.fn()
    render(<ExtractosAMedias lista={lista} onSeguir={vi.fn()} onCambiarCuenta={onCambiarCuenta} />)
    fireEvent.click(screen.getByText('Pasarlo a Nu Colombia Crédito'))
    expect(onCambiarCuenta).toHaveBeenCalledWith(expect.objectContaining({ historialId: 'h1' }), 'tj')
  })
})

describe('hoja «Cambiar de cuenta»', () => {
  it('con la sugerencia abre la vista previa y confirma; nada cambia antes de confirmar', async () => {
    api.previaCambiarCuentaExtracto.mockResolvedValue(PREVIA)
    api.cambiarCuentaExtracto.mockResolvedValue({ ok: true, movidos: 3, destino: { nombre: 'Nu Colombia Crédito' } })
    const onListo = vi.fn()
    render(<CambiarCuentaExtracto historialId="h1" titulo="Agosto" cuentaActualId="nu" cuentas={CUENTAS} destinoInicial="tj" onCerrar={vi.fn()} onListo={onListo} />)
    await waitFor(() => expect(screen.getByTestId('previa-cambio').textContent).toContain('Moverá 3 movimientos'))
    expect(api.previaCambiarCuentaExtracto).toHaveBeenCalledWith('h1', 'tj')
    expect(api.cambiarCuentaExtracto).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('Sí, cambiar de cuenta'))
    await waitFor(() => expect(onListo).toHaveBeenCalledWith('Listo: pasamos 3 movimientos a Nu Colombia Crédito.', expect.anything()))
    expect(api.cambiarCuentaExtracto).toHaveBeenCalledWith('h1', 'tj')
  })

  it('manual: hasta elegir la cuenta no hay vista previa y el botón está apagado', async () => {
    api.previaCambiarCuentaExtracto.mockResolvedValue(PREVIA)
    render(<CambiarCuentaExtracto historialId="h1" cuentaActualId="nu" cuentas={CUENTAS} onCerrar={vi.fn()} />)
    expect(api.previaCambiarCuentaExtracto).not.toHaveBeenCalled()
    expect(screen.getByText('Sí, cambiar de cuenta').disabled).toBe(true)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'tj' } })
    await waitFor(() => expect(screen.getByTestId('previa-cambio')).toBeTruthy())
    expect(screen.getByText('Sí, cambiar de cuenta').disabled).toBe(false)
  })
})
