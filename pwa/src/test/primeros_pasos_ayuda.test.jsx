// Asistente de primeros pasos, Centro de ayuda y mensajes en lenguaje llano.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({ conexionesEstado: vi.fn() }))
const push = vi.hoisted(() => ({ estadoPermiso: vi.fn(), activarPush: vi.fn(), pushSoportado: vi.fn() }))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/push', () => push)
vi.mock('../lib/AuthContext', () => ({ useAuth: () => ({ usuario: { id: 'u1', email: 'a@b.co', nombre: 'Ana' } }) }))

import AsistentePrimerUso from '../components/AsistentePrimerUso'
import Ayuda from '../screens/Ayuda'
import { PREGUNTAS, TEMAS, buscarPreguntas, agruparPorTema } from '../lib/ayuda'
import { TODOS_LOS_DESTINOS } from '../lib/navegacion'
import { armarPasos, detectarDispositivo, resumenProgreso, siguientePaso } from '../lib/primerUso'
import { mensajeAmable, mensajePorEstado } from '../lib/mensajes'

const UA_IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1'
const UA_ANDROID = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36'
const UA_PC = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'

function conexiones(extra = {}) {
  return {
    gmail: { conectado: false },
    atajo: { ultimo_uso: null },
    push: { suscripciones: 0 },
    conciliacion: { cuentas: [{ extracto: false }] },
    ...extra,
  }
}

const montar = (ui, ruta = '/') => render(<MemoryRouter initialEntries={[ruta]}>{ui}</MemoryRouter>)

beforeEach(() => {
  localStorage.clear()
  api.conexionesEstado.mockReset().mockResolvedValue(conexiones())
  push.estadoPermiso.mockReset().mockResolvedValue('default')
  push.pushSoportado.mockReset().mockReturnValue(false)
  push.activarPush.mockReset().mockResolvedValue(true)
  Object.defineProperty(window.navigator, 'userAgent', { value: UA_PC, configurable: true })
})

describe('primerUso: reglas puras', () => {
  it('detecta el dispositivo (incluye el iPad que se presenta como Mac)', () => {
    expect(detectarDispositivo(UA_IPHONE, 5)).toBe('ios')
    expect(detectarDispositivo('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)', 5)).toBe('ios')
    expect(detectarDispositivo('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)', 0)).toBe('otro')
    expect(detectarDispositivo(UA_ANDROID, 5)).toBe('android')
    expect(detectarDispositivo(UA_PC, 0)).toBe('otro')
  })

  it('cada paso sale del estado real y el atajo es solo de iPhone', () => {
    const datos = { cuentas: 2, instalada: true, permisoPush: 'default', gmailConectado: true, atajoUsado: false, hayExtracto: false }
    const ios = armarPasos({ dispositivo: 'ios', datos })
    expect(ios.map((p) => p.id)).toEqual(['cuentas', 'instalar', 'notificaciones', 'gmail', 'atajo', 'extracto'])
    expect(ios.filter((p) => p.hecho).map((p) => p.id)).toEqual(['cuentas', 'instalar', 'gmail'])
    expect(armarPasos({ dispositivo: 'android', datos }).map((p) => p.id)).not.toContain('atajo')
    expect(siguientePaso(ios).id).toBe('notificaciones')
  })

  it('un paso saltado cuenta como resuelto pero no como hecho; el completo se detecta', () => {
    const datos = { cuentas: 1, instalada: true, permisoPush: 'granted', gmailConectado: true, hayExtracto: false }
    const pasos = armarPasos({ dispositivo: 'android', datos, saltados: ['extracto'] })
    const r = resumenProgreso(pasos)
    expect(r).toMatchObject({ total: 5, resueltos: 5, hechos: 4, completo: true, pct: 100 })
    expect(resumenProgreso(armarPasos({ dispositivo: 'android', datos })).completo).toBe(false)
  })
})

