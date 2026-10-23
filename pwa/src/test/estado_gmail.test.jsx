// Estado de Gmail y de la lectura de extractos: línea, avisos de extracto faltante, «aprendiendo». Datos inventados.
import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import EstadoGmail from '../components/EstadoGmail'
import {
  bancosAprendiendo, extractosFaltantes, fechaCorta, lineaGmail, resumenEstadoGmail, ultimoExtractoLeido,
} from '../lib/estadoGmail'

const HOY = new Date(2026, 9, 23) // 23 oct 2026
const HIST = [
  { estado: 'importado', banco_detectado: 'Nu', fecha_corte: '2026-10-15', creado_en: '2026-10-16T09:00:00' },
  { estado: 'importado', banco_detectado: 'Nu', fecha_corte: '2026-09-15', creado_en: '2026-09-16T09:00:00' },
  { estado: 'error', banco_detectado: 'X', fecha_corte: '2026-10-20' },
]
const CUENTAS = [
  { id: 'a', nombre: 'Nu', tipo: 'ahorro', meses: [{ mes: '2026-08', estado: 'conciliado' }, { mes: '2026-09', estado: 'sin_extracto', movimientos: 8 }, { mes: '2026-10', estado: 'sin_extracto', movimientos: 3 }] },
  { id: 'e', nombre: 'Efectivo', tipo: 'efectivo', meses: [{ mes: '2026-09', estado: 'sin_extracto' }] },
]

describe('lib/estadoGmail', () => {
  it('fecha corta sin correr el día y vacía si no es fecha', () => {
    expect(fechaCorta('2026-10-15T00:00:00')).toBe('15 oct')
    expect(fechaCorta('basura')).toBe('')
  })
  it('último extracto leído: el más reciente sin contar los que dieron error', () => {
    expect(ultimoExtractoLeido(HIST)).toEqual({ fecha: '2026-10-15', banco: 'Nu' })
    expect(ultimoExtractoLeido([])).toBeNull()
    expect(ultimoExtractoLeido(null)).toBeNull()
  })
  it('línea de Gmail: conectado con fecha, sin extractos, sin conectar y desconocido', () => {
    expect(lineaGmail({ conectado: true }, { fecha: '2026-10-15' })).toBe('Gmail conectado · último extracto leído: 15 oct')
    expect(lineaGmail({ conectado: true }, null)).toBe('Gmail conectado · aún no he leído extractos')
    expect(lineaGmail({ conectado: false }, null)).toBe('Gmail sin conectar')
    expect(lineaGmail(null, null)).toBeNull()
  })
  it('falta el extracto del mes cerrado; el mes en curso y el efectivo no cuentan', () => {
    const f = extractosFaltantes(CUENTAS, HOY)
    expect(f).toHaveLength(1)
    expect(f[0].texto).toBe('Falta el extracto de septiembre de Nu')
    expect(extractosFaltantes([{ id: 'a', nombre: 'Nu', tipo: 'ahorro', meses: [{ mes: '2026-09', estado: 'conciliado' }] }], HOY)).toEqual([])
    expect(extractosFaltantes(undefined, HOY)).toEqual([])
  })
  it('aprendiendo: por estado_aprendizaje o por el mensaje del backend; si no existe el campo no rompe', () => {
    expect(bancosAprendiendo([{ banco_detectado: 'Bancolombia', estado_aprendizaje: 'aprendiendo' }])).toEqual(['Bancolombia'])
    expect(bancosAprendiendo([{ banco_detectado: 'Nu', mensaje_lectura: 'No leí completo. Mándame el extracto para aprender su formato.' }])).toEqual(['Nu'])
    expect(bancosAprendiendo([{ banco_detectado: 'Nu', estado_aprendizaje: 'listo' }, { estado: 'importado' }, null])).toEqual([])
    expect(bancosAprendiendo(undefined)).toEqual([])
  })
  it('resumen sin Gmail conectado no avisa de extractos', () => {
    const r = resumenEstadoGmail({ gmail: { conectado: false }, historial: HIST, cuentas: CUENTAS, hoy: HOY })
    expect(r.avisos).toEqual([])
    expect(resumenEstadoGmail().linea).toBeNull()
  })
})

describe('<EstadoGmail>', () => {
  it('muestra la línea, el aviso amable y que estamos aprendiendo', async () => {
    api.historialExtractos = vi.fn().mockResolvedValue([...HIST, { banco_detectado: 'Davivienda', estado_aprendizaje: 'aprendiendo' }])
    render(<EstadoGmail gmail={{ conectado: true }} cuentas={CUENTAS} />)
    expect(await screen.findByText(/último extracto leído: 15 oct/)).toBeInTheDocument()
    expect(screen.getByTestId('aviso-falta-extracto')).toHaveTextContent('Falta el extracto de septiembre de Nu')
    expect(await screen.findByTestId('aprendiendo-formato')).toHaveTextContent('Estamos aprendiendo el formato de tu banco; no tienes que hacer nada')
  })
  it('estado de error del historial: sigue mostrando Gmail sin fecha ni romper', async () => {
    api.historialExtractos = vi.fn().mockRejectedValue(new Error('sin red'))
    render(<EstadoGmail gmail={{ conectado: true }} cuentas={[]} />)
    expect(await screen.findByText('Gmail conectado · aún no he leído extractos')).toBeInTheDocument()
    await waitFor(() => expect(api.historialExtractos).toHaveBeenCalled())
    expect(screen.queryByTestId('aviso-falta-extracto')).toBeNull()
    expect(screen.queryByTestId('aprendiendo-formato')).toBeNull()
  })
  it('estado vacío: sin dato de Gmail no pinta nada; sin api.historialExtractos tampoco rompe', () => {
    delete api.historialExtractos
    const { container } = render(<EstadoGmail gmail={null} cuentas={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
