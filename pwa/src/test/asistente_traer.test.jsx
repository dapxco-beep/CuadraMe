// «Traer movimientos» como asistente: una acción a la vez, avance solo al siguiente paso y trabajo automático al abrir.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [{ id: 'nu', nombre: 'Nu Colombia', saldo: 0, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }]

const api = vi.hoisted(() => ({
  sincronizacionEstado: vi.fn(),
  sincronizacionPorCategorizar: vi.fn(),
  gmailEstado: vi.fn(),
  extractosCorreo: vi.fn(),
  clavePdfEstado: vi.fn(),
  probarClavePdf: vi.fn(),
  sincronizarCorreos: vi.fn(),
  obtenerReviewExtracto: vi.fn(),
  correosPendientes: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn() }),
}))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ nombres: ['Otros'], iconoDe: () => '' }) }))

import { DialogosProvider } from '../lib/DialogosContext'
import Sincronizacion from '../screens/Sincronizacion'

const base = (extra = {}) => ({
  meses: [], cuentas: [], sin_cuenta: [], tareas: [], ultima_sync: '2026-10-05T10:00:00',
  punto_partida: { definido: true, modo: 'hoy', fecha: '2026-10-01', anteriores: { correos: 0, extractos: 0 } },
  ...extra,
})
const tarea = (id, cantidad = 1, extra = {}) => ({ id, titulo: id, detalle: '', cantidad, ruta: '/x', ...extra })
const aMedias = {
  todos_extractos: {
    items: [{
      id: 'h:h1', extracto_id: null, historial_id: 'h1', cuenta_id: 'nu', cuenta: 'Nu Colombia', banco: 'Nu', tipo: 'cuenta', mes: '2026-08', mes_etiqueta: 'Agosto 2026',
      titulo: 'Nu · Agosto 2026', estado_vista: 'por_revisar', estado_etiqueta: 'Por revisar', por_revisar: 3, copias: 1, acciones: ['revisar'],
    }],
    contadores: { por_revisar: 1 }, resumen: '1 por revisar', sin_adjunto: [],
  },
}

const montar = (modo) => render(
  <DialogosProvider>
    <MemoryRouter initialEntries={['/sincronizacion']}>
      <Routes><Route path="/sincronizacion" element={<Sincronizacion modo={modo} />} /></Routes>
    </MemoryRouter>
  </DialogosProvider>,
)

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('cuadrame_gmail_sync', String(Date.now())) // recién leído: no hay lectura automática salvo que el test la pida
  Object.values(api).forEach((f) => f.mockReset())
  api.sincronizacionPorCategorizar.mockResolvedValue({ items: [], total: 0 })
  api.gmailEstado.mockResolvedValue({ conectado: true, email: 'yo@gmail.com' })
  api.extractosCorreo.mockResolvedValue([])
  api.clavePdfEstado.mockResolvedValue({})
  api.correosPendientes.mockResolvedValue([])
})