describe('AsistentePrimerUso', () => {
  it('en Inicio muestra el avance y solo el paso que sigue, con botón directo a su pantalla', async () => {
    montar(<AsistentePrimerUso variante="inicio" />)
    expect(await screen.findByText('Primeros pasos')).toBeInTheDocument()
    expect(screen.getByTestId('progreso-pasos')).toHaveTextContent('1 de 5')
    // cuentas ya está hecho: el siguiente es instalar la app (abre la guía, no una pantalla)
    expect(screen.getByText('Ponla en tu celular')).toBeInTheDocument()
    expect(screen.queryByText('Conecta tu Gmail')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Ver todos los pasos' }))
    const gmail = screen.getByText('Conecta tu Gmail').closest('li')
    expect(within(gmail).getByRole('link', { name: 'Conectar Gmail' })).toHaveAttribute('href', '/sincronizacion')
    const extracto = screen.getByText('Sube tu primer extracto').closest('li')
    expect(within(extracto).getByRole('link', { name: 'Subir un extracto' })).toHaveAttribute('href', '/sincronizacion')
  })

  it('explica en lenguaje simple qué se lee de Gmail y qué no', async () => {
    montar(<AsistentePrimerUso variante="perfil" />)
    const caja = await screen.findByTestId('privacidad-gmail')
    expect(caja).toHaveTextContent('Solo los correos de tu banco')
    expect(caja).toHaveTextContent('No leemos tus correos personales')
    expect(caja).toHaveTextContent('No enviamos, borramos ni cambiamos ningún correo')
    expect(within(caja).getByRole('link')).toHaveAttribute('href', '/ayuda?p=gmail-seguro')
  })

  it('los pasos se marcan solos según el estado real (Gmail, avisos, extracto)', async () => {
    push.estadoPermiso.mockResolvedValue('granted')
    api.conexionesEstado.mockResolvedValue(
      conexiones({ gmail: { conectado: true }, conciliacion: { cuentas: [{ extracto: true }] } })
    )
    montar(<AsistentePrimerUso variante="perfil" />)
    await screen.findByText('Primeros pasos')
    const estado = (id) => document.querySelector(`[data-paso="${id}"]`).getAttribute('data-estado')
    await waitFor(() => expect(estado('gmail')).toBe('hecho'))
    expect(estado('notificaciones')).toBe('hecho')
    expect(estado('extracto')).toBe('hecho')
    expect(estado('instalar')).toBe('pendiente')
  })

  it('el atajo de Apple Pay solo aparece en iPhone y se marca al usarse', async () => {
    Object.defineProperty(window.navigator, 'userAgent', { value: UA_IPHONE, configurable: true })
    api.conexionesEstado.mockResolvedValue(conexiones({ atajo: { ultimo_uso: '2026-10-01T10:00:00' } }))
    montar(<AsistentePrimerUso variante="perfil" />)
    await screen.findByText('Primeros pasos')
    await waitFor(() => expect(document.querySelector('[data-paso="atajo"]')?.getAttribute('data-estado')).toBe('hecho'))
  })

  it('«Ocultar por ahora» lo quita de Inicio y se recuerda; en Perfil sigue disponible', async () => {
    const { unmount } = montar(<AsistentePrimerUso variante="inicio" />)
    await userEvent.click(await screen.findByRole('button', { name: 'Ocultar por ahora' }))
    expect(screen.queryByTestId('primeros-pasos-inicio')).not.toBeInTheDocument()
    unmount()

    montar(<AsistentePrimerUso variante="inicio" />)
    await waitFor(() => expect(api.conexionesEstado).toHaveBeenCalledTimes(2))
    expect(screen.queryByTestId('primeros-pasos-inicio')).not.toBeInTheDocument()

    montar(<AsistentePrimerUso variante="perfil" />)
    expect(await screen.findByTestId('primeros-pasos-perfil')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Volver a mostrarlos en Inicio/ })).toBeInTheDocument()
  })

  it('«Más tarde» deja un paso para después y «Retomar» lo vuelve a pedir', async () => {
    montar(<AsistentePrimerUso variante="perfil" />)
    await screen.findByText('Primeros pasos')
    const fila = () => document.querySelector('[data-paso="extracto"]')
    await userEvent.click(within(fila()).getByRole('button', { name: 'Más tarde' }))
    expect(fila().getAttribute('data-estado')).toBe('saltado')
    expect(screen.getByTestId('progreso-pasos')).toHaveTextContent('2 de 5')
    await userEvent.click(within(fila()).getByRole('button', { name: 'Retomar' }))
    expect(fila().getAttribute('data-estado')).toBe('pendiente')
  })

  it('completo: desaparece de Inicio y en Perfil dice «Todo listo»', async () => {
    push.estadoPermiso.mockResolvedValue('granted')
    api.conexionesEstado.mockResolvedValue(
      conexiones({ gmail: { conectado: true }, conciliacion: { cuentas: [{ extracto: true }] } })
    )
    const original = window.matchMedia
    window.matchMedia = () => ({ matches: true, addEventListener() {}, removeEventListener() {} }) // app instalada
    try {
      const inicio = montar(<AsistentePrimerUso variante="inicio" />)
      await waitFor(() => expect(api.conexionesEstado).toHaveBeenCalled())
      await new Promise((r) => setTimeout(r, 20))
      // El checklist ya no aparece; solo queda la celebración breve de Cuadri (descartable).
      expect(inicio.container.querySelector('[data-testid="celebracion-cuadri"]')).not.toBeNull()
      expect(screen.queryByText('Primeros pasos')).not.toBeInTheDocument()
      inicio.unmount()
      montar(<AsistentePrimerUso variante="perfil" />)
      expect(await screen.findByText('Todo listo')).toBeInTheDocument()
    } finally {
      window.matchMedia = original
    }
  })

  it('activar los avisos desde el paso: si el celular los rechaza, lo explica sin tecnicismos', async () => {
    push.pushSoportado.mockReturnValue(true)
    push.activarPush.mockRejectedValue(new Error('Permiso de notificaciones denegado'))
    montar(<AsistentePrimerUso variante="perfil" />)
    await screen.findByText('Primeros pasos')
    const fila = document.querySelector('[data-paso="notificaciones"]')
    await userEvent.click(within(fila).getByRole('button', { name: 'Activar avisos' }))
    expect(await within(fila).findByRole('alert')).toHaveTextContent('Permítelos para CuadraMe en los Ajustes del celular')
  })

  it('la guía de instalar muestra los pasos del iPhone con sus dibujos', async () => {
    Object.defineProperty(window.navigator, 'userAgent', { value: UA_IPHONE, configurable: true })
    montar(<AsistentePrimerUso variante="perfil" />)
    await screen.findByText('Primeros pasos')
    const fila = document.querySelector('[data-paso="instalar"]')
    await userEvent.click(within(fila).getByRole('button', { name: 'Ver cómo' }))
    const guia = await screen.findByTestId('guia-instalar')
    expect(within(guia).getByRole('list', { name: 'Pasos para iPhone' })).toBeInTheDocument()
    expect(guia).toHaveTextContent('Añadir a pantalla de inicio')
    expect(within(guia).queryByRole('list', { name: 'Pasos para Android' })).not.toBeInTheDocument()
  })

  it('un paso con dispositivo de escritorio muestra ambas guías y avisa que se hace desde el celular', async () => {
    montar(<AsistentePrimerUso variante="perfil" />)
    await screen.findByText('Primeros pasos')
    await userEvent.click(within(document.querySelector('[data-paso="instalar"]')).getByRole('button', { name: 'Ver cómo' }))
    const guia = await screen.findByTestId('guia-instalar')
    expect(guia).toHaveTextContent('desde tu celular')
    expect(within(guia).getByRole('list', { name: 'Pasos para Android' })).toBeInTheDocument()
  })

  it('si falla la carga no rompe la pantalla: deja los pasos pendientes', async () => {
    api.conexionesEstado.mockRejectedValue(new Error('x'))
    montar(<AsistentePrimerUso variante="perfil" />)
    expect(await screen.findByText('Primeros pasos')).toBeInTheDocument()
  })
})

