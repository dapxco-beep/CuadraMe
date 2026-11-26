// Rediseño UX (2026-11-26): acciones en la línea del título, orden de Inicio, barra lateral y un solo botón principal.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
const auth = vi.hoisted(() => ({ usuario: { id: 'u1', email: 'a@test.com', nombre: 'Ana' } }))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => auth }))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ iconoDe: () => 'x' }) }))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import { EmbebidoProvider } from '../lib/EmbebidoContext'
import { EncabezadoPantalla } from '../lib/AccionesPantallaContext'
import PantallaConPestanas from '../components/PantallaConPestanas'
import InicioSimple from '../components/InicioSimple'
import { EnlaceLateral } from '../components/BarraLateral'

const envolver = (ui, ruta = '/') => (
  <ThemeProvider>
    <DialogosProvider>
      <MemoryRouter initialEntries={[ruta]}>{ui}</MemoryRouter>
    </DialogosProvider>
  </ThemeProvider>
)

// Una «pestaña» de prueba: pinta sus botones con EncabezadoPantalla igual que Presupuesto, Metas, Cuentas…
function PantallaConAcciones({ embebido }) {
  return (
    <div>
      <EncabezadoPantalla embebido={embebido} className="encabezado-propio">
        <div className="flex gap-2">
          <button type="button" aria-label="Crear un presupuesto">+</button>
        </div>
      </EncabezadoPantalla>
      <p>contenido de la pestaña</p>
    </div>
  )
}

