// Cuadre con el banco: textos, advertencias y confirmaciones. Datos inventados.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  cuadreEvaluar: vi.fn(), cuadreQueFalta: vi.fn(), cuadreAjuste: vi.fn(), cuadreSaldoInicial: vi.fn(),
  cuadreSaldos: vi.fn(), cuadreDeshacer: vi.fn(), cuadreCuenta: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))

import CuadreExtracto from '../components/CuadreExtracto'
import CuadreMes, { TarjetaCuadreBanco } from '../components/CuadreMes'
import { cuerpoEvaluar, lineasPorImportar, textoEstadoMes } from '../lib/cuadreExtracto'

const montar = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>)
const base = { cuenta_id: 'c1', orientacion: 'Orientación: el saldo oficial es el de tu banco.', moneda_cuenta: 'COP', tipo_cuenta: 'ahorro', causas: [], advertencias: [], acciones: {} }
const dif = (extra = {}) => ({
  ...base, estado: 'diferencia', diferencia: -50000, saldo_extracto: 1800000, saldo_libro: 1850000, fecha_corte: '2026-09-30',
  texto: 'Diferencia de $50.000: el banco dice $1.800.000 y tus movimientos suman $1.850.000.',
  causas: [{ codigo: 'falta_movimiento', probable: false, texto: 'Puede faltar un gasto o cobro.' }],
  acciones: { ver_que_falta: true, dejar_asi: true, ajuste: { permitido: true, monto: -50000, grande: false, nota: 'Ajuste para cuadrar con el extracto del 30 sep 2026' } },
  ...extra,
})

beforeEach(() => Object.values(api).forEach((f) => f.mockReset()))

describe('ayudas puras', () => {
  it('cuentan como por importar solo las líneas nuevas marcadas', () => {
    const items = [{ k: 'a', estado: 'nuevo', fecha: '2026-09-01', monto: 5, tipo: 'expense' }, { k: 'b', estado: 'ya' }, { k: 'c', estado: 'nuevo', fecha: '2026-09-02', monto: 6, tipo: 'income' }]
    expect(lineasPorImportar(items, new Set(['x:a', 'x:b']), 'x')).toEqual([{ fecha: '2026-09-01', monto: 5, tipo: 'expense' }])
  })
  it('en PDF el servidor usa el historial; en Excel viajan los saldos leídos o escritos', () => {
    expect(cuerpoEvaluar({ cuentaId: 'c1', historialId: 'h1', saldos: { saldo_final: 9 } })).toMatchObject({ historial_id: 'h1' })
    expect(cuerpoEvaluar({ cuentaId: 'c1', historialId: 'h1', saldos: { saldo_final: 9 } }).saldo_final).toBeUndefined()
    expect(cuerpoEvaluar({ cuentaId: 'c1', saldos: { saldo_final: 9, fecha_corte: '2026-09-30' } })).toMatchObject({ saldo_final: 9, fecha_corte: '2026-09-30' })
    expect(textoEstadoMes({ estado: 'cuadra', dejo_de_cuadrar: true })).toBe('Dejó de cuadrar')
  })
})

