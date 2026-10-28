// Importar Excel/CSV, regla contable en cliente, Impuestos, Cierre de mes y textos legales.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const CUENTAS = [{ id: 'c1', nombre: 'Banco', saldo: 0, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]

const api = vi.hoisted(() => ({
  importarVistaPrevia: vi.fn(),
  importarConfirmar: vi.fn(),
  impuestosResumen: vi.fn(),
  impuestosAjustes: vi.fn(),
  impuestosMarcar: vi.fn(),
  impuestosQuitarMarca: vi.fn(),
  impuestosExcel: vi.fn(),
  cierresMes: vi.fn(),
  cierreMes: vi.fn(),
  generarCierreMes: vi.fn(),
  cierrePreferencias: vi.fn(),
  guardarCierrePreferencias: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ nombres: ['Comida', 'Otros'], iconoDe: () => '🏷️' }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { esPagoTarjeta, tipoEfectivo } from '../lib/contabilidad'
import { construirFilas, efectoSaldo, extensionValida, seleccionInicial } from '../lib/importar'
import ImportarArchivo from '../screens/ImportarArchivo'
import Impuestos from '../screens/Impuestos'
import CierreMes from '../screens/CierreMes'
import TerminosCondiciones from '../screens/legal/TerminosCondiciones'
import PoliticaPrivacidad from '../screens/legal/PoliticaPrivacidad'
import AutorizacionDatos from '../screens/legal/AutorizacionDatos'

const montar = (ui) => render(<DialogosProvider><MemoryRouter>{ui}</MemoryRouter></DialogosProvider>)

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  api.cierrePreferencias.mockResolvedValue({ correo: false })
})

describe('regla contable en cliente', () => {
  it('el pago de tarjeta y los traslados no son gasto ni ingreso', () => {
    expect(esPagoTarjeta('Pago tarjeta Visa')).toBe(true)
    expect(esPagoTarjeta('Pago con tarjeta en Éxito')).toBe(false)
    expect(tipoEfectivo({ tipo: 'expense', descripcion: 'Pago tarjeta Visa', categoria: 'Deudas' })).toBe('transfer')
    expect(tipoEfectivo({ tipo: 'expense', descripcion: 'Mercado', categoria: 'Comida' })).toBe('expense')
    expect(tipoEfectivo({ tipo: 'transfer', descripcion: 'x', categoria: 'x' })).toBe('transfer')
    expect(tipoEfectivo({ tipo: 'income', cuenta_id: 't', descripcion: 'Abono', categoria: 'Otros' }, { t: 'credito' })).toBe('transfer')
    expect(tipoEfectivo({ tipo: 'income', cuenta_id: 'c1', descripcion: 'Nómina', categoria: 'Ingresos' }, { c1: 'ahorro' })).toBe('income')
  })
})

describe('lógica de importación', () => {
  const propuesta = [
    { fila: 1, fecha: '2026-10-01', descripcion: 'A', monto: 100, tipo: 'expense', categoria: 'Comida', estado: 'nuevo' },
    { fila: 2, fecha: '2026-10-02', descripcion: 'B', monto: 500, tipo: 'income', categoria: 'Otros', estado: 'posible_duplicado' },
    { fila: 3, fecha: '2026-10-03', descripcion: 'C', monto: 70, tipo: 'expense', categoria: 'Otros', estado: 'duplicado' },
  ]
  it('solo preselecciona los nuevos y nunca envía los ya registrados', () => {
    const sel = seleccionInicial(propuesta)
    expect([...sel]).toEqual([1])
    const todos = new Set([1, 2, 3])
    const filas = construirFilas(propuesta, todos, { 1: 'Comida', 2: 'Otros', 3: 'Otros' })
    expect(filas.map((f) => f.descripcion)).toEqual(['A', 'B'])
    expect(efectoSaldo(filas)).toBe(400) // +500 - 100
  })
  it('valida extensiones', () => {
    expect(extensionValida('x.XLSX')).toBe(true)
    expect(extensionValida('x.pdf')).toBe(false)
  })
})

