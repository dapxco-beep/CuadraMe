import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle,
  Bell,
  BellOff,
  ChevronDown,
  Gauge,
  Mail,
  MessageCircle,
  Rocket,
  ServerCrash,
  TrendingUp,
  UserMinus,
  UserPlus,
  Wallet,
  Zap,
} from 'lucide-react'
import { api } from '../lib/api'
import { fechaCorta } from '../lib/opinion'
import { activarPush, pushSoportado } from '../lib/push'
import Icono from './Icono'
import { Boton, Chip, Tarjeta } from './ui'

// «Actividad reciente»: lo que pasa en CuadraMe (registros, primeras cuentas, problemas...) para quien
// administra. Funciona aunque no llegue ni push ni correo: la lista sale de la base. El correo completo
// solo se ve aquí; los avisos al celular y al correo van con el correo enmascarado (d***@gmail.com).
// Solo el administrador la ve (el servidor responde 404 a cualquier otra persona).

const ICONO_TIPO = {
  nuevo_registro: UserPlus,
  primera_cuenta: Wallet,
  primer_movimiento: Rocket,
  gmail_conectado: Mail,
  atajo_activado: Zap,
  cuenta_eliminada: UserMinus,
  comentario_problema: AlertTriangle,
  comentarios_pendientes: MessageCircle,
  limite_alcanzado: Gauge,
  umbral_capacidad: TrendingUp,
  errores_5xx_picos: ServerCrash,
}

const AVISO_TEXTO = {
  silenciado: 'No se avisó (silencio)',
  resumen: 'En el resumen del día',
  agrupado: 'Agrupado por exceso de avisos',
}

function dia(iso) {
  const [, m, d] = String(iso).split('-')
  return `${Number(d)}/${Number(m)}`
}

// 30 barras: registros por día. El resumen en texto va aparte para quien no ve la gráfica.
function BarrasRegistros({ serie }) {
  const max = Math.max(1, ...serie.map((p) => p.registros))
  const total = serie.reduce((a, p) => a + p.registros, 0)
  return (
    <div data-testid="registros-por-dia">
      <p className="text-xs text-ink-soft">
        Registros por día (30 días): <b className="text-ink">{total}</b> en total
      </p>
      <div
        className="flex items-end gap-px h-12 mt-1.5"
        role="img"
        aria-label={`Registros por día en los últimos 30 días: ${total} en total, máximo ${max} en un día`}
      >
        {serie.map((p) => (
          <span
            key={p.dia}
            title={`${dia(p.dia)}: ${p.registros}`}
            className={`flex-1 rounded-t-sm ${p.registros ? 'bg-accent' : 'bg-line'}`}
            style={{ height: `${p.registros ? Math.max(12, (p.registros / max) * 100) : 6}%` }}
          />
        ))}
      </div>
      <div className="flex justify-between text-[11px] text-ink-soft mt-0.5">
        <span>{dia(serie[0]?.dia)}</span>
        <span>{dia(serie[serie.length - 1]?.dia)}</span>
      </div>
    </div>
  )
}

function Interruptor({ activo, onChange, etiqueta, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={activo}
      aria-label={etiqueta}
      disabled={disabled}
      onClick={() => onChange(!activo)}
      className={`shrink-0 w-12 h-7 rounded-full transition-colors relative ${activo ? 'bg-accent' : 'bg-ink-soft/35'} disabled:opacity-60`}
    >
      <span className={`absolute top-0.5 left-0 w-6 h-6 rounded-full bg-white shadow transition-transform ${activo ? 'translate-x-5' : 'translate-x-0.5'}`} />
    </button>
  )
}

