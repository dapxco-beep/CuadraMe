// «Mi cuenta cuadra»: mapeo del cuadre del servidor a semáforo, pantalla (carga, vacío, error, filas) y acceso en Inicio.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

const api = vi.hoisted(() => ({ correrAutoarreglo: vi.fn() }))
vi.mock('../lib/api', () => ({ api }))

import MiCuentaCuadra from '../screens/MiCuentaCuadra'
import AccesoCuadre from '../components/AccesoCuadre'
import { reiniciarParaPruebas, iniciar } from '../lib/autoarreglo'
import { resumenCuadre, unaFrase, vistaCuadre, vistasCuadre } from '../lib/miCuentaCuadra'

const CUADRA = { cuenta_id: 'a', cuenta: 'Nu Colombia', estado: 'cuadra', texto: 'Cuadra todos los meses', primer_mes_malo: null, causa: null, ruta: '/sincronizacion#cuadre' }
const MALA = {
  cuenta_id: 'b', cuenta: 'Bancolombia', estado: 'no_cuadra', primer_mes_malo: '2026-03', diferencia: 45000,
  causa: 'Parece que falta un movimiento de $45.000 que está en tu extracto. Revisa el extracto de marzo con calma y compáralo.',
  texto: 'Primer mes que no cuadra: marzo 2026 por $45.000', ruta: '/sincronizacion#cuadre',
}
const respuesta = (cuadre) => ({ estado: 'listo', progreso: { hecho: 6, total: 6 }, resumen: null, decisiones: [], cuadre })

function Sitio() { const l = useLocation(); return <p data-testid="sitio">{l.pathname}{l.hash}</p> }
const montar = (ui = <MiCuentaCuadra />) => render(<MemoryRouter><Routes><Route path="*" element={<>{ui}<Sitio /></>} /></Routes></MemoryRouter>)

beforeEach(() => { cleanup(); vi.clearAllMocks(); reiniciarParaPruebas() })

describe('mapeo', () => {
  it('verde: Cuadra todos los meses, con lo que falte si el servidor lo dice', () => {
    expect(vistaCuadre(CUADRA)).toMatchObject({ estado: 'cuadra', titulo: 'Cuadra todos los meses', detalle: '' })
    expect(vistaCuadre({ ...CUADRA, texto: 'Cuadra todos los meses; solo falta el extracto de abril 2026' }).detalle).toBe('Solo falta el extracto de abril 2026')
  })
  it('ámbar: el mes y UNA frase de causa', () => {
    const v = vistaCuadre(MALA)
    expect(v).toMatchObject({ estado: 'no_cuadra', titulo: 'Deja de cuadrar en marzo 2026' })
    expect(v.detalle).toBe('Parece que falta un movimiento de $45.000 que está en tu extracto.')
  })
  it('sin causa usa texto; frase larga se recorta; las que no cuadran van primero', () => {
    expect(vistaCuadre({ ...MALA, causa: null }).detalle).toMatch(/^Primer mes que no cuadra/)
    const larga = unaFrase('x'.repeat(300))
    expect(larga.length).toBeLessThanOrEqual(120)
    expect(larga.endsWith('…')).toBe(true)
    expect(vistasCuadre([CUADRA, MALA]).map((v) => v.id)).toEqual(['b', 'a'])
    expect(vistasCuadre(null)).toEqual([])
  })
  it('resumen', () => {
    expect(resumenCuadre(vistasCuadre([CUADRA, MALA]))).toBe('1 de 2 cuentas cuadran')
    expect(resumenCuadre(vistasCuadre([CUADRA]))).toBe('Tu cuenta cuadra todos los meses')
    expect(resumenCuadre([])).toBe('')
  })
})

describe('pantalla', () => {
  it('muestra carga y luego una fila por cuenta; tocar abre el detalle', async () => {
    let soltar
    api.correrAutoarreglo.mockImplementation(() => new Promise((r) => { soltar = r }))
    montar()
    expect(screen.getByRole('status', { name: 'Revisando tus cuentas' })).toBeInTheDocument()
    await waitFor(() => expect(soltar).toBeTypeOf('function'))
    soltar(respuesta([CUADRA, MALA]))
    const mala = await screen.findByTestId('cuadre-b')
    expect(mala).toHaveAttribute('data-estado', 'no_cuadra')
    expect(mala).toHaveTextContent('Deja de cuadrar en marzo 2026')
    expect(screen.getByTestId('cuadre-a')).toHaveTextContent('Cuadra todos los meses')
    expect(screen.getByTestId('resumen-cuadre')).toHaveTextContent('1 de 2 cuentas cuadran')
    await userEvent.click(mala)
    expect(screen.getByTestId('sitio')).toHaveTextContent('/sincronizacion#cuadre')
  })
  it('sin cuentas con extracto: estado vacío con salida', async () => {
    api.correrAutoarreglo.mockResolvedValue(respuesta([]))
    montar()
    expect(await screen.findByText('Aún no hay nada que comparar')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Traer extractos' }))
    expect(screen.getByTestId('sitio')).toHaveTextContent('/sincronizacion')
  })
  it('si falla, lo dice y permite reintentar', async () => {
    api.correrAutoarreglo.mockRejectedValueOnce(new Error('sin red'))
    montar()
    expect(await screen.findByRole('alert')).toHaveTextContent('No pude revisar tus cuentas ahora')
    api.correrAutoarreglo.mockResolvedValue(respuesta([CUADRA]))
    await userEvent.click(screen.getByRole('button', { name: 'Intentar de nuevo' }))
    expect(await screen.findByTestId('cuadre-a')).toBeInTheDocument()
  })
})

describe('acceso en Inicio', () => {
  it('no sale sin datos; con datos resume y lleva a la pantalla', async () => {
    api.correrAutoarreglo.mockResolvedValue(respuesta([CUADRA, MALA]))
    montar(<AccesoCuadre />)
    expect(screen.queryByTestId('acceso-cuadre')).toBeNull()
    await iniciar({ espera: 0 })
    const acceso = await screen.findByTestId('acceso-cuadre')
    expect(acceso).toHaveTextContent('1 de 2 cuentas cuadran')
    await userEvent.click(acceso)
    expect(screen.getByTestId('sitio')).toHaveTextContent('/mi-cuenta-cuadra')
  })
})
