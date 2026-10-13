// Menú «Más» agrupado con buscador, «Recientes», barra lateral con grupos plegables
// y una sola fuente de verdad (lib/navegacion.js).
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import ShellApp from '../components/ShellApp'
import BottomNav from '../components/BottomNav'
import { GRUPOS, ITEMS_MAS, buscarDestinos, leerRecientes, normalizar, registrarReciente } from '../lib/navegacion'

const matchMediaOriginal = window.matchMedia
function simularAncho(ancho) {
  window.matchMedia = (consulta) => {
    const m = /min-width:\s*(\d+)px/.exec(consulta)
    return {
      matches: m ? ancho >= Number(m[1]) : false,
      media: consulta,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
    }
  }
}

function Ruta() {
  return <p data-testid="ruta">{useLocation().pathname}</p>
}

function montarShell(ancho, ruta = '/') {
  simularAncho(ancho)
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ShellApp>
        <Routes>
          <Route path="*" element={<p>Pantalla</p>} />
        </Routes>
      </ShellApp>
      <Ruta />
    </MemoryRouter>
  )
}

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('cuadrame:modo-completo:anon', '1') // el menú agrupado de siempre = modo completo
})
afterEach(() => {
  window.matchMedia = matchMediaOriginal
})

describe('navegacion.js (fuente única)', () => {
  it('agrupa los destinos por tema con los nombres pedidos', () => {
    expect(GRUPOS.map((g) => g.titulo)).toEqual(['Dinero', 'Ahorro e inversión', 'Entender', 'Datos', 'Ajustes'])
    const etiquetas = (id) => GRUPOS.find((g) => g.id === id).items.map((i) => i.label)
    expect(etiquetas('dinero')).toEqual(['Cuentas', 'Deudas', 'Pagos fijos', 'Impuestos'])
    expect(etiquetas('datos')).toContain('Traer movimientos')
    expect(ITEMS_MAS.find((i) => i.label === 'Traer movimientos').to).toBe('/sincronizacion')
    expect(etiquetas('ajustes')).toEqual(['Perfil', 'Aprende', 'Ayuda', 'Privacidad', 'Registro automático'])
  })

  it('la búsqueda tolera acentos y mayúsculas, y encuentra por palabras clave', () => {
    expect(normalizar('Categorías')).toBe('categorias')
    expect(buscarDestinos('CATEGORIAS').map((d) => d.label)).toContain('Categorías')
    expect(buscarDestinos('sincronizacion')[0].label).toBe('Traer movimientos')
    expect(buscarDestinos('gmail').map((d) => d.to)).toContain('/sincronizacion')
    expect(buscarDestinos('zzzz')).toEqual([])
    expect(buscarDestinos('   ')).toEqual([])
  })

  it('recuerda los últimos 4 destinos, sin repetir, el más reciente primero', () => {
    for (const r of ['/cuentas', '/deudas', '/metas', '/impuestos', '/deudas', '/informe', '/']) registrarReciente(r)
    expect(leerRecientes().map((d) => d.to)).toEqual(['/informe', '/deudas', '/impuestos', '/metas'])
  })
})

