// «Tu plata trabajando»: cajitas, rendimiento estimado, comparación informativa y silenciar el aviso.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({
  api: new Proxy(api, { get: (t, nombre) => t[nombre] ?? (() => Promise.resolve([])) }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import ConsejoParaTi from '../components/ConsejoParaTi'
import TarjetaTuPlata, { CajitasDeCuenta, RenglonTuPlata, RendimientoCuenta } from '../components/TuPlataTrabajando'
import { fechaCorta, formatTasa, leerTasa } from '../lib/rendimientos'
import { GLOSARIO, LECCIONES, terminoPorId } from '../lib/aprende'

const FILA = {
  cuenta_id: 'c1', nombre: 'Nu', moneda: 'COP', saldo: 3000000, principal: 2500000, tasa_principal: 0.1, descuadre: false,
  sin_tasa: false, estimado: { dia: 7, mes_corrido: 90000, mes: 220, anio: 2650 },
  cajitas: [{ id: 'k1', nombre: 'Viaje', saldo: 500000, tasa_ea: 9, tasa_fecha: '2026-10-12', est: null }],
}
const RESUMEN = {
  hay_cuentas: true, hay_cajitas: true, cuentas: [FILA],
  total: { mes_corrido: 90000, anio: 2650, hay_estimacion: true, recibido_mes: 1234 },
  comparacion: {
    ociosa: [{ cuenta_id: 'c1', nombre: 'Nu', saldo: 2500000, tasa_actual: 0.1, tasa_ref: 9, extra_anual: 222500 }],
    tasa_ref: 9, ref_fecha: '2026-10-12', nota: 'Verifica en tu banco.',
    opciones: [{ id: 't1', entidad: 'Nu Colombia', producto: 'Cajitas', tasa_ea: 9, vigente_desde: '2026-10-12', nota: 'Referencia, verifica en la app de tu banco.' }],
  },
}

function montar(ui) {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  for (const k of Object.keys(api)) delete api[k]
  api.rendimientos = vi.fn().mockResolvedValue(RESUMEN)
})

describe('formato', () => {
  it('tasas con coma decimal y fechas cortas', () => {
    expect(formatTasa(0.1)).toBe('0,1 %')
    expect(formatTasa(9)).toBe('9 %')
    expect(formatTasa(null)).toBe('—')
    expect(fechaCorta('2026-10-12')).toContain('2026')
    expect(leerTasa('9,5')).toBe(9.5)
    expect(leerTasa('')).toBeNull()
    expect(leerTasa('abc')).toBeNaN()
  })
  it('el glosario y la microlección explican E.A., cajita, CDT y rendimiento sin recomendar productos', () => {
    for (const id of ['ea', 'cajita', 'cdt', 'rendimiento']) expect(terminoPorId(id), id).toBeTruthy()
    expect(GLOSARIO.filter((t) => t.leccion === 'donde-rinde-mi-plata').length).toBeGreaterThanOrEqual(3)
    const l = LECCIONES.find((x) => x.id === 'donde-rinde-mi-plata')
    expect(l.ejemplo).toMatch(/\$\d/)
    expect(l.cuerpo.join(' ')).toMatch(/no te recomienda ningún banco/i)
  })
})

