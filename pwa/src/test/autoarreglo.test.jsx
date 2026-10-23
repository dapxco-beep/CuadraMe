// Autoarreglo: textos, corredor (una vez por sesión y por hora, sin bloquear), aviso en pantalla, hoja «Qué hice» y deshacer.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({ correrAutoarreglo: vi.fn(), lotesAutoarreglo: vi.fn(), deshacerLoteAutoarreglo: vi.fn() }))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({ useCuentas: () => ({ cuentas: [], recargar: vi.fn().mockResolvedValue() }) }))

import AvisoAutoarreglo from '../components/AvisoAutoarreglo'
import {
  INTERVALO_MS, iniciar, lineasConteo, reiniciarParaPruebas, textoAviso, textoListo, textoPaso, textoProgreso, tocaCorrer,
} from '../lib/autoarreglo'

const fmt = (n) => `$${n}`
const LOTE = {
  lote_id: 'L1', cambios: 9, revertido: false, deshacible: true,
  texto: 'Listo, ordené tus cuentas: moví 4 extractos a tu tarjeta, corregí 31 compras, registré 12 rendimientos e impuestos.',
  contadores: { extractos_movidos: 4, compras_corregidas: 31, pagos_corregidos: 0, repetidos_quitados: 0, rendimientos_registrados: 12, lineas_importadas: 1, ajustes_iniciales: 0 },
  cuentas: [{ cuenta_id: 'a', cuenta: 'Nu Colombia', saldo_antes: 2700000, saldo_despues: 2706100 }],
  detalle: [{ tipo: 'corregir_tipo', descripcion: 'Tienda Uno SAS', monto: 40000, fecha: '2026-07-03' }],
}
const LISTO = { estado: 'listo', progreso: { hecho: 6, total: 6, paso: null }, resumen: LOTE, decisiones: [], cuadre: [] }

function montar() {
  return render(<MemoryRouter><AvisoAutoarreglo /></MemoryRouter>)
}

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  reiniciarParaPruebas()
  api.lotesAutoarreglo.mockResolvedValue({ lotes: [LOTE] })
})

describe('textos', () => {
  it('progreso y resultado', () => {
    expect(textoProgreso({ hecho: 1, total: 6 })).toBe('Ordenando tus cuentas: paso 2 de 6')
    expect(textoProgreso(null)).toBe('Ordenando tus cuentas: paso 1 de 6')
    expect(textoProgreso({ hecho: 9, total: 6 })).toBe('Ordenando tus cuentas: paso 6 de 6')
    expect(textoAviso(LOTE)).toMatch(/^Ordené tus cuentas: moví 4 extractos/)
    expect(textoAviso({})).toBe('Ordené tus cuentas.')
    expect(textoPaso({ paso: ' Reviso que cuadre ' })).toBe('Reviso que cuadre')
    expect(textoPaso(null)).toBe('')
    expect(textoListo(LOTE)).toMatch(/^Listo, ordené tus cuentas: moví 4 extractos/)
  })

  it('conteo: solo lo que no es cero y con plurales', () => {
    expect(lineasConteo(LOTE.contadores)).toEqual([
      'Pasé 4 extractos a tu tarjeta', 'Corregí 31 compras que estaban como ingresos',
      'Registré 12 rendimientos e impuestos', 'Traje 1 movimiento comprobado de tus extractos',
    ])
    expect(lineasConteo({})).toEqual([])
  })
})

describe('corredor', () => {
  it('sigue llamando mientras diga trabajando y se detiene al estar listo', async () => {
    api.correrAutoarreglo
      .mockResolvedValueOnce({ estado: 'trabajando', progreso: { hecho: 1, total: 6 } })
      .mockResolvedValueOnce({ estado: 'trabajando', progreso: { hecho: 3, total: 6 } })
      .mockResolvedValueOnce(LISTO)
    await iniciar({ espera: 0 })
    expect(api.correrAutoarreglo).toHaveBeenCalledTimes(3)
  })

  it('una vez por sesión y por hora; "forzar" lo salta; una segunda llamada simultánea comparte la primera', async () => {
    api.correrAutoarreglo.mockResolvedValue({ ...LISTO, resumen: null })
    const a = iniciar({ espera: 0 })
    const b = iniciar({ espera: 0 })
    await Promise.all([a, b])
    expect(api.correrAutoarreglo).toHaveBeenCalledTimes(1)
    await iniciar({ espera: 0 })
    expect(api.correrAutoarreglo).toHaveBeenCalledTimes(1) // todavía no pasó una hora
    expect(tocaCorrer(Date.now() + INTERVALO_MS + 1000)).toBe(true)
    await iniciar({ forzar: true, espera: 0 })
    expect(api.correrAutoarreglo).toHaveBeenCalledTimes(2)
  })

  it('si el servidor falla no lanza ni molesta', async () => {
    api.correrAutoarreglo.mockRejectedValue(new Error('sin red'))
    await expect(iniciar({ espera: 0 })).resolves.toBeTruthy()
  })
})

