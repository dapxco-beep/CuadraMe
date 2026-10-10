import { useLayoutEffect, useRef } from 'react'
import {
  canonicoDesdeEscrito,
  canonicoDesdePegado,
  mostrarMonto,
  posicionTrasSignificativos,
  significativosAntes,
} from '../lib/monto'

// Campo de monto con miles en vivo (1250000 -> 1.250.000), teclado numérico en el celular y coma decimal.
//  - `value` y `onValor` usan el valor CANÓNICO ("1250000" o "1250000.5"): se envía tal cual con Number().
//  - Se conserva el cursor: se cuenta cuántos dígitos había antes de él y se repone tras dar formato.
//  - `entero`: sin decimales (pesos, objetivos de meta). `negativo`: acepta signo menos.
export default function InputMonto({ value, onValor, entero = false, negativo = false, onPaste, onKeyDown, ...resto }) {
  const ref = useRef(null)
  const pendiente = useRef(null) // dígitos que debe haber antes del cursor tras el próximo render
  const mostrado = mostrarMonto(value)

  useLayoutEffect(() => {
    const el = ref.current
    if (pendiente.current === null || !el || document.activeElement !== el) {
      pendiente.current = null
      return
    }
    const pos = posicionTrasSignificativos(el.value, pendiente.current)
    pendiente.current = null
    try {
      el.setSelectionRange(pos, pos)
    } catch {
      // algunos teclados no permiten fijar la selección; no es grave
    }
  })

  const opciones = { decimales: !entero, negativo }

  const alCambiar = (e) => {
    const el = e.target
    const texto = el.value
    const cursor = el.selectionStart ?? texto.length
    let sig = significativosAntes(texto, cursor)
    let canonico = canonicoDesdeEscrito(texto, opciones)
    // Borrar justo un punto de miles no cambia el valor: en ese caso se borra el dígito vecino.
    const tipo = e.nativeEvent?.inputType || ''
    if (tipo.startsWith('delete') && mostrarMonto(canonico) === mostrado && texto !== mostrado) {
      const digitos = canonicoDesdeEscrito(mostrado, opciones).length
      const quitar = tipo === 'deleteContentForward' ? sig : sig - 1
      const base = canonicoDesdeEscrito(mostrado, opciones)
      if (quitar >= 0 && quitar < digitos) {
        canonico = base.slice(0, quitar) + base.slice(quitar + 1)
        sig = Math.max(0, quitar)
      }
    }
    pendiente.current = sig
    onValor?.(canonico)
  }

  const alPegar = (e) => {
    onPaste?.(e)
    if (e.defaultPrevented) return
    const pegado = e.clipboardData?.getData('text')
    if (pegado === undefined || pegado === null) return
    const canonico = canonicoDesdePegado(pegado)
    if (!canonico && /\S/.test(pegado)) return // no es un número: se deja que el navegador lo filtre
    e.preventDefault()
    pendiente.current = mostrarMonto(canonico).length
    onValor?.(entero ? canonico.split('.')[0] : canonico)
  }

  return (
    <input
      type="text"
      inputMode={entero ? 'numeric' : 'decimal'}
      autoComplete="off"
      enterKeyHint="done"
      {...resto}
      ref={ref}
      value={mostrado}
      onChange={alCambiar}
      onPaste={alPegar}
      onKeyDown={onKeyDown}
    />
  )
}
