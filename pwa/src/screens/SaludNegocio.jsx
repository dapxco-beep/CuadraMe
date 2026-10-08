import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, ArrowLeft, Lock, Users } from 'lucide-react'
import { EstadoVacio } from '../brand/Marca'
import { api } from '../lib/api'
import { useVolver } from '../lib/useVolver'
import BarraProgreso from '../components/BarraProgreso'
import Icono from '../components/Icono'
import Sparkline from '../components/Sparkline'
import { Tarjeta } from '../components/ui'

// «Salud del negocio»: solo para quien administra CuadraMe. El servidor decide (responde 404 a cualquier
// otra persona); esta pantalla solo muestra lo que llega. Los colores de las barras avisan en tres pasos:
// verde (holgado), dorado (desde 60 %: ya vale la pena planear) y rojo (desde 80 %: actúa).
const COLOR_NIVEL = {
  ok: 'var(--c-cuadra)',
  atencion: 'var(--c-gold)',
  alto: 'var(--c-danger)',
  critico: 'var(--c-danger)',
  sin_dato: 'var(--c-line)',
}
const TEXTO_NIVEL = { ok: 'Holgado', atencion: 'Planea', alto: 'Actúa pronto', critico: 'Urgente', sin_dato: 'Sin dato' }

const fmt = (n) => (n === null || n === undefined ? '—' : Number(n).toLocaleString('es-CO', { maximumFractionDigits: 1 }))

function Capacidad({ c }) {
  const pct = c.pct ?? 0
  const alerta = c.nivel === 'alto' || c.nivel === 'critico'
  return (
    <li className="py-3" data-testid={`cap-${c.id}`}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-semibold">{c.nombre}</p>
        <p className="text-xs text-ink-soft tabular-nums">
          {fmt(c.actual)} de {fmt(c.limite)} {c.unidad}
        </p>
      </div>
      <BarraProgreso
        pct={pct}
        color={COLOR_NIVEL[c.nivel]}
        label={`Uso de ${c.nombre}`}
        texto={c.pct === null ? 'Sin dato' : `${c.pct} %`}
        className="h-2.5 rounded-full bg-line overflow-hidden mt-2"
      />
      <p className={`text-xs mt-1.5 font-medium ${alerta ? 'text-danger' : 'text-ink-soft'}`}>
        {c.pct === null ? 'Sin dato' : `${c.pct} %`} · {TEXTO_NIVEL[c.nivel]}
      </p>
      {c.nivel !== 'ok' && c.nivel !== 'sin_dato' && (
        <p className="text-xs text-ink mt-1.5">
          <b>Qué hacer:</b> {c.accion}
        </p>
      )}
    </li>
  )
}

export default function SaludNegocio() {
  const volver = useVolver('/perfil')
  const [datos, setDatos] = useState(null)
  const [estado, setEstado] = useState('cargando') // cargando | ok | prohibido | error

  useEffect(() => {
    let vivo = true
    api
      .panelNegocio()
      .then((d) => {
        if (!vivo) return
        setDatos(d)
        setEstado('ok')
      })
      .catch((e) => {
        if (vivo) setEstado(e?.status === 404 ? 'prohibido' : 'error')
      })
    return () => {
      vivo = false
    }
  }, [])

  const encabezado = (
    <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
      <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
        <Icono icono={ArrowLeft} tam="md" />
      </button>
      <h1 className="text-xl font-bold">Salud del negocio</h1>
    </header>
  )

  if (estado === 'prohibido') {
    return (
      <div className="flex-1 overflow-y-auto pb-6 screen-enter">
        {encabezado}
        <EstadoVacio icono={Lock} titulo="Esta pantalla no está disponible" texto="Solo la ve quien administra CuadraMe." />
      </div>
    )
  }

  if (estado === 'error') {
    return (
      <div className="flex-1 overflow-y-auto pb-6 screen-enter">
        {encabezado}
        <EstadoVacio icono={AlertTriangle} titulo="No se pudo cargar" texto="Intenta de nuevo en un momento." />
      </div>
    )
  }

  if (estado === 'cargando' || !datos) {
    return (
      <div className="flex-1 overflow-y-auto pb-6 screen-enter">
        {encabezado}
        <p className="mx-6 mt-4 text-sm text-ink-soft" role="status">
          Cargando…
        </p>
      </div>
    )
  }

  const u = datos.usuarios
  const totales = (datos.tendencia || []).map((p) => p.total)
  const alertas = (datos.senales || []).filter((s) => s.alerta)

  return (
    <div className="flex-1 overflow-y-auto pb-6 screen-enter">
      {encabezado}

      <Tarjeta className="mx-5 mt-3 px-4 py-4">
        <div className="flex items-center gap-2 text-ink-soft t-kicker">
          <Icono icono={Users} tam="sm" /> Usuarios
        </div>
        <div className="grid grid-cols-3 gap-3 mt-2 text-center">
          <div>
            <p className="text-2xl font-bold tabular-nums" data-testid="usuarios-total">{fmt(u.usuarios_total)}</p>
            <p className="text-xs text-ink-soft">registrados</p>
          </div>
          <div>
            <p className="text-2xl font-bold tabular-nums">{fmt(u.activos_7d)}</p>
            <p className="text-xs text-ink-soft">activos 7 días</p>
          </div>
          <div>
            <p className="text-2xl font-bold tabular-nums">{fmt(u.activos_30d)}</p>
            <p className="text-xs text-ink-soft">activos 30 días</p>
          </div>
        </div>
        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="text-xs text-ink-soft">
            Nuevos: <b className="text-ink">{fmt(u.nuevos_7d)}</b> esta semana · <b className="text-ink">{fmt(u.nuevos_30d)}</b> en 30 días
          </p>
          <Sparkline valores={totales} resumen={`Usuarios acumulados en 30 días: de ${fmt(totales[0])} a ${fmt(totales[totales.length - 1])}`} className="text-accent" />
        </div>
      </Tarjeta>

      {alertas.length > 0 && (
        <Tarjeta className="mx-5 mt-3 px-4 py-3 bg-danger-soft" role="alert">
          {alertas.map((s) => (
            <p key={s.id} className="text-sm">
              <Icono icono={AlertTriangle} tam="sm" className="inline mr-1 text-danger" />
              <b>{s.nombre}:</b> {fmt(s.actual)}. {s.accion}
            </p>
          ))}
        </Tarjeta>
      )}

      <section className="mx-5 mt-4" aria-labelledby="cap-titulo">
        <h2 id="cap-titulo" className="t-kicker text-ink-soft flex items-center gap-1.5 mb-1">
          <Icono icono={Activity} tam="sm" /> Capacidad
        </h2>
        <Tarjeta variante="lista" className="px-4">
          <ul className="divide-y divide-line">
            {datos.capacidades.map((c) => (
              <Capacidad key={c.id} c={c} />
            ))}
          </ul>
        </Tarjeta>
      </section>

      <p className="mx-6 mt-4 text-xs text-ink-soft">
        Movimientos: {fmt(datos.volumen.movimientos)} · correos leídos: {fmt(datos.volumen.correos_procesados)} · extractos:{' '}
        {fmt(datos.volumen.extractos_procesados)} · preguntas a la IA este mes: {fmt(datos.volumen.ia_mes)}. Son aproximaciones:
        la cifra real de cada plan está en el panel de Supabase, Railway y Resend.
      </p>
    </div>
  )
}