describe('aviso', () => {
  it('mientras trabaja dice en qué paso va, sin bloquear', async () => {
    let soltar
    api.correrAutoarreglo
      .mockResolvedValueOnce({ estado: 'trabajando', progreso: { hecho: 1, total: 6 } })
      .mockImplementationOnce(() => new Promise((r) => { soltar = r }))
    montar()
    expect(await screen.findByRole('status')).toHaveTextContent('Ordenando tus cuentas: paso 2 de 6')
    await waitFor(() => expect(typeof soltar).toBe('function'), { timeout: 4000 }) // la segunda llamada llega tras la pausa corta
    await act(async () => { soltar({ ...LISTO, resumen: null }) })
    await waitFor(() => expect(screen.queryByTestId('autoarreglo-trabajando')).toBeNull())
  })

  it('al terminar cuenta lo que hizo; "Ver qué hice" abre el detalle con los saldos de antes y después', async () => {
    api.correrAutoarreglo.mockResolvedValue(LISTO)
    montar()
    const caja = await screen.findByTestId('autoarreglo-listo')
    expect(caja).toHaveTextContent('Ordené tus cuentas: moví 4 extractos a tu tarjeta, corregí 31 compras, registré 12 rendimientos e impuestos.')
    expect(within(caja).getByRole('button', { name: 'Deshacer' })).toBeInTheDocument()
    await userEvent.click(within(caja).getByRole('button', { name: 'Ver qué hice' }))
    const hoja = await screen.findByTestId('hoja-autoarreglo')
    expect(within(hoja).getByTestId('autoarreglo-saldos')).toHaveTextContent(/Nu Colombia: de \$\s?2\.700\.000 a \$\s?2\.706\.100/)
    expect(within(hoja).getByTestId('autoarreglo-conteo')).toHaveTextContent('Pasé 4 extractos a tu tarjeta')
  })

  it('Deshacer pide confirmar y revierte el lote', async () => {
    api.correrAutoarreglo.mockResolvedValue(LISTO)
    api.deshacerLoteAutoarreglo.mockResolvedValue({ ok: true, texto: 'Listo, deshice el arreglo: tus cuentas quedaron como estaban antes.' })
    montar()
    await userEvent.click(within(await screen.findByTestId('autoarreglo-listo')).getByRole('button', { name: 'Deshacer' }))
    expect(await screen.findByTestId('autoarreglo-confirmar')).toHaveTextContent('¿Deshacer todo lo que ordené?')
    expect(screen.getByTestId('autoarreglo-se-deshara')).toHaveTextContent('Pasé 4 extractos a tu tarjeta')
    expect(api.deshacerLoteAutoarreglo).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Sí, deshacer' }))
    await waitFor(() => expect(api.deshacerLoteAutoarreglo).toHaveBeenCalledWith('L1'))
    expect(await screen.findByText('Listo, deshice el arreglo: tus cuentas quedaron como estaban antes.')).toBeInTheDocument()
    expect(screen.queryByTestId('autoarreglo-listo')).toBeNull() // el aviso se va; la hoja se queda para decirlo
  })

  it('si deshacer no se puede (409) lo dice con palabras de la persona y no cambia nada', async () => {
    api.correrAutoarreglo.mockResolvedValue(LISTO)
    api.deshacerLoteAutoarreglo.mockRejectedValue(new Error('No pude deshacerlo: Un movimiento que corregí cambió después. Lo que hiciste después lo hace inconsistente; no cambié nada.'))
    montar()
    await userEvent.click(within(await screen.findByTestId('autoarreglo-listo')).getByRole('button', { name: 'Deshacer' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Sí, deshacer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/no cambié nada/i)
  })

  it('lo que necesita decisión sale con una acción de un toque', async () => {
    api.correrAutoarreglo.mockResolvedValue({
      ...LISTO, resumen: null,
      decisiones: [
        { tipo: 'dudosas', cantidad: 7, texto: 'Hay movimientos de tus extractos que no importé porque no estoy seguro.', accion: 'Revisarlos', ruta: '/sincronizacion' },
        { tipo: 'clave_pdf', cantidad: 1, texto: 'Me falta la clave de tus extractos en PDF para leerlos.', accion: 'Poner la clave', ruta: '/correos' },
      ],
    })
    montar()
    expect(await screen.findByTestId('autoarreglo-decision-dudosas')).toHaveTextContent('Tengo una duda con 7 movimientos. ¿Los revisamos?')
    expect(screen.getByTestId('autoarreglo-decision-dudosas')).toHaveTextContent('Revisar')
    expect(screen.queryByText(/dudosa/i)).toBeNull()
    expect(screen.getByTestId('autoarreglo-decision-clave_pdf')).toHaveTextContent('Poner la clave')
    expect(screen.queryByTestId('autoarreglo-listo')).toBeNull()
  })

  it('sin nada que decir no se ve nada', async () => {
    api.correrAutoarreglo.mockResolvedValue({ ...LISTO, resumen: null })
    const { container } = montar()
    await waitFor(() => expect(api.correrAutoarreglo).toHaveBeenCalled())
    await act(async () => {})
    expect(container).toBeEmptyDOMElement()
  })
})
