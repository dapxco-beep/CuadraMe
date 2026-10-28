// «Aprende» (microlecciones y glosario), «¿qué es esto?», «Consejo para ti» y la diferencia débito/crédito.
import { readdirSync, readFileSync } from 'node:fs'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const CUENTAS = [
  { id: 'c1', nombre: 'Bancolombia', saldo: 1500000, moneda: 'COP', tipo: 'ahorro', icono: 'b' },
  { id: 'c2', nombre: 'Visa Nu', saldo: -800000, moneda: 'COP', tipo: 'credito', icono: 'v', cupo_total: 3000000 },
]
const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({
  api: new Proxy(api, { get: (t, nombre) => t[nombre] ?? (() => Promise.resolve([])) }),
}))
vi.mock('../lib/AuthContext', () => ({
  useAuth: () => ({ usuario: { id: 'u1', email: 'l@test.com', nombre: 'Laura' }, logout: vi.fn() }),
}))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn().mockResolvedValue() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ categorias: [], nombres: ['Mercado'], cargando: false, recargar: vi.fn(), iconoDe: () => 'x' }),
}))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import Ayudita from '../components/Ayudita'
import ConsejoParaTi from '../components/ConsejoParaTi'
import Aprende from '../screens/Aprende'
import Agregar from '../screens/Agregar'
import DetalleCuenta from '../components/DetalleCuenta'
import { buscarGlosario, buscarLecciones, GLOSARIO, LECCIONES, terminoPorId } from '../lib/aprende'
import { etiquetaCuenta } from '../lib/saldos'

function montar(ui, ruta = '/') {
  return render(
    <ThemeProvider>
      <DialogosProvider>
        <MemoryRouter initialEntries={[ruta]}>{ui}</MemoryRouter>
      </DialogosProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  for (const k of Object.keys(api)) delete api[k]
})