describe('Acciones de cada pestaña en la línea del título', () => {
  it('dentro de una pantalla con pestañas los botones van en la línea del título, no en una fila propia', async () => {
    const pestanas = [{ id: 'a', texto: 'Presupuesto', Pantalla: () => <PantallaConAcciones embebido /> }]
    render(envolver(<PantallaConPestanas titulo="Presupuesto" pestanas={pestanas} raiz />))
    const destino = await screen.findByTestId('acciones-pantalla')
    const encabezado = destino.closest('header')
    expect(encabezado).toContainElement(screen.getByRole('heading', { name: 'Presupuesto', level: 1 }))
    expect(within(destino).getByRole('button', { name: 'Crear un presupuesto' })).toBeInTheDocument()
    // y no quedó un segundo encabezado con los botones debajo de las pestañas
    expect(document.querySelectorAll('.encabezado-propio')).toHaveLength(0)
    expect(screen.getByText('contenido de la pestaña')).toBeInTheDocument()
  })

  it('el botón sigue funcionando (el estado y los eventos siguen siendo de la pantalla)', async () => {
    const alClic = vi.fn()
    const Pantalla = () => (
      <EncabezadoPantalla embebido className="x">
        <button type="button" onClick={alClic}>Nuevo</button>
      </EncabezadoPantalla>
    )
    render(envolver(<PantallaConPestanas titulo="Metas" pestanas={[{ id: 'm', texto: 'Metas', Pantalla }]} />))
    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo' }))
    expect(alClic).toHaveBeenCalledTimes(1)
  })

  it('al cambiar de pestaña los botones de la anterior desaparecen del título', async () => {
    const A = () => <EncabezadoPantalla embebido className="x"><button type="button">Acción A</button></EncabezadoPantalla>
    const B = () => <EncabezadoPantalla embebido className="x"><button type="button">Acción B</button></EncabezadoPantalla>
    render(envolver(<PantallaConPestanas titulo="Pantalla" pestanas={[{ id: 'a', texto: 'Uno', Pantalla: A }, { id: 'b', texto: 'Dos', Pantalla: B }]} />))
    expect(await screen.findByRole('button', { name: 'Acción A' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'Dos' }))
    expect(await screen.findByRole('button', { name: 'Acción B' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Acción A' })).toBeNull()
  })

  it('una pantalla suelta (sin pestañas) conserva su encabezado de siempre', () => {
    const { container } = render(envolver(<PantallaConAcciones embebido={false} />))
    expect(container.querySelector('header.encabezado-propio')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Crear un presupuesto' })).toBeInTheDocument()
  })

  it('embebida en otro contenedor que no ofrece destino (p. ej. Informes) también conserva su encabezado', () => {
    const { container } = render(envolver(<EmbebidoProvider value><PantallaConAcciones embebido /></EmbebidoProvider>))
    expect(container.querySelector('header.encabezado-propio')).not.toBeNull()
  })
})

describe('Inicio: lo importante primero', () => {
  const props = { saldo: 1_000_000, gastosSemana: 0, recientes: [], siguiente: null, fmt: (v) => `$${v}`, iconoDe: () => '' }

  it('los avisos no urgentes (instalar, elegir modo) salen DESPUÉS del saldo y de los accesos rápidos', () => {
    render(envolver(<InicioSimple {...props} despuesDelSaldo={<aside data-testid="aviso-suave">Pon CuadraMe en tu celular</aside>} />))
    const saldo = screen.getByLabelText('Cuánto tienes y qué pasó esta semana')
    const aviso = screen.getByTestId('aviso-suave')
    expect(saldo.compareDocumentPosition(aviso) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // y también después de los accesos rápidos (Gasto, Ingreso…)
    const gasto = screen.getByRole('link', { name: /Gasto/ })
    expect(gasto.compareDocumentPosition(aviso) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('sin avisos no se pinta nada extra', () => {
    render(envolver(<InicioSimple {...props} />))
    expect(screen.queryByTestId('aviso-suave')).toBeNull()
  })
})

describe('Barra lateral: la explicación larga solo en la sección activa', () => {
  const item = { to: '/cuentas', label: 'Cuentas', icon: () => null, explica: 'Tus bancos, tarjetas y efectivo, cada uno con su saldo.' }

  it('en la sección donde estás se ve la explicación', () => {
    render(envolver(<EnlaceLateral item={item} />, '/cuentas'))
    const texto = screen.getByText(item.explica)
    expect(texto.className).not.toMatch(/sr-only/)
  })

  it('en las demás queda solo para lectores de pantalla y como tooltip (no desaparece)', () => {
    render(envolver(<EnlaceLateral item={item} />, '/movimientos'))
    const enlace = screen.getByRole('link', { name: /Cuentas/ })
    expect(enlace).toHaveAttribute('title', item.explica)
    expect(screen.getByText(item.explica).className).toMatch(/sr-only/)
  })
})

// ── Candado: un solo botón principal ─────────────────────────────────────────────────────────
function archivosJsx(dir) {
  return readdirSync(dir).flatMap((n) => {
    const ruta = join(dir, n)
    if (statSync(ruta).isDirectory()) return n === 'test' ? [] : archivosJsx(ruta)
    return ruta.endsWith('.jsx') ? [ruta] : []
  })
}

describe('Sistema de botones', () => {
  it('no se crean botones principales sueltos: se usa .btn .btn-primario (o <Boton>)', () => {
    const sueltos = []
    for (const ruta of archivosJsx(join(process.cwd(), 'src'))) {
      const texto = readFileSync(ruta, 'utf8')
      for (const m of texto.matchAll(/className="([^"]*)"/g)) {
        const t = m[1].split(/\s+/)
        const esRectangulo = (t.includes('rounded-xl') || t.includes('rounded-2xl')) && t.includes('font-semibold')
        const esCirculo = t.includes('rounded-full') || t.some((x) => /^[wh]-(5|6|7|8|9|10|11|12|14|16)$/.test(x))
        if (t.includes('bg-accent') && t.includes('text-paper-raised') && esRectangulo && !esCirculo) {
          sueltos.push(`${ruta.split('src')[1]}: ${m[1].slice(0, 70)}`)
        }
      }
    }
    expect(sueltos, `Usa <Boton> o «btn btn-primario» en vez de armar el botón a mano:\n${sueltos.join('\n')}`).toEqual([])
  })

  it('el sistema define el botón grande y el pequeño', () => {
    const css = readFileSync(join(process.cwd(), 'src/index.css'), 'utf8')
    expect(css).toMatch(/\.btn-grande\s*\{[^}]*min-height:\s*52px/)
    expect(css).toMatch(/\.btn-sm\s*\{/)
  })

  it('los rótulos en mayúsculas miden al menos 12 px', () => {
    const css = readFileSync(join(process.cwd(), 'src/brand/estilos.css'), 'utf8')
    expect(/\.t-kicker\s*\{[^}]*font-size:\s*(\d+)px/.exec(css)[1] * 1).toBeGreaterThanOrEqual(12)
  })

  it('las celdas del calendario de gasto miden al menos 44 px', () => {
    const fuente = readFileSync(join(process.cwd(), 'src/components/MapaActividad.jsx'), 'utf8')
    expect(fuente).toMatch(/aspect-square min-h-11/)
    expect(fuente).not.toMatch(/min-h-\[38px\]/)
  })
})