describe('Centro de ayuda: contenido', () => {
  it('cada pregunta tiene id único, respuesta, tema válido y una acción a una pantalla que existe', () => {
    const ids = PREGUNTAS.map((p) => p.id)
    expect(new Set(ids).size).toBe(ids.length)
    const rutas = new Set(TODOS_LOS_DESTINOS.map((d) => d.to))
    for (const p of PREGUNTAS) {
      expect(TEMAS[p.tema], p.id).toBeTruthy()
      expect(p.respuesta.length, p.id).toBeGreaterThan(0)
      if (p.accion?.to) expect(rutas.has(p.accion.to) || p.accion.to === '/perfil', `${p.id} -> ${p.accion.to}`).toBe(true)
    }
  })

  it('responde las preguntas que más hacen los clientes nuevos', () => {
    const quien = (q) => buscarPreguntas(q).map((p) => p.id)
    expect(quien('extracto')).toContain('donde-extracto')
    expect(quien('clave pdf')[0]).toBe('clave-pdf')
    expect(quien('repetido')).toContain('pago-dos-veces')
    expect(quien('traslado')[0]).toBe('traslado')
    expect(quien('seguro gmail')[0]).toBe('gmail-seguro')
    expect(quien('borrar mis datos')).toContain('borrar-datos')
  })

  it('el buscador ignora mayúsculas, tildes y plurales', () => {
    expect(buscarPreguntas('EXTRACTOS').map((p) => p.id)).toEqual(buscarPreguntas('extracto').map((p) => p.id))
    expect(buscarPreguntas('contrasena').map((p) => p.id)).toContain('clave-pdf')
    expect(buscarPreguntas('zzzzqqq')).toEqual([])
    expect(buscarPreguntas('  ')).toEqual(PREGUNTAS)
  })

  it('no usa jerga técnica en lo que ve el cliente', () => {
    const jerga = /\b(token|endpoint|api|json|oauth|jwt|backend|http)\b/i
    for (const p of PREGUNTAS) {
      expect(jerga.test([p.pregunta, ...p.respuesta, p.accion?.texto || ''].join(' ')), p.id).toBe(false)
    }
  })

  it('agrupa por tema en el orden definido', () => {
    const grupos = agruparPorTema(PREGUNTAS)
    expect(grupos.map((g) => g.id)).toEqual(Object.keys(TEMAS))
  })
})

