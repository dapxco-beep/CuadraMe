// Metas con sugerencia, «Compartir con mi pareja o familia» y «Mi banco no aparece». API simulada.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  metas: vi.fn(), metasSugerencias: vi.fn(), consejos: vi.fn(), aportarMeta: vi.fn(), crearMeta: vi.fn(), simularMeta: vi.fn(),
  misInvitacionesPendientes: vi.fn(), compartidaCon: vi.fn(), invitacionesDeCuenta: vi.fn(), invitarACuenta: vi.fn(), revocarAcceso: vi.fn(),
  almacenMuestras: vi.fn(), enviarComentario: vi.fn(), subirMuestraBanco: vi.fn(), borrarMuestraBanco: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
const avisar = vi.hoisted(() => vi.fn())
const confirmar = vi.hoisted(() => vi.fn())
vi.mock('../lib/DialogosContext', () => ({ useDialogos: () => ({ avisar, confirmar }) }))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: [{ id: 'c1', nombre: 'Bancolombia' }, { id: 'c2', nombre: 'Nequi' }], recargar: vi.fn() }),
}))

import Metas, { montoSugerido } from '../screens/Metas'
import Compartir from '../screens/Compartir'
import BancoNoEsta, { problemaDeArchivo } from '../components/BancoNoEsta'
import { gruposSegunModo } from '../lib/navegacion'
import { marcarFuncionEnUso, leerFuncionesEnUso } from '../lib/modoSimple'

const montar = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>)

const PLAN = {
  estado_ritmo: 'atrasado', frase_ritmo: 'Vas atrasado: te faltan $200.000 para ir al día.',
  texto_necesario: 'Para llegar a tiempo necesitas $400.000 al mes', aporte_necesario_mes: 400000, opcion_sugerida: 'recomendado',
  opciones: [
    { id: 'comodo', nombre: 'Cómodo', monto: 300000, texto: 'Si apartas $300.000 al mes llegas en marzo de 2027' },
    { id: 'recomendado', nombre: 'Recomendado', monto: 500000, texto: 'Si apartas $500.000 al mes llegas en enero de 2027' },
  ],
}
const META = { id: 'm1', nombre: 'Viaje', monto_objetivo: 3000000, monto_actual: 600000, progreso_pct: 20, completada: false, cuenta_origen_id: 'c1' }

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  avisar.mockReset()
  confirmar.mockReset()
  api.consejos.mockResolvedValue({ consejos: [] })
})

describe('A. Metas con sugerencia', () => {
  it('muestra lo que necesitas, cuándo llegas, si vas atrasado y el consejo de la meta', async () => {
    api.metas.mockResolvedValue([META])
    api.metasSugerencias.mockResolvedValue({ metas: { m1: PLAN } })
    api.consejos.mockResolvedValue({ consejos: [{ tipo: 'meta_sin_aporte', meta_id: 'm1', texto: 'Este mes aún no has apartado nada.' }] })
    montar(<Metas />)
    expect(await screen.findByText(/Para llegar a tiempo necesitas \$400\.000 al mes/)).toBeInTheDocument()
    expect(screen.getByText(/Si apartas \$500\.000 al mes llegas en enero de 2027/)).toBeInTheDocument()
    expect(screen.getByTestId('ritmo-meta')).toHaveTextContent('Vas atrasado')
    expect(await screen.findByTestId('consejo-meta')).toHaveTextContent('aún no has apartado')
    expect(screen.getByRole('progressbar', { name: 'Progreso de Viaje' })).toBeInTheDocument()
  })

  it('«Aportar ahora» propone la opción sugerida y registra el aporte desde la cuenta de la meta', async () => {
    api.metas.mockResolvedValue([META])
    api.metasSugerencias.mockResolvedValue({ metas: { m1: PLAN } })
    api.aportarMeta.mockResolvedValue({ ...META, completada: false })
    montar(<Metas />)
    fireEvent.click(await screen.findByRole('button', { name: 'Aportar ahora' }))
    expect(await screen.findByLabelText('Cuánto aportas')).toHaveValue('500.000')
    expect(screen.getByLabelText('De dónde sale la plata')).toHaveValue('c1')
    fireEvent.click(screen.getAllByRole('button', { name: 'Aportar ahora' }).pop())
    await waitFor(() => expect(api.aportarMeta).toHaveBeenCalledWith('m1', 500000, 'c1'))
  })

  it('sin plan usa el aporte necesario y luego el automático', () => {
    expect(montoSugerido(null, { aporte_automatico: 150000 })).toBe(150000)
    expect(montoSugerido({ aporte_necesario_mes: 90000, opciones: [] }, {})).toBe(90000)
    expect(montoSugerido(PLAN, {})).toBe(500000)
  })

  it('en modo simple «Metas» aparece cuando se crea la primera', () => {
    const uid = 'u-metas'
    const sin = gruposSegunModo({ completo: false, enUso: leerFuncionesEnUso(uid) })
    expect(sin.find((g) => g.id === 'en-uso')).toBeUndefined()
    marcarFuncionEnUso(uid, '/metas')
    const con = gruposSegunModo({ completo: false, enUso: leerFuncionesEnUso(uid) })
    expect(con.find((g) => g.id === 'en-uso').items.map((i) => i.to)).toContain('/metas')
  })
})

