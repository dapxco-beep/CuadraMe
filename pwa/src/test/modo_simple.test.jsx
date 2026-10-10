// Modo simple: menú con lo esencial, «Más funciones» plegado con una frase de qué hace cada una,
// funciones que aparecen solas al usarlas, Inicio de 3 bloques y primer uso en un solo camino.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from './userEvent.js'
import { MemoryRouter } from 'react-router-dom'

const api = vi.hoisted(() => ({}))
const auth = vi.hoisted(() => ({ usuario: { id: 'u1', email: 'l@test.com', nombre: 'Laura Gómez' } }))
vi.mock('../lib/api', () => ({ api }))
vi.mock('../lib/AuthContext', () => ({ useAuth: () => auth }))
vi.mock('../lib/CategoriasContext', () => ({ useCategorias: () => ({ iconoDe: () => '💳' }) }))

import { ThemeProvider } from '../lib/ThemeContext'
import { DialogosProvider } from '../lib/DialogosContext'
import ShellApp from '../components/ShellApp'
import BottomNav from '../components/BottomNav'
import Inicio from '../screens/Inicio'
import Perfil from '../screens/Perfil'
import {
  EXPLICACION, GRUPOS, ITEMS_MAS, MAS_FUNCIONES_ID, buscarDestinos, extrasRiel, gruposSegunModo,
} from '../lib/navegacion'
import { detectarFuncionesEnUso, guardarModoCompleto, leerModoCompleto } from '../lib/modoSimple'
import { armarCamino, CAMINO, META_CAMINO } from '../lib/primerUso'
import { fechaHace, gastosDeLaSemana, siguientePasoInicio } from '../lib/inicioSimple'

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

let contador = 0
beforeEach(() => {
  localStorage.clear()
  contador += 1
  // un usuario distinto por prueba: la revisión de «funciones en uso» es una vez por sesión y usuario
  auth.usuario = { id: `u${contador}`, email: 'l@test.com', nombre: 'Laura Gómez' }
  Object.assign(api, {
    metas: vi.fn().mockResolvedValue([]),
    deudas: vi.fn().mockResolvedValue([]),
    recurrentes: vi.fn().mockResolvedValue([]),
    patrimonio: vi.fn().mockResolvedValue({ activos: [], pasivos: [] }),
  })
})
afterEach(() => {
  window.matchMedia = matchMediaOriginal
})

describe('navegacion: grupos según el modo', () => {
  it('modo completo = los grupos de siempre', () => {
    expect(gruposSegunModo({ completo: true })).toBe(GRUPOS)
  })

  it('modo simple: lo esencial a la vista y el resto en «Más funciones», plegado y explicado', () => {
    const g = gruposSegunModo({ completo: false })
    expect(g.map((x) => x.id)).toEqual(['esencial', MAS_FUNCIONES_ID])
    expect(g[0].items.map((i) => i.label)).toEqual(['Traer movimientos', 'Perfil', 'Ayuda'])
    const mas = g[1]
    expect(mas.plegado).toBe(true)
    // todas las demás pantallas siguen ahí (las rutas no cambian) y cada una trae su frase
    const rutasMas = mas.items.map((i) => i.to)
    for (const i of ITEMS_MAS.filter((x) => !g[0].items.some((e) => e.to === x.to))) {
      expect(rutasMas).toContain(i.to)
      expect(EXPLICACION[i.to], `falta la frase de ${i.to}`).toBeTruthy()
    }
    expect(mas.items.every((i) => i.explica)).toBe(true)
  })

  it('una función que ya usa la persona sube sola al menú', () => {
    const g = gruposSegunModo({ completo: false, enUso: ['/metas', '/deudas'] })
    expect(g.map((x) => x.id)).toEqual(['esencial', 'en-uso', MAS_FUNCIONES_ID])
    expect(g[1].items.map((i) => i.label)).toEqual(['Deudas', 'Metas'])
    expect(g[2].items.map((i) => i.to)).not.toContain('/metas')
  })

  it('el buscador sigue encontrando todo, aunque esté plegado', () => {
    expect(buscarDestinos('deudas').map((d) => d.to)).toContain('/deudas')
    expect(buscarDestinos('4x1000').map((d) => d.to)).toContain('/impuestos')
  })

  it('el riel solo suma «Traer movimientos» en modo simple', () => {
    expect(extrasRiel({ completo: false }).map((i) => i.to)).toEqual(['/sincronizacion'])
    expect(extrasRiel({ completo: true }).map((i) => i.to)).toEqual(['/patrimonio', '/sincronizacion'])
  })
})

