// Experiencia: errores de subida con siguiente paso, vibración protegida y «Letra grande».
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const api = vi.hoisted(() => ({
  procesarExtracto: vi.fn(),
  clavePdfEstado: vi.fn(),
  guardarClavePdf: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({
    cuentas: [{ id: 'c1', nombre: 'Nequi', icono: '💜' }],
    recargar: vi.fn(),
  }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Otros'], iconoDe: () => '💳' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import SubidaMultiple from '../components/SubidaMultiple'
import { etiquetaArchivo, procesarCola } from '../lib/subidaMultiple'
import { error as vibError, exito, toque } from '../lib/haptico'
import { aplicarLetraGrande, guardarLetraGrande, iniciarLetraGrande, leerLetraGrande } from '../lib/letraGrande'

const pdf = (n) => new File(['%PDF-1.4'], n, { type: 'application/pdf' })

describe('subida: errores con siguiente paso', () => {
  beforeEach(() => {
    Object.values(api).forEach((f) => f.mockReset())
    api.clavePdfEstado.mockResolvedValue({ configurada: false })
  })

  it('un error crudo se traduce, dice qué hacer y ofrece «Anotar a mano»', async () => {
    api.procesarExtracto.mockRejectedValueOnce(new Error('Unexpected token < in JSON'))
    render(
      <DialogosProvider>
        <MemoryRouter initialEntries={['/subir']}>
          <Routes>
            <Route path="/subir" element={<SubidaMultiple archivosIniciales={[pdf('a.pdf')]} cuentaInicial="c1" onCancelar={vi.fn()} />} />
            <Route path="/agregar" element={<p>pantalla agregar</p>} />
          </Routes>
        </MemoryRouter>
      </DialogosProvider>
    )
    await userEvent.click(screen.getByRole('button', { name: /Procesar/ }))
    expect(await screen.findByText('No se pudo procesar')).toBeInTheDocument()
    expect(screen.queryByText(/Unexpected token/)).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Anotar a mano' }))
    expect(await screen.findByText('pantalla agregar')).toBeInTheDocument()
  })

  it('un error sin texto cae al mensaje con siguiente paso', async () => {
    const cambios = []
    await procesarCola([{ id: 'x', estado: 'pendiente' }], async () => { throw new Error('') }, { onCambio: (id, p) => cambios.push(p) })
    expect(cambios.at(-1).error).toMatch(/toca Reintentar/)
  })

  it('falta la clave: pista de la cédula y apoyo mientras el campo está vacío', async () => {
    api.procesarExtracto.mockResolvedValueOnce({ ok: false, requiere_clave: true, error: 'El PDF tiene clave' })
    render(
      <DialogosProvider>
        <MemoryRouter><SubidaMultiple archivosIniciales={[pdf('b.pdf')]} cuentaInicial="c1" onCancelar={vi.fn()} /></MemoryRouter>
      </DialogosProvider>
    )
    await userEvent.click(screen.getByRole('button', { name: /Procesar/ }))
    expect(await screen.findByText(/Casi siempre es tu cédula, sin puntos\. Escribe la clave para continuar/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Clave de b.pdf'), '1234')
    expect(screen.queryByText(/Escribe la clave para continuar/)).toBeNull()
  })

  it('las etiquetas de un PDF avisan que puede tardar', () => {
    expect(etiquetaArchivo({ tipo: 'pdf', estado: 'procesando' })).toMatch(/Procesando… · puede tardar hasta 1 minuto/)
    expect(etiquetaArchivo({ tipo: 'pdf', estado: 'pendiente' })).toMatch(/En espera/)
    expect(etiquetaArchivo({ tipo: 'tabular', estado: 'procesando' })).toBe('Procesando…')
  })
})

describe('háptico', () => {
  it('no falla sin navigator.vibrate y vibra cuando existe', () => {
    const orig = navigator.vibrate
    Object.defineProperty(navigator, 'vibrate', { value: undefined, configurable: true })
    expect(() => { toque(); exito(); vibError() }).not.toThrow()
    const v = vi.fn()
    Object.defineProperty(navigator, 'vibrate', { value: v, configurable: true })
    toque(); exito(); vibError()
    expect(v).toHaveBeenCalledTimes(3)
    Object.defineProperty(navigator, 'vibrate', { value: () => { throw new Error('x') }, configurable: true })
    expect(() => toque()).not.toThrow()
    Object.defineProperty(navigator, 'vibrate', { value: orig, configurable: true })
  })
})

describe('letra grande', () => {
  beforeEach(() => { localStorage.clear(); aplicarLetraGrande(false) })

  it('se guarda, se aplica al arrancar y se quita', () => {
    expect(leerLetraGrande()).toBe(false)
    guardarLetraGrande(true)
    expect(document.documentElement.style.fontSize).toBe('112.5%')
    aplicarLetraGrande(false)
    iniciarLetraGrande()
    expect(document.documentElement.style.fontSize).toBe('112.5%')
    guardarLetraGrande(false)
    expect(document.documentElement.style.fontSize).toBe('')
    expect(leerLetraGrande()).toBe(false)
  })
})