describe('B. Compartir con mi pareja o familia', () => {
  beforeEach(() => {
    api.misInvitacionesPendientes.mockResolvedValue([])
    api.compartidaCon.mockResolvedValue([])
    api.invitacionesDeCuenta.mockResolvedValue([])
  })

  it('tiene los 3 pasos y explica qué ve y qué no ve según lo que puede hacer', async () => {
    montar(<Compartir />)
    expect(await screen.findByRole('heading', { name: 'Compartir con mi pareja o familia' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Paso 1/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Paso 2/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Paso 3/)).toBeInTheDocument()
    expect(screen.getByTestId('que-ve')).toHaveTextContent('No podrá anotar')
    fireEvent.click(screen.getByRole('radio', { name: /Ver y anotar/ }))
    expect(screen.getByTestId('que-ve')).toHaveTextContent('anotar y corregir')
  })

  it('invita las cuentas elegidas con el rol elegido (viewer / editor)', async () => {
    api.invitarACuenta.mockResolvedValue({ id: 'i1' })
    montar(<Compartir />)
    await screen.findByRole('checkbox', { name: /Bancolombia/ })
    fireEvent.click(screen.getByRole('checkbox', { name: /Bancolombia/ }))
    fireEvent.click(screen.getByRole('checkbox', { name: /Nequi/ }))
    fireEvent.change(screen.getByLabelText('Correo de la persona'), { target: { value: 'ana@correo.com' } })
    fireEvent.click(screen.getByRole('radio', { name: /Ver y anotar/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Enviar invitación' }))
    await waitFor(() => expect(api.invitarACuenta).toHaveBeenCalledTimes(2))
    expect(api.invitarACuenta).toHaveBeenCalledWith('c1', 'ana@correo.com', 'editor')
    expect(api.invitarACuenta).toHaveBeenCalledWith('c2', 'ana@correo.com', 'editor')
  })

  it('pide elegir una cuenta y un correo completo antes de enviar', async () => {
    montar(<Compartir />)
    await screen.findByRole('checkbox', { name: /Nequi/ })
    fireEvent.click(screen.getByRole('button', { name: 'Enviar invitación' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Elige al menos una cuenta')
    fireEvent.click(screen.getByRole('checkbox', { name: /Nequi/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Enviar invitación' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('correo completo')
    expect(api.invitarACuenta).not.toHaveBeenCalled()
  })

  it('muestra el estado de cada invitación y permite dejar de compartir', async () => {
    api.compartidaCon.mockImplementation(async (id) => (id === 'c1' ? [{ id: 'x', cuenta_id: 'c1', usuario_id: 'u9', rol: 'viewer' }] : []))
    api.invitacionesDeCuenta.mockImplementation(async (id) =>
      id === 'c1'
        ? [{ id: 'i1', email_invitado: 'ana@correo.com', rol: 'viewer', estado: 'aceptada' }]
        : [{ id: 'i2', email_invitado: 'luis@correo.com', rol: 'editor', estado: 'pendiente' }]
    )
    confirmar.mockResolvedValue(true)
    api.revocarAcceso.mockResolvedValue({ ok: true })
    montar(<Compartir />)
    expect(await screen.findByText('ana@correo.com')).toBeInTheDocument()
    expect(screen.getByText('Ya tiene acceso')).toBeInTheDocument()
    expect(screen.getByText('luis@correo.com')).toBeInTheDocument()
    expect(screen.getByText('Esperando respuesta')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Dejar de compartir Bancolombia con ana@correo.com/ }))
    await waitFor(() => expect(api.revocarAcceso).toHaveBeenCalledWith('c1', 'u9'))
  })

  it('separa «Dividir gastos con amigos» con un enlace claro', async () => {
    montar(<Compartir />)
    expect(await screen.findByRole('link', { name: 'Dividir gastos con amigos' })).toHaveAttribute('href', '/amigos')
  })
})

describe('C. Mi banco no aparece', () => {
  const abrir = () => montar(<BancoNoEsta onClose={vi.fn()} />)

  it('valida el archivo: solo pdf/xls/xlsx/csv y máximo 5 MB', () => {
    expect(problemaDeArchivo({ name: 'a.pdf', size: 1000 })).toBe('')
    expect(problemaDeArchivo({ name: 'a.exe', size: 1000 })).toMatch(/Solo recibimos/)
    expect(problemaDeArchivo({ name: 'a.csv', size: 6 * 1024 * 1024 })).toMatch(/5 MB/)
    expect(problemaDeArchivo(null)).toBe('')
  })

  it('envía el comentario tipo banco sin archivo (se puede omitir)', async () => {
    api.almacenMuestras.mockResolvedValue({ disponible: true })
    api.enviarComentario.mockResolvedValue({ ok: true, id: 'k1' })
    abrir()
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('nombre de tu banco')
    fireEvent.change(screen.getByLabelText('¿Cómo se llama tu banco o billetera?'), { target: { value: 'Banco Agrario' } })
    fireEvent.click(screen.getByRole('radio', { name: 'Excel' }))
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    expect(await screen.findByTestId('banco-gracias')).toBeInTheDocument()
    expect(api.enviarComentario).toHaveBeenCalledWith(expect.objectContaining({ tipo: 'banco', banco: 'Banco Agrario', tipo_archivo: 'excel' }))
    expect(api.subirMuestraBanco).not.toHaveBeenCalled()
  })

  it('con archivo muestra el aviso de privacidad, lo sube y se puede borrar', async () => {
    api.almacenMuestras.mockResolvedValue({ disponible: true })
    api.enviarComentario.mockResolvedValue({ ok: true, id: 'k2' })
    api.subirMuestraBanco.mockResolvedValue({ ok: true })
    api.borrarMuestraBanco.mockResolvedValue({ ok: true })
    abrir()
    expect(await screen.findByText(/Puedes borrar los datos personales antes/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('¿Cómo se llama tu banco o billetera?'), { target: { value: 'Mi Banco' } })
    const archivo = new File(['%PDF-1.4'], 'extracto.pdf', { type: 'application/pdf' })
    fireEvent.change(document.querySelector('input[type=file]'), { target: { files: [archivo] } })
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    await screen.findByTestId('banco-gracias')
    expect(api.subirMuestraBanco).toHaveBeenCalledWith('k2', archivo)
    fireEvent.click(screen.getByRole('button', { name: /Borrar el archivo extracto.pdf/ }))
    await waitFor(() => expect(api.borrarMuestraBanco).toHaveBeenCalledWith('k2'))
  })

  it('si no hay almacenamiento avisa y guarda solo el nombre', async () => {
    api.almacenMuestras.mockResolvedValue({ disponible: false })
    api.enviarComentario.mockResolvedValue({ ok: true, id: 'k3' })
    abrir()
    expect(await screen.findByText(/no podemos recibir archivos/)).toBeInTheDocument()
    expect(document.querySelector('input[type=file]')).toBeNull()
  })

  it('rechaza un archivo de tipo no permitido sin subirlo', async () => {
    api.almacenMuestras.mockResolvedValue({ disponible: true })
    abrir()
    await screen.findByTestId('muestra-banco')
    fireEvent.change(document.querySelector('input[type=file]'), { target: { files: [new File(['x'], 'virus.exe')] } })
    expect(await screen.findByRole('alert')).toHaveTextContent('Solo recibimos')
  })
})
