import { textoError } from '../lib/textoError'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, ChevronRight, Receipt, Repeat, X } from 'lucide-react'
import { EstadoVacio } from '../brand/Marca'
import { api } from '../lib/api'
import { useBloqueo } from '../lib/BloqueoContext'
import { useVolver } from '../lib/useVolver'
import { AVISO_EDUCATIVO } from '../lib/avisoEducativo'
import { barrasPorTipo, hayCostos, mesCorto, nombreMes, textoVariacion } from '../lib/costos'
import { leerDescartados, guardarDescartados } from '../components/ConsejoParaTi'
import { EsqueletoGrafica, EsqueletoLista } from '../components/Esqueletos'
import Ayudita from '../components/Ayudita'
import BarraProgreso from '../components/BarraProgreso'
import Icono from '../components/Icono'
import { Boton, Chip } from '../components/ui'

// «Lo que te cuesta tu plata»: lo que pagas (sin notarlo) por tener tu plata en bancos y tarjetas, y lo que
// ella te rinde. Es información para entender tus extractos, no asesoría financiera.

function Alerta({ a, onDescartar }) {
  const urgente = a.prioridad === 1
  return (
    <li
      className={`rounded-2xl border p-4 ${urgente ? 'border-danger bg-paper-raised' : 'border-line bg-paper-raised'}`}
      data-testid="alerta-costos"
    >
      <div className="flex items-start gap-2">
        <Icono icono={AlertTriangle} tam="md" className={urgente ? 'text-danger mt-0.5' : 'text-accent mt-0.5'} />
        <h3 className="flex-1 t-cuerpo font-semibold">{a.titulo}</h3>
        {a.cifra && <span className="shrink-0 rounded-full bg-accent-soft text-accent px-2.5 py-0.5 text-xs font-semibold">{a.cifra}</span>}
        <button
          type="button"
          onClick={() => onDescartar(a.id)}
          aria-label={`Descartar alerta: ${a.titulo}`}
          className="shrink-0 w-11 h-11 -mt-2 -mr-2 flex items-center justify-center text-ink-soft"
        >
          <Icono icono={X} tam="sm" />
        </button>
      </div>
      <p className="t-cuerpo text-ink-soft mt-1">{a.texto}</p>
      {a.accion?.ruta && (
        <Link to={a.accion.ruta} className="inline-flex items-center min-h-[44px] text-sm font-semibold text-accent">
          {a.accion.texto}
        </Link>
      )}
    </li>
  )
}

