import { Fragment, useEffect, useId, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ArrowLeft, BookOpen, Calculator, ChevronDown, CreditCard, GraduationCap, Landmark, PiggyBank, Repeat, Search,
  ShieldAlert, Receipt, Scale, Snowflake, Coffee, TrendingUp, Wallet,
} from 'lucide-react'
import { EstadoVacio } from '../brand/Marca'
import Cuadri from '../brand/Cuadri'
import Icono from '../components/Icono'
import { Boton, CampoTexto } from '../components/ui'
import { AVISO_EDUCATIVO, buscarGlosario, buscarLecciones, GLOSARIO, LECCIONES } from '../lib/aprende'
import { useVolver } from '../lib/useVolver'

// Un ícono por lección (familia lucide, 20 px). Si falta alguna, cae en el libro.
const ICONOS = {
  'presupuesto-50-30-20': Calculator,
  'fondo-de-emergencia': PiggyBank,
  'tarjeta-de-credito': CreditCard,
  'debito-vs-credito': Scale,
  'interes-ea-vs-nominal': TrendingUp,
  traslado: Repeat,
  'deudas-avalancha-bola-de-nieve': Snowflake,
  'gastos-hormiga': Coffee,
  'inflacion-y-ahorro': Landmark,
  'seguridad-fraudes': ShieldAlert,
  'revisar-extractos': Receipt,
}

// «**negrita**» dentro de un párrafo
function Texto({ texto }) {
  return texto.split(/(\*\*[^*]+\*\*)/g).map((trozo, i) =>
    trozo.startsWith('**') ? <b key={i}>{trozo.slice(2, -2)}</b> : <Fragment key={i}>{trozo}</Fragment>
  )
}

// Párrafos y viñetas («- ») del archivo de datos
function Cuerpo({ lineas }) {
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

function Leccion({ l, abierta, onAlternar }) {
  const uid = useId()
  return (
    <div id={`leccion-${l.id}`} data-leccion={l.id}>
      <h3 className="m-0">
        <button
          type="button"
          aria-expanded={abierta}
          aria-controls={`${uid}-c`}
          onClick={onAlternar}
          className="w-full min-h-16 px-4 py-3 flex items-center gap-3 text-left"
        >
          <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
            <Icono icono={ICONOS[l.id] || BookOpen} tam="md" />
          </span>
          <span className="flex-1 min-w-0">
            <span className="block t-cuerpo font-semibold">{l.titulo}</span>
            <span className="block t-apoyo">{l.resumen}</span>
          </span>
          <span className="t-apoyo shrink-0">1 min</span>
          <Icono icono={ChevronDown} tam="sm" className={`text-ink-soft transition-transform ${abierta ? 'rotate-180' : ''}`} />
        </button>
      </h3>
      {abierta && (
        <div id={`${uid}-c`} className="px-4 pb-4">
          <Cuerpo lineas={l.cuerpo} />
          <div className="mt-3 rounded-xl bg-paper p-3">
            <p className="t-kicker text-ink-soft">Ejemplo en pesos</p>
            <p className="t-cuerpo mt-1">{l.ejemplo}</p>
          </div>
          {l.accion && (
            <Boton to={l.accion.to} tam="sm" variante="suave" className="mt-3">
              {l.accion.texto}
            </Boton>
          )}
          <p className="t-apoyo mt-3">{AVISO_EDUCATIVO}</p>
        </div>
      )}
    </div>
  )
}

export default function Aprende() {
  const volver = useVolver('/')
  const [params] = useSearchParams()
  const inicial = params.get('l')
  const [consulta, setConsulta] = useState('')
  const [abierta, setAbierta] = useState(LECCIONES.some((l) => l.id === inicial) ? inicial : null)

  // Un enlace directo (/aprende?l=tarjeta-de-credito) deja esa lección abierta y a la vista.
  useEffect(() => {
    if (!inicial) return
    document.getElementById(`leccion-${inicial}`)?.scrollIntoView?.({ block: 'start' })
  }, [inicial])

  const lecciones = useMemo(() => buscarLecciones(consulta), [consulta])
  const terminos = useMemo(() => buscarGlosario(consulta), [consulta])
  const buscando = consulta.trim().length > 0
  const total = lecciones.length + terminos.length

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
        <h1 className="text-xl font-semibold flex-1">Aprende</h1>
        <Cuadri pose="senalando" size={56} />
      </header>

      <p className="mx-5 mt-1 t-cuerpo text-ink-soft">
        Lecciones de un minuto y un glosario para entender tu plata, con ejemplos en pesos colombianos.
      </p>

      <div className="mx-5 mt-3">
        <CampoTexto
          etiqueta="Buscar una lección o un término"
          type="search"
          value={consulta}
          onChange={(e) => setConsulta(e.target.value)}
          placeholder="Busca: cupo, interés, fraude…"
          autoComplete="off"
          enterKeyHint="search"
        />
        <p className="sr-only" role="status" aria-live="polite">
          {buscando ? `${total} ${total === 1 ? 'resultado' : 'resultados'}` : ''}
        </p>
      </div>

      {total === 0 && (
        <EstadoVacio
          icono={Search}
          titulo="No encontramos eso"
          texto="Prueba con otra palabra, por ejemplo «tarjeta», «ahorro» o «deuda»."
          className="mx-5 mt-6"
        />
      )}

      {lecciones.length > 0 && (
        <section className="mx-5 mt-5" aria-labelledby="aprende-lecciones">
          <h2 id="aprende-lecciones" className="t-kicker mb-2 flex items-center gap-2">
            <Icono icono={GraduationCap} tam="sm" /> Microlecciones
          </h2>
          <div className="tarjeta-lista divide-y divide-line">
            {lecciones.map((l) => (
              <Leccion
                key={l.id}
                l={l}
                abierta={abierta === l.id || (buscando && lecciones.length === 1 && terminos.length === 0)}
                onAlternar={() => setAbierta(abierta === l.id ? null : l.id)}
              />
            ))}
          </div>
        </section>
      )}

      {terminos.length > 0 && (
        <section className="mx-5 mt-6" aria-labelledby="aprende-glosario">
          <h2 id="aprende-glosario" className="t-kicker mb-2 flex items-center gap-2">
            <Icono icono={Wallet} tam="sm" /> Glosario
          </h2>
          <dl className="tarjeta-lista divide-y divide-line" data-testid="glosario">
            {terminos.map((t) => (
              <div key={t.id} id={`termino-${t.id}`} className="px-4 py-3">
                <dt className="t-cuerpo font-semibold">{t.termino}</dt>
                <dd className="t-cuerpo mt-0.5 m-0">{t.definicion}</dd>
              </div>
            ))}
          </dl>
          {!buscando && GLOSARIO.length > 0 && (
            <p className="t-apoyo mt-2">{GLOSARIO.length} términos.</p>
          )}
        </section>
      )}

      <p className="mx-5 mt-6 t-apoyo text-center">{AVISO_EDUCATIVO}</p>
    </div>
  )
}
