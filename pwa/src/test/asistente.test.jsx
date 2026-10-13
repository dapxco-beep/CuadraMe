import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({ api }))

import Asistente from '../screens/Asistente'

const CUENTAS = [
  { id: 'c1', nombre: 'Bancolombia' },
  { id: 'c2', nombre: 'Nequi' },
]

function montar() {
  return render(
    <MemoryRouter initialEntries={['/asistente']}>
      <Routes>
        <Route path="/asistente" element={<Asistente />} />
        <Route path="*" element={<p>otra</p>} />
      </Routes>
    </MemoryRouter>
  )
}

beforeEach(() => {
  api.asistenteSugerencias = vi.fn().mockResolvedValue({
    preguntas: [{ id: 'gasto_mes', texto: '¿En qué gasté más este mes?' }],
    oportunidades: [{ tipo: 'recurrentes', titulo: 'Tus gastos fijos suman $480.000 al año', detalle: 'Revisa.' }],
  })
  api.asistenteMensaje = vi.fn()
  api.asistenteConfirmarMovimiento = vi.fn().mockResolvedValue({ ok: true })
  api.asistenteConfirmarPlan = vi.fn().mockResolvedValue({ ok: true })
})

describe('CuadraMe AI', () => {
  it('muestra oportunidades y preguntas sugeridas; tocar una pregunta la envía y cita las fuentes', async () => {
    api.asistenteMensaje.mockResolvedValue({
      tipo: 'respuesta',
      texto: 'En octubre llevas $80.000.',
      fuentes: ['Tus movimientos de octubre de 2026 (3)'],
    })
    montar()
    expect(await screen.findByText('Tus gastos fijos suman $480.000 al año')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '¿En qué gasté más este mes?' }))
    expect(api.asistenteMensaje).toHaveBeenCalledWith('¿En qué gasté más este mes?')
    expect(await screen.findByText('En octubre llevas $80.000.')).toBeInTheDocument()
    expect(screen.getByText(/Basado en: Tus movimientos de octubre de 2026/)).toBeInTheDocument()
  })

  it('al abrir, las preguntas sugeridas van antes que los avisos y los avisos son máximo dos', async () => {
    api.asistenteSugerencias.mockResolvedValue({
      preguntas: [{ id: 'gasto_mes', texto: '¿En qué gasté más este mes?' }],
      oportunidades: [1, 2, 3, 4].map((n) => ({ tipo: 'alerta', titulo: `Aviso ${n}`, detalle: 'd' })),
    })
    montar()
    const pregunta = await screen.findByRole('button', { name: '¿En qué gasté más este mes?' })
    const primerAviso = await screen.findByText('Aviso 1')
    // la pregunta aparece antes en el documento que el primer aviso
    expect(pregunta.compareDocumentPosition(primerAviso) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByText('Aviso 2')).toBeInTheDocument()
    expect(screen.queryByText('Aviso 3')).toBeNull()
  })

  it('un movimiento propuesto NO se guarda hasta confirmar', async () => {
    api.asistenteMensaje.mockResolvedValue({
      tipo: 'propuesta_movimiento',
      texto: 'Esto es lo que entendí.',
      propuesta: { monto: 18000, tipo: 'expense', descripcion: 'Almuerzo', categoria: 'Comida', cuenta_id: 'c2', fecha: '2026-10-03T12:00:00' },
      cuentas: CUENTAS,
      fuentes: [],
    })
    montar()
    await userEvent.type(await screen.findByLabelText('Mensaje para CuadraMe AI'), 'Gasté 18.000 en almuerzo con Nequi')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    const tarjeta = await screen.findByRole('group', { name: 'Movimiento propuesto' })
    expect(tarjeta).toHaveTextContent('Almuerzo')
    expect(tarjeta).toHaveTextContent('18.000')
    expect(api.asistenteConfirmarMovimiento).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
    await waitFor(() => expect(api.asistenteConfirmarMovimiento).toHaveBeenCalledTimes(1))
    expect(api.asistenteConfirmarMovimiento).toHaveBeenCalledWith(
      expect.objectContaining({ cuenta_id: 'c2', monto: 18000, tipo: 'expense', descripcion: 'Almuerzo' })
    )
    expect(await screen.findByText('Movimiento guardado')).toBeInTheDocument()
  })

  it('cancelar la propuesta no llama al backend; sin cuenta pide elegirla', async () => {
    api.asistenteMensaje.mockResolvedValue({
      tipo: 'propuesta_movimiento',
      texto: 'Esto es lo que entendí.',
      propuesta: { monto: 5000, tipo: 'expense', descripcion: 'Tinto', categoria: 'Comida', cuenta_id: null, fecha: '2026-10-03T12:00:00' },
      cuentas: CUENTAS,
      fuentes: [],
    })
    montar()
    await userEvent.type(await screen.findByLabelText('Mensaje para CuadraMe AI'), 'gasté 5 mil en tinto')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    await screen.findByRole('group', { name: 'Movimiento propuesto' })
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(await screen.findByText('Elige la cuenta')).toBeInTheDocument()
    expect(api.asistenteConfirmarMovimiento).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(await screen.findByText(/no se guardó nada/)).toBeInTheDocument()
    expect(api.asistenteConfirmarMovimiento).not.toHaveBeenCalled()
  })

  it('simulación: muestra el veredicto y las cuotas calculadas por el backend', async () => {
    api.asistenteMensaje.mockResolvedValue({
      tipo: 'simulacion',
      texto: 'Alcanza, pero justo.',
      calculo: {
        veredicto: 'ajustado', precio: 4000000, disponible_real: 4000000, colchon_sugerido: 1500000,
        quedaria_disponible: 0, capacidad_ahorro_mensual: 1000000, meses_ahorrando: 2,
        tasa_mensual_referencia_pct: 2,
        cuotas: [{ plazo_meses: 12, cuota_con_interes: 378238, cabe_en_tu_capacidad: true }],
      },
      fuentes: ['Saldos de tus cuentas de ahorro y efectivo'],
    })
    montar()
    await userEvent.type(await screen.findByLabelText('Mensaje para CuadraMe AI'), '¿Puedo comprar un celular de 4 millones?')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    const detalle = await screen.findByLabelText('Detalle del cálculo')
    expect(detalle).toHaveTextContent('Alcanza, pero justo')
    expect(detalle).toHaveTextContent('378.238')
    expect(detalle).toHaveTextContent('2 meses')
  })

  it('plan: aceptar crea la meta con la cuenta opcional; los errores se muestran', async () => {
    api.asistenteMensaje.mockResolvedValue({
      tipo: 'plan',
      texto: 'Necesitas apartar $1.000.000 al mes.',
      calculo: { objetivo: 12000000, aporte_mensual: 1000000, meses: 12, viable: true },
      accion: { tipo: 'crear_meta', nombre: 'Ahorrar $12.000.000', monto_objetivo: 12000000, fecha_objetivo: '2027-10-31T00:00:00', aporte_mensual: 1000000 },
      cuentas: CUENTAS,
      fuentes: [],
    })
    api.asistenteConfirmarPlan.mockRejectedValueOnce(new Error('Cuenta de origen no encontrada'))
    montar()
    await userEvent.type(await screen.findByLabelText('Mensaje para CuadraMe AI'), 'ahorrar 12 millones en 12 meses')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    await screen.findByRole('group', { name: 'Plan propuesto' })
    await userEvent.click(screen.getByRole('button', { name: 'Aceptar plan' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Cuenta de origen no encontrada')

    await userEvent.selectOptions(screen.getByRole('combobox'), 'c1')
    await userEvent.click(screen.getByRole('button', { name: 'Aceptar plan' }))
    await waitFor(() => expect(api.asistenteConfirmarPlan).toHaveBeenCalledTimes(2))
    expect(api.asistenteConfirmarPlan).toHaveBeenLastCalledWith(
      expect.objectContaining({ nombre: 'Ahorrar $12.000.000', monto_objetivo: 12000000, cuenta_origen_id: 'c1' })
    )
    expect(await screen.findByText(/Meta creada/)).toBeInTheDocument()
  })

  it('un error del servicio se muestra como mensaje genérico, sin romper la pantalla', async () => {
    api.asistenteMensaje.mockRejectedValue(new Error('Llegaste al límite diario del asistente. Vuelve mañana.'))
    montar()
    await userEvent.type(await screen.findByLabelText('Mensaje para CuadraMe AI'), 'hola')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    expect(await screen.findByText('Llegaste al límite diario del asistente. Vuelve mañana.')).toBeInTheDocument()
  })
})
