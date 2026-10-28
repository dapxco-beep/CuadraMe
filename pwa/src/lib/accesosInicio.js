import { useCallback, useEffect, useState } from 'react'
import { ArrowDownLeft, ArrowLeftRight, ArrowUpRight, Bot, CreditCard, Download, Landmark, Mail, PieChart, PiggyBank, Repeat, Users, Wallet } from 'lucide-react'
import { useAuth } from './AuthContext'

// Accesos del Inicio que la persona elige («Personalizar»).
//
// Dónde se guarda: igual que modoSimple.js, en este dispositivo y separado por usuario (no hay tabla de
// ajustes en el backend; crearla sería una migración). Se guarda la lista de ids, no las rutas, para que
// un cambio de ruta no deje accesos rotos guardados.

export const CATALOGO_ACCESOS = [
  { id: 'gasto', texto: 'Gasto', icono: ArrowUpRight, ruta: '/agregar?foco=monto' },
  { id: 'ingreso', texto: 'Ingreso', icono: ArrowDownLeft, ruta: '/agregar?tipo=income&foco=monto' },
  { id: 'pasar', texto: 'Pasar plata', icono: ArrowLeftRight, ruta: '/agregar?tipo=transfer' },
  { id: 'traer', texto: 'Traer extractos', icono: Download, ruta: '/sincronizacion' },
  { id: 'correo', texto: 'Movimientos del correo', icono: Mail, ruta: '/movimientos-correo' },
  { id: 'dividir', texto: 'Dividir cuenta', icono: Users, ruta: '/amigos' },
  { id: 'metas', texto: 'Metas', icono: PiggyBank, ruta: '/metas' },
  { id: 'deudas', texto: 'Deudas', icono: CreditCard, ruta: '/deudas' },
  { id: 'fijos', texto: 'Pagos fijos', icono: Repeat, ruta: '/recurrentes' },
  { id: 'presupuesto', texto: 'Presupuesto', icono: PieChart, ruta: '/presupuesto' },
  { id: 'cuentas', texto: 'Cuentas', icono: Wallet, ruta: '/cuentas' },
  { id: 'patrimonio', texto: 'Patrimonio', icono: Landmark, ruta: '/patrimonio' },
  { id: 'asistente', texto: 'Pregúntale a la IA', icono: Bot, ruta: '/asistente' },
]

// Una fila de cuatro: lo de todos los días. «Personalizar» deja sumar hasta MAX_ACCESOS; quien ya eligió los suyos los conserva.
export const ACCESOS_POR_DEFECTO = ['gasto', 'ingreso', 'pasar', 'traer']
export const MAX_ACCESOS = 12

const CLAVE = 'cuadrame:accesos-inicio'
const EVENTO = 'cuadrame:accesos-inicio'
const IDS = new Set(CATALOGO_ACCESOS.map((a) => a.id))

export function leerAccesos(uid = 'anon') {
  try {
    const crudo = localStorage.getItem(`${CLAVE}:${uid}`)
    if (!crudo) return ACCESOS_POR_DEFECTO
    const v = JSON.parse(crudo)
    const ids = Array.isArray(v) ? v.filter((id) => IDS.has(id)) : []
    return ids.length ? ids : ACCESOS_POR_DEFECTO
  } catch {
    return ACCESOS_POR_DEFECTO
  }
}

export function guardarAccesos(uid = 'anon', ids) {
  try {
    localStorage.setItem(`${CLAVE}:${uid}`, JSON.stringify(ids))
  } catch {
    /* sin almacenamiento: vale solo para esta sesión */
  }
  window.dispatchEvent(new Event(EVENTO))
}

export function restablecerAccesos(uid = 'anon') {
  try {
    localStorage.removeItem(`${CLAVE}:${uid}`)
  } catch {
    /* ignorar */
  }
  window.dispatchEvent(new Event(EVENTO))
}

/** { accesos (objetos del catálogo, en el orden elegido), ids, guardar(ids), restablecer() } */
export function useAccesosInicio() {
  const { usuario } = useAuth() || {}
  const uid = usuario?.id || 'anon'
  const [, repintar] = useState(0)

  useEffect(() => {
    const alCambiar = () => repintar((n) => n + 1)
    window.addEventListener(EVENTO, alCambiar)
    window.addEventListener('storage', alCambiar)
    return () => {
      window.removeEventListener(EVENTO, alCambiar)
      window.removeEventListener('storage', alCambiar)
    }
  }, [])

  const ids = leerAccesos(uid)
  const porId = Object.fromEntries(CATALOGO_ACCESOS.map((a) => [a.id, a]))
  const guardar = useCallback((nuevos) => guardarAccesos(uid, nuevos), [uid])
  const restablecer = useCallback(() => restablecerAccesos(uid), [uid])
  return { ids, accesos: ids.map((id) => porId[id]), guardar, restablecer }
}
