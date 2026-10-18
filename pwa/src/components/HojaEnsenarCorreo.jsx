import { useEffect, useMemo, useState } from 'react'
import { Check, ChevronRight, Loader2 } from 'lucide-react'
import { api } from '../lib/api'
import { mensajeDeError } from '../lib/mensajes'
import Hoja from './Hoja'
import { montosDelTexto, nombreDelRango, palabrasDelTexto, textoRecuperados, textoSimilares, tocarPalabra } from '../lib/ensenarCorreo'

const LIMITE_TEXTO = 900

/**
 * «Enséñale a leer este correo»: muestra el texto del correo (solo a su dueño, no se guarda) y pide tres toques:
 * el monto, el nombre y si fue gasto o ingreso. Al guardar crea una regla PERSONAL; si hay correos parecidos
 * que se habían dejado de lado, pregunta antes de pasarlos a «Por revisar».
 *   correoId: id de un correo de «Por revisar»  ·  gmailMsgId: id del mensaje (viene de «Buscar un movimiento»)
 *   onListo({ correo, recuperados }): se guardó la regla (correo = lectura nueva si ya estaba en la lista)
 */
export default function HojaEnsenarCorreo({ correoId, gmailMsgId, onCerrar, onListo }) {
  const [vista, setVista] = useState(null)
  const [error, setError] = useState('')
  const [paso, setPaso] = useState('monto') // monto | nombre | tipo | similares | fin
  const [monto, setMonto] = useState('')
  const [rango, setRango] = useState(null)
  const [tipo, setTipo] = useState('expense')
  const [guardando, setGuardando] = useState(false)
  const [resultado, setResultado] = useState(null)
  const [mensajeFin, setMensajeFin] = useState('')

  useEffect(() => {
    let vivo = true
    api.vistaReglaCorreo(correoId ? { correo_id: correoId } : { gmail_msg_id: gmailMsgId })
      .then((v) => {
        if (!vivo) return
        setVista(v)
        setTipo(v.tipo_actual === 'income' ? 'income' : 'expense')
      })
      .catch((e) => vivo && setError(mensajeDeError(e)))
    return () => {
      vivo = false
    }
  }, [correoId, gmailMsgId])

  const texto = (vista?.texto || '').slice(0, LIMITE_TEXTO)
  const montos = useMemo(() => montosDelTexto(texto), [texto])
  const palabras = useMemo(() => palabrasDelTexto(texto), [texto])
  const nombre = nombreDelRango(palabras, rango)

  async function guardar() {
    if (guardando) return
    setGuardando(true)
    setError('')
    try {
      const r = await api.crearReglaCorreo({
        ...(correoId ? { correo_id: correoId } : { gmail_msg_id: gmailMsgId }),
        monto_texto: monto || null, comercio_texto: nombre || null, tipo,
      })
      setResultado(r)
      if (r.similares > 0) setPaso('similares')
      else {
        setMensajeFin('Listo. Cuando llegue un correo así, lo leo solo.')
        setPaso('fin')
        onListo?.({ correo: r.correo, recuperados: 0 })
      }
    } catch (e) {
      setError(mensajeDeError(e))
    } finally {
      setGuardando(false)
    }
  }

  async function pasarParecidos() {
    if (guardando) return
    setGuardando(true)
    setError('')
    try {
      const r = await api.aplicarReglaCorreoAnteriores(resultado.regla.id)
      setMensajeFin(`Listo. ${textoRecuperados(r.recuperados)} Los que lleguen después, los leo solo.`)
      setPaso('fin')
      onListo?.({ correo: resultado.correo, recuperados: r.recuperados })
    } catch (e) {
      setError(mensajeDeError(e))
    } finally {
      setGuardando(false)
    }
  }

  function sinPasar() {
    setMensajeFin('Listo. Cuando llegue un correo así, lo leo solo.')
    setPaso('fin')
    onListo?.({ correo: resultado?.correo, recuperados: 0 })
  }

  const puedeGuardar = Boolean(monto || nombre)
  const boton = 'w-full flex items-center justify-center gap-2 font-semibold rounded-xl min-h-[44px] text-sm disabled:opacity-50'

  return (
    <Hoja onCerrar={onCerrar} titulo="Enseñar a leer este correo" clasePanel="p-6 pb-8">
      {({ cerrar }) => (
        <div data-testid="ensenar-correo">
          <h2 className="text-lg font-bold">Enseñar a leer</h2>
          {!vista && !error && (
            <p className="mt-3 text-sm text-ink-soft flex items-center gap-2" role="status">
              <Loader2 size={16} className="animate-spin" aria-hidden="true" /> Abriendo el correo...
            </p>
          )}
          {error && <p className="mt-3 text-sm text-danger" role="alert">{error}</p>}

          {vista && paso === 'monto' && (
            <section aria-label="Paso 1 de 3: el monto">
              <p className="mt-1 text-xs text-ink-soft">Paso 1 de 3</p>
              <h3 className="mt-2 text-[15px] font-semibold">¿Cuál es el monto?</h3>
              <p className="text-xs text-ink-soft mt-0.5">Toca el número que es la plata de este movimiento.</p>
              <ul className="mt-3 flex flex-col gap-2">
                {montos.map((m) => (
                  <li key={m.texto}>
                    <button
                      type="button"
                      onClick={() => { setMonto(m.texto); setPaso('nombre') }}
                      aria-pressed={monto === m.texto}
                      className="w-full text-left rounded-xl bg-paper min-h-[44px] px-3 py-2 flex flex-col"
                    >
                      <span className="text-sm font-semibold">{m.texto}</span>
                      {m.contexto && <span className="text-xs text-ink-soft truncate">después de «{m.contexto}»</span>}
                    </button>
                  </li>
                ))}
              </ul>
              {!montos.length && <p className="mt-3 text-sm text-ink-soft">No veo ninguna cifra en este correo.</p>}
              <button type="button" onClick={() => { setMonto(''); setPaso('nombre') }} className={`${boton} mt-3 border border-line text-ink-soft`}>
                Saltar este paso
              </button>
            </section>
          )}

          {vista && paso === 'nombre' && (
            <section aria-label="Paso 2 de 3: el nombre">
              <p className="mt-1 text-xs text-ink-soft">Paso 2 de 3</p>
              <h3 className="mt-2 text-[15px] font-semibold">¿A quién o dónde fue?</h3>
              <p className="text-xs text-ink-soft mt-0.5">Toca la primera palabra del nombre y luego la última. Si es una sola, con un toque basta.</p>
              <p className="mt-3 rounded-xl bg-paper p-2 text-sm leading-relaxed" data-testid="texto-correo">
                {palabras.map((p, i) => {
                  const dentro = rango && i >= Math.min(rango.a, rango.b) && i <= Math.max(rango.a, rango.b)
                  return (
                    <button
                      key={`${i}-${p}`}
                      type="button"
                      onClick={() => setRango((r) => tocarPalabra(r, i))}
                      aria-pressed={Boolean(dentro)}
                      className={`inline-flex items-center min-h-[44px] px-1.5 rounded-lg ${dentro ? 'bg-accent text-paper-raised font-semibold' : ''}`}
                    >
                      {p}
                    </button>
                  )
                })}
              </p>
              {nombre && <p className="mt-2 text-sm">Nombre: <span className="font-semibold">{nombre}</span></p>}
              <div className="mt-3 flex gap-2">
                <button type="button" onClick={() => { setRango(null); setPaso('tipo') }} className={`${boton} border border-line text-ink-soft`}>
                  Saltar este paso
                </button>
                <button type="button" onClick={() => setPaso('tipo')} disabled={!nombre} className={`${boton} bg-accent text-paper-raised`}>
                  Seguir <ChevronRight size={16} aria-hidden="true" />
                </button>
              </div>
            </section>
          )}

          {vista && paso === 'tipo' && (
            <section aria-label="Paso 3 de 3: gasto o ingreso">
              <p className="mt-1 text-xs text-ink-soft">Paso 3 de 3</p>
              <h3 className="mt-2 text-[15px] font-semibold">¿Fue un gasto o un ingreso?</h3>
              <div className="mt-3 grid grid-cols-2 gap-2" role="group" aria-label="Tipo de movimiento">
                {[['expense', 'Gasto'], ['income', 'Ingreso']].map(([v, t]) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setTipo(v)}
                    aria-pressed={tipo === v}
                    className={`rounded-xl min-h-[44px] text-sm font-semibold ${tipo === v ? 'bg-accent text-paper-raised' : 'bg-paper'}`}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <ul className="mt-3 text-sm flex flex-col gap-0.5" aria-label="Lo que marcaste">
                <li>Monto: <span className="font-semibold">{monto || 'sin marcar'}</span></li>
                <li>Nombre: <span className="font-semibold">{nombre || 'sin marcar'}</span></li>
              </ul>
              <p className="mt-3 text-xs text-ink-soft">
                Guardo solo dónde está cada dato en este tipo de correo, no el correo. Es solo para ti.
              </p>
              <button type="button" onClick={guardar} disabled={!puedeGuardar || guardando} className={`${boton} mt-3 bg-accent text-paper-raised`}>
                {guardando ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <Check size={16} aria-hidden="true" />}
                Guardar
              </button>
            </section>
          )}

          {paso === 'similares' && resultado && (
            <section aria-label="Correos parecidos">
              <h3 className="mt-3 text-[15px] font-semibold">{textoSimilares(resultado.similares)}</h3>
              <p className="text-xs text-ink-soft mt-0.5">¿Los paso a «Por revisar» con lo que me enseñaste?</p>
              <button type="button" onClick={pasarParecidos} disabled={guardando} className={`${boton} mt-3 bg-accent text-paper-raised`}>
                {guardando ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : null}
                Pasar a Por revisar
              </button>
              <button type="button" onClick={sinPasar} disabled={guardando} className={`${boton} mt-2 border border-line text-ink-soft`}>
                Ahora no
              </button>
            </section>
          )}

          {paso === 'fin' && (
            <section aria-label="Listo">
              <p className="mt-3 text-sm" role="status" data-testid="ensenar-fin">{mensajeFin}</p>
              <button type="button" onClick={cerrar} className={`${boton} mt-3 bg-accent text-paper-raised`}>Cerrar</button>
            </section>
          )}
        </div>
      )}
    </Hoja>
  )
}