describe('CuadreExtracto', () => {
  it('cuando cuadra lo dice y recuerda que el saldo oficial es el del banco', async () => {
    api.cuadreEvaluar.mockResolvedValue({ ...base, estado: 'cuadra', diferencia: 0, texto: 'Cuadra ✓ con tu banco al 30 sep 2026.' })
    montar(<CuadreExtracto cuentaId="c1" historialId="h1" />)
    expect(await screen.findByText(/Cuadra ✓ con tu banco/)).toBeInTheDocument()
    expect(screen.getByText(/el saldo oficial es el de tu banco/)).toBeInTheDocument()
  })

  it('con diferencia explica y ofrece las tres acciones; antes de traer no deja crear el ajuste', async () => {
    api.cuadreEvaluar.mockResolvedValue(dif())
    montar(<CuadreExtracto cuentaId="c1" historialId="h1" porImportar={[{ fecha: '2026-09-25', monto: 1, tipo: 'expense' }]} />)
    expect(await screen.findByText(/Diferencia de \$50.000/)).toBeInTheDocument()
    expect(screen.getByText('Puede faltar un gasto o cobro.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Ver qué puede faltar/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Dejarlo así por ahora' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Crear ajuste de saldo' })).toBeDisabled()
    expect(screen.getByTestId('motivo-bloqueo')).toHaveTextContent('Primero trae las líneas nuevas')
    expect(api.cuadreAjuste).not.toHaveBeenCalled()
  })

  it('el ajuste pide confirmación y nunca se crea con solo abrir el panel; se puede deshacer', async () => {
    api.cuadreEvaluar.mockResolvedValue(dif())
    api.cuadreAjuste.mockResolvedValue({ ok: true, movimiento_id: 'm1', texto: 'Listo: ajuste creado.' })
    api.cuadreDeshacer.mockResolvedValue({ ok: true, texto: 'Listo: lo deshice.' })
    const u = userEvent.setup()
    montar(<CuadreExtracto cuentaId="c1" historialId="h1" despues />)
    await u.click(await screen.findByRole('button', { name: 'Crear ajuste de saldo' }))
    expect(screen.getByTestId('panel-ajuste')).toHaveTextContent('no cuenta como gasto ni ingreso')
    expect(api.cuadreAjuste).not.toHaveBeenCalled()
    await u.click(screen.getByRole('button', { name: 'Sí, crear el ajuste' }))
    await waitFor(() => expect(api.cuadreAjuste).toHaveBeenCalledWith(expect.objectContaining({ cuenta_id: 'c1', historial_id: 'h1', confirmar: true, confirmar_reforzado: false })))
    expect(await screen.findByTestId('mensaje-cuadre')).toHaveTextContent('Listo: ajuste creado.')
    await u.click(screen.getByRole('button', { name: /Deshacer/ }))
    await waitFor(() => expect(api.cuadreDeshacer).toHaveBeenCalledWith('m1'))
  })

  it('un ajuste grande advierte y exige marcar que lo entiendes', async () => {
    api.cuadreEvaluar.mockResolvedValue(dif({ diferencia: -850000, acciones: { ajuste: { permitido: true, monto: -850000, grande: true, nota: 'Ajuste para cuadrar con el extracto del 30 sep 2026' }, dejar_asi: true, ver_que_falta: true } }))
    const u = userEvent.setup()
    montar(<CuadreExtracto cuentaId="c1" historialId="h1" despues />)
    await u.click(await screen.findByRole('button', { name: 'Crear ajuste de saldo' }))
    expect(screen.getByRole('alert')).toHaveTextContent('puede ocultar un movimiento que falta')
    const enviar = screen.getByRole('button', { name: 'Sí, crear el ajuste' })
    expect(enviar).toBeDisabled()
    await u.click(screen.getByRole('checkbox'))
    expect(enviar).toBeEnabled()
  })

  it('con líneas por resolver explica el bloqueo del ajuste', async () => {
    api.cuadreEvaluar.mockResolvedValue(dif({ acciones: { ajuste: { permitido: false, motivo_bloqueo: 'Primero trae o resuelve las líneas del extracto que faltan; después podrás crear el ajuste.', monto: -1, grande: false }, dejar_asi: true } }))
    montar(<CuadreExtracto cuentaId="c1" historialId="h1" despues />)
    expect(await screen.findByTestId('motivo-bloqueo')).toHaveTextContent('Primero trae o resuelve')
    expect(screen.getByRole('button', { name: 'Crear ajuste de saldo' })).toBeDisabled()
  })

  it('«Ver qué puede faltar» lista las dos puntas', async () => {
    api.cuadreEvaluar.mockResolvedValue(dif())
    api.cuadreQueFalta.mockResolvedValue({
      sin_pareja_en_tus_movimientos: [{ fecha: '2026-09-25', descripcion: 'Cobro del banco', monto: 50000, tipo: 'expense' }],
      sin_respaldo_en_el_extracto: [{ fecha: '2026-09-10', descripcion: 'Restaurante', monto: 100000, tipo: 'expense' }],
    })
    const u = userEvent.setup()
    montar(<CuadreExtracto cuentaId="c1" historialId="h1" />)
    await u.click(await screen.findByRole('button', { name: /Ver qué puede faltar/ }))
    expect(await screen.findByText(/Cobro del banco/)).toBeInTheDocument()
    expect(screen.getByText(/Restaurante/)).toBeInTheDocument()
  })

  it('sin saldo en el extracto pide escribirlo y lo guarda con confirmación', async () => {
    api.cuadreEvaluar.mockResolvedValue({ ...base, estado: 'sin_saldo', fecha_corte: '2026-09-30', texto: 'Este extracto no trae un saldo que pueda leer. Escribe el saldo que dice tu extracto al 30 sep 2026 y lo comparo con tus movimientos.' })
    api.cuadreSaldos.mockResolvedValue({ ok: true })
    const u = userEvent.setup()
    montar(<CuadreExtracto cuentaId="c1" historialId="h1" />)
    expect(await screen.findByText(/Escribe el saldo que dice tu extracto al 30 sep 2026/)).toBeInTheDocument()
    await u.type(screen.getByLabelText('Saldo del extracto'), '1800000')
    await u.click(screen.getByRole('button', { name: 'Comparar con mis movimientos' }))
    await waitFor(() => expect(api.cuadreSaldos).toHaveBeenCalledWith({ historial_id: 'h1', saldo_final: 1800000, fecha_corte: '2026-09-30', confirmar: true }))
  })

  it('moneda distinta o cuenta equivocada se advierten antes de comparar', async () => {
    api.cuadreEvaluar.mockResolvedValue({ ...base, estado: 'moneda_distinta', texto: 'Este extracto está en USD y tu cuenta «Nu» está en COP. No lo comparo.' })
    montar(<CuadreExtracto cuentaId="c1" historialId="h1" />)
    expect(await screen.findByText(/está en USD/)).toBeInTheDocument()
  })

  it('si el servidor falla, no estorba (no pinta nada)', async () => {
    api.cuadreEvaluar.mockRejectedValue(new Error('x'))
    const { container } = montar(<CuadreExtracto cuentaId="c1" historialId="h1" />)
    await waitFor(() => expect(api.cuadreEvaluar).toHaveBeenCalled())
    expect(container.querySelector('[data-testid="cuadre-extracto"]')).toBeNull()
  })
})

describe('histórico por mes y tarjeta del detalle', () => {
  const datos = {
    moneda: 'COP',
    meses: [
      { mes: '2026-08', etiqueta: 'Agosto 2026', estado: 'diferencia', diferencia: -100000, dejo_de_cuadrar: true, historial_id: 'h1', fecha_corte: '2026-08-31' },
      { mes: '2026-09', etiqueta: 'Septiembre 2026', estado: 'cuadra', diferencia: 0, historial_id: 'h2', fecha_corte: '2026-09-30' },
      { mes: '2026-10', etiqueta: 'Octubre 2026', estado: 'sin_extracto' },
    ],
    alertas: [{ mes: '2026-08', texto: 'Agosto 2026 cuadraba y ahora tiene una diferencia de $100.000.' }],
    ultimo_cuadre: { mes: '2026-09', fecha_corte: '2026-09-30' },
    estado_actual: { mes: '2026-09', estado: 'cuadra', historial_id: 'h2', diferencia: 0 },
    diagnostico: { descuadre: false },
  }

  it('CuadreMes muestra cada mes con texto (no solo color) y la alerta de «dejó de cuadrar»', () => {
    montar(<CuadreMes cuentaId="c1" datos={datos} />)
    expect(screen.getByText('Dejó de cuadrar')).toBeInTheDocument()
    expect(screen.getByText('Cuadra')).toBeInTheDocument()
    expect(screen.getByText('Sin extracto')).toBeInTheDocument()
    expect(screen.getByText(/cuadraba y ahora tiene una diferencia/)).toBeInTheDocument()
  })

  it('la tarjeta del detalle dice la última fecha cuadrada y tiene «Revisar»', async () => {
    api.cuadreCuenta.mockResolvedValue(datos)
    api.cuadreEvaluar.mockResolvedValue({ ...base, estado: 'cuadra', texto: 'Cuadra ✓ con tu banco al 30 sep 2026.' })
    const u = userEvent.setup()
    montar(<TarjetaCuadreBanco cuentaId="c1" />)
    expect(await screen.findByTestId('ultimo-cuadre')).toHaveTextContent('Última vez que cuadró: 30 sep 2026.')
    expect(screen.getByTestId('diferencia-actual')).toHaveTextContent('no hay diferencia')
    await u.click(screen.getByRole('button', { name: 'Revisar' }))
    expect(await screen.findByTestId('cuadre-extracto')).toBeInTheDocument()
  })

  it('un saldo que no viene de movimientos ofrece el saldo inicial con confirmación y sin cambiar el saldo', async () => {
    api.cuadreCuenta.mockResolvedValue({ ...datos, meses: [], estado_actual: null, alertas: [], ultimo_cuadre: null, diagnostico: { descuadre: true, diferencia: 1000000, texto: 'El saldo no coincide con la suma de sus movimientos.' } })
    api.cuadreSaldoInicial.mockResolvedValue({ ok: true, movimiento_id: 'm9', texto: 'Listo: saldo inicial registrado.' })
    const u = userEvent.setup()
    montar(<TarjetaCuadreBanco cuentaId="c1" />)
    expect(await screen.findByTestId('diagnostico-saldo')).toBeInTheDocument()
    await u.click(screen.getByRole('button', { name: 'Revisar' }))
    expect(screen.getByTestId('saldo-inicial-sin-explicar')).toHaveTextContent('tu saldo no cambia')
    expect(api.cuadreSaldoInicial).not.toHaveBeenCalled()
    await u.click(screen.getByRole('button', { name: 'Registrar saldo inicial' }))
    await waitFor(() => expect(api.cuadreSaldoInicial).toHaveBeenCalledWith({ cuenta_id: 'c1', modo: 'sin_explicar', confirmar: true }))
  })
})