function Preferencias({ onCambio }) {
  const [p, setP] = useState(null)
  const [abierto, setAbierto] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [mensaje, setMensaje] = useState('')

  const cargar = useCallback(async () => {
    try {
      setP(await api.preferenciasAvisos())
    } catch {
      setP(null)
    }
  }, [])
  useEffect(() => {
    cargar()
  }, [cargar])

  if (!p) return null

  const guardar = async (cambio) => {
    setOcupado(true)
    setMensaje('')
    try {
      setP(await api.guardarPreferenciasAvisos(cambio))
      onCambio?.()
    } catch (e) {
      setMensaje(e?.message || 'No se pudo guardar. Intenta de nuevo.')
    } finally {
      setOcupado(false)
    }
  }

  const cambiarTipo = (t, campo, valor) =>
    guardar({ tipos: { [t.id]: { push: campo === 'push' ? valor : t.push, correo: campo === 'correo' ? valor : t.correo } } })

  const probar = async () => {
    setOcupado(true)
    setMensaje('')
    try {
      const r = await api.probarAvisos()
      const partes = []
      partes.push(r.push > 0 ? 'Llegó al celular.' : 'No hay celular con avisos activados.')
      partes.push(r.correo ? 'Salió el correo.' : 'El correo no salió (revisa la configuración).')
      setMensaje(partes.join(' '))
      await cargar()
    } catch (e) {
      setMensaje(e?.message || 'No se pudo enviar la prueba.')
    } finally {
      setOcupado(false)
    }
  }

  const activarEnEsteCelular = async () => {
    setOcupado(true)
    setMensaje('')
    try {
      await activarPush()
      setMensaje('Listo: los avisos llegarán a este celular.')
      await cargar()
    } catch (e) {
      setMensaje(e?.message || 'No se pudieron activar. Revisa los permisos del navegador.')
    } finally {
      setOcupado(false)
    }
  }

  const silenciado = Boolean(p.silenciado_hasta)
  const { canales } = p

  return (
    <div className="mt-4 border-t border-line pt-3">
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        className="w-full flex items-center gap-2 min-h-11 text-left"
      >
        <Icono icono={silenciado ? BellOff : Bell} tam="md" className="text-accent" />
        <span className="flex-1 text-sm font-semibold">Qué te avisa y cuándo</span>
        <Icono icono={ChevronDown} tam="sm" className={`text-ink-soft transition-transform ${abierto ? 'rotate-180' : ''}`} />
      </button>

      {abierto && (
        <div className="space-y-4" data-testid="preferencias-avisos">
          <ul className="text-xs space-y-1">
            <li data-testid="canal-push">
              {canales.push_activo ? 'Celular: activado.' : 'Celular: sin activar. Actívalo en el dispositivo donde quieras recibirlos.'}
            </li>
            <li data-testid="canal-correo">
              {canales.correo_configurado ? 'Correo: configurado.' : 'Correo: sin configurar (faltan ADMIN_EMAIL o RESEND_API_KEY).'}
            </li>
          </ul>
          {canales.correo_error && (
            <p className="text-xs rounded-xl bg-danger-soft px-3 py-2" role="alert" data-testid="error-correo">
              <b>El correo no está llegando.</b> {canales.correo_error}
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            {!canales.push_activo && pushSoportado() && (
              <Boton tam="sm" icono={Bell} disabled={ocupado} onClick={activarEnEsteCelular}>
                Activar en este celular
              </Boton>
            )}
            <Boton tam="sm" variante="secundario" disabled={ocupado} onClick={probar}>
              Enviar aviso de prueba
            </Boton>
          </div>
          {mensaje && (
            <p className="text-xs" role="status">
              {mensaje}
            </p>
          )}

          <div>
            <p className="text-xs text-ink-soft mb-1.5">
              Máximo {p.max_por_hora} avisos por hora; si hay más, llegan agrupados en uno solo.
            </p>
            <ul className="divide-y divide-line">
              {p.tipos.map((t) => (
                <li key={t.id} className="py-2 flex items-center gap-3" data-testid={`pref-${t.id}`}>
                  <span className="flex-1 text-sm">{t.etiqueta}</span>
                  <label className="flex items-center gap-1.5 text-xs">
                    <span>Celular</span>
                    <Interruptor activo={t.push} disabled={ocupado} etiqueta={`${t.etiqueta}: avisar al celular`} onChange={(v) => cambiarTipo(t, 'push', v)} />
                  </label>
                  <label className="flex items-center gap-1.5 text-xs">
                    <span>Correo</span>
                    <Interruptor activo={t.correo} disabled={ocupado} etiqueta={`${t.etiqueta}: avisar por correo`} onChange={(v) => cambiarTipo(t, 'correo', v)} />
                  </label>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex-1">
              <p className="text-sm font-medium">Un resumen al día</p>
              <p className="text-xs text-ink-soft">En vez de un aviso por cada cosa, uno solo al final del día.</p>
            </div>
            <Interruptor activo={p.resumen_diario} disabled={ocupado} etiqueta="Resumen diario en vez de avisos inmediatos" onChange={(v) => guardar({ resumen_diario: v })} />
          </div>

          <div>
            <p className="text-sm font-medium">Silenciar avisos</p>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {[1, 8, 24].map((h) => (
                <Chip key={h} disabled={ocupado} onClick={() => guardar({ silenciar_horas: h })}>
                  {h === 24 ? '1 día' : `${h} ${h === 1 ? 'hora' : 'horas'}`}
                </Chip>
              ))}
              {silenciado && (
                <Chip activo disabled={ocupado} onClick={() => guardar({ silenciar_horas: 0 })}>
                  Quitar silencio
                </Chip>
              )}
            </div>
            {silenciado && (
              <p className="text-xs text-ink-soft mt-1.5" data-testid="silencio-activo">
                Silenciado hasta {fechaCorta(p.silenciado_hasta)}. La actividad sigue apareciendo aquí.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ActividadAvisos() {
  const [datos, setDatos] = useState(null)
  const [tipo, setTipo] = useState('')
  const [estado, setEstado] = useState('cargando') // cargando | ok | error

  const cargar = useCallback(async () => {
    try {
      const d = await api.actividadAvisos({ tipo, por_pagina: 30 })
      setDatos(d)
      setEstado('ok')
    } catch {
      setEstado('error')
    }
  }, [tipo])

  useEffect(() => {
    cargar()
  }, [cargar])

  if (estado === 'error') return null // el resto del panel sigue funcionando
  if (estado === 'cargando' || !datos) {
    return (
      <p className="mx-6 mt-4 text-sm text-ink-soft" role="status">
        Cargando actividad…
      </p>
    )
  }

  const c = datos.contadores
  const tipos = datos.tipos || []

  return (
    <section className="mx-5 mt-4" aria-labelledby="actividad-titulo" data-testid="actividad-reciente">
      <h2 id="actividad-titulo" className="t-kicker text-ink-soft flex items-center gap-1.5 mb-1">
        <Icono icono={Bell} tam="sm" /> Actividad reciente
      </h2>
      <Tarjeta className="px-4 py-4">
        <div className="grid grid-cols-2 gap-3 text-center">
          <div>
            <p className="text-2xl font-bold tabular-nums" data-testid="actividad-hoy">{c.total_hoy}</p>
            <p className="text-xs text-ink-soft">hoy</p>
          </div>
          <div>
            <p className="text-2xl font-bold tabular-nums" data-testid="actividad-7d">{c.total_7d}</p>
            <p className="text-xs text-ink-soft">últimos 7 días</p>
          </div>
        </div>

        <div className="mt-4">
          <BarrasRegistros serie={datos.registros_por_dia || []} />
        </div>

        <div className="mt-4">
          <label htmlFor="filtro-actividad" className="text-xs text-ink-soft">
            Filtrar por tipo
          </label>
          <select id="filtro-actividad" value={tipo} onChange={(e) => setTipo(e.target.value)} className="mt-1 w-full">
            <option value="">Todos los tipos</option>
            {tipos.map((t) => (
              <option key={t.id} value={t.id}>
                {t.etiqueta}
                {c.por_tipo?.[t.id]?.dias7 ? ` (${c.por_tipo[t.id].dias7} en 7 días)` : ''}
              </option>
            ))}
          </select>
        </div>

        {datos.items.length === 0 ? (
          <p className="text-sm text-ink-soft mt-4" data-testid="actividad-vacia">
            Todavía no hay actividad{tipo ? ' de este tipo' : ''}. Cuando alguien se registre o pase algo importante, aparecerá aquí.
          </p>
        ) : (
          <ul className="divide-y divide-line mt-3" data-testid="actividad-lista">
            {datos.items.map((e) => (
              <li key={e.id} className="py-2.5 flex items-start gap-3" data-testid={`evento-${e.id}`}>
                <Icono icono={ICONO_TIPO[e.tipo] || Bell} tam="md" className="mt-0.5 text-accent" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium break-words">{e.resumen}</p>
                  {e.email && <p className="text-xs text-ink-soft break-all">{e.email}</p>}
                  <p className="text-xs text-ink-soft">
                    {e.etiqueta} · {fechaCorta(e.creado_en)}
                    {AVISO_TEXTO[e.aviso] ? ` · ${AVISO_TEXTO[e.aviso]}` : ''}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
        {datos.total > datos.items.length && (
          <p className="text-xs text-ink-soft mt-2">
            Mostrando los {datos.items.length} más recientes de {datos.total}.
          </p>
        )}

        <Preferencias onCambio={cargar} />
      </Tarjeta>
    </section>
  )
}
