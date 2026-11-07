import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import TarjetaGestoRegistro, { GESTOS } from '../components/TarjetaGestoRegistro'

const URL_ATAJO = 'https://www.icloud.com/shortcuts/ejemplo'

describe('Tarjeta «Cuando el banco no avisa»', () => {
  beforeEach(() => localStorage.clear())

  it('arranca con el gesto recomendado y enlaza el atajo', () => {
    render(<TarjetaGestoRegistro url={URL_ATAJO} />)
    expect(screen.getByRole('link', { name: /Instalar «CuadraMe Registrar»/ })).toHaveAttribute('href', URL_ATAJO)
    expect(screen.getByRole('button', { name: /Tocar atrás del iPhone/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('pasos-gesto')).toHaveTextContent('Accesibilidad > Tocar > Tocar atrás')
  })

  it('cada persona elige su gesto y ve solo los pasos de ese', async () => {
    render(<TarjetaGestoRegistro url={URL_ATAJO} />)
    await userEvent.click(screen.getByRole('button', { name: /Botón de acción/ }))
    expect(screen.getByRole('button', { name: /Botón de acción/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Tocar atrás del iPhone/ })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByTestId('pasos-gesto')).toHaveTextContent('Ajustes > Botón de acción')
    expect(screen.getByTestId('pasos-gesto')).not.toHaveTextContent('Tocar atrás')
    expect(screen.getByTestId('uso-gesto')).toHaveTextContent('mantén presionado el botón de acción')
  })

  it('recuerda la elección la próxima vez que se abre', async () => {
    const { unmount } = render(<TarjetaGestoRegistro url={URL_ATAJO} />)
    await userEvent.click(screen.getByRole('button', { name: /Decirle a Siri/ }))
    unmount()
    render(<TarjetaGestoRegistro url={URL_ATAJO} />)
    expect(screen.getByRole('button', { name: /Decirle a Siri/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('uso-gesto')).toHaveTextContent('Oye Siri, CuadraMe Registrar')
  })

  it('solo ofrece gestos que no sacan al usuario del comprobante', () => {
    expect(GESTOS.map((g) => g.id)).toEqual(['atras', 'boton', 'siri'])
    expect(GESTOS.filter((g) => g.recomendado)).toHaveLength(1)
  })
})
