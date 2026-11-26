import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { aISO, rangoPeriodo, rangoValido } from './informe'

// El periodo de Informes es UNO SOLO para todas las pestañas. Vive en la URL (?p=este_mes, o ?p=rango&desde=…&hasta=…):
// sobrevive a cambiar de pestaña, a recargar y a compartir el enlace. Las pantallas lo leen con usePeriodoInforme();
// fuera de Informes (pantallas sueltas, pruebas) usan useValorPeriodo(), que cae en un estado propio.
export const PERIODOS_INFORMES = [
  { id: 'este_mes', label: 'Este mes' },
  { id: 'mes_pasado', label: 'Mes pasado' },
  { id: '3_meses', label: '3 meses' },
  { id: '6_meses', label: '6 meses' },
  { id: 'anio', label: 'Este año' },
  { id: 'anio_pasado', label: 'Año pasado' },
  { id: 'rango', label: 'Personalizado' },
]
export const MAX_DIAS_PERSONALIZADO = 1830 // 5 años: el tope del servidor

const IDS = new Set(PERIODOS_INFORMES.map((p) => p.id))
// Los que el servidor entiende por su nombre (así la etiqueta y el «periodo anterior» salen de él); el resto va como rango.
const NATIVOS = new Set(['este_mes', 'mes_pasado', '3_meses', 'anio'])
const MES_RE = /^\d{4}-(0[1-9]|1[0-2])$/

/** Valor completo { periodo, desde, hasta } de un periodo con nombre. */
export const valorDe = (id, hoy = new Date()) => ({ periodo: id, ...rangoPeriodo(id, hoy) })

/** Un mes calendario concreto 'AAAA-MM' (el actual llega solo hasta hoy). Es un rango, así el servidor lo compara con el mes anterior. */
export function valorDeMes(clave, hoy = new Date()) {
  const [a, m] = clave.split('-').map(Number)
  if (a === hoy.getFullYear() && m === hoy.getMonth() + 1) return valorDe('este_mes', hoy)
  const ultimo = new Date(a, m, 0)
  const hasta = ultimo > hoy ? hoy : ultimo
  return { periodo: 'rango', desde: aISO(new Date(a, m - 1, 1)), hasta: aISO(hasta) }
}

/** Un año calendario completo (el actual llega hasta hoy). */
export function valorDeAnio(anio, hoy = new Date()) {
  if (anio === hoy.getFullYear()) return valorDe('anio', hoy)
  return { periodo: 'rango', desde: `${anio}-01-01`, hasta: `${anio}-12-31` }
}

/** Parámetros para la API de informes. */
export function paramsApi(valor) {
  if (NATIVOS.has(valor.periodo)) return { periodo: valor.periodo }
  // Un mes calendario completo se pide como «mes»: el servidor lo nombra («julio de 2026») y lo compara con el anterior.
  const mes = valor.desde.slice(0, 7)
  if (valor.periodo === 'rango' && valor.desde.endsWith('-01') && mes === valor.hasta.slice(0, 7)) {
    const [a, m] = mes.split('-').map(Number)
    if (valor.hasta === aISO(new Date(a, m, 0))) return { periodo: 'mes', mes }
  }
  return { periodo: 'rango', desde: valor.desde, hasta: valor.hasta }
}

/** Mes 'AAAA-MM' en el que termina el periodo. Con `terminado`, si ese mes aún no acaba se usa el anterior (un cierre se hace con el mes cerrado). */
export function mesDeValor(valor, { terminado = false, hoy = new Date() } = {}) {
  const mes = valor.hasta.slice(0, 7)
  if (!terminado) return mes
  const actual = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}`
  if (mes < actual) return mes
  const f = new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1)
  return `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, '0')}`
}

/** ¿El periodo es exactamente un mes calendario (o el mes en curso hasta hoy)? */
export function esUnMes(valor, hoy = new Date()) {
  if (!valor.desde.endsWith('-01') || valor.desde.slice(0, 7) !== valor.hasta.slice(0, 7)) return false
  const [a, m] = valor.hasta.split('-').map(Number)
  return valor.hasta === aISO(new Date(a, m, 0)) || valor.hasta === aISO(hoy)
}

/** Ventana de meses 'AAAA-MM' de las gráficas de historia: el periodo, ampliado a 6 meses si es más corto. */
export function ventanaHistorial(valor) {
  const hasta = valor.hasta.slice(0, 7)
  const [a, m] = hasta.split('-').map(Number)
  const f = new Date(a, m - 1 - 5, 1)
  const seis = `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, '0')}`
  const desde = valor.desde.slice(0, 7)
  return { desde: desde < seis ? desde : seis, hasta }
}

/** Lee el periodo de la URL; lo que no se entienda cae en «Este mes». Acepta el viejo ?mes=AAAA-MM. */
export function leerValor(params, hoy = new Date()) {
  const p = params.get('p')
  if (p === 'rango') {
    const desde = params.get('desde')
    const hasta = params.get('hasta')
    if (rangoValido(desde, hasta, MAX_DIAS_PERSONALIZADO)) return { periodo: 'rango', desde, hasta }
  } else if (IDS.has(p) && p !== 'rango') {
    return valorDe(p, hoy)
  }
  const mes = params.get('mes')
  if (!p && MES_RE.test(mes || '')) return valorDeMes(mes, hoy)
  return valorDe('este_mes', hoy)
}

const Contexto = createContext(null)

export function PeriodoInformeProvider({ children }) {
  const [params, setParams] = useSearchParams()
  const valor = useMemo(() => leerValor(params), [params])
  const setValor = useCallback(
    (v) =>
      setParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.delete('mes')
          n.set('p', v.periodo)
          if (v.periodo === 'rango') {
            n.set('desde', v.desde)
            n.set('hasta', v.hasta)
          } else {
            n.delete('desde')
            n.delete('hasta')
          }
          return n
        },
        { replace: true }
      ),
    [setParams]
  )
  const ctx = useMemo(() => ({ valor, setValor, global: true }), [valor, setValor])
  return <Contexto.Provider value={ctx}>{children}</Contexto.Provider>
}

/** El periodo global de Informes, o null si la pantalla no va dentro de Informes. */
export const usePeriodoInforme = () => useContext(Contexto)

/** El periodo global si existe; si no, un estado propio (la pantalla pinta entonces su propio selector). */
export function useValorPeriodo(inicial = 'este_mes') {
  const ctx = useContext(Contexto)
  const [local, setLocal] = useState(() => valorDe(inicial))
  return ctx ?? { valor: local, setValor: setLocal, global: false }
}
