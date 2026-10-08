import { Fragment, useEffect, useId, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ChevronDown, LifeBuoy, Mail, Search } from 'lucide-react'
import { EstadoVacio } from '../brand/Marca'
import GuiaInstalar from '../components/GuiaInstalar'
import Icono from '../components/Icono'
import { Boton, CampoTexto } from '../components/ui'
import { agruparPorTema, buscarPreguntas, PREGUNTAS } from '../lib/ayuda'
import { useVolver } from '../lib/useVolver'

const SOPORTE = 'dapxco@gmail.com'

// «**negrita**» dentro de un párrafo
function Texto({ texto }) {
  return texto.split(/(\*\*[^*]+\*\*)/g).map((trozo, i) =>
    trozo.startsWith('**') ? <b key={i}>{trozo.slice(2, -2)}</b> : <Fragment key={i}>{trozo}</Fragment>
  )
}

// Párrafos y viñetas («- ») del archivo de datos
function Respuesta({ lineas }) {
  const bloques = []
  for (const l of lineas) {
    if (l.startsWith('- ')) {
      const ultimo = bloques[bloques.length - 1]
      if (ultimo?.lista) ultimo.items.push(l.slice(2))
      else bloques.push({ lista: true, items: [l.slice(2)] })
    } else {
      bloques.push({ texto: l })
    }
  }
  return (
    <div className="space-y-2 t-cuerpo">
      {bloques.map((b, i) =>
        b.lista ? (
          <ul key={i} className="list-disc pl-5 space-y-1">
            {b.items.map((it, j) => (
              <li key={j}>
                <Texto texto={it} />
              </li>
            ))}
          </ul>
        ) : (
          <p key={i}>
            <Texto texto={b.texto} />
          </p>
        )
      )}
    </div>
  )
}

function Pregunta({ p, abierta, onAlternar, onGuia }) {
  const uid = useId()
  return (
    <div id={`ayuda-${p.id}`} data-pregunta={p.id}>
      <h3 className="m-0">
        <button
          type="button"
          aria-expanded={abierta}
          aria-controls={`${uid}-r`}
          onClick={onAlternar}
          className="w-full min-h-14 px-4 py-3 flex items-center gap-3 text-left"
        >
          <span className="flex-1 t-cuerpo font-semibold">{p.pregunta}</span>
          <Icono icono={ChevronDown} tam="sm" className={`text-ink-soft transition-transform ${abierta ? 'rotate-180' : ''}`} />
        </button>
      </h3>
      {abierta && (
        <div id={`${uid}-r`} className="px-4 pb-4">
          <Respuesta lineas={p.respuesta} />
          {p.accion &&
            (p.accion.to ? (
              <Boton to={p.accion.to} tam="sm" variante="suave" className="mt-3">
                {p.accion.texto}
              </Boton>
            ) : (
              <Boton tam="sm" variante="suave" className="mt-3" onClick={() => onGuia(p.accion.guia)}>
                {p.accion.texto}
              </Boton>
            ))}
        </div>
      )}
    </div>
  )
}

export default function Ayuda() {
  const volver = useVolver('/perfil')
  const [params] = useSearchParams()
  const inicial = params.get('p')
  const [consulta, setConsulta] = useState('')
  const [abierta, setAbierta] = useState(PREGUNTAS.some((p) => p.id === inicial) ? inicial : null)
  const [guia, setGuia] = useState(null)

  // Un enlace directo (/ayuda?p=gmail-seguro) deja esa respuesta abierta y a la vista.
  useEffect(() => {
    if (!inicial) return
    document.getElementById(`ayuda-${inicial}`)?.scrollIntoView?.({ block: 'start' })
  }, [inicial])

  const resultados = useMemo(() => buscarPreguntas(consulta), [consulta])
  const grupos = useMemo(() => agruparPorTema(resultados), [resultados])
  const buscando = consulta.trim().length > 0

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      <header className="px-5 pantalla-top pb-2 flex items-center gap-3">
        <button
          onClick={volver}
          className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
          aria-label="Volver"
        >
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-semibold">Ayuda</h1>
      </header>

      <div className="mx-5 mt-3">
        <div className="relative">
          <CampoTexto
            etiqueta="¿Qué necesitas saber?"
            type="search"
            value={consulta}
            onChange={(e) => setConsulta(e.target.value)}
            placeholder="Busca: extracto, Gmail, clave…"
            autoComplete="off"
            enterKeyHint="search"
          />
        </div>
        <p className="sr-only" role="status" aria-live="polite">
          {buscando ? `${resultados.length} ${resultados.length === 1 ? 'respuesta' : 'respuestas'}` : ''}
        </p>
      </div>

      {resultados.length === 0 ? (
        <EstadoVacio
          icono={Search}
          titulo="No encontramos eso"
          texto="Prueba con otra palabra, por ejemplo «extracto», «Gmail» o «saldo». Si no aparece, escríbenos y te ayudamos."
          className="mx-5 mt-6"
        >
          <a
            href={`mailto:${SOPORTE}?subject=${encodeURIComponent('Necesito ayuda con CuadraMe')}`}
            className="btn btn-suave btn-sm mt-4 inline-flex"
          >
            <Icono icono={Mail} tam="sm" /> Escribirnos
          </a>
        </EstadoVacio>
      ) : (
        grupos.map((g) => (
          <section key={g.id} className="mx-5 mt-5" aria-labelledby={`tema-${g.id}`}>
            <h2 id={`tema-${g.id}`} className="t-kicker mb-2">
              {g.titulo}
            </h2>
            <div className="tarjeta-lista divide-y divide-line">
              {g.preguntas.map((p) => (
                <Pregunta
                  key={p.id}
                  p={p}
                  abierta={abierta === p.id || (buscando && resultados.length === 1)}
                  onAlternar={() => setAbierta(abierta === p.id ? null : p.id)}
                  onGuia={setGuia}
                />
              ))}
            </div>
          </section>
        ))
      )}

      <section className="mx-5 mt-6 tarjeta p-4 flex items-center gap-3">
        <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
          <Icono icono={LifeBuoy} tam="md" />
        </span>
        <div className="flex-1 min-w-0">
          <p className="t-cuerpo font-semibold">¿Sigues con dudas?</p>
          <p className="t-apoyo">Escríbenos y una persona te responde.</p>
        </div>
        <a href={`mailto:${SOPORTE}?subject=${encodeURIComponent('Necesito ayuda con CuadraMe')}`} className="btn btn-secundario btn-sm">
          Escribir
        </a>
      </section>
      <p className="mx-5 mt-4 t-apoyo text-center">
        <Link to="/legal/privacidad" className="underline">
          Política de privacidad
        </Link>
      </p>

      {guia === 'instalar' && <GuiaInstalar onCerrar={() => setGuia(null)} />}
    </div>
  )
}
