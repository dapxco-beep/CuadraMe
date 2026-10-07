// Un usuario recién registrado no tiene datos: ninguna pantalla debe romperse
// con listas vacías ni con respuestas sin campos. Esto es lo primero que verá
// cada cliente nuevo.
import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const CUENTAS = [{ id: 'c1', nombre: 'Efectivo', saldo: 0, moneda: 'COP', tipo: 'efectivo', icono: '💵' }]

// Cualquier método de api responde con una lista vacía, salvo los que devuelven objetos.
const api = vi.hoisted(() => ({}))
vi.mock('../lib/api', () => ({
  api: new Proxy(api, {
    get: (_t, nombre) => (...args) => {
      const especiales = {
        reporteMensual: { salud: { score: 0, tips: [] }, top_categorias: [], ingresos: 0, gastos: 0 },
        disponibleHoy: { categorias: [] },
        enMiBolsillo: { saldo_total: 0, recurrentes_pendientes_mes: 0, aportes_comprometidos_mes: 0, disponible_real: 0, disponible_real_por_dia: 0 },
        gmailEstado: { conectado: false },
        vidasAhorcado: { vidas_disponibles: 0, racha_actual: 0, mejor_racha: 0 },
        apiKey: { api_key: 'k' },
        confianzaAutoimport: { confianza_autoimport: 0.75 },
        plan: { plan: 'free' },
        tendencias: { meses: [] },
        alertasProactivas: { comisiones: [], cobros_duplicados: [] },
        resumenSemanal: { ingresos: 0, gastos: 0, ahorro: 0, top_categorias: [], anomalias: [], texto: '' },
        edadDelDinero: { dias: null },
        flujoCajaFuturo: { meses: [] },
      }
      return Promise.resolve(especiales[nombre] ?? [])
    },
  }),
}))
vi.mock('../lib/AuthContext', () => ({
  useAuth: () => ({ usuario: { id: 'u', email: 'a@b.co', nombre: 'Nueva Persona' }, logout: vi.fn() }),
}))
vi.mock('../lib/CuentasContext', () => ({
  useCuentas: () => ({ cuentas: CUENTAS, cargando: false, error: '', recargar: vi.fn().mockResolvedValue() }),
}))
vi.mock('../lib/CategoriasContext', () => ({
  useCategorias: () => ({ categorias: [], nombres: [], iconoDe: () => '💳', cargando: false, recargar: vi.fn() }),
}))

import { DialogosProvider } from '../lib/DialogosContext'
import { ThemeProvider } from '../lib/ThemeContext'
import Presupuesto from '../screens/Presupuesto'
import Metas from '../screens/Metas'
import Recurrentes from '../screens/Recurrentes'
import Deudas from '../screens/Deudas'
import Insights from '../screens/Insights'
import Sincronizacion from '../screens/Sincronizacion'
import ImportarArchivo from '../screens/ImportarArchivo'
import Ahorcado from '../screens/Ahorcado'
import ConectarDispositivo from '../screens/ConectarDispositivo'
import Categorias from '../screens/Categorias'
import ReglasCategoria from '../screens/ReglasCategoria'
import Compartir from '../screens/Compartir'
import Cuentas from '../screens/Cuentas'
import Inicio from '../screens/Inicio'
import Movimientos from '../screens/Movimientos'
import Perfil from '../screens/Perfil'
import Agregar from '../screens/Agregar'

const PANTALLAS = {
  Presupuesto, Metas, Recurrentes, Deudas, Insights, Sincronizacion, ImportarArchivo, Ahorcado,
  ConectarDispositivo, Categorias, ReglasCategoria, Compartir, Cuentas, Inicio, Movimientos, Perfil, Agregar,
}

describe('pantallas sin datos', () => {
  for (const [nombre, Pantalla] of Object.entries(PANTALLAS)) {
    it(`${nombre} se muestra sin romperse`, async () => {
      const errores = vi.spyOn(console, 'error').mockImplementation(() => {})
      const { container } = render(
        <ThemeProvider>
          <DialogosProvider>
            <MemoryRouter>
              <Pantalla />
            </MemoryRouter>
          </DialogosProvider>
        </ThemeProvider>
      )
      // dejar que terminen las cargas asíncronas
      await waitFor(() => expect(container.textContent.length).toBeGreaterThan(0))
      await new Promise((r) => setTimeout(r, 50))
      expect(container.textContent).not.toMatch(/Algo salió mal/)
      const graves = errores.mock.calls.filter((c) => /Error|Uncaught|TypeError|not defined/.test(String(c[0])))
      expect(graves, graves.map((c) => String(c[0]).slice(0, 200)).join('\n')).toHaveLength(0)
      errores.mockRestore()
    })
  }
})
