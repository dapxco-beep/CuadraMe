import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CreditCard, Pencil } from 'lucide-react'
import Hoja from './Hoja'
import Icono from './Icono'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { useCuentas } from '../lib/CuentasContext'
import { formatCOP } from '../lib/format'
import { mensajeAmable } from '../lib/mensajes'
import {
  avisoExtracto, juntarResultados, lineaExtracto, lineaResultado, textoBoton, textoCorreccionesTarjeta, textoProgreso, textoSaldo,
} from '../lib/arreglarTarjetas'

/**
 * «Arreglar mis extractos de la tarjeta (N)»: UN botón y una hoja. La hoja muestra la vista previa (qué extracto pasa
 * a qué cuenta, cuántos movimientos y cómo quedan los saldos) y un solo «Sí, arreglar todo». Se arregla de a uno
 * («Arreglando 3 de 6…»); un extracto que no se puede leer se salta y se dice por qué. Nada se importa solo: si
 * quedaron compras por importar, «Revisar e importar» lleva a revisarlas. Se oculta solo cuando no hay nada que arreglar.
 */
export default function ArreglarTarjetas({ className = '', onListo, onRevisar }) {
  const navigate = useNavigate()
  const bloqueo = useBloqueo() || {}
  const fmt = bloqueo.fmt || formatCOP
  const { recargar: recargarCuentas } = useCuentas() || {}
  const [previa, setPrevia] = useState(null)
  const [abierta, setAbierta] = useState(false)
  const [progreso, setProgreso] = useState(0)
  const [total, setTotal] = useState(0)
  const [trabajando, setTrabajando] = useState(false)
  const [final, setFinal] = useState(null)
  const [error, setError] = useState('')
  const montado = useRef(true)

  const cargar = useCallback(() => {
    return Promise.resolve()
      .then(() => api.previaArreglarTarjetas?.())
      .then((p) => { if (montado.current) setPrevia(p || null) })
      .catch(() => { if (montado.current) setPrevia(null) }) // es un extra: si falla no se muestra nada
  }, [])

  useEffect(() => {
    montado.current = true
    cargar()
    return () => { montado.current = false }
  }, [cargar])

  async function arreglarTodo() {
    const cuantos = previa?.total || 0
    setTotal(cuantos)
    setTrabajando(true)
    setError('')
    const pasos = []
    const intentados = []
    let restantes = 0
    try {
      for (let i = 0; i < cuantos; i += 1) {
        if (montado.current) setProgreso(i + 1)
        const r = await api.arreglarTarjetas({ maximo: 1, excluir: [...intentados], continuar: i > 0 })
        if (!r?.resultados?.length) break
        pasos.push(r)
        intentados.push(...r.resultados.map((x) => x.historial_id))
        restantes = r.restantes || 0
      }
    } catch (err) {
      if (montado.current) setError(mensajeAmable(err?.message, { porDefecto: 'No pudimos seguir ahora. Lo hecho hasta aquí quedó guardado; intenta de nuevo en un rato.' }))
    }
    if (!montado.current) return
    setFinal(juntarResultados(pasos, restantes))
    setTrabajando(false)
    await recargarCuentas?.()
    await cargar()
    onListo?.()
  }

  function revisar(cerrar) {
    cerrar()
    if (onRevisar) onRevisar()
    else navigate('/sincronizacion')
  }

  const n = previa?.total || 0
  if (!n && !abierta && !final) return null

  return (
    <>
      {n > 0 && (
        <button
          type="button"
          data-testid="arreglar-tarjetas"
          onClick={() => { setFinal(null); setError(''); setAbierta(true) }}
          className={`w-full min-h-11 flex items-center justify-center gap-2 rounded-2xl bg-accent text-paper-raised text-sm font-semibold px-4 py-2.5 ${className}`}
        >
          <Icono icono={CreditCard} tam="md" />
          <span>{textoBoton(n)}</span>
        </button>
      )}

      {abierta && (
        <Hoja onCerrar={() => { if (!trabajando) setAbierta(false) }} titulo="Arreglar mis extractos de la tarjeta">
          {({ cerrar }) => (
            <div data-testid="hoja-arreglar-tarjetas">
              <h2 className="text-lg font-bold">Arreglar mis extractos de la tarjeta</h2>

              {!final && (
                <>
                  <p className="text-sm text-ink-soft mt-1">
                    Paso cada extracto a su tarjeta (si estaba en otra cuenta), lo leo otra vez con el lector de hoy y dejo como compras las que se guardaron como ingresos. No importo compras nuevas solo.
                  </p>
                  <ul className="mt-3 flex flex-col gap-2" data-testid="lista-arreglar">
                    {(previa?.extractos || []).map((e) => (
                      <li key={e.historial_id} className="rounded-2xl ring-1 ring-line/60 p-3 text-sm">
                        <p className="font-semibold leading-snug">{lineaExtracto(e)}</p>
                        {avisoExtracto(e) && <p className="text-xs text-ink-soft mt-1">{avisoExtracto(e)}</p>}
                      </li>
                    ))}
                  </ul>
                  {textoCorreccionesTarjeta(previa, fmt) && (
                    <p className="mt-3 flex items-start gap-2 rounded-2xl bg-accent-soft p-3 text-sm font-semibold text-accent" data-testid="correcciones-arreglar">
                      <Icono icono={Pencil} tam="sm" className="mt-0.5" />
                      <span>{textoCorreccionesTarjeta(previa, fmt)}</span>
                    </p>
                  )}
                  {(previa?.saldos?.por_cuenta || []).length > 0 && (
                    <div className="mt-3 rounded-2xl bg-paper p-3 text-sm" data-testid="saldos-arreglar">
                      <p className="font-semibold">Así quedan tus saldos</p>
                      <ul className="mt-1 flex flex-col gap-0.5 text-ink-soft">
                        {previa.saldos.por_cuenta.map((c) => <li key={c.id}>{textoSaldo(c, fmt)}</li>)}
                      </ul>
                      <p className="text-xs text-ink-soft mt-1">En total tienes lo mismo: solo se pasan movimientos entre tus cuentas.</p>
                    </div>
                  )}
                  {trabajando && <p className="text-sm font-semibold mt-3" role="status" data-testid="progreso-arreglar">{textoProgreso(progreso, total)}</p>}
                  {error && <p className="text-sm text-danger mt-3" role="alert">{error}</p>}
                  <button
                    type="button"
                    disabled={trabajando}
                    onClick={arreglarTodo}
                    className="mt-4 w-full min-h-11 rounded-xl bg-accent text-paper-raised text-sm font-semibold disabled:opacity-60"
                  >
                    {trabajando ? 'Un momento...' : 'Sí, arreglar todo'}
                  </button>
                  <button type="button" disabled={trabajando} onClick={cerrar} className="mt-1 w-full min-h-11 text-sm font-semibold text-ink-soft disabled:opacity-50">Dejarlo así</button>
                </>
              )}

              {final && (
                <>
                  <p className="text-sm font-semibold mt-2 leading-snug" role="status" data-testid="resumen-arreglar">{final.resumen}</p>
                  {error && <p className="text-sm text-danger mt-2" role="alert">{error}</p>}
                  <ul className="mt-3 flex flex-col gap-1.5 text-sm text-ink-soft">
                    {final.resultados.map((r) => <li key={r.historial_id}>{lineaResultado(r)}</li>)}
                  </ul>
                  {final.por_importar > 0 && (
                    <button
                      type="button"
                      onClick={() => revisar(cerrar)}
                      data-testid="revisar-importar"
                      className="mt-4 w-full min-h-11 rounded-xl bg-accent text-paper-raised text-sm font-semibold"
                    >
                      Revisar e importar
                    </button>
                  )}
                  <button type="button" onClick={cerrar} className="mt-1 w-full min-h-11 text-sm font-semibold text-ink-soft">Cerrar</button>
                </>
              )}
            </div>
          )}
        </Hoja>
      )}
    </>
  )
}