describe('pantalla Importar', () => {
  it('muestra vista previa, deja desmarcar y confirma solo lo elegido', async () => {
    api.importarVistaPrevia.mockResolvedValue({
      fila_encabezado: 0, total_filas: 2, hojas: [], truncado: false, errores: [],
      columnas: [{ indice: 0, nombre: 'Fecha' }, { indice: 1, nombre: 'Detalle' }, { indice: 2, nombre: 'Valor' }],
      muestra: [['01/10/2026', 'Mercado', '-45.000']],
      mapeo: { fecha: 0, descripcion: 1, monto: 2, debito: null, credito: null, saldo: null, tipo: null },
      opciones: { separador_decimal: 'coma', orden_fecha: 'dmy', invertir_signo: false },
      resumen: { nuevos: 2, duplicados: 0, posibles_duplicados: 0, con_error: 0 },
      propuesta: [
        { fila: 1, fecha: '2026-10-01', descripcion: 'Mercado', monto: 45000, tipo: 'expense', categoria: 'Comida', estado: 'nuevo' },
        { fila: 2, fecha: '2026-10-02', descripcion: 'Nómina', monto: 2000000, tipo: 'income', categoria: 'Otros', estado: 'nuevo' },
      ],
    })
    api.importarConfirmar.mockResolvedValue({ ok: true, importados: 1, duplicados_omitidos: 0, saldo: 0 })
    montar(<ImportarArchivo />)
    const file = new File(['Fecha,Detalle,Valor\n'], 'extracto.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText('Archivo a importar'), { target: { files: [file] } })
    expect((await screen.findAllByText('Mercado')).length).toBeGreaterThan(0)
    expect(screen.getByText('Importar (2)')).toBeTruthy()
    fireEvent.click(screen.getByLabelText('Importar Nómina'))
    fireEvent.click(screen.getByText('Importar (1)'))
    await waitFor(() => expect(api.importarConfirmar).toHaveBeenCalled())
    const enviado = api.importarConfirmar.mock.calls[0][0]
    expect(enviado.filas).toHaveLength(1)
    expect(enviado.filas[0]).toMatchObject({ descripcion: 'Mercado', monto: 45000, tipo: 'expense', categoria: 'Comida' })
    expect(await screen.findByText(/1 movimiento importado/)).toBeTruthy()
  })

  it('rechaza formatos no soportados sin llamar al servidor', async () => {
    montar(<ImportarArchivo />)
    const pdf = new File(['x'], 'a.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText('Archivo a importar'), { target: { files: [pdf] } })
    expect(await screen.findByRole('alert')).toHaveTextContent('Formato no soportado')
    expect(api.importarVistaPrevia).not.toHaveBeenCalled()
  })
})

describe('pantalla Impuestos', () => {
  const datos = {
    anio: 2026, aviso: 'Información de apoyo, no asesoría tributaria.',
    gmf: { total_estimado: 6000, total_registrado: 0, promedio_mensual: 6000, tope_exento_mensual: 18330900, nota: 'nota', meses: [{ mes: '2026-10', gmf_estimado: 6000 }] },
    cuenta_exenta_gmf_id: null, cuentas_ahorro: [{ id: 'c1', nombre: 'Banco' }],
    deducibles: {
      total_confirmado: 0, total_sugerido: 300000,
      por_categoria: [{ categoria_fiscal: 'salud', etiqueta: 'Salud', ayuda: 'ayuda', confirmado: 0, sugerido: 300000, cantidad: 1 }],
      items: [{ movimiento_id: 'm1', fecha: '2026-05-01', descripcion: 'Colsanitas', monto: 300000, categoria_fiscal: 'salud', estado: 'sugerido', soporte: '' }],
    },
  }
  it('muestra el aviso, el 4x1000 y permite confirmar con soporte', async () => {
    api.impuestosResumen.mockResolvedValue(datos)
    api.impuestosMarcar.mockResolvedValue({ ok: true })
    montar(<Impuestos />)
    expect(await screen.findByText(/no asesoría tributaria/)).toBeTruthy()
    expect(screen.getByText('Colsanitas')).toBeTruthy()
    fireEvent.click(screen.getByText('Confirmar'))
    fireEvent.change(screen.getByLabelText('Nota de soporte'), { target: { value: 'Factura en Drive' } })
    fireEvent.click(screen.getByText('Guardar como posible deducible'))
    await waitFor(() => expect(api.impuestosMarcar).toHaveBeenCalledWith('m1', {
      categoria_fiscal: 'salud', soporte: 'Factura en Drive', estado: 'confirmada',
    }))
  })
  it('guarda la cuenta exenta', async () => {
    api.impuestosResumen.mockResolvedValue(datos)
    api.impuestosAjustes.mockResolvedValue({ ok: true })
    montar(<Impuestos />)
    await screen.findByText('Colsanitas')
    fireEvent.change(screen.getByLabelText('Cuenta exenta del 4x1000'), { target: { value: 'c1' } })
    await waitFor(() => expect(api.impuestosAjustes).toHaveBeenCalledWith('c1'))
  })
})

describe('pantalla Cierre de mes', () => {
  const informe = {
    titulo: 'Cierre de septiembre de 2026', resumen_corto: 'Ingresaste $2.000.000.', ingresos: 2000000, gastos: 500000,
    ahorro: 1500000, tasa_ahorro: 75, intereses_pagados: 0, patrimonio: null,
    categoria_que_mas_subio: { categoria: 'Comida', monto: 400000, monto_anterior: 300000, aumento: 100000, variacion_pct: 33.3 },
    acciones: ['Revisa Comida'],
  }
  it('muestra el informe guardado y deja activar el correo', async () => {
    api.cierresMes.mockResolvedValue([{ mes: '2026-09', visto: false }])
    api.cierreMes.mockResolvedValue(informe)
    api.guardarCierrePreferencias.mockResolvedValue({ ok: true })
    montar(<CierreMes />)
    expect(await screen.findByText('Lo que más subió: Comida')).toBeTruthy()
    expect(screen.getByText('Revisa Comida')).toBeTruthy()
    fireEvent.click(screen.getByRole('checkbox'))
    await waitFor(() => expect(api.guardarCierrePreferencias).toHaveBeenCalledWith(true))
  })
  it('ofrece generar el cierre si aún no existe', async () => {
    api.cierresMes.mockResolvedValue([])
    api.cierreMes.mockRejectedValue(new Error('404'))
    api.generarCierreMes.mockResolvedValue(informe)
    montar(<CierreMes />)
    fireEvent.click(await screen.findByRole('button', { name: /Paso 4/ })) // el cierre se genera en el último paso
    fireEvent.click(await screen.findByText('Generar cierre'))
    expect(await screen.findByText('Revisa Comida')).toBeTruthy()
  })
})

describe('textos legales', () => {
  it('reflejan lo nuevo y conservan el aviso de borrador y la versión', () => {
    const { unmount: u1 } = montar(<PoliticaPrivacidad />)
    expect(screen.getByText(/Versión 1.2 \(borrador\)/)).toBeTruthy()
    expect(screen.getByText(/Asistente de IA/)).toBeTruthy()
    expect(screen.getByText(/Clave del PDF/)).toBeTruthy()
    expect(screen.getByText(/borrador preparado/)).toBeTruthy()
    u1()
    const { unmount: u2 } = montar(<TerminosCondiciones />)
    expect(screen.getByText(/no presta asesoría tributaria/)).toBeTruthy()
    expect(screen.getByText(/borrador preparado/)).toBeTruthy()
    u2()
    montar(<AutorizacionDatos />)
    expect(screen.getByText(/datos de terceros/)).toBeTruthy()
    expect(screen.getByText(/borrador preparado/)).toBeTruthy()
  })
})
