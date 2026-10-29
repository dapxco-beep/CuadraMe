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
import { HojaMas } from '../components/MenuMas'
import BottomNav from '../components/BottomNav'
import Inicio from '../screens/Inicio'
import InicioSimple from '../components/InicioSimple'
import Perfil from '../screens/Perfil'
import {
  EXPLICACION, GRUPOS, ITEMS_MAS, MAS_FUNCIONES_ID, RUTAS_AVANZADAS, buscarDestinos, extrasRiel, gruposSegunModo,
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

  it('modo simple: todo lo de todos los días a la vista por temas y solo lo avanzado plegado en «Avanzadas»', () => {
    const g = gruposSegunModo({ completo: false })
    expect(g.map((x) => x.id)).toEqual(['datos', 'dinero', 'juntos', 'ahorro', 'entender', 'ajustes', MAS_FUNCIONES_ID])
    const visibles = g.slice(0, -1).flatMap((x) => x.items.map((i) => i.to))
    // lo de cada día está a la vista
    for (const ruta of ['/sincronizacion', '/movimientos-correo', '/cuentas', '/deudas', '/recurrentes', '/amigos', '/hogares', '/colectas', '/metas', '/informe', '/cierre-mes', '/asistente', '/perfil', '/ayuda']) {
      expect(visibles, ruta).toContain(ruta)
    }
    // lo avanzado está aparte, plegado y explicado
    const avanzadas = g[g.length - 1]
    expect(avanzadas).toMatchObject({ titulo: 'Avanzadas', plegado: true })
    expect(avanzadas.items.map((i) => i.to).sort()).toEqual([...RUTAS_AVANZADAS].sort())
    expect(avanzadas.items.every((i) => i.explica), 'cada avanzada trae su frase').toBe(true)
    for (const ruta of RUTAS_AVANZADAS) expect(visibles).not.toContain(ruta)
    // nada se pierde: todas las pantallas siguen en el menú (las rutas no cambian)
    expect([...visibles, ...avanzadas.items.map((i) => i.to)].sort()).toEqual(ITEMS_MAS.map((i) => i.to).sort())
  })

  it('una función avanzada que la persona ya usa deja de ser avanzada: vuelve a su tema', () => {
    const g = gruposSegunModo({ completo: false, enUso: ['/patrimonio', '/impuestos'] })
    const ahorro = g.find((x) => x.id === 'ahorro').items.map((i) => i.to)
    expect(ahorro).toContain('/patrimonio')
    expect(g.find((x) => x.id === 'dinero').items.map((i) => i.to)).toContain('/impuestos')
    expect(g[g.length - 1].items.map((i) => i.to)).not.toContain('/patrimonio')
  })

  it('el buscador sigue encontrando todo, aunque esté plegado', () => {
    expect(buscarDestinos('deudas').map((d) => d.to)).toContain('/deudas')
    expect(buscarDestinos('4x1000').map((d) => d.to)).toContain('/impuestos')
  })

  it('el riel solo suma «Traer extractos» en modo simple', () => {
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

  it('lo de todos los días está a la vista; lo avanzado, plegado en «Avanzadas» y con su frase', async () => {
    await abrirMas()
    const hoja = await screen.findByRole('dialog', { name: 'Más opciones' })
    for (const nombre of ['Traer extractos', 'Movimientos del correo', 'Cuentas', 'Deudas', 'Metas', 'Perfil', 'Ayuda']) {
      expect(within(hoja).getByRole('link', { name: new RegExp('^' + nombre) }), nombre).toBeInTheDocument()
    }
    expect(within(hoja).queryByRole('link', { name: /Impuestos/ })).toBeNull()
    const boton = within(hoja).getByRole('button', { name: /Avanzadas/ })
    expect(boton).toHaveAttribute('aria-expanded', 'false')

    await userEvent.click(boton)
    expect(boton).toHaveAttribute('aria-expanded', 'true')
    const impuestos = within(hoja).getByRole('link', { name: /Impuestos/ })
    expect(impuestos).toHaveAttribute('href', '/impuestos')
    expect(impuestos).toHaveTextContent('Cuánto te cobran por el 4x1000')
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
  it('riel: Inicio, Movimientos, Presupuesto y Traer extractos; sin Patrimonio', () => {
    simularAncho(820)
    render(
      <MemoryRouter>
        <ShellApp>
          <p>Pantalla</p>
        </ShellApp>
      </MemoryRouter>
    )
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    for (const nombre of ['Inicio', 'Movimientos', 'Presupuesto', 'Traer extractos']) {
      expect(within(nav).getByRole('link', { name: nombre })).toBeInTheDocument()
    }
    expect(within(nav).queryByRole('link', { name: 'Patrimonio' })).toBeNull()
  })

  it('barra lateral: lo diario a la vista y «Avanzadas» empieza plegado y se abre con un toque', async () => {
    simularAncho(1440)
    render(
      <MemoryRouter>
        <ShellApp>
          <p>Pantalla</p>
        </ShellApp>
      </MemoryRouter>
    )
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    expect(within(nav).getByRole('link', { name: /^Traer extractos/ })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Perfil' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Deudas/ })).toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: /Impuestos/ })).toBeNull()
    const boton = within(nav).getByRole('button', { name: 'Avanzadas' })
    expect(boton).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(boton)
    expect(within(nav).getByRole('link', { name: /Impuestos/ })).toBeInTheDocument()
  })
})

describe('«Mostrar todas las funciones» vive en el menú «Más»', () => {
  it('es un interruptor apagado por defecto, al final de la hoja, que cambia el modo', async () => {
    render(
      <MemoryRouter>
        <HojaMas onCerrar={() => {}} pathname="/" />
      </MemoryRouter>
    )
    const interruptor = await screen.findByRole('switch', { name: 'Mostrar todas las funciones' })
    expect(interruptor).toHaveAttribute('aria-checked', 'false')
    await userEvent.click(interruptor)
    expect(interruptor).toHaveAttribute('aria-checked', 'true')
    expect(leerModoCompleto(auth.usuario.id)).toBe(true)
  })

  it('Perfil ya no trae el interruptor, solo un enlace corto que hace lo mismo', async () => {
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
    const enlace = await screen.findByTestId('enlace-todas-funciones')
    expect(screen.queryByRole('switch', { name: 'Mostrar todas las funciones' })).toBeNull()
    expect(screen.queryByText('Planeación')).toBeNull()
    await userEvent.click(enlace)
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
    expect(within(camino).queryByRole('link', { name: /^Traer extractos/ })).toBeNull()
    // el recorrido largo no se abre solo y, mientras el camino de 3 pasos está a la vista, tampoco compite con él
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByRole('button', { name: /Conoce CuadraMe en 1 minuto/ })).toBeNull()
    // mientras el camino está a la vista, no se repite otro «siguiente paso»
    expect(screen.queryByTestId('siguiente-paso')).toBeNull()
  })

  it('con cuenta y sin movimientos, el paso 2 es el que sigue (el atajo no es obligatorio)', async () => {
    mocksInicio({ cuentas: 1, movs: [] })
    montarInicio()
    const camino = await screen.findByTestId('camino-primer-uso')
    expect(within(camino).getByTestId('progreso-camino')).toHaveTextContent('1 de 3 pasos')
    expect(within(camino).getByRole('link', { name: /^Traer extractos/ })).toHaveAttribute('href', '/sincronizacion')
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
    // a la vista: saldo, accesos y «Este mes»; lo reciente y el consejo quedan tras «Ver más»
    expect(screen.getByTestId('acciones-rapidas')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Últimos movimientos' })).toBeNull()
    expect(screen.queryByTestId('consejo-para-ti')).toBeNull()
    expect(screen.queryByRole('button', { name: /Presupuesto/ })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Ver más' }))
    const lista = await screen.findByRole('region', { name: 'Últimos movimientos' })
    expect(within(lista).getAllByRole('link', { name: /Compra/ })).toHaveLength(3)
    expect(await screen.findByTestId('consejo-para-ti')).toHaveTextContent('Ahorra algo cada semana')
    expect(await screen.findByRole('button', { name: /Presupuesto/ })).toBeInTheDocument()
  })

  it('un solo siguiente paso: categorizar si hay movimientos sin tipo', async () => {
    mocksInicio({ cuentas: 1, movs: [MOV('a')], tareas: [{ id: 'movimientos_por_categorizar', cantidad: 3 }] })
    localStorage.setItem('cuadrame:primeros-pasos', JSON.stringify({ [auth.usuario.id]: { resumenVisto: true, oculto: true, saltados: [] } }))
    montarInicio()
    const paso = await screen.findByTestId('siguiente-paso')
    await waitFor(() => expect(paso).toHaveAttribute('data-paso', 'categorizar'))
    expect(paso).toHaveTextContent('Ordena lo que más pesa (opcional)')
    expect(within(paso).getByRole('link')).toHaveAttribute('href', '/categorizar')
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

  it('al completar los 3 pasos, «Mejora tu experiencia» sale de Inicio y queda tras «Ver la guía de primeros pasos» en Perfil', async () => {
    mocksInicio({ cuentas: 1, movs: [MOV('a')] })
    localStorage.setItem('cuadrame:primeros-pasos', JSON.stringify({ [auth.usuario.id]: { resumenVisto: true, saltados: [] } }))
    montarInicio()
    expect(await screen.findByTestId('inicio-simple')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Mejora tu experiencia' })).toBeNull()
    expect(screen.queryByTestId('camino-primer-uso')).toBeNull()
    // una sola guía a la vista: el siguiente paso (y no «¿Qué puedes hacer?» a la vez)
    expect(screen.getByTestId('siguiente-paso')).toBeInTheDocument()
    expect(screen.queryByTestId('que-se-puede-hacer')).toBeNull()
  })

  it('sin camino ni siguiente paso, «¿Qué puedes hacer?» ocupa el lugar de la guía', () => {
    render(
      <MemoryRouter>
        <InicioSimple saldo={1000} gastosSemana={0} recientes={[]} siguiente={null} enCamino={false} fmt={(n) => String(n)} iconoDe={() => ''} />
      </MemoryRouter>
    )
    expect(screen.getByTestId('que-se-puede-hacer')).toBeInTheDocument()
  })

  it('con el camino de 3 pasos a la vista es la única guía (sin recorrido, sin siguiente paso, sin «¿Qué puedes hacer?»)', async () => {
    mocksInicio({ cuentas: 1, movs: [] })
    montarInicio()
    await screen.findByTestId('camino-primer-uso')
    expect(screen.queryByTestId('que-se-puede-hacer')).toBeNull()
    expect(screen.queryByTestId('siguiente-paso')).toBeNull()
    expect(screen.queryByTestId('recorrido-retomar')).toBeNull()
  })

  it('modo completo: Inicio con todas las secciones, como siempre', async () => {
    mocksInicio({ cuentas: 1, movs: [MOV('a')] })
    guardarModoCompleto(auth.usuario.id, true)
    montarInicio()
    expect(await screen.findByRole('button', { name: /Presupuesto/ })).toBeInTheDocument()
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
      { id: 'a', tipo: 'expense', monto: 100, fecha: '2026-10-09T08:00:00' },
      { id: 'b', tipo: 'expense', monto: 50, fecha: '2026-10-03T08:00:00' },
      { id: 'c', tipo: 'expense', monto: 999, fecha: '2026-10-02T08:00:00' },
      { id: 'd', tipo: 'income', monto: 5000, fecha: '2026-10-08T08:00:00' },
      { id: 'e', tipo: 'transfer', monto: 700, fecha: '2026-10-08T08:00:00' },
    ]
    expect(gastosDeLaSemana(movs, ahora)).toBe(150)
  })
})
