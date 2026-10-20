import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, ShieldCheck } from 'lucide-react'
import Hoja from './Hoja'
import Icono from './Icono'
import CambiarCuentaExtracto from './CambiarCuentaExtracto'
import ArreglarTarjetas from './ArreglarTarjetas'
import { api } from '../lib/api'
import { useCuentas } from '../lib/CuentasContext'
import { useDialogos } from '../lib/DialogosContext'
import { mensajeAmable } from '../lib/mensajes'

// «Revisé tu cuenta y encontré N cosas»: UN banner discreto (Inicio y Traer movimientos). Se oculta solo
// cuando no hay nada. Cada hallazgo trae su acción de un toque; lo que toca movimientos ya importados
// siempre pasa por una vista previa (CambiarCuentaExtracto) y nunca se mueve en silencio.
// Los hallazgos vienen de GET /salud (sin montos ni descripciones).

export const textoBanner = (n) => `Revisé tu cuenta y encontré ${n === 1 ? 'una cosa' : `${n} cosas`}`

// Acciones que solo llevan a la pantalla donde se resuelven.
const RUTA_DE_ACCION = {
  reintentar_errores: null, // se resuelve aquí mismo
  ver_descartados: '/correos',
  revisar_conexion: '/conexiones',
  sincronizar: '/sincronizacion',
  ver_extractos: '/sincronizacion',
  guardar_clave: '/conexiones',
}

export default function AvisoSalud({ className = '' }) {
  const navigate = useNavigate()
  const { cuentas, recargar: recargarCuentas } = useCuentas() || { cuentas: [] }
  const { avisar } = useDialogos() || {}
  const [hallazgos, setHallazgos] = useState([])
  const [abierto, setAbierto] = useState(false)
  const [ocupado, setOcupado] = useState('')
  const [cambiando, setCambiando] = useState(null)

  const cargar = useCallback(() => {
    return Promise.resolve()
      .then(() => api.salud?.())
      .then((r) => setHallazgos(Array.isArray(r?.hallazgos) ? r.hallazgos : []))
      .catch(() => {}) // es un extra: si falla no se muestra nada ni se molesta
  }, [])

  useEffect(() => { cargar() }, [cargar])

  if (!hallazgos.length && !abierto) return null

  async function actuar(h) {
    const a = h.accion || {}
    setOcupado(h.codigo + (a.banco || ''))
    try {
      if (a.tipo === 'crear_cuenta_tarjeta') {
        const r = await api.saludCrearTarjeta(a.banco)
        avisar?.(`Listo: creamos «${r.nombre}».`, 'ok')
        await recargarCuentas?.()
        await cargar()
      } else if (a.tipo === 'reintentar_errores') {
        await api.reintentarErroresExtractos()
        avisar?.('Lo volvimos a intentar.', 'ok')
        await cargar()
      } else if (a.tipo === 'cambiar_cuenta_extracto') {
        if (a.historial_id) setCambiando({ historialId: a.historial_id, cuentaId: a.cuenta_id })
        else { setAbierto(false); navigate('/sincronizacion') }
      } else if (RUTA_DE_ACCION[a.tipo]) {
        setAbierto(false)
        navigate(RUTA_DE_ACCION[a.tipo])
      }
    } catch (err) {
      avisar?.(mensajeAmable(err?.message, { porDefecto: 'No pudimos hacerlo ahora. Intenta de nuevo en un rato.' }))
    } finally {
      setOcupado('')
    }
  }

  const n = hallazgos.length
  return (
    <>
      {n > 0 && (
        <div className={className}>
          <button
            type="button"
            onClick={() => setAbierto(true)}
            data-testid="aviso-salud"
            className="w-full min-h-11 flex items-center gap-2.5 rounded-2xl bg-paper-raised ring-1 ring-line/60 px-4 py-3 text-left"
          >
            <Icono icono={ShieldCheck} tam="md" className="text-accent" />
            <span className="flex-1 text-sm font-semibold">{textoBanner(n)}</span>
            <Icono icono={ChevronRight} tam="sm" className="text-ink-soft" />
          </button>
        </div>
      )}

      {abierto && (
        <Hoja onCerrar={() => setAbierto(false)} titulo="Lo que encontré">
          {() => (
            <div data-testid="lista-salud">
              <h2 className="text-lg font-bold">{n > 0 ? textoBanner(n) : 'Todo en orden'}</h2>
              {n === 0 && <p className="text-sm text-ink-soft mt-2">No hay nada pendiente por revisar.</p>}
              <ul className="mt-3 flex flex-col gap-3">
                {hallazgos.map((h) => (
                  <li key={h.codigo + (h.accion?.banco || '')} className="rounded-2xl ring-1 ring-line/60 p-4">
                    <p className="text-sm font-semibold">{h.titulo}</p>
                    <p className="text-sm text-ink-soft mt-1">{h.texto}</p>
                    <button
                      type="button"
                      onClick={() => actuar(h)}
                      disabled={ocupado === h.codigo + (h.accion?.banco || '')}
                      className="mt-3 w-full min-h-11 rounded-2xl bg-accent text-paper-raised text-sm font-semibold disabled:opacity-60"
                    >
                      {h.accion?.etiqueta || 'Revisar'}
                    </button>
                    {/* «Extracto de tarjeta en cuenta de ahorros»: un solo paso para arreglarlos todos (se oculta si no hay nada). */}
                    {h.codigo === 'extracto_producto_distinto' && <ArreglarTarjetas className="mt-2" onListo={cargar} />}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Hoja>
      )}

      {cambiando && (
        <CambiarCuentaExtracto
          historialId={cambiando.historialId}
          titulo="Extracto"
          cuentaActualId={cambiando.cuentaId}
          cuentas={cuentas}
          onCerrar={() => setCambiando(null)}
          onListo={() => { setCambiando(null); recargarCuentas?.(); cargar() }}
        />
      )}
    </>
  )
}
