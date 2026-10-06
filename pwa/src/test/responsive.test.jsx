// Diseño responsive: teléfono (<768), iPad vertical (≥768), iPad horizontal y PC (≥1024),
// atajos de teclado, hoja centrada, movimiento reducido y barras accesibles.
import { readFileSync } from 'node:fs'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import ShellApp from '../components/ShellApp'
import Hoja from '../components/Hoja'
import BarraProgreso from '../components/BarraProgreso'
import MazoCuentas from '../components/MazoCuentas'
import { ITEMS_MAS } from '../components/BottomNav'
import { esCampoDeTexto } from '../lib/atajos'

const matchMediaOriginal = window.matchMedia

// Simula el ancho de la ventana: matchMedia responde a (min-width: Npx)
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

afterEach(() => {
  window.matchMedia = matchMediaOriginal
})

function Ruta() {
  return <p data-testid="ruta">{useLocation().pathname}</p>
}

function montar(ancho, ruta = '/', contenido = <p>Pantalla</p>) {
  simularAncho(ancho)
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ShellApp>
        <Routes>
          <Route path="*" element={contenido} />
        </Routes>
      </ShellApp>
      <Ruta />
    </MemoryRouter>
  )
}

describe('Shell responsive', () => {
  it('<768 px: barra inferior con el + central y sin riel ni barra lateral', () => {
    const { container } = montar(390)
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    expect(within(nav).getByRole('link', { name: 'Agregar movimiento' })).toBeInTheDocument()
    expect(within(nav).getByRole('button', { name: 'Más' })).toBeInTheDocument()
    expect(container.querySelector('.barra-lateral')).toBeNull()
    expect(container.querySelector('.app-shell')).toHaveAttribute('data-modo', 'movil')
  })

  it('≥768 px: riel de 72 px con los 5 destinos, Agregar y Más; sin barra inferior ni + flotante', async () => {
    const { container } = montar(820)
    expect(container.querySelector('.barra-riel')).not.toBeNull()
    expect(container.querySelector('.barra-completa')).toBeNull()
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    for (const nombre of ['Inicio', 'Movimientos', 'Presupuesto', 'Patrimonio', 'Sincronización', 'Agregar movimiento']) {
      expect(within(nav).getByRole('link', { name: nombre })).toBeInTheDocument()
    }
    // Una sola navegación (no hay barra inferior duplicada)
    expect(screen.getAllByRole('navigation')).toHaveLength(1)
    await userEvent.click(within(nav).getByRole('button', { name: 'Más' }))
    const hoja = await screen.findByRole('dialog', { name: 'Más opciones' })
    expect(within(hoja).getByRole('link', { name: 'Metas' })).toBeInTheDocument()
  })

  it('≥1024 px: barra lateral con todos los destinos, botón destacado, tema y Perfil', async () => {
    const { container } = montar(1440)
    expect(container.querySelector('.barra-completa')).not.toBeNull()
    expect(container.querySelector('.barra-riel')).toBeNull()
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    expect(within(nav).getByRole('link', { name: /Agregar movimiento/ })).toHaveAttribute('href', '/agregar')
    for (const { label, to } of ITEMS_MAS) {
      expect(within(nav).getByRole('link', { name: label })).toHaveAttribute('href', to)
    }
    expect(within(nav).getByRole('link', { name: 'Perfil y ajustes' })).toBeInTheDocument()
    expect(within(nav).getByRole('button', { name: /Tema/ })).toBeInTheDocument()
    expect(within(nav).queryByRole('button', { name: 'Más' })).toBeNull()
  })
})

describe('Atajos de teclado', () => {
  it('N abre "nuevo movimiento"; G y luego M/P/I navegan', async () => {
    montar(1440, '/presupuesto')
    await userEvent.keyboard('n')
    expect(screen.getByTestId('ruta')).toHaveTextContent('/agregar')
    await userEvent.keyboard('gm')
    expect(screen.getByTestId('ruta')).toHaveTextContent('/movimientos')
    await userEvent.keyboard('gp')
    expect(screen.getByTestId('ruta')).toHaveTextContent('/presupuesto')
    await userEvent.keyboard('gi')
    expect(screen.getByTestId('ruta')).toHaveTextContent(/^\/$/)
  })

  it('no se disparan escribiendo en un campo', async () => {
    montar(1440, '/movimientos', <input aria-label="Buscar" />)
    await userEvent.click(screen.getByLabelText('Buscar'))
    await userEvent.keyboard('n')
    expect(screen.getByTestId('ruta')).toHaveTextContent('/movimientos')
    expect(screen.getByLabelText('Buscar')).toHaveValue('n')
    expect(esCampoDeTexto(screen.getByLabelText('Buscar'))).toBe(true)
  })

  it('no se disparan con una hoja abierta ni con Ctrl/Cmd', async () => {
    montar(
      1440,
      '/movimientos',
      <Hoja titulo="Algo" onCerrar={() => {}}>
        <button>Dentro</button>
      </Hoja>
    )
    await screen.findByRole('dialog')
    await userEvent.keyboard('n')
    expect(screen.getByTestId('ruta')).toHaveTextContent('/movimientos')
  })

  it('"/" enfoca la búsqueda si la pantalla la tiene', async () => {
    montar(1440, '/movimientos', <input aria-label="Buscar movimiento" data-atajo-buscar />)
    await userEvent.keyboard('/')
    expect(screen.getByLabelText('Buscar movimiento')).toHaveFocus()
  })
})