// ── contenido ────────────────────────────────────────────────────────────────────────
describe('Contenido de Aprende (lib/aprende.js)', () => {
  it('tiene entre 10 y 12 microlecciones con ejemplo en pesos y ids únicos', () => {
    expect(LECCIONES.length).toBeGreaterThanOrEqual(10)
    expect(LECCIONES.length).toBeLessThanOrEqual(12)
    expect(new Set(LECCIONES.map((l) => l.id)).size).toBe(LECCIONES.length)
    for (const l of LECCIONES) {
      expect(l.ejemplo, l.id).toMatch(/\$\d/)
      expect(l.cuerpo.length, l.id).toBeGreaterThan(0)
      if (l.accion) expect(l.accion.to.startsWith('/')).toBe(true)
    }
  })

  it('cubre los temas pedidos', () => {
    const ids = LECCIONES.map((l) => l.id)
    for (const id of ['presupuesto-50-30-20', 'fondo-de-emergencia', 'tarjeta-de-credito', 'debito-vs-credito',
      'interes-ea-vs-nominal', 'traslado', 'deudas-avalancha-bola-de-nieve', 'gastos-hormiga', 'inflacion-y-ahorro',
      'seguridad-fraudes', 'revisar-extractos']) {
      expect(ids).toContain(id)
    }
  })

  it('el glosario no tiene ids repetidos y cada término apunta a una lección real', () => {
    expect(new Set(GLOSARIO.map((t) => t.id)).size).toBe(GLOSARIO.length)
    for (const t of GLOSARIO) {
      expect(t.definicion.length, t.id).toBeGreaterThan(20)
      if (t.leccion) expect(LECCIONES.some((l) => l.id === t.leccion), `${t.id} -> ${t.leccion}`).toBe(true)
    }
  })

  it('nada promete rendimientos ni recomienda productos', () => {
    const todo = JSON.stringify([LECCIONES, GLOSARIO]).toLowerCase()
    for (const p of ['te garantizamos', 'rentabilidad asegurada', 'compra acciones', 'invierte en']) expect(todo).not.toContain(p)
  })

  it('todo <Ayudita termino="..."> usado en la app existe en el glosario', () => {
    const raiz = `${process.cwd()}/src`
    const usados = new Set()
    for (const carpeta of ['screens', 'components']) {
      for (const f of readdirSync(`${raiz}/${carpeta}`).filter((x) => x.endsWith('.jsx'))) {
        const texto = readFileSync(`${raiz}/${carpeta}/${f}`, 'utf8')
        for (const m of texto.matchAll(/termino=["']([a-z0-9-]+)["']/g)) usados.add(m[1])
        for (const m of texto.matchAll(/termino: '([a-z0-9-]+)'/g)) usados.add(m[1])
      }
    }
    for (const m of readFileSync(`${raiz}/lib/saldos.js`, 'utf8').matchAll(/termino: '([a-z0-9-]+)'/g)) usados.add(m[1])
    expect(usados.size).toBeGreaterThan(5)
    for (const id of usados) expect(terminoPorId(id), `término «${id}» no está en el glosario`).not.toBeNull()
  })

  it('las lecciones a las que apuntan los consejos del servidor existen aquí', () => {
    const py = readFileSync(`${process.cwd()}/../backend/app/consejos.py`, 'utf8')
    const bloque = /LECCIONES = \{([^}]*)\}/.exec(py)[1]
    const slugs = [...bloque.matchAll(/"([a-z0-9-]+)"/g)].map((m) => m[1])
    expect(slugs.length).toBeGreaterThan(3)
    for (const s of slugs) expect(LECCIONES.some((l) => l.id === s), s).toBe(true)
  })

  it('la búsqueda ignora acentos y mayúsculas', () => {
    expect(buscarGlosario('INTERES').some((t) => t.id === 'intereses')).toBe(true)
    expect(buscarGlosario('cupo')[0].id).toBe('cupo')
    expect(buscarLecciones('fraude').map((l) => l.id)).toContain('seguridad-fraudes')
    expect(buscarGlosario('zzzz')).toEqual([])
  })
})

// ── pantalla ─────────────────────────────────────────────────────────────────────────
describe('Pantalla Aprende', () => {
  it('lista las lecciones cerradas; al abrir una muestra el ejemplo en pesos y el aviso', async () => {
    montar(<Aprende />)
    expect(screen.getByRole('heading', { name: 'Aprende', level: 1 })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { expanded: false }).length).toBeGreaterThanOrEqual(10)
    await userEvent.click(screen.getByRole('button', { name: /Fondo de emergencia/ }))
    expect(screen.getByText('Ejemplo en pesos')).toBeInTheDocument()
    expect(screen.getByText(/\$6\.000\.000/)).toBeInTheDocument()
    expect(screen.getAllByText('Orientación educativa, no es asesoría financiera.').length).toBeGreaterThan(0)
  })

  it('el buscador filtra lecciones y glosario', async () => {
    montar(<Aprende />)
    await userEvent.type(screen.getByLabelText('Buscar una lección o un término'), 'cupo')
    const glosario = screen.getByTestId('glosario')
    expect(within(glosario).getByText('Cupo')).toBeInTheDocument()
    expect(within(glosario).queryByText('Inflación')).toBeNull()
    expect(screen.queryByText('Gastos hormiga')).toBeNull()
  })

  it('sin resultados lo dice', async () => {
    montar(<Aprende />)
    await userEvent.type(screen.getByLabelText('Buscar una lección o un término'), 'xqzwv')
    expect(screen.getByText('No encontramos eso')).toBeInTheDocument()
  })

  it('un enlace directo abre esa lección', () => {
    montar(<Aprende />, '/aprende?l=tarjeta-de-credito')
    expect(screen.getByRole('button', { name: /Cómo funciona tu tarjeta/ })).toHaveAttribute('aria-expanded', 'true')
  })
})

// ── ayudita ──────────────────────────────────────────────────────────────────────────
describe('Ayudita «¿qué es esto?»', () => {
  it('abre la definición del glosario y enlaza a la lección', async () => {
    montar(<Ayudita termino="cupo" />)
    await userEvent.click(screen.getByRole('button', { name: '¿Qué es Cupo?' }))
    const hoja = await screen.findByRole('dialog', { name: 'Cupo' })
    expect(within(hoja).getByText(/Lo máximo que el banco te deja deber/)).toBeInTheDocument()
    expect(within(hoja).getByRole('link', { name: 'Aprender más' })).toHaveAttribute('href', '/aprende?l=tarjeta-de-credito')
    await userEvent.click(within(hoja).getByRole('button', { name: 'Entendido' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('con un término desconocido no pinta nada', () => {
    const { container } = montar(<Ayudita termino="no-existe" />)
    expect(container.querySelector('button')).toBeNull()
  })
})

// ── consejo para ti ──────────────────────────────────────────────────────────────────
const CONSEJOS = [1, 2, 3, 4].map((n) => ({
  id: `consejo-${n}`, tipo: 't', prioridad: 2, titulo: `Título ${n}`, texto: `Texto ${n}`, cifra: `$${n}00.000`,
  accion: { texto: `Hacer ${n}`, ruta: `/ruta-${n}` }, aprende: n === 1 ? 'tarjeta-de-credito' : null,
}))

describe('Consejo para ti', () => {
  it('muestra hasta 3 en carrusel, con cifra, acción y aviso educativo', async () => {
    api.consejos = vi.fn().mockResolvedValue({ aviso: 'Orientación educativa, no es asesoría financiera.', consejos: CONSEJOS })
    montar(<ConsejoParaTi />)
    expect(await screen.findByText('Título 1')).toBeInTheDocument()
    expect(screen.getByTestId('consejo-cifra')).toHaveTextContent('$100.000')
    expect(screen.getByRole('link', { name: 'Hacer 1' })).toHaveAttribute('href', '/ruta-1')
    expect(screen.getByRole('link', { name: 'Entender por qué' })).toHaveAttribute('href', '/aprende?l=tarjeta-de-credito')
    expect(screen.getByText('Orientación educativa, no es asesoría financiera.')).toBeInTheDocument()
    expect(screen.getByText('1/3')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Consejo siguiente' }))
    expect(screen.getByText('Título 2')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Consejo siguiente' }))
    await userEvent.click(screen.getByRole('button', { name: 'Consejo siguiente' }))
    expect(screen.getByText('Título 1')).toBeInTheDocument() // da la vuelta: nunca más de 3
  })

  it('al descartar uno no vuelve (ni al recargar) y entra el siguiente', async () => {
    api.consejos = vi.fn().mockResolvedValue({ consejos: CONSEJOS })
    const { unmount } = montar(<ConsejoParaTi />)
    await userEvent.click(await screen.findByRole('button', { name: /Descartar consejo: Título 1/ }))
    expect(screen.queryByText('Título 1')).toBeNull()
    expect(screen.getByText('Título 2')).toBeInTheDocument()
    expect(screen.getByText('1/3')).toBeInTheDocument() // entró el cuarto para completar tres
    unmount()

    montar(<ConsejoParaTi />)
    expect(await screen.findByText('Título 2')).toBeInTheDocument()
    expect(screen.queryByText('Título 1')).toBeNull()
  })

  it('si descartas todos desaparece la tarjeta', async () => {
    api.consejos = vi.fn().mockResolvedValue({ consejos: CONSEJOS.slice(0, 1) })
    montar(<ConsejoParaTi />)
    await userEvent.click(await screen.findByRole('button', { name: /Descartar consejo/ }))
    expect(screen.queryByTestId('consejo-para-ti')).toBeNull()
  })

  it('sin consejos, o si falla la carga, no pinta nada', async () => {
    api.consejos = vi.fn().mockRejectedValue(new Error('x'))
    const { container } = montar(<ConsejoParaTi />)
    await waitFor(() => expect(api.consejos).toHaveBeenCalled())
    expect(container.querySelector('[data-testid="consejo-para-ti"]')).toBeNull()
  })
})

// ── débito vs crédito ────────────────────────────────────────────────────────────────
describe('Débito vs crédito en la app', () => {
  it('etiquetaCuenta distingue lo que significa cada saldo', () => {
    expect(etiquetaCuenta({ tipo: 'ahorro' })).toMatchObject({ etiqueta: 'Débito / Ahorros' })
    expect(etiquetaCuenta({ tipo: 'ahorro' }).significado).toMatch(/Saldo disponible/)
    expect(etiquetaCuenta({ tipo: 'credito' })).toMatchObject({ etiqueta: 'Tarjeta de crédito' })
    expect(etiquetaCuenta({ tipo: 'credito' }).significado).toMatch(/lo que debes/)
  })

  it('el detalle de una tarjeta dice «Tarjeta de crédito» y explica que es deuda', async () => {
    api.detalleCuenta = vi.fn().mockResolvedValue({
      cuenta: CUENTAS[1], saldo_actual: -800000, ultimo_movimiento: null, ingresos_mes: 0, gastos_mes: 0, movimientos: [],
    })
    montar(<DetalleCuenta cuentaId="c2" onClose={() => {}} />)
    expect(await screen.findByTestId('tipo-cuenta')).toHaveTextContent('Tarjeta de crédito')
    expect(screen.getByTestId('significado-saldo')).toHaveTextContent(/lo que debes al banco/)
  })

  it('al transferir hacia una tarjeta avisa que pagarla no es un gasto nuevo', async () => {
    montar(<Agregar />)
    expect(screen.queryByTestId('aviso-pago-tarjeta')).toBeNull() // un gasto normal no lo lleva
    await userEvent.click(screen.getByRole('button', { name: 'Pasar plata' }))
    // desde Bancolombia, el único destino posible es la tarjeta Visa Nu
    expect(screen.getByTestId('aviso-pago-tarjeta')).toHaveTextContent('Esto no es un gasto nuevo, es pagar lo que ya compraste')
  })
})
