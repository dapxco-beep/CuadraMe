// «Importar mi respaldo»: vista previa en lenguaje llano -> importar -> resultado -> deshacer.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({
  api: new Proxy(api, { get: (t, nombre) => t[nombre] ?? (() => Promise.resolve([])) }),
}))
vi.mock('../lib/AuthContext', () => ({
  useAuth: () => ({ usuario: { id: 'u1', email: 'l@test.com', nombre: 'Laura' }, logout: vi.fn() }),
}))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import ImportarRespaldo, { frasesRespaldo } from '../components/ImportarRespaldo'

const VISTA = {
  vista_previa: true,
  cuentas: { nuevos: 2, existentes: 1, invalidos: 0 },
  movimientos: { nuevos: 120, existentes: 30, invalidos: 0, sin_cuenta: 0, anteriores_al_punto_de_partida: 4 },
  presupuestos: { nuevos: 1, existentes: 0, invalidos: 0 },
  metas: { nuevos: 0, existentes: 1, invalidos: 0 },
  reglas: { nuevos: 3, existentes: 0, invalidos: 0 },
}

function montar() {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter>
          <ImportarRespaldo onCerrar={() => {}} />
        </MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  for (const k of Object.keys(api)) delete api[k]
  api.ultimaImportacionRespaldo = vi.fn().mockResolvedValue({ hay: false })
})

describe('frasesRespaldo', () => {
  it('explica en lenguaje llano qué se agrega, qué ya existe y qué queda fuera', () => {
    const f = frasesRespaldo(VISTA, true)
    expect(f[0]).toBe('Se agregarían 2 cuentas, 120 movimientos, 1 presupuesto y 3 reglas.')
    expect(f[1]).toBe('Ya tenías 1 cuenta, 30 movimientos y 1 meta: no se repiten.')
    expect(f[2]).toMatch(/4 movimientos quedan por fuera/)
  })
  it('en pasado y cuando no hay nada nuevo', () => {
    expect(frasesRespaldo(VISTA, false)[0]).toMatch(/^Se agregaron /)
    const vacio = { cuentas: { nuevos: 0, existentes: 2, invalidos: 0 }, movimientos: { nuevos: 0, existentes: 5, invalidos: 0 } }
    expect(frasesRespaldo(vacio, true)[0]).toBe('No hay nada nuevo para agregar.')
  })
})

describe('ImportarRespaldo', () => {
  it('muestra la vista previa, importa, muestra el resultado y permite deshacer', async () => {
    api.vistaPreviaRespaldo = vi.fn().mockResolvedValue(VISTA)
    api.importarRespaldo = vi.fn().mockResolvedValue({ ok: true, ...VISTA, vista_previa: undefined })
    api.deshacerImportacionRespaldo = vi.fn().mockResolvedValue({ ok: true })
    montar()

    const archivo = new File(['zip'], 'cuadrame_mis_datos.zip', { type: 'application/zip' })
    await userEvent.upload(screen.getByTestId('archivo-respaldo'), archivo)
    expect(await screen.findByTestId('vista-previa-respaldo')).toHaveTextContent('Se agregarían 2 cuentas')
    expect(api.vistaPreviaRespaldo).toHaveBeenCalledWith(archivo)
    expect(api.importarRespaldo).not.toHaveBeenCalled() // la vista previa no guarda nada

    await userEvent.click(screen.getByRole('button', { name: 'Importar' }))
    expect(await screen.findByTestId('resultado-respaldo')).toHaveTextContent('Se agregaron 2 cuentas')
    expect(api.importarRespaldo).toHaveBeenCalledWith(archivo)

    await userEvent.click(screen.getByRole('button', { name: /Deshacer última importación/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Deshacer' }))
    await waitFor(() => expect(api.deshacerImportacionRespaldo).toHaveBeenCalled())
    expect(await screen.findByText(/deshicimos la importación/)).toBeInTheDocument()
  })

  it('si el archivo no sirve, lo dice con claridad y no ofrece importar', async () => {
    api.vistaPreviaRespaldo = vi.fn().mockRejectedValue(new Error('Este ZIP no trae el archivo datos.json.'))
    montar()
    await userEvent.upload(screen.getByTestId('archivo-respaldo'), new File(['x'], 'raro.zip'))
    expect(await screen.findByRole('alert')).toHaveTextContent('no trae el archivo datos.json')
    expect(screen.queryByRole('button', { name: 'Importar' })).not.toBeInTheDocument()
  })

  it('ofrece deshacer una importación anterior desde que se abre', async () => {
    api.ultimaImportacionRespaldo = vi.fn().mockResolvedValue({ hay: true })
    montar()
    expect(await screen.findByRole('button', { name: /Deshacer última importación/ })).toBeInTheDocument()
  })
})