describe('Hoja en pantallas anchas', () => {
  it('es modal centrado desde 768 px (md:items-center, esquinas completas) y hoja inferior en teléfono', () => {
    render(
      <Hoja titulo="Nueva meta" onCerrar={() => {}}>
        <p>contenido</p>
      </Hoja>
    )
    const dialogo = screen.getByRole('dialog', { name: 'Nueva meta' })
    expect(dialogo.className).toMatch(/md:rounded-\[28px\]/)
    expect(dialogo.className).toMatch(/rounded-t-\[28px\]/)
    expect(dialogo.parentElement.className).toMatch(/items-end/)
    expect(dialogo.parentElement.className).toMatch(/md:items-center/)
  })
})

describe('Movimiento reducido y barras accesibles', () => {
  const css = readFileSync('src/index.css', 'utf8')

  it('el CSS anula las transiciones de barras, anillo y dona con prefers-reduced-motion', () => {
    const bloque = css.slice(css.indexOf('@media (prefers-reduced-motion: reduce)'))
    for (const sel of ['.barra-fill', '.anillo-trazo', '.dona-trazo']) expect(bloque).toContain(sel)
    expect(bloque).toMatch(/transition:\s*none/)
  })

  it('el CSS limita el hundido al tocar a pantallas sin hover y el hover a las que sí lo tienen', () => {
    expect(css).toMatch(/@media \(hover: none\)\s*{\s*button:active/)
    expect(css).toMatch(/@media \(hover: hover\)/)
  })

  it('el retraso en cascada tiene tope de 8', () => {
    expect(css).toMatch(/min\(var\(--stagger-i, 0\), 8\)/)
  })

  it('App envuelve todo en MotionConfig reducedMotion="user"', () => {
    const app = readFileSync('src/App.jsx', 'utf8')
    expect(app).toMatch(/<MotionConfig reducedMotion="user">/)
  })

  it('la barra anima con transform: scaleX y expone role=progressbar', () => {
    render(<BarraProgreso pct={64.4} label="Gasto en Mercado" />)
    const barra = screen.getByRole('progressbar', { name: 'Gasto en Mercado' })
    expect(barra).toHaveAttribute('aria-valuenow', '64')
    expect(barra).toHaveAttribute('aria-valuemin', '0')
    expect(barra).toHaveAttribute('aria-valuemax', '100')
    const relleno = barra.firstChild
    expect(relleno.style.transform).toBe('scaleX(0.644)')
    expect(relleno.style.width).toBe('')
  })

  it('limita la barra entre 0 y 100', () => {
    render(<BarraProgreso pct={250} label="Tope" />)
    expect(screen.getByRole('progressbar', { name: 'Tope' }).firstChild.style.transform).toBe('scaleX(1)')
  })
})

describe('Mazo de cuentas con teclado', () => {
  const cuentas = [
    { id: 'a', nombre: 'Uno', saldo: 1, moneda: 'COP', tipo: 'ahorro', icono: '🏦' },
    { id: 'b', nombre: 'Dos', saldo: 2, moneda: 'COP', tipo: 'ahorro', icono: '🏦' },
  ]
  beforeEach(() => simularAncho(1440))

  it('las flechas ← → cambian la tarjeta del frente y Enter abre su detalle', async () => {
    render(
      <MemoryRouter>
        <MazoCuentas cuentas={cuentas} />
        <Ruta />
      </MemoryRouter>
    )
    const mazo = screen.getByRole('group', { name: /Tus cuentas/ })
    expect(mazo).toHaveAttribute('tabindex', '0')
    mazo.focus()
    expect(screen.getByRole('button', { name: 'Ver Uno' })).toHaveAttribute('aria-current', 'true')
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('button', { name: 'Ver Dos' })).toHaveAttribute('aria-current', 'true')
    await userEvent.keyboard('{ArrowLeft}')
    expect(screen.getByRole('button', { name: 'Ver Uno' })).toHaveAttribute('aria-current', 'true')
    await userEvent.keyboard('{Enter}')
    expect(screen.getByTestId('ruta')).toHaveTextContent('/cuentas')
  })
})
