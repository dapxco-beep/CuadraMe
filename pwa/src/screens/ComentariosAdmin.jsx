import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, ArrowLeft, ChevronDown, Download, FileText, Lock, Search } from 'lucide-react'
import { EstadoVacio } from '../brand/Marca'
import Icono from '../components/Icono'
import { Boton, Campo, Chip, Tarjeta } from '../components/ui'
import { useDialogos } from '../lib/DialogosContext'
import { api } from '../lib/api'
import { ESTADOS_ADMIN, TIPOS_PANEL, etiquetaEstado, fechaCorta, tipoPorId } from '../lib/opinion'
import { useVolver } from '../lib/useVolver'

// Panel del administrador del buzón de opinión. El servidor decide (404 a cualquier otra persona);
// esta pantalla solo muestra lo que llega. Primero lo nuevo y los problemas (así llegan ordenados).
const POR_PAGINA = 30

function Fila({ c, marcado, onMarcar, abierto, onAbrir, onGuardado }) {
  const { avisar } = useDialogos()
  const [estado, setEstado] = useState(c.estado)
  const [nota, setNota] = useState(c.nota_admin || '')
  const [respuesta, setRespuesta] = useState(c.respuesta_publica || '')
  const [guardando, setGuardando] = useState(false)
  const t = tipoPorId(c.tipo)

  const descargarMuestra = async () => {
    try {
      await api.descargarMuestraBanco(c.id, c.adjunto_nombre)
    } catch (e) {
      avisar(e?.message || 'No se pudo descargar el archivo')
    }
  }

  const guardar = async () => {
    setGuardando(true)
    try {
      const nuevo = await api.cambiarComentario(c.id, { estado, nota_admin: nota, respuesta_publica: respuesta })
      onGuardado(nuevo)
      avisar('Cambios guardados', 'info')
    } catch (e) {
      avisar(e?.message || 'No se pudo guardar')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <li className="px-4 py-3" data-testid={`comentario-${c.id}`}>
      <div className="flex items-start gap-3">
        {c.estado === 'nuevo' && (
          <input
            type="checkbox"
            checked={marcado}
            onChange={(e) => onMarcar(c.id, e.target.checked)}
            aria-label={`Seleccionar comentario de ${c.email || 'una persona'}`}
            className="mt-1 w-5 h-5 accent-[var(--c-accent)] shrink-0"
          />
        )}
        <button
          type="button"
          onClick={onAbrir}
          aria-expanded={abierto}
          className="flex-1 min-w-0 text-left min-h-11"
        >
          <span className="flex items-center gap-2 flex-wrap t-apoyo">
            <span aria-hidden="true">{t.emoji}</span>
            <span className="font-semibold text-ink">{t.etiqueta}</span>
            <span
              className={`text-xs font-semibold rounded-full px-2 py-0.5 ${
                c.estado === 'nuevo' ? 'bg-accent-soft text-accent' : 'bg-paper border border-line text-ink-soft'
              }`}
            >
              {etiquetaEstado(c.estado)}
            </span>
            <span>{fechaCorta(c.creado_en)}</span>
          </span>
          <span className={`block t-cuerpo mt-1 break-words whitespace-pre-line ${abierto ? '' : 'line-clamp-2'}`}>{c.mensaje}</span>
        </button>
        <Icono icono={ChevronDown} tam="sm" className={`mt-2 text-ink-soft transition-transform ${abierto ? 'rotate-180' : ''}`} />
      </div>

      {abierto && (
        <div className="mt-3 space-y-3 sm:ml-8">
          <dl className="t-apoyo grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
            <dt>Correo</dt>
            <dd className="break-all">
              {c.email || '—'} {c.puede_contactar ? '(puede contactarse)' : '(prefiere no ser contactado)'}
            </dd>
            <dt>Pantalla</dt>
            <dd>{c.pantalla || '—'}</dd>
            <dt>Dispositivo</dt>
            <dd>{[c.dispositivo, c.version_app].filter(Boolean).join(' · ') || '—'}</dd>
            {c.banco && (
              <>
                <dt>Banco</dt>
                <dd className="break-words">{c.banco}</dd>
              </>
            )}
          </dl>
          {c.tiene_adjunto && (
            <Boton variante="secundario" tam="sm" icono={FileText} onClick={descargarMuestra}>
              Descargar muestra ({c.adjunto_nombre})
            </Boton>
          )}

          <Campo etiqueta="Estado">
            {(props) => (
              <select {...props} value={estado} onChange={(e) => setEstado(e.target.value)}>
                {ESTADOS_ADMIN.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.etiqueta}
                  </option>
                ))}
              </select>
            )}
          </Campo>
          <Campo etiqueta="Nota interna" ayuda="Solo la ves tú.">
            {(props) => <textarea {...props} rows={2} maxLength={2000} value={nota} onChange={(e) => setNota(e.target.value)} />}
          </Campo>
          <Campo etiqueta="Respuesta para la persona" ayuda="Ella la verá en «Tu opinión cuenta».">
            {(props) => (
              <textarea {...props} rows={3} maxLength={1000} value={respuesta} onChange={(e) => setRespuesta(e.target.value)} />
            )}
          </Campo>
          <Boton tam="sm" cargando={guardando} onClick={guardar}>
            Guardar cambios
          </Boton>
        </div>
      )}
    </li>
  )
}

