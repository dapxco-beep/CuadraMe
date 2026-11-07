// Catálogo de atajos en «Registro automático»: los 4 atajos con su botón de instalar, para quién sirven y sus pasos.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({
  apiKey: vi.fn(),
  regenerarApiKey: vi.fn(),
  conexionesEstado: vi.fn(),
}))
vi.mock('../lib/api', () => ({ api }))
const capturas = vi.hoisted(() => ({ CAPTURAS_REALES: {} }))
vi.mock('../lib/capturasGuia', () => capturas)

import { DialogosProvider } from '../lib/DialogosContext'
import CatalogoAtajos, { ATAJOS } from '../components/CatalogoAtajos'
import ConectarDispositivo from '../screens/ConectarDispositivo'
import {
  ATAJO_CIERRE_URL, ATAJO_ICLOUD_URL, ATAJO_NOTIFICACIONES_URL, ATAJO_REGISTRAR_URL,
} from '../lib/atajosEnlaces'

const CLAVE = { clave: 'cdm_demo', cargando: false, tieneClave: true, prefijo: '', recienCreada: false, crearNueva: vi.fn() }

const montarCatalogo = () =>
  render(
    <DialogosProvider>
      <MemoryRouter>
        <CatalogoAtajos claveAtajo={CLAVE} />
      </MemoryRouter>
    </DialogosProvider>
  )

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  capturas.CAPTURAS_REALES = {}
  localStorage.clear()
})

describe('Catálogo de atajos', () => {
  it('muestra los 4 atajos, cada uno con su botón de instalar al enlace correcto', () => {
    montarCatalogo()
    const esperados = {
      'apple-pay': ATAJO_ICLOUD_URL,
      notificaciones: ATAJO_NOTIFICACIONES_URL,
      registrar: ATAJO_REGISTRAR_URL,
      cierre: ATAJO_CIERRE_URL,
    }
    expect(ATAJOS.map((a) => a.id)).toEqual(Object.keys(esperados))
    for (const [id, url] of Object.entries(esperados)) {
      const tarjeta = screen.getByTestId(`atajo-${id}`)
      const boton = within(tarjeta).getByRole('link', { name: /^Instalar CuadraMe/ })
      expect(boton).toHaveAttribute('href', url)
      expect(boton).toHaveAttribute('target', '_blank')
      expect(boton).toHaveAttribute('rel', expect.stringContaining('noopener'))
    }
  })

  it('cada atajo dice para quién es y trae sus pasos numerados', () => {
    montarCatalogo()
    for (const a of ATAJOS) {
      const tarjeta = screen.getByTestId(`atajo-${a.id}`)
      expect(tarjeta).toHaveTextContent(`Para ti si: ${a.paraQuien}`)
      const pasos = within(screen.getByTestId(`pasos-${a.id}`)).getAllByRole('listitem')
      expect(pasos.length).toBeGreaterThanOrEqual(4)
    }
    expect(screen.getByTestId('pasos-registrar')).toHaveTextContent('Tocar atrás')
    expect(screen.getByTestId('pasos-notificaciones')).toHaveTextContent('Cuando recibo una notificación')
    expect(screen.getByTestId('pasos-apple-pay')).toHaveTextContent('Transacción')
  })

  it('ayuda a elegir y muestra la clave para copiarla en el mismo lugar', () => {
    montarCatalogo()
    const guia = screen.getByTestId('cual-instalo')
    expect(guia).toHaveTextContent('Pagas con Apple Pay')
    expect(guia).toHaveTextContent('Tu banco no avisa')
    expect(screen.getByTestId('clave-catalogo')).toHaveTextContent('cdm_demo')
    expect(screen.getByRole('button', { name: 'Copiar clave' })).toBeInTheDocument()
  })

  it('usa las capturas reales cuando existen y el dibujo propio cuando no', () => {
    montarCatalogo()
    expect(screen.getByTestId('atajo-registrar').querySelectorAll('img')).toHaveLength(0)
    expect(screen.getByTestId('atajo-registrar').querySelectorAll('svg[role="img"]').length).toBeGreaterThan(0)
    capturas.CAPTURAS_REALES = { registrar: [{ src: '/guia/registrar-1.webp', alt: 'Tocar atrás en Ajustes' }] }
    const { container } = montarCatalogo()
    const real = container.querySelector('img[src="/guia/registrar-1.webp"]')
    expect(real).not.toBeNull()
    expect(real).toHaveAttribute('alt', 'Tocar atrás en Ajustes')
  })

  it('en la pestaña «Registro automático» de iPhone el catálogo aparece desde la primera pantalla', async () => {
    api.apiKey.mockResolvedValue({ api_key: 'cdm_demo', tiene_clave: true, nueva: false })
    api.conexionesEstado.mockResolvedValue({ atajo: { ultimo_uso: null } })
    localStorage.setItem('cuadrame:atajo-paso', '-1')
    render(
      <DialogosProvider>
        <MemoryRouter>
          <ConectarDispositivo />
        </MemoryRouter>
      </DialogosProvider>
    )
    expect(await screen.findByTestId('catalogo-atajos')).toBeInTheDocument()
    expect(screen.getByTestId('atajo-notificaciones')).toBeInTheDocument()
    expect(screen.getByTestId('atajo-registrar')).toBeInTheDocument()
  })
})