describe('Centro de ayuda: pantalla', () => {
  it('lista las preguntas, abre una respuesta y enlaza a la acción', async () => {
    montar(<Ayuda />)
    expect(screen.getByRole('heading', { name: 'Ayuda' })).toBeInTheDocument()
    const q = screen.getByRole('button', { name: '¿Dónde saco mi extracto?' })
    expect(q).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(q)
    expect(q).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('link', { name: 'Subir un extracto' })).toHaveAttribute('href', '/sincronizacion')
  })

  it('el buscador filtra y, sin resultados, ofrece escribirnos', async () => {
    montar(<Ayuda />)
    const caja = screen.getByLabelText('¿Qué necesitas saber?')
    await userEvent.type(caja, 'gmail')
    expect(screen.getByRole('button', { name: '¿Es seguro conectar mi Gmail?' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '¿Qué es un traslado?' })).not.toBeInTheDocument()

    fireEvent.change(caja, { target: { value: 'zzzzqqq' } })
    expect(screen.getByText('No encontramos eso')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Escribirnos/ })).toHaveAttribute('href', expect.stringContaining('mailto:'))
  })

  it('un enlace directo deja abierta la respuesta pedida', () => {
    montar(<Ayuda />, '/ayuda?p=gmail-seguro')
    expect(screen.getByRole('button', { name: '¿Es seguro conectar mi Gmail?' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText(/no enviamos nada/i)).toBeInTheDocument()
  })

  it('una pregunta con guía visual la abre', async () => {
    montar(<Ayuda />)
    await userEvent.click(screen.getByRole('button', { name: '¿Cómo pongo CuadraMe en mi celular?' }))
    await userEvent.click(screen.getByRole('button', { name: 'Ver los pasos con dibujos' }))
    expect(await screen.findByTestId('guia-instalar')).toBeInTheDocument()
  })
})

describe('Mensajes en lenguaje llano', () => {
  it('traduce los textos técnicos y deja pasar los que ya son claros', () => {
    expect(mensajeAmable('Error 404')).toBe(mensajePorEstado(404))
    expect(mensajeAmable('Not Found', { status: 404 })).toMatch(/No encontramos/)
    expect(mensajeAmable('Invalid login credentials')).toMatch(/correo o la contraseña/)
    expect(mensajeAmable('Failed to fetch')).toMatch(/Sin conexión/)
    expect(mensajeAmable('jwt expired')).toMatch(/sesión venció/)
    expect(mensajeAmable('Unexpected token < in JSON at position 0')).toMatch(/Tuvimos un problema/)
    expect(mensajeAmable('La cuenta ya existe')).toBe('La cuenta ya existe')
    expect(mensajeAmable('', { porDefecto: 'No pudimos guardar.' })).toBe('No pudimos guardar.')
    expect(mensajeAmable('Tu API key no es válida')).toBe('Tu clave no es válida')
  })

  it('ningún mensaje por código HTTP trae números ni jerga', () => {
    for (const s of [400, 401, 403, 404, 409, 413, 422, 429, 500, 503, 418]) {
      expect(mensajePorEstado(s)).not.toMatch(/\d{3}|token|api|endpoint/i)
    }
  })
})