describe('Cuentas y detalle', () => {
  it('cada cuenta muestra tasa y lo ganado (estimado) y ofrece «Agregar una cajita»', async () => {
    montar(<RendimientoCuenta cuentaId="c1" />)
    expect(await screen.findByText(/Rinde 0,1 % E\.A\./)).toBeInTheDocument()
    expect(screen.getByText(/ganó ~\$\s?90\.000 este mes/)).toBeInTheDocument()
    expect(screen.getByText(/\(estimado\)/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Agregar una cajita/ })).toBeInTheDocument()
  })

  it('el detalle lista las cajitas con saldo y tasa, y mover plata llama a la API', async () => {
    api.moverCajita = vi.fn().mockResolvedValue({})
    const user = userEvent.setup()
    montar(<CajitasDeCuenta cuentaId="c1" />)
    expect(await screen.findByText('Viaje')).toBeInTheDocument()
    expect(screen.getByText(/9 % E\.A\. · tasa del/)).toBeInTheDocument()
    expect(screen.getByText(/no es un gasto ni un ingreso/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Mover plata/ }))
    await user.type(await screen.findByLabelText(/¿Cuánto\?/), '100000')
    await user.click(screen.getAllByRole('button', { name: 'Mover plata' }).at(-1))
    await waitFor(() => expect(api.moverCajita).toHaveBeenCalledWith('k1', { monto: 100000, sentido: 'entrar' }))
  })

  it('no deja mover más que el saldo principal', async () => {
    api.moverCajita = vi.fn()
    const user = userEvent.setup()
    montar(<CajitasDeCuenta cuentaId="c1" />)
    await user.click(await screen.findByRole('button', { name: /Mover plata/ }))
    await user.type(await screen.findByLabelText(/¿Cuánto\?/), '9000000')
    await user.click(screen.getAllByRole('button', { name: 'Mover plata' }).at(-1))
    expect(await screen.findByRole('alert')).toHaveTextContent(/solo hay/)
    expect(api.moverCajita).not.toHaveBeenCalled()
  })
})

describe('Inicio', () => {
  it('la tarjeta muestra el estimado del mes y de 12 meses, lo real y la comparación con aviso educativo', async () => {
    montar(<TarjetaTuPlata />)
    expect(await screen.findByTestId('tu-plata-mes')).toHaveTextContent(/~\$\s?90\.000 este mes/)
    expect(screen.getByTestId('tu-plata-mes')).toHaveTextContent(/~\$\s?2\.650 en 12 meses/)
    expect(screen.getByTestId('tu-plata')).toHaveTextContent(/estimación/i)
    expect(screen.getByTestId('tu-plata-real')).toHaveTextContent(/\$\s?1\.234/)
    expect(screen.getByTestId('tu-plata-ociosa')).toHaveTextContent(/~\$\s?222\.500 más al año/)
    expect(screen.getByTestId('tu-plata')).toHaveTextContent('no es asesoría financiera')
  })

  it('las tasas de referencia se listan con fecha y nota, sin recomendar', async () => {
    const user = userEvent.setup()
    montar(<TarjetaTuPlata />)
    await user.click(await screen.findByRole('button', { name: /Ver tasas de referencia/ }))
    const lista = await screen.findByTestId('lista-tasas')
    expect(lista).toHaveTextContent('Nu Colombia · Cajitas')
    expect(lista).toHaveTextContent(/verifica en la app de tu banco/i)
  })

  it('el Inicio simple solo muestra el renglón si hay cajitas', async () => {
    const { unmount } = montar(<RenglonTuPlata />)
    expect(await screen.findByTestId('tu-plata-simple')).toHaveTextContent(/~\$\s?90\.000/)
    unmount()
    api.rendimientos = vi.fn().mockResolvedValue({ ...RESUMEN, hay_cajitas: false })
    montar(<RenglonTuPlata />)
    await waitFor(() => expect(api.rendimientos).toHaveBeenCalled())
    expect(screen.queryByTestId('tu-plata-simple')).toBeNull()
  })
})

describe('consejo «plata ociosa»', () => {
  it('se puede silenciar y no vuelve', async () => {
    api.consejos = vi.fn().mockResolvedValue({
      aviso: 'Orientación educativa, no es asesoría financiera.',
      consejos: [{ id: 'plata-ociosa:c1:2026-10', tipo: 'plata_ociosa', prioridad: 3, titulo: 'Tu plata en Nu casi no rinde',
        texto: 'x', cifra: '~$222.500/año', accion: { texto: 'Ver las opciones', ruta: '/cuentas' }, aprende: 'donde-rinde-mi-plata', silenciable: true }],
    })
    const user = userEvent.setup()
    const { unmount } = montar(<ConsejoParaTi />)
    await user.click(await screen.findByTestId('silenciar-consejo'))
    expect(screen.queryByTestId('consejo-para-ti')).toBeNull()
    unmount()
    montar(<ConsejoParaTi />)
    await waitFor(() => expect(api.consejos).toHaveBeenCalledTimes(2))
    expect(screen.queryByTestId('consejo-para-ti')).toBeNull()
  })
})
