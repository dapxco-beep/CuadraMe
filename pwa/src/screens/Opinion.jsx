import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import Cuadri from '../brand/Cuadri'
import Icono from '../components/Icono'
import { Boton, Campo, Chip, Tarjeta } from '../components/ui'
import { useDialogos } from '../lib/DialogosContext'
import { api } from '../lib/api'
import {
  MAX_MENSAJE, TIPOS, VERSION_APP, fechaCorta, limpiarDesde, resumenDispositivo, tipoInicial, tipoPorId,
} from '../lib/opinion'
import { useVolver } from '../lib/useVolver'

// «Tu opinión cuenta»: un buzón simple. Se elige qué tipo de comentario es, se escribe y se envía.
// La pantalla de origen (?desde=) y el dispositivo viajan solos; nunca datos financieros.
export default function Opinion() {
  const volver = useVolver('/ayuda')
  const { avisar } = useDialogos()
  const [params] = useSearchParams()
  const desde = limpiarDesde(params.get('desde'))
  const [tipo, setTipo] = useState(() => tipoInicial(params.get('tipo')))
  const [mensaje, setMensaje] = useState('')
  const [puedeContactar, setPuedeContactar] = useState(true)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [enviado, setEnviado] = useState(false)
  const [mios, setMios] = useState(null) // null = cargando, [] = ninguno
  const [errorMios, setErrorMios] = useState(false)

  const cargarMios = useCallback(() => {
    return api
      .misComentarios()
      .then((l) => {
        setMios(Array.isArray(l) ? l : [])
        setErrorMios(false)
      })
      .catch(() => {
        setMios([])
        setErrorMios(true)
      })
  }, [])
  useEffect(() => {
    cargarMios()
  }, [cargarMios])

  const actual = tipoPorId(tipo)
  const restante = MAX_MENSAJE - mensaje.length
  const vacio = mensaje.trim().length === 0

  const enviar = async (e) => {
    e.preventDefault()
    if (vacio || enviando) return
    setEnviando(true)
    setError('')
    try {
      await api.enviarComentario({
        tipo,
        mensaje: mensaje.trim(),
        pantalla: desde || null,
        version_app: VERSION_APP || null,
        dispositivo: resumenDispositivo() || null,
        puede_contactar: puedeContactar,
      })
      setEnviado(true)
      setMensaje('')
      avisar('¡Gracias! Leemos todo lo que nos cuentas.', 'info')
      cargarMios()
    } catch (err) {
      // El texto se conserva: no se pierde lo escrito si falla.
      setError(err?.message || 'No pudimos enviar tu comentario. Intenta de nuevo en un momento.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3 lg:max-w-2xl lg:mx-auto">
        <button
          type="button"
          onClick={volver}
          className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Volver"
        >
          <Icono icono={ArrowLeft} tam="md" />
        </button>
        <h1 className="text-xl font-semibold flex-1">Tu opinión cuenta</h1>
      </header>

      <div className="lg:max-w-2xl lg:mx-auto">
        {enviado ? (
          <Tarjeta className="mx-5 mt-3 px-5 py-6 text-center" role="status" data-testid="opinion-gracias">
            <Cuadri pose="celebrando" size={96} className="mx-auto" />
            <p className="text-base font-semibold mt-2">¡Gracias por contarnos!</p>
            <p className="t-apoyo mt-1">Lo leemos con cariño. Abajo puedes ver cómo va.</p>
            <Boton variante="suave" tam="sm" className="mt-4" onClick={() => setEnviado(false)}>
              Enviar otro comentario
            </Boton>
          </Tarjeta>
        ) : (
          <form onSubmit={enviar} className="mx-5 mt-3 space-y-4" noValidate>
            <p className="t-cuerpo text-ink-soft">Una idea, una duda o algo que no funcionó: cuéntanos y lo miramos.</p>

            <div>
              <p id="tipo-op" className="campo-etiqueta">
                ¿Qué quieres contarnos?
              </p>
              <div role="radiogroup" aria-labelledby="tipo-op" className="grid grid-cols-2 gap-2">
                {TIPOS.map((t) => (
                  <Chip key={t.id} rol="radio" activo={tipo === t.id} onClick={() => setTipo(t.id)} className="justify-start">
                    <span aria-hidden="true">{t.emoji}</span> {t.etiqueta}
                  </Chip>
                ))}
              </div>
            </div>

            <Campo
              etiqueta="Tu mensaje"
              ayuda={
                <span className="flex justify-between gap-3">
                  <span>{actual.pista}</span>
                  <span className={`tabular-nums ${restante < 100 ? 'text-danger' : ''}`} aria-live="polite">
                    {mensaje.length}/{MAX_MENSAJE}
                  </span>
                </span>
              }
              error={error}
            >
              {(props) => (
                <textarea
                  {...props}
                  rows={6}
                  maxLength={MAX_MENSAJE}
                  value={mensaje}
                  onChange={(e) => setMensaje(e.target.value)}
                  placeholder="Escribe aquí con confianza"
                />
              )}
            </Campo>

            <label className="flex items-start gap-3 t-cuerpo cursor-pointer">
              <input
                type="checkbox"
                checked={puedeContactar}
                onChange={(e) => setPuedeContactar(e.target.checked)}
                className="mt-1 w-5 h-5 accent-[var(--c-accent)] shrink-0"
              />
              <span>Puedes escribirme a mi correo si necesitas aclarar.</span>
            </label>

            <Boton type="submit" bloque cargando={enviando} disabled={vacio}>
              Enviar
            </Boton>
            <p className="t-apoyo">
              No enviamos tus saldos ni tus movimientos. Solo tu mensaje, la pantalla donde estabas y el tipo de dispositivo.
            </p>
          </form>
        )}

        <section className="mx-5 mt-8" aria-labelledby="mios-titulo">
          <h2 id="mios-titulo" className="t-kicker mb-2">
            Tus comentarios
          </h2>
          {mios === null ? (
            <p className="t-apoyo" role="status">
              Cargando…
            </p>
          ) : errorMios ? (
            <p className="t-apoyo">No pudimos cargar tus comentarios ahora.</p>
          ) : mios.length === 0 ? (
            <p className="t-apoyo">Aún no nos has escrito. Cuando lo hagas, aquí verás cómo va.</p>
          ) : (
            <ul className="tarjeta-lista divide-y divide-line" data-testid="mis-comentarios">
              {mios.map((c) => (
                <li key={c.id} className="px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="t-apoyo">
                      <span aria-hidden="true">{tipoPorId(c.tipo).emoji}</span> {tipoPorId(c.tipo).etiqueta} · {fechaCorta(c.creado_en)}
                    </span>
                    <span className="text-xs font-semibold rounded-full bg-accent-soft text-accent px-2.5 py-1 whitespace-nowrap">
                      {c.estado}
                    </span>
                  </div>
                  <p className="t-cuerpo mt-1.5 whitespace-pre-line break-words">{c.mensaje}</p>
                  {c.respuesta && (
                    <p className="t-cuerpo mt-2 rounded-xl bg-paper border border-line px-3 py-2 whitespace-pre-line break-words">
                      <b>Respuesta:</b> {c.respuesta}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}