export default function ComentariosAdmin() {
  const volver = useVolver('/salud-negocio')
  const { avisar } = useDialogos()
  const [vista, setVista] = useState('cargando') // cargando | ok | prohibido | error
  const [datos, setDatos] = useState(null)
  const [items, setItems] = useState([])
  const [estado, setEstado] = useState('')
  const [tipo, setTipo] = useState('')
  const [buscar, setBuscar] = useState('')
  const [consulta, setConsulta] = useState('')
  const [pagina, setPagina] = useState(1)
  const [abierto, setAbierto] = useState(null)
  const [marcados, setMarcados] = useState([])
  const [trabajando, setTrabajando] = useState(false)
  const ultima = useRef(0)

  // Búsqueda con pausa corta para no pedir en cada tecla.
  useEffect(() => {
    const t = setTimeout(() => setConsulta(buscar.trim()), 350)
    return () => clearTimeout(t)
  }, [buscar])

  const cargar = useCallback(
    async (n = 1, { reiniciar = true } = {}) => {
      const id = ++ultima.current
      try {
        const r = await api.comentariosAdmin({ estado, tipo, q: consulta, pagina: n, por_pagina: POR_PAGINA })
        if (id !== ultima.current) return
        setDatos(r)
        setItems((previos) => (reiniciar ? r.items : [...previos, ...r.items]))
        setPagina(n)
        setVista('ok')
      } catch (e) {
        if (id !== ultima.current) return
        setVista(e?.status === 404 ? 'prohibido' : 'error')
      }
    },
    [estado, tipo, consulta]
  )

  useEffect(() => {
    setMarcados([])
    cargar(1)
  }, [cargar])

  const encabezado = (
    <header className="px-5 pantalla-top pb-2 flex items-center gap-3 lg:max-w-3xl lg:mx-auto">
      <button
        type="button"
        onClick={volver}
        className="w-11 h-11 rounded-full bg-paper-raised border border-line flex items-center justify-center"
        aria-label="Volver"
      >
        <Icono icono={ArrowLeft} tam="md" />
      </button>
      <h1 className="text-xl font-semibold flex-1">Comentarios</h1>
    </header>
  )

  if (vista === 'prohibido') {
    return (
      <div className="flex-1 overflow-y-auto pb-6 screen-enter">
        {encabezado}
        <EstadoVacio icono={Lock} titulo="Esta pantalla no está disponible" texto="Solo la ve quien administra CuadraMe." />
      </div>
    )
  }
  if (vista === 'error') {
    return (
      <div className="flex-1 overflow-y-auto pb-6 screen-enter">
        {encabezado}
        <EstadoVacio icono={AlertTriangle} titulo="No se pudo cargar" texto="Intenta de nuevo en un momento.">
          <Boton variante="suave" tam="sm" className="mt-4" onClick={() => cargar(1)}>
            Reintentar
          </Boton>
        </EstadoVacio>
      </div>
    )
  }
  if (vista === 'cargando' || !datos) {
    return (
      <div className="flex-1 overflow-y-auto pb-6 screen-enter">
        {encabezado}
        <p className="mx-6 mt-4 t-apoyo" role="status">
          Cargando…
        </p>
      </div>
    )
  }

  const marcarVistos = async () => {
    setTrabajando(true)
    try {
      await api.marcarComentariosVistos(marcados)
      avisar(`${marcados.length === 1 ? '1 comentario marcado' : `${marcados.length} comentarios marcados`} como visto`, 'info')
      setMarcados([])
      await cargar(1)
    } catch (e) {
      avisar(e?.message || 'No se pudo marcar')
    } finally {
      setTrabajando(false)
    }
  }

  const exportar = async () => {
    try {
      await api.exportarComentariosCSV()
    } catch (e) {
      avisar(e?.message || 'No se pudo descargar')
    }
  }

  const alGuardar = (nuevo) => {
    setItems((l) => l.map((c) => (c.id === nuevo.id ? nuevo : c)))
    cargar(1) // refresca los conteos y el orden
  }
  const hayMas = datos.total > pagina * POR_PAGINA
  const alternar = (id, on) => setMarcados((m) => (on ? [...new Set([...m, id])] : m.filter((x) => x !== id)))

  return (
    <div className="flex-1 overflow-y-auto pb-8 screen-enter">
      {encabezado}
      <div className="lg:max-w-3xl lg:mx-auto">
        <Tarjeta className="mx-5 mt-3 px-4 py-4" data-testid="resumen-comentarios">
          <p className="t-kicker text-ink-soft">Por estado</p>
          <div className="grid grid-cols-5 gap-2 mt-2 text-center">
            {ESTADOS_ADMIN.map((e) => (
              <div key={e.id}>
                <p className="text-xl font-bold tabular-nums" data-testid={`conteo-${e.id}`}>
                  {datos.por_estado?.[e.id] ?? 0}
                </p>
                <p className="text-xs text-ink-soft">{e.etiqueta}</p>
              </div>
            ))}
          </div>
          <p className="t-kicker text-ink-soft mt-4">Por tipo</p>
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 mt-2 text-center">
            {TIPOS_PANEL.map((t) => (
              <div key={t.id}>
                <p className="text-lg font-bold tabular-nums">
                  <span aria-hidden="true">{t.emoji}</span> {datos.por_tipo?.[t.id] ?? 0}
                </p>
                <p className="text-xs text-ink-soft">{t.corta || t.etiqueta}</p>
              </div>
            ))}
          </div>
        </Tarjeta>

        <section className="mx-5 mt-4 space-y-3" aria-label="Filtros">
          <Campo etiqueta="Buscar">
            {(props) => (
              <div className="relative">
                <input
                  {...props}
                  type="search"
                  value={buscar}
                  onChange={(e) => setBuscar(e.target.value)}
                  placeholder="Palabra, correo o pantalla"
                  autoComplete="off"
                  enterKeyHint="search"
                />
                <Icono icono={Search} tam="sm" className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-soft pointer-events-none" />
              </div>
            )}
          </Campo>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar por estado">
            <Chip activo={estado === ''} onClick={() => setEstado('')}>
              Todos
            </Chip>
            {ESTADOS_ADMIN.map((e) => (
              <Chip key={e.id} activo={estado === e.id} onClick={() => setEstado(estado === e.id ? '' : e.id)}>
                {e.etiqueta}
              </Chip>
            ))}
          </div>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar por tipo">
            {TIPOS_PANEL.map((t) => (
              <Chip key={t.id} activo={tipo === t.id} onClick={() => setTipo(tipo === t.id ? '' : t.id)}>
                <span aria-hidden="true">{t.emoji}</span> {t.corta || t.etiqueta}
              </Chip>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <Boton variante="secundario" tam="sm" icono={Download} onClick={exportar}>
              Exportar CSV
            </Boton>
            <Boton variante="suave" tam="sm" disabled={marcados.length === 0 || trabajando} onClick={marcarVistos}>
              {marcados.length > 0 ? `Marcar ${marcados.length} como vistos` : 'Marcar como vistos'}
            </Boton>
          </div>
        </section>

        <section className="mx-5 mt-4" aria-labelledby="lista-com">
          <h2 id="lista-com" className="t-kicker text-ink-soft mb-2">
            {datos.total === 1 ? '1 comentario' : `${datos.total} comentarios`}
          </h2>
          {items.length === 0 ? (
            <p className="t-apoyo" data-testid="sin-comentarios">
              No hay comentarios con esos filtros.
            </p>
          ) : (
            <ul className="tarjeta-lista divide-y divide-line">
              {items.map((c) => (
                <Fila
                  key={c.id}
                  c={c}
                  marcado={marcados.includes(c.id)}
                  onMarcar={alternar}
                  abierto={abierto === c.id}
                  onAbrir={() => setAbierto(abierto === c.id ? null : c.id)}
                  onGuardado={alGuardar}
                />
              ))}
            </ul>
          )}
          {hayMas && (
            <Boton variante="suave" tam="sm" className="mt-3" onClick={() => cargar(pagina + 1, { reiniciar: false })}>
              Ver más
            </Boton>
          )}
        </section>
      </div>
    </div>
  )
}
