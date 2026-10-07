// Esqueletos de carga: accesibles, con la forma de la pantalla y apagados con prefers-reduced-motion.
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  EsqueletoFila, EsqueletoGrafica, EsqueletoLista, EsqueletoPantalla, EsqueletoTarjeta, EsqueletoTexto,
} from '../components/Esqueletos'

const css = readFileSync(`${process.cwd()}/src/index.css`, 'utf8')

describe('Esqueletos', () => {
  it('cada esqueleto es UN estado accesible (role=status, aria-busy) con nombre en español', () => {
    render(
      <>
        <EsqueletoLista filas={3} etiqueta="Cargando tus deudas" />
        <EsqueletoTarjeta etiqueta="Cargando tu resumen" />
        <EsqueletoGrafica etiqueta="Cargando tu informe" />
        <EsqueletoTexto lineas={2} etiqueta="Cargando el texto" />
      </>
    )
    for (const nombre of ['Cargando tus deudas', 'Cargando tu resumen', 'Cargando tu informe', 'Cargando el texto']) {
      const estado = screen.getByRole('status', { name: nombre })
      expect(estado).toHaveAttribute('aria-busy', 'true')
    }
    // las barras internas no se anuncian una por una
    expect(screen.getAllByRole('status')).toHaveLength(4)
  })

  it('la lista pinta tantas filas como se pide, y la fila mide lo mismo que una fila real (64 px: sin saltos de layout)', () => {
    const { container } = render(<EsqueletoLista filas={4} />)
    expect(container.querySelectorAll('.skeleton').length).toBeGreaterThanOrEqual(4 * 4)
    const { container: c2 } = render(<EsqueletoFila />)
    expect(c2.firstChild.className).toContain('h-16')
  })

  it('la tarjeta y la gráfica reservan su alto desde el primer pintado', () => {
    const { container } = render(
      <>
        <EsqueletoTarjeta alto={216} />
        <EsqueletoGrafica alto={180} />
      </>
    )
    const altos = [...container.querySelectorAll('.skeleton')].map((e) => e.style.height).filter(Boolean)
    expect(altos).toContain('216px')
    expect(container.querySelector('[style*="height: 180px"]')).not.toBeNull()
  })

  it('la pantalla completa mantiene un solo role=status', () => {
    render(<EsqueletoPantalla variante="grafica" etiqueta="Cargando la pantalla" />)
    expect(screen.getAllByRole('status')).toHaveLength(1)
    expect(screen.getByRole('status', { name: 'Cargando la pantalla' })).toBeInTheDocument()
  })

  it('con prefers-reduced-motion el brillo se apaga (queda un bloque quieto)', () => {
    // el brillo usa la animación shimmer…
    expect(css).toMatch(/\.skeleton\s*\{[^}]*animation:\s*shimmer/)
    // …y el bloque reduced-motion la anula para .skeleton
    const reducido = css.match(/@media \(prefers-reduced-motion: reduce\)\s*\{[\s\S]*?\n\}/)[0]
    expect(reducido).toMatch(/\.skeleton[\s\S]*animation:\s*none\s*!important/)
  })

  it('ninguna pantalla de la app (salvo las de otro frente) deja «Cargando...» en texto plano', () => {
    const fs = require('node:fs')
    const pantallas = ['Categorias', 'Cuentas', 'Deudas', 'Metas', 'Recurrentes', 'ReglasCategoria', 'EntrenarCategorias', 'Ahorcado', 'Conexiones', 'CuentasAmigos', 'Wrapped', 'DetalleMovimiento', 'Patrimonio', 'Informe', 'Presupuesto']
    for (const p of pantallas) {
      const fuente = fs.readFileSync(`${process.cwd()}/src/screens/${p}.jsx`, 'utf8')
      expect(fuente, p).not.toMatch(/>\s*Cargando\.\.\.\s*</)
    }
  })
})