describe('Menú «Más» del teléfono', () => {
  it('muestra encabezados de grupo y filtra con el buscador', async () => {
    simularAncho(390)
    render(
      <MemoryRouter>
        <BottomNav />
      </MemoryRouter>
    )
    await userEvent.click(screen.getByRole('button', { name: 'Más' }))
    const hoja = await screen.findByRole('dialog', { name: 'Más opciones' })
    for (const g of GRUPOS) expect(within(hoja).getByRole('heading', { name: g.titulo })).toBeInTheDocument()

    const buscador = within(hoja).getByRole('searchbox', { name: 'Buscar en el menú' })
    await userEvent.type(buscador, 'categorias')
    // sin acentos encuentra «Categorías» y «Entrenar categorías»; desaparecen los encabezados
    expect(within(hoja).getByRole('link', { name: 'Categorías' })).toBeInTheDocument()
    expect(within(hoja).getByRole('link', { name: 'Enseñar categorías' })).toBeInTheDocument()
    expect(within(hoja).queryByRole('link', { name: 'Deudas' })).toBeNull()
    expect(within(hoja).queryByRole('heading', { name: 'Dinero' })).toBeNull()

    await userEvent.clear(buscador)
    await userEvent.type(buscador, 'xyzxyz')
    expect(within(hoja).getByRole('status')).toHaveTextContent(/No encontré/)
  })

  it('Escape borra primero la búsqueda y luego cierra la hoja; Enter abre el primer resultado', async () => {
    simularAncho(390)
    render(
      <MemoryRouter>
        <BottomNav />
        <Ruta />
      </MemoryRouter>
    )
    await userEvent.click(screen.getByRole('button', { name: 'Más' }))
    const buscador = await screen.findByRole('searchbox', { name: 'Buscar en el menú' })
    await userEvent.type(buscador, 'deud')
    await userEvent.keyboard('{Escape}')
    expect(buscador).toHaveValue('')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await userEvent.type(buscador, 'deud{Enter}')
    await waitFor(() => expect(screen.getByTestId('ruta')).toHaveTextContent('/deudas'))
  })

  it('«Recientes» lista los últimos destinos usados', async () => {
    registrarReciente('/metas')
    registrarReciente('/deudas')
    simularAncho(390)
    render(
      <MemoryRouter>
        <BottomNav />
      </MemoryRouter>
    )
    await userEvent.click(screen.getByRole('button', { name: 'Más' }))
    const hoja = await screen.findByRole('dialog')
    const seccion = within(hoja).getByRole('heading', { name: /Recientes/ }).closest('section')
    const enlaces = within(seccion).getAllByRole('link').map((a) => a.textContent)
    expect(enlaces).toEqual(['Deudas', 'Metas'])
  })
})

describe('Barra lateral de escritorio', () => {
  it('agrupa los destinos en secciones plegables y recuerda el estado', async () => {
    montarShell(1440)
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    const btnDatos = within(nav).getByRole('button', { name: 'Datos' })
    expect(btnDatos).toHaveAttribute('aria-expanded', 'true')
    expect(within(nav).getByRole('link', { name: 'Traer movimientos' })).toBeInTheDocument()

    await userEvent.click(btnDatos)
    expect(btnDatos).toHaveAttribute('aria-expanded', 'false')
    expect(within(nav).queryByRole('link', { name: 'Traer movimientos' })).toBeNull()
    expect(JSON.parse(localStorage.getItem('cuadrame:nav-grupos-cerrados'))).toEqual(['datos'])
  })

  it('«Recientes» no repite pantallas que ya están en un grupo abierto', () => {
    localStorage.setItem('cuadrame:nav-recientes', JSON.stringify(['/sincronizacion']))
    montarShell(1440)
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    // «Traer movimientos» ya está en su grupo: aparece UNA sola vez y no se mueve arriba
    expect(within(nav).getAllByRole('link', { name: 'Traer movimientos' })).toHaveLength(1)
    expect(within(nav).queryByText('Recientes')).toBeNull()
  })

  it('un grupo plegado se abre solo al ir a una de sus pantallas', () => {
    localStorage.setItem('cuadrame:nav-grupos-cerrados', JSON.stringify(['datos']))
    montarShell(1440, '/categorias')
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    expect(within(nav).getByRole('button', { name: 'Datos' })).toHaveAttribute('aria-expanded', 'true')
  })

  it('el buscador filtra y «/» lo enfoca', async () => {
    montarShell(1440)
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    await userEvent.keyboard('/')
    const buscador = within(nav).getByRole('searchbox', { name: 'Buscar en el menú' })
    expect(buscador).toHaveFocus()
    await userEvent.keyboard('inversion')
    expect(within(nav).getByRole('link', { name: 'Patrimonio' })).toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: 'Cuentas' })).toBeNull()
  })

  it('los atajos N y G+letra siguen funcionando', async () => {
    montarShell(1440, '/presupuesto')
    await userEvent.keyboard('n')
    expect(screen.getByTestId('ruta')).toHaveTextContent('/agregar')
    await userEvent.keyboard('gm')
    expect(screen.getByTestId('ruta')).toHaveTextContent('/movimientos')
  })
})
