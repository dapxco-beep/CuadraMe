// «Estado por cuenta y mes»: cada mes dice UN estado que se entiende solo y abre su acción lógica.
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import EstadoPorCuenta from '../components/EstadoPorCuenta'
import { nombreCompleto, resumenMeses, vistaCelda } from '../lib/estadoPorCuenta'

describe('vistaCelda', () => {
  it('conciliado: dice cuántos movimientos', () => {
    expect(vistaCelda({ estado: 'conciliado', movimientos: 14 })).toMatchObject({ clave: 'conciliado', texto: 'Cuadra con tu banco', detalle: '14 mov.', accion: 'ver' })
  })
  it('a medias: cuántos faltan importar y abre la revisión', () => {
    expect(vistaCelda({ estado: 'parcial', por_revisar: 3 })).toMatchObject({ clave: 'falta_importar', texto: 'Faltan 3 por agregar', accion: 'importar' })
    expect(vistaCelda({ estado: 'parcial', por_revisar: 1, lectura_dudosa: 1 }).detalle).toBe('Elige un monto')
  })
  it('no se pudo leer: dice el motivo corto; si es la clave, abre la clave', () => {
    expect(vistaCelda({ estado: 'no_se_pudo_leer', motivo_corto: 'formato no reconocido' })).toMatchObject({
      clave: 'no_se_pudo_leer', texto: 'No se pudo leer', detalle: 'formato no reconocido', accion: 'revisar_error',
    })
    expect(vistaCelda({ estado: 'no_se_pudo_leer', motivo_corto: 'falta la clave' }).accion).toBe('clave')
    expect(vistaCelda({ estado: 'falta_clave' })).toMatchObject({ clave: 'no_se_pudo_leer', detalle: 'falta la clave', accion: 'clave' })
  })
  it('sin extracto: «Falta el extracto» y sube; el mes que no termina está en curso', () => {
    expect(vistaCelda({ estado: 'vacio' })).toMatchObject({ clave: 'falta_extracto', texto: 'Falta el extracto', accion: 'subir' })
    expect(vistaCelda({ estado: 'vacio' }, { esMesActual: true })).toMatchObject({ clave: 'en_curso', texto: 'Mes en curso' })
  })
  it('un extracto de la tarjeta que quedó en otra cuenta lo dice y ofrece pasarlo', () => {
    const v = vistaCelda({ estado: 'vacio', en_otra_cuenta: [{ historial_id: 'h', desde: 'Nu Colombia' }] })
    expect(v).toMatchObject({ clave: 'otra_cuenta', detalle: 'Está en Nu Colombia', accion: 'pasar' })
  })
  it('anterior a tu inicio no hace nada', () => {
    expect(vistaCelda({ estado: 'anterior' }).accion).toBe('ninguna')
  })
})

describe('resumen y nombre', () => {
  it('«3 de 6 meses completos» sin contar lo anterior al inicio ni el mes en curso', () => {
    const v = (e, o) => vistaCelda({ estado: e }, o)
    const vistas = [v('conciliado'), v('conciliado'), v('conciliado'), v('vacio'), v('parcial'), v('vacio')]
    expect(resumenMeses(vistas)).toBe('3 de 6 meses completos')
    expect(resumenMeses([v('anterior'), v('conciliado'), v('vacio', { esMesActual: true })])).toBe('1 de 1 mes completo')
    expect(resumenMeses([])).toBe('Aún sin meses por revisar')
  })
  it('nombre completo con el tipo', () => {
    expect(nombreCompleto({ nombre: 'Nu Colombia', tipo: 'ahorro' })).toBe('Nu Colombia · Ahorros')
    expect(nombreCompleto({ nombre: 'Nu Colombia Crédito', tipo: 'credito' })).toBe('Nu Colombia Crédito · Tarjeta')
  })
})

const MESES = [{ clave: '2026-08', etiqueta: 'ago 26' }, { clave: '2026-09', etiqueta: 'sep 26' }]
const celda = (mes, extra) => ({ mes, estado: 'vacio', movimientos: 0, por_revisar: 0, lista: [], en_otra_cuenta: [], ...extra })
const CUENTAS = [
  { id: 'n', nombre: 'Nequi', tipo: 'ahorro', meses: [celda('2026-08', { estado: 'conciliado', movimientos: 5 }), celda('2026-09', { estado: 'conciliado', movimientos: 7 })] },
  { id: 'c', nombre: 'Nu Colombia Crédito', tipo: 'credito', meses: [celda('2026-08'), celda('2026-09', { estado: 'no_se_pudo_leer', motivo_corto: 'falta la clave' })] },
  { id: 'e', nombre: 'Efectivo', tipo: 'efectivo', meses: [celda('2026-08'), celda('2026-09')] },
]

describe('<EstadoPorCuenta>', () => {
  it('una tarjeta por cuenta con su nombre completo y su resumen; el efectivo no tiene extracto', () => {
    render(<EstadoPorCuenta cuentas={CUENTAS} meses={MESES} />)
    expect(screen.getByRole('article', { name: 'Nequi · Ahorros' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Nu Colombia Crédito · Tarjeta' })).toBeInTheDocument()
    expect(screen.queryByRole('article', { name: /Efectivo/ })).not.toBeInTheDocument()
    expect(screen.getByTestId('resumen-n')).toHaveTextContent('2 de 2 meses completos')
    expect(screen.getByTestId('resumen-c')).toHaveTextContent('0 de 2 meses completos')
  })

  it('cada mes dice su estado y al tocarlo abre su acción', async () => {
    const onMes = vi.fn()
    render(<EstadoPorCuenta cuentas={CUENTAS} meses={MESES} onMes={onMes} />)
    const sep = screen.getByTestId('mes-c-2026-09')
    expect(within(sep).getByText('No se pudo leer')).toBeInTheDocument()
    expect(within(sep).getByText('falta la clave')).toBeInTheDocument()
    await userEvent.click(sep)
    expect(onMes).toHaveBeenCalledTimes(1)
    expect(onMes.mock.calls[0][0].id).toBe('c')
    expect(onMes.mock.calls[0][2].accion).toBe('clave')
    await userEvent.click(screen.getByTestId('mes-c-2026-08'))
    expect(onMes.mock.calls[1][2].accion).toBe('subir')
  })

  it('sin cuentas o sin meses no pinta nada', () => {
    const { container } = render(<EstadoPorCuenta cuentas={[]} meses={MESES} />)
    expect(container).toBeEmptyDOMElement()
  })
})