describe('modoSimple: preferencia y detección', () => {
  it('por defecto es simple; el interruptor se guarda por usuario', () => {
    expect(leerModoCompleto('a')).toBe(false)
    guardarModoCompleto('a', true)
    expect(leerModoCompleto('a')).toBe(true)
    expect(leerModoCompleto('b')).toBe(false)
    guardarModoCompleto('a', false)
    expect(leerModoCompleto('a')).toBe(false)
  })

  it('detecta las funciones con datos y tolera que una falle', async () => {
    const rutas = await detectarFuncionesEnUso({
      metas: async () => [{ id: 1 }],
      deudas: async () => {
        throw new Error('caído')
      },
      recurrentes: async () => [],
      patrimonio: async () => ({ activos: [{ id: 9 }] }),
    })
    expect(rutas).toEqual(['/metas', '/patrimonio'])
  })
})

describe('Menú «Más» (teléfono) en modo simple', () => {
  function abrirMas() {
    simularAncho(390)
    render(
      <MemoryRouter>
        <BottomNav />
      </MemoryRouter>
    )
    return userEvent.click(screen.getByRole('button', { name: 'Más' }))
  }

  it('muestra solo lo esencial y «Más funciones» plegado; al abrirlo, cada una con su frase', async () => {
    await abrirMas()
    const hoja = await screen.findByRole('dialog', { name: 'Más opciones' })
    for (const nombre of ['Traer movimientos', 'Perfil', 'Ayuda']) {
      expect(within(hoja).getByRole('link', { name: nombre })).toBeInTheDocument()
    }
    expect(within(hoja).queryByRole('link', { name: /Deudas/ })).toBeNull()
    const boton = within(hoja).getByRole('button', { name: /Más funciones/ })
    expect(boton).toHaveAttribute('aria-expanded', 'false')

    await userEvent.click(boton)
    expect(boton).toHaveAttribute('aria-expanded', 'true')
    const deudas = within(hoja).getByRole('link', { name: /Deudas/ })
    expect(deudas).toHaveAttribute('href', '/deudas')
    expect(deudas).toHaveTextContent('Lo que debes y cuál conviene pagar primero.')
  })

  it('si ya tiene metas, «Metas» aparece sola en «Lo que ya usas»', async () => {
    api.metas.mockResolvedValue([{ id: 'm1', nombre: 'Viaje' }])
    await abrirMas()
    const hoja = await screen.findByRole('dialog', { name: 'Más opciones' })
    const seccion = await waitFor(() => {
      const h = within(hoja).getByRole('heading', { name: 'Lo que ya usas' })
      return h.closest('section')
    })
    expect(within(seccion).getByRole('link', { name: /Metas/ })).toHaveAttribute('href', '/metas')
  })

  it('con «Mostrar todas las funciones» vuelve el menú completo por grupos', async () => {
    guardarModoCompleto(auth.usuario.id, true)
    await abrirMas()
    const hoja = await screen.findByRole('dialog', { name: 'Más opciones' })
    for (const g of GRUPOS) expect(within(hoja).getByRole('heading', { name: g.titulo })).toBeInTheDocument()
    expect(within(hoja).getByRole('link', { name: 'Deudas' })).toBeInTheDocument()
  })
})