describe('asistente de «Traer movimientos»', () => {
  it('un extracto a medias es el paso principal y «Seguir» abre exactamente esa revisión', async () => {
    api.sincronizacionEstado.mockResolvedValue(base(aMedias))
    api.obtenerReviewExtracto.mockResolvedValue({
      ok: true, historial_id: 'h1', cuenta_id: 'nu', banco_detectado: 'Nu', total_movimientos: 1,
      review: [{ fingerprint: 'f1', fecha: '2026-08-02', descripcion: 'Compra', monto: 1000, tipo: 'expense', estado: 'faltante' }],
    })
    montar()
    expect(await screen.findByTestId('paso-titulo')).toHaveTextContent('Sigue con tu extracto de agosto')
    expect(screen.getByText('Nu Colombia: faltan importar 3 movimientos.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^Seguir/ }))
    expect(await screen.findByTestId('revision-multiple')).toBeTruthy()
    expect(api.obtenerReviewExtracto).toHaveBeenCalledWith('h1')
  })

  it('al resolverse un paso aparece «Listo ✓ — siguiente:» y el contador avanza', async () => {
    api.sincronizacionEstado.mockResolvedValueOnce(base({ tareas: [tarea('falta_clave'), tarea('extractos_por_conciliar', 2)] }))
    api.sincronizarCorreos.mockResolvedValue({ ok: true, completado: true, nuevos: 0, extractos_encontrados: 0 })
    montar()
    expect(await screen.findByTestId('progreso-pasos')).toHaveTextContent('Paso 1 de 2')
    expect(screen.queryByTestId('paso-listo')).toBeNull()
    // Se lee el correo y la clave guardada abre los PDF: el paso de la clave desaparece solo.
    api.sincronizacionEstado.mockResolvedValue(base({ tareas: [tarea('extractos_por_conciliar', 2)] }))
    fireEvent.click(screen.getByRole('button', { name: 'Buscar ahora' }))
    expect(await screen.findByTestId('paso-listo')).toHaveTextContent('Listo ✓ — siguiente:')
    expect(screen.getByTestId('paso-titulo')).toHaveTextContent('Revisa tus 2 extractos')
    expect(screen.getByTestId('progreso-pasos')).toHaveTextContent('Paso 2 de 2')
  })

  it('al abrir, sin tocar nada, lee el correo y prueba la clave guardada', async () => {
    localStorage.removeItem('cuadrame_gmail_sync') // nunca se ha leído
    api.sincronizacionEstado.mockResolvedValue(base({ tareas: [tarea('falta_clave')] }))
    api.clavePdfEstado.mockResolvedValue({ configurada: true, protegidos: 2, abrieron: 0, no_abrieron: 0, por_probar: 2 })
    api.sincronizarCorreos.mockResolvedValue({ ok: true, completado: true, nuevos: 0, extractos_encontrados: 2 })
    api.probarClavePdf.mockResolvedValue({ ok: true, abrieron: 2, no_abrieron: 0, restantes: 0, mensaje: 'La clave funcionó en 2 extractos.' })
    montar()
    await waitFor(() => expect(api.sincronizarCorreos).toHaveBeenCalled())
    await waitFor(() => expect(api.probarClavePdf).toHaveBeenCalledWith(undefined))
  })

  it('en el primer uso (sin Gmail ni datos) el primer paso es conectar', async () => {
    api.sincronizacionEstado.mockResolvedValue(base({ ultima_sync: null }))
    api.gmailEstado.mockResolvedValue({ conectado: false })
    montar()
    expect(await screen.findByTestId('paso-titulo')).toHaveTextContent('Conecta tu Gmail')
  })

  it('sin Gmail pero con datos y todo hecho: calma, y el botón secundario lleva a conectar', async () => {
    const celda = { mes: '2026-08', estado: 'conciliado', movimientos: 4, conciliados: 4, por_confirmar: 0, extractos: 1 }
    api.sincronizacionEstado.mockResolvedValue(base({ meses: [{ clave: '2026-08', etiqueta: 'ago 26' }], cuentas: [{ id: 'nu', nombre: 'Nu Colombia', meses: [celda] }] }))
    api.gmailEstado.mockResolvedValue({ conectado: false })
    montar()
    expect(await screen.findByTestId('todo-al-dia')).toBeTruthy()
    expect(screen.getByTestId('resumen-tareas')).toHaveTextContent('Gmail sin conectar')
    fireEvent.click(screen.getByTestId('buscar-ahora'))
    expect(await screen.findByRole('dialog', { name: 'Conexiones y claves' })).toBeTruthy()
  })

  it('«Ver todo» y «Conexiones y claves» son hojas con su propio contenido, no secciones apiladas', async () => {
    api.sincronizacionEstado.mockResolvedValue(base({ tareas: [tarea('extractos_por_conciliar', 2)] }))
    montar()
    await screen.findByTestId('paso-guiado')
    expect(screen.queryByTestId('seccion-extractos')).toBeNull()
    fireEvent.click(screen.getByTestId('ver-todo'))
    expect(await screen.findByRole('dialog', { name: 'Ver todo' })).toBeTruthy()
    expect(screen.getByTestId('seccion-extractos')).toBeTruthy()
    expect(screen.queryByTestId('tab-correos')).toBeNull() // los avisos del banco viven en su propia pantalla
    fireEvent.click(screen.getByTestId('tab-meses'))
    expect(screen.getByTestId('seccion-meses')).toBeTruthy()
    expect(screen.queryByTestId('seccion-extractos')).toBeNull()
  })

  it('«Movimientos del correo» tiene su propia pantalla: solo los avisos del banco', async () => {
    api.sincronizacionEstado.mockResolvedValue(base({ tareas: [tarea('correos_por_revisar', 2), tarea('extractos_por_conciliar', 1)] }))
    montar('correo')
    expect(await screen.findByRole('heading', { name: 'Movimientos del correo' })).toBeTruthy()
    expect(await screen.findByTestId('paso-titulo')).toHaveTextContent('Revisa 2 movimientos') // el extracto NO aparece aquí
    expect(screen.queryByText(/Revisa tu extracto/)).toBeNull()
    fireEvent.click(screen.getByTestId('ver-todo'))
    expect(await screen.findByTestId('seccion-correos')).toBeTruthy()
    expect(screen.queryByTestId('tab-extractos')).toBeNull()
  })
})
