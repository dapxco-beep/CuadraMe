import { useCallback, useEffect, useRef, useState } from 'react'
import { TrendingUp } from 'lucide-react'
import Hoja from './Hoja'
import Icono from './Icono'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { useCuentas } from '../lib/CuentasContext'
import { formatCOP } from '../lib/format'
import { mensajeAmable } from '../lib/mensajes'
import {
  avisoExtracto, juntarResultados, lineaExtracto, lineaResultado, textoBoton, textoProgreso, textoTotal,
} from '../lib/registrarRendimientos'

/**
 * «Registrar los rendimientos de mis extractos (N)»: UN botón y una hoja. Los extractos de tu cuenta de ahorros suman
 * los rendimientos a tu saldo pero no los listan como movimientos, y por eso esos meses no cuadran al peso. La hoja
 * muestra la vista previa (qué extractos, de cuánto y el total) y un solo «Sí, registrar». Se registra de a uno
 * («Registrando 3 de 6…»); un extracto que no se puede leer se salta y se dice por qué. Se oculta solo cuando no hay nada.
 */
export default function RegistrarRendimientos({ className = '', onListo }) {
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
      .then(() => api.previaRendimientos?.())
      .then((p) => { if (montado.current) setPrevia(p || null) })
      .catch(() => { if (montado.current) setPrevia(null) }) // es un extra: si falla no se muestra nada
  }, [])

  useEffect(() => {
    montado.current = true
    cargar()
    return () => { montado.current = false }
  }, [cargar])

  async function registrarTodo() {
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
        const r = await api.registrarRendimientos({ maximo: 1, excluir: [...intentados], continuar: i > 0 })
        if (!r?.resultados?.length) break
        pasos.push(r)
        intentados.push(...r.resultados.map((x) => x.historial_id))
        restantes = r.restantes || 0
      }
    } catch (err) {
      if (montado.current) setError(mensajeAmable(err?.message, { porDefecto: 'No pudimos seguir ahora. Lo hecho hasta aquí quedó guardado; intenta de nuevo en un rato.' }))
    }
    if (!montado.current) return
    setFinal(juntarResultados(pasos, restantes, fmt))
    setTrabajando(false)
    await recargarCuentas?.()
    await cargar()
    onListo?.()
  }

  const n = previa?.total || 0
  if (!n && !abierta && !final) return null

  return (
    <>
      {n > 0 && (
        <button
          type="button"
          data-testid="registrar-rendimientos"
          onClick={() => { setFinal(null); setError(''); setAbierta(true) }}
          className={`w-full min-h-11 flex items-center justify-center gap-2 rounded-2xl bg-accent text-paper-raised text-sm font-semibold px-4 py-2.5 ${className}`}
        >
          <Icono icono={TrendingUp} tam="md" />
          <span>{textoBoton(n)}</span>
        </button>
      )}

      {abierta && (
        <Hoja onCerrar={() => { if (!trabajando) setAbierta(false) }} titulo="Registrar los rendimientos de mis extractos">
          {({ cerrar }) => (
            <div data-testid="hoja-registrar-rendimientos">
              <h2 className="text-lg font-bold">Registrar los rendimientos de mis extractos</h2>

              {!final && (
                <>
                  <p className="text-sm text-ink-soft mt-1">
                    Tu banco le suma rendimientos a tu cuenta, pero el extracto no los lista como movimientos. Por eso esos meses no cuadran al peso.
                    Los leo de cada extracto y los registro como ingreso en «Rendimientos». No toco lo que ya tienes.
                  </p>
                  <ul className="mt-3 flex flex-col gap-2" data-testid="lista-rendimientos">
                    {(previa?.extractos || []).map((e) => (
                      <li key={e.historial_id} className="rounded-2xl ring-1 ring-line/60 p-3 text-sm">
                        <p className="font-semibold leading-snug">{lineaExtracto(e, fmt)}</p>
                        {avisoExtracto(e) && <p className="text-xs text-ink-soft mt-1">{avisoExtracto(e)}</p>}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-3 rounded-2xl bg-paper p-3 text-sm font-semibold" data-testid="total-rendimientos">{textoTotal(previa, fmt)}</p>
                  {trabajando && <p className="text-sm font-semibold mt-3" role="status" data-testid="progreso-rendimientos">{textoProgreso(progreso, total)}</p>}
                  {error && <p className="text-sm text-danger mt-3" role="alert">{error}</p>}
                  <button
                    type="button"
                    disabled={trabajando}
                    onClick={registrarTodo}
                    className="mt-4 w-full min-h-11 rounded-xl bg-accent text-paper-raised text-sm font-semibold disabled:opacity-60"
                  >
                    {trabajando ? 'Un momento...' : 'Sí, registrar'}
                  </button>
                  <button type="button" disabled={trabajando} onClick={cerrar} className="mt-1 w-full min-h-11 text-sm font-semibold text-ink-soft disabled:opacity-50">Dejarlo así</button>
                </>
              )}

              {final && (
                <>
                  <p className="text-sm font-semibold mt-2 leading-snug" role="status" data-testid="resumen-rendimientos">{final.resumen}</p>
                  {error && <p className="text-sm text-danger mt-2" role="alert">{error}</p>}
                  <ul className="mt-3 flex flex-col gap-1.5 text-sm text-ink-soft">
                    {final.resultados.map((r) => <li key={r.historial_id}>{lineaResultado(r, fmt)}</li>)}
                  </ul>
                  <button type="button" onClick={cerrar} className="mt-4 w-full min-h-11 text-sm font-semibold text-ink-soft">Cerrar</button>
                </>
              )}
            </div>
          )}
        </Hoja>
      )}
    </>
  )
}
