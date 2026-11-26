import { useEffect, useMemo, useState } from 'react'
import { BarChart3 } from 'lucide-react'
import { api } from '../lib/api'
import { textoError } from '../lib/textoError'
import { useBloqueo } from '../lib/BloqueoContext'
import { paramsApi, useValorPeriodo, valorDe, valorDeMes } from '../lib/periodoInforme'
import { PANELES_RESUMEN, usePanelesInforme } from '../lib/panelesInforme'
import { EstadoVacio } from '../brand/Marca'
import { EsqueletoGrafica, EsqueletoLista } from '../components/Esqueletos'
import AvisoSinTasa from '../components/AvisoSinTasa'
import { enPeriodo } from '../components/informe/comun'
import ResumenCifras from '../components/informe/ResumenCifras'
import Hallazgos from '../components/informe/Hallazgos'
import FlujoNeto from '../components/informe/FlujoNeto'
import TasaAhorro from '../components/informe/TasaAhorro'
import IngresosFuente from '../components/informe/IngresosFuente'
import PresupuestoReal from '../components/informe/PresupuestoReal'
import PersonalizarPaneles from '../components/informe/PersonalizarPaneles'

// Informes > Resumen. Una sola lectura (GET /informes/resumen) alimenta todos los paneles, así que todo cuenta con
// la misma regla y el mismo periodo. Los cálculos viven en el servidor (informe_resumen.py); aquí solo se pinta.
export default function Panorama() {
  const { valor, setValor } = useValorPeriodo()
  const { fmt } = useBloqueo()
  const paneles = usePanelesInforme(PANELES_RESUMEN)
  const params = useMemo(() => paramsApi(valor), [valor])
  const clave = JSON.stringify(params)
  // La agrupación (día/semana/mes) se elige por periodo: al cambiar de periodo vuelve a «automática».
  const [elegida, setElegida] = useState({ clave: null, id: null })
  const agrupar = elegida.clave === clave ? elegida.id : null
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(true)
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    let activo = true
    setCargando(true)
    setError('')
    api.informeResumen({ ...params, ...(agrupar ? { agrupar } : {}) })
      .then((r) => activo && setD(r))
      .catch((e) => activo && setError(textoError(e, 'cargar el resumen')))
      .finally(() => activo && setCargando(false))
    return () => {
      activo = false
    }
  }, [clave, agrupar, recarga]) // eslint-disable-line react-hooks/exhaustive-deps

  const anchos = new Set(PANELES_RESUMEN.filter((p) => p.ancho).map((p) => p.id))
  const hoy = new Date()
  const mesPasado = `${hoy.getMonth() === 0 ? hoy.getFullYear() - 1 : hoy.getFullYear()}-${String(hoy.getMonth() === 0 ? 12 : hoy.getMonth()).padStart(2, '0')}`
  const periodoDelDato = d && d.desde === valor.desde ? d : null // no pintar cifras de otro periodo bajo el rótulo nuevo
  const listo = !!periodoDelDato

  const panel = d && {
    cifras: <ResumenCifras d={d} fmt={fmt} parametrosMov={`desde=${d.desde}&hasta=${d.hasta}`} />,
    hallazgos: <Hallazgos hallazgos={d.hallazgos} etiqueta={d.etiqueta} />,
    flujo: <FlujoNeto flujo={d.flujo} fmt={fmt} agrupar={d.flujo.agrupar} onAgrupar={(id) => setElegida({ clave, id })} />,
    tasa: <TasaAhorro meses={d.meses} resumen={d.tasa_serie} fmt={fmt} onVerMes={(m) => setValor(valorDeMes(m))} />,
    fuentes: <IngresosFuente datos={d.fuentes} fmt={fmt} paramsPeriodo={params} />,
    presupuesto: <PresupuestoReal datos={d.presupuesto} fmt={fmt} parametrosMov={`desde=${d.desde}&hasta=${d.hasta}`} />,
  }

  return (
    <div className="pb-8" aria-busy={cargando}>
      {error && (
        <div role="alert" className="mx-5 mt-6 card-marca bg-danger-soft p-4 text-center">
          <p className="text-sm text-danger">{error}</p>
          <button type="button" onClick={() => setRecarga((n) => n + 1)} className="mt-2 min-h-11 px-3 text-sm font-semibold text-danger underline">
            Reintentar
          </button>
        </div>
      )}
      {!d && cargando && (
        <div className="mx-5 mt-4 space-y-4">
          <EsqueletoGrafica alto={180} etiqueta="Cargando el resumen" />
          <EsqueletoLista filas={3} />
        </div>
      )}
      {d && (
        <AvisoSinTasa monedas={d.monedas_sin_tasa} base={d.moneda_base} onResuelto={() => setRecarga((n) => n + 1)} className="mx-5 mt-4" />
      )}
      {d && !d.hay_datos && (
        <EstadoVacio
          icono={BarChart3}
          titulo={`Aún no hay movimientos ${enPeriodo(d.etiqueta)}`}
          texto="Prueba con otro periodo, o registra un ingreso o un gasto para empezar a ver tu resumen."
          className="mx-5 mt-4"
        >
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            <button type="button" onClick={() => setValor(valorDe('3_meses'))} className="min-h-11 px-4 rounded-full border border-line bg-paper text-sm font-semibold text-accent">Ver 3 meses</button>
            <button type="button" onClick={() => setValor(valorDeMes(mesPasado))} className="min-h-11 px-4 rounded-full border border-line bg-paper text-sm font-semibold text-accent">Ver el mes pasado</button>
          </div>
        </EstadoVacio>
      )}
      {d && d.hay_datos && (
        <div className={`px-5 mt-4 grid gap-4 lg:grid-cols-2 transition-opacity ${cargando && !listo ? 'opacity-60' : ''}`}>
          {paneles.orden.filter((id) => paneles.visible(id) && panel[id]).map((id) => (
            <div key={id} className={`min-w-0 ${anchos.has(id) ? 'lg:col-span-2' : ''}`}>{panel[id]}</div>
          ))}
        </div>
      )}
      <PersonalizarPaneles paneles={paneles} lista={PANELES_RESUMEN} className="px-5 mt-4" />
    </div>
  )
}