function Tendencia({ meses, fmt }) {
  const ultimos = (meses || []).slice(-6)
  const max = Math.max(1, ...ultimos.map((m) => m.total))
  return (
    <div data-testid="tendencia-costos">
      <div className="flex items-end gap-2 h-[96px]">
        {ultimos.map((m) => (
          <div key={m.mes} className="flex-1 flex flex-col justify-end h-full min-w-0" role="img"
            aria-label={`${nombreMes(m.mes)}: ${fmt(m.total)}`}>
            <div className="rounded-t-md" style={{ height: `${Math.max(m.total ? 4 : 0, (m.total / max) * 100)}%`, background: 'var(--c-serie-1)' }} />
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-1.5">
        {ultimos.map((m) => (
          <p key={m.mes} className="flex-1 text-center text-[11px] text-ink-soft capitalize">{mesCorto(m.mes)}</p>
        ))}
      </div>
    </div>
  )
}

export default function Costos() {
  const volver = useVolver('/')
  const { fmt } = useBloqueo()
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(true)
  const [vista, setVista] = useState('anio') // 'mes' | 'anio'
  const [descartados, setDescartados] = useState(leerDescartados)

  useEffect(() => {
    let activo = true
    setCargando(true)
    setError('')
    Promise.resolve()
      .then(() => api.costosBancarios())
      .then((d) => activo && setDatos(d))
      .catch((e) => activo && setError(textoError(e, 'cargar')))
      .finally(() => activo && setCargando(false))
    return () => {
      activo = false
    }
  }, [])

  function descartar(id) {
    const nuevos = [...descartados, id]
    setDescartados(nuevos)
    guardarDescartados(nuevos)
  }

  const conDatos = hayCostos(datos)
  const alertas = (datos?.alertas || []).filter((a) => !descartados.includes(a.id))
  const bloque = vista === 'mes' ? datos?.mes : datos?.anio
  const barras = conDatos ? barrasPorTipo(bloque) : []
  const subs = datos?.suscripciones

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter pantalla-ancha">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <Icono icono={ArrowLeft} tam="md" />
        </button>
        <h1 className="text-xl font-bold">Lo que te cuesta tu plata</h1>
      </header>

      {cargando && (
        <div className="mx-6 mt-6 space-y-4">
          <EsqueletoGrafica alto={140} etiqueta="Cargando lo que te cuesta tu plata" />
          <EsqueletoLista filas={3} />
        </div>
      )}
      {error && <p role="alert" className="mx-6 mt-6 text-sm text-danger text-center">{error}</p>}

      {!cargando && !error && !conDatos && (
        <EstadoVacio
          icono={Receipt}
          pose="feliz"
          titulo="Todavía no veo cobros del banco"
          texto="Cuando traigas un extracto con intereses o comisiones, te lo muestro aquí."
          className="mx-6 mt-6"
        >
          <Boton to="/sincronizacion" variante="suave" className="mt-4">Traer un extracto</Boton>
        </EstadoVacio>
      )}

      {!cargando && conDatos && (
        <div className="lg:grid lg:grid-cols-2 lg:gap-x-5 lg:items-start">
          <div>
          <section className="mx-6 mt-4 hero-marca card-marca p-4" aria-label="Resumen del año y del mes">
            <p className="t-kicker">Este año has pagado</p>
            <p className="text-[32px] t-display mt-1" data-testid="costo-anio">{fmt(datos.anio.total)}</p>
            <p className="t-apoyo">en intereses, cuotas, comisiones y 4x1000 durante {datos.anio.anio}.</p>
            <div className="mt-3 pt-3 border-t border-line">
              <p className="t-kicker capitalize">{nombreMes(datos.mes.mes)}</p>
              <p className="text-2xl t-display mt-0.5" data-testid="costo-mes">{fmt(datos.mes.total)}</p>
              <p className="t-apoyo">{textoVariacion(datos.mes)}</p>
              {datos.promedio_mensual > 0 && (
                <p className="t-apoyo">Tu promedio mensual antes de este mes: {fmt(datos.promedio_mensual)}.</p>
              )}
            </div>
            {datos.anio.rendimientos > 0 && (
              <p className="text-sm mt-3" data-testid="costo-neto">
                Tu plata te rindió {fmt(datos.anio.rendimientos)} este año. <strong>Costo neto: {fmt(datos.anio.costo_neto)}</strong>{' '}
                <Ayudita termino="costo-neto" />
              </p>
            )}
          </section>

          <section className="mx-6 mt-4 card-marca bg-paper-raised border border-line p-4" aria-label="Por tipo de cobro">
            <div className="flex items-center gap-2 mb-3">
              <h2 className="flex-1 t-kicker">En qué se va</h2>
              <Chip activo={vista === 'mes'} onClick={() => setVista('mes')}>Este mes</Chip>
              <Chip activo={vista === 'anio'} onClick={() => setVista('anio')}>Este año</Chip>
            </div>
            <ul className="space-y-3">
              {barras.map((b) => (
                <li key={b.clave}>
                  <div className="flex items-center gap-1 text-sm">
                    <span className="flex-1 min-w-0 truncate">{b.nombre}</span>
                    <Ayudita termino={b.ayuda} />
                    <span className="font-semibold tabular-nums">{fmt(b.monto)}</span>
                  </div>
                  <BarraProgreso pct={b.pct} color={b.color} label={b.nombre} texto={fmt(b.monto)} className="h-2 rounded-full bg-line overflow-hidden mt-1" />
                </li>
              ))}
            </ul>
          </section>

          <section className="mx-6 mt-4 card-marca bg-paper-raised border border-line p-4" aria-label="Mes a mes">
            <h2 className="t-kicker mb-3">Mes a mes</h2>
            <Tendencia meses={datos.meses} fmt={fmt} />
          </section>

          {datos.por_cuenta?.length > 0 && (
            <section className="mx-6 mt-4 card-marca bg-paper-raised border border-line p-4" aria-label="Por cuenta o tarjeta">
              <h2 className="t-kicker mb-2">Por cuenta o tarjeta</h2>
              <ul className="divide-y divide-line">
                {datos.por_cuenta.map((c) => (
                  <li key={c.cuenta_id} className="flex items-center gap-2 py-2.5 text-sm">
                    <span className="flex-1 min-w-0 truncate">{c.nombre}</span>
                    <span className="font-semibold tabular-nums">{fmt(c.total)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          </div>

          <div>
            {alertas.length > 0 && (
              <section className="mx-6 mt-4" aria-label="Alertas">
                <h2 className="t-kicker mb-2">Para revisar</h2>
                <ul className="space-y-3">
                  {alertas.map((a) => <Alerta key={a.id} a={a} onDescartar={descartar} />)}
                </ul>
              </section>
            )}

            {subs?.lista?.length > 0 && (
              <section className="mx-6 mt-4 card-marca bg-paper-raised border border-line p-4" aria-label="Tus suscripciones" data-testid="suscripciones">
                <div className="flex items-center gap-2">
                  <Icono icono={Repeat} tam="md" className="text-accent" />
                  <h2 className="flex-1 t-cuerpo font-semibold">Tus suscripciones: {fmt(subs.total_mensual)} al mes</h2>
                </div>
                <ul className="divide-y divide-line mt-2">
                  {subs.lista.map((s) => (
                    <li key={s.huella} className="flex items-center gap-2 py-2.5 text-sm">
                      <span className="flex-1 min-w-0 truncate">{s.nombre}</span>
                      {s.subio && <span className="text-[11px] font-semibold text-danger">subió</span>}
                      <span className="font-semibold tabular-nums">{fmt(s.monto)}</span>
                    </li>
                  ))}
                </ul>
                <Link to="/recurrentes" className="inline-flex items-center gap-1 min-h-[44px] text-sm font-semibold text-accent">
                  Registrar mis recurrentes <Icono icono={ChevronRight} tam="sm" />
                </Link>
              </section>
            )}
          </div>

          <p className="mx-6 mt-4 t-apoyo">{datos.aviso || AVISO_EDUCATIVO}</p>
        </div>
      )}
    </div>
  )
}