describe('Barras de pantalla ancha en modo simple', () => {
  it('riel: Inicio, Movimientos, Presupuesto y Traer movimientos; sin Patrimonio', () => {
    simularAncho(820)
    render(
      <MemoryRouter>
        <ShellApp>
          <p>Pantalla</p>
        </ShellApp>
      </MemoryRouter>
    )
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    for (const nombre of ['Inicio', 'Movimientos', 'Presupuesto', 'Traer movimientos']) {
      expect(within(nav).getByRole('link', { name: nombre })).toBeInTheDocument()
    }
    expect(within(nav).queryByRole('link', { name: 'Patrimonio' })).toBeNull()
  })

  it('barra lateral: «Más funciones» empieza plegado y se abre con un toque', async () => {
    simularAncho(1440)
    render(
      <MemoryRouter>
        <ShellApp>
          <p>Pantalla</p>
        </ShellApp>
      </MemoryRouter>
    )
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    expect(within(nav).getByRole('link', { name: 'Traer movimientos' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Perfil' })).toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: /Deudas/ })).toBeNull()
    const boton = within(nav).getByRole('button', { name: 'Más funciones' })
    expect(boton).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(boton)
    expect(within(nav).getByRole('link', { name: /Deudas/ })).toBeInTheDocument()
  })
})

describe('Perfil: «Mostrar todas las funciones»', () => {
  it('es un interruptor apagado por defecto que cambia el modo y oculta lo avanzado', async () => {
    Object.assign(api, {
      confianzaAutoimport: vi.fn().mockResolvedValue({ confianza_autoimport: 0.75 }),
      apiKey: vi.fn().mockResolvedValue({ api_key: 'k' }),
    })
    render(
      <ThemeProvider>
        <DialogosProvider>
          <MemoryRouter>
            <Perfil />
          </MemoryRouter>
        </DialogosProvider>
      </ThemeProvider>
    )
    const interruptor = await screen.findByRole('switch', { name: 'Mostrar todas las funciones' })
    expect(interruptor).toHaveAttribute('aria-checked', 'false')
    expect(screen.queryByText('Planeación')).toBeNull()
    await userEvent.click(interruptor)
    expect(interruptor).toHaveAttribute('aria-checked', 'true')
    expect(leerModoCompleto(auth.usuario.id)).toBe(true)
    expect(screen.getByText('Planeación')).toBeInTheDocument()
  })
})

describe('Primer uso: el camino de 3 pasos', () => {
  it('la meta es explícita y los pasos son crear cuenta, traer movimientos y ver el resumen', () => {
    expect(META_CAMINO).toBe('Ver a dónde se va tu plata en 5 minutos')
    expect(CAMINO.map((p) => p.titulo)).toEqual(['Crea tu cuenta', 'Trae tus movimientos', 'Mira tu resumen'])
    // el atajo no es obligatorio: el paso 2 habla de correo, extracto y Excel
    expect(CAMINO[1].apoyo).toMatch(/correo/)
    expect(CAMINO[1].apoyo).toMatch(/extracto/)
    expect(CAMINO[1].apoyo).toMatch(/Excel/)
    expect(JSON.stringify(CAMINO)).not.toMatch(/atajo/i)
  })

  it('cada paso se marca solo según lo que hay', () => {
    expect(armarCamino({}).map((p) => p.hecho)).toEqual([false, false, false])
    expect(armarCamino({ cuentas: 1 }).map((p) => p.hecho)).toEqual([true, false, false])
    expect(armarCamino({ cuentas: 1, movimientos: 3 }).map((p) => p.hecho)).toEqual([true, true, false])
    expect(armarCamino({ cuentas: 1, movimientos: 3, resumenVisto: true }).every((p) => p.hecho)).toBe(true)
    // sin movimientos no hay resumen que ver
    expect(armarCamino({ cuentas: 1, resumenVisto: true })[2].hecho).toBe(false)
  })
})

describe('Inicio simplificado', () => {
  function montarInicio() {
    return render(
      <ThemeProvider>
        <DialogosProvider>
          <MemoryRouter>
            <Inicio />
          </MemoryRouter>
        </DialogosProvider>
      </ThemeProvider>
    )
  }
  const MOV = (id, extra = {}) => ({
    id, fecha: new Date().toISOString(), descripcion: `Compra ${id}`, categoria: 'Mercado', tipo: 'expense', monto: 10000, ...extra,
  })

  function mocksInicio({ cuentas = 1, movs = [], tareas = [] } = {}) {
    Object.assign(api, {
      cuentas: vi.fn().mockResolvedValue(
        Array.from({ length: cuentas }, (_, i) => ({ id: `c${i}`, nombre: 'Bancolombia', saldo: 500_000, moneda: 'COP', tipo: 'ahorro', icono: '🏦' }))
      ),
      movimientos: vi.fn().mockResolvedValue(movs),
      reporteMensual: vi.fn().mockResolvedValue({ salud: { score: 80, tips: ['ok'] }, top_categorias: [] }),
      disponibleHoy: vi.fn().mockResolvedValue({ categorias: [] }),
      enMiBolsillo: vi.fn().mockResolvedValue({ saldo_total: 500_000, recurrentes_pendientes_mes: 0, aportes_comprometidos_mes: 0, disponible_real: 400_000, disponible_real_por_dia: 20_000 }),
      gmailEstado: vi.fn().mockResolvedValue({ conectado: true }),
      sincronizacionEstado: vi.fn().mockResolvedValue({ tareas }),
      tendencias: vi.fn().mockResolvedValue({ meses: [] }),
      consejos: vi.fn().mockResolvedValue([{ id: 'c1', titulo: 'Ahorra algo cada semana', texto: 'Aunque sea poco.', prioridad: 3, accion: { texto: 'Ver presupuesto', ruta: '/presupuesto' } }]),
    })
  }

  it('cuenta nueva: una meta, 3 pasos y barra de progreso; solo el paso que sigue trae botón', async () => {
    mocksInicio({ cuentas: 0, movs: [] })
    montarInicio()
    const camino = await screen.findByTestId('camino-primer-uso')
    expect(within(camino).getByRole('heading', { name: 'Ver a dónde se va tu plata en 5 minutos' })).toBeInTheDocument()
    expect(within(camino).getAllByRole('listitem')).toHaveLength(3)
    expect(within(camino).getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
    expect(within(camino).getByRole('link', { name: 'Crear mi cuenta' })).toHaveAttribute('href', '/cuentas')
    expect(within(camino).queryByRole('link', { name: 'Traer movimientos' })).toBeNull()
    // el recorrido largo no se abre solo; es una invitación discreta
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByRole('button', { name: /Conoce CuadraMe en 1 minuto/ })).toBeInTheDocument()
    // mientras el camino está a la vista, no se repite otro «siguiente paso»
    expect(screen.queryByTestId('siguiente-paso')).toBeNull()
  })

  it('con cuenta y sin movimientos, el paso 2 es el que sigue (el atajo no es obligatorio)', async () => {
    mocksInicio({ cuentas: 1, movs: [] })
    montarInicio()
    const camino = await screen.findByTestId('camino-primer-uso')
    expect(within(camino).getByTestId('progreso-camino')).toHaveTextContent('1 de 3 pasos')
    expect(within(camino).getByRole('link', { name: 'Traer movimientos' })).toHaveAttribute('href', '/sincronizacion')
    expect(camino).not.toHaveTextContent(/atajo/i)
  })

  it('bloque 1: saldo disponible, gastos de la semana y 3 últimos movimientos; bloque 3: un consejo', async () => {
    mocksInicio({ cuentas: 1, movs: [MOV('a'), MOV('b'), MOV('c'), MOV('d')] })
    api.movimientos.mockImplementation((limite) =>
      Promise.resolve([MOV('a'), MOV('b'), MOV('c'), MOV('d')].slice(0, limite >= 100 ? 99 : limite))
    )
    montarInicio()
    const b1 = await screen.findByRole('region', { name: 'Cuánto tienes y qué pasó esta semana' })
    expect(b1).toHaveTextContent('Tienes disponible')
    await waitFor(() => expect(within(b1).getByTestId('gastos-semana')).toHaveTextContent(/40\.000/))
    const lista = screen.getByRole('region', { name: 'Últimos movimientos' })
    expect(within(lista).getAllByRole('link', { name: /Compra/ })).toHaveLength(3)
    expect(await screen.findByTestId('consejo-para-ti')).toHaveTextContent('Ahorra algo cada semana')
    // el resto de tarjetas queda tras «Ver más»
    expect(screen.queryByRole('button', { name: /Presupuesto del mes/ })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Ver más' }))
    expect(await screen.findByRole('button', { name: /Presupuesto del mes/ })).toBeInTheDocument()
  })

  it('un solo siguiente paso: categorizar si hay movimientos sin tipo', async () => {
    mocksInicio({ cuentas: 1, movs: [MOV('a')], tareas: [{ id: 'movimientos_por_categorizar', cantidad: 3 }] })
    localStorage.setItem('cuadrame:primeros-pasos', JSON.stringify({ [auth.usuario.id]: { resumenVisto: true, oculto: true, saltados: [] } }))
    montarInicio()
    const paso = await screen.findByTestId('siguiente-paso')
    await waitFor(() => expect(paso).toHaveAttribute('data-paso', 'categorizar'))
    expect(paso).toHaveTextContent('Ponle tipo a 3 gastos')
    expect(within(paso).getAllByRole('link')).toHaveLength(1)
  })

  it('todo al día: el siguiente paso es mirar el presupuesto', async () => {
    mocksInicio({ cuentas: 1, movs: [MOV('a')] })
    localStorage.setItem('cuadrame:primeros-pasos', JSON.stringify({ [auth.usuario.id]: { resumenVisto: true, oculto: true, saltados: [] } }))
    montarInicio()
    const paso = await screen.findByTestId('siguiente-paso')
    expect(paso).toHaveAttribute('data-paso', 'presupuesto')
    expect(within(paso).getByRole('link', { name: 'Ver presupuesto' })).toHaveAttribute('href', '/presupuesto')
  })

  it('al completar los 3 pasos, instalar, avisos y atajo quedan como «Mejora tu experiencia»', async () => {
    mocksInicio({ cuentas: 1, movs: [MOV('a')] })
    localStorage.setItem('cuadrame:primeros-pasos', JSON.stringify({ [auth.usuario.id]: { resumenVisto: true, saltados: [] } }))
    montarInicio()
    const mejora = await screen.findByRole('region', { name: 'Mejora tu experiencia' })
    expect(within(mejora).getByRole('heading', { name: 'Mejora tu experiencia' })).toBeInTheDocument()
    expect(screen.queryByTestId('camino-primer-uso')).toBeNull()
    expect(within(mejora).queryByText('Crea tus cuentas')).toBeNull()
  })

  it('modo completo: Inicio con todas las secciones, como siempre', async () => {
    mocksInicio({ cuentas: 1, movs: [MOV('a')] })
    guardarModoCompleto(auth.usuario.id, true)
    montarInicio()
    expect(await screen.findByRole('button', { name: /Presupuesto del mes/ })).toBeInTheDocument()
    expect(screen.queryByTestId('inicio-simple')).toBeNull()
  })
})

describe('inicioSimple: reglas puras', () => {
  it('elige UN siguiente paso según el estado', () => {
    expect(siguientePasoInicio({ cuentas: 0 }).id).toBe('cuenta')
    expect(siguientePasoInicio({ cuentas: 1, movimientos: 0 }).id).toBe('traer')
    expect(siguientePasoInicio({ cuentas: 1, movimientos: 5, sinCategorizar: 2 }).id).toBe('categorizar')
    expect(siguientePasoInicio({ cuentas: 1, movimientos: 5, sinCategorizar: 0 }).id).toBe('presupuesto')
  })

  it('suma solo los gastos de los últimos 7 días (los traslados no cuentan)', () => {
    const ahora = new Date('2026-10-09T12:00:00')
    expect(fechaHace(6, ahora)).toBe('2026-10-03')
    const movs = [
      { tipo: 'expense', monto: 100, fecha: '2026-10-09T08:00:00' },
      { tipo: 'expense', monto: 50, fecha: '2026-10-03T08:00:00' },
      { tipo: 'expense', monto: 999, fecha: '2026-10-02T08:00:00' },
      { tipo: 'income', monto: 5000, fecha: '2026-10-08T08:00:00' },
      { tipo: 'transfer', monto: 700, fecha: '2026-10-08T08:00:00' },
    ]
    expect(gastosDeLaSemana(movs, ahora)).toBe(150)
  })
})
