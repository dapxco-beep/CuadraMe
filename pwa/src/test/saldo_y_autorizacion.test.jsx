// Saldo actual claro (etiquetas, tarjetas, ajuste), autorización de datos y aviso de Gmail por invitación.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  detalleCuenta: vi.fn(),
  ajustarSaldo: vi.fn(),
  guardarConsentimientos: vi.fn(),
  consentimientos: vi.fn(),
  historialConsentimientos: vi.fn(),
  gmailEstado: vi.fn(),
  gmailConectar: vi.fn(),
  correosPendientes: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  sincronizarCorreos: vi.fn(),
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Efectivo' }], cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/AuthContext', () => ({
  useAuth: () => ({ usuario: { email: 'yo@gmail.com', nombre: 'Yo' }, logout: vi.fn() }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import TarjetaCuenta from '../components/TarjetaCuenta'
import DetalleCuenta from '../components/DetalleCuenta'
import ResumenSaldo from '../components/ResumenSaldo'
import AutorizacionTratamiento from '../screens/AutorizacionTratamiento'
import SeccionPrivacidad from '../components/SeccionPrivacidad'
import Sincronizacion from '../screens/Sincronizacion'
import { textoActualizado } from '../lib/saldos'

const AHORRO = { id: 'c1', nombre: 'Bancolombia', tipo: 'ahorro', saldo: 1500000, moneda: 'COP' }
const TC = {
  id: 't1', nombre: 'Visa', tipo: 'credito', saldo: -800000, moneda: 'COP',
  tarjeta: { cupo_usado: 800000, cupo_disponible: 2200000 },
}

const envolver = (ui, ruta = '/') => render(<DialogosProvider><MemoryRouter initialEntries={[ruta]}>{ui}</MemoryRouter></DialogosProvider>)

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
})

describe('Saldo actual claro', () => {
  it('la tarjeta de cuenta rotula el saldo y dice cuándo se actualizó', () => {
    envolver(<TarjetaCuenta cuenta={AHORRO} ultimoMovimiento="2026-10-03T10:00:00" />)
    expect(screen.getByText('Saldo actual')).toBeInTheDocument()
    expect(screen.getByText(/1\.500\.000/)).toBeInTheDocument()
    expect(screen.getByText(/último movimiento|actualizado hoy/)).toBeInTheDocument()
  })

  it('una tarjeta de crédito muestra "Debes" en positivo y el disponible del cupo, nunca el saldo negativo', () => {
    envolver(<TarjetaCuenta cuenta={TC} />)
    expect(screen.getByText('Debes')).toBeInTheDocument()
    expect(screen.queryByText('Saldo actual')).toBeNull()
    expect(screen.getByText(/800\.000/)).toBeInTheDocument()
    expect(screen.queryByText(/-\s?\$?\s?800/)).toBeNull()
    expect(screen.getByText(/Cupo disponible .*2\.200\.000/)).toBeInTheDocument()
  })

  it('tarjeta con saldo positivo dice "Saldo a favor", sin "+" ni cupo disponible', () => {
    envolver(<TarjetaCuenta cuenta={{ ...TC, saldo: 50000, tarjeta: { cupo_disponible: 3000000 } }} />)
    expect(screen.getByText('Saldo a favor')).toBeInTheDocument()
    expect(screen.queryByText('Debes')).toBeNull()
    expect(screen.getByText(/50.000/)).toBeInTheDocument()
    expect(screen.queryByText(/Cupo disponible/)).toBeNull()
    expect(screen.queryByText(/+/)).toBeNull()
  })

  it('tarjeta sin cupo definido no inventa cupo disponible', () => {
    envolver(<TarjetaCuenta cuenta={{ id: 't2', nombre: 'Visa', tipo: 'credito', saldo: -100000, moneda: 'COP' }} />)
    expect(screen.getByText('Debes')).toBeInTheDocument()
    expect(screen.queryByText(/Cupo disponible/)).toBeNull()
  })

  it('textoActualizado distingue hoy, ayer, fecha y sin movimientos', () => {
    const hoy = new Date(2026, 9, 3)
    expect(textoActualizado('2026-10-03T08:00:00', hoy)).toBe('actualizado hoy')
    expect(textoActualizado('2026-10-02T23:00:00', hoy)).toBe('último movimiento: ayer')
    expect(textoActualizado('2026-09-20T08:00:00', hoy)).toBe('último movimiento: 20 sep')
    expect(textoActualizado(null, hoy)).toBe('sin movimientos aún')
  })

  it('el desglose alterna total / por moneda / por tipo', async () => {
    const resumen = {
      disponible_cop: 1900000, deudas_tarjeta_cop: 300000,
      por_moneda: { COP: 1600000, USD: 50 }, por_tipo: { ahorro: 1900000, credito: -300000 },
    }
    envolver(<ResumenSaldo resumen={resumen} bolsillo={{ recurrentes_pendientes_mes: 100000, aportes_comprometidos_mes: 50000 }} />)
    expect(screen.getByText(/Disponible hoy/)).toBeInTheDocument()
    expect(screen.getByText(/Comprometido este mes/)).toBeInTheDocument()
    expect(screen.getByText(/Deudas de tarjeta/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Por moneda' }))
    expect(screen.getByText('USD')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Por tipo' }))
    expect(screen.getByText('Tarjetas de crédito')).toBeInTheDocument()
  })

  it('ajustar saldo: muestra la vista previa, avisa que no cuenta como gasto y llama al backend', async () => {
    api.detalleCuenta.mockResolvedValue({
      cuenta: AHORRO, saldo_actual: 1500000, ingresos_mes: 2000000, gastos_mes: 100000,
      ultimo_movimiento: '2026-10-03T10:00:00', movimientos: [],
    })
    api.ajustarSaldo.mockResolvedValue({ ok: true })
    envolver(<DetalleCuenta cuentaId="c1" onClose={() => {}} />)
    expect(await screen.findByTestId('saldo-detalle')).toHaveTextContent('1.500.000')
    expect(screen.getByText('Comparar con mi banco')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Ajustar saldo/ }))
    fireEvent.change(screen.getByLabelText('Saldo real'), { target: { value: '1300000' } })
    expect(screen.getByTestId('vista-previa-ajuste')).toHaveTextContent(/-.*200\.000.*No cuenta como gasto ni ingreso/)
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar ajuste' }))
    await waitFor(() => expect(api.ajustarSaldo).toHaveBeenCalledWith('c1', 1300000))
  })

  it('ajustar una tarjeta: lo que escribes es lo que DEBES y se envía en negativo', async () => {
    api.detalleCuenta.mockResolvedValue({ cuenta: TC, saldo_actual: -800000, ingresos_mes: 0, gastos_mes: 0, ultimo_movimiento: null, movimientos: [] })
    api.ajustarSaldo.mockResolvedValue({ ok: true })
    envolver(<DetalleCuenta cuentaId="t1" onClose={() => {}} />)
    await screen.findByTestId('saldo-detalle')
    await userEvent.click(screen.getByRole('button', { name: /Ajustar saldo/ }))
    fireEvent.change(screen.getByLabelText('Lo que debes hoy'), { target: { value: '1000000' } })
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar ajuste' }))
    await waitFor(() => expect(api.ajustarSaldo).toHaveBeenCalledWith('t1', -1000000))
  })

  it('cuenta sin movimientos explica qué es el saldo', async () => {
    api.detalleCuenta.mockResolvedValue({ cuenta: AHORRO, saldo_actual: 0, ingresos_mes: 0, gastos_mes: 0, ultimo_movimiento: null, movimientos: [] })
    envolver(<DetalleCuenta cuentaId="c1" onClose={() => {}} />)
    expect(await screen.findByText(/aún no tiene movimientos/)).toBeInTheDocument()
  })
})

describe('Autorización de tratamiento de datos', () => {
  it('casillas separadas y sin premarcar; solo la obligatoria habilita continuar', async () => {
    api.guardarConsentimientos.mockResolvedValue({})
    const listo = vi.fn()
    envolver(<AutorizacionTratamiento onListo={listo} />)
    const boxes = screen.getAllByRole('checkbox')
    expect(boxes).toHaveLength(5)
    boxes.forEach((b) => expect(b).not.toBeChecked())
    const continuar = screen.getByRole('button', { name: 'Aceptar y continuar' })
    expect(continuar).toBeDisabled()
    expect(screen.getByText(/borrador pendiente de revisión por un abogado/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Términos y Condiciones' })).toBeInTheDocument()
    await userEvent.click(boxes[0]) // obligatoria
    expect(continuar).toBeEnabled()
    await userEvent.click(boxes[2]) // IA
    await userEvent.click(continuar)
    await waitFor(() => expect(listo).toHaveBeenCalled())
    const [version, items] = api.guardarConsentimientos.mock.calls[0]
    expect(version).toBe('1.1')
    expect(items).toEqual([
      { finalidad: 'tratamiento_basico', aceptado: true },
      { finalidad: 'lectura_correo', aceptado: false },
      { finalidad: 'ia', aceptado: true },
      { finalidad: 'notificaciones', aceptado: false },
      { finalidad: 'estadisticas_anonimas', aceptado: false }, // opcional y apagada por defecto
    ])
  })

  it('Perfil: revocar una autorización opcional registra aceptado=false', async () => {
    const f = (aceptado) => ({ aceptado, version: '1.1', fecha_co: '2026-10-03T09:00:00' })
    api.consentimientos.mockResolvedValue({
      finalidades: { tratamiento_basico: f(true), lectura_correo: f(false), ia: f(true), notificaciones: f(false) },
    })
    api.guardarConsentimientos.mockResolvedValue({})
    envolver(<SeccionPrivacidad onEliminarCuenta={() => {}} />)
    const interruptor = await screen.findByRole('switch', { name: /inteligencia artificial/ })
    expect(interruptor).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText('Descargar mis datos')).toBeInTheDocument()
    expect(screen.getByText('Borrar mi cuenta y todos mis datos')).toBeInTheDocument()
    await userEvent.click(interruptor)
    await userEvent.click(await screen.findByRole('button', { name: 'Revocar' }))
    await waitFor(() => expect(api.guardarConsentimientos).toHaveBeenCalledWith('1.1', [{ finalidad: 'ia', aceptado: false }], 'perfil'))
  })
})

describe('Gmail por invitación y consentimiento', () => {
  function montarCorreos(estado, ruta = '/sincronizacion') {
    api.sincronizacionEstado.mockResolvedValue({ meses: [], cuentas: [], sin_cuenta: [], tareas: [], ultima_sync: null })
    api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 0 })
    api.extractosCorreo.mockResolvedValue([])
    api.clavePdfEstado.mockResolvedValue({})
    api.gmailEstado.mockResolvedValue({ conectado: false, etiqueta: 'gastos', ...estado })
    api.correosPendientes.mockResolvedValue([])
    return envolver(<Sincronizacion />, ruta)
  }

  it('si Google devolvió sin_acceso muestra el mensaje amable con mailto al soporte', async () => {
    montarCorreos({ modo_pruebas: true, soporte_email: 'ayuda@cuadrame.test', consentimiento: true }, '/sincronizacion?gmail=sin_acceso')
    expect(await screen.findByText('Gmail aún es por invitación')).toBeInTheDocument()
    expect(screen.getByText(/Google no te dejó entrar/)).toBeInTheDocument()
    const pedir = screen.getByRole('link', { name: 'Pedir acceso' })
    expect(pedir.getAttribute('href')).toMatch(/^mailto:ayuda@cuadrame\.test\?/)
    expect(decodeURIComponent(pedir.getAttribute('href'))).toContain('yo@gmail.com')
    expect(screen.getByRole('button', { name: /Copiar mi correo/ })).toBeInTheDocument()
  })

  it('sin la autorización de lectura de correo no conecta: pide el consentimiento primero', async () => {
    montarCorreos({ modo_pruebas: false, consentimiento: false })
    // Primero el asistente: el paso «Conecta tu Gmail» abre «Conexiones y claves», donde está el botón de conectar.
    await userEvent.click(await screen.findByTestId('tarea-conectar'))
    const hoja = await screen.findByRole('dialog', { name: 'Conexiones y claves' })
    await userEvent.click(within(hoja).getByRole('button', { name: 'Conectar Gmail' }))
    expect(api.gmailConectar).not.toHaveBeenCalled()
    expect(await screen.findByText('Leer mi correo (Gmail, solo lectura)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Autorizo' })).toBeDisabled() // casilla sin marcar
  })

  it('con la autorización dada no muestra el aviso de invitación si ya no está en modo pruebas', async () => {
    montarCorreos({ modo_pruebas: false, consentimiento: true })
    await screen.findAllByRole('button', { name: 'Conectar Gmail' })
    expect(screen.queryByTestId('aviso-invitacion')).toBeNull()
  })
})
